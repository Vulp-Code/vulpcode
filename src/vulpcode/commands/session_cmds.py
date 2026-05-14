"""/save and /load slash commands."""
from __future__ import annotations

from typing import TYPE_CHECKING

from vulpcode.commands._base import SlashCommand
from vulpcode.session import load_session, save_session

if TYPE_CHECKING:
    from vulpcode.ui.repl import Repl


class SaveCommand(SlashCommand):
    name = "save"
    help_text = "Save current session messages: /save <name>"

    async def run(self, repl: "Repl", args: str) -> None:
        name = args.strip() or "default"
        path = save_session(name, repl.agent)
        repl.renderer.console.print(f"[green]saved session to {path}[/]")


class LoadCommand(SlashCommand):
    name = "load"
    help_text = "Load a saved session: /load <name>"

    async def run(self, repl: "Repl", args: str) -> None:
        name = args.strip() or "default"
        try:
            load_session(name, repl.agent)
        except FileNotFoundError:
            repl.renderer.render_error(f"no saved session named {name!r}")
            return
        repl.renderer.console.print(f"[green]loaded session {name}[/]")
