"""Tests for AnthropicProvider (translation only — no real API calls)."""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

pytest.importorskip("anthropic")

from anthropic.types import (  # noqa: E402
    RawContentBlockDeltaEvent,
    RawContentBlockStartEvent,
    RawContentBlockStopEvent,
    RawMessageDeltaEvent,
    RawMessageStopEvent,
)

from vulpcode.providers import Message, ProviderError, ToolCall  # noqa: E402
from vulpcode.providers.anthropic import AnthropicProvider  # noqa: E402


def test_supports_tools_and_vision() -> None:
    p = AnthropicProvider(api_key="test")
    assert p.supports_tools() is True
    assert p.supports_vision() is True


def test_translate_user_message() -> None:
    p = AnthropicProvider(api_key="test")
    out = p._msg_to_anthropic(Message(role="user", content="hello"))
    assert out == {"role": "user", "content": "hello"}


def test_translate_assistant_with_tools() -> None:
    p = AnthropicProvider(api_key="test")
    msg = Message(
        role="assistant",
        content="thinking",
        tool_calls=[ToolCall(id="t1", name="Read", arguments={"file_path": "/a"})],
    )
    out = p._msg_to_anthropic(msg)
    assert out["role"] == "assistant"
    assert isinstance(out["content"], list)
    assert out["content"][0] == {"type": "text", "text": "thinking"}
    assert out["content"][1]["type"] == "tool_use"
    assert out["content"][1]["id"] == "t1"
    assert out["content"][1]["name"] == "Read"
    assert out["content"][1]["input"] == {"file_path": "/a"}


def test_translate_assistant_with_tools_no_text() -> None:
    p = AnthropicProvider(api_key="test")
    msg = Message(
        role="assistant",
        content="",
        tool_calls=[ToolCall(id="t1", name="Bash", arguments={"command": "ls"})],
    )
    out = p._msg_to_anthropic(msg)
    assert out["role"] == "assistant"
    assert len(out["content"]) == 1
    assert out["content"][0]["type"] == "tool_use"


def test_translate_tool_result_message() -> None:
    p = AnthropicProvider(api_key="test")
    msg = Message(role="tool", tool_call_id="t1", content="42")
    out = p._msg_to_anthropic(msg)
    assert out["role"] == "user"
    assert isinstance(out["content"], list)
    assert out["content"][0]["type"] == "tool_result"
    assert out["content"][0]["tool_use_id"] == "t1"
    assert out["content"][0]["content"] == "42"


def test_tools_translation() -> None:
    p = AnthropicProvider(api_key="test")
    canonical = [
        {"name": "Read", "description": "reads", "input_schema": {"type": "object"}}
    ]
    out = p._tools_to_anthropic(canonical)
    assert out[0]["name"] == "Read"
    assert out[0]["description"] == "reads"
    assert out[0]["input_schema"] == {"type": "object"}


def test_tools_translation_defaults_input_schema() -> None:
    p = AnthropicProvider(api_key="test")
    out = p._tools_to_anthropic([{"name": "X"}])
    assert out[0]["input_schema"] == {"type": "object"}
    assert out[0]["description"] == ""


async def test_list_models_is_curated() -> None:
    p = AnthropicProvider(api_key="test")
    models = await p.list_models()
    assert any("claude" in m for m in models)
    assert len(models) >= 1


# ---- _handle_event behavior ----


def _make_block_start(index: int, block: Any) -> RawContentBlockStartEvent:
    return RawContentBlockStartEvent.model_construct(
        type="content_block_start", index=index, content_block=block
    )


def _make_block_delta(index: int, delta: Any) -> RawContentBlockDeltaEvent:
    return RawContentBlockDeltaEvent.model_construct(
        type="content_block_delta", index=index, delta=delta
    )


def _make_block_stop(index: int) -> RawContentBlockStopEvent:
    return RawContentBlockStopEvent.model_construct(
        type="content_block_stop", index=index
    )


