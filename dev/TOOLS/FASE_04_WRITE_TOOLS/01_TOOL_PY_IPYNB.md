# Tarefa 04.01 — Tools `WritePy` e `WriteIpynb`

**Status**: PENDENTE
**Fase**: 04 - Write Tools
**Dependências**: FASE_03 (`ValidatedWriteTool`)
**Bloqueia**: FASE_06_TESTES

---

## Objetivo

Implementar duas tools especializadas para Python:

- **`WritePy`** — cria/sobrescreve um `.py`. Valida via `ast.parse()` antes de gravar.
- **`WriteIpynb`** — cria/sobrescreve um `.ipynb`. Aceita lista de cells e monta o JSON.
  Valida (a) `nbformat.validate` no notebook inteiro, (b) `ast.parse` em cada cell code.

---

## `WritePy`

### `src/vulpcode/tools/write_py.py`

```python
"""WritePy tool: create or overwrite a .py file, validating syntax via ast.parse."""
from __future__ import annotations

import ast

from pydantic import BaseModel

from vulpcode.tools._validated_write import (
    ValidatedWriteTool, ValidationError, format_snippet,
)
from vulpcode.tools.base import tool


@tool(
    name="WritePy",
    description=(
        "Create or overwrite a Python (.py) file. Validates the content with "
        "ast.parse() before saving. If there is a SyntaxError, the file is NOT "
        "written and the error is returned with line, column and a 5-line snippet "
        "around the failure point — use this to fix and resubmit. UTF-8."
    ),
    requires_confirm=True,
)
class WritePyTool(ValidatedWriteTool):
    class Input(BaseModel):
        file_path: str
        content: str

    def validate(self, content, args):
        try:
            ast.parse(content, filename=args.file_path)
        except SyntaxError as exc:
            line = exc.lineno or 1
            col = exc.offset or None
            raise ValidationError(
                f"SyntaxError: {exc.msg}",
                line=line, col=col,
                snippet=format_snippet(content, line, col),
            )
```

### Tests em `tests/test_tools/test_write_py.py`

```python
import pytest
from vulpcode.tools import get_tool
import vulpcode.tools.write_py  # noqa: register

@pytest.mark.asyncio
async def test_write_py_valid(tmp_path):
    cls = get_tool("WritePy")
    target = tmp_path / "ok.py"
    res = await cls().run(cls.Input(
        file_path=str(target),
        content="def f(x):\n    return x + 1\n",
    ))
    assert res.is_error is False
    assert target.exists()

@pytest.mark.asyncio
async def test_write_py_syntax_error_blocks_save(tmp_path):
    cls = get_tool("WritePy")
    target = tmp_path / "bad.py"
    res = await cls().run(cls.Input(
        file_path=str(target),
        content="def f(x):\n    return x +\n",  # incomplete expression
    ))
    assert res.is_error is True
    assert "SyntaxError" in res.error
    assert "line" in res.error.lower()
    assert not target.exists()

@pytest.mark.asyncio
async def test_write_py_error_includes_snippet(tmp_path):
    cls = get_tool("WritePy")
    res = await cls().run(cls.Input(
        file_path=str(tmp_path / "bad.py"),
        content="a = 1\nb = 2 3\nc = 4\n",
    ))
    assert res.is_error is True
    assert "b = 2 3" in res.error  # snippet line should appear

@pytest.mark.asyncio
async def test_write_py_empty_file_is_valid(tmp_path):
    cls = get_tool("WritePy")
    target = tmp_path / "empty.py"
    res = await cls().run(cls.Input(file_path=str(target), content=""))
    assert res.is_error is False
    assert target.read_text() == ""

@pytest.mark.asyncio
async def test_write_py_only_comments_is_valid(tmp_path):
    cls = get_tool("WritePy")
    target = tmp_path / "c.py"
    res = await cls().run(cls.Input(
        file_path=str(target),
        content="# just a comment\n# nothing else\n",
    ))
    assert res.is_error is False
```

---

## `WriteIpynb`

### Input

O modelo pode escolher entre dois formatos — o segundo é fortemente preferido:

**Formato 1: notebook JSON cru** (escape-hell — desencorajado mas suportado)
```python
content: str  # JSON do nbformat
```

**Formato 2: lista de cells** (recomendado)
```python
cells: list[Cell]    # Cell = {"type": "code"|"markdown", "source": str}
metadata: dict | None = None
```

A tool prefere `cells` quando presente; cai pra `content` como fallback.

### `src/vulpcode/tools/write_ipynb.py`

