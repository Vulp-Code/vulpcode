"""/mcp slash command."""
from __future__ import annotations

from typing import TYPE_CHECKING

from vulpcode.commands._base import SlashCommand

if TYPE_CHECKING:
    from vulpcode.ui.repl import Repl


class McpCommand(SlashCommand):
    name = "mcp"
    help_text = "List MCP servers and the tools they provide"

    async def run(self, repl: "Repl", args: str) -> None:
        config = getattr(repl, "config", {}) or {}
        servers = config.get("mcp", {}).get("servers", []) or []
        if not servers:
            repl.renderer.console.print("[muted]no MCP servers configured[/]")
            return
        rows: list[list[str]] = []
        for s in servers:
            rows.append(
                [
                    s.get("name", "?"),
                    s.get("command", ""),
                    " ".join(s.get("args", []) or []),
                ]
            )
        repl.renderer.render_table(
            "MCP servers", ["name", "command", "args"], rows
        )
        try:
            from vulpcode.mcp import list_active_servers
            active = list_active_servers()
        except ImportError:
            active = []
        if active:
            tool_rows = [[s.name, ", ".join(s.tools)] for s in active]
            repl.renderer.render_table(
                "MCP tools", ["server", "tools"], tool_rows
            )
