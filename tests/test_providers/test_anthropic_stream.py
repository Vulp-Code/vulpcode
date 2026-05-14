"""Stream-level tests for AnthropicProvider with mocked SDK.

Translation-only and event-handler tests live in test_anthropic.py. The tests
here focus on the outer pipeline: empty streams still emit a stop chunk, and
exceptions raised during stream construction are wrapped in ProviderError.
Deeper event-replay tests are intentionally minimal because event-class
mocking is verbose; full coverage of streaming SSE events is left to the
integration smoke tests in phase 14.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import MagicMock

import pytest

pytest.importorskip("anthropic")

from vulpcode.providers.anthropic import AnthropicProvider
from vulpcode.providers.base import Message, ProviderError


class _FakeEvents:
    """Async iterable that yields a fixed list of events then stops."""

    def __init__(self, events: list[Any]) -> None:
        self._events = events

    def __aiter__(self) -> "_FakeEvents":
        self._iter = iter(self._events)
        return self

    async def __anext__(self) -> Any:
        try:
            return next(self._iter)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


def _install_fake_stream(provider: AnthropicProvider, events: list[Any]) -> None:
    """Patch provider._client.messages.stream to return a fake async context."""

    @asynccontextmanager
    async def fake_stream(**_kwargs: Any) -> Any:
        yield _FakeEvents(events)

    provider._client = MagicMock()
    provider._client.messages = MagicMock()
    provider._client.messages.stream = fake_stream  # type: ignore[assignment]


@pytest.mark.asyncio
async def test_anthropic_stream_empty_yields_stop() -> None:
    """An empty event stream must still emit a single stop chunk."""
    p = AnthropicProvider(api_key="x")
    _install_fake_stream(p, [])

    chunks = []
    async for c in p.stream(
        messages=[Message(role="user", content="hi")],
        tools=[],
        model="claude-x",
    ):
        chunks.append(c)

    assert len(chunks) == 1
    assert chunks[0].type == "stop"


@pytest.mark.asyncio
async def test_anthropic_stream_wraps_exception_in_provider_error() -> None:
    """Any exception raised by the SDK stream context must surface as ProviderError."""
    p = AnthropicProvider(api_key="x")

    @asynccontextmanager
    async def boom(**_kwargs: Any) -> Any:
        raise RuntimeError("network down")
        yield  # pragma: no cover

    p._client = MagicMock()
    p._client.messages = MagicMock()
    p._client.messages.stream = boom  # type: ignore[assignment]

    with pytest.raises(ProviderError, match="Anthropic stream failed"):
        async for _ in p.stream(
            messages=[Message(role="user", content="hi")],
            tools=[],
            model="claude-x",
        ):
            pass


@pytest.mark.asyncio
async def test_anthropic_stream_with_system_and_tools_passes_args() -> None:
    """system, tools, and max_tokens kwargs must reach the SDK call."""
    p = AnthropicProvider(api_key="x")
    captured: dict[str, Any] = {}

    @asynccontextmanager
    async def capturing(**kwargs: Any) -> Any:
        captured.update(kwargs)
        yield _FakeEvents([])

    p._client = MagicMock()
    p._client.messages = MagicMock()
    p._client.messages.stream = capturing  # type: ignore[assignment]

    async for _ in p.stream(
        messages=[Message(role="user", content="hi")],
        tools=[{"name": "Read", "description": "r", "input_schema": {"type": "object"}}],
        model="claude-x",
        system="be helpful",
        max_tokens=64,
    ):
        pass

    assert captured["model"] == "claude-x"
    assert captured["system"] == "be helpful"
    assert captured["max_tokens"] == 64
    assert captured["tools"][0]["name"] == "Read"
