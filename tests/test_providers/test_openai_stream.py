"""Stream-level tests for OpenAIProvider with mocked SDK.

These tests focus on the streaming pipeline: tool_call aggregation across
chunks, error wrapping in ProviderError, and graceful handling of malformed
tool argument JSON. Translation-only tests live in test_openai.py.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

pytest.importorskip("openai")

from vulpcode.providers.base import Message, ProviderError
from vulpcode.providers.openai import OpenAIProvider


def _make_chunk(
    text: str | None = None,
    tool_index: int | None = None,
    tc_id: str | None = None,
    tc_name: str | None = None,
    tc_args: str | None = None,
    finish: str | None = None,
    usage: SimpleNamespace | None = None,
) -> SimpleNamespace:
    """Build a SimpleNamespace shaped like an OpenAI streaming chunk."""
    tool_calls = None
    if tool_index is not None:
        tool_calls = [
            SimpleNamespace(
                index=tool_index,
                id=tc_id,
                function=SimpleNamespace(name=tc_name, arguments=tc_args),
            )
        ]
    delta = SimpleNamespace(content=text, tool_calls=tool_calls)
    choices = [SimpleNamespace(delta=delta, finish_reason=finish)]
    return SimpleNamespace(choices=choices, usage=usage)


class _AsyncIter:
    """Minimal async iterator over a list of items."""

    def __init__(self, items: list) -> None:
        self.items = list(items)

    def __aiter__(self) -> "_AsyncIter":
        return self

    async def __anext__(self):
        if not self.items:
            raise StopAsyncIteration
        return self.items.pop(0)


@pytest.mark.asyncio
async def test_openai_stream_aggregates_tool_call() -> None:
    """Fragmented tool_call across chunks must collapse into one ToolCall."""
    chunks = [
        _make_chunk(tool_index=0, tc_id="t1", tc_name="Read"),
        _make_chunk(tool_index=0, tc_args='{"file_path":'),
        _make_chunk(tool_index=0, tc_args='"/abs"}'),
        _make_chunk(finish="tool_calls"),
        _make_chunk(usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5)),
    ]
    p = OpenAIProvider(api_key="x")
    fake_create = AsyncMock(return_value=_AsyncIter(chunks))
    with patch.object(p._client.chat.completions, "create", new=fake_create):
        out = []
        async for c in p.stream(
            messages=[Message(role="user", content="x")],
            tools=[],
            model="gpt-4",
        ):
            out.append(c)

    tool_calls = [c for c in out if c.type == "tool_call"]
    assert len(tool_calls) == 1
    assert tool_calls[0].tool_call is not None
    assert tool_calls[0].tool_call.name == "Read"
    assert tool_calls[0].tool_call.id == "t1"
    assert tool_calls[0].tool_call.arguments == {"file_path": "/abs"}

    usage = [c for c in out if c.type == "usage"]
    assert len(usage) == 1
    assert usage[0].usage is not None
    assert usage[0].usage.input_tokens == 10
    assert usage[0].usage.output_tokens == 5

    assert out[-1].type == "stop"


@pytest.mark.asyncio
async def test_openai_stream_provider_error_on_exception() -> None:
    """A raw SDK exception must be re-wrapped as ProviderError."""
    p = OpenAIProvider(api_key="x")
    with patch.object(
        p._client.chat.completions,
        "create",
        new=AsyncMock(side_effect=RuntimeError("boom")),
    ):
        with pytest.raises(ProviderError, match="OpenAI stream failed"):
            async for _ in p.stream(messages=[], tools=[], model="x"):
                pass


@pytest.mark.asyncio
async def test_openai_stream_malformed_tool_args_falls_back_to_empty() -> None:
    """Invalid JSON in tool arguments must yield empty arguments without raising."""
    chunks = [
        _make_chunk(tool_index=0, tc_id="t1", tc_name="Bash", tc_args="{bad json"),
        _make_chunk(finish="tool_calls"),
    ]
    p = OpenAIProvider(api_key="x")
    fake_create = AsyncMock(return_value=_AsyncIter(chunks))
    with patch.object(p._client.chat.completions, "create", new=fake_create):
        out = []
        async for c in p.stream(
            messages=[Message(role="user", content="x")],
            tools=[],
            model="gpt-4",
        ):
            out.append(c)

    tool_calls = [c for c in out if c.type == "tool_call"]
    assert len(tool_calls) == 1
    assert tool_calls[0].tool_call is not None
    assert tool_calls[0].tool_call.arguments == {}
    assert tool_calls[0].tool_call.name == "Bash"
