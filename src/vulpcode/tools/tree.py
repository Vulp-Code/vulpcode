"""Tree tool: compact recursive directory listing for project overview."""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from vulpcode.tools._ignore import build_matcher
from vulpcode.tools.base import Tool, ToolResult, tool


_DEFAULT_MAX_DEPTH = 3
_DEFAULT_MAX_ENTRIES = 500


@tool(
    name="Tree",
    description=(
        "Render a compact recursive directory tree for project overview. "
        "Honors .gitignore and skips noise dirs (node_modules, __pycache__, "
        ".venv, .git, dist, build, target, ...) by default. Use this BEFORE "
        "Read/Grep to understand a project's layout — it's far cheaper than "
        "listing files one by one."
    ),
    requires_confirm=False,
)
class TreeTool(Tool):
    """Recursive directory listing with depth and entry caps.

    Designed for the "analyze my project" flow: gives the model a structural
    overview in a few hundred lines while filtering out the heavy noise dirs.
    """

    class Input(BaseModel):
        path: str | None = None
        max_depth: int = Field(default=_DEFAULT_MAX_DEPTH, ge=1, le=10)
        max_entries: int = Field(default=_DEFAULT_MAX_ENTRIES, ge=10, le=5000)
        include_ignored: bool = False
        show_sizes: bool = False

    async def run(self, args: BaseModel) -> ToolResult:  # type: ignore[override]
        assert isinstance(args, TreeTool.Input)
        base = Path(args.path or ".").expanduser().resolve()
        if not base.exists():
            return ToolResult(error=f"Path does not exist: {base}", is_error=True)
        if not base.is_dir():
            return ToolResult(error=f"Path is not a directory: {base}", is_error=True)

        matcher = None if args.include_ignored else build_matcher(base)

        lines: list[str] = [str(base)]
        counters = {"entries": 0, "dirs": 0, "files": 0, "ignored": 0, "truncated": False}

        def _walk(directory: Path, depth: int, prefix: str) -> None:
            if counters["truncated"]:
                return
            if depth > args.max_depth:
                return
            try:
                children = sorted(
                    directory.iterdir(),
                    key=lambda p: (not p.is_dir(), p.name.lower()),
                )
            except OSError as exc:
                lines.append(f"{prefix}└── [error: {exc}]")
                return

            visible: list[Path] = []
            for child in children:
                if matcher is not None and matcher(child):
                    counters["ignored"] += 1
                    continue
                visible.append(child)

            for idx, child in enumerate(visible):
                if counters["entries"] >= args.max_entries:
                    counters["truncated"] = True
                    lines.append(
                        f"{prefix}└── [truncated at {args.max_entries} entries]"
                    )
                    return
                is_last = idx == len(visible) - 1
                connector = "└── " if is_last else "├── "
                suffix = "/" if child.is_dir() else ""
                size = ""
                if args.show_sizes and child.is_file():
                    try:
                        size = f"  ({child.stat().st_size}B)"
                    except OSError:
                        size = ""
                lines.append(f"{prefix}{connector}{child.name}{suffix}{size}")
                counters["entries"] += 1
                if child.is_dir():
                    counters["dirs"] += 1
                    if depth < args.max_depth:
                        next_prefix = prefix + ("    " if is_last else "│   ")
                        _walk(child, depth + 1, next_prefix)
                    else:
                        # Hint that there's more below the depth cap.
                        try:
                            inner = any(True for _ in child.iterdir())
                        except OSError:
                            inner = False
                        if inner:
                            deeper = prefix + ("    " if is_last else "│   ")
                            lines.append(f"{deeper}└── …")
                else:
                    counters["files"] += 1

        _walk(base, depth=1, prefix="")

        summary_parts = [
            f"{counters['dirs']} dir(s)",
            f"{counters['files']} file(s)",
        ]
        if counters["ignored"]:
            summary_parts.append(f"{counters['ignored']} ignored")
        if counters["truncated"]:
            summary_parts.append("output truncated")
        lines.append("")
        lines.append("[" + ", ".join(summary_parts) + "]")

        return ToolResult(
            output="\n".join(lines),
            metadata={
                "base": str(base),
                "max_depth": args.max_depth,
                **counters,
            },
        )
