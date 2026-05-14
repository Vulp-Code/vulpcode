"""Tests for GeminiProvider (translation only)."""
import pytest

pytest.importorskip("google.genai")

from vulpcode.providers import Message, ToolCall
from vulpcode.providers.gemini import GeminiProvider


def test_supports_tools_and_vision():
    p = GeminiProvider(api_key="test")
    assert p.supports_tools() is True
    assert p.supports_vision() is True


def test_translate_user_message():
    p = GeminiProvider(api_key="test")
    out = p._msg_to_gemini(Message(role="user", content="hi"))
    assert out["role"] == "user"
    assert out["parts"] == [{"text": "hi"}]


def test_translate_assistant_with_tool_calls():
    p = GeminiProvider(api_key="test")
    msg = Message(
        role="assistant",
        content="ok",
        tool_calls=[ToolCall(id="t1", name="Read", arguments={"file_path": "/a"})],
    )
    out = p._msg_to_gemini(msg)
    assert out["role"] == "model"
    assert any("function_call" in p_ for p_ in out["parts"])


def test_translate_tool_response():
    p = GeminiProvider(api_key="test")
    msg = Message(role="tool", tool_call_id="t1", name="Read", content="42")
    out = p._msg_to_gemini(msg)
    assert out["parts"][0]["function_response"]["name"] == "Read"
    assert out["parts"][0]["function_response"]["response"]["result"] == "42"


def test_system_message_is_skipped_in_contents():
    p = GeminiProvider(api_key="test")
    out = p._msg_to_gemini(Message(role="system", content="be brief"))
    assert out is None


def test_tools_translation():
    p = GeminiProvider(api_key="test")
    out = p._tools_to_gemini(
        [{"name": "Read", "description": "r", "input_schema": {"type": "object"}}]
    )
    assert out[0]["function_declarations"][0]["name"] == "Read"
