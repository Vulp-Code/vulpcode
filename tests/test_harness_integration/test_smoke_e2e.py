"""Subprocess smoke test for the Vulpcode harness integration.

Exercises the CLI end-to-end via subprocess using the built-in stub/scripted
provider. Verifies the agent loop, tool dispatch, and harness hooks all wire
together without import errors or crashes.
"""
from __future__ import annotations

import subprocess
import sys

import pytest


def _run_vulp(*args: str, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "vulpcode", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def test_version_exits_cleanly() -> None:
    """--version exits 0 and prints a version string."""
    result = _run_vulp("--version")
    assert result.returncode == 0
    assert result.stdout.strip()


def test_help_exits_cleanly() -> None:
    """--help exits 0 and mentions key flags."""
    result = _run_vulp("--help")
    assert result.returncode == 0
    assert "--provider" in result.stdout or "provider" in result.stdout.lower()


def test_providers_subcommand() -> None:
    """providers subcommand exits 0 and lists at least one provider."""
    result = _run_vulp("providers")
    assert result.returncode == 0
    assert result.stdout.strip()


def test_harness_import_clean() -> None:
    """All harness modules import without errors."""
    result = subprocess.run(
        [
            sys.executable, "-c",
            "from vulpcode.harness import register_default_middleware; "
            "from vulpcode.harness.hooks import HookBus; "
            "from vulpcode.harness.eviction import EvictionConfig, evict_messages; "
            "from vulpcode.harness.summarization import SummarizationConfig, SummarizationHook; "
            "from vulpcode.harness.context_hub import ContextHub, ContextHubConfig; "
            "from vulpcode.harness.skills import SkillRegistry, SkillsConfig; "
            "from vulpcode.harness.profiles import Profile; "
            "from vulpcode.harness.tool_patch import ToolPatcher, ToolPatchConfig; "
            "from vulpcode.harness.state import LoopState; "
            "print('ok')",
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, f"Harness import failed:\n{result.stderr}"
    assert "ok" in result.stdout


def test_agent_with_hookbus_no_crash() -> None:
    """Agent + HookBus + eviction hook completes a turn without crashing."""
    result = subprocess.run(
        [
            sys.executable, "-c",
            """
import asyncio
from vulpcode.agent import Agent
from vulpcode.harness.hooks import HookBus
from vulpcode.harness.eviction import EvictionConfig, evict_messages
from vulpcode.harness.state import LoopState
from vulpcode.providers.base import Message, Provider, StreamChunk
from typing import Any, AsyncIterator

class ScriptedProvider(Provider):
    name = "scripted"
    async def stream(self, messages, tools, model="", system=None, **kw) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(type="text", delta="all good")
        yield StreamChunk(type="stop")
    def supports_tools(self): return True
    def supports_vision(self): return False

bus = HookBus()
cfg = EvictionConfig(enabled=True, max_messages=10, keep_recent=5)
def evict(state, **_): evict_messages(state, cfg)
bus.register("before_iteration", evict)

agent = Agent(provider=ScriptedProvider(), tools=[], hook_bus=bus)
result = asyncio.run(agent.run_to_completion("hello"))
assert "all good" in result, f"Unexpected result: {result!r}"
print("smoke ok")
""",
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, f"Agent smoke test failed:\n{result.stderr}"
    assert "smoke ok" in result.stdout
