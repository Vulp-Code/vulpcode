"""Tests for InternalLLMAgenticProvider (text-based tool calling shim)."""
from unittest.mock import AsyncMock, patch

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
    out = InternalLLMAgenticProvider._flatten(msgs)
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
    out = InternalLLMAgenticProvider._flatten(msgs)
    assert len(out) == 1
    assert 'is_error="true"' in out[0]["content"]
    assert "SyntaxError at line 3" in out[0]["content"]


def test_flatten_skips_empty_assistant_text():
    msgs = [
        Message(role="assistant", content=""),
        Message(role="user", content="hi"),
    ]
    out = InternalLLMAgenticProvider._flatten(msgs)
    assert len(out) == 1
    assert out[0]["content"] == "hi"


def test_flatten_keeps_assistant_text():
    msgs = [Message(role="assistant", content="some reply")]
    out = InternalLLMAgenticProvider._flatten(msgs)
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
