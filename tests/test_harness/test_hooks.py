"""Tests for HookBus and agent-loop hook integration."""
from __future__ import annotations

from typing import Any, AsyncIterator

import pytest
from pydantic import BaseModel

from vulpcode.agent import Agent, ErrorEvent, ToolEndEvent, TurnEndEvent
from vulpcode.harness.hooks import HookBus, LoopState
from vulpcode.providers.base import Message, Provider, StreamChunk, ToolCall, Usage
from vulpcode.tools import Tool, ToolResult, clear_registry, tool


# ---------------------------------------------------------------------------
# Helpers / fakes
# ---------------------------------------------------------------------------


def _make_state(**kwargs: Any) -> LoopState:
    defaults = dict(messages=[], usage=Usage(), iteration=0)
    defaults.update(kwargs)
    return LoopState(**defaults)  # type: ignore[arg-type]


class _MockProvider(Provider):
    name = "mock"

    def __init__(self, scripted: list[list[StreamChunk]]) -> None:
        super().__init__()
        self.scripted = list(scripted)
        self.stream_calls = 0

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict],
        model: str,
        system: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        self.stream_calls += 1
        if not self.scripted:
            yield StreamChunk(type="stop")
            return
        for ch in self.scripted.pop(0):
            yield ch

    def supports_tools(self) -> bool:
        return True

    def supports_vision(self) -> bool:
        return False


# ---------------------------------------------------------------------------
# HookBus unit tests
# ---------------------------------------------------------------------------


def test_emit_calls_hooks_in_order() -> None:
    bus = HookBus()
    order: list[int] = []
    state = _make_state()

    def h1(s: LoopState, **kw: Any) -> None:
        order.append(1)

    def h2(s: LoopState, **kw: Any) -> None:
        order.append(2)

    def h3(s: LoopState, **kw: Any) -> None:
        order.append(3)

    h1.name = "h1"
    h2.name = "h2"
    h3.name = "h3"

    bus.register("before_iteration", h1)
    bus.register("before_iteration", h2)
    bus.register("before_iteration", h3)
    bus.emit("before_iteration", state)

    assert order == [1, 2, 3]


def test_emit_collects_returns() -> None:
    bus = HookBus()
    state = _make_state()

    def noop(s: LoopState, **kw: Any) -> None:
        return None

    def returns_value(s: LoopState, **kw: Any) -> str:
        return "hello"

    noop.name = "noop"
    returns_value.name = "returns_value"

    bus.register("before_send", noop)
    bus.register("before_send", returns_value)
    results = bus.emit("before_send", state)

    assert results == [None, "hello"]


def test_emit_swallows_exception() -> None:
    bus = HookBus()
    state = _make_state()
    ran_after: list[bool] = []

    def bad_hook(s: LoopState, **kw: Any) -> None:
        raise RuntimeError("oops")

    def good_hook(s: LoopState, **kw: Any) -> str:
        ran_after.append(True)
        return "ok"

    bad_hook.name = "bad_hook"
    good_hook.name = "good_hook"

    bus.register("before_compress", bad_hook)
    bus.register("before_compress", good_hook)

    results = bus.emit("before_compress", state)

    assert ran_after == [True]
    assert results == ["ok"]


# ---------------------------------------------------------------------------
# Agent integration tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def _echo_tool():
    clear_registry()

    @tool(name="Echo", description="echo")
    class Echo(Tool):
        class Input(BaseModel):
            text: str

        async def run(self, args: BaseModel) -> ToolResult:  # type: ignore[override]
            assert isinstance(args, Echo.Input)
            return ToolResult(output=f"echoed:{args.text}")

    yield Echo
    clear_registry()


async def test_agent_emits_before_iteration() -> None:
    """before_iteration hook is called once per loop iteration."""
    provider = _MockProvider(
        [
            [StreamChunk(type="text", delta="hi"), StreamChunk(type="stop")],
            [StreamChunk(type="text", delta="bye"), StreamChunk(type="stop")],
        ]
    )

    bus = HookBus()
    iterations_seen: list[int] = []

    def capture(state: LoopState, **kw: Any) -> None:
        iterations_seen.append(state.iteration)

    capture.name = "capture"
    bus.register("before_iteration", capture)

    agent = Agent(provider=provider, tools=[], hook_bus=bus)
    async for _ in agent.turn("hello"):
        pass

    assert iterations_seen == [0]


