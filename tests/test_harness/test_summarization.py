"""Tests for harness auto-summarization middleware."""
from __future__ import annotations

from typing import Any, AsyncIterator

import pytest

from vulpcode.harness.state import LoopState
from vulpcode.harness.summarization import (
    SUMMARIZATION_PROMPT_TEMPLATE,
    SummarizationConfig,
    SummarizationHook,
    summarize_history,
)
from vulpcode.providers.base import Message, Provider, StreamChunk, Usage


# ---------------------------------------------------------------------------
# FakeProvider
# ---------------------------------------------------------------------------


class FakeProvider(Provider):
    """Provider that returns a fixed string from stream() without any real API call."""

    name = "fake"

    def __init__(self, reply: str = "summary text") -> None:
        super().__init__()
        self.reply = reply
        self.calls: list[list[Message]] = []

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        model: str,
        system: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        self.calls.append(list(messages))
        yield StreamChunk(type="text", delta=self.reply)
        yield StreamChunk(type="stop")

    def supports_tools(self) -> bool:
        return False

    def supports_vision(self) -> bool:
        return False


class ErrorProvider(Provider):
    """Provider that always raises an exception."""

    name = "error"

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        model: str,
        system: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        raise RuntimeError("provider exploded")
        yield  # pragma: no cover

    def supports_tools(self) -> bool:
        return False

    def supports_vision(self) -> bool:
        return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _system(text: str = "sys") -> Message:
    return Message(role="system", content=text)


def _user(text: str = "hi") -> Message:
    return Message(role="user", content=text)


def _assistant(text: str = "ok") -> Message:
    return Message(role="assistant", content=text)


def _make_state(messages: list[Message], iteration: int = 0) -> LoopState:
    return LoopState(messages=messages, usage=Usage(), iteration=iteration)


def _big_conversation(n: int = 100) -> list[Message]:
    """Build a conversation with a system msg, then n user+assistant pairs."""
    msgs: list[Message] = [_system("You are a coding agent.")]
    for i in range(n):
        msgs.append(_user(f"question {i} " + "x" * 200))
        msgs.append(_assistant(f"answer {i} " + "x" * 200))
    return msgs


# ---------------------------------------------------------------------------
# Tests — summarize_history (pure function)
# ---------------------------------------------------------------------------


async def test_summarize_history_reduces_count() -> None:
    """Large history is collapsed to system + summary + keep_recent messages."""
    provider = FakeProvider("compact summary")
    messages = _big_conversation(50)  # 1 system + 100 user/assistant = 101 total

    result = await summarize_history(
        messages, provider, keep_recent=5, target_tokens=500
    )

    # system + 1 summary + 5 recent
    assert len(result) == 7
    assert result[0].role == "system"
    assert result[0].content == "You are a coding agent."
    assert result[1].role == "system"
    assert "[Conversation summary:" in str(result[1].content)
    # last 5 messages preserved verbatim
    assert result[2:] == messages[-5:]


async def test_summarize_preserves_system_and_recent() -> None:
    """Leading system messages and last keep_recent messages are untouched."""
    provider = FakeProvider("summary here")
    sys1 = _system("prompt 1")
    sys2 = _system("prompt 2")
    u1 = _user("old question 1")
    a1 = _assistant("old answer 1")
    u2 = _user("recent question")
    a2 = _assistant("recent answer")
    messages = [sys1, sys2, u1, a1, u2, a2]

    result = await summarize_history(
        messages, provider, keep_recent=2, target_tokens=100
    )

    # sys1, sys2, summary_msg, u2, a2
    assert result[0] is sys1
    assert result[1] is sys2
    assert result[2].role == "system"
    assert "[Conversation summary:" in str(result[2].content)
    assert result[3] is u2
    assert result[4] is a2


async def test_summarize_calls_provider_with_template() -> None:
    """The summarization prompt sent to the provider includes all 5 preservation rules."""
    provider = FakeProvider("ok")
    messages = [_user("question"), _assistant("answer"), _user("q2"), _assistant("a2")]

    await summarize_history(messages, provider, keep_recent=1, target_tokens=200)

    assert len(provider.calls) == 1
    prompt = provider.calls[0][0].content
    assert isinstance(prompt, str)
    # All 5 preservation rules must appear in the prompt
    assert "Objetivo principal" in prompt
    assert "Decisões tomadas" in prompt
    assert "Arquivos criados" in prompt
    assert "Erros encontrados" in prompt
    assert "TODO pendente" in prompt


