"""Tests for vulpcode.session persistence."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from vulpcode.providers.base import Message, ToolCall, Usage
from vulpcode.session import (
    delete_session,
    latest_session_name,
    list_sessions,
    load_session,
    save_session,
)


class FakeAgent:
    def __init__(self) -> None:
        self.model = "m"
        self.system = "sys"
        self._messages: list[Message] = [Message(role="user", content="hi")]
        self._session_usage = Usage(input_tokens=5, output_tokens=10)
        self.provider = type("P", (), {"name": "x"})()


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    a = FakeAgent()
    p = save_session("test", a, scope=tmp_path)
    assert p.exists()
    a._messages = []
    a.model = "?"
    a.system = "different"
    load_session("test", a, scope=tmp_path)
    assert a._messages[0].content == "hi"
    assert a.model == "m"
    assert a.system == "sys"
    assert a._session_usage.input_tokens == 5
    assert a._session_usage.output_tokens == 10


def test_load_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_session("nope", FakeAgent(), scope=tmp_path)


def test_list_sessions_orders_by_mtime(tmp_path: Path) -> None:
    a = FakeAgent()
    save_session("a", a, scope=tmp_path)
    time.sleep(0.05)
    save_session("b", a, scope=tmp_path)
    sessions = list_sessions(scope=tmp_path)
    names = [s["name"] for s in sessions]
    assert names == ["b", "a"]
    assert sessions[0]["messages"] == 1
    assert sessions[0]["model"] == "m"


def test_latest_session_name(tmp_path: Path) -> None:
    a = FakeAgent()
    save_session("first", a, scope=tmp_path)
    time.sleep(0.05)
    save_session("second", a, scope=tmp_path)
    assert latest_session_name(scope=tmp_path) == "second"


def test_latest_session_name_empty(tmp_path: Path) -> None:
    assert latest_session_name(scope=tmp_path) is None


def test_delete(tmp_path: Path) -> None:
    save_session("x", FakeAgent(), scope=tmp_path)
    assert delete_session("x", scope=tmp_path) is True
    assert delete_session("x", scope=tmp_path) is False


def test_name_sanitization(tmp_path: Path) -> None:
    p = save_session("../etc/passwd", FakeAgent(), scope=tmp_path)
    assert ".." not in p.name
    assert "/" not in p.name
    assert p.parent == tmp_path


def test_atomic_write_no_tmp_left(tmp_path: Path) -> None:
    save_session("atomic", FakeAgent(), scope=tmp_path)
    leftovers = list(tmp_path.glob("*.tmp"))
    assert leftovers == []


def test_corrupt_session_skipped_in_list(tmp_path: Path) -> None:
    save_session("good", FakeAgent(), scope=tmp_path)
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")
    sessions = list_sessions(scope=tmp_path)
    names = [s["name"] for s in sessions]
    assert "good" in names
    assert "broken" not in names


def test_save_preserves_tool_calls(tmp_path: Path) -> None:
    a = FakeAgent()
    a._messages = [
        Message(role="user", content="run it"),
        Message(
            role="assistant",
            content="calling",
            tool_calls=[ToolCall(id="t1", name="bash", arguments={"cmd": "ls"})],
        ),
        Message(role="tool", tool_call_id="t1", name="bash", content="output"),
    ]
    save_session("withtools", a, scope=tmp_path)

    fresh = FakeAgent()
    fresh._messages = []
    load_session("withtools", fresh, scope=tmp_path)
    assert len(fresh._messages) == 3
    assert fresh._messages[1].tool_calls is not None
    assert fresh._messages[1].tool_calls[0].name == "bash"
    assert fresh._messages[1].tool_calls[0].arguments == {"cmd": "ls"}
    assert fresh._messages[2].tool_call_id == "t1"


def test_save_payload_format(tmp_path: Path) -> None:
    p = save_session("fmt", FakeAgent(), scope=tmp_path)
    payload = json.loads(p.read_text(encoding="utf-8"))
    assert payload["version"] == 1
    assert payload["name"] == "fmt"
    assert payload["provider_name"] == "x"
    assert payload["model"] == "m"
    assert payload["system"] == "sys"
    assert "saved_at" in payload
    assert payload["session_usage"]["input_tokens"] == 5


def test_default_name_when_sanitized_empty(tmp_path: Path) -> None:
    p = save_session("///", FakeAgent(), scope=tmp_path)
    assert p.name == "default.json"
