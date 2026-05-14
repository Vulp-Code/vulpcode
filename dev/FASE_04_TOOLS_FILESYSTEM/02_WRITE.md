# Tarefa 04.02 - Tool Write

**Status**: PENDENTE
**Fase**: 04 - Tools Filesystem
**Dependencias**: 02.02 (Tool ABC), 04.01 (padrao da Read)
**Bloqueia**: Nada

---

## Objetivo

Implementar a tool `Write` em `src/vulpcode/tools/write.py`. Cria ou sobrescreve
arquivo no disco com `requires_confirm=True`. Cria diretorios pai
automaticamente. Retorna confirmacao com path absoluto e tamanho escrito.

---

## Descricao Tecnica

### Comportamento

- Se o arquivo nao existe: cria com mkdir -p de diretorios pai.
- Se existe: sobrescreve sem aviso (a confirmacao do usuario via permissions
  cuida disso na FASE 07.02; a tool por si nao pergunta).
- Sempre escreve em UTF-8.
- Retorna no `output` algo como `"Wrote 234 bytes to /abs/path/file.txt"`.

### Schema de input

```python
class Input(BaseModel):
    file_path: str
    content: str
```

### Estrutura

**`src/vulpcode/tools/write.py`**:

```python
"""Write tool: creates or overwrites a file with given content."""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from vulpcode.tools.base import Tool, ToolResult, tool


@tool(
    name="Write",
    description=(
        "Create or overwrite a file with the given content. Parent directories are "
        "created automatically. Always writes UTF-8."
    ),
    requires_confirm=True,
)
class WriteTool(Tool):
    class Input(BaseModel):
        file_path: str
        content: str

    async def run(self, args: BaseModel) -> ToolResult:  # type: ignore[override]
        assert isinstance(args, WriteTool.Input)
        path = Path(args.file_path).expanduser().resolve()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(args.content, encoding="utf-8")
        except OSError as exc:
            return ToolResult(error=f"Failed to write {path}: {exc}", is_error=True)
        size = path.stat().st_size
        return ToolResult(
            output=f"Wrote {size} bytes to {path}",
            metadata={"file_path": str(path), "size": size, "created": True},
        )
```

### Atualizar `tools/__init__.py`

```python
from vulpcode.tools import write as _write  # noqa: F401
```

---

## INSTRUCAO CRITICA

- `requires_confirm=True` — a confirmacao real vem da FASE 07.02. A tool nunca
  pergunta diretamente ao usuario.
- `Path.resolve()` para registrar o caminho absoluto canonico no metadata.
- Nao implementar backup automatico — quem quiser pode usar git ou Edit (que
  preserva conteudo nao-modificado).
- O output e curto e descritivo, comeca com `"Wrote ... bytes to ..."` para que
  o LLM possa parsear se quiser.
- Aceitar conteudo vazio (`""`) — escreve um arquivo de 0 bytes.

---

## Etapas de Implementacao

### Etapa 1: Criar `tools/write.py`

### Etapa 2: Atualizar `tools/__init__.py`

### Etapa 3: Criar `tests/test_tools/test_write.py`

```python
from pathlib import Path

import pytest

import vulpcode.tools  # noqa: F401
from vulpcode.tools import get_tool


@pytest.mark.asyncio
async def test_write_creates_new_file(tmp_path: Path):
    cls = get_tool("Write")
    target = tmp_path / "subdir" / "out.txt"
    res = await cls().run(cls.Input(file_path=str(target), content="hello"))
    assert res.is_error is False
    assert target.read_text() == "hello"
    assert "5 bytes" in res.output
    assert str(target) in res.output


@pytest.mark.asyncio
async def test_write_overwrites_existing(tmp_path: Path):
    cls = get_tool("Write")
    f = tmp_path / "x.txt"
    f.write_text("old")
    res = await cls().run(cls.Input(file_path=str(f), content="new"))
    assert res.is_error is False
    assert f.read_text() == "new"


@pytest.mark.asyncio
async def test_write_empty_content(tmp_path: Path):
    cls = get_tool("Write")
    f = tmp_path / "empty.txt"
    res = await cls().run(cls.Input(file_path=str(f), content=""))
    assert res.is_error is False
    assert f.exists()
    assert f.read_text() == ""


@pytest.mark.asyncio
async def test_write_creates_parent_dirs(tmp_path: Path):
    cls = get_tool("Write")
    deep = tmp_path / "a" / "b" / "c" / "d.txt"
    res = await cls().run(cls.Input(file_path=str(deep), content="x"))
    assert res.is_error is False
    assert deep.exists()


def test_write_requires_confirm():
    cls = get_tool("Write")
    assert cls._requires_confirm is True
```

### Etapa 4: Rodar testes

```bash
pytest tests/test_tools/test_write.py -v
```

---

## Criterios de Aceite

- [x] `src/vulpcode/tools/write.py` implementa `WriteTool` com `requires_confirm=True`
- [x] Cria diretorios pai automaticamente
- [x] Sobrescreve arquivos existentes
- [x] Aceita conteudo vazio
- [x] Retorna `output` com tamanho e path absoluto
- [x] Usa UTF-8 sempre
- [x] `tools/__init__.py` importa `write.py`
- [x] `tests/test_tools/test_write.py` com >=5 testes, todos passando

---

## Riscos Tecnicos

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|---------------|---------|-----------|
| Sobrescrita acidental | Alta (sem confirm UI) | Alto | `requires_confirm=True` cobre via permissions |
| Permissao negada | Media | Medio | OSError -> erro explicito |
| Path traversal | Baixa | Alto | A confirmacao de quem aprova e responsavel; a tool nao filtra |

---

**End of Specification**
