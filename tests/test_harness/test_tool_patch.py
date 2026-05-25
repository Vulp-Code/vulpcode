"""Tests for the ToolPatcher middleware (FASE_07)."""
from __future__ import annotations

import logging
from typing import Any, AsyncIterator

import pytest
from pydantic import BaseModel

from vulpcode.harness.state import LoopState, StateMetadata
from vulpcode.harness.tool_patch import (
    PatchRule,
    ToolPatchConfig,
    ToolPatcher,
    _compile_rules,
)
from vulpcode.providers.base import Message, Provider, StreamChunk, ToolCall, Usage
from vulpcode.tools import Tool, ToolResult, clear_registry, tool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(**kwargs: Any) -> LoopState:
    defaults: dict[str, Any] = {
        "messages": [],
        "usage": Usage(),
        "iteration": 0,
        "metadata": StateMetadata(),
    }
    defaults.update(kwargs)
    return LoopState(**defaults)  # type: ignore[arg-type]


def _make_patcher(rules: list[dict], enabled: bool = True) -> ToolPatcher:
    cfg = ToolPatchConfig(enabled=enabled, rules=_compile_rules(rules))
    return ToolPatcher(cfg)


def _bash_call(command: str, call_id: str = "tc1") -> ToolCall:
    return ToolCall(id=call_id, name="Bash", arguments={"command": command})


def _read_call(file_path: str, call_id: str = "tc1") -> ToolCall:
    return ToolCall(id=call_id, name="Read", arguments={"file_path": file_path})


# ---------------------------------------------------------------------------
# Unit tests — ToolPatcher.__call__
# ---------------------------------------------------------------------------


def test_no_op_when_disabled() -> None:
    """When enabled=False the patcher always returns the original call."""
    patcher = _make_patcher(
        [{"tool": "Bash", "match": {"command": ".*"}, "action": "block", "message": "x"}],
        enabled=False,
    )
    state = _make_state()
    call = _bash_call("ls /")
    result = patcher(state, call=call)
    assert result is call


def test_block_returns_false() -> None:
    """A matching block rule returns False."""
    patcher = _make_patcher(
        [
            {
                "tool": "Bash",
                "match": {"command": "(?i)\\brm\\s+-rf"},
                "action": "block",
                "message": "rm -rf blocked.",
            }
        ]
    )
    state = _make_state()
    call = _bash_call("rm -rf /")
    result = patcher(state, call=call)
    assert result is False


def test_redact_substitutes_value() -> None:
    """A matching redact rule applies re.sub and returns a new ToolCall."""
    patcher = _make_patcher(
        [
            {
                "tool": "Bash",
                "match": {"command": "(?i)(secret_key)\\s*=\\s*\\S+"},
                "action": "redact",
                "replace": "\\1=***REDACTED***",
            }
        ]
    )
    state = _make_state()
    call = _bash_call("export secret_key=abc123")
    result = patcher(state, call=call)
    assert isinstance(result, ToolCall)
    assert "***REDACTED***" in result.arguments["command"]
    assert "abc123" not in result.arguments["command"]
    assert result.id == call.id
    assert result.name == call.name


def test_wildcard_tool_matches_any() -> None:
    """tool='*' makes the rule apply to any tool name."""
    patcher = _make_patcher(
        [
            {
                "tool": "*",
                "match": {"*": "(?i)password\\s*[:=]\\s*\\S+"},
                "action": "block",
                "message": "password blocked",
            }
        ]
    )
    state_bash = _make_state()
    state_read = _make_state()

    bash_call = ToolCall(
        id="b1", name="Bash", arguments={"command": "echo password=secret"}
    )
    read_call = ToolCall(
        id="r1", name="Read", arguments={"file_path": "/tmp/x", "extra": "password: s3cr3t"}
    )

    assert patcher(state_bash, call=bash_call) is False
    assert patcher(state_read, call=read_call) is False


def test_wildcard_arg_scans_all() -> None:
    """arg_name='*' in match scans all argument values."""
    patcher = _make_patcher(
        [
            {
                "tool": "Bash",
                "match": {"*": "SENSITIVE"},
                "action": "block",
                "message": "sensitive data",
            }
        ]
    )
    state = _make_state()
    # The sensitive word is in a non-standard argument
    call = ToolCall(id="t1", name="Bash", arguments={"env": "MY_VAR=SENSITIVE"})
    assert patcher(state, call=call) is False


def test_log_only_passes_through_but_logs(caplog: pytest.LogCaptureFixture) -> None:
    """action=log_only returns the original call but emits a WARNING."""
    patcher = _make_patcher(
        [
            {
                "tool": "Bash",
                "match": {"command": "ls"},
                "action": "log_only",
            }
        ]
    )
    state = _make_state()
    call = _bash_call("ls /tmp")

    with caplog.at_level(logging.WARNING, logger="vulpcode.harness.tool_patch"):
        result = patcher(state, call=call)

    assert result is call
    assert any("log_only" in r.message for r in caplog.records)


def test_rule_no_match_returns_original() -> None:
    """When no rule pattern matches, the original call is returned unchanged."""
    patcher = _make_patcher(
        [{"tool": "Bash", "match": {"command": "NOMATCH_XYZ"}, "action": "block"}]
    )
    state = _make_state()
    call = _bash_call("echo hello")
    result = patcher(state, call=call)
    assert result is call


