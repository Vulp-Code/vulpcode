"""Agent loop: LLM <-> tools."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import AsyncIterator, Union

from vulpcode.permissions import Mode, PermissionManager
from vulpcode.providers.base import (
    Message,
    Provider,
    ProviderError,
    ToolCall,
    Usage,
)
from vulpcode.tools.base import Tool, ToolResult


_PHANTOM_COMMIT_RE = re.compile(
    r"\b("
    r"vou\s+\w+|"
    r"vamos\s+\w+|"
    r"deixa\s+(?:eu|que\s+eu)|"
    r"let\s+me\s+\w+|"
    r"i['’]?ll\s+\w+|"
    r"i\s+will\s+\w+|"
    r"i['’]?m\s+going\s+to|"
    r"going\s+to\s+\w+"
    r")\b",
    re.IGNORECASE,
)

_PHANTOM_NUDGES: tuple[str, ...] = (
    # Attempt 1 — polite.
    "REMINDER: você descreveu uma ação mas não invocou nenhuma ferramenta. "
    "Invoque a ferramenta apropriada agora, no formato exato do protocolo, "
    "sem mais prosa. (If you cannot, explain explicitly what is blocking you.)",
    # Attempt 2 — firmer + concrete hint about the most likely next tool.
    "SECOND REMINDER: ainda sem tool call. Pare de descrever — EMITA o bloco "
    "<vulp:tool name=\"...\"> AGORA. Se acabou de listar arquivos com Glob/Tree "
    "e o pedido envolve buscar conteúdo, o próximo bloco é OBRIGATORIAMENTE "
    "<vulp:tool name=\"Grep\"> com o padrão de busca. Zero prosa antes ou depois.",
    # Attempt 3 — last call.
    "FINAL REMINDER: três tentativas consumidas. Se você não consegue emitir "
    "uma tool call agora, explique em UMA frase exatamente o que está "
    "bloqueando (falta de path, ambiguidade no pedido, etc.) — não descreva "
    "mais ações sem executá-las.",
)

_MAX_PHANTOM_NUDGES = len(_PHANTOM_NUDGES)

_PHANTOM_EXHAUSTED_ERROR = (
    f"Model emitted {_MAX_PHANTOM_NUDGES} consecutive phantom commits "
    "(described actions without invoking any tool). Turn aborted. "
    "Try refining the prompt with a concrete next step, or switch to a "
    "stronger model."
)


def _looks_like_phantom_commit(text: str) -> bool:
    """Heuristic: assistant text promises an action but no tool was called.

    Used to nudge the model when its turn ends with "I'll read X" / "vou ler X"
    style prose and no tool call — common with weaker models on the agentic
    text-protocol provider.
    """
    if not text or not text.strip():
        return False
    return bool(_PHANTOM_COMMIT_RE.search(text))


@dataclass
class TextEvent:
    """A chunk of assistant text streamed from the model.

    Attributes:
        text: The delta text fragment. Concatenate consecutive ``TextEvent``s
            within a turn to reconstruct the full assistant message.
    """

    text: str


@dataclass
class ToolStartEvent:
    """Emitted right before a tool is invoked (after permission was granted).

    Attributes:
        tool_call: The :class:`~vulpcode.providers.base.ToolCall` issued by the
            model, including ``name`` and ``arguments``.
    """

    tool_call: ToolCall


@dataclass
class ToolEndEvent:
    """Emitted after a tool finishes (successfully or with a captured error).

    Attributes:
        tool_call: The original :class:`~vulpcode.providers.base.ToolCall`.
        result: The :class:`~vulpcode.tools.base.ToolResult`. Inspect
            ``result.is_error`` to detect failures.
    """

    tool_call: ToolCall
    result: ToolResult


@dataclass
class ToolDeniedEvent:
    """Emitted when the permission system blocks a tool call.

    The model is informed that the call was cancelled and may try a different
    approach on the next iteration.

    Attributes:
        tool_call: The :class:`~vulpcode.providers.base.ToolCall` that was denied.
        reason: Human-readable explanation (e.g. ``"plan mode (no execution)"``,
            ``"user rejected"``).
    """

    tool_call: ToolCall
    reason: str


@dataclass
class UsageEvent:
    """Token-accounting snapshot reported by the provider for a single response.

    The :class:`Agent` also accumulates these into ``self._session_usage`` so
    callers can read a running total.

    Attributes:
        usage: A :class:`~vulpcode.providers.base.Usage` with input/output and
            cache token counts for this provider response.
    """

    usage: Usage


@dataclass
class TurnEndEvent:
    """Emitted exactly once when the assistant finishes a turn without further tools.

    Attributes:
        stop_reason: Provider-reported stop reason
            (e.g. ``"end_turn"``, ``"max_tokens"``, ``"stop_sequence"``).
    """

    stop_reason: str


@dataclass
class ErrorEvent:
    """Emitted when the agent loop cannot continue.

    Sources include provider failures, unknown tool names, and the safety
    cap on iterations. After an :class:`ErrorEvent` the turn aborts.

    Attributes:
        error: Human-readable error message.
    """

    error: str


Event = Union[
    TextEvent,
    ToolStartEvent,
    ToolEndEvent,
    ToolDeniedEvent,
    UsageEvent,
    TurnEndEvent,
    ErrorEvent,
]
"""Union of every event type yielded by :meth:`Agent.turn`."""


_DEFAULT_SYSTEM_PROMPT = """\
You are Vulpcode, a terminal coding agent. You can read files, run shell commands,
edit code, search the web, and delegate to subagents.

