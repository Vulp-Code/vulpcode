"""WriteJson tool: write a .json file, validated via json.loads."""
from __future__ import annotations

import json

from pydantic import BaseModel

from vulpcode.tools._validated_write import (
    ValidatedWriteTool,
    ValidationError,
    format_snippet,
)
from vulpcode.tools.base import tool


@tool(
    name="WriteJson",
    description=(
        "Create or overwrite a JSON file. Validates with json.loads BEFORE saving. "
        "On JSONDecodeError the file is NOT written and the line/column of the "
        "failure are returned for you to fix and resubmit."
    ),
    requires_confirm=True,
)
class WriteJsonTool(ValidatedWriteTool):
    class Input(BaseModel):
        file_path: str
        content: str
        indent: int | None = 2

    def transform(self, args):
        if args.indent is None:
            return args.content
        try:
            obj = json.loads(args.content)
        except json.JSONDecodeError:
            return args.content
        return json.dumps(obj, indent=args.indent, ensure_ascii=False) + "\n"

    def validate(self, content, args):
        try:
            json.loads(content)
        except json.JSONDecodeError as e:
            raise ValidationError(
                f"JSONDecodeError: {e.msg}",
                line=e.lineno,
                col=e.colno,
                snippet=format_snippet(content, e.lineno, e.colno),
            )
