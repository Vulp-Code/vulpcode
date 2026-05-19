"""Tests for InternalLLMAgenticProvider (text-based tool calling shim)."""
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from vulpcode.providers import Message, ToolCall
from vulpcode.providers.base import ProviderError
from vulpcode.providers.internal_llm_agentic import InternalLLMAgenticProvider


# ---------------------------------------------------------------------------
# Capability flags
# ---------------------------------------------------------------------------


def test_supports_tools_true():
    p = InternalLLMAgenticProvider()
    assert p.supports_tools() is True


def test_supports_vision_false():
    p = InternalLLMAgenticProvider()
    assert p.supports_vision() is False


# ---------------------------------------------------------------------------
# _flatten
# ---------------------------------------------------------------------------


def test_flatten_converts_tool_role_to_xml_envelope():
    msgs = [
        Message(role="user", content="call a tool"),
        Message(
            role="assistant",
            content="<vulp:tool .../>",
        ),
        Message(
            role="tool",
            tool_call_id="tt-abc123",
            name="WritePy",
            content="hello.py written",
        ),
    ]
    out = InternalLLMAgenticProvider()._flatten(msgs)
    tool_result_msg = next(m for m in out if m["role"] == "user" and "vulp:tool_result" in m["content"])
    assert 'name="WritePy"' in tool_result_msg["content"]
    assert 'id="tt-abc123"' in tool_result_msg["content"]
    assert 'is_error="false"' in tool_result_msg["content"]
    assert "hello.py written" in tool_result_msg["content"]


def test_flatten_marks_error_result():
    msgs = [
        Message(
            role="tool",
            tool_call_id="tt-err",
            name="WritePy",
            content="Error: SyntaxError at line 3",
        ),
    ]
    out = InternalLLMAgenticProvider()._flatten(msgs)
    assert len(out) == 1
    assert 'is_error="true"' in out[0]["content"]
    assert "SyntaxError at line 3" in out[0]["content"]


def test_flatten_skips_empty_assistant_text():
    msgs = [
        Message(role="assistant", content=""),
        Message(role="user", content="hi"),
    ]
    out = InternalLLMAgenticProvider()._flatten(msgs)
    assert len(out) == 1
    assert out[0]["content"] == "hi"


def test_flatten_keeps_assistant_text():
    msgs = [Message(role="assistant", content="some reply")]
    out = InternalLLMAgenticProvider()._flatten(msgs)
    assert out == [{"role": "assistant", "content": "some reply"}]


# ---------------------------------------------------------------------------
# _build_system
# ---------------------------------------------------------------------------


def test_build_system_appends_protocol_help():
    p = InternalLLMAgenticProvider()
    result = p._build_system("You are helpful.", [{"name": "Read", "description": "Reads a file"}])
    assert "You are helpful." in result
    assert "Tool calling protocol" in result
    assert "Read" in result


def test_build_system_without_user_system():
    p = InternalLLMAgenticProvider()
    result = p._build_system(None, [])
    assert "Tool calling protocol" in result
    assert not result.startswith("\n\n")


# ---------------------------------------------------------------------------
# stream — error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_raises_without_endpoint():
    p = InternalLLMAgenticProvider(base_url=None, user_uuid="u-123")
    with pytest.raises(ProviderError, match="base_url"):
        async for _ in p.stream(
            messages=[Message(role="user", content="hi")],
            tools=[],
            model="internal-llm-agentic",
        ):
            pass


@pytest.mark.asyncio
async def test_stream_raises_without_user_uuid():
    p = InternalLLMAgenticProvider(base_url="http://x/chat", user_uuid=None)
    with pytest.raises(ProviderError, match="user_uuid"):
        async for _ in p.stream(
            messages=[Message(role="user", content="hi")],
            tools=[],
            model="internal-llm-agentic",
        ):
            pass


# ---------------------------------------------------------------------------
# stream — happy paths (mocked HTTP)
# ---------------------------------------------------------------------------


def _make_fake_resp(payload):
    r = AsyncMock()
    r.status_code = 200
    r.text = ""
    r.json = lambda: payload
    return r


