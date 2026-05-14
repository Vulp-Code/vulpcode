"""Tests for the canonical provider types and ABC."""
import pytest
from pydantic import ValidationError

from vulpcode.providers import Message, Provider, StreamChunk, ToolCall, Usage


def test_message_minimal() -> None:
    m = Message(role="user", content="hi")
    assert m.role == "user"
    assert m.content == "hi"
    assert m.tool_calls is None


def test_message_with_tool_calls() -> None:
    tc = ToolCall(id="t1", name="Read", arguments={"file_path": "/a"})
    m = Message(role="assistant", content="", tool_calls=[tc])
    assert m.tool_calls is not None
    assert m.tool_calls[0].name == "Read"


def test_message_invalid_role() -> None:
    with pytest.raises(ValidationError):
        Message(role="other", content="x")  # type: ignore[arg-type]


def test_streamchunk_text() -> None:
    c = StreamChunk(type="text", delta="hello")
    assert c.delta == "hello"


def test_streamchunk_tool_call() -> None:
    tc = ToolCall(id="x", name="Bash", arguments={"command": "ls"})
    c = StreamChunk(type="tool_call", tool_call=tc)
    assert c.tool_call is not None
    assert c.tool_call.name == "Bash"


def test_usage_defaults() -> None:
    u = Usage()
    assert u.input_tokens == 0
    assert u.output_tokens == 0
    assert u.cache_read_tokens == 0
    assert u.cache_creation_tokens == 0


def test_provider_is_abstract() -> None:
    with pytest.raises(TypeError):
        Provider()  # type: ignore[abstract]
