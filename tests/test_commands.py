"""Tests for slash commands."""
from __future__ import annotations

import io
from typing import Any, AsyncIterator

from rich.console import Console

import vulpcode.tools  # noqa: F401  (force tool registration)
from vulpcode.agent import Agent
from vulpcode.commands import (
    CompactCommand,
    CostCommand,
    LoadCommand,
    McpCommand,
    ModelCommand,
    ProviderCommand,
    SaveCommand,
    SlashCommand,
    ToolsCommand,
    build_default_commands,
)
from vulpcode.providers.base import (
    Message,
    Provider,
    StreamChunk,
    Usage,
)
from vulpcode.ui import Renderer, get_theme


class FakeRepl:
    def __init__(self, agent: Any = None) -> None:
        buf = io.StringIO()
        console = Console(
            file=buf, width=80, force_terminal=False, color_system=None
        )
        self.renderer = Renderer(console, get_theme("default"))
        self.agent = agent
        self.buf = buf


class _SummaryProvider(Provider):
    name = "summary"

    def __init__(self, text: str = "summary text") -> None:
        super().__init__()
        self._text = text

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        model: str,
        system: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(type="text", delta=self._text)
        yield StreamChunk(type="stop")

    def supports_tools(self) -> bool:
        return False

    def supports_vision(self) -> bool:
        return False


class _RaisingProvider(Provider):
    name = "raising"

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        model: str,
        system: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        raise RuntimeError("boom")
        yield  # pragma: no cover

    def supports_tools(self) -> bool:
        return False

    def supports_vision(self) -> bool:
        return False


async def test_tools_command_lists_registered():
    repl = FakeRepl()
    await ToolsCommand().run(repl, "")
    output = repl.buf.getvalue()
    assert "Active tools" in output
    assert "Read" in output or "Bash" in output


async def test_cost_command_no_data():
    class _BareAgent:
        pass

    repl = FakeRepl(agent=_BareAgent())
    await CostCommand().run(repl, "")
    assert "no usage" in repl.buf.getvalue()


async def test_cost_command_renders_usage():
    class _AgentWithUsage:
        _session_usage = Usage(
            input_tokens=10,
            output_tokens=20,
            cache_read_tokens=3,
            cache_creation_tokens=5,
        )

    repl = FakeRepl(agent=_AgentWithUsage())
    await CostCommand().run(repl, "")
    output = repl.buf.getvalue()
    assert "Session usage" in output
    assert "10" in output
    assert "20" in output


def test_build_default_commands():
    cmds = build_default_commands()
    assert "tools" in cmds
    assert "cost" in cmds
    assert "compact" in cmds
    assert "provider" in cmds
    assert "model" in cmds
    assert all(isinstance(c, SlashCommand) for c in cmds.values())


async def test_compact_command_short_history():
    agent = Agent(provider=_SummaryProvider(), tools=[], system="s")
    agent._messages = [
        Message(role="user", content="hi"),
        Message(role="assistant", content="hello"),
    ]
    repl = FakeRepl(agent=agent)
    await CompactCommand().run(repl, "")
    assert "too short" in repl.buf.getvalue()
    assert len(agent._messages) == 2


async def test_compact_command_summarizes_and_replaces_history():
    agent = Agent(provider=_SummaryProvider("brief"), tools=[], system="s")
    agent._messages = [
        Message(role="user", content="m1"),
        Message(role="assistant", content="m2"),
        Message(role="user", content="m3"),
        Message(role="assistant", content="m4"),
    ]
    repl = FakeRepl(agent=agent)
    await CompactCommand().run(repl, "")
    assert len(agent._messages) == 2
    assert agent._messages[0].role == "user"
    assert agent._messages[0].content == "<previous conversation summary>"
    assert agent._messages[1].role == "assistant"
    assert agent._messages[1].content == "brief"
    assert "history compacted" in repl.buf.getvalue()


async def test_compact_command_preserves_history_on_error():
    agent = Agent(provider=_RaisingProvider(), tools=[], system="s")
    original = [
        Message(role="user", content="m1"),
        Message(role="assistant", content="m2"),
        Message(role="user", content="m3"),
        Message(role="assistant", content="m4"),
    ]
    agent._messages = list(original)
    repl = FakeRepl(agent=agent)
    await CompactCommand().run(repl, "")
    assert agent._messages == original
    assert "compact failed" in repl.buf.getvalue()


async def test_agent_aggregates_session_usage():
    class _UsageProvider(Provider):
        name = "usage"

        async def stream(
            self,
            messages: list[Message],
            tools: list[dict[str, Any]],
            model: str,
            system: str | None = None,
            **kwargs: Any,
        ) -> AsyncIterator[StreamChunk]:
            yield StreamChunk(type="text", delta="ok")
            yield StreamChunk(
                type="usage",
                usage=Usage(
                    input_tokens=4,
                    output_tokens=2,
                    cache_read_tokens=1,
                    cache_creation_tokens=0,
                ),
            )
            yield StreamChunk(type="stop")

        def supports_tools(self) -> bool:
            return False

        def supports_vision(self) -> bool:
            return False

    agent = Agent(provider=_UsageProvider(), tools=[], system="s")
    async for _ in agent.turn("hi"):
        pass
    async for _ in agent.turn("hi again"):
        pass
    assert agent._session_usage.input_tokens == 8
    assert agent._session_usage.output_tokens == 4
    assert agent._session_usage.cache_read_tokens == 2
    assert agent._session_usage.cache_creation_tokens == 0