def test_handle_event_text_delta_emits_text_chunk() -> None:
    p = AnthropicProvider(api_key="test")
    pending: dict[int, dict[str, Any]] = {}
    delta = SimpleNamespace(type="text_delta", text="hello")
    chunk = p._handle_event(_make_block_delta(0, delta), pending)
    assert chunk is not None
    assert chunk.type == "text"
    assert chunk.delta == "hello"


def test_handle_event_tool_use_aggregates_and_emits_on_stop() -> None:
    p = AnthropicProvider(api_key="test")
    pending: dict[int, dict[str, Any]] = {}

    block = SimpleNamespace(type="tool_use", id="tu_1", name="Read", input={})
    assert p._handle_event(_make_block_start(0, block), pending) is None
    assert 0 in pending

    d1 = SimpleNamespace(type="input_json_delta", partial_json='{"file_path"')
    d2 = SimpleNamespace(type="input_json_delta", partial_json=': "/x"}')
    assert p._handle_event(_make_block_delta(0, d1), pending) is None
    assert p._handle_event(_make_block_delta(0, d2), pending) is None

    chunk = p._handle_event(_make_block_stop(0), pending)
    assert chunk is not None
    assert chunk.type == "tool_call"
    assert chunk.tool_call is not None
    assert chunk.tool_call.id == "tu_1"
    assert chunk.tool_call.name == "Read"
    assert chunk.tool_call.arguments == {"file_path": "/x"}
    assert 0 not in pending


def test_handle_event_tool_use_invalid_json_yields_empty_args() -> None:
    p = AnthropicProvider(api_key="test")
    pending: dict[int, dict[str, Any]] = {}
    block = SimpleNamespace(type="tool_use", id="tu_2", name="Bash", input={})
    p._handle_event(_make_block_start(0, block), pending)
    bad = SimpleNamespace(type="input_json_delta", partial_json="{not-json")
    p._handle_event(_make_block_delta(0, bad), pending)
    chunk = p._handle_event(_make_block_stop(0), pending)
    assert chunk is not None
    assert chunk.tool_call is not None
    assert chunk.tool_call.arguments == {}


def test_handle_event_text_block_start_is_ignored() -> None:
    p = AnthropicProvider(api_key="test")
    pending: dict[int, dict[str, Any]] = {}
    block = SimpleNamespace(type="text", text="")
    assert p._handle_event(_make_block_start(0, block), pending) is None
    assert pending == {}


def test_handle_event_message_delta_emits_usage() -> None:
    p = AnthropicProvider(api_key="test")
    pending: dict[int, dict[str, Any]] = {}
    usage = SimpleNamespace(output_tokens=42)
    event = RawMessageDeltaEvent.model_construct(
        type="message_delta",
        delta=SimpleNamespace(),
        usage=usage,
    )
    chunk = p._handle_event(event, pending)
    assert chunk is not None
    assert chunk.type == "usage"
    assert chunk.usage is not None
    assert chunk.usage.output_tokens == 42


def test_handle_event_message_stop_returns_none() -> None:
    p = AnthropicProvider(api_key="test")
    pending: dict[int, dict[str, Any]] = {}
    event = RawMessageStopEvent.model_construct(type="message_stop")
    assert p._handle_event(event, pending) is None


# ---- stream() integration with mocked SDK ----


class _FakeStream:
    def __init__(self, events: list[Any]) -> None:
        self._events = events

    def __aiter__(self) -> "_FakeStream":
        self._iter = iter(self._events)
        return self

    async def __anext__(self) -> Any:
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


def _install_fake_stream(provider: AnthropicProvider, events: list[Any]) -> None:
    @asynccontextmanager
    async def fake_stream(**_kwargs: Any) -> Any:
        yield _FakeStream(events)

    provider._client = MagicMock()
    provider._client.messages = MagicMock()
    provider._client.messages.stream = fake_stream  # type: ignore[assignment]


