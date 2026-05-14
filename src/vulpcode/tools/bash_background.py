"""BashOutput and KillBash tools (operate on the bash registry)."""
from __future__ import annotations

import asyncio
import re

from pydantic import BaseModel

from vulpcode.tools._bash_registry import get, list_all, remove
from vulpcode.tools.base import Tool, ToolResult, tool


def _drain_buffer(
    buf: list[str], offset: int, regex: re.Pattern | None
) -> tuple[str, int]:
    new_lines = buf[offset:]
    if regex is not None:
        new_lines = [ln for ln in new_lines if regex.search(ln)]
    return "\n".join(new_lines), len(buf)


@tool(
    name="BashOutput",
    description=(
        "Read incremental output from a background bash process started with "
        "Bash(run_in_background=True). Returns only lines emitted since the "
        "previous BashOutput call for the same bash_id."
    ),
    requires_confirm=False,
)
class BashOutputTool(Tool):
    """Read incremental output from a background bash process.

    Returns only the stdout/stderr lines emitted since the previous
    ``BashOutput`` call for the same ``bash_id``. ``filter`` is an optional
    regex applied per line. Pair with :class:`BashTool` (started with
    ``run_in_background=True``).
    """

    class Input(BaseModel):
        bash_id: str
        filter: str | None = None

    async def run(self, args: BaseModel) -> ToolResult:  # type: ignore[override]
        assert isinstance(args, BashOutputTool.Input)
        bp = get(args.bash_id)
        if bp is None:
            return ToolResult(
                error=(
                    f"No background process with id {args.bash_id!r}. "
                    f"Active: {[b.bash_id for b in list_all()]}"
                ),
                is_error=True,
            )
        regex: re.Pattern | None = None
        if args.filter:
            try:
                regex = re.compile(args.filter)
            except re.error as exc:
                return ToolResult(
                    error=f"Invalid filter regex: {exc}", is_error=True
                )

        out_text, new_out_offset = _drain_buffer(bp.stdout, bp.stdout_offset, regex)
        err_text, new_err_offset = _drain_buffer(bp.stderr, bp.stderr_offset, regex)
        bp.stdout_offset = new_out_offset
        bp.stderr_offset = new_err_offset

        if bp.exit_code is None:
            status = "running"
        else:
            status = f"completed (exit code {bp.exit_code})"

        sections = [f"<status>{status}</status>"]
        if out_text:
            sections.append(f"<stdout>\n{out_text}\n</stdout>")
        if err_text:
            sections.append(f"<stderr>\n{err_text}\n</stderr>")
        if not out_text and not err_text:
            sections.append("<no new output>")

        return ToolResult(
            output="\n".join(sections),
            metadata={
                "bash_id": args.bash_id,
                "exit_code": bp.exit_code,
                "running": bp.exit_code is None,
            },
        )


@tool(
    name="KillBash",
    description="Terminate a background bash process by bash_id.",
    requires_confirm=True,
)
class KillBashTool(Tool):
    """Terminate a background bash process by ``bash_id``.

    Looks up the process in the registry and sends SIGTERM. Marked
    ``requires_confirm=True`` because it stops a running process.
    """

    class Input(BaseModel):
        bash_id: str

    async def run(self, args: BaseModel) -> ToolResult:  # type: ignore[override]
        assert isinstance(args, KillBashTool.Input)
        bp = get(args.bash_id)
        if bp is None:
            return ToolResult(
                error=(
                    f"No background process with id {args.bash_id!r}. "
                    f"Active: {[b.bash_id for b in list_all()]}"
                ),
                is_error=True,
            )
        if bp.exit_code is not None:
            remove(args.bash_id)
            return ToolResult(
                output=(
                    f"Process {args.bash_id} already exited with code "
                    f"{bp.exit_code}"
                ),
                metadata={"bash_id": args.bash_id, "already_done": True},
            )
        try:
            bp.process.kill()
            await asyncio.wait_for(bp.process.wait(), timeout=5.0)
        except (ProcessLookupError, asyncio.TimeoutError):
            pass
        bp.exit_code = (
            bp.process.returncode if bp.process.returncode is not None else -1
        )
        remove(args.bash_id)
        return ToolResult(
            output=f"Killed background process {args.bash_id}",
            metadata={"bash_id": args.bash_id, "exit_code": bp.exit_code},
        )
