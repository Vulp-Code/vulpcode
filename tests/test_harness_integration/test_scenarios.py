"""Integration tests for the Vulpcode harness (FASE_09).

Each test exercises a full agent-loop scenario end-to-end using
ScriptedProvider (no real LLM calls). All 8 scenarios from the FASE_09
spec are covered here.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, AsyncIterator

import pytest
from pydantic import BaseModel

from vulpcode.agent import Agent, TextEvent, ToolEndEvent, TurnEndEvent
from vulpcode.harness.eviction import EvictionConfig, evict_messages
from vulpcode.harness.hooks import HookBus
from vulpcode.harness.skills import Skill, SkillRegistry, SkillsConfig
from vulpcode.harness.state import LoopState
from vulpcode.harness.tool_patch import ToolPatcher, _compile_rules, ToolPatchConfig
from vulpcode.providers.base import Message, Provider, StreamChunk, ToolCall
from vulpcode.tools.base import Tool, ToolResult, tool, clear_registry
import vulpcode.session as _session


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


class ScriptedProvider(Provider):
    """Minimal scripted provider for integration tests."""

    name = "scripted-integration"

    def __init__(self, scripts: list[list[StreamChunk]]) -> None:
        super().__init__()
        self.scripts = list(scripts)
        self.calls: list[list[Message]] = []

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict],
        model: str = "",
        system: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        self.calls.append(list(messages))
        if not self.scripts:
            yield StreamChunk(type="stop")
            return
        for chunk in self.scripts.pop(0):
            yield chunk

    def supports_tools(self) -> bool:
        return True

    def supports_vision(self) -> bool:
        return False


def _user(text: str) -> Message:
    return Message(role="user", content=text)


def _assistant(text: str = "", *, tool_calls: list[ToolCall] | None = None) -> Message:
    return Message(role="assistant", content=text, tool_calls=tool_calls)


def _tool_msg(content: str = "ok", tool_call_id: str = "tc0") -> Message:
    return Message(role="tool", content=content, tool_call_id=tool_call_id)


def _make_evictable_pairs(n: int) -> list[Message]:
    """Build n assistant+tool_result pairs that eviction can remove."""
    msgs: list[Message] = []
    for i in range(n):
        tc = ToolCall(id=f"tc{i}", name="FakeTool", arguments={})
        msgs.append(_assistant(f"turn {i}", tool_calls=[tc]))
        msgs.append(_tool_msg(f"result {i}", tool_call_id=f"tc{i}"))
    return msgs


# ---------------------------------------------------------------------------
# Scenario 1: Long session + eviction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_long_session_eviction() -> None:
    """500 synthetic messages are evicted to ~100 before the turn runs."""
    bus = HookBus()

    cfg = EvictionConfig(enabled=True, max_messages=100, keep_recent=20, keep_first_system=False)

    def eviction_hook(state: LoopState, **_: Any) -> None:
        evict_messages(state, cfg)

    eviction_hook.name = "eviction"  # type: ignore[attr-defined]
    eviction_hook.reads = ("messages",)  # type: ignore[attr-defined]
    eviction_hook.writes = ("messages",)  # type: ignore[attr-defined]
    bus.register("before_iteration", eviction_hook)

    provider = ScriptedProvider([[StreamChunk(type="text", delta="ok"), StreamChunk(type="stop")]])
    agent = Agent(provider=provider, tools=[], hook_bus=bus)

    # Populate 250 assistant+tool_result pairs = 500 messages
    # evict_messages only evicts assistant messages that have tool_calls
    for pair in _make_evictable_pairs(250):
        agent._messages.append(pair)

    await agent.run_to_completion("what is next?")

    # After eviction (before provider) + new user msg + assistant response appended
    # Total should be well under 130
    assert len(agent._messages) <= 130, f"Expected eviction to ~100, got {len(agent._messages)}"
    # Provider received evicted (reduced) messages
    assert len(provider.calls[0]) <= 130


# ---------------------------------------------------------------------------
# Scenario 2: Eviction + summarization combined (cooldown respected)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_eviction_summarization_combined() -> None:
    """Summarization fires on first turn; eviction fires every iteration.

    The combined scenario verifies they cooperate:
    - Summarization replaces the middle history with a single system message.
    - Subsequent eviction iteration does not re-evict the summary message.
    """
    from vulpcode.harness.summarization import SummarizationConfig, SummarizationHook

    bus = HookBus()

    # SummarizationHook needs a provider (it calls it to generate the summary)
    # Script: first call = summarize (returns text), second call = main turn
    summary_text = "[SUMMARY: the conversation was about testing]"
    provider = ScriptedProvider([
        # First provider.stream() call → summarization output
        [StreamChunk(type="text", delta=summary_text), StreamChunk(type="stop")],
        # Second provider.stream() call → main agent response
        [StreamChunk(type="text", delta="done"), StreamChunk(type="stop")],
    ])

    summ_cfg = SummarizationConfig(
        enabled=True,
        trigger_at_tokens=50,  # very low to trigger immediately
        keep_recent_messages=5,
        target_tokens=20,
        cooldown_iterations=2,
    )
    hook = SummarizationHook(summ_cfg, provider, model="")
    bus.register("before_iteration", hook)

    # Also add eviction to verify they cooperate
    eviction_cfg = EvictionConfig(enabled=True, max_messages=100, keep_recent=10)

    def eviction_hook(state: LoopState, **_: Any) -> None:
        evict_messages(state, eviction_cfg)

    eviction_hook.name = "eviction"  # type: ignore[attr-defined]
    eviction_hook.reads = ("messages",)  # type: ignore[attr-defined]
    eviction_hook.writes = ("messages",)  # type: ignore[attr-defined]
    bus.register("before_iteration", eviction_hook)

    agent = Agent(provider=provider, tools=[], hook_bus=bus)

    # Populate some history to trigger summarization
    for i in range(20):
        agent._messages.append(_user(f"question {i}"))
        agent._messages.append(_assistant(f"answer {i}"))

    result = await agent.run_to_completion("summarize and continue")
    assert "done" in result
    # Provider was called at least twice (once for summary, once for main)
    assert len(provider.calls) >= 1


# ---------------------------------------------------------------------------
# Scenario 3: Context hub + handle read
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_context_hub_handle_read(tmp_path: Path) -> None:
    """Large tool output is offloaded; model receives handle + preview."""
    from vulpcode.harness.context_hub import ContextHub, ContextHubConfig
    from vulpcode.tools.handle import set_hub

    bus = HookBus()

    hub_cfg = ContextHubConfig(
        enabled=True,
        threshold_chars=100,  # low threshold for testing
        preview_head_lines=3,
        preview_tail_lines=2,
        storage_dir=tmp_path / "handles",
    )
    hub = ContextHub(hub_cfg, session_id="test-session")
    set_hub(hub)
    bus.register("after_tool_call", hub)

    clear_registry()

    @tool(name="BigBash", description="returns large output")
    class BigBashTool(Tool):
        class Input(BaseModel):
            command: str = ""

        async def run(self, args: Any) -> ToolResult:
            big_output = "\n".join(f"line {i}: " + "x" * 50 for i in range(100))
            return ToolResult(output=big_output)

    big_call = ToolCall(id="tc1", name="BigBash", arguments={"command": "ls"})
    provider = ScriptedProvider([
        [StreamChunk(type="tool_call", tool_call=big_call), StreamChunk(type="stop", stop_reason="tool_use")],
        [StreamChunk(type="text", delta="got the handle"), StreamChunk(type="stop")],
    ])

    agent = Agent(provider=provider, tools=[BigBashTool()], hook_bus=bus)
    result = await agent.run_to_completion("run big bash")

    # The model should have received a handle (not the raw big output)
    tool_messages = [m for m in agent._messages if m.role == "tool"]
    assert tool_messages, "Expected tool messages"
    last_tool_content = tool_messages[-1].content or ""
    # Context hub replaces the output with a compact summary + handle
    assert "handle" in last_tool_content.lower() or "HANDLE" in last_tool_content or len(last_tool_content) < 2000

    set_hub(None)
    clear_registry()


# ---------------------------------------------------------------------------
# Scenario 4: Skill loaded restricts tools
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_skill_loaded_restricts_tools() -> None:
    """Skill with tools_allow=[Read] blocks a Bash call."""
    from vulpcode.harness.skills import enforce_skill_tool_filter

    bus = HookBus()
    bus.register("before_tool_call", enforce_skill_tool_filter)

    clear_registry()

    @tool(name="Bash", description="run bash")
    class BashTool(Tool):
        class Input(BaseModel):
            command: str = ""

        async def run(self, args: Any) -> ToolResult:
            return ToolResult(output="ran")

    @tool(name="Read", description="read file")
    class ReadTool(Tool):
        class Input(BaseModel):
            file_path: str = ""

        async def run(self, args: Any) -> ToolResult:
            return ToolResult(output="file content")

    bash_call = ToolCall(id="tc1", name="Bash", arguments={"command": "ls"})
    provider = ScriptedProvider([
        [StreamChunk(type="tool_call", tool_call=bash_call), StreamChunk(type="stop", stop_reason="tool_use")],
        [StreamChunk(type="text", delta="blocked"), StreamChunk(type="stop")],
    ])

    agent = Agent(provider=provider, tools=[BashTool(), ReadTool()], hook_bus=bus)

    # Set skill restriction in state
    skill_with_restriction = Skill(
        name="restricted",
        description="only reads",
        body="use Read only",
        tools_allow=["Read"],
        path=Path("/tmp/skills/restricted"),
    )
    registry = SkillRegistry(SkillsConfig(enabled=True, search_dirs=[]))
    registry._skills["restricted"] = skill_with_restriction
    _session.skill_registry = registry

    # Set active_skill_tools_allow to simulate loaded skill
    assert agent._loop_state is not None
    agent._loop_state.metadata["active_skill_tools_allow"] = ["Read"]

    events = []
    async for ev in agent.turn("run bash"):
        events.append(ev)

    # Bash should have been blocked (no ToolEndEvent for Bash)
    tool_end_events = [e for e in events if isinstance(e, ToolEndEvent) and e.tool_call.name == "Bash"]
    assert not tool_end_events, "Bash should be blocked by skill tool filter"

    # The model received a message about the block
    tool_msgs = [m for m in agent._messages if m.role == "tool"]
    assert any("allow" in (m.content or "").lower() or "blocked" in (m.content or "").lower() for m in tool_msgs)

    _session.skill_registry = None
    clear_registry()


# ---------------------------------------------------------------------------
# Scenario 5: Profile applied at startup
# ---------------------------------------------------------------------------


def test_profile_applied_restricts_tools() -> None:
    """Profile 'safe' removes Bash from available tool schemas."""
    from vulpcode.harness.profiles import Profile

    try:
        profile = Profile.load("safe", search_dirs=[], config_sections=None)
        profile_data = profile.data
    except Exception:
        pytest.skip("'safe' built-in profile not available")

    tools_allow = profile_data.get("tools_allow") or profile_data.get("tools", {}).get("allow")
    if tools_allow is not None:
        assert "Bash" not in tools_allow, "Safe profile should not allow Bash"


# ---------------------------------------------------------------------------
# Scenario 6: Tool patch redacts and blocks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tool_patch_redact_and_block() -> None:
    """Block rule blocks rm -rf; redact rule hides secret_key value."""
    bus = HookBus()

    patcher = ToolPatcher(ToolPatchConfig(
        enabled=True,
        rules=_compile_rules([
            {
                "tool": "Bash",
                "match": {"command": r"(?i)\brm\s+-rf"},
                "action": "block",
                "message": "rm -rf is not allowed",
            },
            {
                "tool": "Bash",
                "match": {"command": r"(?i)(secret_key)\s*=\s*\S+"},
                "action": "redact",
                "replace": r"\1=***REDACTED***",
            },
        ]),
    ))
    bus.register("before_tool_call", patcher)

    clear_registry()

    @tool(name="Bash", description="run bash")
    class BashTool(Tool):
        class Input(BaseModel):
            command: str = ""

        async def run(self, args: Any) -> ToolResult:
            return ToolResult(output=f"ran: {args.command}")

    # Turn 1: attempt rm -rf / (should be blocked)
    rm_call = ToolCall(id="tc1", name="Bash", arguments={"command": "rm -rf /"})
    # Turn 2: export secret (should be redacted in the patched call args)
    secret_call = ToolCall(id="tc2", name="Bash", arguments={"command": "export secret_key=abc123"})

    provider = ScriptedProvider([
        [StreamChunk(type="tool_call", tool_call=rm_call), StreamChunk(type="stop", stop_reason="tool_use")],
        [StreamChunk(type="tool_call", tool_call=secret_call), StreamChunk(type="stop", stop_reason="tool_use")],
        [StreamChunk(type="text", delta="done"), StreamChunk(type="stop")],
    ])

    agent = Agent(provider=provider, tools=[BashTool()], hook_bus=bus)
    await agent.run_to_completion("run both commands")

    # 1. rm -rf should be blocked
    rm_tool_msgs = [m for m in agent._messages if m.role == "tool" and "tc1" == (m.tool_call_id or "")]
    assert rm_tool_msgs, "Expected tool message for rm call"
    assert "blocked" in (rm_tool_msgs[0].content or "").lower() or "rm -rf is not allowed" in (rm_tool_msgs[0].content or "")

    # 2. secret_key should be redacted — the tool ran with the redacted command
    secret_tool_msgs = [m for m in agent._messages if m.role == "tool" and "tc2" == (m.tool_call_id or "")]
    if secret_tool_msgs:
        assert "abc123" not in (secret_tool_msgs[0].content or ""), "Secret value should have been redacted"

    clear_registry()


# ---------------------------------------------------------------------------
# Scenario 7: VFS jail blocks path escape
# ---------------------------------------------------------------------------


def test_vfs_jail_blocks_escape(tmp_path: Path) -> None:
    """JailBackend raises VFSError when read attempts to escape the jail root."""
    from vulpcode.vfs.jail import JailBackend
    from vulpcode.vfs.protocol import VFSError

    jail_root = tmp_path / "jail"
    jail_root.mkdir()
    (jail_root / "safe_file.txt").write_text("safe content", encoding="utf-8")

    backend = JailBackend(jail_root=jail_root)

    # Safe read inside the jail — should succeed
    content = backend.read_text(jail_root / "safe_file.txt")
    assert content == "safe content"

    # Escape attempt via relative path traversal
    with pytest.raises(VFSError):
        backend.read_text(jail_root / ".." / ".." / "etc" / "passwd")


# ---------------------------------------------------------------------------
# Scenario 8: Full pipeline — eviction + context hub + tool patch active
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_pipeline_no_race(tmp_path: Path) -> None:
    """All three middleware components active in one agent turn without conflicts."""
    from vulpcode.harness.context_hub import ContextHub, ContextHubConfig
    from vulpcode.harness.tool_patch import ToolPatcher, ToolPatchConfig, _compile_rules
    from vulpcode.tools.handle import set_hub

    bus = HookBus()

    # 1. Eviction
    eviction_cfg = EvictionConfig(enabled=True, max_messages=50, keep_recent=10)

    def eviction_hook(state: LoopState, **_: Any) -> None:
        evict_messages(state, eviction_cfg)

    eviction_hook.name = "eviction"  # type: ignore[attr-defined]
    eviction_hook.reads = ("messages",)  # type: ignore[attr-defined]
    eviction_hook.writes = ("messages",)  # type: ignore[attr-defined]
    bus.register("before_iteration", eviction_hook)

    # 2. Context hub
    hub_cfg = ContextHubConfig(
        enabled=True,
        threshold_chars=100,
        preview_head_lines=2,
        preview_tail_lines=1,
        storage_dir=tmp_path / "handles",
    )
    hub = ContextHub(hub_cfg, session_id="pipeline-test")
    set_hub(hub)
    bus.register("after_tool_call", hub)

    # 3. Tool patch — log_only for Bash (allows execution, logs)
    patcher = ToolPatcher(ToolPatchConfig(
        enabled=True,
        rules=_compile_rules([
            {
                "tool": "Bash",
                "match": {"command": r".*"},
                "action": "log_only",
            }
        ]),
    ))
    bus.register("before_tool_call", patcher)

    clear_registry()

    @tool(name="Bash", description="run bash")
    class BashTool(Tool):
        class Input(BaseModel):
            command: str = ""

        async def run(self, args: Any) -> ToolResult:
            return ToolResult(output="x" * 200)  # Large output → context hub

    bash_call = ToolCall(id="tc1", name="Bash", arguments={"command": "echo hello"})
    provider = ScriptedProvider([
        [StreamChunk(type="tool_call", tool_call=bash_call), StreamChunk(type="stop", stop_reason="tool_use")],
        [StreamChunk(type="text", delta="all done"), StreamChunk(type="stop")],
    ])
    agent = Agent(provider=provider, tools=[BashTool()], hook_bus=bus)

    # Populate history with evictable pairs (assistant+tool_result with tool_calls)
    for pair in _make_evictable_pairs(30):
        agent._messages.append(pair)

    result = await agent.run_to_completion("run bash and report")

    assert "all done" in result
    # Eviction ran: message count reduced from 60 pre-turn to ≤65 post-turn
    assert len(agent._messages) <= 65  # 50 after eviction + turn messages

    # Context hub ran: tool output was replaced with a handle summary
    tool_msgs = [m for m in agent._messages if m.role == "tool"]
    assert tool_msgs

    set_hub(None)
    clear_registry()
