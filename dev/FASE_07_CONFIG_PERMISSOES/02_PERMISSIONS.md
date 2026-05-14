# Tarefa 07.02 - Sistema de Permissoes

**Status**: PENDENTE
**Fase**: 07 - Config + Permissoes
**Dependencias**: 07.01 (config), 02.02 (Tool ABC)
**Bloqueia**: FASE 08 (Agent loop chama PermissionManager.check antes de executar)

---

## Objetivo

Implementar `src/vulpcode/permissions.py` com `PermissionManager` que decide
para cada tool call se: (a) executa direto, (b) pergunta ao usuario, (c) bloqueia.

---

## Descricao Tecnica

### Decisao

```python
@dataclass
class PermissionDecision:
    allow: bool
    requires_prompt: bool
    reason: str
```

### Modos

```python
class Mode(StrEnum):
    DEFAULT = "default"   # respeita requires_confirm da tool
    AUTO = "auto"         # auto-aprova tudo (perigoso)
    SAFE = "safe"         # confirma ate reads
    PLAN = "plan"         # bloqueia tudo (so planeja)
```

### Logica

```python
class PermissionManager:
    def __init__(
        self,
        config: dict,
        mode: Mode = Mode.DEFAULT,
        prompter: Callable[[str, dict], Awaitable[str]] | None = None,
    ): ...

    async def check(self, tool_call: ToolCall, tool_cls: type[Tool]) -> PermissionDecision: ...
```

A funcao `prompter` e injetada (assim a UI pode plugar a sua propria forma de
perguntar — em FASE 09 com Rich, ou stdin simples em testes/headless).

A interface do prompter:
- input: `(message, context_dict) -> Awaitable[str]` retornando uma das chaves:
  - `"y"` -> aprova esta vez
  - `"a"` -> aprova esta tool nesta sessao (memoria de sessao)
  - `"n"` -> rejeita
  - `"e"` -> editar (futuro; v1 trata como "n")

### Estrutura

**`src/vulpcode/permissions.py`**:

```python
"""Permission system for tool execution."""
from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from enum import StrEnum
from typing import Awaitable, Callable

from vulpcode.providers import ToolCall
from vulpcode.tools import Tool


class Mode(StrEnum):
    DEFAULT = "default"
    AUTO = "auto"
    SAFE = "safe"
    PLAN = "plan"


@dataclass
class PermissionDecision:
    allow: bool
    requires_prompt: bool
    reason: str


PrompterFn = Callable[[str, dict], Awaitable[str]]


async def stdin_prompter(message: str, ctx: dict) -> str:
    """Default prompter: read y/a/n from stdin (sync, wrapped in executor)."""
    print(f"\n[permission] {message}")
    print("Tool args:", ctx.get("arguments"))
    print("[y] yes once  [a] always for this tool  [n] no")
    loop = asyncio.get_running_loop()
    answer = await loop.run_in_executor(None, sys.stdin.readline)
    answer = (answer or "n").strip().lower()[:1]
    if answer not in {"y", "a", "n"}:
        return "n"
    return answer


class PermissionManager:
    def __init__(
        self,
        config: dict,
        mode: Mode = Mode.DEFAULT,
        prompter: PrompterFn | None = None,
    ) -> None:
        self.config = config
        self.mode = mode
        self.prompter = prompter or stdin_prompter
        # Tools the user opted into "always allow" for this session
        self._session_allowlist: set[str] = set(
            (config.get("permissions", {}) or {}).get("always_allow_tools", []) or []
        )

    async def check(self, tool_call: ToolCall, tool_cls: type[Tool]) -> PermissionDecision:
        if self.mode == Mode.AUTO:
            return PermissionDecision(True, False, "auto mode")
        if self.mode == Mode.PLAN:
            return PermissionDecision(False, False, "plan mode (no execution)")

        # SAFE: confirm everything (even reads)
        # DEFAULT: confirm only when tool requires it
        requires = tool_cls._requires_confirm
        if self.mode == Mode.SAFE:
            requires = True

        if not requires:
            return PermissionDecision(True, False, "no confirmation needed")

        if tool_call.name in self._session_allowlist:
            return PermissionDecision(True, False, "session allowlist")

        # Need to prompt
        msg = f"Tool {tool_call.name!r} wants to run."
        ctx = {"name": tool_call.name, "arguments": tool_call.arguments}
        try:
            answer = await self.prompter(msg, ctx)
        except Exception:
            return PermissionDecision(False, False, "prompt failed")

        if answer == "y":
            return PermissionDecision(True, True, "user approved once")
        if answer == "a":
            self._session_allowlist.add(tool_call.name)
            return PermissionDecision(True, True, "user approved always")
        return PermissionDecision(False, True, "user rejected")
```

---

## INSTRUCAO CRITICA

- O `prompter` e injetavel. Em FASE 09, a UI passa um prompter Rich-aware. Em
  testes, passamos um lambda que retorna `"y"`, `"a"`, ou `"n"`. O default
  `stdin_prompter` cobre o caso headless.
- O `_session_allowlist` comeca com `always_allow_tools` do config — usuario
  pode pre-aprovar tools.
- Modos sao mutuamente exclusivos: AUTO > PLAN > SAFE > DEFAULT em precedencia
  de logica.
