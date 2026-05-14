"""Task tool: launch a subagent with isolated context."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from vulpcode.tools.base import Tool, ToolResult, tool


SUBAGENT_PROMPTS: dict[str, str] = {
    "general-purpose": (
        "You are a focused subagent. Solve the given task in as few steps as "
        "possible. Use tools as needed. End by writing the final answer as plain "
        "text - no markdown headers, just the answer."
    ),
    "Explore": (
        "You are a fast read-only search subagent. Locate files and patterns. "
        "Do NOT edit, write, or run shell commands beyond `find`/`grep`. Report "
        "findings concisely with file paths."
    ),
}

ALLOWED_TOOLS: dict[str, set[str]] = {
    "general-purpose": {
        "Read",
        "Write",
        "Edit",
        "MultiEdit",
        "Bash",
        "BashOutput",
        "Grep",
        "Glob",
        "WebFetch",
        "WebSearch",
        "TodoWrite",
    },
    "Explore": {"Read", "Grep", "Glob"},
}


@tool(
    name="Task",
    description=(
        "Launch a subagent to perform a focused task with isolated context. "
        "Useful for parallelizable independent work. Returns the subagent's "
        "final answer as a string."
    ),
    requires_confirm=False,
)
class TaskTool(Tool):
    """Launch a subagent with isolated context.

    Spawns a fresh :class:`vulpcode.agent.Agent` with its own message history
    and a constrained tool whitelist (see :data:`ALLOWED_TOOLS`). The
    subagent runs to completion and returns its final answer as plain text.
    Use ``subagent_type="Explore"`` for read-only search tasks and
    ``"general-purpose"`` for everything else.
    """

    class Input(BaseModel):
        description: str
        prompt: str
        subagent_type: Literal["general-purpose", "Explore"] = "general-purpose"

    async def run(self, args: BaseModel) -> ToolResult:  # type: ignore[override]
        assert isinstance(args, TaskTool.Input)

        # Lazy imports avoid circular dependency: Agent imports the tool registry.
        try:
            from vulpcode.agent import Agent
            from vulpcode.config import load_config
            from vulpcode.providers import build_provider
        except ImportError as exc:
            return ToolResult(
                error=f"Subagent unavailable (missing module): {exc}",
                is_error=True,
            )

        try:
            cfg = load_config()
        except Exception as exc:
            return ToolResult(
                error=f"Subagent unavailable (config load failed): {exc}",
                is_error=True,
            )

        provider_name = cfg.get("default_provider", "anthropic")
        model = cfg.get("default_model", "")
        provider_cfg = (cfg.get("providers", {}) or {}).get(provider_name, {})

        try:
            provider = build_provider(provider_name, provider_cfg)
        except Exception as exc:
            return ToolResult(
                error=f"Subagent unavailable (provider build failed): {exc}",
                is_error=True,
            )

        from vulpcode.tools.base import TOOL_REGISTRY

        allowed = ALLOWED_TOOLS.get(
            args.subagent_type, ALLOWED_TOOLS["general-purpose"]
        )
        # Subagents cannot call Task themselves (no nesting in v1).
        sub_tools = [
            cls() for name, cls in TOOL_REGISTRY.items()
            if name in allowed and name != "Task"
        ]

        try:
            agent = Agent(
                provider=provider,
                tools=sub_tools,
                system=SUBAGENT_PROMPTS[args.subagent_type],
                model=model,
            )
        except Exception as exc:
            return ToolResult(
                error=f"Subagent unavailable (agent init failed): {exc}",
                is_error=True,
            )

        try:
            final_text = await agent.run_to_completion(args.prompt)
        except Exception as exc:
            return ToolResult(
                error=f"Subagent failed: {type(exc).__name__}: {exc}",
                is_error=True,
            )

        return ToolResult(
            output=final_text or "<subagent returned no text>",
            metadata={
                "subagent_type": args.subagent_type,
                "description": args.description,
            },
        )
