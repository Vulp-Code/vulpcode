"""Read tool: reads a file from disk with optional offset/limit."""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from vulpcode.tools.base import Tool, ToolResult, tool


_DEFAULT_LIMIT = 2000
_MAX_LINE_LEN = 2000
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
_BINARY_SAMPLE = 4096


@tool(
    name="Read",
    description=(
        "Read a file from the local filesystem. Supports text files (returned with "
        "line numbers in cat -n format) and identifies image files. Use offset (1-based) "
        "and limit (max lines) for large files."
    ),
    requires_confirm=False,
)
class ReadTool(Tool):
    """Read a file from disk.

    Returns text files as ``cat -n``-style numbered output, identifies image
    files by extension, and rejects binaries. Use ``offset`` (1-based) and
    ``limit`` to page through large files.
    """

    class Input(BaseModel):
        file_path: str
        offset: int | None = None
        limit: int | None = None

    async def run(self, args: BaseModel) -> ToolResult:  # type: ignore[override]
        assert isinstance(args, ReadTool.Input)
        path = Path(args.file_path).expanduser()

        if not path.exists():
            return ToolResult(
                error=f"File does not exist: {args.file_path}",
                is_error=True,
            )
        if path.is_dir():
            return ToolResult(
                error=f"Path is a directory, not a file: {args.file_path}",
                is_error=True,
            )

        if path.suffix.lower() in _IMAGE_SUFFIXES:
            size = path.stat().st_size
            return ToolResult(
                output=f"<image file: {path.name}, {size} bytes>",
                metadata={"image_path": str(path), "is_image": True, "size": size},
            )

        try:
            with path.open("rb") as fh:
                sample = fh.read(_BINARY_SAMPLE)
            if b"\x00" in sample:
                return ToolResult(
                    error=f"File appears to be binary: {args.file_path}",
                    is_error=True,
                )
        except OSError as exc:
            return ToolResult(error=f"Cannot read file: {exc}", is_error=True)

        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return ToolResult(error=f"Cannot read file: {exc}", is_error=True)

        if not text:
            return ToolResult(output="<file is empty>")

        lines = text.splitlines()
        offset = max(args.offset or 1, 1)
        limit = args.limit or _DEFAULT_LIMIT
        end = min(len(lines), offset - 1 + limit)
        slice_ = lines[offset - 1 : end]

        formatted = []
        for i, line in enumerate(slice_, start=offset):
            if len(line) > _MAX_LINE_LEN:
                line = line[:_MAX_LINE_LEN] + "...[truncated]"
            formatted.append(f"{i}\t{line}")

        body = "\n".join(formatted)
        meta = {
            "file_path": str(path),
            "lines_total": len(lines),
            "lines_returned": len(slice_),
            "offset": offset,
        }
        if end < len(lines):
            body += (
                f"\n[truncated: {len(lines) - end} more lines, "
                f"use offset={end + 1} to continue]"
            )
        return ToolResult(output=body, metadata=meta)
