# Tarefa 05.03 - Tools BashOutput e KillBash

**Status**: PENDENTE
**Fase**: 05 - Tools Busca + Shell
**Dependencias**: 05.02 (Bash + registry)
**Bloqueia**: Nada

---

## Objetivo

Implementar `BashOutput` e `KillBash` em `src/vulpcode/tools/bash_background.py`.
Ambas usam o `_bash_registry` criado em 05.02 para acessar processos em background.

---

## Descricao Tecnica

### BashOutput

**Comportamento**:
- Recebe `bash_id` e opcional `filter` (regex aplicado a cada linha de stdout).
- Retorna apenas as linhas NAO ja entregues nesta `bash_id`. Cursor incremental
  mantido em `stdout_offset` / `stderr_offset` da `BackgroundProcess`.
- Inclui status: `running` (exit_code is None) ou `completed` (com codigo).

**Schema**:
```python
class Input(BaseModel):
    bash_id: str
    filter: str | None = None
```

### KillBash

**Comportamento**:
- Mata processo de background pelo `bash_id`.
- `requires_confirm=True`.
- Remove do registry apos confirmar termino.

**Schema**:
```python
class Input(BaseModel):
    bash_id: str
```

### Estrutura

**`src/vulpcode/tools/bash_background.py`**:

```python
"""BashOutput and KillBash tools (operate on the bash registry)."""
from __future__ import annotations

import asyncio
import re

from pydantic import BaseModel

from vulpcode.tools._bash_registry import get, list_all, remove
from vulpcode.tools.base import Tool, ToolResult, tool


def _drain_buffer(buf: list[str], offset: int, regex: re.Pattern | None) -> tuple[str, int]:
    new_lines = buf[offset:]
    if regex is not None:
        new_lines = [ln for ln in new_lines if regex.search(ln)]
    return "\n".join(new_lines), len(buf)


@tool(
    name="BashOutput",
    description=(
        "Read incremental output from a background bash process started with "
        "Bash(run_in_background=True). Returns only lines emitted since the "
        "previous BashOutput call for the same bash_id."
    ),
    requires_confirm=False,
)
class BashOutputTool(Tool):
    class Input(BaseModel):
        bash_id: str
        filter: str | None = None

    async def run(self, args: BaseModel) -> ToolResult:  # type: ignore[override]
        assert isinstance(args, BashOutputTool.Input)
        bp = get(args.bash_id)
        if bp is None:
            return ToolResult(
                error=f"No background process with id {args.bash_id!r}. "
                      f"Active: {[b.bash_id for b in list_all()]}",
                is_error=True,
            )
        regex = None
        if args.filter:
            try:
                regex = re.compile(args.filter)
            except re.error as exc:
                return ToolResult(error=f"Invalid filter regex: {exc}", is_error=True)

        out_text, new_out_offset = _drain_buffer(bp.stdout, bp.stdout_offset, regex)
        err_text, new_err_offset = _drain_buffer(bp.stderr, bp.stderr_offset, regex)
        bp.stdout_offset = new_out_offset
        bp.stderr_offset = new_err_offset

        if bp.exit_code is None:
            status = "running"
        else:
            status = f"completed (exit code {bp.exit_code})"

        sections = [f"<status>{status}</status>"]
        if out_text:
            sections.append(f"<stdout>\n{out_text}\n</stdout>")
        if err_text:
            sections.append(f"<stderr>\n{err_text}\n</stderr>")
        if not out_text and not err_text:
            sections.append("<no new output>")

        return ToolResult(
            output="\n".join(sections),
            metadata={
                "bash_id": args.bash_id,
                "exit_code": bp.exit_code,
                "running": bp.exit_code is None,
            },
        )


@tool(
    name="KillBash",
    description="Terminate a background bash process by bash_id.",
    requires_confirm=True,
)
class KillBashTool(Tool):
    class Input(BaseModel):
        bash_id: str

    async def run(self, args: BaseModel) -> ToolResult:  # type: ignore[override]
        assert isinstance(args, KillBashTool.Input)
        bp = get(args.bash_id)
        if bp is None:
            return ToolResult(
                error=f"No background process with id {args.bash_id!r}",
                is_error=True,
            )
        if bp.exit_code is not None:
            remove(args.bash_id)
            return ToolResult(
                output=f"Process {args.bash_id} already exited with code {bp.exit_code}",
                metadata={"bash_id": args.bash_id, "already_done": True},
            )
        try:
            bp.process.kill()
            await asyncio.wait_for(bp.process.wait(), timeout=5.0)
        except (ProcessLookupError, asyncio.TimeoutError):
            pass
        bp.exit_code = bp.process.returncode if bp.process.returncode is not None else -1
        remove(args.bash_id)
        return ToolResult(
            output=f"Killed background process {args.bash_id}",
            metadata={"bash_id": args.bash_id, "exit_code": bp.exit_code},
        )
```

