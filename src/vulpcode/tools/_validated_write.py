"""Base class for file-creation tools with built-in validation and atomic save."""
from __future__ import annotations
import os
import tempfile
from abc import abstractmethod
from pathlib import Path
from typing import Any
from pydantic import BaseModel
from vulpcode.tools._safety import format_secret_error, scan_secrets
from vulpcode.tools.base import Tool, ToolResult


class ValidationError(Exception):
    def __init__(self, message, *, line=None, col=None, snippet=None):
        super().__init__(message)
        self.message = message
        self.line = line
        self.col = col
        self.snippet = snippet

    def to_error_text(self):
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


def format_snippet(content, line, col=None, context=2):
    lines = content.splitlines()
    if not lines:
        return ""
    line = max(1, min(line, len(lines)))
    start = max(1, line - context)
    end = min(len(lines), line + context)
    width = len(str(end))
    out = []
    for i in range(start, end + 1):
        marker = ">" if i == line else " "
        out.append(f"{marker} {i:>{width}} | {lines[i-1]}")
        if i == line and col is not None and col > 0:
            pad = " " * (width + 4 + col - 1)
            out.append(f"  {pad}^")
    return "\n".join(out)


class ValidatedWriteTool(Tool):
    binary: bool = False

    @abstractmethod
    def validate(self, content: Any, args: BaseModel) -> None:
        """Raise ValidationError if content is not a valid file of this type."""

    def transform(self, args: BaseModel) -> Any:
        return getattr(args, "content")

    async def run(self, args: BaseModel) -> ToolResult:  # type: ignore[override]
        try:
            payload = self.transform(args)
        except ValidationError as ve:
            return ToolResult(error=ve.to_error_text(), is_error=True)
        except Exception as exc:
            return ToolResult(error=f"{type(exc).__name__} while transforming: {exc}", is_error=True)
        try:
            self.validate(payload, args)
        except ValidationError as ve:
            return ToolResult(error=ve.to_error_text(), is_error=True, metadata={"phase": "validate"})
        except Exception as exc:
            return ToolResult(error=f"{type(exc).__name__} during validation: {exc}", is_error=True)
        if not self.binary and isinstance(payload, str):
            hits = scan_secrets(payload)
            if hits:
                return ToolResult(error=format_secret_error(hits), is_error=True)
        path = Path(getattr(args, "file_path")).expanduser().resolve()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            mode = "wb" if self.binary else "w"
            data = payload if self.binary else (payload if isinstance(payload, str) else str(payload))
            with tempfile.NamedTemporaryFile(mode=mode, dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False, encoding=None if self.binary else "utf-8") as tf:
                tf.write(data)
                tmp_path = Path(tf.name)
            os.replace(tmp_path, path)
        except OSError as exc:
            return ToolResult(error=f"Failed to write {path}: {exc}", is_error=True)
        size = path.stat().st_size
        return ToolResult(output=f"Wrote {size} bytes to {path}", metadata={"file_path": str(path), "size": size, "validated": True, "tool": self._tool_name})
