# Tarefa 06.04 - Tool NotebookEdit

**Status**: PENDENTE
**Fase**: 06 - Tools Web + Agente
**Dependencias**: 02.02
**Bloqueia**: Nada

---

## Objetivo

Implementar `NotebookEdit` em `src/vulpcode/tools/notebook.py`. Edita celulas de
arquivos `.ipynb` (Jupyter): replace, insert, delete por id ou indice. Preserva
o formato JSON do notebook.

---

## Descricao Tecnica

### Comportamento

- `notebook_path`: caminho absoluto do `.ipynb`.
- `cell_id`: id da celula (string como `"cell-uuid"`) OU
- `cell_number`: indice 0-based.
- `new_source`: novo conteudo da celula (texto bruto, sem split em linhas).
- `cell_type`: `"code"` | `"markdown"` (default: preserva o atual).
- `edit_mode`: `"replace"` (default) | `"insert"` | `"delete"`.

### Estrutura

**`src/vulpcode/tools/notebook.py`**:

```python
"""NotebookEdit tool: edit cells in Jupyter .ipynb files."""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, model_validator

from vulpcode.tools.base import Tool, ToolResult, tool


@tool(
    name="NotebookEdit",
    description=(
        "Edit cells in a Jupyter .ipynb file. Modes: replace (default), insert, "
        "delete. Cell can be located by cell_id or cell_number (0-based)."
    ),
    requires_confirm=True,
)
class NotebookEditTool(Tool):
    class Input(BaseModel):
        notebook_path: str
        new_source: str = ""
        cell_id: str | None = None
        cell_number: int | None = None
        cell_type: Literal["code", "markdown"] | None = None
        edit_mode: Literal["replace", "insert", "delete"] = "replace"

        @model_validator(mode="after")
        def _check_locator(self):
            if self.edit_mode == "delete" and (self.cell_id is None and self.cell_number is None):
                raise ValueError("delete requires cell_id or cell_number")
            if self.edit_mode == "replace" and (self.cell_id is None and self.cell_number is None):
                raise ValueError("replace requires cell_id or cell_number")
            return self

    async def run(self, args: BaseModel) -> ToolResult:  # type: ignore[override]
        assert isinstance(args, NotebookEditTool.Input)
        path = Path(args.notebook_path).expanduser().resolve()
        if not path.exists():
            return ToolResult(error=f"Notebook does not exist: {path}", is_error=True)
        try:
            with path.open("r", encoding="utf-8") as fh:
                nb = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            return ToolResult(error=f"Cannot parse notebook: {exc}", is_error=True)

        cells = nb.get("cells")
        if cells is None:
            return ToolResult(error="Notebook has no 'cells' key", is_error=True)

        idx = self._find_index(cells, args)
        if args.edit_mode != "insert" and idx is None:
            return ToolResult(error="Cell not found by id or number", is_error=True)

        if args.edit_mode == "delete":
            removed = cells.pop(idx)
            metadata = {"cell_id": removed.get("id"), "removed_index": idx}
        elif args.edit_mode == "insert":
            new_cell = self._make_cell(args.cell_type or "code", args.new_source)
            insert_at = idx if idx is not None else len(cells)
            cells.insert(insert_at, new_cell)
            metadata = {"cell_id": new_cell["id"], "inserted_at": insert_at}
        else:  # replace
            cell = cells[idx]
            cell["source"] = self._split_source(args.new_source)
            if args.cell_type is not None:
                cell["cell_type"] = args.cell_type
                # outputs/execution_count only meaningful for code cells
                if args.cell_type == "markdown":
                    cell.pop("outputs", None)
                    cell.pop("execution_count", None)
            metadata = {"cell_id": cell.get("id"), "replaced_index": idx}

        try:
            with path.open("w", encoding="utf-8") as fh:
                json.dump(nb, fh, indent=1, ensure_ascii=False)
                fh.write("\n")
        except OSError as exc:
            return ToolResult(error=f"Failed to write: {exc}", is_error=True)

        return ToolResult(
            output=f"Notebook {path} updated ({args.edit_mode})",
            metadata={"notebook_path": str(path), "edit_mode": args.edit_mode, **metadata},
        )

    @staticmethod
    def _find_index(cells: list[dict[str, Any]], args: "NotebookEditTool.Input") -> int | None:
        if args.cell_id is not None:
            for i, c in enumerate(cells):
                if c.get("id") == args.cell_id:
                    return i
            return None
        if args.cell_number is not None:
            if 0 <= args.cell_number < len(cells):
                return args.cell_number
            return None
        return None

    @staticmethod
    def _split_source(text: str) -> list[str]:
        # Jupyter source is a list of strings, each ending with \n except possibly the last.
        if not text:
            return []
        lines = text.splitlines(keepends=True)
        return lines

    @staticmethod
    def _make_cell(cell_type: str, source: str) -> dict[str, Any]:
        cell: dict[str, Any] = {
            "id": str(uuid.uuid4())[:8],
            "cell_type": cell_type,
            "metadata": {},
            "source": NotebookEditTool._split_source(source),
        }
        if cell_type == "code":
            cell["outputs"] = []
            cell["execution_count"] = None
        return cell
```

