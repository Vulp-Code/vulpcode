"""/snapshot slash command: save, list, load."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from vulpcode.commands._base import SlashCommand
from vulpcode.harness.snapshot import SNAPSHOT_DIR

if TYPE_CHECKING:
    from vulpcode.ui.repl import Repl


class SnapshotCommand(SlashCommand):
    name = "snapshot"
    help_text = "State snapshots: /snapshot save | list | load [path]"

    async def run(self, repl: "Repl", args: str) -> None:
        subcmd, _, rest = args.strip().partition(" ")
        subcmd = subcmd.lower()
        if subcmd == "save":
            await self._save(repl)
        elif subcmd == "list":
            await self._list(repl)
        elif subcmd == "load":
            await self._load(repl, rest.strip())
        else:
            repl.renderer.console.print(
                "[yellow]Usage: /snapshot save | list | load [path][/]"
            )

    async def _save(self, repl: "Repl") -> None:
        from vulpcode.harness.snapshot import dump_state
        from vulpcode.harness.state import LoopState

        agent = repl.agent
        session_id: str = getattr(agent, "session_id", "default")
        iteration = len(agent._messages)
        state = LoopState(
            messages=list(agent._messages),
            usage=agent._session_usage,
            iteration=iteration,
        )
        path = dump_state(state, session_id=session_id, iteration=iteration)
        repl.renderer.console.print(f"[green]snapshot saved: {path}[/]")

    async def _list(self, repl: "Repl") -> None:
        agent = repl.agent
        session_id: str = getattr(agent, "session_id", "default")
        session_dir = SNAPSHOT_DIR / session_id
        if not session_dir.exists():
            repl.renderer.console.print("[yellow]no snapshots found[/]")
            return
        snapshots = sorted(session_dir.glob("iter_*.json"))
        if not snapshots:
            repl.renderer.console.print("[yellow]no snapshots found[/]")
            return
        for p in snapshots:
            repl.renderer.console.print(str(p))

    async def _load(self, repl: "Repl", path_str: str) -> None:
        from vulpcode.harness.snapshot import latest_snapshot, load_state

        agent = repl.agent
        if not path_str:
            session_id: str = getattr(agent, "session_id", "default")
            p = latest_snapshot(session_id)
            if p is None:
                repl.renderer.console.print("[red]no snapshots available to load[/]")
                return
        else:
            p = Path(path_str)
            if not p.exists():
                repl.renderer.console.print(f"[red]snapshot not found: {path_str}[/]")
                return
        state = load_state(p)
        agent._messages = list(state.messages)
        agent._session_usage = state.usage
        repl.renderer.console.print(f"[green]snapshot loaded from {p}[/]")
