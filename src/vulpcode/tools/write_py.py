"""WritePy tool: create or overwrite a .py file, validating syntax via ast.parse."""
from __future__ import annotations

import ast

from pydantic import BaseModel

from vulpcode.tools._validated_write import (
    ValidatedWriteTool,
    ValidationError,
    format_snippet,
)
from vulpcode.tools.base import tool


@tool(
    name="WritePy",
    description=(
        "Create or overwrite a Python (.py) file. Validates the content with "
        "ast.parse() before saving. If there is a SyntaxError, the file is NOT "
        "written and the error is returned with line, column and a 5-line snippet "
        "around the failure point — use this to fix and resubmit. UTF-8."
    ),
    requires_confirm=True,
)
class WritePyTool(ValidatedWriteTool):
    class Input(BaseModel):
        file_path: str
        content: str

    def validate(self, content, args):
        try:
            ast.parse(content, filename=args.file_path)
        except SyntaxError as exc:
            line = exc.lineno or 1
            col = exc.offset or None
            raise ValidationError(
                f"SyntaxError: {exc.msg}",
                line=line,
                col=col,
                snippet=format_snippet(content, line, col),
            )