@pytest.mark.asyncio
async def test_stream_emits_text_when_no_tool_blocks():
    p = InternalLLMAgenticProvider(
        base_url="http://x/chat", user_uuid="u-123", retry_delay=0.01
    )

    async def fake_post(*args, **kwargs):
        return _make_fake_resp({"data": "Just a plain text reply."})

    with patch.object(p._client, "post", new=fake_post):
        chunks = []
        async for c in p.stream(
            messages=[Message(role="user", content="hello")],
            tools=[],
            model="internal-llm-agentic",
        ):
            chunks.append(c)

    text_chunks = [c for c in chunks if c.type == "text"]
    assert any("plain text reply" in (c.delta or "") for c in text_chunks)
    stop_chunks = [c for c in chunks if c.type == "stop"]
    assert stop_chunks
    assert stop_chunks[0].stop_reason == "end_turn"


@pytest.mark.asyncio
async def test_stream_emits_tool_call_for_each_block():
    p = InternalLLMAgenticProvider(
        base_url="http://x/chat", user_uuid="u-123", retry_delay=0.01
    )

    raw_response = (
        'Calling two tools:\n'
        '<vulp:tool name="WritePy">\n'
        '  <vulp:arg name="path">hello.py</vulp:arg>\n'
        '  <vulp:content name="content">\nprint("hi")\n</vulp:content>\n'
        '</vulp:tool>\n'
        '<vulp:tool name="Read">\n'
        '  <vulp:arg name="path">hello.py</vulp:arg>\n'
        '</vulp:tool>\n'
    )

    async def fake_post(*args, **kwargs):
        return _make_fake_resp({"data": raw_response})

    with patch.object(p._client, "post", new=fake_post):
        chunks = []
        async for c in p.stream(
            messages=[Message(role="user", content="do it")],
            tools=[],
            model="internal-llm-agentic",
        ):
            chunks.append(c)

    tool_chunks = [c for c in chunks if c.type == "tool_call"]
    assert len(tool_chunks) == 2
    names = [c.tool_call.name for c in tool_chunks]
    assert "WritePy" in names
    assert "Read" in names

    stop_chunks = [c for c in chunks if c.type == "stop"]
    assert stop_chunks[0].stop_reason == "tool_use"


@pytest.mark.asyncio
async def test_stream_retries_on_data_null():
    p = InternalLLMAgenticProvider(
        base_url="http://x/chat",
        user_uuid="u-123",
        max_retries=3,
        retry_delay=0.01,
    )

    call_count = {"n": 0}

    async def fake_post(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] < 3:
            return _make_fake_resp({"data": None})
        return _make_fake_resp({"data": "finally here"})

    with patch.object(p._client, "post", new=fake_post):
        chunks = []
        async for c in p.stream(
            messages=[Message(role="user", content="hi")],
            tools=[],
            model="internal-llm-agentic",
        ):
            chunks.append(c)

    assert call_count["n"] == 3
    assert any("finally here" in (c.delta or "") for c in chunks if c.type == "text")


@pytest.mark.asyncio
async def test_stream_raises_after_all_retries_exhausted():
    p = InternalLLMAgenticProvider(
        base_url="http://x/chat",
        user_uuid="u-123",
        max_retries=2,
        retry_delay=0.01,
    )

    async def fake_post(*args, **kwargs):
        return _make_fake_resp({"data": None})

    with patch.object(p._client, "post", new=fake_post):
        with pytest.raises(ProviderError, match="data=null"):
            async for _ in p.stream(
                messages=[Message(role="user", content="hi")],
                tools=[],
                model="internal-llm-agentic",
            ):
                pass


# ---------------------------------------------------------------------------
# Temperature default
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_default_temperature_is_0_3():
    """Temperature defaults to 0.3 for better protocol adherence."""
    p = InternalLLMAgenticProvider(
        base_url="http://x/chat", user_uuid="u-123", retry_delay=0.01
    )

    captured: list[dict] = []

    async def fake_post(url, *, headers, json, **kwargs):
        captured.append(json)
        return _make_fake_resp({"data": "ok"})

    with patch.object(p._client, "post", new=fake_post):
        async for _ in p.stream(
            messages=[Message(role="user", content="hi")],
            tools=[],
            model="internal-llm-agentic",
        ):
            pass

    assert captured
    config = captured[0]["data"]["config"]
    assert config["temperature"] == pytest.approx(0.3)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def test_registry_recognizes_internal_llm_agentic():
    from vulpcode.providers import build_provider, list_provider_names

    assert "internal-llm-agentic" in list_provider_names()
    p = build_provider(
        "internal-llm-agentic",
        {"base_url": "http://x/chat", "user_uuid": "u"},
    )
    assert isinstance(p, InternalLLMAgenticProvider)
    assert p.endpoint == "http://x/chat"
    assert p.user_uuid == "u"