async def test_summarize_noop_when_all_recent() -> None:
    """When keep_recent >= non-system messages, returns the original list unchanged."""
    provider = FakeProvider("nope")
    messages = [_system(), _user("hi"), _assistant("hello")]

    result = await summarize_history(messages, provider, keep_recent=10, target_tokens=100)

    assert result == messages
    assert provider.calls == []


# ---------------------------------------------------------------------------
# Tests — SummarizationHook
# ---------------------------------------------------------------------------


async def test_hook_noop_when_below_threshold() -> None:
    """Hook does not call provider when total tokens are below trigger_at_tokens."""
    provider = FakeProvider()
    cfg = SummarizationConfig(
        enabled=True,
        trigger_at_tokens=60000,
        keep_recent_messages=5,
        cooldown_iterations=1,
    )
    hook = SummarizationHook(cfg, provider)
    # 10 short messages — well below 60k tokens
    msgs = [_user(f"msg{i}") for i in range(10)]
    state = _make_state(msgs, iteration=10)

    await hook(state)

    assert provider.calls == []
    assert state.messages == msgs


async def test_hook_respects_cooldown() -> None:
    """Second firing is suppressed if cooldown_iterations has not elapsed."""
    provider = FakeProvider("summary")
    cfg = SummarizationConfig(
        enabled=True,
        trigger_at_tokens=1,  # always triggers on any content
        keep_recent_messages=1,
        cooldown_iterations=5,
    )
    hook = SummarizationHook(cfg, provider)
    msgs = [_user("x" * 100), _assistant("y" * 100), _user("z")]
    state = _make_state(msgs, iteration=5)

    # First call — fires
    await hook(state)
    assert len(provider.calls) == 1
    first_fire_iter = hook._last_fired

    # Second call immediately (iteration unchanged) — suppressed
    provider.calls.clear()
    await hook(state)
    assert provider.calls == []

    # Call after cooldown has elapsed — use a fresh message list so there is
    # still middle content to summarize.
    provider.calls.clear()
    fresh_msgs = [_user("x" * 100), _assistant("y" * 100), _user("z")]
    state2 = _make_state(fresh_msgs, iteration=first_fire_iter + cfg.cooldown_iterations + 1)
    hook._last_fired = first_fire_iter  # restore to simulate time passing
    await hook(state2)
    assert len(provider.calls) == 1


async def test_hook_swallows_provider_error() -> None:
    """Provider exception is logged and swallowed; state.messages is unchanged."""
    cfg = SummarizationConfig(
        enabled=True,
        trigger_at_tokens=1,
        keep_recent_messages=1,
        cooldown_iterations=1,
    )
    hook = SummarizationHook(cfg, ErrorProvider())
    original = [_user("x" * 100), _assistant("y" * 100)]
    state = _make_state(list(original), iteration=10)

    # Must not raise
    await hook(state)

    assert state.messages == original


# ---------------------------------------------------------------------------
# Test — /compact command smoke test
# ---------------------------------------------------------------------------


async def test_compact_command_still_works() -> None:
    """CompactCommand delegates to summarize_history and produces console output."""
    from unittest.mock import AsyncMock, MagicMock

    from vulpcode.commands.compact import CompactCommand

    provider = FakeProvider("concise summary of the conversation")

    # Build a minimal mock repl/agent
    agent = MagicMock()
    agent._messages = [
        _system("You are Vulpcode."),
        _user("write a hello world"),
        _assistant("here is hello world"),
        _user("now add types"),
        _assistant("done with types"),
        _user("commit it"),
        _assistant("committed"),
    ]
    agent.provider = provider
    agent.model = "test-model"

    console_output: list[str] = []

    renderer = MagicMock()
    renderer.console.print = lambda msg: console_output.append(msg)

    repl = MagicMock()
    repl.agent = agent
    repl.renderer = renderer

    cmd = CompactCommand()
    await cmd.run(repl, "")

    # history was replaced
    assert agent._messages is not None
    assert len(agent._messages) < 7  # compacted

    # Console showed completion message
    printed = " ".join(console_output)
    assert "compacted" in printed
