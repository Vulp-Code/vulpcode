"""Rich-based renderer for Agent events."""
from __future__ import annotations

import json

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from vulpcode.providers.base import ToolCall, Usage
from vulpcode.tools.base import ToolResult
from vulpcode.ui.theme import Theme


class Renderer:
    def __init__(self, console: Console, theme: Theme) -> None:
        self.console = console
        self.theme = theme
        self._streaming_active = False

    def render_text_chunk(self, delta: str) -> None:
        self.console.print(delta, end="", soft_wrap=True, highlight=False)
        self._streaming_active = True

    def render_assistant_markdown(self, text: str) -> None:
        if self._streaming_active:
            self.console.print()
            self._streaming_active = False
        self.console.print(Markdown(text))

    def render_tool_start(self, tool_call: ToolCall) -> None:
        if self._streaming_active:
            self.console.print()
            self._streaming_active = False
        args_pretty = json.dumps(tool_call.arguments, indent=2, ensure_ascii=False)
        body = Syntax(args_pretty, "json", theme=self.theme.code_theme, word_wrap=True)
        self.console.print(
            Panel(
                body,
                title=f"[{self.theme.accent}]{tool_call.name}[/]",
                subtitle=f"[{self.theme.muted}]running...[/]",
                border_style=self.theme.primary,
            )
        )

    def render_tool_end(self, tool_call: ToolCall, result: ToolResult) -> None:
        if self._streaming_active:
            self.console.print()
            self._streaming_active = False
        if result.is_error:
            content = result.error or result.output or "<error>"
            color = self.theme.danger
            label = "error"
        else:
            content = result.output or "<no output>"
            color = self.theme.success
            label = "ok"
        if len(content) > 1500:
            content = content[:1500] + "\n[...truncated...]"
        self.console.print(
            Panel(
                content,
                title=f"[{color}]{tool_call.name} -> {label}[/]",
                border_style=color,
            )
        )

    def render_tool_denied(self, tool_call: ToolCall, reason: str) -> None:
        if self._streaming_active:
            self.console.print()
            self._streaming_active = False
        self.console.print(
            f"[{self.theme.warning}]Tool {tool_call.name!r} denied: {reason}[/]"
        )

    def render_usage(self, usage: Usage) -> None:
        if usage.input_tokens or usage.output_tokens:
            self.console.print(
                f"[{self.theme.muted}]tokens: in={usage.input_tokens} "
                f"out={usage.output_tokens}[/]"
            )

    def render_error(self, msg: str) -> None:
        if self._streaming_active:
            self.console.print()
            self._streaming_active = False
        self.console.print(f"[{self.theme.danger}]error: {msg}[/]")

    def render_turn_end(self, stop_reason: str | None = None) -> None:
        if self._streaming_active:
            self.console.print()
            self._streaming_active = False
        if stop_reason and stop_reason != "end_turn":
            label = stop_reason.replace("_", " ")
            self.console.print(f"[{self.theme.muted}](stopped: {label})[/]")

    def render_table(
        self, title: str, columns: list[str], rows: list[list[str]]
    ) -> None:
        t = Table(title=title)
        for c in columns:
            t.add_column(c, style=self.theme.primary)
        for r in rows:
            t.add_row(*r)
        self.console.print(t)
