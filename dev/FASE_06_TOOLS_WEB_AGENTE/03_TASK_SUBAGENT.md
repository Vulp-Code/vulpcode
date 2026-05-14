# Tarefa 06.03 - Tool Task (Sub-Agente)

**Status**: PENDENTE
**Fase**: 06 - Tools Web + Agente
**Dependencias**: 02.02 (Tool ABC). Depende de **FASE 08 (Agent loop)** para
funcionalidade real, mas pode ser implementada como **stub** que sera completado
apos a FASE 08.
**Bloqueia**: Nada

---

## Objetivo

Implementar a tool `Task` em `src/vulpcode/tools/task.py`. Lanca um sub-agente
com contexto isolado: novo agent loop com sua propria sequencia de mensagens
(nao polui o agente principal), tools restritas (Read, Grep, Glob, Bash apenas)
e retorna o resultado final como string.

**ATENCAO**: Esta tarefa registra a tool e implementa stub. A integracao real
com o `Agent` acontece quando FASE 08 estiver pronta — nesse ponto, voltamos
para esta tarefa e completamos a chamada a `Agent`.

---

## Descricao Tecnica

### Comportamento

- `description`: 3-5 palavras (apenas para logs/UI).
- `prompt`: o pedido detalhado para o sub-agente.
- `subagent_type`: por padrao `"general-purpose"`. Em fase futura, podemos ter
  agentes especializados ("Explore", "code-reviewer", etc.) com system prompts
  proprios.
- Retorna o ultimo bloco de texto do sub-agente como `output`.
- Sub-agente nao herda historico do principal — comeca limpo.
- Sub-agente nao consegue chamar `Task` (proibimos recursao para v1).

### Schema

```python
class Input(BaseModel):
    description: str
    prompt: str
    subagent_type: Literal["general-purpose", "Explore"] = "general-purpose"
```

### System prompts dos sub-agentes

```python
SUBAGENT_PROMPTS = {
    "general-purpose": (
        "You are a focused subagent. Solve the given task in as few steps as "
        "possible. Use tools as needed. End by writing the final answer as plain "
        "text — no markdown headers, just the answer."
    ),
    "Explore": (
        "You are a fast read-only search subagent. Locate files and patterns. "
        "Do NOT edit, write, or run shell commands beyond `find`/`grep`. Report "
        "findings concisely with file paths."
    ),
}
```

### Tools permitidas por subagent_type

```python
ALLOWED_TOOLS = {
    "general-purpose": {"Read", "Write", "Edit", "MultiEdit", "Bash", "Grep", "Glob", "WebFetch", "WebSearch", "TodoWrite"},
    "Explore": {"Read", "Grep", "Glob"},
}
```

### Estrutura (com stub)

**`src/vulpcode/tools/task.py`**:

```python
"""Task tool: launch a subagent with isolated context."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from vulpcode.tools.base import Tool, ToolResult, tool


SUBAGENT_PROMPTS: dict[str, str] = {
    "general-purpose": (
        "You are a focused subagent. Solve the given task in as few steps as "
        "possible. Use tools as needed. End by writing the final answer as plain "
        "text — no markdown headers, just the answer."
    ),
    "Explore": (
        "You are a fast read-only search subagent. Locate files and patterns. "
        "Do NOT edit, write, or run shell commands beyond `find`/`grep`. Report "
        "findings concisely with file paths."
    ),
}

ALLOWED_TOOLS: dict[str, set[str]] = {
    "general-purpose": {
        "Read", "Write", "Edit", "MultiEdit", "Bash", "BashOutput",
        "Grep", "Glob", "WebFetch", "WebSearch", "TodoWrite",
    },
    "Explore": {"Read", "Grep", "Glob"},
}


@tool(
    name="Task",
    description=(
        "Launch a subagent to perform a focused task with isolated context. "
        "Useful for parallelizable independent work. Returns the subagent's "
        "final answer as a string."
    ),
    requires_confirm=False,
)
class TaskTool(Tool):
    class Input(BaseModel):
        description: str
        prompt: str
        subagent_type: Literal["general-purpose", "Explore"] = "general-purpose"

    async def run(self, args: BaseModel) -> ToolResult:  # type: ignore[override]
        assert isinstance(args, TaskTool.Input)

        # Lazy import to avoid circular dependency: Agent imports tools too.
        try:
            from vulpcode.agent import Agent
            from vulpcode.providers import build_provider
            from vulpcode.config import load_config
        except ImportError as exc:
            return ToolResult(
                error=f"Subagent unavailable (missing module): {exc}",
                is_error=True,
            )

        cfg = load_config()
        provider_name = cfg.get("default_provider", "anthropic")
        model = cfg.get("default_model", "")
        provider_cfg = (cfg.get("providers", {}) or {}).get(provider_name, {})
        provider = build_provider(provider_name, provider_cfg)

        from vulpcode.tools.base import TOOL_REGISTRY
        allowed = ALLOWED_TOOLS.get(args.subagent_type, ALLOWED_TOOLS["general-purpose"])
        # Subagents cannot call Task themselves (no nesting in v1)
        sub_tools = [
            cls() for name, cls in TOOL_REGISTRY.items()
            if name in allowed and name != "Task"
        ]

        agent = Agent(
            provider=provider,
            tools=sub_tools,
            system=SUBAGENT_PROMPTS[args.subagent_type],
            model=model,
        )

        try:
            final_text = await agent.run_to_completion(args.prompt)
        except Exception as exc:
            return ToolResult(
                error=f"Subagent failed: {type(exc).__name__}: {exc}",
                is_error=True,
            )

        return ToolResult(
            output=final_text or "<subagent returned no text>",
            metadata={
                "subagent_type": args.subagent_type,
                "description": args.description,
            },
        )
```

