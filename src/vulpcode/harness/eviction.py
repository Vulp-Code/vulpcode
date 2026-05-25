"""Message eviction and overflow-clip middleware.

Eviction (oldest_pair strategy):
    Removes the oldest assistant+tool_result pair when message count or estimated
    token count exceeds configured thresholds.

Overflow clip:
    Truncates ToolResult.output that exceeds a character limit, inserting an
    informative header so the model knows data was omitted.

Both are opt-in via config — see ``register_default_middleware`` in
``harness/__init__.py``.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Literal

from vulpcode.harness._tokens import count_tokens
from vulpcode.harness.state import LoopState
from vulpcode.providers.base import Message
from vulpcode.tools.base import ToolResult

logger = logging.getLogger("vulpcode.harness.eviction")


@dataclass
class EvictionConfig:
    """Configuration for message eviction.

    Fields:
        enabled: Activate eviction middleware.
        max_messages: Evict pairs when message count exceeds this.
        max_tokens: Evict pairs when estimated token count exceeds this. When
            ``None`` only ``max_messages`` is checked.
        keep_recent: Never evict the last N messages from the conversation.
        keep_first_system: Preserve leading ``role="system"`` messages.
        drop_strategy: Eviction strategy. Only ``"oldest_pair"`` is implemented;
            ``"summary_then_drop"`` is reserved for FASE_03.
    """

    enabled: bool = False
    max_messages: int = 200
    max_tokens: int | None = None
    keep_recent: int = 20
    keep_first_system: bool = True
    drop_strategy: Literal["oldest_pair", "summary_then_drop"] = "oldest_pair"


@dataclass
class OverflowClipConfig:
    """Configuration for tool-output overflow clipping.

    Fields:
        enabled: Activate clip middleware.
        max_tool_output_chars: Clip ``ToolResult.output`` longer than this.
        head_chars: Characters to keep from the start of the output.
        tail_chars: Characters to keep from the end of the output.
    """

    enabled: bool = False
    max_tool_output_chars: int = 8000
    head_chars: int = 4000
    tail_chars: int = 1000


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _msg_text(m: Message) -> str:
    """Extract a plain-text representation of a message for token counting."""
    if isinstance(m.content, str):
        return m.content
    if isinstance(m.content, list):
        parts: list[str] = []
        for block in m.content:
            if isinstance(block, dict):
                text = block.get("text", "")
                if text:
                    parts.append(text)
        return " ".join(parts)
    return ""


def _leading_system_count(msgs: list[Message]) -> int:
    """Return the number of consecutive ``role="system"`` messages at the start."""
    count = 0
    for m in msgs:
        if m.role == "system":
            count += 1
        else:
            break
    return count


def _total_tokens(msgs: list[Message]) -> int:
    return sum(count_tokens(_msg_text(m)) for m in msgs)


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


def evict_messages(state: LoopState, config: EvictionConfig) -> None:
    """Evict old assistant+tool_result pairs from *state.messages* in-place.

    This is a ``before_iteration`` hook handler. It mutates ``state.messages``
    directly when the message count or estimated token count exceeds the
    configured limits.

    When ``config.drop_strategy == "summary_then_drop"`` the function falls
    back to ``"oldest_pair"`` — summarisation is reserved for FASE_03.

    Args:
        state: Current loop state. ``state.messages`` is modified in-place.
        config: Eviction configuration.
    """
    if not config.enabled:
        return

    msgs = state.messages

    while True:
        n = len(msgs)
        over_count = n > config.max_messages
        over_tokens = (
            config.max_tokens is not None and _total_tokens(msgs) > config.max_tokens
        )

        if not over_count and not over_tokens:
            break

        # Protected range: leading system messages + last keep_recent messages.
        system_end = _leading_system_count(msgs) if config.keep_first_system else 0
        # Index of the first message in the protected tail.
        protected_tail_start = max(system_end, n - config.keep_recent)

        # Find the oldest evictable assistant+tool pair outside the protected window.
        evicted = False
        i = system_end
        while i < protected_tail_start:
            m = msgs[i]
            if m.role == "assistant" and m.tool_calls:
                # Collect consecutive tool-result messages following this assistant msg.
                j = i + 1
                while j < protected_tail_start and msgs[j].role == "tool":
                    j += 1
                # Estimate tokens reclaimed.
                pair_tokens = sum(count_tokens(_msg_text(msgs[k])) for k in range(i, j))
                logger.info(
                    "evicted assistant+tool_result pair at index=%d (~%d tokens reclaimed)",
                    i,
                    pair_tokens,
                )
                del msgs[i:j]
                evicted = True
                break
            i += 1

        if not evicted:
            # No more evictable pairs — stop to avoid an infinite loop.
            break


# ---------------------------------------------------------------------------
# Overflow clip
# ---------------------------------------------------------------------------


def clip_tool_output(
    state: LoopState,
    *,
    call: Any,
    result: ToolResult,
    config: OverflowClipConfig,
) -> ToolResult:
    """Clip ``result.output`` when it exceeds ``config.max_tool_output_chars``.

    Returns the original *result* unchanged when the output is within the
    limit, or a new :class:`~vulpcode.tools.base.ToolResult` with the clipped
    content when it is not.

    The clip marker has the exact form::

        [clipped N chars — total was T, showing first H and last L]

    where N = T - H - L, T = total characters, H = head_chars, L = tail_chars.

    Args:
        state: Current loop state (unused; present for hook protocol consistency).
        call: The tool call that produced this result (unused here; present for
            hook protocol consistency).
        result: The original tool result.
        config: Clip configuration.

    Returns:
        Original or clipped :class:`~vulpcode.tools.base.ToolResult`.
    """
    text = result.output
    total = len(text)
    if total <= config.max_tool_output_chars:
        return result

    head = text[: config.head_chars]
    tail = text[total - config.tail_chars :]
    clipped = total - config.head_chars - config.tail_chars
    marker = (
        f"[clipped {clipped} chars — total was {total},"
        f" showing first {config.head_chars} and last {config.tail_chars}]"
    )
    new_output = head + marker + tail
    return ToolResult(
        output=new_output,
        error=result.error,
        is_error=result.is_error,
        metadata=result.metadata,
    )
