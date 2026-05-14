# Tarefa 09.01 - UI Theme + Render (Rich)

**Status**: PENDENTE
**Fase**: 09 - UI
**Dependencias**: 08.01 (eventos do Agent)
**Bloqueia**: 09.02, 09.03

---

## Objetivo

Implementar `src/vulpcode/ui/theme.py` (definicoes de cor) e `src/vulpcode/ui/render.py`
(render de eventos do Agent usando `rich`). Estes modulos formatam tool calls,
markdown, diffs e tabelas para exibir bonito no terminal.

---

## Descricao Tecnica

### theme.py

```python
@dataclass(frozen=True)
class Theme:
    name: str
    primary: str
    accent: str
    success: str
    warning: str
    danger: str
    muted: str
    code_theme: str  # for rich.syntax

THEMES: dict[str, Theme] = {
    "monokai": Theme(...),
    "default": Theme(...),
}

def get_theme(name: str) -> Theme:
    return THEMES.get(name, THEMES["default"])
```

### render.py

Funcoes que recebem um `rich.console.Console` e um evento, retornam None
(escrevem direto). Permite customizar via tema.

```python
class Renderer:
    def __init__(self, console: Console, theme: Theme): ...
    def render_text_chunk(self, delta: str) -> None: ...   # streaming text
    def render_tool_start(self, tool_call: ToolCall) -> None: ...
    def render_tool_end(self, tool_call: ToolCall, result: ToolResult) -> None: ...
    def render_tool_denied(self, tool_call: ToolCall, reason: str) -> None: ...
    def render_usage(self, usage: Usage) -> None: ...
    def render_error(self, msg: str) -> None: ...
    def render_turn_end(self) -> None: ...
    def render_assistant_markdown(self, text: str) -> None: ...
```

### Estrutura

**`src/vulpcode/ui/theme.py`**:

```python
"""UI themes."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    name: str
    primary: str
    accent: str
    success: str
    warning: str
    danger: str
    muted: str
    code_theme: str


THEMES: dict[str, Theme] = {
    "default": Theme(
        name="default",
        primary="cyan",
        accent="magenta",
        success="green",
        warning="yellow",
        danger="red",
        muted="bright_black",
        code_theme="monokai",
    ),
    "monokai": Theme(
        name="monokai",
        primary="bright_cyan",
        accent="bright_magenta",
        success="bright_green",
        warning="bright_yellow",
        danger="bright_red",
        muted="bright_black",
        code_theme="monokai",
    ),
    "light": Theme(
        name="light",
        primary="blue",
        accent="magenta",
        success="green",
        warning="yellow",
        danger="red",
        muted="grey50",
        code_theme="default",
    ),
}


def get_theme(name: str) -> Theme:
    return THEMES.get(name, THEMES["default"])
```

**`src/vulpcode/ui/render.py`**:

```python
"""Rich-based renderer for Agent events."""
from __future__ import annotations

import json

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from vulpcode.providers.base import ToolCall, Usage
from vulpcode.tools.base import ToolResult
from vulpcode.ui.theme import Theme


class Renderer:
    def __init__(self, console: Console, theme: Theme) -> None:
        self.console = console
        self.theme = theme
        self._streaming_active = False

    def render_text_chunk(self, delta: str) -> None:
        # Print without newline; flush via console
        self.console.print(delta, end="", soft_wrap=True, highlight=False)
        self._streaming_active = True

    def render_assistant_markdown(self, text: str) -> None:
        if self._streaming_active:
            self.console.print()  # close streamed line
            self._streaming_active = False
        self.console.print(Markdown(text))

    def render_tool_start(self, tool_call: ToolCall) -> None:
        if self._streaming_active:
            self.console.print()
            self._streaming_active = False
        args_pretty = json.dumps(tool_call.arguments, indent=2, ensure_ascii=False)
        body = Syntax(args_pretty, "json", theme=self.theme.code_theme, word_wrap=True)
        self.console.print(Panel(
            body,
            title=f"[{self.theme.accent}]{tool_call.name}[/]",
            subtitle=f"[{self.theme.muted}]running...[/]",
            border_style=self.theme.primary,
        ))

    def render_tool_end(self, tool_call: ToolCall, result: ToolResult) -> None:
        if result.is_error:
            content = result.error or result.output or "<error>"
            color = self.theme.danger
            label = "error"
        else:
            content = result.output or "<no output>"
            color = self.theme.success
            label = "ok"
        # Truncate display (full content is in messages)
        if len(content) > 1500:
            content = content[:1500] + "\n[...truncated...]"
        self.console.print(Panel(
            content,
            title=f"[{color}]{tool_call.name} -> {label}[/]",
            border_style=color,
        ))

    def render_tool_denied(self, tool_call: ToolCall, reason: str) -> None:
        self.console.print(
            f"[{self.theme.warning}]Tool {tool_call.name!r} denied: {reason}[/]"
        )

    def render_usage(self, usage: Usage) -> None:
        if usage.input_tokens or usage.output_tokens:
            self.console.print(
                f"[{self.theme.muted}]tokens: in={usage.input_tokens} "
                f"out={usage.output_tokens}[/]"
            )

    def render_error(self, msg: str) -> None:
        if self._streaming_active:
            self.console.print()
            self._streaming_active = False
        self.console.print(f"[{self.theme.danger}]error: {msg}[/]")

    def render_turn_end(self) -> None:
        if self._streaming_active:
            self.console.print()
            self._streaming_active = False

    def render_table(self, title: str, columns: list[str], rows: list[list[str]]) -> None:
        t = Table(title=title)
        for c in columns:
            t.add_column(c, style=self.theme.primary)
        for r in rows:
            t.add_row(*r)
        self.console.print(t)
```

