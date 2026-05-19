# Tarefa 06.01 — Testes integrados e e2e

**Status**: CONCLUÍDA
**Fase**: 06 - Testes
**Dependências**: FASE_01 a FASE_05 concluídas
**Bloqueia**: FASE_07_DOCS

---

## Objetivo

Cobrir a integração das peças com testes que **não dependem do endpoint corporativo real**:

1. **Integração agent + provider mockado**: simula a resposta-texto do endpoint, garante
   que o provider parseia, o agente dispatcha, a tool executa, o resultado volta como
   `<vulp:tool_result>` e o ciclo termina.
2. **Loop de reparo end-to-end**: mock retorna primeiro um Python com `SyntaxError`,
   recebe `is_error=true`, retorna versão corrigida → arquivo final é válido.
3. **Smoke contra endpoint real**: teste opcional rodado quando
   `VULP_INTERNAL_LLM_E2E=1` está setado.

Os testes unitários por-tool já existem (tarefas 04–07). Aqui foca em **integração**.

---

## Estrutura de Testes

### `tests/test_providers/test_agentic_integration.py`

```python
"""Mock the HTTP layer of InternalLLMAgenticProvider and drive the full agent loop."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import respx
import httpx

# Make sure every tool is registered
import vulpcode.tools  # noqa
import vulpcode.tools.write_py  # noqa

from vulpcode.agent import Agent, TextEvent, ToolEndEvent, TurnEndEvent
from vulpcode.permissions import Mode, PermissionManager
from vulpcode.providers.internal_llm_agentic import InternalLLMAgenticProvider
from vulpcode.tools import list_tools


ENDPOINT = "http://fake.corp/chatCompletion"


def _wrap(text: str) -> dict:
    return {"data": text}


@pytest.fixture
def provider():
    return InternalLLMAgenticProvider(
        base_url=ENDPOINT,
        user_uuid="00000000-0000-0000-0000-000000000000",
        max_retries=1,
    )


@respx.mock
@pytest.mark.asyncio
async def test_one_shot_write_py(tmp_path, provider):
    target = tmp_path / "hello.py"
    response_text = f"""\
<vulp:tool name="WritePy">
  <vulp:arg name="file_path">{target}</vulp:arg>
  <vulp:content name="content">
print("hello")
  </vulp:content>
</vulp:tool>
"""
    respx.post(ENDPOINT).mock(
        return_value=httpx.Response(200, json=_wrap(response_text))
    )
    agent = Agent(
        provider=provider,
        tools=[cls() for cls in list_tools()],
        model="internal-llm-agentic",
        permissions=PermissionManager(config={}, mode=Mode.AUTO),
    )
    events = [ev async for ev in agent.turn("create hello.py that prints hello")]
    assert any(isinstance(e, ToolEndEvent) and not e.result.is_error for e in events)
    assert target.exists()
    assert "hello" in target.read_text()


@respx.mock
@pytest.mark.asyncio
async def test_repair_loop_recovers_from_syntax_error(tmp_path, provider):
    target = tmp_path / "fib.py"
    # First response: code with a SyntaxError
    bad = f"""\
<vulp:tool name="WritePy">
  <vulp:arg name="file_path">{target}</vulp:arg>
  <vulp:content name="content">
def fib(n):
    a, b = 0 1
    for _ in range(n):
        print(a)
        a, b = b, a + b
  </vulp:content>
</vulp:tool>
"""
    # Second response: corrected
    good = f"""\
<vulp:tool name="WritePy">
  <vulp:arg name="file_path">{target}</vulp:arg>
  <vulp:content name="content">
def fib(n):
    a, b = 0, 1
    for _ in range(n):
        print(a)
        a, b = b, a + b
  </vulp:content>
</vulp:tool>
"""
    # Third response: ack (no tool)
    ack = "Done."

    respx.post(ENDPOINT).mock(side_effect=[
        httpx.Response(200, json=_wrap(bad)),
        httpx.Response(200, json=_wrap(good)),
        httpx.Response(200, json=_wrap(ack)),
    ])

    agent = Agent(
        provider=provider,
        tools=[cls() for cls in list_tools()],
        model="internal-llm-agentic",
        permissions=PermissionManager(config={}, mode=Mode.AUTO),
    )
    events = [ev async for ev in agent.turn("create fibonacci script")]

    tool_ends = [e for e in events if isinstance(e, ToolEndEvent)]
    assert len(tool_ends) == 2
    assert tool_ends[0].result.is_error is True   # first attempt fails validation
    assert "SyntaxError" in tool_ends[0].result.error
    assert tool_ends[1].result.is_error is False  # second attempt succeeds
    assert target.exists()
    src = target.read_text()
    # Verify the GOOD version was saved (with the comma)
    assert "0, 1" in src


@respx.mock
@pytest.mark.asyncio
async def test_parse_error_surfaces_as_text(tmp_path, provider):
    """Malformed tool block: parser should not crash; text feedback to the model."""
    response_text = """\
<vulp:tool name="WritePy">
  <vulp:arg name="file_path">/tmp/x.py</vulp:arg>
  <vulp:content name="content">
print("hi")
  -- MISSING </vulp:content> AND </vulp:tool>
"""
    respx.post(ENDPOINT).mock(
        return_value=httpx.Response(200, json=_wrap(response_text))
    )
    agent = Agent(
        provider=provider,
        tools=[cls() for cls in list_tools()],
        model="internal-llm-agentic",
        permissions=PermissionManager(config={}, mode=Mode.AUTO),
    )
    events = [ev async for ev in agent.turn("...")]
    # No ToolEndEvent (parser dropped the malformed block)
    assert not any(isinstance(e, ToolEndEvent) for e in events)
    # But agent should still complete with a TurnEnd (text-only response)
    assert any(isinstance(e, TurnEndEvent) for e in events)
```

