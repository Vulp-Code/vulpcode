"""Tests for stream_agent_turn (UI <-> Agent glue)."""
import io

import pytest
from pydantic import BaseModel
from rich.console import Console

from vulpcode.agent import Agent
from vulpcode.providers import StreamChunk, ToolCall
from vulpcode.providers.base import Provider
from vulpcode.tools import Tool, ToolResult, clear_registry, tool
from vulpcode.ui import Renderer, get_theme, stream_agent_turn


class StaticProvider(Provider):
    name = "static"

    def __init__(self, scripted):
        super().__init__()
        self.scripted = list(scripted)

    async def stream(self, messages, tools, model, system=None, **kwargs):
        if not self.scripted:
            yield StreamChunk(type="stop")
            return
        for ch in self.scripted.pop(0):
            yield ch

    def supports_tools(self):
        return True

    def supports_vision(self):
        return False


def _make_renderer():
    buf = io.StringIO()
    console = Console(file=buf, width=80, force_terminal=False, color_system=None)
    return Renderer(console, get_theme("default")), buf


@pytest.mark.asyncio
async def test_stream_text_only():
    p = StaticProvider(
        [
            [
                StreamChunk(type="text", delta="hi"),
                StreamChunk(type="stop"),
            ]
        ]
    )
    a = Agent(provider=p, tools=[], system="s")
    r, buf = _make_renderer()
    await stream_agent_turn(a, "?", r, spinner=False)
    assert "hi" in buf.getvalue()


@pytest.mark.asyncio
async def test_stream_with_tool():
    clear_registry()

    @tool(name="Greet", description="g")
    class T(Tool):
        class Input(BaseModel):
            name: str

        async def run(self, args):
            return ToolResult(output=f"hello {args.name}")

    p = StaticProvider(
        [
            [
                StreamChunk(
                    type="tool_call",
                    tool_call=ToolCall(
                        id="1", name="Greet", arguments={"name": "world"}
                    ),
                ),
                StreamChunk(type="stop"),
            ],
            [
                StreamChunk(type="text", delta="done"),
                StreamChunk(type="stop"),
            ],
        ]
    )
    a = Agent(provider=p, tools=[T()], system="s")
    r, buf = _make_renderer()
    await stream_agent_turn(a, "?", r, spinner=False)
    out = buf.getvalue()
    assert "Greet" in out
    assert "hello world" in out
    assert "done" in out
    clear_registry()