@pytest.mark.asyncio
async def test_list_models():
    p = InternalLLMAgenticProvider()
    assert await p.list_models() == ["internal-llm-agentic"]


# ---------------------------------------------------------------------------
# 60s timeout safety
# ---------------------------------------------------------------------------


def test_default_timeout_below_endpoint_wall():
    """Client timeout must be under the 60s endpoint wall so we catch it first."""
    p = InternalLLMAgenticProvider()
    assert p.timeout < 60.0


@pytest.mark.asyncio
async def test_timeout_retries_with_halved_max_tokens():
    """A ReadTimeout halves max_tokens on the next attempt."""
    p = InternalLLMAgenticProvider(
        base_url="http://x/chat",
        user_uuid="u-123",
        max_retries=3,
        retry_delay=0.01,
    )

    captured: list[dict] = []
    state = {"calls": 0}

    async def fake_post(url, *, headers, json, **kwargs):
        captured.append({"max_tokens": json["data"]["config"]["max_tokens"]})
        state["calls"] += 1
        if state["calls"] < 3:
            raise httpx.ReadTimeout("simulated 60s wall hit")
        return _make_fake_resp({"data": "recovered"})

    with patch.object(p._client, "post", new=fake_post):
        chunks = []
        async for c in p.stream(
            messages=[Message(role="user", content="hi")],
            tools=[],
            model="internal-llm-agentic",
            max_tokens=4000,
        ):
            chunks.append(c)

    assert state["calls"] == 3
    # 4000 -> 2000 -> 1000 (halved on each timeout).
    assert captured[0]["max_tokens"] == 4000
    assert captured[1]["max_tokens"] == 2000
    assert captured[2]["max_tokens"] == 1000
    assert any("recovered" in (c.delta or "") for c in chunks if c.type == "text")


@pytest.mark.asyncio
async def test_timeout_max_tokens_floor_respected():
    """max_tokens halving never goes below the configured floor."""
    p = InternalLLMAgenticProvider(
        base_url="http://x/chat",
        user_uuid="u-123",
        max_retries=5,
        retry_delay=0.01,
    )

    captured: list[int] = []

    async def fake_post(url, *, headers, json, **kwargs):
        captured.append(json["data"]["config"]["max_tokens"])
        if len(captured) < 5:
            raise httpx.ReadTimeout("still timing out")
        return _make_fake_resp({"data": "ok"})

    with patch.object(p._client, "post", new=fake_post):
        async for _ in p.stream(
            messages=[Message(role="user", content="hi")],
            tools=[],
            model="internal-llm-agentic",
            max_tokens=800,
        ):
            pass

    # 800 -> 500 (floor) -> 500 -> 500 -> 500
    floor = InternalLLMAgenticProvider._MIN_MAX_TOKENS
    assert captured[0] == 800
    assert all(v >= floor for v in captured[1:])


@pytest.mark.asyncio
async def test_timeout_exhausts_retries_raises_provider_error():
    p = InternalLLMAgenticProvider(
        base_url="http://x/chat",
        user_uuid="u-123",
        max_retries=2,
        retry_delay=0.01,
    )

    async def fake_post(*args, **kwargs):
        raise httpx.ReadTimeout("permanent timeout")

    with patch.object(p._client, "post", new=fake_post):
        with pytest.raises(ProviderError, match="timeout"):
            async for _ in p.stream(
                messages=[Message(role="user", content="hi")],
                tools=[],
                model="internal-llm-agentic",
            ):
                pass


# ---------------------------------------------------------------------------
# 128k input budgeting
# ---------------------------------------------------------------------------


def test_estimate_tokens_char_over_four():
    assert InternalLLMAgenticProvider._estimate_tokens("") == 0
    assert InternalLLMAgenticProvider._estimate_tokens("abcd") == 1
    assert InternalLLMAgenticProvider._estimate_tokens("a" * 400) == 100


def test_fit_budget_under_limit_returns_unchanged():
    p = InternalLLMAgenticProvider(max_input_tokens=10_000)
    msgs = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
    ]
    out, note = p._fit_budget(msgs)
    assert out == msgs
    assert note is None


