"""LoadSkill tool: load a skill's full body into the conversation context."""
from __future__ import annotations

from pydantic import BaseModel, Field

from vulpcode.tools.base import Tool, ToolResult, tool


@tool(
    name="LoadSkill",
    description=(
        "Load the full body of a skill into the conversation context. "
        "Use this when the user's task matches a skill's description listed "
        "under 'Skills disponíveis' in the system prompt. Returns the skill "
        "content; you should then follow its instructions for the rest of "
        "the turn."
    ),
    requires_confirm=False,
)
class LoadSkillTool(Tool):
    class Input(BaseModel):
        name: str = Field(..., description="Skill name as listed in the system prompt.")

    async def run(self, args: "LoadSkillTool.Input") -> ToolResult:  # type: ignore[override]
        import vulpcode.session as _session

        registry = _session.get_session_skill_registry()
        if registry is None:
            return ToolResult(error="Skill registry not configured.", is_error=True)

        skill = registry.get(args.name)
        if skill is None:
            available = [s.name for s in registry.all()]
            return ToolResult(
                error=f"Skill {args.name!r} not found. Available: {available}",
                is_error=True,
            )

        if skill.tools_allow is not None:
            state = _session._current_state.get(None)
            if state is not None:
                state.metadata["active_skill_tools_allow"] = skill.tools_allow

        return ToolResult(output=skill.body)
