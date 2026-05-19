"""Tests for the Agent loop."""
from __future__ import annotations

from typing import Any, AsyncIterator

import pytest
from pydantic import BaseModel

from vulpcode.agent import (
    Agent,
    ErrorEvent,
    TextEvent,
    ToolEndEvent,
    ToolStartEvent,
    TurnEndEvent,
    _looks_like_phantom_commit,
)
from vulpcode.providers.base import (
    Message,
    Provider,
    StreamChunk,
    ToolCall,
)
from vulpcode.tools import Tool, ToolResult, clear_registry, tool


class MockProvider(Provider):
    name = "mock"

    def __init__(self, scripted_chunks: list[list[StreamChunk]]):
        super().__init__()
        self.scripted = list(scripted_chunks)

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
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


@pytest.fixture
def echo_tool():
    clear_registry()

    @tool(name="Echo", description="echo")
    class T(Tool):
        class Input(BaseModel):
            text: str

        async def run(self, args: BaseModel) -> ToolResult:  # type: ignore[override]
            assert isinstance(args, T.Input)
            return ToolResult(output=f"echoed: {args.text}")

    yield T
    clear_registry()


async def test_simple_turn_no_tools():
    p = MockProvider(
        [
            [
                StreamChunk(type="text", delta="hello "),
                StreamChunk(type="text", delta="world"),
                StreamChunk(type="stop"),
            ]
        ]
    )
    a = Agent(provider=p, tools=[], system="s")
    events = []
    async for ev in a.turn("hi"):
        events.append(ev)
    text = "".join(e.text for e in events if isinstance(e, TextEvent))
    assert text == "hello world"
    assert any(isinstance(e, TurnEndEvent) for e in events)


async def test_tool_call_loop(echo_tool):
    tc = ToolCall(id="t1", name="Echo", arguments={"text": "hi"})
    p = MockProvider(
        [
            [
                StreamChunk(type="tool_call", tool_call=tc),
                StreamChunk(type="stop"),
            ],
            [
                StreamChunk(type="text", delta="done"),
                StreamChunk(type="stop"),
            ],
        ]
    )
    a = Agent(provider=p, tools=[echo_tool()], system="s")
    events = []
    async for ev in a.turn("go"):
        events.append(ev)
    starts = [e for e in events if isinstance(e, ToolStartEvent)]
    ends = [e for e in events if isinstance(e, ToolEndEvent)]
    assert len(starts) == 1 and len(ends) == 1
    assert "echoed: hi" in ends[0].result.output
    # The tool message is added to history with name and tool_call_id.
    msgs = a.messages()
    tool_msgs = [m for m in msgs if m.role == "tool"]
    assert len(tool_msgs) == 1
    assert tool_msgs[0].name == "Echo"
    assert tool_msgs[0].tool_call_id == "t1"
    assert "echoed: hi" in tool_msgs[0].content


async def test_run_to_completion_returns_text():
    p = MockProvider(
        [
            [
                StreamChunk(type="text", delta="answer"),
                StreamChunk(type="stop"),
            ]
        ]
    )
    a = Agent(provider=p, tools=[], system="s")
    out = await a.run_to_completion("?")
    assert out == "answer"


async def test_unknown_tool_yields_error():
    bad = ToolCall(id="x", name="DoesNotExist", arguments={})
    p = MockProvider(
        [
            [
                StreamChunk(type="tool_call", tool_call=bad),
                StreamChunk(type="stop"),
            ],
            [
                StreamChunk(type="text", delta="recovered"),
                StreamChunk(type="stop"),
            ],
        ]
    )
    a = Agent(provider=p, tools=[], system="s")
    events = []
    async for ev in a.turn("?"):
        events.append(ev)
    assert any(isinstance(e, ErrorEvent) for e in events)


async def test_max_iters_safety():
    clear_registry()

    @tool(name="EchoLoop", description="echo")
    class T(Tool):
        class Input(BaseModel):
            text: str

        async def run(self, args: BaseModel) -> ToolResult:  # type: ignore[override]
            return ToolResult(output="x")

    chunks = [
        [
            StreamChunk(
                type="tool_call",
                tool_call=ToolCall(id=f"{i}", name="EchoLoop", arguments={"text": "x"}),
            ),
            StreamChunk(type="stop"),
        ]
        for i in range(50)
    ]
    p = MockProvider(chunks)
    a = Agent(provider=p, tools=[T()], system="s")
    events = []
    async for ev in a.turn("loop"):
        events.append(ev)
    assert any(
        isinstance(e, ErrorEvent) and "Max iterations" in e.error for e in events
    )
    clear_registry()


