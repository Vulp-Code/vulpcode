"""/cost - print accumulated token usage of the session."""
from __future__ import annotations

from vulpcode.commands._base import SlashCommand


class CostCommand(SlashCommand):
    name = "cost"
    help_text = "Show accumulated token usage for this session"

    async def run(self, repl, args: str) -> None:
        usage = getattr(repl.agent, "_session_usage", None)
        if usage is None:
            repl.renderer.console.print(
                "[muted]no usage data tracked (will populate after first turn)[/]"
            )
            return
        repl.renderer.render_table(
            "Session usage",
            ["metric", "tokens"],
            [
                ["input", str(usage.input_tokens)],
                ["output", str(usage.output_tokens)],
                ["cache_read", str(usage.cache_read_tokens)],
                ["cache_create", str(usage.cache_creation_tokens)],
            ],
        )
