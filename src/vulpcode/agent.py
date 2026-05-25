"""Agent loop: LLM <-> tools."""
from __future__ import annotations
import asyncio
import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, AsyncIterator, Union
import vulpcode.session as _session
from vulpcode.permissions import Mode, PermissionManager
from vulpcode.providers.base import Message, Provider, ProviderError, ToolCall, Usage
from vulpcode.tools.base import Tool, ToolResult

if TYPE_CHECKING:
    from vulpcode.harness.hooks import HookBus
    from vulpcode.harness.state import LoopState

logger = logging.getLogger(__name__)

_PHANTOM_COMMIT_RE = re.compile(
    r"\b(vou\s+\w+|vamos\s+\w+|deixa\s+(?:eu|que\s+eu)|let\s+me\s+\w+|"
    r"i['\']?ll\s+\w+|i\s+will\s+\w+|i['\']?m\s+going\s+to|going\s+to\s+\w+)\b",
    re.IGNORECASE,
)

_PHANTOM_NUDGES: tuple[str, ...] = (
    "REMINDER: você descreveu uma ação mas não invocou nenhuma ferramenta. "
    "Invoque a ferramenta apropriada agora, no formato exato do protocolo, "
    "sem mais prosa. (If you cannot, explain explicitly what is blocking you.)",
    "SECOND REMINDER: ainda sem tool call. Pare de descrever — EMITA o bloco "
    "<vulp:tool name=\"...\"> AGORA. Se acabou de listar arquivos com Glob/Tree "
    "e o pedido envolve buscar conteúdo, o próximo bloco é OBRIGATORIAMENTE "
    "<vulp:tool name=\"Grep\"> com o padrão de busca. Zero prosa antes ou depois.",
    "FINAL REMINDER: três tentativas consumidas. Se você não consegue emitir "
    "uma tool call agora, explique em UMA frase exatamente o que está "
    "bloqueando (falta de path, ambiguidade no pedido, etc.) — não descreva "
    "mais ações sem executá-las.",
)

_MAX_PHANTOM_NUDGES = len(_PHANTOM_NUDGES)
_PHANTOM_EXHAUSTED_ERROR = (
    f"Model emitted {_MAX_PHANTOM_NUDGES} consecutive phantom commits "
    "(described actions without invoking any tool). Turn aborted. "
    "Try refining the prompt with a concrete next step, or switch to a stronger model."
)


def _looks_like_phantom_commit(text):
    if not text or not text.strip():
        return False
    return bool(_PHANTOM_COMMIT_RE.search(text))


@dataclass
class TextEvent:
    text: str

@dataclass
class ToolStartEvent:
    tool_call: ToolCall

@dataclass
class ToolEndEvent:
    tool_call: ToolCall
    result: ToolResult

@dataclass
class ToolDeniedEvent:
    tool_call: ToolCall
    reason: str

@dataclass
class UsageEvent:
    usage: Usage

@dataclass
class TurnEndEvent:
    stop_reason: str

@dataclass
class ErrorEvent:
    error: str

Event = Union[TextEvent, ToolStartEvent, ToolEndEvent, ToolDeniedEvent, UsageEvent, TurnEndEvent, ErrorEvent]

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

# Bash
- Use the Bash tool for shell commands. Use absolute paths.
- For long-running processes, use run_in_background=True and read with BashOutput.

