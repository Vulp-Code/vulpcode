"""Glob tool: pattern-match files with recursive ** support."""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from vulpcode.tools._ignore import build_matcher
from vulpcode.tools.base import Tool, ToolResult, tool


_MAX_RESULTS = 100


@tool(
    name="Glob",
    description=(
        "Find files by glob pattern. Supports * ? [abc] and ** for recursive match. "
        "Returns absolute paths sorted by modification time (newest first). "
        "By default skips noise dirs (node_modules, __pycache__, .venv, .git, dist, "
        "build, target, ...) and honors the project .gitignore — pass "
        "include_ignored=true to disable filtering."
    ),
    requires_confirm=False,
)
class GlobTool(Tool):
    """Find files matching a glob pattern.

    Supports ``*``, ``?``, ``[abc]`` and ``**`` for recursive matching. When
    ``pattern`` is absolute, the leading directory is used as the base.
    Results are absolute paths sorted by modification time (newest first),
    capped at 100 entries.

    By default ignores noise directories (see
    :data:`vulpcode.tools._ignore.DEFAULT_IGNORE_PATTERNS`) and honors the
    project ``.gitignore``. Set ``include_ignored=True`` to disable both.
    """

    class Input(BaseModel):
        pattern: str
        path: str | None = None
        include_ignored: bool = False

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

        matcher = (
            None
            if args.include_ignored
            else build_matcher(base)
        )

        files: list[tuple[float, Path]] = []
        ignored_count = 0
        for p in matches:
            try:
                if not p.is_file():
                    continue
                if matcher is not None and matcher(p):
                    ignored_count += 1
                    continue
                files.append((p.stat().st_mtime, p))
            except OSError:
                continue

        files.sort(reverse=True)
        truncated = len(files) > _MAX_RESULTS
        files = files[:_MAX_RESULTS]

        if not files:
            msg = f"No files match {args.pattern!r} under {base}"
            if ignored_count:
                msg += (
                    f" ({ignored_count} matched but were skipped by ignore rules; "
                    "pass include_ignored=true to see them)"
                )
            return ToolResult(
                output=msg,
                metadata={
                    "base": str(base),
                    "pattern": args.pattern,
                    "matches": 0,
                    "ignored": ignored_count,
                },
            )

        body = "\n".join(str(p) for _, p in files)
        if truncated:
            body += f"\n[truncated to {_MAX_RESULTS} most recent matches]"
        if ignored_count:
            body += (
                f"\n[{ignored_count} additional match(es) hidden by ignore rules; "
                "include_ignored=true to disable]"
            )

        return ToolResult(
            output=body,
            metadata={
                "base": str(base),
                "pattern": args.pattern,
                "matches": len(files),
                "truncated": truncated,
                "ignored": ignored_count,
            },
        )