---

### `tests/test_providers/test_agentic_e2e_real.py` (opt-in)

```python
"""E2E test against the real corporate endpoint. Skipped by default.

Enable with: VULP_INTERNAL_LLM_E2E=1 pytest tests/test_providers/test_agentic_e2e_real.py -v
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

import vulpcode.tools  # noqa
import vulpcode.tools.write_py  # noqa
from vulpcode.agent import Agent, ToolEndEvent
from vulpcode.permissions import Mode, PermissionManager
from vulpcode.providers.internal_llm_agentic import InternalLLMAgenticProvider
from vulpcode.tools import list_tools


pytestmark = pytest.mark.skipif(
    os.environ.get("VULP_INTERNAL_LLM_E2E") != "1",
    reason="Set VULP_INTERNAL_LLM_E2E=1 to run E2E against the real endpoint",
)


@pytest.mark.asyncio
async def test_real_endpoint_creates_python_file(tmp_path: Path):
    endpoint = os.environ["INTERNAL_LLM_ENDPOINT"]
    uuid_val = os.environ["INTERNAL_LLM_USER_UUID"]
    provider = InternalLLMAgenticProvider(
        base_url=endpoint, user_uuid=uuid_val,
    )
    agent = Agent(
        provider=provider,
        tools=[cls() for cls in list_tools()],
        model="internal-llm-agentic",
        permissions=PermissionManager(config={}, mode=Mode.AUTO),
    )
    target = tmp_path / "hello.py"
    prompt = (
        f'Create a Python script at {target} that, when run, prints "hello, world". '
        "Use the WritePy tool."
    )
    saw_success = False
    async for ev in agent.turn(prompt):
        if isinstance(ev, ToolEndEvent) and not ev.result.is_error:
            saw_success = True
    assert saw_success
    assert target.exists()
    assert "hello" in target.read_text().lower()
```

---

## Etapas

### Etapa 1 — Adicionar `respx` em `[dev]` extras

```toml
[project.optional-dependencies]
dev = [..., "respx>=0.20"]
```

### Etapa 2 — Implementar `tests/test_providers/test_agentic_integration.py`

### Etapa 3 — Implementar `tests/test_providers/test_agentic_e2e_real.py` (skip por default)

### Etapa 4 — Rodar suite

```bash
pytest tests/ -v --ignore=tests/test_providers/test_agentic_e2e_real.py
```

E o smoke real, manual:

```bash
export VULP_INTERNAL_LLM_E2E=1
export INTERNAL_LLM_ENDPOINT=...
export INTERNAL_LLM_USER_UUID=...
pytest tests/test_providers/test_agentic_e2e_real.py -v
```

---

## Critérios de Aceite

- [x] `tests/test_providers/test_agentic_integration.py` cobre: happy path, repair loop,
      parse error
- [x] Repair loop test confirma 2 tool runs (1 erro + 1 sucesso) e arquivo final correto
- [x] E2E real existe, skip por default, documentado como ativar
- [x] `respx` adicionado ao extra `dev`
- [x] Suite inteira (sem e2e) passa: `pytest tests/ -v`

---

## Riscos

| Risco | Probabilidade | Mitigação |
|-------|---------------|-----------|
| `respx` versão muda API entre releases | Média | Pinar `>=0.20` |
| Permission mode bloqueia tools no teste | Alta se default | Setar `Mode.AUTO` explicitamente |
| Endpoint real responde lento → flaky e2e | Alta | Timeout generoso (120s); e2e é opt-in, não bloqueia CI |

---

**End of Specification**
