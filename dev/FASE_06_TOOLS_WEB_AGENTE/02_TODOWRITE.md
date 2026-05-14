# Tarefa 06.02 - Tool TodoWrite

**Status**: PENDENTE
**Fase**: 06 - Tools Web + Agente
**Dependencias**: 02.02
**Bloqueia**: Nada

---

## Objetivo

Implementar a tool `TodoWrite` em `src/vulpcode/tools/todo.py`. Mantem uma lista
de tarefas por sessao na memoria do processo. O LLM gerencia a lista para
acompanhar progresso de tarefas multi-step.

---

## Descricao Tecnica

### Comportamento

- Substitui inteiramente a lista a cada chamada (paridade com Claude Code).
- Cada item tem `content`, `status` (`pending` | `in_progress` | `completed`),
  e `activeForm` (gerundio para a UI mostrar enquanto in_progress).
- Apenas UM item pode estar `in_progress` simultaneamente — validar.
- Lista persistida em `_todo_store` (dict modulo-level), keyed por session_id.
  Por enquanto, session_id e fixo `"default"` — FASE 12 (session) injeta o id
  real.

### Schema

```python
class TodoItem(BaseModel):
    content: str               # imperative form ("Implement X")
    activeForm: str            # progressive form ("Implementing X")
    status: Literal["pending", "in_progress", "completed"]

class Input(BaseModel):
    todos: list[TodoItem]
```

### Estrutura

**`src/vulpcode/tools/todo.py`**:

```python
"""TodoWrite tool: in-memory todo list managed by the LLM."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from vulpcode.tools.base import Tool, ToolResult, tool


# Module-level store: session_id -> list of TodoItem
_TODO_STORE: dict[str, list["TodoItem"]] = {}
_DEFAULT_SESSION = "default"


class TodoItem(BaseModel):
    content: str
    activeForm: str
    status: Literal["pending", "in_progress", "completed"]


def get_todos(session_id: str = _DEFAULT_SESSION) -> list[TodoItem]:
    return list(_TODO_STORE.get(session_id, []))


def clear_todos(session_id: str = _DEFAULT_SESSION) -> None:
    _TODO_STORE.pop(session_id, None)


@tool(
    name="TodoWrite",
    description=(
        "Replace the agent's todo list. Each item has content (imperative), "
        "activeForm (progressive), and status. Only one item may be 'in_progress'."
    ),
    requires_confirm=False,
)
class TodoWriteTool(Tool):
    class Input(BaseModel):
        todos: list[TodoItem] = Field(default_factory=list)

        @field_validator("todos")
        @classmethod
        def _at_most_one_in_progress(cls, v: list[TodoItem]) -> list[TodoItem]:
            in_progress = sum(1 for t in v if t.status == "in_progress")
            if in_progress > 1:
                raise ValueError("at most one task may be 'in_progress' at a time")
            return v

    async def run(self, args: BaseModel) -> ToolResult:  # type: ignore[override]
        assert isinstance(args, TodoWriteTool.Input)
        # Replace the list for the default session
        _TODO_STORE[_DEFAULT_SESSION] = list(args.todos)
        # Render compact summary
        rendered = []
        for i, t in enumerate(args.todos, start=1):
            marker = {
                "pending": "[ ]",
                "in_progress": "[~]",
                "completed": "[x]",
            }[t.status]
            label = t.activeForm if t.status == "in_progress" else t.content
            rendered.append(f"{i}. {marker} {label}")
        body = "\n".join(rendered) or "<empty list>"
        return ToolResult(
            output=body,
            metadata={
                "session": _DEFAULT_SESSION,
                "total": len(args.todos),
                "in_progress": sum(1 for t in args.todos if t.status == "in_progress"),
                "completed": sum(1 for t in args.todos if t.status == "completed"),
            },
        )
```

### Atualizar `tools/__init__.py`

```python
from vulpcode.tools import todo as _todo  # noqa: F401
```

E exportar helpers:
```python
from vulpcode.tools.todo import TodoItem, get_todos, clear_todos
```

