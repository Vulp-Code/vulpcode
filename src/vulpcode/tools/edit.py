"""Edit and MultiEdit tools: exact-string substitution in files."""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from vulpcode.tools.base import Tool, ToolResult, tool


def _apply_edit(
    text: str, old: str, new: str, replace_all: bool
) -> tuple[str, int, str | None]:
    """Apply a single edit to text. Returns (new_text, count, error_message)."""
    if old == new:
        return text, 0, "old_string and new_string are identical"
    if old == "":
        return text, 0, "old_string cannot be empty"
    if replace_all:
        count = text.count(old)
        if count == 0:
            return text, 0, "old_string not found"
        return text.replace(old, new), count, None
    occurrences = text.count(old)
    if occurrences == 0:
        return text, 0, "old_string not found"
    if occurrences > 1:
        return text, 0, (
            f"old_string is not unique ({occurrences} occurrences). "
            "Add more context or set replace_all=True."
        )
    return text.replace(old, new, 1), 1, None


def _snippet_around_change(
    new_text: str, search: str, context_lines: int = 3
) -> str:
    """Return a small numbered snippet showing the result around the first match."""
    lines = new_text.splitlines()
    if not lines:
        return "<file is empty after edit>"
    target_line = 1
    needle_first = search.splitlines()[0] if search else ""
    if needle_first:
        for i, line in enumerate(lines, start=1):
            if needle_first in line:
                target_line = i
                break
    start = max(1, target_line - context_lines)
    end = min(len(lines), target_line + context_lines)
    out = []
    for i in range(start, end + 1):
        out.append(f"{i}\t{lines[i - 1]}")
    return "\n".join(out)


@tool(
    name="Edit",
    description=(
        "Replace exact occurrences of old_string with new_string in a file. "
        "old_string must be unique unless replace_all=True."
    ),
    requires_confirm=True,
)
class EditTool(Tool):
    """Replace an exact substring in a file.

    Performs a literal (non-regex) substitution. ``old_string`` must occur
    exactly once unless ``replace_all=True``. Errors when the file is missing,
    is a directory, or ``old_string`` is not found.
    """

    class Input(BaseModel):
        file_path: str
        old_string: str
        new_string: str
        replace_all: bool = False

    async def run(self, args: BaseModel) -> ToolResult:  # type: ignore[override]
        assert isinstance(args, EditTool.Input)
        path = Path(args.file_path).expanduser().resolve()
        if not path.exists():
            return ToolResult(error=f"File does not exist: {path}", is_error=True)
        if path.is_dir():
            return ToolResult(error=f"Path is a directory: {path}", is_error=True)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            return ToolResult(error=f"Cannot read file: {exc}", is_error=True)

        new_text, count, err = _apply_edit(
            text, args.old_string, args.new_string, args.replace_all,
        )
        if err is not None:
            return ToolResult(error=err, is_error=True)
        try:
            path.write_text(new_text, encoding="utf-8")
        except OSError as exc:
            return ToolResult(error=f"Failed to write: {exc}", is_error=True)

        snippet = _snippet_around_change(new_text, args.new_string)
        return ToolResult(
            output=f"Applied {count} edit(s) to {path}\n{snippet}",
            metadata={"file_path": str(path), "edits_applied": count},
        )


@tool(
    name="MultiEdit",
    description=(
        "Atomically apply multiple edits to a single file. If any edit fails, "
        "no changes are written."
    ),
    requires_confirm=True,
)
class MultiEditTool(Tool):
    """Apply multiple edits to a single file atomically.

    Each edit follows the same rules as :class:`EditTool`. If any edit fails
    (substring not found, ambiguous, etc.), nothing is written — the file is
    left untouched.
    """

    class EditOp(BaseModel):
        old_string: str
        new_string: str
        replace_all: bool = False

    class Input(BaseModel):
        file_path: str
        edits: list["MultiEditTool.EditOp"] = Field(default_factory=list)

    async def run(self, args: BaseModel) -> ToolResult:  # type: ignore[override]
        assert isinstance(args, MultiEditTool.Input)
        if not args.edits:
            return ToolResult(error="edits list cannot be empty", is_error=True)
        path = Path(args.file_path).expanduser().resolve()
        if not path.exists():
            return ToolResult(error=f"File does not exist: {path}", is_error=True)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            return ToolResult(error=f"Cannot read file: {exc}", is_error=True)

        total = 0
        for i, op in enumerate(args.edits, start=1):
            text, count, err = _apply_edit(
                text, op.old_string, op.new_string, op.replace_all,
            )
            if err is not None:
                return ToolResult(
                    error=f"Edit #{i} failed: {err}",
                    is_error=True,
                )
            total += count

        try:
            path.write_text(text, encoding="utf-8")
        except OSError as exc:
            return ToolResult(error=f"Failed to write: {exc}", is_error=True)

        return ToolResult(
            output=f"Applied {total} edit(s) across {len(args.edits)} operations to {path}",
            metadata={"file_path": str(path), "edits_applied": total, "ops": len(args.edits)},
        )


# Required for forward-ref in MultiEditTool.Input
MultiEditTool.Input.model_rebuild()
