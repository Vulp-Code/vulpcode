# Tarefa 08.01 - Agent Loop

**Status**: PENDENTE
**Fase**: 08 - Agent Loop
**Dependencias**: 02.01, 02.02, 03.05, 04 (todas), 05 (todas), 06 (todas), 07 (config + permissoes)
**Bloqueia**: FASE 09 (UI), FASE 06.03 (Task usa Agent.run_to_completion)

---

## Objetivo

Implementar `src/vulpcode/agent.py` com a classe `Agent` que orquestra o loop
LLM <-> tools, aplica permissoes, emite eventos para a UI consumir, e expoe
`run_to_completion(prompt)` para uso em modo headless e em sub-agentes.

---

## Descricao Tecnica

### API publica

```python
class Agent:
    def __init__(
        self,
        provider: Provider,
        tools: list[Tool],
        system: str,
        model: str,
        permissions: PermissionManager | None = None,
    ): ...

    async def turn(self, user_input: str) -> AsyncIterator[Event]: ...
    async def run_to_completion(self, user_input: str) -> str: ...
    def messages(self) -> list[Message]: ...
    def reset(self) -> None: ...
```

### Eventos emitidos

```python
@dataclass
class TextEvent: text: str
@dataclass
class ToolStartEvent: tool_call: ToolCall
@dataclass
class ToolEndEvent: tool_call: ToolCall; result: ToolResult
@dataclass
class ToolDeniedEvent: tool_call: ToolCall; reason: str
@dataclass
class UsageEvent: usage: Usage
@dataclass
class TurnEndEvent: stop_reason: str
@dataclass
class ErrorEvent: error: str

Event = Union[TextEvent, ToolStartEvent, ToolEndEvent, ToolDeniedEvent, UsageEvent, TurnEndEvent, ErrorEvent]
```

### Fluxo do `turn()`

1. Append `Message(role="user", content=user_input)` em `self._messages`.
2. Loop externo (ate stop sem tool calls):
   a. Chama `provider.stream(messages, tool_schemas, model, system)`.
   b. Para cada `StreamChunk`:
      - `text` -> emite `TextEvent`, append em buffer.
      - `tool_call` -> coleta em lista local.
      - `usage` -> emite `UsageEvent`.
      - `stop` -> sai do loop interno.
   c. Append `Message(role="assistant", content=text_buffer, tool_calls=tool_calls)`.
   d. Se sem tool_calls -> emite `TurnEndEvent("end_turn")` e retorna.
   e. Para cada tool_call:
      - `permissions.check(tool_call, tool_cls)`.
      - Se rejeitado -> emite `ToolDeniedEvent`, append `Message(role="tool", content="<rejected>")`.
      - Se aprovado -> emite `ToolStartEvent`, executa, emite `ToolEndEvent`,
        append `Message(role="tool", tool_call_id=..., name=..., content=result.to_string())`.
   f. Volta ao topo do loop externo.

### Fluxo do `run_to_completion()`

Consome todos os eventos do `turn()`, agrega texto e devolve.

### Estrutura

**`src/vulpcode/agent.py`**:

