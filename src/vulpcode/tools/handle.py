"""HandleRead tool: read a slice of an offloaded tool output."""
from __future__ import annotations

from pydantic import BaseModel, Field

from vulpcode.tools.base import Tool, ToolResult, tool

# Module-level reference to the active ContextHub.  Set by
# register_default_middleware when the hub is instantiated.  Tests can replace
# this directly with a ContextHub instance pointing at a tmp_path.
_hub: object | None = None


def set_hub(hub: object | None) -> None:
    """Wire the active ContextHub into HandleReadTool.  Call from middleware setup."""
    global _hub
    _hub = hub


@tool(
    name="HandleRead",
    description=(
        "Read a slice of an offloaded tool output. Outputs from previous tool "
        "calls that exceeded the context threshold are stored on disk under a "
        "handle ID. Use this to retrieve specific line ranges without re-running "
        "the original command."
    ),
    requires_confirm=False,
)
class HandleReadTool(Tool):
    """Read a slice of a handle written by the ContextHub middleware."""

    class Input(BaseModel):
        handle: str = Field(
            ..., description="Handle filename, e.g. '2026-05-25_14-03-22_Bash_a1b2c3.txt'"
        )
        lines: str = Field(
            "1-200",
            description="Line range like '1-200', '500-600', or 'all'",
        )
        grep: str | None = Field(
            None, description="Optional regex; returns only matching lines"
        )
        max_chars: int = Field(8000, ge=100, le=50000)

    async def run(self, args: BaseModel) -> ToolResult:  # type: ignore[override]
        assert isinstance(args, HandleReadTool.Input)

        if _hub is None:
            return ToolResult(
                error="HandleRead is not available: context hub middleware is not enabled.",
                is_error=True,
            )

        from vulpcode.harness.context_hub import ContextHub

        hub: ContextHub = _hub  # type: ignore[assignment]

        try:
            text = hub.read_slice(
                args.handle,  # type: ignore[attr-defined]
                lines=args.lines,  # type: ignore[attr-defined]
                grep=args.grep,  # type: ignore[attr-defined]
                max_chars=args.max_chars,  # type: ignore[attr-defined]
            )
        except ValueError as exc:
            return ToolResult(error=str(exc), is_error=True)
        except FileNotFoundError as exc:
            return ToolResult(error=str(exc), is_error=True)
        return ToolResult(output=text)
