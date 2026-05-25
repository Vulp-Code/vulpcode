"""Tests for harness eviction and overflow-clip middleware."""
from __future__ import annotations

import sys
from typing import Any

from vulpcode.harness.eviction import (
    EvictionConfig,
    OverflowClipConfig,
    clip_tool_output,
    evict_messages,
)
from vulpcode.harness.state import LoopState
from vulpcode.providers.base import Message, ToolCall, Usage
from vulpcode.tools.base import ToolResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(messages: list[Message]) -> LoopState:
    return LoopState(messages=messages, usage=Usage(), iteration=0)


def _assistant(text: str = "", with_tool_call: bool = False) -> Message:
    tool_calls = (
        [ToolCall(id="tc1", name="Bash", arguments={"cmd": "ls"})]
        if with_tool_call
        else None
    )
    return Message(role="assistant", content=text, tool_calls=tool_calls)


def _tool_result(content: str = "ok") -> Message:
    return Message(role="tool", content=content, tool_call_id="tc1")


def _user(text: str = "hi") -> Message:
    return Message(role="user", content=text)


def _system(text: str = "system prompt") -> Message:
    return Message(role="system", content=text)


def _make_conversation(num_pairs: int, include_system: bool = True) -> list[Message]:
    """Build a conversation of assistant+tool_result pairs, optionally with a system message."""
    msgs: list[Message] = []
    if include_system:
        msgs.append(_system())
    msgs.append(_user())
    for i in range(num_pairs):
        msgs.append(_assistant(f"doing {i}", with_tool_call=True))
        msgs.append(_tool_result(f"result {i}"))
    return msgs


# ---------------------------------------------------------------------------
# Token counting
# ---------------------------------------------------------------------------