```python
"""Agent loop: LLM <-> tools."""
from __future__ import annotations

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


Event = Union[
    TextEvent,
    ToolStartEvent,
    ToolEndEvent,
    ToolDeniedEvent,
    UsageEvent,
    TurnEndEvent,
    ErrorEvent,
]


_DEFAULT_SYSTEM_PROMPT = (
    "You are Vulpcode, a terminal coding agent. You can read files, run shell "
    "commands, edit code, search the web, and delegate to subagents. Be concise. "
    "Prefer concrete actions over long explanations. When you finish a task, "
    "stop emitting tool calls and the conversation ends."
)


class Agent:
    def __init__(
        self,
        provider: Provider,
        tools: list[Tool],
        system: str | None = None,
        model: str = "",
        permissions: PermissionManager | None = None,
    ) -> None:
        self.provider = provider
        self.tools = {t._tool_name: t for t in tools}
        self.system = system or _DEFAULT_SYSTEM_PROMPT
        self.model = model
        self.permissions = permissions or PermissionManager(config={}, mode=Mode.AUTO)
        self._messages: list[Message] = []
        self._max_iters = 25  # safety bound for tool loops

    def messages(self) -> list[Message]:
        return list(self._messages)

    def reset(self) -> None:
        self._messages = []

    def _tool_schemas(self) -> list[dict]:
        return [type(t).to_schema() for t in self.tools.values()]

    async def turn(self, user_input: str) -> AsyncIterator[Event]:
        self._messages.append(Message(role="user", content=user_input))
        for _ in range(self._max_iters):
            text_buffer = ""
            tool_calls: list[ToolCall] = []
            try:
                async for chunk in self.provider.stream(
                    messages=self._messages,
                    tools=self._tool_schemas(),
                    model=self.model,
                    system=self.system,
                ):
                    if chunk.type == "text" and chunk.delta:
                        text_buffer += chunk.delta
                        yield TextEvent(chunk.delta)
                    elif chunk.type == "tool_call" and chunk.tool_call is not None:
                        tool_calls.append(chunk.tool_call)
                    elif chunk.type == "usage" and chunk.usage is not None:
                        yield UsageEvent(chunk.usage)
                    elif chunk.type == "stop":
                        break
                    elif chunk.type == "error":
                        yield ErrorEvent(chunk.error or "unknown stream error")
                        return
            except ProviderError as exc:
                yield ErrorEvent(str(exc))
                return

            self._messages.append(Message(
                role="assistant",
                content=text_buffer,
                tool_calls=tool_calls or None,
            ))

            if not tool_calls:
                yield TurnEndEvent("end_turn")
                return

            for tc in tool_calls:
                tool_obj = self.tools.get(tc.name)
                if tool_obj is None:
                    self._messages.append(Message(
                        role="tool",
                        tool_call_id=tc.id,
                        name=tc.name,
                        content=f"Unknown tool: {tc.name}",
                    ))
                    yield ErrorEvent(f"Unknown tool: {tc.name}")
                    continue

                tool_cls = type(tool_obj)
                decision = await self.permissions.check(tc, tool_cls)
                if not decision.allow:
                    yield ToolDeniedEvent(tc, decision.reason)
                    self._messages.append(Message(
                        role="tool",
                        tool_call_id=tc.id,
                        name=tc.name,
                        content=f"Cancelled: {decision.reason}",
                    ))
                    continue

                yield ToolStartEvent(tc)
                try:
                    args = tool_cls.parse_args(tc.arguments or {})
                    result = await tool_obj.run(args)
                except Exception as exc:
                    result = ToolResult(error=f"{type(exc).__name__}: {exc}", is_error=True)
                yield ToolEndEvent(tc, result)
                self._messages.append(Message(
                    role="tool",
                    tool_call_id=tc.id,
                    name=tc.name,
                    content=result.to_string(),
                ))
        # If we exit the loop, hit max_iters
        yield ErrorEvent(f"Max iterations ({self._max_iters}) reached")

    async def run_to_completion(self, user_input: str) -> str:
        final_text = ""
        async for ev in self.turn(user_input):
            if isinstance(ev, TextEvent):
                final_text += ev.text
            elif isinstance(ev, ErrorEvent):
                # Stop on error but keep accumulated text
                break
        return final_text
```

---

## INSTRUCAO CRITICA

- O `Agent` mantem `_messages` mutavel — chamadas sucessivas a `turn()` continuam
  a conversa. `reset()` limpa.
- `_max_iters = 25` previne loops infinitos de tool calls.
- `PermissionManager` injetado, default e `Mode.AUTO` para uso programatico
  (testes, sub-agentes). Em CLI normal, sera substituido com modo correto.
- `Message(role="tool", name=tc.name, ...)` — o `name` e necessario para o
  GeminiProvider (que correlaciona pelo nome, nao por id). Outros providers
  ignoram o `name`.
- `tool_call_id` SEMPRE preenchido nas mensagens role="tool" (mesmo para
  Gemini, onde nao e usado, isso simplifica logica).
- Erros de tool sao capturados e enviados como `ToolEndEvent` com
  `result.is_error=True`. O LLM ve o erro como conteudo de resposta.
- Quando o provider retorna `error` chunk, abortamos o turno.

---

## Etapas de Implementacao

### Etapa 1: Criar `agent.py`

### Etapa 2: Voltar a `tools/task.py` (FASE 06.03) e remover qualquer TODO de stub

Agora `Agent.run_to_completion` existe, entao `TaskTool.run()` pode chamar de
verdade.

### Etapa 3: Criar `tests/test_agent.py` com Provider mock

