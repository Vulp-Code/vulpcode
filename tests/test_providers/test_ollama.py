"""Tests for OllamaProvider (translation only)."""
from vulpcode.providers import Message, ToolCall
from vulpcode.providers.ollama import OllamaProvider


def test_supports_tools_and_vision():
    p = OllamaProvider()
    assert p.supports_tools() is True
    assert p.supports_vision() is True


def test_default_base_url():
    p = OllamaProvider()
    assert p.base_url == "http://localhost:11434"


def test_base_url_override():
    p = OllamaProvider(base_url="http://remote-ollama:11434")
    assert p.base_url == "http://remote-ollama:11434"


def test_translate_user_message():
    p = OllamaProvider()
    out = p._msg_to_ollama(Message(role="user", content="hi"))
    assert out == {"role": "user", "content": "hi"}


def test_translate_assistant_with_tool_calls():
    p = OllamaProvider()
    msg = Message(
        role="assistant",
        content="ok",
        tool_calls=[ToolCall(id="t1", name="Read", arguments={"file_path": "/a"})],
    )
    out = p._msg_to_ollama(msg)
    assert out["role"] == "assistant"
    assert out["tool_calls"][0]["function"]["name"] == "Read"
    assert out["tool_calls"][0]["function"]["arguments"] == {"file_path": "/a"}
    assert out["tool_calls"][0]["type"] == "function"
    assert out["tool_calls"][0]["id"] == "t1"


def test_translate_tool_message():
    p = OllamaProvider()
    out = p._msg_to_ollama(Message(role="tool", tool_call_id="t1", content="42"))
    assert out["role"] == "tool"
    assert out["tool_call_id"] == "t1"
    assert out["content"] == "42"


def test_tools_translation():
    p = OllamaProvider()
    out = p._tools_to_ollama(
        [{"name": "Read", "description": "r", "input_schema": {"type": "object"}}]
    )
    assert out[0]["type"] == "function"
    assert out[0]["function"]["name"] == "Read"
    assert out[0]["function"]["description"] == "r"
    assert out[0]["function"]["parameters"] == {"type": "object"}


def test_tools_translation_default_schema():
    p = OllamaProvider()
    out = p._tools_to_ollama([{"name": "Bare"}])
    assert out[0]["function"]["parameters"] == {"type": "object"}
    assert out[0]["function"]["description"] == ""
