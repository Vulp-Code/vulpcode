"""Tests for OpenAIProvider (translation only)."""
import json

import pytest

pytest.importorskip("openai")

from vulpcode.providers import Message, ToolCall
from vulpcode.providers.openai import OpenAIProvider


def test_supports_tools_and_vision():
    p = OpenAIProvider(api_key="test")
    assert p.supports_tools() is True
    assert p.supports_vision() is True


def test_translate_user_message():
    p = OpenAIProvider(api_key="test")
    out = p._msg_to_openai(Message(role="user", content="hello"))
    assert out == {"role": "user", "content": "hello"}


def test_translate_assistant_with_tool_calls():
    p = OpenAIProvider(api_key="test")
    msg = Message(
        role="assistant",
        content="ok",
        tool_calls=[ToolCall(id="t1", name="Read", arguments={"file_path": "/a"})],
    )
    out = p._msg_to_openai(msg)
    assert out["role"] == "assistant"
    assert out["content"] == "ok"
    assert out["tool_calls"][0]["id"] == "t1"
    assert out["tool_calls"][0]["type"] == "function"
    assert out["tool_calls"][0]["function"]["name"] == "Read"
    assert json.loads(out["tool_calls"][0]["function"]["arguments"]) == {"file_path": "/a"}


def test_translate_assistant_with_empty_arguments():
    p = OpenAIProvider(api_key="test")
    msg = Message(
        role="assistant",
        content="",
        tool_calls=[ToolCall(id="t9", name="NoArgs", arguments={})],
    )
    out = p._msg_to_openai(msg)
    assert out["tool_calls"][0]["function"]["arguments"] == "{}"


def test_translate_tool_message():
    p = OpenAIProvider(api_key="test")
    out = p._msg_to_openai(Message(role="tool", tool_call_id="t1", content="42"))
    assert out["role"] == "tool"
    assert out["tool_call_id"] == "t1"
    assert out["content"] == "42"


def test_translate_system_and_assistant_plain():
    p = OpenAIProvider(api_key="test")
    sys_out = p._msg_to_openai(Message(role="system", content="be kind"))
    assert sys_out == {"role": "system", "content": "be kind"}

    assist_out = p._msg_to_openai(Message(role="assistant", content="hi"))
    assert assist_out == {"role": "assistant", "content": "hi"}


def test_tools_translation():
    p = OpenAIProvider(api_key="test")
    canonical = [
        {
            "name": "Read",
            "description": "reads",
            "input_schema": {"type": "object", "properties": {}},
        }
    ]
    out = p._tools_to_openai(canonical)
    assert out[0]["type"] == "function"
    assert out[0]["function"]["name"] == "Read"
    assert out[0]["function"]["description"] == "reads"
    assert out[0]["function"]["parameters"] == {"type": "object", "properties": {}}


def test_tools_translation_defaults_when_missing():
    p = OpenAIProvider(api_key="test")
    canonical = [{"name": "Bare"}]
    out = p._tools_to_openai(canonical)
    assert out[0]["function"]["name"] == "Bare"
    assert out[0]["function"]["description"] == ""
    assert out[0]["function"]["parameters"] == {"type": "object"}


def test_supports_arbitrary_base_url():
    p = OpenAIProvider(api_key="test", base_url="https://api.deepseek.com/v1")
    assert "deepseek" in str(p._client.base_url)


def test_default_api_key_for_local_backends():
    p = OpenAIProvider(base_url="http://localhost:1234/v1")
    assert p._client.api_key == "EMPTY"


