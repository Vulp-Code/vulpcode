"""Grep tool: regex search across files using ripgrep when available."""
from __future__ import annotations

import asyncio
import re
import shutil
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from vulpcode.tools._ignore import build_matcher
from vulpcode.tools.base import Tool, ToolResult, tool


@tool(
    name="Grep",
    description=(
        "Search files for regex patterns. Uses ripgrep when available, with a "
        "Python fallback. Supports glob filtering, context lines, and three "
        "output modes (content, files_with_matches, count)."
    ),
    requires_confirm=False,
)
class GrepTool(Tool):
    """Regex search across files.

    Uses ``ripgrep`` when available on ``$PATH`` and falls back to a Python
    implementation otherwise. Supports glob filtering, case-insensitive
    matching (``-i``), context flags (``-A``, ``-B``, ``-C``), multiline mode,
    and three output modes: ``content``, ``files_with_matches``, ``count``.
    """

    class Input(BaseModel):
        pattern: str
        path: str | None = None
        glob: str | None = None
        output_mode: Literal["content", "files_with_matches", "count"] = "content"
        flag_i: bool = Field(default=False, alias="-i")
        flag_A: int | None = Field(default=None, alias="-A")
        flag_B: int | None = Field(default=None, alias="-B")
        flag_C: int | None = Field(default=None, alias="-C")
        head_limit: int | None = None
        multiline: bool = False
        include_ignored: bool = False

        model_config = {"populate_by_name": True}

    async def run(self, args: BaseModel) -> ToolResult:  # type: ignore[override]
        assert isinstance(args, GrepTool.Input)
        if shutil.which("rg"):
            return await self._run_rg(args)
        return await self._run_python(args)

    @staticmethod
    async def _run_rg(args: GrepTool.Input) -> ToolResult:
        cmd: list[str] = ["rg", "--color=never"]
        # ripgrep honors .gitignore + common VCS ignores by default. Only pass
        # --no-ignore when the caller explicitly asked to include ignored files.
        if args.include_ignored:
            cmd.append("--no-ignore")
        if args.flag_i:
            cmd.append("-i")
        if args.multiline:
            cmd.extend(["-U", "--multiline-dotall"])
        if args.glob:
            cmd.extend(["-g", args.glob])

        if args.output_mode == "files_with_matches":
            cmd.append("-l")
        elif args.output_mode == "count":
            cmd.append("-c")
        else:
            cmd.append("-n")
            if args.flag_C is not None:
                cmd.extend(["-C", str(args.flag_C)])
            else:
                if args.flag_A is not None:
                    cmd.extend(["-A", str(args.flag_A)])
                if args.flag_B is not None:
                    cmd.extend(["-B", str(args.flag_B)])

        cmd.append(args.pattern)
        cmd.append(args.path or ".")

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_b, stderr_b = await proc.communicate()
        except OSError as exc:
            return ToolResult(error=f"ripgrep failed: {exc}", is_error=True)

        out = stdout_b.decode("utf-8", errors="replace")
        if proc.returncode == 1:
            return ToolResult(output=f"No matches for {args.pattern!r}")
        if proc.returncode not in (0, 1):
            return ToolResult(
                error=stderr_b.decode("utf-8", errors="replace") or f"rg exit {proc.returncode}",
                is_error=True,
            )

        lines = out.splitlines()
        if args.head_limit is not None and len(lines) > args.head_limit:
            lines = lines[: args.head_limit]
            out = "\n".join(lines) + f"\n[truncated to {args.head_limit} lines]"
        return ToolResult(output=out, metadata={"backend": "ripgrep", "matches": len(lines)})

    @staticmethod
    async def _run_python(args: GrepTool.Input) -> ToolResult:
        flags = re.IGNORECASE if args.flag_i else 0
        if args.multiline:
            flags |= re.DOTALL | re.MULTILINE
        try:
            pat = re.compile(args.pattern, flags)
        except re.error as exc:
            return ToolResult(error=f"Invalid regex: {exc}", is_error=True)

        base = Path(args.path or ".").expanduser().resolve()
        if not base.exists():
            return ToolResult(error=f"Path does not exist: {base}", is_error=True)

        if base.is_file():
            files = [base]
        else:
            matcher = None if args.include_ignored else build_matcher(base)
            files = []
            for p in base.rglob(args.glob or "*"):
                if not p.is_file():
                    continue
                if matcher is not None and matcher(p):
                    continue
                files.append(p)

        files_with_matches: list[Path] = []
        counts: dict[Path, int] = {}
        content_lines: list[str] = []

        for fp in files:
            try:
                text = fp.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if args.multiline:
                if pat.search(text):
                    files_with_matches.append(fp)
                    counts[fp] = len(pat.findall(text))
                    if args.output_mode == "content":
                        split = text.splitlines()
                        for m in pat.finditer(text):
                            line_no = text[: m.start()].count("\n") + 1
                            line = split[line_no - 1] if 1 <= line_no <= len(split) else ""
                            content_lines.append(f"{fp}:{line_no}:{line}")
                continue
            file_match = False
            file_count = 0
            for i, line in enumerate(text.splitlines(), start=1):
                if pat.search(line):
                    file_match = True
                    file_count += 1
                    if args.output_mode == "content":
                        content_lines.append(f"{fp}:{i}:{line}")
            if file_match:
                files_with_matches.append(fp)
                counts[fp] = file_count

        if args.output_mode == "files_with_matches":
            output = "\n".join(str(p) for p in files_with_matches)
            if not output:
                output = f"No matches for {args.pattern!r}"
            return ToolResult(
                output=output,
                metadata={"backend": "python", "files": len(files_with_matches)},
            )

        if args.output_mode == "count":
            output = "\n".join(f"{p}:{counts[p]}" for p in files_with_matches)
            if not output:
                output = f"No matches for {args.pattern!r}"
            return ToolResult(
                output=output,
                metadata={"backend": "python", "files": len(files_with_matches)},
            )

        if args.head_limit is not None and len(content_lines) > args.head_limit:
            content_lines = content_lines[: args.head_limit]
            content_lines.append(f"[truncated to {args.head_limit} lines]")
        output = "\n".join(content_lines) or f"No matches for {args.pattern!r}"
        return ToolResult(
            output=output,
            metadata={"backend": "python", "matches": len(content_lines)},
        )