### Atualizar `ui/__init__.py`

```python
"""Terminal UI utilities (Rich + prompt_toolkit)."""
from vulpcode.ui.render import Renderer
from vulpcode.ui.theme import Theme, get_theme

__all__ = ["Renderer", "Theme", "get_theme"]
```

---

## INSTRUCAO CRITICA

- O renderer mantem flag `_streaming_active`: quando texto e impresso por chunks
  via `render_text_chunk`, NAO ha newline. Antes de qualquer outra renderizacao
  (panel, error, etc.), forcar newline para fechar a linha.
- Tool start usa Panel com syntax-highlighted JSON dos argumentos.
- Tool end tem cor diferente para error vs ok.
- Truncamento visual de 1500 chars no tool result — o conteudo completo continua
  no historico do agente, so a UI corta.
- Usage so e renderizado se houver tokens.
- `render_assistant_markdown(text)` e usado para texto NAO-streaming (modo
  one-shot ou apos resposta completa). Em streaming, usamos `render_text_chunk`
  delta a delta.

---

## Etapas de Implementacao

### Etapa 1: Criar `ui/theme.py`

### Etapa 2: Criar `ui/render.py`

### Etapa 3: Atualizar `ui/__init__.py`

### Etapa 4: Criar `tests/test_ui_render.py`

```python
import io

from rich.console import Console

from vulpcode.providers import ToolCall, Usage
from vulpcode.tools import ToolResult
from vulpcode.ui import Renderer, get_theme


def make_renderer():
    buf = io.StringIO()
    console = Console(file=buf, width=80, force_terminal=False, color_system=None)
    return Renderer(console, get_theme("default")), buf


def test_render_text_chunk():
    r, buf = make_renderer()
    r.render_text_chunk("hello")
    assert "hello" in buf.getvalue()


def test_render_tool_start_panel():
    r, buf = make_renderer()
    tc = ToolCall(id="1", name="Read", arguments={"file_path": "/a"})
    r.render_tool_start(tc)
    out = buf.getvalue()
    assert "Read" in out
    assert "/a" in out


def test_render_tool_end_ok():
    r, buf = make_renderer()
    tc = ToolCall(id="1", name="Read", arguments={})
    r.render_tool_end(tc, ToolResult(output="hello"))
    out = buf.getvalue()
    assert "hello" in out
    assert "ok" in out


def test_render_tool_end_error():
    r, buf = make_renderer()
    tc = ToolCall(id="1", name="Bash", arguments={})
    r.render_tool_end(tc, ToolResult(error="boom", is_error=True))
    out = buf.getvalue()
    assert "boom" in out
    assert "error" in out


def test_render_tool_denied():
    r, buf = make_renderer()
    tc = ToolCall(id="1", name="Bash", arguments={})
    r.render_tool_denied(tc, "user rejected")
    assert "denied" in buf.getvalue()


def test_render_usage_only_if_nonzero():
    r, buf = make_renderer()
    r.render_usage(Usage())
    assert "tokens" not in buf.getvalue()
    r.render_usage(Usage(input_tokens=10, output_tokens=20))
    assert "tokens" in buf.getvalue()


def test_render_error():
    r, buf = make_renderer()
    r.render_error("nope")
    assert "nope" in buf.getvalue()


def test_render_table():
    r, buf = make_renderer()
    r.render_table("Hi", ["a", "b"], [["1", "2"]])
    assert "Hi" in buf.getvalue()
    assert "1" in buf.getvalue()
```

### Etapa 5: Rodar testes

```bash
pytest tests/test_ui_render.py -v
```

---

## Criterios de Aceite

- [x] `src/vulpcode/ui/theme.py` define `Theme` dataclass e `THEMES` (>=3 temas)
- [x] `get_theme(name)` retorna o tema certo (fallback default)
- [x] `src/vulpcode/ui/render.py` define `Renderer` com metodos:
- [x]   `render_text_chunk`, `render_assistant_markdown`
- [x]   `render_tool_start`, `render_tool_end`, `render_tool_denied`
- [x]   `render_usage`, `render_error`, `render_turn_end`, `render_table`
- [x] Streaming respeita flag `_streaming_active` (fecha linha antes de paneis)
- [x] Tool result truncado a 1500 chars na UI
- [x] `ui/__init__.py` re-exporta `Renderer`, `Theme`, `get_theme`
- [x] `tests/test_ui_render.py` com >=8 testes, todos passando

---

## Riscos Tecnicos

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|---------------|---------|-----------|
| Cores ruins em terminal claro | Media | Baixo | Tema "light" |
| Markdown render quebra linha em codigo | Baixa | Baixo | Aceitar v1 |
| Console buffer em testes | Baixa | Baixo | force_terminal=False, color_system=None |

---

**End of Specification**
