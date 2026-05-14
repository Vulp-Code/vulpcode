# Tarefa 04.04 - Tool Glob

**Status**: PENDENTE
**Fase**: 04 - Tools Filesystem
**Dependencias**: 02.02
**Bloqueia**: Nada

---

## Objetivo

Implementar a tool `Glob` em `src/vulpcode/tools/glob.py`. Faz match de arquivos
por padrao tipo `**/*.py` (estilo gitignore/glob), retorna lista ordenada por
mtime decrescente (arquivos modificados mais recentemente primeiro).

---

## Descricao Tecnica

### Comportamento

- Padrao usa sintaxe glob padrao: `*`, `**`, `?`, `[abc]`.
- `**` matches zero ou mais diretorios (recursivo).
- `path` opcional: diretorio base para a busca (default: `cwd`).
- Retorna lista de paths absolutos, um por linha.
- Ordena por `stat().st_mtime` decrescente.
- Limita a 100 resultados; se truncado, anuncia no output.
- Ignora erros de permissao silenciosamente (continua a busca).

### Schema

```python
class Input(BaseModel):
    pattern: str
    path: str | None = None  # base directory; default: cwd
```

### Estrutura

**`src/vulpcode/tools/glob.py`**:

```python
"""Glob tool: pattern-match files with recursive ** support."""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from vulpcode.tools.base import Tool, ToolResult, tool


_MAX_RESULTS = 100


@tool(
    name="Glob",
    description=(
        "Find files by glob pattern. Supports * ? [abc] and ** for recursive match. "
        "Returns absolute paths sorted by modification time (newest first)."
    ),
    requires_confirm=False,
)
class GlobTool(Tool):
    class Input(BaseModel):
        pattern: str
        path: str | None = None

    async def run(self, args: BaseModel) -> ToolResult:  # type: ignore[override]
        assert isinstance(args, GlobTool.Input)
        base = Path(args.path).expanduser().resolve() if args.path else Path.cwd()
        if not base.exists():
            return ToolResult(error=f"Base path does not exist: {base}", is_error=True)
        if not base.is_dir():
            return ToolResult(error=f"Base path is not a directory: {base}", is_error=True)

        try:
            matches = list(base.glob(args.pattern))
        except (OSError, ValueError) as exc:
            return ToolResult(error=f"Glob failed: {exc}", is_error=True)

        files: list[tuple[float, Path]] = []
        for p in matches:
            try:
                if p.is_file():
                    files.append((p.stat().st_mtime, p))
            except OSError:
                continue

        files.sort(reverse=True)
        truncated = len(files) > _MAX_RESULTS
        files = files[:_MAX_RESULTS]

        if not files:
            return ToolResult(
                output=f"No files match {args.pattern!r} under {base}",
                metadata={"base": str(base), "pattern": args.pattern, "matches": 0},
            )

        body = "\n".join(str(p) for _, p in files)
        if truncated:
            body += f"\n[truncated to {_MAX_RESULTS} most recent matches]"

        return ToolResult(
            output=body,
            metadata={
                "base": str(base),
                "pattern": args.pattern,
                "matches": len(files),
                "truncated": truncated,
            },
        )
```

### Atualizar `tools/__init__.py`

```python
from vulpcode.tools import glob as _glob  # noqa: F401
```

---

## INSTRUCAO CRITICA

- Usar `Path.glob()` e nao `pathlib.Path.rglob` ou `glob.glob`. Path.glob
  suporta `**` quando o usuario inclui no padrao.
- Excluir diretorios — apenas arquivos. Diretorios em matches sao filtrados via
  `p.is_file()`.
- Capturar erros de stat (arquivo deletado entre glob e stat) silenciosamente.
- Truncamento: ordenar primeiro, depois limitar a 100. Anuncar no output e
  metadata.
- Se nao encontrar nada, retornar `output` com mensagem "No files match...",
  NAO erro — busca vazia e resultado valido.

---

## Etapas de Implementacao

