"""Bash tool: execute shell commands (foreground or background)."""
from __future__ import annotations
import asyncio
import os
from pydantic import BaseModel
from vulpcode.tools._bash_registry import BackgroundProcess, new_id, now, register
from vulpcode.tools._safety import classify_command
from vulpcode.tools.base import Tool, ToolResult, tool

_DEFAULT_TIMEOUT_MS = 120_000
_MAX_TIMEOUT_MS = 600_000
_OUTPUT_LIMIT = 30_000

@tool(name="Bash", description="Run a shell command via bash -c. Supports foreground (default) and background mode.", requires_confirm=True)
class BashTool(Tool):
    class Input(BaseModel):
        command: str
        timeout: int | None = None
        description: str | None = None
        run_in_background: bool = False

    async def run(self, args: BaseModel) -> ToolResult:  # type: ignore[override]
        assert isinstance(args, BashTool.Input)
        timeout_ms = min(args.timeout or _DEFAULT_TIMEOUT_MS, _MAX_TIMEOUT_MS)
        if not os.environ.get("VULPCODE_ALLOW_UNSAFE_COMMANDS"):
            risk = classify_command(args.command)
            if risk is not None and risk.level == "catastrophic":
                return ToolResult(
                    error="Safety guard blocked command: " + str(risk.reason) + ". Set VULPCODE_ALLOW_UNSAFE_COMMANDS=1 to override.",
                    is_error=True, metadata={"risk": "catastrophic", "command": args.command},
                )
        if args.run_in_background:
            return await self._run_background(args.command)
        result = await self._run_foreground(args.command, timeout_ms / 1000.0)
        if not os.environ.get("VULPCODE_ALLOW_UNSAFE_COMMANDS"):
            risk = classify_command(args.command)
            if risk is not None and risk.level == "risky":
                meta = dict(result.metadata or {})
                meta["risk"] = "risky"
                return ToolResult(
                    output="Risky pattern detected: " + str(risk.reason) + "\n\n" + (result.output or ""),
                    error=result.error, is_error=result.is_error, metadata=meta,
                )
        return result

    @staticmethod
    async def _run_foreground(command, timeout):
        try:
            proc = await asyncio.create_subprocess_exec("bash", "-c", command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        except OSError as exc:
            return ToolResult(error=f"Failed to spawn bash: {exc}", is_error=True)
        try:
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return ToolResult(error=f"Command timed out after {timeout}s", is_error=True, metadata={"command": command, "timeout": True})
        stdout = stdout_b.decode("utf-8", errors="replace")
        stderr = stderr_b.decode("utf-8", errors="replace")
        merged = stdout + ("\n" if stdout and stderr else "") + stderr
        if len(merged) > _OUTPUT_LIMIT:
            merged = merged[:_OUTPUT_LIMIT] + f"\n[truncated, full output {len(merged)} chars]"
        if proc.returncode == 0:
            return ToolResult(output=merged, metadata={"exit_code": 0, "command": command})
        return ToolResult(output=merged, error=f"Command exited with code {proc.returncode}", is_error=True, metadata={"exit_code": proc.returncode, "command": command})

    @staticmethod
    async def _run_background(command):
        try:
            proc = await asyncio.create_subprocess_exec("bash", "-c", command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        except OSError as exc:
            return ToolResult(error=f"Failed to spawn bash: {exc}", is_error=True)
        bash_id = new_id()
        bp = BackgroundProcess(bash_id=bash_id, command=command, process=proc, started_at=now())
        register(bp)
        bp._reader_task = asyncio.create_task(_drain(bp))
        return ToolResult(output=f"Started background process {bash_id}: {command}", metadata={"bash_id": bash_id, "background": True})


async def _drain(bp):
    async def _pump(stream, sink):
        if stream is None:
            return
        while True:
            line = await stream.readline()
            if not line:
                break
            sink.append(line.decode("utf-8", errors="replace").rstrip("\n"))
    await asyncio.gather(_pump(bp.process.stdout, bp.stdout), _pump(bp.process.stderr, bp.stderr))
    bp.exit_code = await bp.process.wait()
