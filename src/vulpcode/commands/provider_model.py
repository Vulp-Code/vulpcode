"""/provider and /model commands."""
from __future__ import annotations

from vulpcode.commands._base import SlashCommand
from vulpcode.providers import build_provider, list_provider_names


class ProviderCommand(SlashCommand):
    name = "provider"
    help_text = "List providers, or switch with /provider <name>"

    async def run(self, repl, args: str) -> None:
        if not args:
            current = type(repl.agent.provider).__name__
            current_name = getattr(repl.agent.provider, "name", "")
            rows = []
            for n in list_provider_names():
                marker = "*" if n == current_name else ""
                rows.append([n, marker])
            repl.renderer.render_table("Providers", ["name", "active"], rows)
            repl.renderer.console.print(f"[muted]current: {current}[/]")
            return

        name = args.strip()
        if name not in list_provider_names():
            repl.renderer.render_error(f"Unknown provider: {name}")
            return
        cfg = repl.config.get("providers", {}).get(name, {})
        try:
            new_provider = build_provider(name, cfg)
        except Exception as exc:
            repl.renderer.render_error(f"Failed to build provider {name}: {exc}")
            return

        old = repl.agent.provider
        try:
            await old.aclose()
        except Exception:
            pass
        repl.agent.provider = new_provider
        repl.renderer.console.print(f"[green]provider switched to {name}[/]")


class ModelCommand(SlashCommand):
    name = "model"
    help_text = "List models, or switch with /model <name>"

    async def run(self, repl, args: str) -> None:
        if not args:
            try:
                models = await repl.agent.provider.list_models()
            except Exception as exc:
                repl.renderer.render_error(f"list_models failed: {exc}")
                return
            current = repl.agent.model
            if not models:
                repl.renderer.console.print(
                    f"[muted]no models reported by provider; current: {current}[/]"
                )
                return
            rows = [[m, "*" if m == current else ""] for m in models]
            repl.renderer.render_table("Models", ["name", "active"], rows)
            return
        repl.agent.model = args.strip()
        repl.renderer.console.print(f"[green]model set to {repl.agent.model}[/]")