@pytest.mark.asyncio
async def test_stream_aggregates_tool_calls_and_emits_usage(monkeypatch):
    """Verify stream() handles fragmented tool_calls, usage, and stop chunks."""
    from types import SimpleNamespace

    def make_chunk(
        *,
        content: str | None = None,
        tool_calls: list[SimpleNamespace] | None = None,
        finish_reason: str | None = None,
        usage: SimpleNamespace | None = None,
    ) -> SimpleNamespace:
        delta = SimpleNamespace(content=content, tool_calls=tool_calls)
        choice = SimpleNamespace(delta=delta, finish_reason=finish_reason)
        return SimpleNamespace(choices=[choice], usage=usage)

    def tc_frag(index, *, tc_id=None, name=None, args=None) -> SimpleNamespace:
        fn = SimpleNamespace(name=name, arguments=args) if (name or args) else None
        return SimpleNamespace(index=index, id=tc_id, function=fn)

    chunks_seq = [
        make_chunk(content="Hello "),
        make_chunk(content="world"),
        make_chunk(tool_calls=[tc_frag(0, tc_id="call_a", name="Read")]),
        make_chunk(tool_calls=[tc_frag(0, args='{"file_path"')]),
        make_chunk(tool_calls=[tc_frag(0, args=': "/x"}')]),
        make_chunk(tool_calls=[tc_frag(1, tc_id="call_b", name="Bash", args='{"cmd":"ls"}')]),
        make_chunk(finish_reason="tool_calls"),
        make_chunk(
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5)
        ),
    ]

    class FakeStream:
        def __init__(self, items):
            self._items = items

        def __aiter__(self):
            self._iter = iter(self._items)
            return self

        async def __anext__(self):
            try:
                return next(self._iter)
            except StopIteration:
                raise StopAsyncIteration

    captured: dict = {}

    async def fake_create(**params):
        captured["params"] = params
        return FakeStream(chunks_seq)

    p = OpenAIProvider(api_key="test")
    monkeypatch.setattr(p._client.chat.completions, "create", fake_create)

    events = []
    async for ev in p.stream(
        messages=[Message(role="user", content="hi")],
        tools=[{"name": "Read", "description": "", "input_schema": {"type": "object"}}],
        model="gpt-4o",
        system="be kind",
    ):
        events.append(ev)

    assert captured["params"]["model"] == "gpt-4o"
    assert captured["params"]["stream"] is True
    assert captured["params"]["stream_options"] == {"include_usage": True}
    assert captured["params"]["tool_choice"] == "auto"
    assert captured["params"]["messages"][0] == {"role": "system", "content": "be kind"}

    text_events = [e for e in events if e.type == "text"]
    assert "".join(e.delta for e in text_events) == "Hello world"

    tool_events = [e for e in events if e.type == "tool_call"]
    assert len(tool_events) == 2
    assert tool_events[0].tool_call.id == "call_a"
    assert tool_events[0].tool_call.name == "Read"
    assert tool_events[0].tool_call.arguments == {"file_path": "/x"}
    assert tool_events[1].tool_call.id == "call_b"
    assert tool_events[1].tool_call.arguments == {"cmd": "ls"}

    usage_events = [e for e in events if e.type == "usage"]
    assert len(usage_events) == 1
    assert usage_events[0].usage.input_tokens == 10
    assert usage_events[0].usage.output_tokens == 5

    assert events[-1].type == "stop"


@pytest.mark.asyncio
async def test_stream_wraps_sdk_errors_in_provider_error(monkeypatch):
    from vulpcode.providers.base import ProviderError

    async def boom(**params):
        raise RuntimeError("network down")

    p = OpenAIProvider(api_key="test")
    monkeypatch.setattr(p._client.chat.completions, "create", boom)

    with pytest.raises(ProviderError) as info:
        async for _ in p.stream(
            messages=[Message(role="user", content="hi")],
            tools=[],
            model="gpt-4o",
        ):
            pass
    assert "OpenAI stream failed" in str(info.value)


@pytest.mark.asyncio
async def test_stream_handles_malformed_tool_call_arguments(monkeypatch):
    from types import SimpleNamespace

    def make_chunk(*, tool_calls=None, finish_reason=None) -> SimpleNamespace:
        delta = SimpleNamespace(content=None, tool_calls=tool_calls)
        return SimpleNamespace(
            choices=[SimpleNamespace(delta=delta, finish_reason=finish_reason)],
            usage=None,
        )

    fn = SimpleNamespace(name="Bash", arguments="{not-valid-json")
    frag = SimpleNamespace(index=0, id="call_x", function=fn)

    chunks_seq = [
        make_chunk(tool_calls=[frag]),
        make_chunk(finish_reason="tool_calls"),
    ]

    class FakeStream:
        def __init__(self, items):
            self._items = items

        def __aiter__(self):
            self._iter = iter(self._items)
            return self

        async def __anext__(self):
            try:
                return next(self._iter)
            except StopIteration:
                raise StopAsyncIteration

    async def fake_create(**params):
        return FakeStream(chunks_seq)

    p = OpenAIProvider(api_key="test")
    monkeypatch.setattr(p._client.chat.completions, "create", fake_create)

    tool_events = []
    async for ev in p.stream(
        messages=[Message(role="user", content="x")],
        tools=[],
        model="gpt-4o",
    ):
        if ev.type == "tool_call":
            tool_events.append(ev)

    assert len(tool_events) == 1
    assert tool_events[0].tool_call.arguments == {}
