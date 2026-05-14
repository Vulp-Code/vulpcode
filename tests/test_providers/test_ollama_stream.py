"""Stream-level tests for OllamaProvider parsing NDJSON.

Translation-only tests live in test_ollama.py. These tests cover the
NDJSON streaming pipeline: text chunks, tool_calls extraction, usage,
stop emission, and graceful skipping of malformed lines.
"""
import json
from unittest.mock import patch

import httpx
import pytest

from vulpcode.providers.base import Message, ProviderError
from vulpcode.providers.ollama import OllamaProvider


class _FakeStream:
    """Async context manager that mimics httpx.AsyncClient.stream(...)."""

    def __init__(self, lines: list[str]) -> None:
        self._lines = list(lines)

    async def __aenter__(self) -> "_FakeStream":
        return self

    async def __aexit__(self, *args: object) -> bool:
        return False

    def raise_for_status(self) -> None:
        return None

    async def aiter_lines(self):
        for ln in self._lines:
            yield ln


@pytest.mark.asyncio
async def test_ollama_parses_ndjson() -> None:
    """A two-line NDJSON stream must yield text, tool_call, usage, then stop."""
    lines = [
        json.dumps({"message": {"role": "assistant", "content": "hello"}, "done": False}),
        json.dumps(
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "t1",
                            "function": {"name": "Read", "arguments": {"file_path": "/a"}},
                        }
                    ],
                },
                "done": True,
                "prompt_eval_count": 8,
                "eval_count": 3,
            }
        ),
    ]
    p = OllamaProvider()
    with patch.object(p._client, "stream", return_value=_FakeStream(lines)):
        out = []
        async for c in p.stream(
            messages=[Message(role="user", content="x")],
            tools=[],
            model="qwen",
        ):
            out.append(c)

    types = [c.type for c in out]
    assert "text" in types
    assert "tool_call" in types
    assert "usage" in types
    assert types[-1] == "stop"

    text_chunks = [c for c in out if c.type == "text"]
    assert text_chunks[0].delta == "hello"

    tool_chunks = [c for c in out if c.type == "tool_call"]
    assert len(tool_chunks) == 1
    assert tool_chunks[0].tool_call is not None
    assert tool_chunks[0].tool_call.name == "Read"
    assert tool_chunks[0].tool_call.arguments == {"file_path": "/a"}
    assert tool_chunks[0].tool_call.id == "t1"

    usage_chunks = [c for c in out if c.type == "usage"]
    assert usage_chunks[0].usage is not None
    assert usage_chunks[0].usage.input_tokens == 8
    assert usage_chunks[0].usage.output_tokens == 3


@pytest.mark.asyncio
async def test_ollama_skips_malformed_and_empty_lines() -> None:
    """Empty lines and lines that fail JSON parsing must be skipped silently."""
    lines = [
        "",
        "not-json-at-all",
        json.dumps({"message": {"content": "ok"}, "done": True}),
    ]
    p = OllamaProvider()
    with patch.object(p._client, "stream", return_value=_FakeStream(lines)):
        out = []
        async for c in p.stream(
            messages=[Message(role="user", content="x")],
            tools=[],
            model="qwen",
        ):
            out.append(c)

    types = [c.type for c in out]
    assert "text" in types
    assert types[-1] == "stop"


@pytest.mark.asyncio
async def test_ollama_string_tool_arguments_are_parsed() -> None:
    """Tool arguments arriving as a JSON-encoded string must be decoded."""
    lines = [
        json.dumps(
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "Bash",
                                "arguments": '{"command": "ls"}',
                            }
                        }
                    ],
                },
                "done": True,
            }
        ),
    ]
    p = OllamaProvider()
    with patch.object(p._client, "stream", return_value=_FakeStream(lines)):
        out = []
        async for c in p.stream(
            messages=[Message(role="user", content="x")],
            tools=[],
            model="qwen",
        ):
            out.append(c)

    tool_chunks = [c for c in out if c.type == "tool_call"]
    assert len(tool_chunks) == 1
    assert tool_chunks[0].tool_call is not None
    assert tool_chunks[0].tool_call.name == "Bash"
    assert tool_chunks[0].tool_call.arguments == {"command": "ls"}
    assert tool_chunks[0].tool_call.id.startswith("ollama_")


@pytest.mark.asyncio
async def test_ollama_string_tool_arguments_malformed_falls_back() -> None:
    """A malformed tool-arguments string must fall back to an empty dict."""
    lines = [
        json.dumps(
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "Bash",
                                "arguments": "{not-json",
                            }
                        }
                    ],
                },
                "done": True,
            }
        ),
    ]
    p = OllamaProvider()
    with patch.object(p._client, "stream", return_value=_FakeStream(lines)):
        out = []
        async for c in p.stream(
            messages=[Message(role="user", content="x")],
            tools=[],
            model="qwen",
        ):
            out.append(c)

    tool_chunks = [c for c in out if c.type == "tool_call"]
    assert len(tool_chunks) == 1
    assert tool_chunks[0].tool_call is not None
    assert tool_chunks[0].tool_call.arguments == {}


@pytest.mark.asyncio
async def test_ollama_http_error_wrapped_in_provider_error() -> None:
    """httpx.HTTPError raised inside the stream must be wrapped as ProviderError."""

    class _RaisingStream:
        async def __aenter__(self):
            raise httpx.HTTPError("network down")

        async def __aexit__(self, *args: object) -> bool:
            return False

    p = OllamaProvider()
    with patch.object(p._client, "stream", return_value=_RaisingStream()):
        with pytest.raises(ProviderError, match="Ollama stream failed"):
            async for _ in p.stream(
                messages=[Message(role="user", content="x")],
                tools=[],
                model="qwen",
            ):
                pass
