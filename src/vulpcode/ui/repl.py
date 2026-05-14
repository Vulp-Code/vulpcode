"""Interactive REPL using prompt_toolkit."""
from __future__ import annotations

from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.patch_stdout import patch_stdout

from vulpcode.agent import Agent
from vulpcode.ui.render import Renderer
from vulpcode.ui.streaming import stream_agent_turn

_DEFAULT_SLASH_COMMANDS = ["/help", "/clear", "/exit", "/tools", "/cost", "/compact"]


class Repl:
    """Interactive REPL wiring Agent + Renderer + prompt_toolkit."""

    def __init__(
        self,
        agent: Agent,
        renderer: Renderer,
        config: dict,
        commands: dict | None = None,
    ) -> None:
        self.agent = agent
        self.renderer = renderer
        self.config = config
        self.commands = commands or {}
        history_path = Path.home() / ".vulpcode" / "history"
        history_path.parent.mkdir(parents=True, exist_ok=True)
        completer_words = _DEFAULT_SLASH_COMMANDS + [
            f"/{n}" for n in self.commands if f"/{n}" not in _DEFAULT_SLASH_COMMANDS
        ]
        self.session: PromptSession[str] = PromptSession(
            history=FileHistory(str(history_path)),
            auto_suggest=AutoSuggestFromHistory(),
            completer=WordCompleter(completer_words, ignore_case=True),
            multiline=False,
            mouse_support=False,
        )

    async def run(self) -> None:
        """Main interactive loop."""
        console = self.renderer.console
        console.print(
            f"[{self.renderer.theme.primary}]Vulpcode REPL[/]  "
            "(type /help for commands, /exit to quit)\n"
        )
        while True:
            try:
                with patch_stdout():
                    user_input = await self.session.prompt_async("> ")
            except (EOFError, KeyboardInterrupt):
                console.print("\nbye")
                return
            user_input = user_input.strip()
            if not user_input:
                continue
            if user_input.startswith("/"):
                if not await self._handle_slash(user_input):
                    return
                continue
            await stream_agent_turn(self.agent, user_input, self.renderer)

    async def one_shot(self, prompt: str) -> None:
        """Execute a single prompt and return."""
        await stream_agent_turn(self.agent, prompt, self.renderer, spinner=False)

    async def _handle_slash(self, line: str) -> bool:
        """Returns False if the loop should terminate (e.g. /exit)."""
        cmd, _, rest = line[1:].partition(" ")
        cmd = cmd.strip()
        rest = rest.strip()
        if cmd in {"exit", "quit"}:
            self.renderer.console.print("bye")
            return False
        if cmd == "clear":
            self.agent.reset()
            self.renderer.console.print(
                f"[{self.renderer.theme.muted}]history cleared[/]"
            )
            return True
        if cmd == "help":
            self._render_help()
            return True
        if cmd in self.commands:
            await self.commands[cmd].run(self, rest)
            return True
        self.renderer.console.print(
            f"[{self.renderer.theme.warning}]unknown command: /{cmd}[/]"
        )
        return True

    def _render_help(self) -> None:
        rows = [
            ["/help", "Show this help"],
            ["/clear", "Clear conversation history"],
            ["/exit", "Quit"],
        ]
        for name, cmd in self.commands.items():
            rows.append([f"/{name}", getattr(cmd, "help_text", "")])
        self.renderer.render_table("Commands", ["command", "description"], rows)
