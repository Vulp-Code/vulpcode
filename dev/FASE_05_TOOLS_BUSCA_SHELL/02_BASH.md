# Tarefa 05.02 - Tool Bash

**Status**: PENDENTE
**Fase**: 05 - Tools Busca + Shell
**Dependencias**: 02.02
**Bloqueia**: 05.03 (BashOutput/KillBash precisam do registry de processos em background)

---

## Objetivo

Implementar a tool `Bash` em `src/vulpcode/tools/bash.py`. Executa comando shell
via `asyncio.subprocess`, com timeout configuravel e modo background. Captura
stdout e stderr (mesclados), retorna exit code. Mantem registro de processos
em background para `BashOutput` e `KillBash` consumirem.

---

## Descricao Tecnica

### Comportamento

- `command`: string para executar via `bash -c`.
- `timeout`: ms (default 120000 = 120s, max 600000 = 10min).
- `description`: docstring opcional do que o comando faz (ignorado pelo runtime).
- `run_in_background=True`: spawn e retorna imediatamente com `bash_id`.

### Registry global de processos em background

Compartilhado entre `Bash`, `BashOutput`, `KillBash`. Cada entrada:

```python
{
    "process": asyncio.subprocess.Process,
    "command": str,
    "started_at": float,
    "stdout": list[str],   # buffered lines as they arrive
    "stderr": list[str],
    "exit_code": int | None,
    "stdout_offset": int,  # cursor for incremental reads (BashOutput)
    "stderr_offset": int,
}
```

Implementar isto em `tools/_bash_registry.py` para que tres tools compartilhem
sem dependencia circular.

### Schema (Bash)

```python
class Input(BaseModel):
    command: str
    timeout: int | None = None         # ms
    description: str | None = None
    run_in_background: bool = False
```

### Estrutura

**`src/vulpcode/tools/_bash_registry.py`**:

```python
"""Shared registry for background bash processes."""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field


@dataclass
class BackgroundProcess:
    bash_id: str
    command: str
    process: asyncio.subprocess.Process
    started_at: float
    stdout: list[str] = field(default_factory=list)
    stderr: list[str] = field(default_factory=list)
    exit_code: int | None = None
    stdout_offset: int = 0
    stderr_offset: int = 0
    _reader_task: asyncio.Task | None = None


_REGISTRY: dict[str, BackgroundProcess] = {}


def new_id() -> str:
    return f"bash_{uuid.uuid4().hex[:8]}"


def register(proc: BackgroundProcess) -> None:
    _REGISTRY[proc.bash_id] = proc


def get(bash_id: str) -> BackgroundProcess | None:
    return _REGISTRY.get(bash_id)


def list_all() -> list[BackgroundProcess]:
    return list(_REGISTRY.values())


def remove(bash_id: str) -> None:
    _REGISTRY.pop(bash_id, None)


def now() -> float:
    return time.time()
```

**`src/vulpcode/tools/bash.py`**:

```python
"""Bash tool: execute shell commands (foreground or background)."""
from __future__ import annotations

import asyncio

from pydantic import BaseModel

from vulpcode.tools._bash_registry import (
    BackgroundProcess,
    new_id,
    now,
    register,
)
from vulpcode.tools.base import Tool, ToolResult, tool


_DEFAULT_TIMEOUT_MS = 120_000
_MAX_TIMEOUT_MS = 600_000
_OUTPUT_LIMIT = 30_000  # chars


@tool(
    name="Bash",
    description=(
        "Run a shell command via bash -c. Supports foreground (default) and "
        "background mode. Foreground waits up to timeout (ms) and returns merged "
        "stdout+stderr. Background returns immediately with a bash_id for use with "
        "BashOutput / KillBash."
    ),
    requires_confirm=True,
)
class BashTool(Tool):
    class Input(BaseModel):
        command: str
        timeout: int | None = None
        description: str | None = None
        run_in_background: bool = False

    async def run(self, args: BaseModel) -> ToolResult:  # type: ignore[override]
        assert isinstance(args, BashTool.Input)
        timeout_ms = args.timeout or _DEFAULT_TIMEOUT_MS
        if timeout_ms > _MAX_TIMEOUT_MS:
            timeout_ms = _MAX_TIMEOUT_MS

        if args.run_in_background:
            return await self._run_background(args.command)
        return await self._run_foreground(args.command, timeout_ms / 1000.0)

    @staticmethod
    async def _run_foreground(command: str, timeout: float) -> ToolResult:
        try:
            proc = await asyncio.create_subprocess_exec(
                "bash", "-c", command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            return ToolResult(error=f"Failed to spawn bash: {exc}", is_error=True)

        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(), timeout=timeout,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return ToolResult(
                error=f"Command timed out after {timeout}s",
                is_error=True,
                metadata={"command": command, "timeout": True},
            )

        stdout = stdout_b.decode("utf-8", errors="replace")
        stderr = stderr_b.decode("utf-8", errors="replace")
        merged = (stdout + ("\n" if stdout and stderr else "") + stderr)
        if len(merged) > _OUTPUT_LIMIT:
            merged = merged[:_OUTPUT_LIMIT] + f"\n[truncated, full output {len(merged)} chars]"
        if proc.returncode == 0:
            return ToolResult(
                output=merged,
                metadata={"exit_code": 0, "command": command},
            )
        return ToolResult(
            output=merged,
            error=f"Command exited with code {proc.returncode}",
            is_error=True,
            metadata={"exit_code": proc.returncode, "command": command},
        )

    @staticmethod
    async def _run_background(command: str) -> ToolResult:
        try:
            proc = await asyncio.create_subprocess_exec(
                "bash", "-c", command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            return ToolResult(error=f"Failed to spawn bash: {exc}", is_error=True)

        bash_id = new_id()
        bp = BackgroundProcess(
            bash_id=bash_id,
            command=command,
            process=proc,
            started_at=now(),
        )
        register(bp)
        bp._reader_task = asyncio.create_task(_drain(bp))
        return ToolResult(
            output=f"Started background process {bash_id}: {command}",
            metadata={"bash_id": bash_id, "background": True},
        )


async def _drain(bp: BackgroundProcess) -> None:
    """Read stdout/stderr lines into bp.stdout/bp.stderr until the process ends."""
    async def _pump(stream, sink: list[str]) -> None:
        if stream is None:
            return
        while True:
            line = await stream.readline()
            if not line:
                break
            sink.append(line.decode("utf-8", errors="replace").rstrip("\n"))

    await asyncio.gather(
        _pump(bp.process.stdout, bp.stdout),
        _pump(bp.process.stderr, bp.stderr),
    )
    bp.exit_code = await bp.process.wait()
```