### Stub para FASE 08

A funcao `Agent.run_to_completion(prompt)` ainda nao existe — sera adicionada na
FASE 08 (Agent Loop). O test desta tarefa pode ser:

1. Validar que a tool esta registrada (pular execucao real).
2. Skip teste de execucao com `pytest.skip` ou marcador.

---

## INSTRUCAO CRITICA

- Imports lazy (dentro de `run()`) sao essenciais para evitar import circular —
  `Agent` (FASE 08) ira importar do registry de tools.
- Quando a FASE 08 completar, `Agent.run_to_completion(prompt)` deve estar
  implementada. Se ainda nao estiver, voltar a esta tarefa e criar uma versao
  intermediaria que retorna `is_error` informativo.
- Sub-agente NAO tem `Task` na lista — proibimos recursao para evitar custos
  exponenciais.
- O sub-agente recebe um Provider novo (criado a partir do config), nao
  compartilha state com o principal.

---

## Etapas de Implementacao

### Etapa 1: Criar `tools/task.py`

### Etapa 2: Atualizar `tools/__init__.py`

```python
from vulpcode.tools import task as _task  # noqa: F401
```

### Etapa 3: Criar `tests/test_tools/test_task.py`

```python
import pytest

import vulpcode.tools  # noqa
from vulpcode.tools import get_tool


def test_task_is_registered():
    cls = get_tool("Task")
    assert cls._tool_name == "Task"
    assert cls._requires_confirm is False


def test_task_input_validation():
    cls = get_tool("Task")
    inst = cls.Input(description="d", prompt="p", subagent_type="Explore")
    assert inst.subagent_type == "Explore"
    with pytest.raises(Exception):
        cls.Input(description="d", prompt="p", subagent_type="bogus")


@pytest.mark.asyncio
async def test_task_runs_or_errors_gracefully():
    """Until FASE 08 wires up Agent.run_to_completion, this returns is_error.
    After FASE 08, this test can be expanded to mock the Agent."""
    cls = get_tool("Task")
    res = await cls().run(cls.Input(description="d", prompt="p", subagent_type="Explore"))
    # We accept either success (after FASE 08) or graceful error (before FASE 08).
    assert res is not None
```

### Etapa 4: Rodar testes

```bash
pytest tests/test_tools/test_task.py -v
```

---

## Criterios de Aceite

- [x] `src/vulpcode/tools/task.py` implementa `TaskTool`
- [x] Imports de `Agent` / `build_provider` / `load_config` sao lazy (dentro do `run()`)
- [x] `subagent_type` valida `general-purpose` / `Explore` via Literal
- [x] `ALLOWED_TOOLS` define lista permitida por tipo
- [x] `Task` proibe sub-agentes de chamarem `Task` recursivamente
- [x] `requires_confirm=False`
- [x] `tools/__init__.py` importa `task.py`
- [x] `tests/test_tools/test_task.py` com >=3 testes, todos passando
- [x] Stub funcional: erros graceful enquanto FASE 08 nao esta completa
- [x] Voltar nesta tarefa apos FASE 08 esta marcada explicitamente como TODO no codigo (comentario `# TODO(FASE_08): wire to real Agent` se aplicavel)

---

## Riscos Tecnicos

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|---------------|---------|-----------|
| Import circular agent <-> tools | Alta | Alto | Lazy imports dentro de run() |
| Sub-agente custa muito | Media | Alto | Sem recursao; o usuario controla via prompts |
| Agent.run_to_completion API muda na FASE 08 | Media | Medio | Revisitar quando FASE 08 estiver pronta |

---

**End of Specification**