async def test_stream_emits_text_tool_call_usage_and_stop() -> None:
    p = AnthropicProvider(api_key="test")

    text_delta = SimpleNamespace(type="text_delta", text="hi")
    tu_block = SimpleNamespace(type="tool_use", id="tu_a", name="Read", input={})
    json_d1 = SimpleNamespace(type="input_json_delta", partial_json='{"a"')
    json_d2 = SimpleNamespace(type="input_json_delta", partial_json=":1}")
    usage = SimpleNamespace(output_tokens=7)

    events = [
        _make_block_start(0, SimpleNamespace(type="text", text="")),
        _make_block_delta(0, text_delta),
        _make_block_stop(0),
        _make_block_start(1, tu_block),
        _make_block_delta(1, json_d1),
        _make_block_delta(1, json_d2),
        _make_block_stop(1),
        RawMessageDeltaEvent.model_construct(
            type="message_delta", delta=SimpleNamespace(), usage=usage
        ),
        RawMessageStopEvent.model_construct(type="message_stop"),
    ]
    _install_fake_stream(p, events)

    chunks = [c async for c in p.stream(messages=[Message(role="user", content="hi")], tools=[], model="claude-x")]
    types = [c.type for c in chunks]
    assert types[0] == "text"
    assert chunks[0].delta == "hi"
    assert "tool_call" in types
    tool_chunk = next(c for c in chunks if c.type == "tool_call")
    assert tool_chunk.tool_call is not None
    assert tool_chunk.tool_call.arguments == {"a": 1}
    assert "usage" in types
    assert types[-1] == "stop"


async def test_stream_wraps_exception_in_provider_error() -> None:
    p = AnthropicProvider(api_key="test")

    @asynccontextmanager
    async def boom(**_kwargs: Any) -> Any:
        if True:
            raise RuntimeError("kaboom")
        yield  # pragma: no cover

    p._client = MagicMock()
    p._client.messages = MagicMock()
    p._client.messages.stream = boom  # type: ignore[assignment]

    with pytest.raises(ProviderError, match="Anthropic stream failed"):
        async for _ in p.stream(messages=[Message(role="user", content="hi")], tools=[], model="x"):
            pass


async def test_aclose_calls_underlying_client() -> None:
    p = AnthropicProvider(api_key="test")
    closer = AsyncMock()
    p._client = MagicMock()
    p._client.close = closer
    await p.aclose()
    closer.assert_awaited_once()


def test_stream_passes_system_and_tools() -> None:
    """Ensure stream() forwards system prompt and translated tools to the SDK."""
    p = AnthropicProvider(api_key="test")
    captured: dict[str, Any] = {}

    @asynccontextmanager
    async def capturing_stream(**kwargs: Any) -> Any:
        captured.update(kwargs)
        yield _FakeStream([RawMessageStopEvent.model_construct(type="message_stop")])

    p._client = MagicMock()
    p._client.messages = MagicMock()
    p._client.messages.stream = capturing_stream  # type: ignore[assignment]

    async def run() -> None:
        async for _ in p.stream(
            messages=[Message(role="user", content="hi")],
            tools=[{"name": "Read", "description": "r", "input_schema": {"type": "object"}}],
            model="claude-x",
            system="be helpful",
            max_tokens=128,
        ):
            pass

    import asyncio

    asyncio.run(run())

    assert captured["model"] == "claude-x"
    assert captured["system"] == "be helpful"
    assert captured["max_tokens"] == 128
    assert captured["messages"] == [{"role": "user", "content": "hi"}]
    assert captured["tools"][0]["name"] == "Read"


def test_translate_tool_result_with_non_string_content() -> None:
    p = AnthropicProvider(api_key="test")
    msg = Message(role="tool", tool_call_id="t1", content=[{"type": "text", "text": "x"}])
    out = p._msg_to_anthropic(msg)
    assert out["content"][0]["content"] == ""


def test_json_decode_error_recovery_fallback() -> None:
    """Sanity check: explicit json.JSONDecodeError path returns empty arguments."""
    p = AnthropicProvider(api_key="test")
    pending: dict[int, dict[str, Any]] = {0: {"id": "x", "name": "y", "json": "garbage"}}
    chunk = p._handle_event(_make_block_stop(0), pending)
    assert chunk is not None
    assert chunk.tool_call is not None
    assert chunk.tool_call.arguments == {}
    # ensure json module is referenced (avoid unused import warning)
    assert json.dumps({}) == "{}"
