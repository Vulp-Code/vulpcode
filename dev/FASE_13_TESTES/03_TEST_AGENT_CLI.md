# Tarefa 13.03 - Testes do Agent e CLI Integrados

**Status**: PENDENTE
**Fase**: 13 - Testes
**Dependencias**: FASE 08, 09, 10
**Bloqueia**: Nada

---

## Objetivo

Aumentar cobertura nos modulos `agent.py`, `app.py`, `cli.py`, `permissions.py`,
`session.py` e `commands/`. Adicionar testes de integracao que cobrem o fluxo
end-to-end do CLI usando `Provider` e `Tool` mocks.

---

## Descricao Tecnica

### Cobertura adicional necessaria

1. **Agent**: tool denied, multi-tool calls em uma resposta, tool call que
   falha, ErrorEvent do provider.
2. **CLI**: `vulp providers`, `vulp --version`, `vulp config` (sem executar
   editor), `vulp <prompt> --print` (com mock provider).
3. **Permissions**: modo SAFE com prompter declinando, allowlist persistente.
4. **Commands**: `/provider <novo>` troca, `/model <m>` define, `/save`/`/load`
   round-trip via `session.py` real.

### Testes adicionais

**`tests/test_agent_extended.py`**:

```python
from typing import AsyncIterator
import pytest
from pydantic import BaseModel

from vulpcode.agent import (
    Agent,
    ErrorEvent,
    ToolDeniedEvent,
    ToolEndEvent,
    TurnEndEvent,
)
from vulpcode.permissions import Mode, PermissionManager
from vulpcode.providers.base import Provider, StreamChunk, ToolCall
from vulpcode.tools import Tool, ToolResult, clear_registry, tool


class ScriptedProvider(Provider):
    name = "scripted"
    def __init__(self, scripts):
        super().__init__()
        self.scripts = list(scripts)
    async def stream(self, messages, tools, model, system=None, **kwargs) -> AsyncIterator[StreamChunk]:
        if not self.scripts:
            yield StreamChunk(type="stop")
            return
        for c in self.scripts.pop(0):
            yield c
    def supports_tools(self): return True
    def supports_vision(self): return False


@pytest.mark.asyncio
async def test_agent_handles_denied_tool():
    clear_registry()

    @tool(name="Risky", description="r", requires_confirm=True)
    class T(Tool):
        class Input(BaseModel):
            x: int
        async def run(self, args):
            return ToolResult(output=str(args.x))

    tc = ToolCall(id="t", name="Risky", arguments={"x": 1})
    p = ScriptedProvider([
        [StreamChunk(type="tool_call", tool_call=tc), StreamChunk(type="stop")],
        [StreamChunk(type="text", delta="ok"), StreamChunk(type="stop")],
    ])

    async def reject(msg, ctx): return "n"
    perms = PermissionManager(config={}, mode=Mode.DEFAULT, prompter=reject)
    a = Agent(provider=p, tools=[T()], permissions=perms)
    events = [ev async for ev in a.turn("?")]
    assert any(isinstance(ev, ToolDeniedEvent) for ev in events)
    clear_registry()


@pytest.mark.asyncio
async def test_agent_multi_tool_calls_in_one_response():
    clear_registry()

    @tool(name="One", description="o")
    class T(Tool):
        class Input(BaseModel):
            v: int
        async def run(self, args):
            return ToolResult(output=f"got {args.v}")

    tc1 = ToolCall(id="a", name="One", arguments={"v": 1})
    tc2 = ToolCall(id="b", name="One", arguments={"v": 2})
    p = ScriptedProvider([
        [StreamChunk(type="tool_call", tool_call=tc1),
         StreamChunk(type="tool_call", tool_call=tc2),
         StreamChunk(type="stop")],
        [StreamChunk(type="text", delta="done"), StreamChunk(type="stop")],
    ])
    a = Agent(provider=p, tools=[T()])
    ends = [e for e in [ev async for ev in a.turn("?")] if isinstance(e, ToolEndEvent)]
    assert len(ends) == 2
    clear_registry()


@pytest.mark.asyncio
async def test_agent_tool_run_raises():
    clear_registry()

    @tool(name="Boom", description="b")
    class T(Tool):
        class Input(BaseModel): pass
        async def run(self, args):
            raise RuntimeError("kaboom")

    tc = ToolCall(id="t", name="Boom", arguments={})
    p = ScriptedProvider([
        [StreamChunk(type="tool_call", tool_call=tc), StreamChunk(type="stop")],
        [StreamChunk(type="text", delta="recovered"), StreamChunk(type="stop")],
    ])
    a = Agent(provider=p, tools=[T()])
    ends = [e for e in [ev async for ev in a.turn("?")] if isinstance(e, ToolEndEvent)]
    assert len(ends) == 1
    assert ends[0].result.is_error
    assert "kaboom" in (ends[0].result.error or "")
    clear_registry()


@pytest.mark.asyncio
async def test_agent_provider_stream_error():
    p = ScriptedProvider([
        [StreamChunk(type="error", error="rate limit")],
    ])
    a = Agent(provider=p, tools=[])
    events = [ev async for ev in a.turn("?")]
    assert any(isinstance(e, ErrorEvent) and "rate limit" in e.error for e in events)
```