### Etapa 1: Criar `tools/glob.py`

### Etapa 2: Atualizar `tools/__init__.py`

### Etapa 3: Criar `tests/test_tools/test_glob.py`

```python
import os
import time
from pathlib import Path

import pytest

import vulpcode.tools  # noqa
from vulpcode.tools import get_tool


@pytest.mark.asyncio
async def test_glob_finds_files(tmp_path: Path):
    (tmp_path / "a.py").write_text("a")
    (tmp_path / "b.py").write_text("b")
    (tmp_path / "c.txt").write_text("c")
    cls = get_tool("Glob")
    res = await cls().run(cls.Input(pattern="*.py", path=str(tmp_path)))
    assert res.is_error is False
    assert "a.py" in res.output
    assert "b.py" in res.output
    assert "c.txt" not in res.output


@pytest.mark.asyncio
async def test_glob_recursive(tmp_path: Path):
    (tmp_path / "x").mkdir()
    (tmp_path / "x" / "deep.py").write_text("z")
    (tmp_path / "top.py").write_text("z")
    cls = get_tool("Glob")
    res = await cls().run(cls.Input(pattern="**/*.py", path=str(tmp_path)))
    assert "deep.py" in res.output
    assert "top.py" in res.output


@pytest.mark.asyncio
async def test_glob_sorted_by_mtime(tmp_path: Path):
    a = tmp_path / "a.py"
    b = tmp_path / "b.py"
    a.write_text("a")
    time.sleep(0.05)
    b.write_text("b")
    # bump b's mtime to be definitely newer
    new_b = time.time()
    os.utime(b, (new_b, new_b))
    new_a = new_b - 10
    os.utime(a, (new_a, new_a))
    cls = get_tool("Glob")
    res = await cls().run(cls.Input(pattern="*.py", path=str(tmp_path)))
    lines = res.output.splitlines()
    assert lines[0].endswith("b.py")
    assert lines[1].endswith("a.py")


@pytest.mark.asyncio
async def test_glob_no_matches(tmp_path: Path):
    cls = get_tool("Glob")
    res = await cls().run(cls.Input(pattern="*.nope", path=str(tmp_path)))
    assert res.is_error is False
    assert "No files match" in res.output


@pytest.mark.asyncio
async def test_glob_invalid_path(tmp_path: Path):
    cls = get_tool("Glob")
    res = await cls().run(cls.Input(pattern="*", path=str(tmp_path / "nope")))
    assert res.is_error


@pytest.mark.asyncio
async def test_glob_excludes_directories(tmp_path: Path):
    (tmp_path / "subdir").mkdir()
    (tmp_path / "f.txt").write_text("x")
    cls = get_tool("Glob")
    res = await cls().run(cls.Input(pattern="*", path=str(tmp_path)))
    assert "f.txt" in res.output
    assert "subdir" not in res.output
```

### Etapa 4: Rodar testes

```bash
pytest tests/test_tools/test_glob.py -v
```

---

## Criterios de Aceite

- [x] `src/vulpcode/tools/glob.py` implementa `GlobTool`
- [x] Suporta `*`, `**`, `?`, `[abc]`
- [x] `path` opcional (default: cwd)
- [x] Filtra apenas arquivos (excluir diretorios)
- [x] Ordena por mtime decrescente
- [x] Trunca a 100 resultados com aviso
- [x] No-match retorna output informativo, nao erro
- [x] `requires_confirm=False`
- [x] `tools/__init__.py` importa `glob.py`
- [x] `tests/test_tools/test_glob.py` com >=6 testes, todos passando

---

## Riscos Tecnicos

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|---------------|---------|-----------|
| Glob recursivo muito caro em /home | Alta | Medio | Truncamento e default cwd; usuario deve especificar path |
| Race condition stat -> glob | Baixa | Baixo | try/except OSError no stat |
| Padroes invalidos | Baixa | Baixo | Capturar ValueError do Path.glob |

---

**End of Specification**