def test_fit_budget_truncates_old_tool_results():
    """Large <vulp:tool_result> bodies in the middle get truncated."""
    p = InternalLLMAgenticProvider(max_input_tokens=2_000)
    big_body = "X" * 20_000
    big_envelope = (
        '<vulp:tool_result name="Read" id="tt-1" is_error="false">\n'
        f"{big_body}\n"
        "</vulp:tool_result>"
    )
    # Need a long enough tail so first user/system stay outside the middle window.
    msgs = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "do it"},
        {"role": "user", "content": big_envelope},
        {"role": "assistant", "content": "ok"},
        {"role": "user", "content": "more"},
        {"role": "assistant", "content": "fine"},
        {"role": "user", "content": "ok"},
        {"role": "assistant", "content": "x"},
        {"role": "user", "content": "y"},
    ]
    out, note = p._fit_budget(msgs)
    truncated = next(m for m in out if "<vulp:tool_result" in m["content"])
    assert len(truncated["content"]) < len(big_envelope)
    assert "truncated to fit context window" in truncated["content"]
    assert "</vulp:tool_result>" in truncated["content"]
    assert note and "truncated" in note


def test_fit_budget_drops_oldest_when_truncation_insufficient():
    """When even truncation isn't enough, oldest middle messages get dropped."""
    p = InternalLLMAgenticProvider(max_input_tokens=200)
    big = "A" * 5_000  # ~1250 tokens each; well over 200-token limit.
    msgs = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "first"},
        # --- middle: candidates for dropping (n - _PRESERVE_TAIL = 12-6 = 6) ---
        {"role": "assistant", "content": big},
        {"role": "user", "content": big},
        {"role": "assistant", "content": big},
        {"role": "user", "content": big},
        # --- tail: last 6 always preserved ---
        {"role": "assistant", "content": "tail-1"},
        {"role": "user", "content": "tail-2"},
        {"role": "assistant", "content": "tail-3"},
        {"role": "user", "content": "tail-4"},
        {"role": "assistant", "content": "tail-5"},
        {"role": "user", "content": "recent-3"},
    ]
    out, note = p._fit_budget(msgs)
    # System + first user always preserved.
    assert out[0]["content"] == "sys"
    assert any(m["content"] == "first" for m in out)
    # Tail preserved.
    assert any("recent-3" in m["content"] for m in out)
    # Placeholder inserted.
    assert any("omitted to fit" in m["content"] for m in out)
    assert note and "dropped" in note


@pytest.mark.asyncio
async def test_stream_emits_budget_notice_when_trimmed():
    p = InternalLLMAgenticProvider(
        base_url="http://x/chat",
        user_uuid="u-123",
        max_input_tokens=500,
        retry_delay=0.01,
    )
    huge = "Q" * 50_000
    messages = [
        Message(role="user", content="task"),
        Message(role="assistant", content=huge),
        Message(role="user", content="more"),
        Message(role="assistant", content=huge),
        Message(role="user", content="now what"),
    ]

    async def fake_post(*args, **kwargs):
        return _make_fake_resp({"data": "answer"})

    with patch.object(p._client, "post", new=fake_post):
        chunks = []
        async for c in p.stream(
            messages=messages,
            tools=[],
            model="internal-llm-agentic",
        ):
            chunks.append(c)

    text_chunks = [c for c in chunks if c.type == "text"]
    joined = "".join(c.delta or "" for c in text_chunks)
    assert "[context optimized:" in joined
    assert "answer" in joined


# ---------------------------------------------------------------------------
# Content store + preview caching
# ---------------------------------------------------------------------------


def test_flatten_caches_large_tool_result_and_emits_preview():
    """Large tool results get stored and rendered as a cached preview envelope."""
    from vulpcode.providers._content_store import ContentStore

    store = ContentStore()
    p = InternalLLMAgenticProvider(
        preview_threshold=200,
        preview_head_lines=2,
        preview_tail_lines=1,
        content_store=store,
    )
    big_body = "\n".join(f"line {i}" for i in range(1, 101))
    msgs = [
        Message(
            role="tool",
            tool_call_id="tt-big",
            name="Read",
            content=big_body,
        )
    ]
    out = p._flatten(msgs)
    envelope = out[0]["content"]
    assert 'cached="true"' in envelope
    assert "Retrieve(cache_id='tt-big'" in envelope
    assert "line 1" in envelope  # head preview
    assert "line 100" in envelope  # tail preview
    assert "line 50" not in envelope  # middle omitted
    # Full body must be in the store.
    stored = store.get("tt-big")
    assert stored is not None
    assert stored.full_body == big_body
    assert stored.line_count == 100