def test_multiple_rules_first_match_wins() -> None:
    """When multiple rules would match, only the first (in order) is applied."""
    patcher = _make_patcher(
        [
            # First rule: block
            {
                "tool": "Bash",
                "match": {"command": "rm"},
                "action": "block",
                "message": "first rule",
            },
            # Second rule: redact — should NOT run
            {
                "tool": "Bash",
                "match": {"command": "rm"},
                "action": "redact",
                "replace": "REPLACED",
            },
        ]
    )
    state = _make_state()
    call = _bash_call("rm /tmp/file")
    result = patcher(state, call=call)
    # First rule wins → blocked
    assert result is False
    assert state.metadata.get("last_block_message") == "first rule"


def test_block_with_message() -> None:
    """block action stores rule.message in state.metadata['last_block_message']."""
    patcher = _make_patcher(
        [
            {
                "tool": "Bash",
                "match": {"command": "dangerous"},
                "action": "block",
                "message": "Refused: dangerous command blocked.",
            }
        ]
    )
    state = _make_state()
    call = _bash_call("run dangerous op")
    result = patcher(state, call=call)
    assert result is False
    assert state.metadata.get("last_block_message") == "Refused: dangerous command blocked."


def test_invalid_regex_in_config_raises_at_load() -> None:
    """A syntactically invalid regex raises ValueError when the rules are compiled."""
    with pytest.raises(ValueError, match="Invalid regex"):
        _compile_rules(
            [{"tool": "Bash", "match": {"command": "(?P<"}, "action": "block"}]
        )


def test_redact_logs_info(caplog: pytest.LogCaptureFixture) -> None:
    """Redact action logs at INFO level."""
    patcher = _make_patcher(
        [
            {
                "tool": "Bash",
                "match": {"command": "secret"},
                "action": "redact",
                "replace": "***",
            }
        ]
    )
    state = _make_state()
    call = _bash_call("export secret=xyz")

    with caplog.at_level(logging.INFO, logger="vulpcode.harness.tool_patch"):
        patcher(state, call=call)

    assert any("[redact]" in r.message for r in caplog.records)


def test_block_logs_info(caplog: pytest.LogCaptureFixture) -> None:
    """Block action logs at INFO level."""
    patcher = _make_patcher(
        [
            {
                "tool": "Bash",
                "match": {"command": "evil"},
                "action": "block",
                "message": "blocked",
            }
        ]
    )
    state = _make_state()
    call = _bash_call("do evil things")

    with caplog.at_level(logging.INFO, logger="vulpcode.harness.tool_patch"):
        patcher(state, call=call)

    assert any("[block]" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Integration test — ToolPatcher wired into Agent
# ---------------------------------------------------------------------------


class _MockProvider(Provider):
    name = "mock"

    def __init__(self, scripted: list[list[StreamChunk]]) -> None:
        super().__init__()
        self.scripted = list(scripted)

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict],
        model: str,
        system: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        if not self.scripted:
            yield StreamChunk(type="stop")
            return
        for ch in self.scripted.pop(0):
            yield ch

    def supports_tools(self) -> bool:
        return True

    def supports_vision(self) -> bool:
        return False


@pytest.fixture()
def _bash_tool():
    clear_registry()

    @tool(name="Bash", description="run bash")
    class BashTool(Tool):
        class Input(BaseModel):
            command: str

        async def run(self, args: BaseModel) -> ToolResult:  # type: ignore[override]
            assert isinstance(args, BashTool.Input)
            return ToolResult(output=f"ran:{args.command}")

    yield BashTool
    clear_registry()


async def test_integration_with_agent(_bash_tool: Any) -> None:
    """A block rule wired into Agent prevents tool execution; model gets is_error message."""
    from vulpcode.agent import Agent
    from vulpcode.harness.hooks import HookBus

    rm_call = ToolCall(id="tc1", name="Bash", arguments={"command": "rm -rf /"})
    provider = _MockProvider(
        [
            [
                StreamChunk(type="tool_call", tool_call=rm_call),
                StreamChunk(type="stop", stop_reason="tool_use"),
            ],
            [StreamChunk(type="text", delta="ok"), StreamChunk(type="stop")],
        ]
    )

    bus = HookBus()
    patcher = _make_patcher(
        [
            {
                "tool": "Bash",
                "match": {"command": "(?i)\\brm\\s+-rf"},
                "action": "block",
                "message": "Refused: rm -rf / blocked by tool_patch.",
            }
        ]
    )
    bus.register("before_tool_call", patcher)

    agent = Agent(provider=provider, tools=[_bash_tool()], hook_bus=bus)
    events = []
    async for ev in agent.turn("delete everything"):
        events.append(ev)

    # Tool should not have executed
    from vulpcode.agent import ToolEndEvent

    tool_end_events = [e for e in events if isinstance(e, ToolEndEvent)]
    assert not tool_end_events, "Tool should have been blocked, not executed"

    # Model should receive a tool message with the block message
    tool_msgs = [
        m
        for m in agent._messages
        if m.role == "tool" and "Refused: rm -rf / blocked by tool_patch." in (m.content or "")
    ]
    assert tool_msgs, "Expected tool message containing block message"

    # Content must also contain 'blocked' (general check)
    assert any("blocked" in (m.content or "") for m in agent._messages if m.role == "tool")
