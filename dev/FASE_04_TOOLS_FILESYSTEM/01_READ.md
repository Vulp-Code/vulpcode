# Tarefa 04.01 - Tool Read

**Status**: PENDENTE
**Fase**: 04 - Tools Filesystem
**Dependencias**: 02.02 (Tool ABC)
**Bloqueia**: Nada diretamente

---

## Objetivo

Implementar a tool `Read` em `src/vulpcode/tools/read.py`. Le arquivos do
filesystem com suporte a `offset`/`limit` (linhas), exibe linhas numeradas
no formato `cat -n`, e detecta arquivos binarios para retornar erro descritivo.

---

## Descricao Tecnica

### Comportamento esperado (espelha Claude Code)

- Le ate `limit` linhas (default: 2000) a partir de `offset` (1-based).
- Saida formatada com `tab`-prefixo: `<line_no>\t<content>`.
- Linhas com mais de 2000 caracteres sao truncadas no final.
- Arquivo nao existe -> erro claro.
- Path relativo -> erro instruindo a usar absoluto (ou aceitar com `Path.resolve`?
  decisao: aceitar, mas avisar quando o caminho nao e absoluto). **Decisao final**:
  aceitar relativo silenciosamente (e mais ergonomico).
- Imagens (`.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`): ler bytes, retornar
  `output=""` e `metadata={"image_path": ...}`. O agente decide se usa visao.
  Por enquanto basta retornar mensagem informativa.
- Arquivo vazio: retornar mensagem do tipo `"<file is empty>"`.

### Schema de input

```python
class Input(BaseModel):
    file_path: str
    offset: int | None = None    # 1-based line number to start from
    limit: int | None = None     # max lines to return
```

### Estrutura

**`src/vulpcode/tools/read.py`**:

```python
"""Read tool: reads a file from disk with optional offset/limit."""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from vulpcode.tools.base import Tool, ToolResult, tool


_DEFAULT_LIMIT = 2000
_MAX_LINE_LEN = 2000
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
_BINARY_SAMPLE = 4096


@tool(
    name="Read",
    description=(
        "Read a file from the local filesystem. Supports text files (returned with "
        "line numbers in cat -n format) and identifies image files. Use offset (1-based) "
        "and limit (max lines) for large files."
    ),
    requires_confirm=False,
)
class ReadTool(Tool):
    class Input(BaseModel):
        file_path: str
        offset: int | None = None
        limit: int | None = None

    async def run(self, args: BaseModel) -> ToolResult:  # type: ignore[override]
        assert isinstance(args, ReadTool.Input)
        path = Path(args.file_path).expanduser()

        if not path.exists():
            return ToolResult(
                error=f"File does not exist: {args.file_path}",
                is_error=True,
            )
        if path.is_dir():
            return ToolResult(
                error=f"Path is a directory, not a file: {args.file_path}",
                is_error=True,
            )

        if path.suffix.lower() in _IMAGE_SUFFIXES:
            size = path.stat().st_size
            return ToolResult(
                output=f"<image file: {path.name}, {size} bytes>",
                metadata={"image_path": str(path), "is_image": True, "size": size},
            )

        # Binary detection
        try:
            with path.open("rb") as fh:
                sample = fh.read(_BINARY_SAMPLE)
            if b"\x00" in sample:
                return ToolResult(
                    error=f"File appears to be binary: {args.file_path}",
                    is_error=True,
                )
        except OSError as exc:
            return ToolResult(error=f"Cannot read file: {exc}", is_error=True)

        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return ToolResult(error=f"Cannot read file: {exc}", is_error=True)

        if not text:
            return ToolResult(output="<file is empty>")

        lines = text.splitlines()
        offset = max(args.offset or 1, 1)
        limit = args.limit or _DEFAULT_LIMIT
        end = min(len(lines), offset - 1 + limit)
        slice_ = lines[offset - 1 : end]

        formatted = []
        for i, line in enumerate(slice_, start=offset):
            if len(line) > _MAX_LINE_LEN:
                line = line[:_MAX_LINE_LEN] + "...[truncated]"
            formatted.append(f"{i}\t{line}")

        body = "\n".join(formatted)
        meta = {
            "file_path": str(path),
            "lines_total": len(lines),
            "lines_returned": len(slice_),
            "offset": offset,
        }
        if end < len(lines):
            body += f"\n[truncated: {len(lines) - end} more lines, use offset={end + 1} to continue]"
        return ToolResult(output=body, metadata=meta)
```

### Atualizar `tools/__init__.py`

Importar a tool para que o `@tool` decorator a registre quando o pacote for carregado:

```python
# At the end of tools/__init__.py:
from vulpcode.tools import read as _read  # noqa: F401  (registers ReadTool)
```

(Esta importacao explicita sera repetida para cada nova tool. Em FASE 14
podemos refatorar para usar `pkgutil.iter_modules`, mas a importacao explicita
e mais previsivel agora.)

---

## INSTRUCAO CRITICA

- Sempre usar `Path` (nao `os.path.join`) e `expanduser()` para suportar `~`.
- O output usa `\t` (tab real) entre numero da linha e conteudo. NAO usar
  `f"{i:6d}\t"` — apenas `f"{i}\t{line}"` para ficar mais limpo.