def test_flatten_small_result_uses_plain_envelope():
    """Below the threshold, no caching, plain envelope."""
    from vulpcode.providers._content_store import ContentStore

    store = ContentStore()
    p = InternalLLMAgenticProvider(
        preview_threshold=10_000,
        content_store=store,
    )
    msgs = [
        Message(
            role="tool",
            tool_call_id="tt-small",
            name="Read",
            content="just a short result",
        )
    ]
    out = p._flatten(msgs)
    envelope = out[0]["content"]
    assert 'cached="true"' not in envelope
    assert "just a short result" in envelope
    assert store.get("tt-small") is None


def test_flatten_caches_error_results_too():
    """An error result above the threshold still gets cached, with is_error=true."""
    from vulpcode.providers._content_store import ContentStore

    store = ContentStore()
    p = InternalLLMAgenticProvider(
        preview_threshold=50,
        preview_head_lines=1,
        preview_tail_lines=1,
        content_store=store,
    )
    err_body = "Error: " + ("\n".join(f"trace line {i}" for i in range(50)))
    msgs = [
        Message(
            role="tool",
            tool_call_id="tt-err",
            name="Read",
            content=err_body,
        )
    ]
    out = p._flatten(msgs)
    envelope = out[0]["content"]
    assert 'is_error="true"' in envelope
    assert 'cached="true"' in envelope
    stored = store.get("tt-err")
    assert stored is not None
    assert stored.is_error is True
    assert not stored.full_body.startswith("Error:")


# ---------------------------------------------------------------------------
# Auto-compact (Phase E)
# ---------------------------------------------------------------------------


def _msg(role: str, content: str) -> dict:
    return {"role": role, "content": content}


def test_needs_auto_compact_false_when_under_threshold():
    p = InternalLLMAgenticProvider(max_input_tokens=10_000, auto_compact_at=0.85)
    msgs = [_msg("system", "s"), _msg("user", "hi"), _msg("assistant", "ok")]
    assert p._needs_auto_compact(msgs) is False


def test_needs_auto_compact_false_when_not_enough_messages():
    """Need head(2) + min_middle(4) + tail(4) = 10 messages minimum."""
    p = InternalLLMAgenticProvider(max_input_tokens=100, auto_compact_at=0.1)
    msgs = [_msg("system", "s")] + [_msg("user", "x" * 1000) for _ in range(5)]
    assert p._needs_auto_compact(msgs) is False


def test_needs_auto_compact_true_when_long_and_over_threshold():
    p = InternalLLMAgenticProvider(max_input_tokens=1_000, auto_compact_at=0.5)
    msgs = (
        [_msg("system", "s"), _msg("user", "first")]
        + [_msg("assistant", "x" * 2000) for _ in range(6)]
        + [_msg("user", "z") for _ in range(4)]
    )
    assert p._needs_auto_compact(msgs) is True


@pytest.mark.asyncio
async def test_auto_compact_replaces_middle_with_summary():
    p = InternalLLMAgenticProvider(
        base_url="http://x/chat",
        user_uuid="u-1",
        retry_delay=0.01,
    )
    msgs = (
        [_msg("system", "s"), _msg("user", "do work")]
        + [_msg("assistant", f"step {i}") for i in range(6)]
        + [_msg("user", "tail-1"), _msg("assistant", "tail-2"),
           _msg("user", "tail-3"), _msg("assistant", "tail-4")]
    )

    async def fake_post(url, *, headers, json, **kwargs):
        # Verify only ONE summarization POST happens and it has the right shape.
        assert json["data"]["config"]["max_tokens"] == p._AUTO_COMPACT_MAX_TOKENS
        sys_msg = json["data"]["solicitacao"]["messages"][0]
        assert sys_msg["role"] == "system"
        assert "summarizer" in sys_msg["content"]
        return _make_fake_resp({"data": "Did A then B; touched foo.py; TODO bar."})

    with patch.object(p._client, "post", new=fake_post):
        new_msgs, note = await p._auto_compact(list(msgs))

    assert note and "auto-compacted" in note
    # System + first user preserved.
    assert new_msgs[0]["role"] == "system"
    assert new_msgs[1]["content"] == "do work"
    # Summary placeholder where the middle was.
    summary_msg = new_msgs[2]
    assert "Previous conversation summary" in summary_msg["content"]
    assert "Did A then B" in summary_msg["content"]
    # Last 4 preserved.
    assert new_msgs[-1]["content"] == "tail-4"
    assert new_msgs[-4]["content"] == "tail-1"