### Atualizar `tools/__init__.py`

```python
from vulpcode.tools import bash as _bash  # noqa: F401
```

---

## INSTRUCAO CRITICA

- Usar `bash -c "<command>"` para que pipes, redirecionamentos, expansoes do
  shell funcionem (`grep ... | head`, `cd && ls`, etc).
- Foreground: `asyncio.wait_for` com timeout. Em timeout, `proc.kill()` e
  retornar erro.
- Background: spawn, registrar no `_bash_registry`, criar uma task de drain que
  alimenta os buffers `stdout`/`stderr` ate o processo terminar.
- Output truncado a 30k chars na resposta — descritivo "truncated, full output
  N chars" se passar.
- `requires_confirm=True` — o sistema de permissoes (FASE 07.02) decide se
  pedir confirmacao por commando (pode haver allowlist).
- Nao implementar restricao a comandos perigosos aqui (ex: `rm -rf`); fica para
  a fase de permissoes.

---

## Etapas de Implementacao

### Etapa 1: Criar `tools/_bash_registry.py`

### Etapa 2: Criar `tools/bash.py`

### Etapa 3: Atualizar `tools/__init__.py`

### Etapa 4: Criar `tests/test_tools/test_bash.py`

```python
import asyncio
import pytest

import vulpcode.tools  # noqa
from vulpcode.tools import get_tool
from vulpcode.tools._bash_registry import _REGISTRY, list_all


@pytest.fixture(autouse=True)
def _clean_registry():
    _REGISTRY.clear()
    yield
    _REGISTRY.clear()


@pytest.mark.asyncio
async def test_bash_simple_echo():
    cls = get_tool("Bash")
    res = await cls().run(cls.Input(command="echo hello"))
    assert res.is_error is False
    assert "hello" in res.output


@pytest.mark.asyncio
async def test_bash_nonzero_exit():
    cls = get_tool("Bash")
    res = await cls().run(cls.Input(command="exit 7"))
    assert res.is_error
    assert res.metadata["exit_code"] == 7


@pytest.mark.asyncio
async def test_bash_pipe():
    cls = get_tool("Bash")
    res = await cls().run(cls.Input(command="printf 'a\\nb\\nc\\n' | head -n 2"))
    assert "a" in res.output and "b" in res.output and "c" not in res.output


@pytest.mark.asyncio
async def test_bash_timeout():
    cls = get_tool("Bash")
    res = await cls().run(cls.Input(command="sleep 5", timeout=200))
    assert res.is_error
    assert "timed out" in (res.error or "")


@pytest.mark.asyncio
async def test_bash_background_registers():
    cls = get_tool("Bash")
    res = await cls().run(cls.Input(command="sleep 0.1; echo done", run_in_background=True))
    assert res.is_error is False
    bash_id = res.metadata["bash_id"]
    assert bash_id in {bp.bash_id for bp in list_all()}
    # Wait for completion
    await asyncio.sleep(0.5)


@pytest.mark.asyncio
async def test_bash_stderr_captured():
    cls = get_tool("Bash")
    res = await cls().run(cls.Input(command="echo OUT; echo ERR 1>&2"))
    assert "OUT" in res.output and "ERR" in res.output


def test_bash_requires_confirm():
    cls = get_tool("Bash")
    assert cls._requires_confirm is True
```

### Etapa 5: Rodar testes

```bash
pytest tests/test_tools/test_bash.py -v
```

---

## Criterios de Aceite

- [x] `src/vulpcode/tools/_bash_registry.py` com `BackgroundProcess`, `register`, `get`, `list_all`, `remove`, `new_id`
- [x] `src/vulpcode/tools/bash.py` implementa `BashTool` com `requires_confirm=True`
- [x] Foreground com timeout configuravel (default 120s, max 600s)
- [x] Timeout mata o processo e retorna erro
- [x] Background registra processo, retorna `bash_id`, dreno em task asyncio
- [x] Stdout e stderr sao capturados e mesclados no output
- [x] Exit code != 0 -> `is_error=True`, mas output ainda e retornado
- [x] Output truncado a 30k chars com aviso
- [x] `tools/__init__.py` importa `bash.py`
- [x] `tests/test_tools/test_bash.py` com >=6 testes, todos passando

---

## Riscos Tecnicos

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|---------------|---------|-----------|
| Comando interativo trava | Media | Alto | Timeout cobre |
| Background process zumbi | Baixa | Medio | KillBash da FASE 05.03 limpa |
| Encoding de output (binario) | Media | Baixo | `errors="replace"` |
| `bash` nao disponivel (Windows raw) | Alta | Alto | Documentar suporte apenas em Linux/macOS por ora |

---

**End of Specification**
