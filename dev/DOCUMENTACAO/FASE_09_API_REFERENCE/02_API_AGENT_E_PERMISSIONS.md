# Tarefa 09.02 - API Reference (Agent + Permissions)

**Status**: PENDENTE
**Fase**: 09 - API Reference
**Dependencias**: 09.01
**Bloqueia**: 09.03

---

## Objetivo

Criar paginas auto-geradas para `agent.py` e `permissions.py`. Inclui melhoria
de docstrings antes de gerar.

---

## Arquivos a criar

- `docs/api/agent.md`
- `docs/api/permissions.md`

---

## Pre-requisito: docstrings

Auditar e melhorar docstrings em:
- `src/vulpcode/agent.py` — `Agent`, `TextEvent`, `ToolStartEvent`, `ToolEndEvent`,
  `ToolDeniedEvent`, `UsageEvent`, `TurnEndEvent`, `ErrorEvent`
- `src/vulpcode/permissions.py` — `Mode`, `PermissionDecision`,
  `PermissionManager`, `stdin_prompter`

Para `Agent`, garantir que esta documentado:
- Construtor: parametros provider, tools, system, model, permissions, model_settings
- `turn(user_input)` async generator: o que cada Event significa
- `run_to_completion(user_input)` que devolve string
- `_max_iters` como salvaguarda

---

## Conteudo de `api/agent.md`

```markdown
# Agent

O coracao do vulpcode: orquestra o loop LLM <-> tools, aplica permissoes e
emite eventos para a UI consumir.

## Eventos

::: vulpcode.agent
    options:
      heading_level: 3
      show_root_full_path: false
      members:
        - TextEvent
        - ToolStartEvent
        - ToolEndEvent
        - ToolDeniedEvent
        - UsageEvent
        - TurnEndEvent
        - ErrorEvent
        - Event

## Classe Agent

::: vulpcode.agent.Agent
    options:
      heading_level: 3
      show_root_full_path: false
      show_source: true
      merge_init_into_class: true
      members_order: source

## Exemplo

```python
import asyncio
from vulpcode.agent import Agent, TextEvent
from vulpcode.providers import build_provider
from vulpcode.permissions import Mode, PermissionManager
from vulpcode.tools import list_tools
import vulpcode.tools  # noqa — registers tools

async def main():
    provider = build_provider("anthropic", {"api_key": "sk-ant-..."})
    tools = [cls() for cls in list_tools()]
    perms = PermissionManager(config={}, mode=Mode.AUTO)
    agent = Agent(provider=provider, tools=tools, model="claude-sonnet-4-6",
                  permissions=perms)
    text = await agent.run_to_completion("explique async/await em 2 frases")
    print(text)

asyncio.run(main())
```
```

---

## Conteudo de `api/permissions.md`

```markdown
# Permissions

Sistema de permissoes para execucao de tools. Veja tambem
[User Guide](../user-guide/permission-modes.md) e
[Configuracao avancada](../configuration/permissions.md).

## Mode

::: vulpcode.permissions.Mode

## PermissionDecision

::: vulpcode.permissions.PermissionDecision

## PermissionManager

::: vulpcode.permissions.PermissionManager
    options:
      heading_level: 3
      merge_init_into_class: true
      members_order: source

## Prompter padrao

::: vulpcode.permissions.stdin_prompter

## Custom prompter

```python
from vulpcode.permissions import PermissionManager, Mode

async def my_prompter(message: str, ctx: dict) -> str:
    # Custom logic
    return "y"

pm = PermissionManager(config={}, mode=Mode.DEFAULT, prompter=my_prompter)
```
```

---

## Atualizar `mkdocs.yml`

As entradas ja foram adicionadas em 09.01. Nao mexer.

---

## INSTRUCAO CRITICA

- O `Agent.turn()` e um async generator. mkdocstrings deve renderizar a
  signature corretamente. Se nao, ajustar docstring.
- Em eventos (dataclasses), garantir que cada um tem ao menos uma linha de
  docstring.

---

## Etapas de Implementacao

### Etapa 1: Auditar e melhorar docstrings em agent.py e permissions.py
### Etapa 2: Criar `api/agent.md` e `api/permissions.md`
### Etapa 3: `mkdocs build`

---

## Criterios de Aceite

- [x] Docstrings em agent.py auditadas/melhoradas
- [x] Docstrings em permissions.py auditadas/melhoradas
- [x] `docs/api/agent.md` criado com 3 secoes (eventos, classe, exemplo)
- [x] `docs/api/permissions.md` criado com 4 secoes (Mode, Decision, Manager, prompter)
- [x] mkdocstrings renderiza todos os simbolos sem warning
- [x] `mkdocs build` continua passando

---

**End of Specification**
