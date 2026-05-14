# Tarefa 09.02 - Streaming Loop (UI consumindo Agent)

**Status**: PENDENTE
**Fase**: 09 - UI
**Dependencias**: 08.01, 09.01
**Bloqueia**: 09.03

---

## Objetivo

Implementar `src/vulpcode/ui/streaming.py` com a funcao `stream_agent_turn()` que
consome eventos do `Agent.turn()` e roteia para o `Renderer` apropriado. E o
ponto de costura entre o agente e a UI.

---

## Descricao Tecnica

### API

```python
async def stream_agent_turn(
    agent: Agent,
    user_input: str,
    renderer: Renderer,
    spinner: bool = True,
) -> None:
    """Consume Agent.turn(user_input) and render each event."""
```

### Logica

- Para cada evento, despacha para o metodo apropriado do renderer.
- Spinner Rich enquanto aguarda o primeiro chunk de texto e enquanto tools rodam.
- Esconde spinner quando texto comeca a fluir.

### Estrutura

**`src/vulpcode/ui/streaming.py`**:

```python
"""Connect Agent events to the Renderer."""
from __future__ import annotations

from rich.console import Console
from rich.spinner import Spinner
from rich.live import Live

from vulpcode.agent import (
    Agent,
    ErrorEvent,
    TextEvent,
    ToolDeniedEvent,
    ToolEndEvent,
    ToolStartEvent,
    TurnEndEvent,
    UsageEvent,
)
from vulpcode.ui.render import Renderer


async def stream_agent_turn(
    agent: Agent,
    user_input: str,
    renderer: Renderer,
    spinner: bool = True,
) -> None:
    console = renderer.console
    live: Live | None = None
    spinning = False

    def start_spinner(msg: str) -> None:
        nonlocal live, spinning
        if not spinner:
            return
        if live is not None:
            return
        live = Live(
            Spinner("dots", text=msg),
            console=console,
            refresh_per_second=10,
            transient=True,
        )
        live.start()
        spinning = True

    def stop_spinner() -> None:
        nonlocal live, spinning
        if live is not None:
            live.stop()
            live = None
            spinning = False

    try:
        start_spinner("Thinking...")
        async for ev in agent.turn(user_input):
            if isinstance(ev, TextEvent):
                stop_spinner()
                renderer.render_text_chunk(ev.text)
            elif isinstance(ev, ToolStartEvent):
                stop_spinner()
                renderer.render_tool_start(ev.tool_call)
                start_spinner(f"Running {ev.tool_call.name}...")
            elif isinstance(ev, ToolEndEvent):
                stop_spinner()
                renderer.render_tool_end(ev.tool_call, ev.result)
                start_spinner("Thinking...")
            elif isinstance(ev, ToolDeniedEvent):
                stop_spinner()
                renderer.render_tool_denied(ev.tool_call, ev.reason)
                start_spinner("Thinking...")
            elif isinstance(ev, UsageEvent):
                renderer.render_usage(ev.usage)
            elif isinstance(ev, ErrorEvent):
                stop_spinner()
                renderer.render_error(ev.error)
            elif isinstance(ev, TurnEndEvent):
                stop_spinner()
                renderer.render_turn_end()
                return
    finally:
        stop_spinner()
```

### Atualizar `ui/__init__.py`

```python
from vulpcode.ui.streaming import stream_agent_turn
__all__ = [..., "stream_agent_turn"]
```

---

## INSTRUCAO CRITICA

- Spinner usa `rich.live.Live` com `transient=True` para limpar a linha quando
  para. Iniciar/parar spinner ao redor de tool calls e blocos longos.
- Quando texto streaming comeca, o spinner para — o usuario ve o texto
  aparecendo em vez do spinner.
- Apos cada `ToolEndEvent`, voltar a "Thinking..." porque o LLM vai processar
  o resultado da tool.
- `try/finally` garante que o spinner e limpo se o gerador for cancelado.

---

## Etapas de Implementacao

### Etapa 1: Criar `ui/streaming.py`

### Etapa 2: Atualizar `ui/__init__.py`

### Etapa 3: Criar `tests/test_ui_streaming.py`

```python
import io
import pytest

from rich.console import Console
from pydantic import BaseModel

from vulpcode.agent import Agent
from vulpcode.providers import StreamChunk, ToolCall
from vulpcode.providers.base import Provider
from vulpcode.tools import Tool, ToolResult, clear_registry, tool
from vulpcode.ui import Renderer, get_theme, stream_agent_turn


class StaticProvider(Provider):
    name = "static"

    def __init__(self, scripted):
        super().__init__()
        self.scripted = list(scripted)

    async def stream(self, messages, tools, model, system=None, **kwargs):
        if not self.scripted:
            yield StreamChunk(type="stop")
            return
        for ch in self.scripted.pop(0):
            yield ch

    def supports_tools(self): return True
    def supports_vision(self): return False


def _make_renderer():
    buf = io.StringIO()
    console = Console(file=buf, width=80, force_terminal=False, color_system=None)
    return Renderer(console, get_theme("default")), buf


@pytest.mark.asyncio
async def test_stream_text_only():
    p = StaticProvider([[
        StreamChunk(type="text", delta="hi"),
        StreamChunk(type="stop"),
    ]])
    a = Agent(provider=p, tools=[], system="s")
    r, buf = _make_renderer()
    await stream_agent_turn(a, "?", r, spinner=False)
    assert "hi" in buf.getvalue()


@pytest.mark.asyncio
async def test_stream_with_tool():
    clear_registry()

    @tool(name="Greet", description="g")
    class T(Tool):
        class Input(BaseModel):
            name: str
        async def run(self, args):
            return ToolResult(output=f"hello {args.name}")

    p = StaticProvider([
        [StreamChunk(type="tool_call",
                     tool_call=ToolCall(id="1", name="Greet", arguments={"name": "world"})),
         StreamChunk(type="stop")],
        [StreamChunk(type="text", delta="done"), StreamChunk(type="stop")],
    ])
    a = Agent(provider=p, tools=[T()], system="s")
    r, buf = _make_renderer()
    await stream_agent_turn(a, "?", r, spinner=False)
    out = buf.getvalue()
    assert "Greet" in out
    assert "hello world" in out
    assert "done" in out
    clear_registry()
```

### Etapa 4: Rodar testes

```bash
pytest tests/test_ui_streaming.py -v
```

---

## Criterios de Aceite

- [x] `src/vulpcode/ui/streaming.py` implementa `stream_agent_turn`
- [x] Despacha cada tipo de evento para o metodo correspondente do `Renderer`
- [x] Spinner aparece/desaparece nos momentos certos
- [x] `spinner=False` desabilita (util em testes)
- [x] `ui/__init__.py` re-exporta `stream_agent_turn`
- [x] `tests/test_ui_streaming.py` com >=2 testes, todos passando

---

## Riscos Tecnicos

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|---------------|---------|-----------|
| Live spinner crasha em terminal nao-TTY | Media | Baixo | spinner=False default em --print |
| Race entre stop_spinner e render | Baixa | Baixo | Sequencial dentro do loop |

---

**End of Specification**
