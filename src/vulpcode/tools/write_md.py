"""WriteMd tool: create or overwrite a Markdown (.md) file with sanity checks."""
from __future__ import annotations

from pydantic import BaseModel

from vulpcode.tools._validated_write import (
    ValidatedWriteTool,
    ValidationError,
)
from vulpcode.tools.base import tool


@tool(
    name="WriteMd",
    description=(
        "Create or overwrite a Markdown (.md) file. Validates with markdown-it-py: "
        "checks the parser tokenizes the document without exceptions and flags "
        "obvious problems like unclosed code fences."
    ),
    requires_confirm=True,
)
class WriteMdTool(ValidatedWriteTool):
    class Input(BaseModel):
        file_path: str
        content: str

    def validate(self, content, args):
        fence_count = sum(1 for line in content.splitlines() if line.startswith("```"))
        if fence_count % 2 != 0:
            raise ValidationError(
                f"Unbalanced code fences: found {fence_count} '```' lines (must be even)."
            )
        try:
            from markdown_it import MarkdownIt
        except ImportError:
            return
        try:
            MarkdownIt().parse(content)
        except Exception as e:
            raise ValidationError(f"markdown-it failed to parse: {e}")
