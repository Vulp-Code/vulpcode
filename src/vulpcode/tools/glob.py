"""Glob tool: pattern-match files with recursive ** support."""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from vulpcode.tools.base import Tool, ToolResult, tool


_MAX_RESULTS = 100


@tool(
    name="Glob",
    description=(
        "Find files by glob pattern. Supports * ? [abc] and ** for recursive match. "
        "Returns absolute paths sorted by modification time (newest first)."
    ),
    requires_confirm=False,
)
class GlobTool(Tool):
    """Find files matching a glob pattern.

    Supports ``*``, ``?``, ``[abc]`` and ``**`` for recursive matching. When
    ``pattern`` is absolute, the leading directory is used as the base.
    Results are absolute paths sorted by modification time (newest first),
    capped at 100 entries.
    """

    class Input(BaseModel):
        pattern: str
        path: str | None = None

    async def run(self, args: BaseModel) -> ToolResult:  # type: ignore[override]
        assert isinstance(args, GlobTool.Input)
        pattern = args.pattern
        explicit_base = args.path

        # Path.glob() only accepts relative patterns. If the model passes an
        # absolute pattern (e.g. "/home/x/**/*.py"), split it into (base, rel).
        if Path(pattern).is_absolute():
            if "**" in pattern:
                anchor_base, _, tail = pattern.partition("**")
                anchor = anchor_base.rstrip("/")
                pattern_rel = "**" + tail
            else:
                anchor = str(Path(pattern).parent)
                pattern_rel = Path(pattern).name
            if explicit_base is None:
                explicit_base = anchor or "/"
            pattern = pattern_rel or "*"

        base = Path(explicit_base).expanduser().resolve() if explicit_base else Path.cwd()
        if not base.exists():
            return ToolResult(error=f"Base path does not exist: {base}", is_error=True)
        if not base.is_dir():
            return ToolResult(error=f"Base path is not a directory: {base}", is_error=True)

        try:
            matches = list(base.glob(pattern))
        except (OSError, ValueError, NotImplementedError) as exc:
            return ToolResult(error=f"Glob failed: {exc}", is_error=True)

        files: list[tuple[float, Path]] = []
        for p in matches:
            try:
                if p.is_file():
                    files.append((p.stat().st_mtime, p))
            except OSError:
                continue

        files.sort(reverse=True)
        truncated = len(files) > _MAX_RESULTS
        files = files[:_MAX_RESULTS]

        if not files:
            return ToolResult(
                output=f"No files match {args.pattern!r} under {base}",
                metadata={"base": str(base), "pattern": args.pattern, "matches": 0},
            )

        body = "\n".join(str(p) for _, p in files)
        if truncated:
            body += f"\n[truncated to {_MAX_RESULTS} most recent matches]"

        return ToolResult(
            output=body,
            metadata={
                "base": str(base),
                "pattern": args.pattern,
                "matches": len(files),
                "truncated": truncated,
            },
        )
