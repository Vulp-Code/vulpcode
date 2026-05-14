# Tarefa 04.03 - Tools Edit e MultiEdit

**Status**: PENDENTE
**Fase**: 04 - Tools Filesystem
**Dependencias**: 02.02, 04.01
**Bloqueia**: Nada

---

## Objetivo

Implementar `Edit` e `MultiEdit` em `src/vulpcode/tools/edit.py`. Ambas substituem
strings exatas em arquivos (paridade Claude Code). Edit faz uma substituicao;
MultiEdit aplica multiplas em sequencia atomicamente (se uma falha, nada e escrito).

---

## Descricao Tecnica

### Edit

**Comportamento**:
- `old_string` deve aparecer EXATAMENTE UMA VEZ no arquivo, exceto se `replace_all=True`.
- `new_string` substitui `old_string`.
- `old_string` nao pode ser igual a `new_string`.
- Arquivo precisa existir.
- Output: snippet do contexto (linhas afetadas com numero, formato cat -n) ou
  mensagem de confirmacao curta com count de substituicoes.

**Schema**:
```python
class Input(BaseModel):
    file_path: str
    old_string: str
    new_string: str
    replace_all: bool = False
```

### MultiEdit

**Comportamento**:
- Aceita lista de `{old_string, new_string, replace_all?}`.
- Aplica em ordem, em memoria; cada edit ve o resultado dos anteriores.
- Se qualquer edit falhar (old_string nao existe, ou ambiguo sem replace_all),
  a operacao inteira falha e nada e escrito ao disco.

**Schema**:
```python
class EditOp(BaseModel):
    old_string: str
    new_string: str
    replace_all: bool = False

class Input(BaseModel):
    file_path: str
    edits: list[EditOp]
```

### Estrutura

**`src/vulpcode/tools/edit.py`**:

