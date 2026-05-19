"""Retrieve tool: fetch slices from a cached large tool result by cache_id.

The agentic provider stores full tool-result bodies in a process-global
:class:`~vulpcode.providers._content_store.ContentStore` whenever they exceed
the preview threshold. The model only sees a head/tail preview plus a
``cache_id`` (the original ``tool_call_id``). To inspect the rest, the model
calls ``Retrieve(cache_id="tt-abc", start_line=200, end_line=260)`` — or
``pattern="^class "`` for regex-based slicing.

The tool is cheap (in-memory lookup, no disk I/O) and works for ANY cached
tool result: Read, Grep, Bash, Glob, etc. Same content is guaranteed —
no race where the file changed between calls.
"""
from __future__ import annotations

import re

from pydantic import BaseModel, Field

from vulpcode.providers._content_store import get_default_store
from vulpcode.tools.base import Tool, ToolResult, tool


_MAX_OUTPUT_LINES = 400  # safety cap on a single Retrieve response


@tool(
    name="Retrieve",
    description=(
        "Fetch a slice from a cached large tool result by cache_id (the same id "
        "you see in a <vulp:tool_result cached=\"true\" ...> envelope). Use this "
        "instead of re-running Read/Grep/Bash. Supports line ranges (start_line, "
        "end_line) AND regex pattern matching with context lines. Cheap, no I/O."
    ),
    requires_confirm=False,
)
class RetrieveTool(Tool):
    """Fetch a slice from a previously-cached tool result.

    Three slicing modes (use exactly one):
      - ``start_line`` / ``end_line`` (1-based, inclusive). End defaults to
        start + 100 if only ``start_line`` is given.
      - ``pattern`` (regex). Returns every matching line + ``context_lines``
        before/after each.
      - Neither: returns the first ``_MAX_OUTPUT_LINES`` lines plus a summary.
    """

    class Input(BaseModel):
        cache_id: str
        start_line: int | None = Field(default=None, ge=1)
        end_line: int | None = Field(default=None, ge=1)
        pattern: str | None = None
        context_lines: int = Field(default=0, ge=0, le=20)
        flag_i: bool = Field(default=False, alias="-i")

        model_config = {"populate_by_name": True}

    async def run(self, args: BaseModel) -> ToolResult:  # type: ignore[override]
        assert isinstance(args, RetrieveTool.Input)
        store = get_default_store()
        stored = store.get(args.cache_id)
        if stored is None:
            available = store.list_ids()
            hint = (
                f" Known cache_ids: {', '.join(available[:10])}"
                + (" …" if len(available) > 10 else "")
                if available
                else " (cache is empty)"
            )
            return ToolResult(
                error=f"cache_id {args.cache_id!r} not found.{hint}",
                is_error=True,
            )

        lines = stored.lines or stored.full_body.splitlines()
        stored.lines = lines  # cache split for next call
        total = len(lines)

        if args.pattern is not None:
            return self._slice_by_pattern(stored, lines, total, args)
        if args.start_line is not None or args.end_line is not None:
            return self._slice_by_range(stored, lines, total, args)
        return self._slice_default(stored, lines, total)

    @staticmethod
    def _slice_by_range(
        stored, lines: list[str], total: int, args: "RetrieveTool.Input"
    ) -> ToolResult:
        start = args.start_line or 1
        end = args.end_line or min(total, start + 100 - 1)
        if start > total:
            return ToolResult(
                output=f"start_line {start} exceeds total lines {total}",
                metadata={"cache_id": stored.cache_id, "total_lines": total},
            )
        end = min(end, total, start + _MAX_OUTPUT_LINES - 1)
        out_lines = [
            f"{i + start}: {lines[i + start - 1]}" for i in range(end - start + 1)
        ]
        truncated = end - start + 1 == _MAX_OUTPUT_LINES and end < (args.end_line or end)
        body = "\n".join(out_lines)
        if truncated:
            body += f"\n[truncated to {_MAX_OUTPUT_LINES} lines]"
        return ToolResult(
            output=body,
            metadata={
                "cache_id": stored.cache_id,
                "tool_name": stored.tool_name,
                "lines_returned": end - start + 1,
                "total_lines": total,
                "range": f"{start}-{end}",
            },
        )

    @staticmethod
    def _slice_by_pattern(
        stored, lines: list[str], total: int, args: "RetrieveTool.Input"
    ) -> ToolResult:
        flags = re.IGNORECASE if args.flag_i else 0
        try:
            pat = re.compile(args.pattern or "", flags)
        except re.error as exc:
            return ToolResult(error=f"Invalid regex: {exc}", is_error=True)

        ctx = args.context_lines
        match_idxs = [i for i, ln in enumerate(lines) if pat.search(ln)]
        if not match_idxs:
            return ToolResult(
                output=f"No matches for {args.pattern!r} in cache {stored.cache_id}",
                metadata={
                    "cache_id": stored.cache_id,
                    "tool_name": stored.tool_name,
                    "matches": 0,
                    "total_lines": total,
                },
            )

        # Build merged windows around each match (inclusive) so adjacent matches
        # share context instead of duplicating it.
        windows: list[tuple[int, int]] = []
        for i in match_idxs:
            lo, hi = max(0, i - ctx), min(total - 1, i + ctx)
            if windows and lo <= windows[-1][1] + 1:
                windows[-1] = (windows[-1][0], max(windows[-1][1], hi))
            else:
                windows.append((lo, hi))

        out: list[str] = []
        emitted = 0
        truncated = False
        for w_idx, (lo, hi) in enumerate(windows):
            if w_idx > 0:
                out.append("--")
            for i in range(lo, hi + 1):
                if emitted >= _MAX_OUTPUT_LINES:
                    truncated = True
                    break
                out.append(f"{i + 1}: {lines[i]}")
                emitted += 1
            if truncated:
                break

        body = "\n".join(out)
        if truncated:
            body += f"\n[truncated to {_MAX_OUTPUT_LINES} lines]"
        return ToolResult(
            output=body,
            metadata={
                "cache_id": stored.cache_id,
                "tool_name": stored.tool_name,
                "matches": len(match_idxs),
                "total_lines": total,
                "lines_returned": emitted,
            },
        )

    @staticmethod
    def _slice_default(stored, lines: list[str], total: int) -> ToolResult:
        head = lines[:_MAX_OUTPUT_LINES]
        out_lines = [f"{i + 1}: {ln}" for i, ln in enumerate(head)]
        body = "\n".join(out_lines)
        if total > _MAX_OUTPUT_LINES:
            body += (
                f"\n[showing first {_MAX_OUTPUT_LINES} of {total} lines — "
                f"call Retrieve again with start_line/end_line for the rest]"
            )
        return ToolResult(
            output=body,
            metadata={
                "cache_id": stored.cache_id,
                "tool_name": stored.tool_name,
                "lines_returned": len(head),
                "total_lines": total,
            },
        )
