"""WriteToml tool: write a .toml file, validated via tomllib."""
from __future__ import annotations

import re
import tomllib

from pydantic import BaseModel

from vulpcode.tools._validated_write import (
    ValidatedWriteTool,
    ValidationError,
    format_snippet,
)
from vulpcode.tools.base import tool

_TOML_LINE_COL = re.compile(r"line\s+(\d+)\s+col(?:umn)?\s+(\d+)", re.IGNORECASE)
_TOML_LINE_ONLY = re.compile(r"line\s+(\d+)", re.IGNORECASE)


def _extract_toml_position(msg: str) -> tuple[int | None, int | None]:
    m = _TOML_LINE_COL.search(msg)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = _TOML_LINE_ONLY.search(msg)
    if m:
        return int(m.group(1)), None
    return None, None


@tool(
    name="WriteToml",
    description=(
        "Create or overwrite a TOML file. Validates with tomllib BEFORE saving. "
        "On TOMLDecodeError the file is NOT written and the error is returned for "
        "you to fix and resubmit."
    ),
    requires_confirm=True,
)
class WriteTomlTool(ValidatedWriteTool):
    class Input(BaseModel):
        file_path: str
        content: str

    def validate(self, content, args):
        try:
            tomllib.loads(content)
        except tomllib.TOMLDecodeError as e:
            msg = str(e)
            line, col = _extract_toml_position(msg)
            raise ValidationError(
                f"TOMLDecodeError: {msg}",
                line=line,
                col=col,
                snippet=format_snippet(content, line, col) if line is not None else None,
            )