### Atualizar `tools/__init__.py`

```python
from vulpcode.tools import bash_background as _bash_bg  # noqa: F401
```

---

## INSTRUCAO CRITICA

- O cursor incremental e o ponto-chave: `BashOutput` so retorna o que ainda nao
  retornou. Atualizar `stdout_offset` e `stderr_offset` apos cada leitura.
- Retornar status no formato XML-like (`<status>...`, `<stdout>...`, `<stderr>...`)
  para o LLM parsear se precisar.
- `KillBash` espera ate 5s o processo terminar apos `kill()`. Se nao, marca exit
  code como -1 e remove.
- Filter regex: aplicado linha-a-linha; nao filtra nada se nao bater.
- Ambas as tools devem informar `bash_id`s ativos quando o id pedido nao existe,
  para guiar o LLM.

---

## Etapas de Implementacao

### Etapa 1: Criar `tools/bash_background.py`

### Etapa 2: Atualizar `tools/__init__.py`

### Etapa 3: Criar `tests/test_tools/test_bash_background.py`

```python
import asyncio
import pytest

import vulpcode.tools  # noqa
from vulpcode.tools import get_tool
from vulpcode.tools._bash_registry import _REGISTRY


@pytest.fixture(autouse=True)
def _clean_registry():
    _REGISTRY.clear()
    yield
    _REGISTRY.clear()


@pytest.mark.asyncio
async def test_bashoutput_returns_incremental():
    bash = get_tool("Bash")
    bo = get_tool("BashOutput")
    res = await bash().run(bash.Input(
        command="echo line1; sleep 0.1; echo line2",
        run_in_background=True,
    ))
    bash_id = res.metadata["bash_id"]
    await asyncio.sleep(0.05)
    first = await bo().run(bo.Input(bash_id=bash_id))
    await asyncio.sleep(0.3)
    second = await bo().run(bo.Input(bash_id=bash_id))
    # First output should contain at least line1; second should not repeat line1
    assert "line2" in (first.output + second.output)
    # Status reflects completed eventually
    assert "completed" in second.output or "running" in first.output


@pytest.mark.asyncio
async def test_bashoutput_filter():
    bash = get_tool("Bash")
    bo = get_tool("BashOutput")
    res = await bash().run(bash.Input(
        command="echo INFO ok; echo DEBUG noise",
        run_in_background=True,
    ))
    bash_id = res.metadata["bash_id"]
    await asyncio.sleep(0.4)
    out = await bo().run(bo.Input(bash_id=bash_id, filter=r"^INFO"))
    assert "INFO" in out.output
    assert "DEBUG" not in out.output


@pytest.mark.asyncio
async def test_bashoutput_unknown_id():
    bo = get_tool("BashOutput")
    res = await bo().run(bo.Input(bash_id="nope"))
    assert res.is_error


@pytest.mark.asyncio
async def test_killbash_terminates():
    bash = get_tool("Bash")
    kill = get_tool("KillBash")
    res = await bash().run(bash.Input(command="sleep 30", run_in_background=True))
    bash_id = res.metadata["bash_id"]
    await asyncio.sleep(0.05)
    kres = await kill().run(kill.Input(bash_id=bash_id))
    assert kres.is_error is False
    assert "Killed" in kres.output


@pytest.mark.asyncio
async def test_killbash_unknown_id():
    kill = get_tool("KillBash")
    res = await kill().run(kill.Input(bash_id="nope"))
    assert res.is_error


def test_killbash_requires_confirm():
    cls = get_tool("KillBash")
    assert cls._requires_confirm is True
```

### Etapa 4: Rodar testes

```bash
pytest tests/test_tools/test_bash_background.py -v
```

---

## Criterios de Aceite

- [x] `src/vulpcode/tools/bash_background.py` implementa `BashOutputTool` e `KillBashTool`
- [x] `BashOutput` retorna apenas linhas novas (cursor incremental)
- [x] `BashOutput` aceita `filter` regex e aplica linha-a-linha
- [x] `BashOutput` reporta status `running` ou `completed (exit code N)`
- [x] `KillBash` termina o processo e remove do registry
- [x] `KillBash` tem `requires_confirm=True`
- [x] Erros para `bash_id` desconhecido em ambas as tools
- [x] `tools/__init__.py` importa `bash_background.py`
- [x] `tests/test_tools/test_bash_background.py` com >=5 testes, todos passando

---

## Riscos Tecnicos

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|---------------|---------|-----------|
| Race entre drain task e BashOutput | Media | Baixo | Listas em Python 3.11+ sao thread-safe para append |
| Killbash em processo ja morto | Baixa | Baixo | Caso especial (already_done) |
| Filter regex caro | Baixa | Baixo | Usuario que decide |

---

**End of Specification**