async def test_agent_blocks_tool_when_hook_returns_false(_echo_tool: Any) -> None:
    """A hook returning False prevents tool execution and injects error message."""
    tool_call = ToolCall(id="tc1", name="Echo", arguments={"text": "world"})
    provider = _MockProvider(
        [
            [
                StreamChunk(type="tool_call", tool_call=tool_call),
                StreamChunk(type="stop", stop_reason="tool_use"),
            ],
            [StreamChunk(type="text", delta="done"), StreamChunk(type="stop")],
        ]
    )

    bus = HookBus()
    executed: list[bool] = []

    def blocker(state: LoopState, **kw: Any) -> bool:
        return False

    blocker.name = "blocker"
    bus.register("before_tool_call", blocker)

    agent = Agent(provider=provider, tools=[_echo_tool()], hook_bus=bus)
    events = []
    async for ev in agent.turn("go"):
        events.append(ev)

    tool_messages = [
        m for m in agent._messages if m.role == "tool" and "blocked" in (m.content or "")
    ]
    assert tool_messages, "Expected a 'blocked by hook' tool message"
    tool_end_events = [e for e in events if isinstance(e, ToolEndEvent)]
    assert not tool_end_events, "Tool should not have executed"


async def test_agent_uses_patched_tool_call(_echo_tool: Any) -> None:
    """A hook returning a ToolCall causes the agent to use the patched arguments."""
    tool_call = ToolCall(id="tc1", name="Echo", arguments={"text": "original"})
    provider = _MockProvider(
        [
            [
                StreamChunk(type="tool_call", tool_call=tool_call),
                StreamChunk(type="stop", stop_reason="tool_use"),
            ],
            [StreamChunk(type="text", delta="done"), StreamChunk(type="stop")],
        ]
    )

    bus = HookBus()

    def patcher(state: LoopState, **kw: Any) -> ToolCall:
        call: ToolCall = kw["call"]
        return ToolCall(id=call.id, name=call.name, arguments={"text": "patched"})

    patcher.name = "patcher"
    bus.register("before_tool_call", patcher)

    agent = Agent(provider=provider, tools=[_echo_tool()], hook_bus=bus)
    events = []
    async for ev in agent.turn("go"):
        events.append(ev)

    tool_end = next((e for e in events if isinstance(e, ToolEndEvent)), None)
    assert tool_end is not None
    assert tool_end.result.output == "echoed:patched"


async def test_agent_uses_patched_result(_echo_tool: Any) -> None:
    """A hook returning a ToolResult from after_tool_call replaces the real result."""
    tool_call = ToolCall(id="tc2", name="Echo", arguments={"text": "hi"})
    provider = _MockProvider(
        [
            [
                StreamChunk(type="tool_call", tool_call=tool_call),
                StreamChunk(type="stop", stop_reason="tool_use"),
            ],
            [StreamChunk(type="text", delta="done"), StreamChunk(type="stop")],
        ]
    )

    bus = HookBus()

    def result_patcher(state: LoopState, **kw: Any) -> ToolResult:
        return ToolResult(output="overridden")

    result_patcher.name = "result_patcher"
    bus.register("after_tool_call", result_patcher)

    agent = Agent(provider=provider, tools=[_echo_tool()], hook_bus=bus)
    events = []
    async for ev in agent.turn("go"):
        events.append(ev)

    tool_end = next((e for e in events if isinstance(e, ToolEndEvent)), None)
    assert tool_end is not None
    assert tool_end.result.output == "overridden"

    tool_msg = next(
        (m for m in agent._messages if m.role == "tool" and m.tool_call_id == "tc2"),
        None,
    )
    assert tool_msg is not None
    assert "overridden" in (tool_msg.content or "")
