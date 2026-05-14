"""Tests for the Task subagent tool."""
import pytest

import vulpcode.tools  # noqa: F401  (ensures all tools are registered)
from vulpcode.tools import get_tool
from vulpcode.tools.task import ALLOWED_TOOLS, SUBAGENT_PROMPTS


def test_task_is_registered():
    cls = get_tool("Task")
    assert cls._tool_name == "Task"
    assert cls._requires_confirm is False


def test_task_input_validation():
    cls = get_tool("Task")
    inst = cls.Input(description="d", prompt="p", subagent_type="Explore")
    assert inst.subagent_type == "Explore"
    default = cls.Input(description="d", prompt="p")
    assert default.subagent_type == "general-purpose"
    with pytest.raises(Exception):
        cls.Input(description="d", prompt="p", subagent_type="bogus")


def test_task_allowed_tools_excludes_recursion():
    """Whatever subagent type is used, Task itself must never be allowed."""
    for subtype, allowed in ALLOWED_TOOLS.items():
        assert "Task" not in allowed, f"{subtype} must not allow Task (no recursion)"


def test_explore_subagent_is_read_only():
    explore = ALLOWED_TOOLS["Explore"]
    for forbidden in {"Write", "Edit", "MultiEdit", "Bash"}:
        assert forbidden not in explore


def test_subagent_prompts_match_types():
    assert set(SUBAGENT_PROMPTS) == set(ALLOWED_TOOLS)


async def test_task_runs_or_errors_gracefully():
    """Until FASE 08 wires up Agent.run_to_completion, this returns is_error.
    After FASE 08, this test can be expanded to mock the Agent."""
    cls = get_tool("Task")
    res = await cls().run(
        cls.Input(description="d", prompt="p", subagent_type="Explore")
    )
    # Accept either success (after FASE 08) or graceful error (before FASE 08).
    assert res is not None
    if res.is_error:
        assert res.error