```python
from typing import AsyncIterator

import pytest
from pydantic import BaseModel

from vulpcode.agent import (
    Agent,
    ErrorEvent,
    TextEvent,
    ToolEndEvent,
    ToolStartEvent,
    TurnEndEvent,
)
from vulpcode.providers.base import (
    Message,
    Provider,
    StreamChunk,
    ToolCall,
)
from vulpcode.tools import Tool, ToolResult, clear_registry, tool


class MockProvider(Provider):
    name = "mock"

    def __init__(self, scripted_chunks: list[list[StreamChunk]]):
        super().__init__()
        self.scripted = list(scripted_chunks)

    async def stream(
        self, messages, tools, model, system=None, **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        if not self.scripted:
            yield StreamChunk(type="stop")
            return
        for ch in self.scripted.pop(0):
            yield ch

    def supports_tools(self): return True
    def supports_vision(self): return False


@pytest.fixture
def echo_tool():
    clear_registry()
    @tool(name="Echo", description="echo")
    class T(Tool):
        class Input(BaseModel):
            text: str
        async def run(self, args):
            return ToolResult(output=f"echoed: {args.text}")
    yield T
    clear_registry()


@pytest.mark.asyncio
async def test_simple_turn_no_tools():
    p = MockProvider([[
        StreamChunk(type="text", delta="hello "),
        StreamChunk(type="text", delta="world"),
        StreamChunk(type="stop"),
    ]])
    a = Agent(provider=p, tools=[], system="s")
    events = []
    async for ev in a.turn("hi"):
        events.append(ev)
    text = "".join(e.text for e in events if isinstance(e, TextEvent))
    assert text == "hello world"
    assert any(isinstance(e, TurnEndEvent) for e in events)


@pytest.mark.asyncio
async def test_tool_call_loop(echo_tool):
    tc = ToolCall(id="t1", name="Echo", arguments={"text": "hi"})
    p = MockProvider([
        [
            StreamChunk(type="tool_call", tool_call=tc),
            StreamChunk(type="stop"),
        ],
        [
            StreamChunk(type="text", delta="done"),
            StreamChunk(type="stop"),
        ],
    ])
    a = Agent(provider=p, tools=[echo_tool()], system="s")
    events = []
    async for ev in a.turn("go"):
        events.append(ev)
    starts = [e for e in events if isinstance(e, ToolStartEvent)]
    ends = [e for e in events if isinstance(e, ToolEndEvent)]
    assert len(starts) == 1 and len(ends) == 1
    assert "echoed: hi" in ends[0].result.output


@pytest.mark.asyncio
async def test_run_to_completion_returns_text():
    p = MockProvider([[
        StreamChunk(type="text", delta="answer"),
        StreamChunk(type="stop"),
    ]])
    a = Agent(provider=p, tools=[], system="s")
    out = await a.run_to_completion("?")
    assert out == "answer"


@pytest.mark.asyncio
async def test_unknown_tool_yields_error():
    bad = ToolCall(id="x", name="DoesNotExist", arguments={})
    p = MockProvider([[
        StreamChunk(type="tool_call", tool_call=bad),
        StreamChunk(type="stop"),
    ], [
        StreamChunk(type="text", delta="recovered"),
        StreamChunk(type="stop"),
    ]])
    a = Agent(provider=p, tools=[], system="s")
    events = []
    async for ev in a.turn("?"):
        events.append(ev)
    assert any(isinstance(e, ErrorEvent) for e in events)


@pytest.mark.asyncio
async def test_max_iters_safety():
    tc = ToolCall(id="t1", name="Echo", arguments={"text": "x"})

    @tool(name="EchoLoop", description="echo")
    class T(Tool):
        class Input(BaseModel):
            text: str
        async def run(self, args):
            return ToolResult(output="x")

    # Never stops emitting tool_call
    chunks = [[StreamChunk(type="tool_call", tool_call=ToolCall(id=f"{i}", name="EchoLoop", arguments={"text": "x"})),
               StreamChunk(type="stop")] for i in range(50)]
    p = MockProvider(chunks)
    a = Agent(provider=p, tools=[T()], system="s")
    events = []
    async for ev in a.turn("loop"):
        events.append(ev)
    assert any(isinstance(e, ErrorEvent) and "Max iterations" in e.error for e in events)
    clear_registry()
```

### Etapa 4: Rodar testes

```bash
pytest tests/test_agent.py -v
```

---

## Criterios de Aceite

- [x] `src/vulpcode/agent.py` implementa classe `Agent` e dataclasses de eventos
- [x] `turn()` consome streams do provider e executa tools com permission check
- [x] Adiciona `Message(role="tool", name=..., tool_call_id=..., content=...)` ao historico
- [x] Mensagens incluem `name` para compatibilidade com Gemini
- [x] `run_to_completion(prompt)` retorna string final
- [x] `_max_iters` (25) protege contra loops infinitos
- [x] `messages()` e `reset()` para inspecao/limpeza
- [x] `_DEFAULT_SYSTEM_PROMPT` definido
- [x] Eventos: `TextEvent`, `ToolStartEvent`, `ToolEndEvent`, `ToolDeniedEvent`, `UsageEvent`, `TurnEndEvent`, `ErrorEvent`
- [x] `tests/test_agent.py` com >=5 testes (Provider mock), todos passando
- [x] Verificar que `tools/task.py` (FASE 06.03) agora funciona end-to-end com o Agent (rodar `pytest tests/test_tools/test_task.py` e ver que nao falha em ImportError; pode ainda nao testar exec real sem provider configurado)

---

## Riscos Tecnicos

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|---------------|---------|-----------|
| Loop infinito de tool calls | Media | Alto | _max_iters guard |
| Permissions chamadas em paralelo | Baixa | Medio | Tools serializadas dentro de turn() |
| Provider stream nao emite stop | Baixa | Medio | break interno; max_iters cobre depois |
| Unknown tool gera tool_call_id duplicado | Baixa | Baixo | Aceitar; mensagem informa |

---

**End of Specification**