```python
"""Edit and MultiEdit tools: exact-string substitution in files."""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from vulpcode.tools.base import Tool, ToolResult, tool


def _apply_edit(
    text: str, old: str, new: str, replace_all: bool
) -> tuple[str, int, str | None]:
    """Apply a single edit to text. Returns (new_text, count, error_message)."""
    if old == new:
        return text, 0, "old_string and new_string are identical"
    if old == "":
        return text, 0, "old_string cannot be empty"
    if replace_all:
        count = text.count(old)
        if count == 0:
            return text, 0, f"old_string not found"
        return text.replace(old, new), count, None
    occurrences = text.count(old)
    if occurrences == 0:
        return text, 0, "old_string not found"
    if occurrences > 1:
        return text, 0, (
            f"old_string is not unique ({occurrences} occurrences). "
            "Add more context or set replace_all=True."
        )
    return text.replace(old, new, 1), 1, None


def _snippet_around_change(
    new_text: str, search: str, context_lines: int = 3
) -> str:
    """Return a small numbered snippet showing the result around the first match."""
    lines = new_text.splitlines()
    if not lines:
        return "<file is empty after edit>"
    target_line = 1
    needle_first = search.splitlines()[0] if search else ""
    if needle_first:
        for i, line in enumerate(lines, start=1):
            if needle_first in line:
                target_line = i
                break
    start = max(1, target_line - context_lines)
    end = min(len(lines), target_line + context_lines)
    out = []
    for i in range(start, end + 1):
        out.append(f"{i}\t{lines[i - 1]}")
    return "\n".join(out)


@tool(
    name="Edit",
    description=(
        "Replace exact occurrences of old_string with new_string in a file. "
        "old_string must be unique unless replace_all=True."
    ),
    requires_confirm=True,
)
class EditTool(Tool):
    class Input(BaseModel):
        file_path: str
        old_string: str
        new_string: str
        replace_all: bool = False

    async def run(self, args: BaseModel) -> ToolResult:  # type: ignore[override]
        assert isinstance(args, EditTool.Input)
        path = Path(args.file_path).expanduser().resolve()
        if not path.exists():
            return ToolResult(error=f"File does not exist: {path}", is_error=True)
        if path.is_dir():
            return ToolResult(error=f"Path is a directory: {path}", is_error=True)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            return ToolResult(error=f"Cannot read file: {exc}", is_error=True)

        new_text, count, err = _apply_edit(
            text, args.old_string, args.new_string, args.replace_all,
        )
        if err is not None:
            return ToolResult(error=err, is_error=True)
        try:
            path.write_text(new_text, encoding="utf-8")
        except OSError as exc:
            return ToolResult(error=f"Failed to write: {exc}", is_error=True)

        snippet = _snippet_around_change(new_text, args.new_string)
        return ToolResult(
            output=f"Applied {count} edit(s) to {path}\n{snippet}",
            metadata={"file_path": str(path), "edits_applied": count},
        )


@tool(
    name="MultiEdit",
    description=(
        "Atomically apply multiple edits to a single file. If any edit fails, "
        "no changes are written."
    ),
    requires_confirm=True,
)
class MultiEditTool(Tool):
    class EditOp(BaseModel):
        old_string: str
        new_string: str
        replace_all: bool = False

    class Input(BaseModel):
        file_path: str
        edits: list["MultiEditTool.EditOp"] = Field(default_factory=list)

    async def run(self, args: BaseModel) -> ToolResult:  # type: ignore[override]
        assert isinstance(args, MultiEditTool.Input)
        if not args.edits:
            return ToolResult(error="edits list cannot be empty", is_error=True)
        path = Path(args.file_path).expanduser().resolve()
        if not path.exists():
            return ToolResult(error=f"File does not exist: {path}", is_error=True)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            return ToolResult(error=f"Cannot read file: {exc}", is_error=True)

        total = 0
        for i, op in enumerate(args.edits, start=1):
            text, count, err = _apply_edit(
                text, op.old_string, op.new_string, op.replace_all,
            )
            if err is not None:
                return ToolResult(
                    error=f"Edit #{i} failed: {err}",
                    is_error=True,
                )
            total += count

        try:
            path.write_text(text, encoding="utf-8")
        except OSError as exc:
            return ToolResult(error=f"Failed to write: {exc}", is_error=True)

        return ToolResult(
            output=f"Applied {total} edit(s) across {len(args.edits)} operations to {path}",
            metadata={"file_path": str(path), "edits_applied": total, "ops": len(args.edits)},
        )


# Required for forward-ref in MultiEditTool.Input
MultiEditTool.Input.model_rebuild()
```

### Atualizar `tools/__init__.py`

```python
from vulpcode.tools import edit as _edit  # noqa: F401
```

---

## INSTRUCAO CRITICA

- `Edit` rejeita `old == new` para evitar no-op silencioso.
- `Edit` rejeita `old == ""` para evitar comportamento inesperado.
- `count > 1` sem `replace_all` -> erro. Mensagem deve sugerir solucoes.
- O snippet de contexto retornado e cosmetico mas ajuda o agente a verificar.
- MultiEdit aplica TUDO em memoria primeiro; so escreve no fim. Se qualquer
  passo falha, retorna sem tocar no disco.
- A forward-ref `list["MultiEditTool.EditOp"]` requer `model_rebuild()` apos a
  classe ser definida — Pydantic v2 idiom.
- `requires_confirm=True` em ambas as tools.

---

## Etapas de Implementacao

### Etapa 1: Criar `tools/edit.py`

### Etapa 2: Atualizar `tools/__init__.py`

### Etapa 3: Criar `tests/test_tools/test_edit.py`

