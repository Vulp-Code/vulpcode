# Tarefa 10.01 - Slash Commands Basicos (/tools, /cost, /compact)

**Status**: PENDENTE
**Fase**: 10 - Slash Commands
**Dependencias**: 09.03 (Repl)
**Bloqueia**: 10.02, 10.03

---

## Objetivo

Implementar `src/vulpcode/commands/` com:
- Classe base `SlashCommand`
- Comandos `tools`, `cost`, `compact`

(`/help`, `/clear`, `/exit` ja estao no Repl como builtins.)

---

## Descricao Tecnica

### SlashCommand base

```python
class SlashCommand(ABC):
    name: str
    help_text: str

    @abstractmethod
    async def run(self, repl: "Repl", args: str) -> None: ...
```

### Estrutura de pasta

```
src/vulpcode/commands/
    __init__.py        # registry: build_default_commands()
    _base.py           # SlashCommand ABC
    tools.py           # /tools — lista tools ativas
    cost.py            # /cost — uso acumulado de tokens
    compact.py         # /compact — sumariza historico
```

### Implementacoes

**`src/vulpcode/commands/_base.py`**:

```python
"""SlashCommand base class."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from vulpcode.ui.repl import Repl


class SlashCommand(ABC):
    name: str
    help_text: str = ""

    @abstractmethod
    async def run(self, repl: "Repl", args: str) -> None: ...
```

**`src/vulpcode/commands/tools.py`**:

```python
"""/tools — list active tools."""
from __future__ import annotations

from vulpcode.commands._base import SlashCommand
from vulpcode.tools import list_tools


class ToolsCommand(SlashCommand):
    name = "tools"
    help_text = "List currently registered tools"

    async def run(self, repl, args: str) -> None:
        rows = []
        for cls in list_tools():
            confirm = "yes" if cls._requires_confirm else "no"
            rows.append([cls._tool_name, confirm, cls._tool_description[:60]])
        repl.renderer.render_table(
            "Active tools", ["name", "confirm?", "description"], rows,
        )
```

**`src/vulpcode/commands/cost.py`**:

```python
"""/cost — print accumulated token usage of the session."""
from __future__ import annotations

from vulpcode.commands._base import SlashCommand


class CostCommand(SlashCommand):
    name = "cost"
    help_text = "Show accumulated token usage for this session"

    async def run(self, repl, args: str) -> None:
        # The Agent does not currently aggregate usage; we add a tiny tracker here.
        usage = getattr(repl.agent, "_session_usage", None)
        if usage is None:
            repl.renderer.console.print(
                "[muted]no usage data tracked (will populate after first turn)[/]"
            )
            return
        repl.renderer.render_table(
            "Session usage",
            ["metric", "tokens"],
            [
                ["input", str(usage.input_tokens)],
                ["output", str(usage.output_tokens)],
                ["cache_read", str(usage.cache_read_tokens)],
                ["cache_create", str(usage.cache_creation_tokens)],
            ],
        )
```

(Para que isto funcione, o `Agent` precisa acumular usage. Na FASE 08 o evento
`UsageEvent` apenas e emitido. Atualizar `Agent` para tambem agregar em
`_session_usage` — isto e uma pequena modificacao a fazer NESTA tarefa.)

**`src/vulpcode/commands/compact.py`**:

```python
"""/compact — summarize history to reduce token usage."""
from __future__ import annotations

from vulpcode.commands._base import SlashCommand
from vulpcode.providers.base import Message


class CompactCommand(SlashCommand):
    name = "compact"
    help_text = "Summarize the conversation history into a compact context"

    async def run(self, repl, args: str) -> None:
        agent = repl.agent
        if len(agent._messages) < 4:
            repl.renderer.console.print(
                "[muted]history too short to compact[/]"
            )
            return
        repl.renderer.console.print("[muted]requesting summary...[/]")
        # Build a focused prompt to produce a brief
        summary_messages = list(agent._messages) + [
            Message(
                role="user",
                content=(
                    "Summarize the conversation so far in a single paragraph, "
                    "preserving any concrete file paths, decisions, or open TODOs. "
                    "No preamble, just the summary."
                ),
            ),
        ]
        text = ""
        try:
            async for chunk in agent.provider.stream(
                messages=summary_messages,
                tools=[],
                model=agent.model,
                system="You are a concise summarizer.",
            ):
                if chunk.type == "text" and chunk.delta:
                    text += chunk.delta
                elif chunk.type == "stop":
                    break
        except Exception as exc:
            repl.renderer.render_error(f"compact failed: {exc}")
            return
        # Replace history with single summary turn
        agent._messages = [
            Message(role="user", content="<previous conversation summary>"),
            Message(role="assistant", content=text),
        ]
        repl.renderer.console.print("[green]history compacted[/]")
        repl.renderer.console.print(f"[muted]{text}[/]")
```

