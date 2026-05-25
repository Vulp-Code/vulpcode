"""/profile slash command: show active profile, list profiles, or switch."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from vulpcode.commands._base import SlashCommand

if TYPE_CHECKING:
    from vulpcode.ui.repl import Repl


def _default_search_dirs() -> list[Path]:
    return [Path.home() / ".vulpcode" / "profiles"]


class ProfileCommand(SlashCommand):
    name = "profile"
    help_text = "Show active profile, list profiles, or switch (next session)"

    async def run(self, repl: "Repl", args: str) -> None:
        """Handle /profile, /profile list, /profile switch NAME."""
        from vulpcode.harness.profiles import Profile, ProfileNotFound, list_profiles

        parts = args.strip().split() if args.strip() else []
        search_dirs = _default_search_dirs()
        config_sections = repl.config.get("profiles", {}) or {}

        if not parts:
            await self._show_active(repl, search_dirs, config_sections)
        elif parts[0] == "list":
            profiles = list_profiles(search_dirs, config_sections=config_sections)
            rows = [[p.name, p.description] for p in profiles]
            repl.renderer.render_table("Profiles", ["name", "description"], rows)
        elif parts[0] == "switch":
            if len(parts) < 2:
                repl.renderer.console.print("[red]Usage: /profile switch NAME[/]")
                return
            name = parts[1]
            try:
                Profile.load(name, search_dirs=search_dirs, config_sections=config_sections)
            except ProfileNotFound as exc:
                repl.renderer.console.print(f"[red]{exc}[/]")
                return
            repl.renderer.console.print(
                f"[yellow]Profile {name!r} validated.[/] "
                "Restart vulp with [bold]--profile "
                f"{name}[/] to apply it.\n"
                "[dim]Provider and model cannot be switched mid-session.[/]"
            )
        else:
            repl.renderer.console.print(
                f"[red]Unknown subcommand: {parts[0]!r}[/]\n"
                "[dim]Usage: /profile [list | switch NAME][/]"
            )

    async def _show_active(
        self,
        repl: "Repl",
        search_dirs: list[Path],
        config_sections: dict,
    ) -> None:
        from vulpcode.harness.profiles import Profile, ProfileNotFound

        active_name = repl.config.get("_active_profile_name")
        if not active_name:
            repl.renderer.console.print("[dim]No profile active (using global config)[/]")
            return

        try:
            profile = Profile.load(
                active_name, search_dirs=search_dirs, config_sections=config_sections
            )
        except ProfileNotFound:
            repl.renderer.console.print(
                f"[red]Active profile {active_name!r} no longer found[/]"
            )
            return

        repl.renderer.console.print(f"[bold]Active profile:[/] {active_name}")
        repl.renderer.console.print(f"[dim]{profile.description}[/]")
        for field in ("provider", "model", "tools_allow", "tools_deny", "skills_priority"):
            val = profile.data.get(field)
            if val:
                repl.renderer.console.print(f"  {field}: {val}")
        if profile.data.get("system_prompt_extra"):
            repl.renderer.console.print("  system_prompt_extra: [dim](set)[/]")