### Atualizar `tools/__init__.py`

```python
from vulpcode.tools import notebook as _notebook  # noqa: F401
```

---

## INSTRUCAO CRITICA

- O formato `.ipynb` e JSON com a chave `cells` contendo lista de dicts.
- `source` de cada celula e SEMPRE uma lista de strings, cada uma terminando
  com `\n` (exceto possivelmente a ultima). Usar `splitlines(keepends=True)`.
- Em insert sem cell_id/number, anexa ao final.
- Em replace, preservamos id, metadata e outputs (a menos que o tipo mude para
  markdown).
- Preservar `nb_format`, `nb_format_minor`, `metadata` do notebook — basta nao
  tocar.
- `requires_confirm=True` — modificacao de arquivo relevante.

---

## Etapas de Implementacao

### Etapa 1: Criar `tools/notebook.py`

### Etapa 2: Atualizar `tools/__init__.py`

### Etapa 3: Criar `tests/test_tools/test_notebook.py`

```python
import json
from pathlib import Path
import pytest

import vulpcode.tools  # noqa
from vulpcode.tools import get_tool


def _make_nb(tmp_path: Path) -> Path:
    p = tmp_path / "n.ipynb"
    nb = {
        "cells": [
            {"id": "a", "cell_type": "code", "metadata": {}, "source": ["print('hi')\n"], "outputs": [], "execution_count": None},
            {"id": "b", "cell_type": "markdown", "metadata": {}, "source": ["# Title\n"]},
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    p.write_text(json.dumps(nb))
    return p


@pytest.mark.asyncio
async def test_replace_by_id(tmp_path: Path):
    p = _make_nb(tmp_path)
    cls = get_tool("NotebookEdit")
    res = await cls().run(cls.Input(
        notebook_path=str(p), cell_id="a", new_source="print('updated')\n",
    ))
    assert res.is_error is False
    nb = json.loads(p.read_text())
    assert nb["cells"][0]["source"] == ["print('updated')\n"]


@pytest.mark.asyncio
async def test_replace_by_number(tmp_path: Path):
    p = _make_nb(tmp_path)
    cls = get_tool("NotebookEdit")
    res = await cls().run(cls.Input(
        notebook_path=str(p), cell_number=1, new_source="# New\n", cell_type="markdown",
    ))
    assert res.is_error is False
    nb = json.loads(p.read_text())
    assert "New" in "".join(nb["cells"][1]["source"])


@pytest.mark.asyncio
async def test_insert(tmp_path: Path):
    p = _make_nb(tmp_path)
    cls = get_tool("NotebookEdit")
    res = await cls().run(cls.Input(
        notebook_path=str(p), edit_mode="insert", new_source="print(2)\n", cell_type="code",
    ))
    assert res.is_error is False
    nb = json.loads(p.read_text())
    assert len(nb["cells"]) == 3


@pytest.mark.asyncio
async def test_delete(tmp_path: Path):
    p = _make_nb(tmp_path)
    cls = get_tool("NotebookEdit")
    res = await cls().run(cls.Input(
        notebook_path=str(p), edit_mode="delete", cell_id="b",
    ))
    assert res.is_error is False
    nb = json.loads(p.read_text())
    assert len(nb["cells"]) == 1


@pytest.mark.asyncio
async def test_missing_locator_for_delete(tmp_path: Path):
    p = _make_nb(tmp_path)
    cls = get_tool("NotebookEdit")
    with pytest.raises(Exception):
        cls.Input(notebook_path=str(p), edit_mode="delete")


@pytest.mark.asyncio
async def test_unknown_id(tmp_path: Path):
    p = _make_nb(tmp_path)
    cls = get_tool("NotebookEdit")
    res = await cls().run(cls.Input(
        notebook_path=str(p), cell_id="zzz", new_source="x",
    ))
    assert res.is_error
```

### Etapa 4: Rodar testes

```bash
pytest tests/test_tools/test_notebook.py -v
```

---

## Criterios de Aceite

- [x] `src/vulpcode/tools/notebook.py` implementa `NotebookEditTool`
- [x] Suporta `replace`, `insert`, `delete`
- [x] Localiza celula por `cell_id` ou `cell_number`
- [x] `source` armazenado como lista de strings com `\n`
- [x] Preserva `metadata` e `nbformat` do notebook
- [x] Insercao com novo cell gera id curto
- [x] `requires_confirm=True`
- [x] `tools/__init__.py` importa `notebook.py`
- [x] `tests/test_tools/test_notebook.py` com >=6 testes, todos passando

---

## Riscos Tecnicos

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|---------------|---------|-----------|
| Notebook corrompido apos edicao | Baixa | Alto | json.dump preserva estrutura; nao tocamos em nbformat |
| Outputs perdidos em troca de tipo | Media | Baixo | Documentar |
| Encoding nao-UTF8 em sources | Baixa | Baixo | Sempre UTF-8 no read/write |

---

**End of Specification**