def test_phantom_commit_detector_positive():
    assert _looks_like_phantom_commit("vou ler o arquivo para analise")
    assert _looks_like_phantom_commit("Vamos analisar isso agora")
    assert _looks_like_phantom_commit("Let me check the logs")
    assert _looks_like_phantom_commit("I'll read the file")
    assert _looks_like_phantom_commit("I will check that")
    assert _looks_like_phantom_commit("I'm going to open it")


def test_phantom_commit_detector_negative():
    assert not _looks_like_phantom_commit("")
    assert not _looks_like_phantom_commit("   ")
    assert not _looks_like_phantom_commit("Done.")
    assert not _looks_like_phantom_commit("O arquivo contém 42 linhas.")
    assert not _looks_like_phantom_commit("The file has 42 lines.")


async def test_phantom_commit_triggers_nudge_and_tool_call(echo_tool):
    """Empty tool_calls + commitment prose -> nudge injected, model retries."""
    tc = ToolCall(id="t1", name="Echo", arguments={"text": "hi"})
    p = MockProvider(
        [
            # 1st turn: phantom commitment, no tool call.
            [
                StreamChunk(type="text", delta="vou chamar a ferramenta"),
                StreamChunk(type="stop"),
            ],
            # 2nd turn (after nudge): actual tool call.
            [
                StreamChunk(type="tool_call", tool_call=tc),
                StreamChunk(type="stop"),
            ],
            # 3rd turn (after tool result): wrap up.
            [
                StreamChunk(type="text", delta="done"),
                StreamChunk(type="stop"),
            ],
        ]
    )
    a = Agent(provider=p, tools=[echo_tool()], system="s")
    events = []
    async for ev in a.turn("go"):
        events.append(ev)
    starts = [e for e in events if isinstance(e, ToolStartEvent)]
    assert len(starts) == 1
    # Nudge appears in history as a user message between turns.
    nudges = [
        m for m in a.messages()
        if m.role == "user" and "REMINDER" in str(m.content)
    ]
    assert len(nudges) == 1


async def test_phantom_commit_nudge_fires_only_once():
    """Even with two consecutive phantom commits, only one nudge is injected."""
    p = MockProvider(
        [
            [
                StreamChunk(type="text", delta="vou ler o arquivo"),
                StreamChunk(type="stop"),
            ],
            [
                StreamChunk(type="text", delta="vou ler agora mesmo"),
                StreamChunk(type="stop"),
            ],
        ]
    )
    a = Agent(provider=p, tools=[], system="s")
    events = []
    async for ev in a.turn("go"):
        events.append(ev)
    # The second phantom commit must end the turn (no second nudge).
    assert any(isinstance(e, TurnEndEvent) for e in events)
    nudges = [
        m for m in a.messages()
        if m.role == "user" and "REMINDER" in str(m.content)
    ]
    assert len(nudges) == 1


async def test_no_nudge_when_text_is_clean():
    """Plain assistant text with no commitment verbs -> turn ends, no nudge."""
    p = MockProvider(
        [
            [
                StreamChunk(type="text", delta="O arquivo tem 42 linhas."),
                StreamChunk(type="stop"),
            ]
        ]
    )
    a = Agent(provider=p, tools=[], system="s")
    events = []
    async for ev in a.turn("quantas linhas?"):
        events.append(ev)
    assert any(isinstance(e, TurnEndEvent) for e in events)
    nudges = [
        m for m in a.messages()
        if m.role == "user" and "REMINDER" in str(m.content)
    ]
    assert nudges == []


async def test_reset_clears_history():
    p = MockProvider(
        [
            [
                StreamChunk(type="text", delta="hi"),
                StreamChunk(type="stop"),
            ]
        ]
    )
    a = Agent(provider=p, tools=[], system="s")
    async for _ in a.turn("first"):
        pass
    assert len(a.messages()) > 0
    a.reset()
    assert a.messages() == []
