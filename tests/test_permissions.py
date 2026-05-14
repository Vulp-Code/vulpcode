"""Tests for the PermissionManager."""
from __future__ import annotations

import pytest
from pydantic import BaseModel

from vulpcode.permissions import Mode, PermissionManager, stdin_prompter
from vulpcode.providers import ToolCall
from vulpcode.tools import Tool, ToolResult, clear_registry, tool


@pytest.fixture
def safe_tool():
    clear_registry()

    @tool(name="ReadX", description="r", requires_confirm=False)
    class T(Tool):
        class Input(BaseModel):
            pass

        async def run(self, args):
            return ToolResult()

    yield T
    clear_registry()


@pytest.fixture
def write_tool():
    clear_registry()

    @tool(name="WriteX", description="w", requires_confirm=True)
    class T(Tool):
        class Input(BaseModel):
            pass

        async def run(self, args):
            return ToolResult()

    yield T
    clear_registry()


@pytest.mark.asyncio
async def test_default_allows_safe_tools(safe_tool):
    pm = PermissionManager(config={}, mode=Mode.DEFAULT)
    d = await pm.check(ToolCall(id="1", name="ReadX", arguments={}), safe_tool)
    assert d.allow and not d.requires_prompt


@pytest.mark.asyncio
async def test_default_prompts_for_destructive(write_tool):
    answers = iter(["y"])

    async def fake(msg, ctx):
        return next(answers)

    pm = PermissionManager(config={}, mode=Mode.DEFAULT, prompter=fake)
    d = await pm.check(ToolCall(id="1", name="WriteX", arguments={}), write_tool)
    assert d.allow
    assert d.requires_prompt


@pytest.mark.asyncio
async def test_default_user_rejects(write_tool):
    async def no(msg, ctx):
        return "n"

    pm = PermissionManager(config={}, mode=Mode.DEFAULT, prompter=no)
    d = await pm.check(ToolCall(id="1", name="WriteX", arguments={}), write_tool)
    assert not d.allow
    assert d.requires_prompt


@pytest.mark.asyncio
async def test_always_persists_in_session(write_tool):
    answers = iter(["a", "x"])  # second call should not invoke the prompter

    async def fake(msg, ctx):
        return next(answers)

    pm = PermissionManager(config={}, mode=Mode.DEFAULT, prompter=fake)
    d1 = await pm.check(ToolCall(id="1", name="WriteX", arguments={}), write_tool)
    d2 = await pm.check(ToolCall(id="2", name="WriteX", arguments={}), write_tool)
    assert d1.allow and d2.allow
    assert "WriteX" in pm._session_allowlist


@pytest.mark.asyncio
async def test_auto_mode_allows_everything(write_tool):
    pm = PermissionManager(config={}, mode=Mode.AUTO)
    d = await pm.check(ToolCall(id="1", name="WriteX", arguments={}), write_tool)
    assert d.allow and not d.requires_prompt


@pytest.mark.asyncio
async def test_plan_mode_blocks_everything(safe_tool):
    pm = PermissionManager(config={}, mode=Mode.PLAN)
    d = await pm.check(ToolCall(id="1", name="ReadX", arguments={}), safe_tool)
    assert not d.allow
    assert not d.requires_prompt


@pytest.mark.asyncio
async def test_safe_mode_prompts_for_safe_tool(safe_tool):
    answers = iter(["y"])

    async def fake(msg, ctx):
        return next(answers)

    pm = PermissionManager(config={}, mode=Mode.SAFE, prompter=fake)
    d = await pm.check(ToolCall(id="1", name="ReadX", arguments={}), safe_tool)
    assert d.allow and d.requires_prompt


@pytest.mark.asyncio
async def test_config_allowlist(write_tool):
    pm = PermissionManager(
        config={"permissions": {"always_allow_tools": ["WriteX"]}},
        mode=Mode.DEFAULT,
    )
    d = await pm.check(ToolCall(id="1", name="WriteX", arguments={}), write_tool)
    assert d.allow
    assert not d.requires_prompt


@pytest.mark.asyncio
async def test_default_unknown_answer_rejects(write_tool):
    async def weird(msg, ctx):
        return "e"

    pm = PermissionManager(config={}, mode=Mode.DEFAULT, prompter=weird)
    d = await pm.check(ToolCall(id="1", name="WriteX", arguments={}), write_tool)
    assert not d.allow


@pytest.mark.asyncio
async def test_prompter_failure_is_rejection(write_tool):
    async def boom(msg, ctx):
        raise RuntimeError("ui broke")

    pm = PermissionManager(config={}, mode=Mode.DEFAULT, prompter=boom)
    d = await pm.check(ToolCall(id="1", name="WriteX", arguments={}), write_tool)
    assert not d.allow


def test_stdin_prompter_is_callable():
    assert callable(stdin_prompter)
