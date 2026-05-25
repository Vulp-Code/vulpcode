"""Write tool: creates or overwrites a file with given content."""
from __future__ import annotations
from pathlib import Path
from pydantic import BaseModel
from vulpcode.tools._safety import check_path_sandbox, format_secret_error, scan_secrets
from vulpcode.tools.base import Tool, ToolResult, tool

@tool(name="Write", description="Create or overwrite a file with the given content. Parent directories are created automatically. Always writes UTF-8.", requires_confirm=True)
class WriteTool(Tool):
    class Input(BaseModel):
        file_path: str
        content: str

    async def run(self, args: BaseModel) -> ToolResult:  # type: ignore[override]
        assert isinstance(args, WriteTool.Input)
        sandbox_err = check_path_sandbox(args.file_path)
        if sandbox_err:
            return ToolResult(error=sandbox_err, is_error=True)
        hits = scan_secrets(args.content)
        if hits:
            return ToolResult(error=format_secret_error(hits), is_error=True)
        path = Path(args.file_path).expanduser().resolve()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(args.content, encoding="utf-8")
        except OSError as exc:
            return ToolResult(error=f"Failed to write {path}: {exc}", is_error=True)
        size = path.stat().st_size
        return ToolResult(output=f"Wrote {size} bytes to {path}", metadata={"file_path": str(path), "size": size, "created": True})