def test_count_tokens_fallback_without_tiktoken(monkeypatch: Any) -> None:
    """count_tokens falls back to max(1, len//4) when tiktoken is not importable."""
    import vulpcode.harness._tokens as _tok_mod
    from vulpcode.harness._tokens import count_tokens

    # Force the module to believe tiktoken is unavailable and there is no cached encoding.
    monkeypatch.setattr(_tok_mod, "_enc", None)
    monkeypatch.setattr(_tok_mod, "_tiktoken_unavailable", False)
    # Simulate import error by removing tiktoken from sys.modules and shadowing it.
    monkeypatch.setitem(sys.modules, "tiktoken", None)  # type: ignore[arg-type]

    s = "hello world this is a test sentence with many words"
    result = count_tokens(s)
    # The encoding cache is already None and tiktoken is unavailable.
    assert result == max(1, len(s) // 4)


def test_count_tokens_fallback_directly() -> None:
    """count_tokens with tiktoken forced unavailable returns max(1, len//4)."""
    import vulpcode.harness._tokens as _tok_mod

    original_enc = _tok_mod._enc
    original_unavailable = _tok_mod._tiktoken_unavailable

    try:
        _tok_mod._enc = None
        _tok_mod._tiktoken_unavailable = True

        from vulpcode.harness._tokens import count_tokens

        s = "hello world"  # 11 chars -> 11//4 = 2
        assert count_tokens(s) == max(1, len(s) // 4)

        s_empty = ""  # 0 chars -> fallback returns max(1, 0) = 1
        assert count_tokens(s_empty) == 1
    finally:
        _tok_mod._enc = original_enc
        _tok_mod._tiktoken_unavailable = original_unavailable


# ---------------------------------------------------------------------------
# Eviction — no-op cases
# ---------------------------------------------------------------------------


def test_no_op_when_disabled() -> None:
    """evict_messages is a no-op when config.enabled is False."""
    msgs = _make_conversation(50)
    original = list(msgs)
    state = _make_state(msgs)
    evict_messages(state, EvictionConfig(enabled=False))
    assert state.messages == original


def test_no_op_when_below_threshold() -> None:
    """evict_messages does nothing when message count is well below max."""
    msgs = _make_conversation(5)  # 1 system + 1 user + 5*2 = 12 messages
    original = list(msgs)
    state = _make_state(msgs)
    evict_messages(state, EvictionConfig(enabled=True, max_messages=100))
    assert state.messages == original


# ---------------------------------------------------------------------------
# Eviction — active cases
# ---------------------------------------------------------------------------


def test_evicts_oldest_pair() -> None:
    """250 message pairs → exceeds max_messages=200, one pair is dropped leaving 248."""
    # Build: system + user + 124*2 pairs = 1 + 1 + 248 = 250 messages
    msgs = _make_conversation(124)
    assert len(msgs) == 250
    state = _make_state(msgs)
    cfg = EvictionConfig(enabled=True, max_messages=200, keep_recent=20)
    evict_messages(state, cfg)
    # After eviction we should be below or at 200.
    assert len(state.messages) <= 200


def test_evicts_down_to_threshold() -> None:
    """Multiple pairs evicted until count <= max_messages."""
    msgs = _make_conversation(150)  # 1 + 1 + 300 = 302 messages
    state = _make_state(msgs)
    cfg = EvictionConfig(enabled=True, max_messages=200, keep_recent=10)
    evict_messages(state, cfg)
    assert len(state.messages) <= 200


def test_preserves_system_first() -> None:
    """Leading system message is never evicted."""
    msgs = _make_conversation(100)
    assert msgs[0].role == "system"
    state = _make_state(msgs)
    evict_messages(state, EvictionConfig(enabled=True, max_messages=50, keep_recent=5))
    assert state.messages[0].role == "system"


def test_preserves_recent() -> None:
    """Last keep_recent messages are never evicted."""
    keep = 10
    msgs = _make_conversation(100)
    tail_before = msgs[-keep:]
    state = _make_state(msgs)
    evict_messages(state, EvictionConfig(enabled=True, max_messages=50, keep_recent=keep))
    tail_after = state.messages[-keep:]
    assert tail_after == tail_before


def test_token_based_eviction() -> None:
    """Eviction triggers on token count even when message count is below max_messages."""
    # Each message content is 400 chars ≈ 100 tokens (fallback: 400//4 = 100)
    big_content = "x" * 400
    msgs: list[Message] = [_system()]
    for _ in range(20):
        msgs.append(_assistant(big_content, with_tool_call=True))
        msgs.append(_tool_result(big_content))
    msgs.append(_user("hi"))

    total_before = len(msgs)
    state = _make_state(msgs)
    # With 21 messages * 100 tokens each ≈ 4100 tokens, set limit to 1000.
    cfg = EvictionConfig(
        enabled=True,
        max_messages=1000,  # won't trigger on count
        max_tokens=1000,
        keep_recent=4,
    )

    import vulpcode.harness._tokens as _tok_mod

    orig_enc = _tok_mod._enc
    orig_unavail = _tok_mod._tiktoken_unavailable
    try:
        _tok_mod._enc = None
        _tok_mod._tiktoken_unavailable = True
        evict_messages(state, cfg)
    finally:
        _tok_mod._enc = orig_enc
        _tok_mod._tiktoken_unavailable = orig_unavail

    assert len(state.messages) < total_before


# ---------------------------------------------------------------------------
# Overflow clip
# ---------------------------------------------------------------------------


def _make_clip_state() -> LoopState:
    return _make_state([])


def test_clip_below_threshold() -> None:
    """ToolResult with output under the limit is returned unchanged."""
    result = ToolResult(output="x" * 1000)
    state = _make_clip_state()
    cfg = OverflowClipConfig(enabled=True, max_tool_output_chars=8000)
    out = clip_tool_output(state, call=None, result=result, config=cfg)
    assert out is result


def test_clip_above_threshold() -> None:
    """ToolResult with output over the limit is clipped to head + marker + tail."""
    content = "A" * 10000 + "B" * 10000  # 20000 chars
    result = ToolResult(output=content)
    state = _make_clip_state()
    cfg = OverflowClipConfig(
        enabled=True,
        max_tool_output_chars=8000,
        head_chars=4000,
        tail_chars=1000,
    )
    out = clip_tool_output(state, call=None, result=result, config=cfg)
    assert out is not result
    assert out.output.startswith("A" * 4000)
    assert out.output.endswith("B" * 1000)
    assert len(out.output) < len(content)
    assert "[clipped" in out.output


def test_clip_message_format() -> None:
    """clip_tool_output inserts the exact marker format."""
    total = 20000
    head = 4000
    tail = 1000
    clipped = total - head - tail  # 15000
    content = "X" * total
    result = ToolResult(output=content)
    state = _make_clip_state()
    cfg = OverflowClipConfig(
        enabled=True,
        max_tool_output_chars=8000,
        head_chars=head,
        tail_chars=tail,
    )
    out = clip_tool_output(state, call=None, result=result, config=cfg)
    expected_marker = (
        f"[clipped {clipped} chars — total was {total},"
        f" showing first {head} and last {tail}]"
    )
    assert expected_marker in out.output


def test_clip_preserves_error_fields() -> None:
    """Clipping preserves is_error and metadata fields."""
    content = "E" * 20000
    result = ToolResult(output=content, is_error=True, error="oops", metadata={"k": "v"})
    state = _make_clip_state()
    cfg = OverflowClipConfig(
        enabled=True,
        max_tool_output_chars=8000,
        head_chars=4000,
        tail_chars=1000,
    )
    out = clip_tool_output(state, call=None, result=result, config=cfg)
    assert out.is_error is True
    assert out.error == "oops"
    assert out.metadata == {"k": "v"}


# ---------------------------------------------------------------------------
# register_default_middleware integration
# ---------------------------------------------------------------------------


def test_register_default_middleware_registers_eviction() -> None:
    """register_default_middleware registers eviction hook when enabled."""
    from vulpcode.harness import register_default_middleware
    from vulpcode.harness.hooks import HookBus

    bus = HookBus()
    cfg = {"middleware": {"eviction": {"enabled": True, "max_messages": 50}}}
    register_default_middleware(bus, cfg)
    desc = bus.describe()
    assert "before_iteration" in desc
    names = [h["name"] for h in desc["before_iteration"]]
    assert "eviction" in names


def test_register_default_middleware_registers_clip() -> None:
    """register_default_middleware registers clip hook when enabled via eviction section."""
    from vulpcode.harness import register_default_middleware
    from vulpcode.harness.hooks import HookBus

    bus = HookBus()
    cfg = {
        "middleware": {
            "eviction": {"enabled": True, "max_tool_output_chars": 4000, "head_chars": 2000}
        }
    }
    register_default_middleware(bus, cfg)
    desc = bus.describe()
    assert "after_tool_call" in desc
    names = [h["name"] for h in desc["after_tool_call"]]
    assert "overflow_clip" in names


def test_register_default_middleware_no_op_when_disabled() -> None:
    """register_default_middleware registers nothing when disabled."""
    from vulpcode.harness import register_default_middleware
    from vulpcode.harness.hooks import HookBus

    bus = HookBus()
    cfg: dict[str, Any] = {}
    register_default_middleware(bus, cfg)
    assert bus.describe() == {}
