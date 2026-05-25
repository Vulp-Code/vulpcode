"""Tests for LoadSkillTool and enforce_skill_tool_filter (FASE_05.02)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

import vulpcode.session as _session
from vulpcode.harness.skills import Skill, SkillRegistry, SkillsConfig, enforce_skill_tool_filter
from vulpcode.harness.state import LoopState
from vulpcode.tools.load_skill import LoadSkillTool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_skill(
    name: str,
    body: str = "skill body",
    tools_allow: list[str] | None = None,
    tmp_path: Path | None = None,
) -> Skill:
    return Skill(
        name=name,
        description=f"Description of {name}",
        body=body,
        tools_allow=tools_allow,
        path=tmp_path or Path("/tmp/skills") / name,
    )


def _make_registry_with_skills(skills: list[Skill]) -> SkillRegistry:
    cfg = SkillsConfig(enabled=True, search_dirs=[])
    registry = SkillRegistry(cfg)
    for s in skills:
        registry._skills[s.name] = s
    return registry


# ---------------------------------------------------------------------------
# LoadSkillTool tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_existing_skill():
    """Tool returns the skill body when the skill exists."""
    skill = _make_skill("foo", body="do the foo thing")
    registry = _make_registry_with_skills([skill])
    _session.skill_registry = registry

    tool = LoadSkillTool()
    result = await tool.run(LoadSkillTool.Input(name="foo"))

    assert not result.is_error
    assert "do the foo thing" in result.output

    _session.skill_registry = None


@pytest.mark.asyncio
async def test_load_missing_skill():
    """Tool returns is_error=True and lists available skills when skill not found."""
    skill_a = _make_skill("alpha")
    skill_b = _make_skill("beta")
    registry = _make_registry_with_skills([skill_a, skill_b])
    _session.skill_registry = registry

    tool = LoadSkillTool()
    result = await tool.run(LoadSkillTool.Input(name="nonexistent"))

    assert result.is_error
    assert "nonexistent" in (result.error or "")
    assert "alpha" in (result.error or "")
    assert "beta" in (result.error or "")

    _session.skill_registry = None


@pytest.mark.asyncio
async def test_load_no_registry():
    """Tool returns is_error=True when skill registry is not configured."""
    _session.skill_registry = None

    tool = LoadSkillTool()
    result = await tool.run(LoadSkillTool.Input(name="anything"))

    assert result.is_error
    assert "not configured" in (result.error or "").lower()


@pytest.mark.asyncio
async def test_load_sets_active_tools_allow():
    """Loading a skill with tools_allow populates state.metadata."""
    skill = _make_skill("refactor", tools_allow=["Read", "Grep"])
    registry = _make_registry_with_skills([skill])
    _session.skill_registry = registry

    state = LoopState()
    token = _session._current_state.set(state)
    try:
        tool = LoadSkillTool()
        result = await tool.run(LoadSkillTool.Input(name="refactor"))

        assert not result.is_error
        assert state.metadata.get("active_skill_tools_allow") == ["Read", "Grep"]
    finally:
        _session._current_state.reset(token)
        _session.skill_registry = None


@pytest.mark.asyncio
async def test_load_no_tools_allow_leaves_metadata_unchanged():
    """Loading a skill without tools_allow does not set active_skill_tools_allow."""
    skill = _make_skill("plain", tools_allow=None)
    registry = _make_registry_with_skills([skill])
    _session.skill_registry = registry

    state = LoopState()
    token = _session._current_state.set(state)
    try:
        tool = LoadSkillTool()
        await tool.run(LoadSkillTool.Input(name="plain"))

        assert "active_skill_tools_allow" not in state.metadata
    finally:
        _session._current_state.reset(token)
        _session.skill_registry = None


# ---------------------------------------------------------------------------
# enforce_skill_tool_filter tests
# ---------------------------------------------------------------------------


def test_filter_blocks_disallowed_tool():
    """Hook returns a ToolResult error when the tool is not in the allow-list."""
    state = LoopState()
    state.metadata["active_skill_tools_allow"] = ["Read"]

    call = MagicMock()
    call.name = "Bash"

    result = enforce_skill_tool_filter(state, call=call)

    assert result is not None
    assert result.is_error
    assert "Bash" in (result.error or "")
    assert "allow" in (result.error or "").lower()


def test_filter_allows_listed_tool():
    """Hook returns None when the tool is in the allow-list."""
    state = LoopState()
    state.metadata["active_skill_tools_allow"] = ["Read", "Grep"]

    call = MagicMock()
    call.name = "Read"

    result = enforce_skill_tool_filter(state, call=call)

    assert result is None


def test_filter_noop_without_active_skill():
    """Hook returns None when no active skill is set (empty metadata)."""
    state = LoopState()

    call = MagicMock()
    call.name = "Bash"

    result = enforce_skill_tool_filter(state, call=call)

    assert result is None


def test_filter_noop_with_none_allow_list():
    """Hook returns None when active_skill_tools_allow is explicitly None."""
    state = LoopState()
    state.metadata["active_skill_tools_allow"] = None

    call = MagicMock()
    call.name = "Bash"

    result = enforce_skill_tool_filter(state, call=call)

    assert result is None
