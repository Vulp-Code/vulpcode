"""Base class for file-creation tools with built-in validation and atomic save.

A subclass overrides ``validate(content) -> None`` (raise on error) and gets:
- atomic save via tmp + rename
- detailed error messages routed back through ToolResult so the agent loop can drive a repair iteration
"""
from __future__ import annotations

import os
import tempfile
from abc import abstractmethod
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from vulpcode.tools.base import Tool, ToolResult


class ValidationError(Exception):
    """Raised by ValidatedWriteTool.validate() when content is not valid.

    Carry structured info so the formatter can produce a great error message:
    line, column, snippet, and a short reason.
    """

    def __init__(
        self,
        message: str,
        *,
        line: int | None = None,
        col: int | None = None,
        snippet: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.line = line
        self.col = col
        self.snippet = snippet

    def to_error_text(self) -> str:
        parts = [self.message]
        if self.line is not None:
            loc = f"at line {self.line}"
            if self.col is not None:
                loc += f", col {self.col}"
            parts.append(loc)
        body = " ".join(parts)
        if self.snippet:
            return f"{body}\n\n{self.snippet}"
        return body


def format_snippet(content: str, line: int, col: int | None = None, context: int = 2) -> str:
    """Render 'context' lines around `line` (1-based), with a caret pointing at `col`."""
    lines = content.splitlines()
    if not lines:
        return ""
    line = max(1, min(line, len(lines)))
    start = max(1, line - context)
    end = min(len(lines), line + context)
    width = len(str(end))
    out: list[str] = []
    for i in range(start, end + 1):
        marker = ">" if i == line else " "
        out.append(f"{marker} {i:>{width}} | {lines[i-1]}")
        if i == line and col is not None and col > 0:
            pad = " " * (width + 4 + col - 1)
            out.append(f"  {pad}^")
    return "\n".join(out)


class ValidatedWriteTool(Tool):
    """Template for file-creation tools.

    Subclasses MUST:
    - Declare ``class Input(BaseModel): file_path: str; content: str``
      (or add fields, but keep these two).
    - Implement ``validate(self, content: str, args: BaseModel) -> None``,
      raising :class:`ValidationError` on syntax/structural problems.
    - Optionally override ``transform(self, args) -> str`` to map args into
      the final on-disk bytes (e.g. WriteIpynb assembles cells -> JSON).
    - Optionally override ``binary`` to ``True`` and return ``bytes`` from
      ``transform`` (e.g. WritePdf, WriteDocx).

    The ``run`` method is final — do not override.
    """

    binary: bool = False

    @abstractmethod
    def validate(self, content: Any, args: BaseModel) -> None:
        """Raise ValidationError if `content` is not a valid file of this type."""

    def transform(self, args: BaseModel) -> Any:
        """Return the bytes/str to actually write. Default: args.content as-is."""
        return getattr(args, "content")

    async def run(self, args: BaseModel) -> ToolResult:  # type: ignore[override]
        # 1. Transform
        try:
            payload = self.transform(args)
        except ValidationError as ve:
            return ToolResult(error=ve.to_error_text(), is_error=True)
        except Exception as exc:
            return ToolResult(
                error=f"{type(exc).__name__} while transforming: {exc}",
                is_error=True,
            )

        # 2. Validate (pre-save)
        try:
            self.validate(payload, args)
        except ValidationError as ve:
            return ToolResult(
                error=ve.to_error_text(),
                is_error=True,
                metadata={"phase": "validate"},
            )
        except Exception as exc:
            return ToolResult(
                error=f"{type(exc).__name__} during validation: {exc}",
                is_error=True,
            )

        # 3. Atomic save
        path = Path(getattr(args, "file_path")).expanduser().resolve()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            mode = "wb" if self.binary else "w"
            data = payload if self.binary else (
                payload if isinstance(payload, str) else str(payload)
            )
            with tempfile.NamedTemporaryFile(
                mode=mode,
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
                encoding=None if self.binary else "utf-8",
            ) as tf:
                tf.write(data)
                tmp_path = Path(tf.name)
            os.replace(tmp_path, path)
        except OSError as exc:
            return ToolResult(
                error=f"Failed to write {path}: {exc}",
                is_error=True,
            )

        size = path.stat().st_size
        return ToolResult(
            output=f"Wrote {size} bytes to {path}",
            metadata={
                "file_path": str(path),
                "size": size,
                "validated": True,
                "tool": self._tool_name,
            },
        )