- Para detectar binarios, sample de 4KB suficiente. Presenca de byte 0 (`\x00`)
  e o sinal mais simples.
- `errors="replace"` no `read_text` evita crash em arquivos com encoding misto.
- Imagens: nao tentamos converter ainda — apenas reportamos como metadata. O
  suporte a vision multimodal vira em fase futura.
- O `assert isinstance(args, ReadTool.Input)` ajuda o type-checker; em runtime
  nao deve disparar pois `execute_tool_call` valida antes.

---

## Etapas de Implementacao

### Etapa 1: Criar `tools/read.py`

Conteudo conforme acima.

### Etapa 2: Atualizar `tools/__init__.py`

Adicionar `from vulpcode.tools import read as _read  # noqa: F401`.

### Etapa 3: Criar `tests/test_tools/test_read.py`

```python
"""Tests for the Read tool."""
from pathlib import Path

import pytest
from pydantic import BaseModel

import vulpcode.tools  # noqa: F401  ensure registry populated
from vulpcode.tools import get_tool, execute_tool_call
from vulpcode.providers import ToolCall


@pytest.mark.asyncio
async def test_read_simple_file(tmp_path: Path):
    f = tmp_path / "hello.txt"
    f.write_text("line 1\nline 2\nline 3\n")
    cls = get_tool("Read")
    res = await cls().run(cls.Input(file_path=str(f)))
    assert res.is_error is False
    assert "1\tline 1" in res.output
    assert "3\tline 3" in res.output


@pytest.mark.asyncio
async def test_read_with_offset_limit(tmp_path: Path):
    f = tmp_path / "n.txt"
    f.write_text("\n".join(f"line{i}" for i in range(1, 11)) + "\n")
    cls = get_tool("Read")
    res = await cls().run(cls.Input(file_path=str(f), offset=5, limit=2))
    assert "5\tline5" in res.output
    assert "6\tline6" in res.output
    assert "7\tline7" not in res.output


@pytest.mark.asyncio
async def test_read_missing_file(tmp_path: Path):
    cls = get_tool("Read")
    res = await cls().run(cls.Input(file_path=str(tmp_path / "nope")))
    assert res.is_error
    assert "does not exist" in (res.error or "")


@pytest.mark.asyncio
async def test_read_directory_is_error(tmp_path: Path):
    cls = get_tool("Read")
    res = await cls().run(cls.Input(file_path=str(tmp_path)))
    assert res.is_error


@pytest.mark.asyncio
async def test_read_binary_file_rejected(tmp_path: Path):
    f = tmp_path / "bin.dat"
    f.write_bytes(b"hello\x00world")
    cls = get_tool("Read")
    res = await cls().run(cls.Input(file_path=str(f)))
    assert res.is_error
    assert "binary" in (res.error or "").lower()


@pytest.mark.asyncio
async def test_read_empty_file(tmp_path: Path):
    f = tmp_path / "e.txt"
    f.write_text("")
    cls = get_tool("Read")
    res = await cls().run(cls.Input(file_path=str(f)))
    assert "empty" in res.output.lower()


@pytest.mark.asyncio
async def test_read_image_returns_metadata(tmp_path: Path):
    f = tmp_path / "img.png"
    f.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)
    cls = get_tool("Read")
    res = await cls().run(cls.Input(file_path=str(f)))
    assert res.is_error is False
    assert res.metadata.get("is_image") is True


@pytest.mark.asyncio
async def test_read_through_execute_tool_call(tmp_path: Path):
    f = tmp_path / "x.txt"
    f.write_text("ok\n")
    tc = ToolCall(id="1", name="Read", arguments={"file_path": str(f)})
    res = await execute_tool_call(tc)
    assert "1\tok" in res.output


@pytest.mark.asyncio
async def test_read_tilde_expansion(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / "home.txt"
    target.write_text("hi\n")
    cls = get_tool("Read")
    res = await cls().run(cls.Input(file_path="~/home.txt"))
    assert "1\thi" in res.output
```

### Etapa 4: Rodar testes

```bash
pytest tests/test_tools/test_read.py -v
```

Todos passam.

---

## Criterios de Aceite

- [x] `src/vulpcode/tools/read.py` implementa `ReadTool` com `@tool(name="Read")`
- [x] `Input` com `file_path`, `offset`, `limit` (offset/limit opcionais)
- [x] Saida em formato `<lineno>\t<content>` (cat -n style)
- [x] Detecta binarios via byte 0 e retorna erro
- [x] Detecta imagens (.png/.jpg/etc) e retorna metadata sem ler bytes para texto
- [x] Arquivo vazio retorna mensagem informativa, nao erro
- [x] `tools/__init__.py` importa `read.py` para registrar a tool
- [x] `tests/test_tools/test_read.py` com >=8 testes, todos passando
- [x] `~` em paths e expandido (`expanduser`)

---

## Riscos Tecnicos

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|---------------|---------|-----------|
| Arquivos com encoding nao-UTF8 | Media | Baixo | `errors="replace"` |
| Arquivo gigante consume RAM | Media | Medio | Default limit 2000, mas le tudo na RAM. Aceitar v1 |
| Falsa deteccao de binario (UTF-16 com NULLs) | Baixa | Baixo | Aceitar v1 |

---

**End of Specification**
