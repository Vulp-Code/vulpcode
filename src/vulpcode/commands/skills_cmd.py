"""/skills slash command: list, inspect, and reload skills."""
from __future__ import annotations

from typing import TYPE_CHECKING

from vulpcode.commands._base import SlashCommand

if TYPE_CHECKING:
    from vulpcode.ui.repl import Repl


class SkillsCommand(SlashCommand):
    name = "skills"
    help_text = "List, inspect, or reload available skills"

    async def run(self, repl: "Repl", args: str) -> None:
        """Handle /skills, /skills show NAME, /skills reload."""
        import vulpcode.session as _session

        registry = _session.get_session_skill_registry()
        parts = args.strip().split() if args.strip() else []

        if not parts:
            if registry is None or not registry.all():
                repl.renderer.console.print("[muted]no skills loaded[/]")
                return
            rows = [[s.name, s.description, str(s.path)] for s in registry.all()]
            repl.renderer.render_table("Skills", ["name", "description", "path"], rows)

        elif parts[0] == "show":
            if len(parts) < 2:
                repl.renderer.console.print("[red]Usage: /skills show NAME[/]")
                return
            name = parts[1]
            if registry is None:
                repl.renderer.console.print("[red]Skill registry not configured.[/]")
                return
            skill = registry.get(name)
            if skill is None:
                available = [s.name for s in registry.all()]
                repl.renderer.console.print(
                    f"[red]Skill {name!r} not found. Available: {available}[/]"
                )
                return
            repl.renderer.console.print(skill.body)

        elif parts[0] == "reload":
            if registry is None:
                repl.renderer.console.print("[muted]no skill registry to reload[/]")
                return
            registry.reload()
            count = len(registry.all())
            repl.renderer.console.print(f"[green]reloaded {count} skill(s)[/]")

        else:
            repl.renderer.console.print(f"[red]Unknown subcommand: {parts[0]!r}[/]")