# Stopping
- When you finish, just stop emitting tool calls. Do not write a closing summary unless the user asked for one.
"""


async def _emit_hooks(hooks, state, **kwargs):
    results = []
    for hook in hooks:
        try:
            rv = hook(state, **kwargs)
            if asyncio.iscoroutine(rv):
                rv = await rv
            results.append(rv)
        except Exception:
            logger.exception("Hook %r raised during event; continuing", getattr(hook, "name", repr(hook)))
    return results


class Agent:
    def __init__(self, provider, tools, system=None, model="", permissions=None,
                 model_settings=None, max_iters=25, hook_bus=None):
        self.provider = provider
        self.tools: dict[str, Tool] = {t._tool_name: t for t in tools}
        self.system = system or _DEFAULT_SYSTEM_PROMPT
        self.model = model
        self.permissions = permissions or PermissionManager(config={}, mode=Mode.AUTO)
        self.model_settings: dict = dict(model_settings or {})
        self._messages: list[Message] = []
        self._session_usage: Usage = Usage()
        self._max_iters = max_iters
        self.hook_bus = hook_bus
        self._loop_state = None
        if hook_bus is not None:
            from vulpcode.harness.state import LoopState
            self._loop_state = LoopState(messages=self._messages)

    def messages(self):
        return list(self._messages)

    def reset(self):
        self._messages = []

    def _tool_schemas(self):
        return [type(t).to_schema() for t in self.tools.values()]

    async def turn(self, user_input: str) -> AsyncIterator[Event]:
        self._messages.append(Message(role="user", content=user_input))
        phantom_nudges_used = 0
        state_token = _session._current_state.set(self._loop_state)
        try:
            for _iter_idx in range(self._max_iters):
                if self.hook_bus is not None and self._loop_state is not None:
                    self._loop_state.iteration = _iter_idx
                    await _emit_hooks(self.hook_bus._hooks.get("before_iteration", []), self._loop_state)
                text_buffer = ""
                tool_calls: list[ToolCall] = []
                stop_reason = None
                try:
                    async for chunk in self.provider.stream(
                        messages=self._messages, tools=self._tool_schemas(),
                        model=self.model, system=self.system, **self.model_settings,
                    ):
                        if chunk.type == "text" and chunk.delta:
                            text_buffer += chunk.delta
                            yield TextEvent(chunk.delta)
                        elif chunk.type == "tool_call" and chunk.tool_call is not None:
                            tool_calls.append(chunk.tool_call)
                        elif chunk.type == "usage" and chunk.usage is not None:
                            self._session_usage.input_tokens += chunk.usage.input_tokens
                            self._session_usage.output_tokens += chunk.usage.output_tokens
                            self._session_usage.cache_read_tokens += chunk.usage.cache_read_tokens
                            self._session_usage.cache_creation_tokens += chunk.usage.cache_creation_tokens
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
                self._messages.append(Message(role="assistant", content=text_buffer, tool_calls=tool_calls or None))
                if not tool_calls:
                    if phantom_nudges_used < _MAX_PHANTOM_NUDGES and _looks_like_phantom_commit(text_buffer):
                        self._messages.append(Message(role="user", content=_PHANTOM_NUDGES[phantom_nudges_used]))
                        phantom_nudges_used += 1
                        continue
                    if phantom_nudges_used == _MAX_PHANTOM_NUDGES and _looks_like_phantom_commit(text_buffer):
                        yield ErrorEvent(_PHANTOM_EXHAUSTED_ERROR)
                        return
                    yield TurnEndEvent(stop_reason or "end_turn")
                    return
                for tc in tool_calls:
                    tool_obj = self.tools.get(tc.name)
                    if tool_obj is None:
                        self._messages.append(Message(role="tool", tool_call_id=tc.id, name=tc.name, content=f"Unknown tool: {tc.name}"))
                        yield ErrorEvent(f"Unknown tool: {tc.name}")
                        continue
                    if self.hook_bus is not None and self._loop_state is not None:
                        hook_returns = await _emit_hooks(self.hook_bus._hooks.get("before_tool_call", []), self._loop_state, call=tc)
                        blocked = False
                        pre_result = None
                        patched_tc = tc
                        for rv in hook_returns:
                            if rv is False:
                                blocked = True
                                break
                            if isinstance(rv, ToolResult):
                                pre_result = rv
                                blocked = True
                                break
                            if isinstance(rv, ToolCall):
                                patched_tc = rv
                                break
                        if blocked:
                            if pre_result is not None:
                                content_str = pre_result.to_string()
                            else:
                                block_msg = self._loop_state.metadata.get("last_block_message") or f"Tool {tc.name} blocked by hook"
                                content_str = f"blocked: {block_msg}"
                            self._messages.append(Message(role="tool", tool_call_id=tc.id, name=tc.name, content=content_str))
                            continue
                        tc = patched_tc
                    tool_cls = type(tool_obj)
                    decision = await self.permissions.check(tc, tool_cls)
                    if not decision.allow:
                        yield ToolDeniedEvent(tc, decision.reason)
                        self._messages.append(Message(role="tool", tool_call_id=tc.id, name=tc.name, content=f"Cancelled: {decision.reason}"))
                        continue
                    yield ToolStartEvent(tc)
                    try:
                        args = tool_cls.parse_args(tc.arguments or {})
                        result = await tool_obj.run(args)
                    except Exception as exc:
                        result = ToolResult(error=f"{type(exc).__name__}: {exc}", is_error=True)
                    if self.hook_bus is not None and self._loop_state is not None:
                        after_returns = await _emit_hooks(self.hook_bus._hooks.get("after_tool_call", []), self._loop_state, call=tc, result=result)
                        for rv in after_returns:
                            if isinstance(rv, ToolResult):
                                result = rv
                                break
                    yield ToolEndEvent(tc, result)
                    self._messages.append(Message(role="tool", tool_call_id=tc.id, name=tc.name, content=result.to_string()))
            yield ErrorEvent(f"Max iterations ({self._max_iters}) reached")
        finally:
            _session._current_state.reset(state_token)

    async def run_to_completion(self, user_input: str) -> str:
        final_text = ""
        async for ev in self.turn(user_input):
            if isinstance(ev, TextEvent):
                final_text += ev.text
            elif isinstance(ev, ErrorEvent):
                break
        return final_text
