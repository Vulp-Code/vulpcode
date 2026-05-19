"""E2E test against the real corporate endpoint. Skipped by default.

Enable with: VULP_INTERNAL_LLM_E2E=1 pytest tests/test_providers/test_agentic_e2e_real.py -v
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

import vulpcode.tools  # noqa: F401
import vulpcode.tools.write_py  # noqa: F401
from vulpcode.agent import Agent, ToolEndEvent
from vulpcode.permissions import Mode, PermissionManager
from vulpcode.providers.internal_llm_agentic import InternalLLMAgenticProvider
from vulpcode.tools import list_tools


pytestmark = pytest.mark.skipif(
    os.environ.get("VULP_INTERNAL_LLM_E2E") != "1",
    reason="Set VULP_INTERNAL_LLM_E2E=1 to run E2E against the real endpoint",
)


@pytest.mark.asyncio
async def test_real_endpoint_creates_python_file(tmp_path: Path):
    endpoint = os.environ["INTERNAL_LLM_ENDPOINT"]
    uuid_val = os.environ["INTERNAL_LLM_USER_UUID"]
    provider = InternalLLMAgenticProvider(
        base_url=endpoint, user_uuid=uuid_val,
    )
    agent = Agent(
        provider=provider,
        tools=[cls() for cls in list_tools()],
        model="internal-llm-agentic",
        permissions=PermissionManager(config={}, mode=Mode.AUTO),
    )
    target = tmp_path / "hello.py"
    prompt = (
        f'Create a Python script at {target} that, when run, prints "hello, world". '
        "Use the WritePy tool."
    )
    saw_success = False
    async for ev in agent.turn(prompt):
        if isinstance(ev, ToolEndEvent) and not ev.result.is_error:
            saw_success = True
    assert saw_success
    assert target.exists()
    assert "hello" in target.read_text().lower()
