"""End-to-end smoke tests for the Vulpcode CLI.

These tests exercise the highest-level integration points:

* A canned ``StubProvider`` driving the full ``Agent`` loop with the real
  production tool registry.
* The packaged ``vulp`` console script for ``--help``, ``--version`` and the
  ``providers`` subcommand.
* An optional live test against the real Anthropic API when
  ``ANTHROPIC_API_KEY`` is present in the environment.
"""
from __future__ import annotations

import os
import subprocess
import sys
from typing import Any, AsyncIterator

import pytest

from vulpcode import __version__
from vulpcode.agent import Agent
from vulpcode.permissions import Mode, PermissionManager
from vulpcode.providers.base import Message, Provider, StreamChunk
from vulpcode.tools import list_tools


class StubProvider(Provider):
    """Minimal provider that emits a single text chunk and stops."""

    name = "stub"

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        model: str,
        system: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(type="text", delta="hello from stub")
        yield StreamChunk(type="stop")

    def supports_tools(self) -> bool:
        return True

    def supports_vision(self) -> bool:
        return False


@pytest.mark.asyncio
async def test_full_agent_turn_with_stub_provider():
    """Drive the full Agent loop with the production tool registry and a stub."""
    provider = StubProvider()
    tools = [cls() for cls in list_tools()]
    perms = PermissionManager(config={}, mode=Mode.AUTO)
    agent = Agent(provider=provider, tools=tools, permissions=perms)

    text = await agent.run_to_completion("hello")

    assert "hello from stub" in text


@pytest.mark.asyncio
async def test_stub_provider_capabilities():
    """Sanity-check the StubProvider used in this smoke suite."""
    provider = StubProvider()
    assert provider.supports_tools() is True
    assert provider.supports_vision() is False
    assert provider.name == "stub"


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    """Invoke ``python -m vulpcode.cli`` with the current interpreter."""
    return subprocess.run(
        [sys.executable, "-m", "vulpcode.cli", *args],
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_cli_help_runs():
    result = _run_cli("--help")
    assert result.returncode == 0
    assert "Vulpcode" in result.stdout
    assert "--print" in result.stdout
    assert "--auto" in result.stdout
    assert "--plan" in result.stdout


def test_cli_version_prints_package_version():
    result = _run_cli("--version")
    assert result.returncode == 0
    assert __version__ in result.stdout
    assert "vulpcode" in result.stdout.lower()


def test_cli_providers_lists_known_providers():
    result = _run_cli("providers")
    assert result.returncode == 0
    for expected in ("anthropic", "openai", "gemini", "ollama"):
        assert expected in result.stdout


@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="No API key for live smoke test",
)
def test_print_mode_with_real_api():
    """Optional live smoke test against the real Anthropic API."""
    result = subprocess.run(
        [sys.executable, "-m", "vulpcode.cli", "--print", "say hi in one word"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0
    assert len(result.stdout.strip()) > 0
