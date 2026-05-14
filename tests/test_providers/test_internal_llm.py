"""Tests for InternalLLMProvider (internal corporate /chatCompletion endpoint)."""
from unittest.mock import AsyncMock, patch

import pytest

from vulpcode.providers import Message, ToolCall
from vulpcode.providers.base import ProviderError
from vulpcode.providers.internal_llm import InternalLLMProvider


def test_does_not_advertise_unsupported_features():
    p = InternalLLMProvider()
    assert p.supports_tools() is False
    assert p.supports_vision() is False


def test_flatten_messages_keeps_order_and_system():
    msgs = [
        Message(role="user", content="hi"),
        Message(role="assistant", content="hello there"),
        Message(role="user", content="another"),
    ]
    out = InternalLLMProvider._flatten_messages(msgs, "you are a bot")
    assert out[0] == {"role": "system", "content": "you are a bot"}
    assert out[1] == {"role": "user", "content": "hi"}
    assert out[2] == {"role": "assistant", "content": "hello there"}
    assert out[3] == {"role": "user", "content": "another"}


def test_flatten_messages_collapses_tool_role_to_user_tag():
    msgs = [
        Message(role="user", content="please read"),
        Message(
            role="assistant",
            content="ok",
            tool_calls=[ToolCall(id="t1", name="Read", arguments={"x": 1})],
        ),
        Message(
            role="tool",
            tool_call_id="t1",
            name="Read",
            content="file contents",
        ),
    ]
    out = InternalLLMProvider._flatten_messages(msgs, None)
    assert {"role": "user", "content": "please read"} in out
    assert {"role": "assistant", "content": "ok"} in out
    last = out[-1]
    assert last["role"] == "user"
    assert "tool Read result" in last["content"]
    assert "file contents" in last["content"]


@pytest.mark.asyncio
async def test_stream_requires_endpoint():
    p = InternalLLMProvider(base_url=None, user_uuid=None)
    with pytest.raises(ProviderError, match="base_url"):
        async for _ in p.stream(
            messages=[Message(role="user", content="hi")],
            tools=[],
            model="internal-llm",
        ):
            pass


@pytest.mark.asyncio
async def test_stream_requires_uuid():
    p = InternalLLMProvider(base_url="http://x/chat", user_uuid=None)
    with pytest.raises(ProviderError, match="user_uuid"):
        async for _ in p.stream(
            messages=[Message(role="user", content="hi")],
            tools=[],
            model="internal-llm",
        ):
            pass


@pytest.mark.asyncio
async def test_stream_happy_path():
    p = InternalLLMProvider(
        base_url="http://x/chat", user_uuid="u-123", retry_delay=0.01
    )

    fake_resp = AsyncMock()
    fake_resp.status_code = 200
    fake_resp.text = "ok"
    fake_resp.json = lambda: {"data": "Olá mundo"}

    async def fake_post(*args, **kwargs):
        return fake_resp

    with patch.object(p._client, "post", new=fake_post):
        chunks = []
        async for c in p.stream(
            messages=[Message(role="user", content="oi")],
            tools=[],
            model="internal-llm",
        ):
            chunks.append(c)

    assert any(c.type == "text" and c.delta == "Olá mundo" for c in chunks)
    stop_chunks = [c for c in chunks if c.type == "stop"]
    assert stop_chunks
    # Model name flows through into raw metadata for tracing
    assert stop_chunks[0].raw == {"model_requested": "internal-llm"}


@pytest.mark.asyncio
async def test_stream_retries_on_data_null():
    """Endpoint returns HTTP 200 with data=null transiently — provider must retry."""
    p = InternalLLMProvider(
        base_url="http://x/chat",
        user_uuid="u-123",
        max_retries=3,
        retry_delay=0.01,
    )

    call_count = {"n": 0}

    def make_resp(payload):
        r = AsyncMock()
        r.status_code = 200
        r.text = ""
        r.json = lambda: payload
        return r

    async def fake_post(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] < 3:
            return make_resp({"data": None, "message": "transient"})
        return make_resp({"data": "finally!"})

    with patch.object(p._client, "post", new=fake_post):
        chunks = []
        async for c in p.stream(
            messages=[Message(role="user", content="oi")],
            tools=[],
            model="internal-llm",
        ):
            chunks.append(c)

    assert call_count["n"] == 3
    assert any(c.type == "text" and "finally" in (c.delta or "") for c in chunks)


@pytest.mark.asyncio
async def test_stream_raises_after_max_retries():
    p = InternalLLMProvider(
        base_url="http://x/chat",
        user_uuid="u-123",
        max_retries=2,
        retry_delay=0.01,
    )

    def fake_resp():
        r = AsyncMock()
        r.status_code = 200
        r.text = ""
        r.json = lambda: {"data": None}
        return r

    async def fake_post(*args, **kwargs):
        return fake_resp()

    with patch.object(p._client, "post", new=fake_post):
        with pytest.raises(ProviderError, match="data=null"):
            async for _ in p.stream(
                messages=[Message(role="user", content="oi")],
                tools=[],
                model="internal-llm",
            ):
                pass


@pytest.mark.asyncio
async def test_stream_warns_when_tools_passed():
    p = InternalLLMProvider(
        base_url="http://x/chat", user_uuid="u-123", retry_delay=0.01
    )

    fake_resp = AsyncMock()
    fake_resp.status_code = 200
    fake_resp.text = ""
    fake_resp.json = lambda: {"data": "ok"}

    async def fake_post(*args, **kwargs):
        return fake_resp

    with patch.object(p._client, "post", new=fake_post):
        chunks = []
        async for c in p.stream(
            messages=[Message(role="user", content="oi")],
            tools=[{"name": "Read", "description": "x", "input_schema": {}}],
            model="internal-llm",
        ):
            chunks.append(c)

    text_chunks = [c for c in chunks if c.type == "text"]
    assert any(
        "endpoint does not support tool calling" in (c.delta or "")
        for c in text_chunks
    )


@pytest.mark.asyncio
async def test_list_models():
    p = InternalLLMProvider()
    assert await p.list_models() == ["internal-llm"]


def test_registry_recognizes_internal_llm():
    from vulpcode.providers import build_provider, list_provider_names

    assert "internal-llm" in list_provider_names()
    p = build_provider(
        "internal-llm",
        {"base_url": "http://x/chat", "user_uuid": "u"},
    )
    assert isinstance(p, InternalLLMProvider)
    assert p.endpoint == "http://x/chat"
    assert p.user_uuid == "u"