- `PLAN` bloqueia TUDO — incluindo Read. Util para "modo dry-run".
- O resultado e um `PermissionDecision`, nao um boolean — facilita UI e logging.

---

## Etapas de Implementacao

### Etapa 1: Criar `permissions.py`

### Etapa 2: Criar `tests/test_permissions.py`

```python
import pytest

from pydantic import BaseModel

from vulpcode.permissions import Mode, PermissionManager, stdin_prompter
from vulpcode.providers import ToolCall
from vulpcode.tools import Tool, ToolResult, tool, clear_registry


@pytest.fixture
def safe_tool():
    clear_registry()

    @tool(name="ReadX", description="r", requires_confirm=False)
    class T(Tool):
        class Input(BaseModel):
            pass
        async def run(self, args):
            return ToolResult()
    yield T
    clear_registry()


@pytest.fixture
def write_tool():
    clear_registry()

    @tool(name="WriteX", description="w", requires_confirm=True)
    class T(Tool):
        class Input(BaseModel):
            pass
        async def run(self, args):
            return ToolResult()
    yield T
    clear_registry()


@pytest.mark.asyncio
async def test_default_allows_safe_tools(safe_tool):
    pm = PermissionManager(config={}, mode=Mode.DEFAULT)
    d = await pm.check(ToolCall(id="1", name="ReadX", arguments={}), safe_tool)
    assert d.allow and not d.requires_prompt


@pytest.mark.asyncio
async def test_default_prompts_for_destructive(write_tool):
    answers = iter(["y"])
    async def fake(msg, ctx): return next(answers)
    pm = PermissionManager(config={}, mode=Mode.DEFAULT, prompter=fake)
    d = await pm.check(ToolCall(id="1", name="WriteX", arguments={}), write_tool)
    assert d.allow


@pytest.mark.asyncio
async def test_default_user_rejects(write_tool):
    async def no(msg, ctx): return "n"
    pm = PermissionManager(config={}, mode=Mode.DEFAULT, prompter=no)
    d = await pm.check(ToolCall(id="1", name="WriteX", arguments={}), write_tool)
    assert not d.allow


@pytest.mark.asyncio
async def test_always_persists_in_session(write_tool):
    answers = iter(["a", "x"])  # second call should not call prompter
    async def fake(msg, ctx): return next(answers)
    pm = PermissionManager(config={}, mode=Mode.DEFAULT, prompter=fake)
    d1 = await pm.check(ToolCall(id="1", name="WriteX", arguments={}), write_tool)
    d2 = await pm.check(ToolCall(id="2", name="WriteX", arguments={}), write_tool)
    assert d1.allow and d2.allow


@pytest.mark.asyncio
async def test_auto_mode_allows_everything(write_tool):
    pm = PermissionManager(config={}, mode=Mode.AUTO)
    d = await pm.check(ToolCall(id="1", name="WriteX", arguments={}), write_tool)
    assert d.allow and not d.requires_prompt


@pytest.mark.asyncio
async def test_plan_mode_blocks_everything(safe_tool):
    pm = PermissionManager(config={}, mode=Mode.PLAN)
    d = await pm.check(ToolCall(id="1", name="ReadX", arguments={}), safe_tool)
    assert not d.allow


@pytest.mark.asyncio
async def test_safe_mode_prompts_for_safe_tool(safe_tool):
    answers = iter(["y"])
    async def fake(msg, ctx): return next(answers)
    pm = PermissionManager(config={}, mode=Mode.SAFE, prompter=fake)
    d = await pm.check(ToolCall(id="1", name="ReadX", arguments={}), safe_tool)
    assert d.allow and d.requires_prompt


@pytest.mark.asyncio
async def test_config_allowlist(write_tool):
    pm = PermissionManager(
        config={"permissions": {"always_allow_tools": ["WriteX"]}},
        mode=Mode.DEFAULT,
    )
    d = await pm.check(ToolCall(id="1", name="WriteX", arguments={}), write_tool)
    assert d.allow
```

### Etapa 3: Rodar testes

```bash
pytest tests/test_permissions.py -v
```

---

## Criterios de Aceite

- [x] `src/vulpcode/permissions.py` com `Mode`, `PermissionDecision`, `PermissionManager`, `stdin_prompter`
- [x] Modo `DEFAULT` respeita `requires_confirm` da tool
- [x] Modo `AUTO` aprova tudo
- [x] Modo `SAFE` confirma ate reads
- [x] Modo `PLAN` bloqueia tudo
- [x] Resposta `"y"` aprova uma vez, `"a"` adiciona ao session allowlist
- [x] `always_allow_tools` do config inicializa o session allowlist
- [x] Prompter injetavel via construtor
- [x] `tests/test_permissions.py` com >=7 testes, todos passando

---

## Riscos Tecnicos

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|---------------|---------|-----------|
| Stdin bloqueia em headless | Alta | Alto | Em --print mode usar Mode.AUTO ou abortar |
| Race em prompts concorrentes | Baixa | Medio | Tools chamadas serialmente (FASE 08) |
| Escape para shell injection | N/A | N/A | Permissions nao executa nada — so decide |

---

**End of Specification**