@pytest.mark.asyncio
async def test_auto_compact_falls_back_on_timeout():
    p = InternalLLMAgenticProvider(
        base_url="http://x/chat",
        user_uuid="u-1",
        retry_delay=0.01,
    )
    msgs = (
        [_msg("system", "s"), _msg("user", "first")]
        + [_msg("assistant", f"x{i}") for i in range(6)]
        + [_msg("user", "t") for _ in range(4)]
    )

    async def fake_post(*args, **kwargs):
        raise httpx.ReadTimeout("simulated")

    with patch.object(p._client, "post", new=fake_post):
        new_msgs, note = await p._auto_compact(list(msgs))

    assert note is None
    assert new_msgs == msgs  # untouched, fallback path


@pytest.mark.asyncio
async def test_auto_compact_falls_back_on_empty_response():
    p = InternalLLMAgenticProvider(
        base_url="http://x/chat", user_uuid="u-1", retry_delay=0.01
    )
    msgs = (
        [_msg("system", "s"), _msg("user", "first")]
        + [_msg("assistant", f"x{i}") for i in range(6)]
        + [_msg("user", "t") for _ in range(4)]
    )

    async def fake_post(*args, **kwargs):
        return _make_fake_resp({"data": None})

    with patch.object(p._client, "post", new=fake_post):
        new_msgs, note = await p._auto_compact(list(msgs))

    assert note is None
    assert new_msgs == msgs


@pytest.mark.asyncio
async def test_stream_triggers_auto_compact_when_enabled():
    p = InternalLLMAgenticProvider(
        base_url="http://x/chat",
        user_uuid="u-1",
        max_input_tokens=1_000,
        auto_compact=True,
        auto_compact_at=0.5,
        retry_delay=0.01,
    )
    # Pre-stuff a big conversation so the threshold trips.
    canon_msgs = (
        [Message(role="user", content="do it")]
        + [Message(role="assistant", content="x" * 2000) for _ in range(6)]
        + [
            Message(role="user", content="t1"),
            Message(role="assistant", content="t2"),
            Message(role="user", content="t3"),
        ]
    )

    call_count = {"n": 0}

    async def fake_post(url, *, headers, json, **kwargs):
        call_count["n"] += 1
        # First call should be the summarization; second the real turn.
        if call_count["n"] == 1:
            return _make_fake_resp({"data": "summary of earlier work"})
        return _make_fake_resp({"data": "final answer"})

    with patch.object(p._client, "post", new=fake_post):
        chunks = []
        async for c in p.stream(
            messages=canon_msgs,
            tools=[],
            model="internal-llm-agentic",
        ):
            chunks.append(c)

    assert call_count["n"] == 2
    text_chunks = "".join(c.delta or "" for c in chunks if c.type == "text")
    assert "auto-compacted" in text_chunks
    assert "final answer" in text_chunks


@pytest.mark.asyncio
async def test_stream_skips_auto_compact_when_disabled():
    p = InternalLLMAgenticProvider(
        base_url="http://x/chat",
        user_uuid="u-1",
        max_input_tokens=1_000,
        auto_compact=False,
        retry_delay=0.01,
    )
    canon_msgs = (
        [Message(role="user", content="do it")]
        + [Message(role="assistant", content="x" * 2000) for _ in range(6)]
        + [Message(role="user", content="t")] * 3
    )
    call_count = {"n": 0}

    async def fake_post(*args, **kwargs):
        call_count["n"] += 1
        return _make_fake_resp({"data": "ok"})

    with patch.object(p._client, "post", new=fake_post):
        async for _ in p.stream(
            messages=canon_msgs,
            tools=[],
            model="internal-llm-agentic",
        ):
            pass

    # Without auto_compact, only one POST (the real turn).
    assert call_count["n"] == 1


@pytest.mark.asyncio
async def test_max_input_tokens_configurable_via_registry():
    from vulpcode.providers import build_provider

    p = build_provider(
        "internal-llm-agentic",
        {
            "base_url": "http://x/chat",
            "user_uuid": "u",
            "max_input_tokens": 50_000,
            "timeout": 30.0,
        },
    )
    assert isinstance(p, InternalLLMAgenticProvider)
    assert p.max_input_tokens == 50_000
    assert p.timeout == 30.0