class _StubProvider(Provider):
    name = "stub"

    def __init__(self, models: list[str] | None = None) -> None:
        super().__init__()
        self._models = models or []
        self.closed = False

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        model: str,
        system: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(type="stop")

    def supports_tools(self) -> bool:
        return False

    def supports_vision(self) -> bool:
        return False

    async def list_models(self) -> list[str]:
        return list(self._models)

    async def aclose(self) -> None:
        self.closed = True


class _Agent:
    def __init__(self, provider: Provider, model: str = "") -> None:
        self.provider = provider
        self.model = model


async def test_provider_command_lists():
    agent = _Agent(provider=_StubProvider())
    repl = FakeRepl(agent=agent)
    repl.config = {"providers": {}}
    await ProviderCommand().run(repl, "")
    output = repl.buf.getvalue()
    assert "anthropic" in output
    assert "openai" in output


async def test_provider_command_unknown_name():
    agent = _Agent(provider=_StubProvider())
    repl = FakeRepl(agent=agent)
    repl.config = {"providers": {}}
    await ProviderCommand().run(repl, "no-such-provider")
    assert "Unknown provider" in repl.buf.getvalue()


async def test_provider_command_switches_and_closes_old():
    old = _StubProvider()
    agent = _Agent(provider=old)
    repl = FakeRepl(agent=agent)
    repl.config = {"providers": {"ollama": {"base_url": "http://localhost:11434"}}}
    await ProviderCommand().run(repl, "ollama")
    assert old.closed is True
    assert agent.provider is not old
    assert agent.provider.name == "ollama"
    assert "switched to ollama" in repl.buf.getvalue()


async def test_model_command_lists():
    agent = _Agent(provider=_StubProvider(models=["m1", "m2"]), model="m1")
    repl = FakeRepl(agent=agent)
    await ModelCommand().run(repl, "")
    output = repl.buf.getvalue()
    assert "m1" in output
    assert "m2" in output


async def test_model_command_set():
    agent = _Agent(provider=_StubProvider(models=["m1", "m2"]), model="")
    repl = FakeRepl(agent=agent)
    await ModelCommand().run(repl, "m1")
    assert agent.model == "m1"
    assert "model set to m1" in repl.buf.getvalue()


async def test_model_command_empty_list_falls_back():
    agent = _Agent(provider=_StubProvider(models=[]), model="current-model")
    repl = FakeRepl(agent=agent)
    await ModelCommand().run(repl, "")
    output = repl.buf.getvalue()
    assert "no models reported" in output
    assert "current-model" in output


class _SessionAgent:
    def __init__(self) -> None:
        self.model = "m"
        self.system = "s"
        self._messages: list[Message] = [Message(role="user", content="hi")]
        self.provider = type("P", (), {"name": "x"})()


async def test_save_and_load_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(
        "pathlib.Path.home", classmethod(lambda cls: tmp_path)
    )
    agent = _SessionAgent()
    repl = FakeRepl(agent=agent)
    await SaveCommand().run(repl, "test1")
    output = repl.buf.getvalue()
    assert "saved session to" in output
    saved_path = tmp_path / ".vulpcode" / "sessions" / "test1.json"
    assert saved_path.exists()

    agent._messages = []
    await LoadCommand().run(repl, "test1")
    assert len(agent._messages) == 1
    assert agent._messages[0].role == "user"
    assert agent._messages[0].content == "hi"


async def test_load_missing_session_renders_error(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(
        "pathlib.Path.home", classmethod(lambda cls: tmp_path)
    )
    agent = _SessionAgent()
    repl = FakeRepl(agent=agent)
    await LoadCommand().run(repl, "missing")
    assert "no saved session" in repl.buf.getvalue()


async def test_mcp_lists_servers():
    repl = FakeRepl()
    repl.config = {
        "mcp": {
            "servers": [
                {"name": "fs", "command": "npx", "args": ["-y", "x"]}
            ]
        }
    }
    await McpCommand().run(repl, "")
    output = repl.buf.getvalue()
    assert "fs" in output
    assert "npx" in output


async def test_mcp_no_servers_configured():
    repl = FakeRepl()
    repl.config = {}
    await McpCommand().run(repl, "")
    assert "no MCP servers" in repl.buf.getvalue()


def test_build_default_commands_includes_session_and_mcp():
    cmds = build_default_commands()
    assert "save" in cmds
    assert "load" in cmds
    assert "mcp" in cmds
    assert isinstance(cmds["save"], SaveCommand)
    assert isinstance(cmds["load"], LoadCommand)
    assert isinstance(cmds["mcp"], McpCommand)