```python
from pathlib import Path
import pytest

import vulpcode.tools  # noqa
from vulpcode.tools import get_tool


@pytest.mark.asyncio
async def test_edit_unique_replacement(tmp_path: Path):
    f = tmp_path / "a.py"
    f.write_text("x = 1\nfoo()\nx = 1\n")
    cls = get_tool("Edit")
    res = await cls().run(cls.Input(file_path=str(f), old_string="foo()", new_string="bar()"))
    assert res.is_error is False
    assert "bar()" in f.read_text()


@pytest.mark.asyncio
async def test_edit_ambiguous_fails(tmp_path: Path):
    f = tmp_path / "a.txt"
    f.write_text("aa\naa\n")
    cls = get_tool("Edit")
    res = await cls().run(cls.Input(file_path=str(f), old_string="aa", new_string="bb"))
    assert res.is_error
    assert "unique" in (res.error or "").lower()


@pytest.mark.asyncio
async def test_edit_replace_all(tmp_path: Path):
    f = tmp_path / "a.txt"
    f.write_text("aa\naa\n")
    cls = get_tool("Edit")
    res = await cls().run(cls.Input(file_path=str(f), old_string="aa", new_string="bb", replace_all=True))
    assert res.is_error is False
    assert f.read_text() == "bb\nbb\n"


@pytest.mark.asyncio
async def test_edit_old_equals_new(tmp_path: Path):
    f = tmp_path / "a.txt"
    f.write_text("x")
    cls = get_tool("Edit")
    res = await cls().run(cls.Input(file_path=str(f), old_string="x", new_string="x"))
    assert res.is_error


@pytest.mark.asyncio
async def test_edit_not_found(tmp_path: Path):
    f = tmp_path / "a.txt"
    f.write_text("hello")
    cls = get_tool("Edit")
    res = await cls().run(cls.Input(file_path=str(f), old_string="zzz", new_string="qq"))
    assert res.is_error
    assert "not found" in (res.error or "")


@pytest.mark.asyncio
async def test_multiedit_atomic_success(tmp_path: Path):
    f = tmp_path / "a.txt"
    f.write_text("a\nb\nc\n")
    cls = get_tool("MultiEdit")
    res = await cls().run(cls.Input(
        file_path=str(f),
        edits=[
            cls.EditOp(old_string="a", new_string="A"),
            cls.EditOp(old_string="b", new_string="B"),
        ],
    ))
    assert res.is_error is False
    assert f.read_text() == "A\nB\nc\n"


@pytest.mark.asyncio
async def test_multiedit_rolls_back_on_failure(tmp_path: Path):
    f = tmp_path / "a.txt"
    original = "a\nb\nc\n"
    f.write_text(original)
    cls = get_tool("MultiEdit")
    res = await cls().run(cls.Input(
        file_path=str(f),
        edits=[
            cls.EditOp(old_string="a", new_string="A"),
            cls.EditOp(old_string="DOES_NOT_EXIST", new_string="X"),
        ],
    ))
    assert res.is_error
    assert f.read_text() == original  # rollback


@pytest.mark.asyncio
async def test_multiedit_empty_list_fails(tmp_path: Path):
    f = tmp_path / "a.txt"
    f.write_text("x")
    cls = get_tool("MultiEdit")
    res = await cls().run(cls.Input(file_path=str(f), edits=[]))
    assert res.is_error
```

### Etapa 4: Rodar testes

```bash
pytest tests/test_tools/test_edit.py -v
```

---

## Criterios de Aceite

- [x] `src/vulpcode/tools/edit.py` implementa `EditTool` e `MultiEditTool`
- [x] `Edit` exige `old_string` unico ou `replace_all=True`
- [x] `Edit` rejeita `old == new` e `old == ""`
- [x] `MultiEdit` aplica em memoria e so escreve se todas as ops sucederam
- [x] Falha em qualquer op de MultiEdit deixa o arquivo inalterado (rollback)
- [x] Ambas com `requires_confirm=True`
- [x] Snippet de contexto retornado no output do Edit
- [x] `tools/__init__.py` importa `edit.py`
- [x] `tests/test_tools/test_edit.py` com >=8 testes, todos passando

---

## Riscos Tecnicos

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|---------------|---------|-----------|
| Whitespace exato dificulta old_string | Alta | Medio | Documentar; o LLM ja conhece o padrao Claude Code |
| Multiedit em arquivo grande consume RAM | Baixa | Baixo | Aceitar v1 |
| forward-ref do Pydantic v2 falha | Baixa | Medio | `model_rebuild()` apos definicao |

---

**End of Specification**
