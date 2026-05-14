"""/tools - list active tools."""
from __future__ import annotations

from vulpcode.commands._base import SlashCommand
from vulpcode.tools import list_tools


class ToolsCommand(SlashCommand):
    name = "tools"
    help_text = "List currently registered tools"

    async def run(self, repl, args: str) -> None:
        rows = []
        for cls in list_tools():
            confirm = "yes" if cls._requires_confirm else "no"
            rows.append([cls._tool_name, confirm, cls._tool_description[:60]])
        repl.renderer.render_table(
            "Active tools", ["name", "confirm?", "description"], rows,
        )