---

## INSTRUCAO CRITICA

- O store e modulo-global. Quando FASE 12 (session) for implementada, refatorar
  para usar `session_id` real. Por enquanto, `_DEFAULT_SESSION = "default"`.
- A validacao de `at most one in_progress` e crucial — espelha Claude Code.
- `activeForm` e cosmetico; mostramos quando o status e `in_progress` para a UI
  exibir "Implementing X" durante a tarefa.
- Renderizar com markers `[ ]`, `[~]`, `[x]` para o agente parsear depois se
  precisar.

---

## Etapas de Implementacao

### Etapa 1: Criar `tools/todo.py`

### Etapa 2: Atualizar `tools/__init__.py`

### Etapa 3: Criar `tests/test_tools/test_todo.py`

```python
import pytest

import vulpcode.tools  # noqa
from vulpcode.tools import get_tool
from vulpcode.tools.todo import _TODO_STORE, get_todos, clear_todos


@pytest.fixture(autouse=True)
def _clean():
    clear_todos()
    yield
    clear_todos()


@pytest.mark.asyncio
async def test_todo_write_replaces_list():
    cls = get_tool("TodoWrite")
    res = await cls().run(cls.Input(todos=[
        cls.Input.model_fields["todos"].annotation.__args__[0](
            content="Do A", activeForm="Doing A", status="in_progress",
        ),
    ]))
    assert res.is_error is False
    assert len(get_todos()) == 1
    assert get_todos()[0].status == "in_progress"


@pytest.mark.asyncio
async def test_todo_at_most_one_in_progress():
    cls = get_tool("TodoWrite")
    TodoItem = cls.Input.model_fields["todos"].annotation.__args__[0]
    with pytest.raises(Exception):
        cls.Input(todos=[
            TodoItem(content="A", activeForm="a", status="in_progress"),
            TodoItem(content="B", activeForm="b", status="in_progress"),
        ])


@pytest.mark.asyncio
async def test_todo_render_uses_active_form():
    cls = get_tool("TodoWrite")
    TodoItem = cls.Input.model_fields["todos"].annotation.__args__[0]
    res = await cls().run(cls.Input(todos=[
        TodoItem(content="Implement X", activeForm="Implementing X", status="in_progress"),
        TodoItem(content="Do Y", activeForm="Doing Y", status="pending"),
    ]))
    assert "Implementing X" in res.output
    assert "Do Y" in res.output


@pytest.mark.asyncio
async def test_todo_completed_marker():
    cls = get_tool("TodoWrite")
    TodoItem = cls.Input.model_fields["todos"].annotation.__args__[0]
    res = await cls().run(cls.Input(todos=[
        TodoItem(content="A", activeForm="a", status="completed"),
    ]))
    assert "[x]" in res.output


@pytest.mark.asyncio
async def test_todo_empty_list_ok():
    cls = get_tool("TodoWrite")
    res = await cls().run(cls.Input(todos=[]))
    assert res.is_error is False
    assert get_todos() == []
```

### Etapa 4: Rodar testes

```bash
pytest tests/test_tools/test_todo.py -v
```

---

## Criterios de Aceite

- [x] `src/vulpcode/tools/todo.py` implementa `TodoWriteTool` e `TodoItem`
- [x] Validacao: no maximo um `in_progress`
- [x] Lista substituida inteiramente a cada chamada
- [x] `get_todos()`, `clear_todos()` exportados
- [x] Render usa `activeForm` quando status e `in_progress`
- [x] `requires_confirm=False`
- [x] `tools/__init__.py` importa `todo.py` e re-exporta helpers
- [x] `tests/test_tools/test_todo.py` com >=5 testes, todos passando

---

## Riscos Tecnicos

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|---------------|---------|-----------|
| Estado global polui entre sessoes | Media | Medio | Refatorar com session_id na FASE 12 |
| LLM esquece de marcar `in_progress` | Alta | Baixo | Apenas cosmetico; nao quebra |

---

**End of Specification**
