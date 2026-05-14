"""Extended Agent tests: denied tools, multi-tool turns, errors."""
from __future__ import annotations

import pytest
from pydantic import BaseModel

from tests.conftest import ScriptedProvider
from vulpcode.agent import (
    Agent,
    ErrorEvent,
    ToolDeniedEvent,
    ToolEndEvent,
)
from vulpcode.permissions import Mode, PermissionManager
from vulpcode.providers.base import StreamChunk, ToolCall
from vulpcode.tools import Tool, ToolResult, clear_registry, tool


@pytest.mark.asyncio
async def test_agent_handles_denied_tool():
    clear_registry()

    @tool(name="Risky", description="r", requires_confirm=True)
    class T(Tool):
        class Input(BaseModel):
            x: int

        async def run(self, args: BaseModel) -> ToolResult:  # type: ignore[override]
            return ToolResult(output=str(args.x))  # type: ignore[attr-defined]

    tc = ToolCall(id="t", name="Risky", arguments={"x": 1})
    provider = ScriptedProvider(
        [
            [StreamChunk(type="tool_call", tool_call=tc), StreamChunk(type="stop")],
            [StreamChunk(type="text", delta="ok"), StreamChunk(type="stop")],
        ]
    )

    async def reject(msg: str, ctx: dict) -> str:
        return "n"

    perms = PermissionManager(config={}, mode=Mode.DEFAULT, prompter=reject)
    agent = Agent(provider=provider, tools=[T()], permissions=perms)
    events = [ev async for ev in agent.turn("?")]
    assert any(isinstance(ev, ToolDeniedEvent) for ev in events)
    clear_registry()


@pytest.mark.asyncio
async def test_agent_multi_tool_calls_in_one_response():
    clear_registry()

    @tool(name="One", description="o")
    class T(Tool):
        class Input(BaseModel):
            v: int

        async def run(self, args: BaseModel) -> ToolResult:  # type: ignore[override]
            return ToolResult(output=f"got {args.v}")  # type: ignore[attr-defined]

    tc1 = ToolCall(id="a", name="One", arguments={"v": 1})
    tc2 = ToolCall(id="b", name="One", arguments={"v": 2})
    provider = ScriptedProvider(
        [
            [
                StreamChunk(type="tool_call", tool_call=tc1),
                StreamChunk(type="tool_call", tool_call=tc2),
                StreamChunk(type="stop"),
            ],
            [StreamChunk(type="text", delta="done"), StreamChunk(type="stop")],
        ]
    )
    agent = Agent(provider=provider, tools=[T()])
    events = [ev async for ev in agent.turn("?")]
    ends = [e for e in events if isinstance(e, ToolEndEvent)]
    assert len(ends) == 2
    assert {e.tool_call.id for e in ends} == {"a", "b"}
    clear_registry()


@pytest.mark.asyncio
async def test_agent_tool_run_raises():
    clear_registry()

    @tool(name="Boom", description="b")
    class T(Tool):
        class Input(BaseModel):
            pass

        async def run(self, args: BaseModel) -> ToolResult:  # type: ignore[override]
            raise RuntimeError("kaboom")

    tc = ToolCall(id="t", name="Boom", arguments={})
    provider = ScriptedProvider(
        [
            [StreamChunk(type="tool_call", tool_call=tc), StreamChunk(type="stop")],
            [StreamChunk(type="text", delta="recovered"), StreamChunk(type="stop")],
        ]
    )
    agent = Agent(provider=provider, tools=[T()])
    events = [ev async for ev in agent.turn("?")]
    ends = [e for e in events if isinstance(e, ToolEndEvent)]
    assert len(ends) == 1
    assert ends[0].result.is_error
    assert "kaboom" in (ends[0].result.error or "")
    clear_registry()


@pytest.mark.asyncio
async def test_agent_provider_stream_error():
    provider = ScriptedProvider(
        [
            [StreamChunk(type="error", error="rate limit")],
        ]
    )
    agent = Agent(provider=provider, tools=[])
    events = [ev async for ev in agent.turn("?")]
    assert any(
        isinstance(ev, ErrorEvent) and "rate limit" in ev.error for ev in events
    )