**`src/vulpcode/commands/__init__.py`**:

```python
"""Built-in slash commands."""
from vulpcode.commands._base import SlashCommand
from vulpcode.commands.compact import CompactCommand
from vulpcode.commands.cost import CostCommand
from vulpcode.commands.tools import ToolsCommand


def build_default_commands() -> dict[str, SlashCommand]:
    """All commands available in the REPL by default."""
    cmds = [ToolsCommand(), CostCommand(), CompactCommand()]
    return {c.name: c for c in cmds}


__all__ = [
    "SlashCommand",
    "ToolsCommand",
    "CostCommand",
    "CompactCommand",
    "build_default_commands",
]
```

### Modificar `Agent` para acumular usage

Em `src/vulpcode/agent.py`:

- Adicionar `self._session_usage = Usage()` no `__init__`.
- No handler de `chunk.type == "usage"`, antes de `yield UsageEvent(...)`,
  somar em `self._session_usage`:

```python
elif chunk.type == "usage" and chunk.usage is not None:
    self._session_usage.input_tokens += chunk.usage.input_tokens
    self._session_usage.output_tokens += chunk.usage.output_tokens
    self._session_usage.cache_read_tokens += chunk.usage.cache_read_tokens
    self._session_usage.cache_creation_tokens += chunk.usage.cache_creation_tokens
    yield UsageEvent(chunk.usage)
```

### Modificar `app.py` para passar `commands` ao `Repl`

```python
from vulpcode.commands import build_default_commands

# inside start_repl, after building Repl:
repl = Repl(agent=agent, renderer=renderer, config=cfg, commands=build_default_commands())
```

---

## INSTRUCAO CRITICA

- O `/compact` faz uma chamada extra ao provider para gerar o resumo. Se falhar,
  preserva o historico original.
- `/cost` requer que `Agent` agregue `Usage` — modificar `Agent` nesta tarefa.
- Comandos sao injetados no `Repl` via `commands` dict — o `Repl` ja tem o
  hook em `_handle_slash`.

---

## Etapas de Implementacao

### Etapa 1: Criar `commands/_base.py`, `tools.py`, `cost.py`, `compact.py`

### Etapa 2: Criar `commands/__init__.py` com `build_default_commands()`

### Etapa 3: Modificar `agent.py` para agregar usage em `_session_usage`

### Etapa 4: Modificar `app.py` para passar `build_default_commands()` ao `Repl`

### Etapa 5: Criar `tests/test_commands.py`

```python
import io
import pytest

from rich.console import Console

from vulpcode.commands import (
    CostCommand,
    ToolsCommand,
    build_default_commands,
)
from vulpcode.ui import Renderer, get_theme


class FakeRepl:
    def __init__(self, agent=None):
        buf = io.StringIO()
        console = Console(file=buf, width=80, force_terminal=False, color_system=None)
        self.renderer = Renderer(console, get_theme("default"))
        self.agent = agent
        self.buf = buf


@pytest.mark.asyncio
async def test_tools_command_lists_registered():
    import vulpcode.tools  # noqa
    repl = FakeRepl()
    await ToolsCommand().run(repl, "")
    assert "Read" in repl.buf.getvalue() or "Bash" in repl.buf.getvalue()


@pytest.mark.asyncio
async def test_cost_command_no_data():
    class Agent: pass
    repl = FakeRepl(agent=Agent())
    await CostCommand().run(repl, "")
    assert "no usage" in repl.buf.getvalue() or "tokens" in repl.buf.getvalue()


def test_build_default_commands():
    cmds = build_default_commands()
    assert "tools" in cmds
    assert "cost" in cmds
    assert "compact" in cmds
```

### Etapa 6: Rodar testes

```bash
pytest tests/test_commands.py tests/test_agent.py -v
```

---

## Criterios de Aceite

- [x] `src/vulpcode/commands/_base.py` define `SlashCommand` ABC
- [x] `commands/tools.py` implementa `ToolsCommand` (lista tools registradas)
- [x] `commands/cost.py` implementa `CostCommand` (usa `Agent._session_usage`)
- [x] `commands/compact.py` implementa `CompactCommand` (resume e substitui historico)
- [x] `commands/__init__.py` exporta `build_default_commands()`
- [x] `Agent` acumula `Usage` em `_session_usage` por turno
- [x] `app.py` passa `build_default_commands()` ao `Repl`
- [x] `tests/test_commands.py` com >=3 testes, todos passando
- [x] `pytest tests/test_agent.py` continua passando apos modificacao do Agent

---

## Riscos Tecnicos

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|---------------|---------|-----------|
| /compact falha em providers sem stream | Baixa | Medio | Captura excecao, mantem historico |
| Usage tokens inconsistentes entre providers | Media | Baixo | Aceitar diferencas |

---

**End of Specification**
