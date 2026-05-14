"""Bash tool: execute shell commands (foreground or background)."""
from __future__ import annotations

import asyncio

from pydantic import BaseModel

from vulpcode.tools._bash_registry import (
    BackgroundProcess,
    new_id,
    now,
    register,
)
from vulpcode.tools.base import Tool, ToolResult, tool


_DEFAULT_TIMEOUT_MS = 120_000
_MAX_TIMEOUT_MS = 600_000
_OUTPUT_LIMIT = 30_000  # chars


@tool(
    name="Bash",
    description=(
        "Run a shell command via bash -c. Supports foreground (default) and "
        "background mode. Foreground waits up to timeout (ms) and returns merged "
        "stdout+stderr. Background returns immediately with a bash_id for use with "
        "BashOutput / KillBash."
    ),
    requires_confirm=True,
)
class BashTool(Tool):
    """Execute a shell command via ``bash -c``.

    Foreground mode (default) waits up to ``timeout`` ms (max 600 000 ms,
    i.e. 10 minutes) and returns merged stdout+stderr clipped to 30 000
    characters. Background mode (``run_in_background=True``) returns
    immediately with a ``bash_id`` you can poll with
    :class:`BashOutputTool` and stop with :class:`KillBashTool`.

    Marked ``requires_confirm=True`` because shell commands are inherently
    destructive on the host system.
    """

    class Input(BaseModel):
        command: str
        timeout: int | None = None
        description: str | None = None
        run_in_background: bool = False

    async def run(self, args: BaseModel) -> ToolResult:  # type: ignore[override]
        assert isinstance(args, BashTool.Input)
        timeout_ms = args.timeout or _DEFAULT_TIMEOUT_MS
        if timeout_ms > _MAX_TIMEOUT_MS:
            timeout_ms = _MAX_TIMEOUT_MS

        if args.run_in_background:
            return await self._run_background(args.command)
        return await self._run_foreground(args.command, timeout_ms / 1000.0)

    @staticmethod
    async def _run_foreground(command: str, timeout: float) -> ToolResult:
        try:
            proc = await asyncio.create_subprocess_exec(
                "bash",
                "-c",
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            return ToolResult(error=f"Failed to spawn bash: {exc}", is_error=True)

        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return ToolResult(
                error=f"Command timed out after {timeout}s",
                is_error=True,
                metadata={"command": command, "timeout": True},
            )

        stdout = stdout_b.decode("utf-8", errors="replace")
        stderr = stderr_b.decode("utf-8", errors="replace")
        merged = stdout + ("\n" if stdout and stderr else "") + stderr
        if len(merged) > _OUTPUT_LIMIT:
            merged = (
                merged[:_OUTPUT_LIMIT]
                + f"\n[truncated, full output {len(merged)} chars]"
            )
        if proc.returncode == 0:
            return ToolResult(
                output=merged,
                metadata={"exit_code": 0, "command": command},
            )
        return ToolResult(
            output=merged,
            error=f"Command exited with code {proc.returncode}",
            is_error=True,
            metadata={"exit_code": proc.returncode, "command": command},
        )

    @staticmethod
    async def _run_background(command: str) -> ToolResult:
        try:
            proc = await asyncio.create_subprocess_exec(
                "bash",
                "-c",
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            return ToolResult(error=f"Failed to spawn bash: {exc}", is_error=True)

        bash_id = new_id()
        bp = BackgroundProcess(
            bash_id=bash_id,
            command=command,
            process=proc,
            started_at=now(),
        )
        register(bp)
        bp._reader_task = asyncio.create_task(_drain(bp))
        return ToolResult(
            output=f"Started background process {bash_id}: {command}",
            metadata={"bash_id": bash_id, "background": True},
        )


async def _drain(bp: BackgroundProcess) -> None:
    """Read stdout/stderr lines into bp.stdout/bp.stderr until the process ends."""

    async def _pump(stream: asyncio.StreamReader | None, sink: list[str]) -> None:
        if stream is None:
            return
        while True:
            line = await stream.readline()
            if not line:
                break
            sink.append(line.decode("utf-8", errors="replace").rstrip("\n"))

    await asyncio.gather(
        _pump(bp.process.stdout, bp.stdout),
        _pump(bp.process.stderr, bp.stderr),
    )
    bp.exit_code = await bp.process.wait()