**`tests/test_cli_extended.py`**:

```python
from typer.testing import CliRunner

from vulpcode.cli import app


runner = CliRunner()


def test_cli_version():
    r = runner.invoke(app, ["--version"])
    assert r.exit_code == 0
    assert "0.1.0" in r.stdout


def test_cli_providers_after_registry():
    r = runner.invoke(app, ["providers"])
    assert r.exit_code == 0
    assert "anthropic" in r.stdout
    assert "ollama" in r.stdout


def test_cli_help_lists_subcommands():
    r = runner.invoke(app, ["--help"])
    assert r.exit_code == 0
    assert "config" in r.stdout
    assert "providers" in r.stdout
```

**`tests/test_permissions_extended.py`** (se nao coberto na FASE 07.02):

```python
import pytest

from pydantic import BaseModel

from vulpcode.permissions import Mode, PermissionManager
from vulpcode.providers.base import ToolCall
from vulpcode.tools import Tool, ToolResult, clear_registry, tool


@pytest.mark.asyncio
async def test_safe_mode_prompts_for_read_tool():
    clear_registry()
    @tool(name="ReadX", description="r")
    class T(Tool):
        class Input(BaseModel): pass
        async def run(self, args): return ToolResult()
    answers = iter(["n"])
    async def reject(msg, ctx): return next(answers)
    pm = PermissionManager(config={}, mode=Mode.SAFE, prompter=reject)
    d = await pm.check(ToolCall(id="x", name="ReadX", arguments={}), T)
    assert not d.allow
    clear_registry()
```

### Cobertura final

```bash
pytest --cov=src/vulpcode --cov-report=term-missing tests/
```

Meta: cobertura global >= 70%. Modulos chave (agent, providers, tools, config,
permissions) >= 80%.

---

## INSTRUCAO CRITICA

- Reaproveitar `ScriptedProvider` ja em uso. Nao criar mocks novos para cada
  arquivo de teste — extrair para `tests/conftest.py` se necessario.
- Para CLI, `CliRunner` do Typer — nao chamar `subprocess.run` direto.
- Cobertura nao precisa ser 100% — buscar 70-80%, identificar trechos
  inalcancaveis (error paths exoticos) e ignorar.

---

## Etapas de Implementacao

### Etapa 1: Criar `tests/test_agent_extended.py`

### Etapa 2: Criar `tests/test_cli_extended.py`

### Etapa 3: Criar testes adicionais para `permissions.py` se cobertura abaixo de 80%

### Etapa 4: Considerar criar `tests/conftest.py` com `ScriptedProvider` reutilizavel

```python
# tests/conftest.py
from typing import AsyncIterator
import pytest

from vulpcode.providers.base import Provider, StreamChunk


class ScriptedProvider(Provider):
    name = "scripted"
    def __init__(self, scripts=None):
        super().__init__()
        self.scripts = list(scripts or [])
    async def stream(self, messages, tools, model, system=None, **kwargs) -> AsyncIterator[StreamChunk]:
        if not self.scripts:
            yield StreamChunk(type="stop"); return
        for c in self.scripts.pop(0): yield c
    def supports_tools(self): return True
    def supports_vision(self): return False


@pytest.fixture
def scripted_provider():
    def factory(scripts):
        return ScriptedProvider(scripts)
    return factory
```

### Etapa 5: Rodar coverage final

```bash
pytest --cov=src/vulpcode --cov-report=html tests/
open htmlcov/index.html  # opcional
```

---

## Criterios de Aceite

- [x] `tests/test_agent_extended.py` com >=4 testes adicionais, todos passando
- [x] `tests/test_cli_extended.py` com >=3 testes, todos passando
- [x] `tests/conftest.py` (opcional) com `ScriptedProvider` fixture reutilizavel
- [x] Cobertura global >= 70% (`pytest --cov`)
- [x] Cobertura de `agent.py`, `permissions.py`, `tools/base.py` >= 80%
- [x] Toda a suite passa (`pytest tests/`)

---

## Riscos Tecnicos

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|---------------|---------|-----------|
| Testes flaky se rodam em paralelo | Media | Baixo | clear_registry() em cada teste de tools |
| CliRunner nao captura asyncio.run | Baixa | Medio | Tipper testou; aceitar |
| Cobertura abaixo de 70% | Baixa | Medio | Adicionar testes pontuais |

---

**End of Specification**