```python
"""WriteIpynb tool: build and write a Jupyter .ipynb with validation."""
from __future__ import annotations

import ast
import json
import uuid
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from vulpcode.tools._validated_write import (
    ValidatedWriteTool, ValidationError, format_snippet,
)
from vulpcode.tools.base import tool


class _Cell(BaseModel):
    type: Literal["code", "markdown"] = "code"
    source: str = ""


@tool(
    name="WriteIpynb",
    description=(
        "Create or overwrite a Jupyter notebook (.ipynb). Prefer passing `cells` "
        "as a list of {type, source} — the tool assembles the JSON for you. "
        "Each code cell is validated with ast.parse(); the whole notebook is "
        "validated with nbformat.validate(). On any error the file is NOT "
        "written and the precise failure is returned for you to fix and resubmit."
    ),
    requires_confirm=True,
)
class WriteIpynbTool(ValidatedWriteTool):
    class Input(BaseModel):
        file_path: str
        cells: list[_Cell] | None = None
        content: str | None = None  # raw JSON fallback
        metadata: dict = Field(default_factory=dict)

        @model_validator(mode="after")
        def _need_one(self):
            if self.cells is None and self.content is None:
                raise ValueError("provide either `cells` or `content`")
            return self

    def transform(self, args):
        if args.cells is not None:
            nb = {
                "cells": [
                    {
                        "cell_type": c.type,
                        "id": uuid.uuid4().hex[:8],
                        "metadata": {},
                        "source": c.source.splitlines(keepends=True),
                        **({"outputs": [], "execution_count": None}
                           if c.type == "code" else {}),
                    }
                    for c in args.cells
                ],
                "metadata": {
                    "kernelspec": {
                        "display_name": "Python 3",
                        "language": "python",
                        "name": "python3",
                    },
                    "language_info": {"name": "python"},
                    **args.metadata,
                },
                "nbformat": 4,
                "nbformat_minor": 5,
            }
            return json.dumps(nb, indent=1)
        return args.content  # raw JSON path

    def validate(self, content, args):
        # JSON parse
        try:
            nb = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValidationError(
                f"Notebook is not valid JSON: {e.msg}",
                line=e.lineno, col=e.colno,
                snippet=format_snippet(content, e.lineno, e.colno),
            )
        # nbformat structural validation
        try:
            import nbformat
        except ImportError:
            raise ValidationError(
                "WriteIpynb requires nbformat. Install with: pip install vulpcode[docs-tools]"
            )
        try:
            nbformat.validate(nb)
        except Exception as e:
            raise ValidationError(f"nbformat.validate failed: {e}")
        # AST check on each code cell
        for i, cell in enumerate(nb.get("cells", [])):
            if cell.get("cell_type") != "code":
                continue
            src = cell.get("source", "")
            if isinstance(src, list):
                src = "".join(src)
            try:
                ast.parse(src, filename=f"<cell {i}>")
            except SyntaxError as exc:
                raise ValidationError(
                    f"SyntaxError in code cell #{i}: {exc.msg}",
                    line=exc.lineno or 1, col=exc.offset,
                    snippet=format_snippet(src, exc.lineno or 1, exc.offset),
                )
```

### Tests em `tests/test_tools/test_write_ipynb.py`

```python
import json
import pytest
from vulpcode.tools import get_tool
import vulpcode.tools.write_ipynb  # noqa

pytest.importorskip("nbformat")

@pytest.mark.asyncio
async def test_write_ipynb_from_cells(tmp_path):
    cls = get_tool("WriteIpynb")
    target = tmp_path / "nb.ipynb"
    res = await cls().run(cls.Input(
        file_path=str(target),
        cells=[
            {"type": "markdown", "source": "# Title"},
            {"type": "code", "source": "x = 1\nprint(x)"},
        ],
    ))
    assert res.is_error is False
    nb = json.loads(target.read_text())
    assert nb["nbformat"] == 4
    assert len(nb["cells"]) == 2

@pytest.mark.asyncio
async def test_write_ipynb_code_syntax_error_blocks(tmp_path):
    cls = get_tool("WriteIpynb")
    target = tmp_path / "bad.ipynb"
    res = await cls().run(cls.Input(
        file_path=str(target),
        cells=[{"type": "code", "source": "x = 1 2"}],
    ))
    assert res.is_error is True
    assert "SyntaxError in code cell #0" in res.error
    assert not target.exists()

@pytest.mark.asyncio
async def test_write_ipynb_raw_json(tmp_path):
    nb = {
        "cells": [],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    cls = get_tool("WriteIpynb")
    target = tmp_path / "empty.ipynb"
    res = await cls().run(cls.Input(file_path=str(target), content=json.dumps(nb)))
    assert res.is_error is False
```

---

## Atualizar `src/vulpcode/tools/__init__.py`

```python
from vulpcode.tools import write_py as _write_py  # noqa
from vulpcode.tools import write_ipynb as _write_ipynb  # noqa
```

---

## Critérios de Aceite

- [x] `WritePy` registrado, valida via `ast.parse`, retorna snippet em caso de erro
- [x] `WriteIpynb` aceita `cells` estruturadas OU `content` JSON cru
- [x] `WriteIpynb` valida cada cell code via `ast.parse` + notebook inteiro via `nbformat.validate`
- [x] Mensagem de erro de ipynb identifica em qual cell o problema está
- [x] Sem arquivo gerado quando há erro de validação
- [x] >= 5 testes para `WritePy` e >= 3 para `WriteIpynb`, todos passando
- [x] Import de `nbformat` é lazy (não quebra import do pacote sem o extra)

---

## Riscos

| Risco | Probabilidade | Mitigação |
|-------|---------------|-----------|
| Modelo emite o source como `list[str]` (jupyter style) | Baixa via `cells` API | A API aceita `str`; documentar |
| Notebook gigante estoura limit do endpoint | Alta | Modelo divide em sessões de `WriteIpynb` para abas + `NotebookEdit` para append |
| Cell magic (`%matplotlib`) faz `ast.parse` falhar | Alta | Permitir prefixo `%`/`%%`: ignorar essas linhas antes do `ast.parse` (TODO no validator) |

---

**End of Specification**
