"""Write tool: creates or overwrites a file with given content."""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from vulpcode.tools.base import Tool, ToolResult, tool


@tool(
    name="Write",
    description=(
        "Create or overwrite a file with the given content. Parent directories are "
        "created automatically. Always writes UTF-8."
    ),
    requires_confirm=True,
)
class WriteTool(Tool):
    """Create or overwrite a file with the given content.

    Parent directories are created automatically and content is always
    written as UTF-8. Marked ``requires_confirm=True`` because it is
    destructive on existing files.
    """

    class Input(BaseModel):
        file_path: str
        content: str

    async def run(self, args: BaseModel) -> ToolResult:  # type: ignore[override]
        assert isinstance(args, WriteTool.Input)
        path = Path(args.file_path).expanduser().resolve()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(args.content, encoding="utf-8")
        except OSError as exc:
            return ToolResult(error=f"Failed to write {path}: {exc}", is_error=True)
        size = path.stat().st_size
        return ToolResult(
            output=f"Wrote {size} bytes to {path}",
            metadata={"file_path": str(path), "size": size, "created": True},
        )
