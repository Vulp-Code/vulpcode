"""Auto-summarization middleware for long conversation histories.

When the estimated token count crosses ``trigger_at_tokens`` the hook calls
``summarize_history`` and replaces the middle portion of the conversation with
a single compact system message, keeping leading system messages and the most
recent turns intact.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from vulpcode.harness._tokens import count_tokens
from vulpcode.harness.state import LoopState
from vulpcode.providers.base import Message, Provider

logger = logging.getLogger("vulpcode.harness.summarization")

SUMMARIZATION_PROMPT_TEMPLATE = """\
Resuma a conversa abaixo entre um agente de programação e o usuário. Preserve:

1. Objetivo principal do usuário (literal, se conhecido).
2. Decisões tomadas (arquitetura, escolha de tools, bibliotecas).
3. Arquivos criados ou modificados com paths completos.
4. Erros encontrados e como foram resolvidos.
5. TODO pendente declarado pelo agente ou pelo usuário.

Não inclua tool outputs verbatim — só o que foi aprendido com eles. Saída em ~{target} tokens\
 de português técnico denso, sem prosa de abertura/fechamento.

Conversa:
{transcript}"""


@dataclass
class SummarizationConfig:
    enabled: bool = False
    trigger_at_tokens: int = 60000
    keep_recent_messages: int = 20
    target_tokens: int = 8000
    cooldown_iterations: int = 5
    summary_model: str = ""


def _content_to_str(content: str | list[Any]) -> str:
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                text = block.get("text", "")
                if text:
                    parts.append(text)
        return " ".join(parts)
    return content if isinstance(content, str) else ""


def _leading_system_count(msgs: list[Message]) -> int:
    count = 0
    for m in msgs:
        if m.role == "system":
            count += 1
        else:
            break
    return count


async def summarize_history(
    messages: list[Message],
    provider: Provider,
    *,
    keep_recent: int,
    target_tokens: int,
    summary_model: str = "",
    model: str = "",
) -> list[Message]:
    """Summarize the middle portion of *messages* using *provider*.

    Leading ``role="system"`` messages and the last *keep_recent* messages are
    preserved verbatim. Everything in between is replaced by a single
    ``role="system"`` summary message.

    Returns the original list unchanged when there is nothing to summarize
    (middle is empty or too small).
    """
    sys_end = _leading_system_count(messages)
    system_msgs = messages[:sys_end]
    rest = messages[sys_end:]

    if len(rest) <= keep_recent:
        return list(messages)

    cutoff = len(rest) - keep_recent
    middle = rest[:cutoff]
    recent = rest[cutoff:]

    if not middle:
        return list(messages)

    transcript_lines = [f"[{m.role}] {_content_to_str(m.content)}" for m in middle]
    transcript = "\n".join(transcript_lines)

    prompt = SUMMARIZATION_PROMPT_TEMPLATE.format(
        target=target_tokens,
        transcript=transcript,
    )

    use_model = summary_model or model
    text = ""
    async for chunk in provider.stream(
        messages=[Message(role="user", content=prompt)],
        tools=[],
        model=use_model,
        system="You are a concise technical summarizer.",
    ):
        if chunk.type == "text" and chunk.delta:
            text += chunk.delta
        elif chunk.type == "stop":
            break

    summary_msg = Message(
        role="system",
        content=f"[Conversation summary: {text.strip()}]",
    )
    return [*system_msgs, summary_msg, *recent]


class SummarizationHook:
    """Stateful ``before_iteration`` hook that auto-compacts long histories.

    Fires when the estimated token count of ``state.messages`` exceeds
    ``config.trigger_at_tokens``, subject to a cooldown between firings.
    Exceptions from the provider are swallowed so the agent loop continues.
    """

    name = "summarization"
    reads: tuple[str, ...] = ("messages", "iteration")
    writes: tuple[str, ...] = ("messages",)

    def __init__(
        self,
        config: SummarizationConfig,
        provider: Provider,
        model: str = "",
    ) -> None:
        self.config = config
        self.provider = provider
        self.model = model
        self._last_fired: int = -(config.cooldown_iterations + 1)
        self._lock: asyncio.Lock = asyncio.Lock()

    async def __call__(self, state: LoopState, **_kwargs: Any) -> None:
        """Async hook handler for ``before_iteration``."""
        if not self.config.enabled:
            return
        if state.iteration - self._last_fired < self.config.cooldown_iterations:
            return

        tokens = sum(count_tokens(_content_to_str(m.content)) for m in state.messages)
        if tokens < self.config.trigger_at_tokens:
            return

        async with self._lock:
            # Re-check cooldown after acquiring the lock.
            if state.iteration - self._last_fired < self.config.cooldown_iterations:
                return
            try:
                new_messages = await summarize_history(
                    state.messages,
                    self.provider,
                    keep_recent=self.config.keep_recent_messages,
                    target_tokens=self.config.target_tokens,
                    summary_model=self.config.summary_model,
                    model=self.model,
                )
                fresh_tokens = sum(
                    count_tokens(_content_to_str(m.content)) for m in new_messages
                )
                logger.info(
                    "auto-summarized %d messages (~%d tokens) -> %d messages (~%d tokens)",
                    len(state.messages),
                    tokens,
                    len(new_messages),
                    fresh_tokens,
                )
                state.messages[:] = new_messages
                self._last_fired = state.iteration
            except Exception:
                logger.exception(
                    "SummarizationHook failed at iteration %d; keeping original messages",
                    state.iteration,
                )

    async def _summarize(self, messages: list[Message]) -> str:
        """Call the provider to summarize *messages* and return the text."""
        transcript_lines = [f"[{m.role}] {_content_to_str(m.content)}" for m in messages]
        transcript = "\n".join(transcript_lines)
        prompt = SUMMARIZATION_PROMPT_TEMPLATE.format(
            target=self.config.target_tokens,
            transcript=transcript,
        )
        use_model = self.config.summary_model or self.model
        text = ""
        async for chunk in self.provider.stream(
            messages=[Message(role="user", content=prompt)],
            tools=[],
            model=use_model,
            system="You are a concise technical summarizer.",
        ):
            if chunk.type == "text" and chunk.delta:
                text += chunk.delta
            elif chunk.type == "stop":
                break
        return text.strip()