# Style
- Be concise. Prefer concrete actions over long explanations.
- Answer the user's question directly without preamble or summary unless asked.

# File creation and editing — CRITICAL
- ALWAYS use the Write tool to create files. NEVER paste file contents as inline text in your response.
- ALWAYS use absolute paths (e.g. /home/user/project/file.py), never relative paths.
- For modifications, use Edit (single replacement) or MultiEdit (atomic batch).
- For files larger than ~500 lines: write a skeleton with Write first, then fill sections with sequential Edit/MultiEdit calls. Do NOT try to emit the whole file inline — you will hit the token limit.
- The user is in a terminal. They will SEE the file you wrote on disk; they do not need a copy in your text response.

# Bash
- Use the Bash tool for shell commands. Use absolute paths.
- For long-running processes, use run_in_background=True and read with BashOutput.

# Tool selection
- Read for one file. Glob for finding files by name. Grep for searching contents.
- Use Task (subagent) for parallelizable independent searches that would otherwise pollute context.
- Use TodoWrite at the start of multi-step tasks (3+ steps) and update status as you go.

# Stopping
- When you finish, just stop emitting tool calls. Do not write a closing summary unless the user asked for one.
"""


class Agent:
    """Orchestrates the LLM <-> tools loop and emits events for the UI.

    The agent keeps the running conversation, asks the
    :class:`~vulpcode.providers.base.Provider` to stream a response, dispatches
    every requested tool through the :class:`~vulpcode.permissions.PermissionManager`,
    feeds the tool results back to the model, and yields one :data:`Event` per
    interesting moment so any UI (REPL, web, tests) can render progress.

    Args:
        provider: A concrete :class:`~vulpcode.providers.base.Provider` (build
            it with :func:`~vulpcode.providers.registry.build_provider`).
        tools: Instances of :class:`~vulpcode.tools.base.Tool` available to the
            model. The agent indexes them by ``_tool_name``.
        system: Optional system prompt. When ``None`` the bundled default
            (``_DEFAULT_SYSTEM_PROMPT``) is used.
        model: Model identifier passed to the provider on every call
            (e.g. ``"claude-sonnet-4-6"``).
        permissions: A :class:`~vulpcode.permissions.PermissionManager`. When
            ``None`` an ``AUTO``-mode manager is created (everything allowed).
        model_settings: Extra keyword arguments forwarded verbatim to
            ``provider.stream`` (e.g. ``{"temperature": 0.2}``).

    Attributes:
        _max_iters: Safety cap on tool-loop iterations per :meth:`turn`
            (default ``25``). When reached the turn yields an :class:`ErrorEvent`
            and stops, preventing runaway tool-calling loops.

    Example:
        ```python
        agent = Agent(
            provider=build_provider("anthropic", {"api_key": "sk-ant-..."}),
            tools=[cls() for cls in list_tools()],
            model="claude-sonnet-4-6",
        )
        async for ev in agent.turn("list files in /tmp"):
            ...
        ```
    """

    def __init__(
        self,
        provider: Provider,
        tools: list[Tool],
        system: str | None = None,
        model: str = "",
        permissions: PermissionManager | None = None,
        model_settings: dict | None = None,
        max_iters: int = 25,
    ) -> None:
        self.provider = provider
        self.tools: dict[str, Tool] = {t._tool_name: t for t in tools}
        self.system = system or _DEFAULT_SYSTEM_PROMPT
        self.model = model
        self.permissions = permissions or PermissionManager(config={}, mode=Mode.AUTO)
        self.model_settings: dict = dict(model_settings or {})
        self._messages: list[Message] = []
        self._session_usage: Usage = Usage()
        self._max_iters = max_iters

    def messages(self) -> list[Message]:
        """Return a shallow copy of the running conversation transcript."""
        return list(self._messages)

    def reset(self) -> None:
        """Clear the conversation history. Tools, permissions and provider stay."""
        self._messages = []

    def _tool_schemas(self) -> list[dict]:
        return [type(t).to_schema() for t in self.tools.values()]

    async def turn(self, user_input: str) -> AsyncIterator[Event]:
        """Run one user turn and stream every event back to the caller.

        This is an ``async`` generator. It appends ``user_input`` to the
        transcript, then loops: stream model output -> if the model asked for
        tools, run the permitted ones and append their results -> repeat. The
        loop ends when the model stops requesting tools, when an error occurs,
        or when ``self._max_iters`` is reached.

        The events yielded form a sequence the UI can consume:

        - :class:`TextEvent` — assistant text deltas (concatenate to render).
        - :class:`UsageEvent` — token accounting from the provider, also
          accumulated into ``self._session_usage``.
        - :class:`ToolStartEvent` — a permitted tool is about to execute.
        - :class:`ToolEndEvent` — that tool finished; check ``result.is_error``.
        - :class:`ToolDeniedEvent` — permission system blocked the call; the
          model is told it was cancelled and may retry differently.
        - :class:`TurnEndEvent` — terminal: the assistant finished without
          requesting more tools (``stop_reason`` carries why).
        - :class:`ErrorEvent` — terminal: provider failure, unknown tool name,
          or hit ``_max_iters``.

        After a :class:`TurnEndEvent` or :class:`ErrorEvent` the generator
        returns; call :meth:`turn` again to continue the conversation.

        Args:
            user_input: The user message to append to the transcript and act on.

        Yields:
            One :data:`Event` at a time, in causal order.
        """
        self._messages.append(Message(role="user", content=user_input))
        phantom_nudges_used = 0
        for _ in range(self._max_iters):
            text_buffer = ""
            tool_calls: list[ToolCall] = []
            stop_reason: str | None = None
            try:
                async for chunk in self.provider.stream(
                    messages=self._messages,
                    tools=self._tool_schemas(),
                    model=self.model,
                    system=self.system,
                    **self.model_settings,
                ):
                    if chunk.type == "text" and chunk.delta:
                        text_buffer += chunk.delta
                        yield TextEvent(chunk.delta)
                    elif chunk.type == "tool_call" and chunk.tool_call is not None:
                        tool_calls.append(chunk.tool_call)
                    elif chunk.type == "usage" and chunk.usage is not None:
                        self._session_usage.input_tokens += chunk.usage.input_tokens
                        self._session_usage.output_tokens += chunk.usage.output_tokens
                        self._session_usage.cache_read_tokens += (
                            chunk.usage.cache_read_tokens
                        )
                        self._session_usage.cache_creation_tokens += (
                            chunk.usage.cache_creation_tokens
                        )
                        yield UsageEvent(chunk.usage)
                    elif chunk.type == "stop":
                        stop_reason = chunk.stop_reason
                        break
                    elif chunk.type == "error":
                        yield ErrorEvent(chunk.error or "unknown stream error")
                        return
            except ProviderError as exc:
                yield ErrorEvent(str(exc))
                return

            self._messages.append(
                Message(
                    role="assistant",
                    content=text_buffer,
                    tool_calls=tool_calls or None,
                )
            )

            if not tool_calls:
                if (
                    phantom_nudges_used < _MAX_PHANTOM_NUDGES
                    and _looks_like_phantom_commit(text_buffer)
                ):
                    self._messages.append(
                        Message(
                            role="user",
                            content=_PHANTOM_NUDGES[phantom_nudges_used],
                        )
                    )
                    phantom_nudges_used += 1
                    continue
                if (
                    phantom_nudges_used == _MAX_PHANTOM_NUDGES
                    and _looks_like_phantom_commit(text_buffer)
                ):
                    yield ErrorEvent(_PHANTOM_EXHAUSTED_ERROR)
                    return
                yield TurnEndEvent(stop_reason or "end_turn")
                return

            for tc in tool_calls:
                tool_obj = self.tools.get(tc.name)
                if tool_obj is None:
                    self._messages.append(
                        Message(
                            role="tool",
                            tool_call_id=tc.id,
                            name=tc.name,
                            content=f"Unknown tool: {tc.name}",
                        )
                    )
                    yield ErrorEvent(f"Unknown tool: {tc.name}")
                    continue

                tool_cls = type(tool_obj)
                decision = await self.permissions.check(tc, tool_cls)
                if not decision.allow:
                    yield ToolDeniedEvent(tc, decision.reason)
                    self._messages.append(
                        Message(
                            role="tool",
                            tool_call_id=tc.id,
                            name=tc.name,
                            content=f"Cancelled: {decision.reason}",
                        )
                    )
                    continue

                yield ToolStartEvent(tc)
                try:
                    args = tool_cls.parse_args(tc.arguments or {})
                    result = await tool_obj.run(args)
                except Exception as exc:
                    result = ToolResult(
                        error=f"{type(exc).__name__}: {exc}", is_error=True
                    )
                yield ToolEndEvent(tc, result)
                self._messages.append(
                    Message(
                        role="tool",
                        tool_call_id=tc.id,
                        name=tc.name,
                        content=result.to_string(),
                    )
                )

        yield ErrorEvent(f"Max iterations ({self._max_iters}) reached")

    async def run_to_completion(self, user_input: str) -> str:
        """Drive a full turn and return only the concatenated assistant text.

        Convenience wrapper around :meth:`turn` for non-streaming callers
        (scripts, tests, batch jobs). All non-text events are silently
        consumed; if an :class:`ErrorEvent` is encountered the loop stops
        early and the partial text gathered so far is returned.

        Args:
            user_input: The user message for this turn.

        Returns:
            The full assistant text response (possibly empty).
        """
        final_text = ""
        async for ev in self.turn(user_input):
            if isinstance(ev, TextEvent):
                final_text += ev.text
            elif isinstance(ev, ErrorEvent):
                break
        return final_text
