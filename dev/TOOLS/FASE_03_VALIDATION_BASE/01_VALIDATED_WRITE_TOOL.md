# Tarefa 03.01 — Base de tools com validação + gravação atômica

**Status**: PENDENTE
**Fase**: 03 - Validation Base
**Dependências**: nenhuma (pode rodar em paralelo com FASE_01/FASE_02)
**Bloqueia**: FASE_04_WRITE_TOOLS

---

## Objetivo

Criar a infraestrutura compartilhada por toda a família `Write*` especializada:

1. **Classe base `ValidatedWriteTool`** que padroniza o template `validate → safe_save → ack`.
2. **Helpers de erro acionável** (`format_syntax_error`, `format_snippet`) que produzem
   mensagens com linha/coluna/snippet — fundamentais para o loop de reparo funcionar.
3. **Gravação atômica** via `tempfile.NamedTemporaryFile` + `os.replace`, garantindo que
   nenhum arquivo half-written toque o path final.

A tarefa **não** introduz tools de tipos específicos — só a base. Cada tarefa 04–07 implementa
seus tipos consumindo essa base.

---

## Estrutura do Arquivo

### `src/vulpcode/tools/_validated_write.py`

```python
"""Base class for file-creation tools with built-in validation and atomic save.

A subclass overrides ``validate(content) -> None`` (raise on error) and gets:
- atomic save via tmp + rename
- detailed error messages routed back through ToolResult so the agent loop can drive a repair iteration
"""
from __future__ import annotations

import os
import tempfile
from abc import abstractmethod
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from vulpcode.tools.base import Tool, ToolResult


class ValidationError(Exception):
    """Raised by ValidatedWriteTool.validate() when content is not valid.

    Carry structured info so the formatter can produce a great error message:
    line, column, snippet, and a short reason.
    """

    def __init__(
        self,
        message: str,
        *,
        line: int | None = None,
        col: int | None = None,
        snippet: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.line = line
        self.col = col
        self.snippet = snippet

    def to_error_text(self) -> str:
        parts = [self.message]
        if self.line is not None:
            loc = f"at line {self.line}"
            if self.col is not None:
                loc += f", col {self.col}"
            parts.append(loc)
        body = " ".join(parts)
        if self.snippet:
            return f"{body}\n\n{self.snippet}"
        return body


def format_snippet(content: str, line: int, col: int | None = None, context: int = 2) -> str:
    """Render 'context' lines around `line` (1-based), with a caret pointing at `col`."""
    lines = content.splitlines()
    if not lines:
        return ""
    line = max(1, min(line, len(lines)))
    start = max(1, line - context)
    end = min(len(lines), line + context)
    width = len(str(end))
    out: list[str] = []
    for i in range(start, end + 1):
        marker = ">" if i == line else " "
        out.append(f"{marker} {i:>{width}} | {lines[i-1]}")
        if i == line and col is not None and col > 0:
            pad = " " * (width + 4 + col - 1)
            out.append(f"  {pad}^")
    return "\n".join(out)


class ValidatedWriteTool(Tool):
    """Template for file-creation tools.

    Subclasses MUST:
    - Declare ``class Input(BaseModel): file_path: str; content: str``
      (or add fields, but keep these two).
    - Implement ``validate(self, content: str, args: BaseModel) -> None``,
      raising :class:`ValidationError` on syntax/structural problems.
    - Optionally override ``transform(self, args) -> str`` to map args into
      the final on-disk bytes (e.g. WriteIpynb assembles cells -> JSON).
    - Optionally override ``binary`` to ``True`` and return ``bytes`` from
      ``transform`` (e.g. WritePdf, WriteDocx).

    The ``run`` method is final — do not override.
    """

    binary: bool = False

    @abstractmethod
    def validate(self, content: Any, args: BaseModel) -> None:
        """Raise ValidationError if `content` is not a valid file of this type."""

    def transform(self, args: BaseModel) -> Any:
        """Return the bytes/str to actually write. Default: args.content as-is."""
        return getattr(args, "content")

    async def run(self, args: BaseModel) -> ToolResult:  # type: ignore[override]
        # 1. Transform
        try:
            payload = self.transform(args)
        except ValidationError as ve:
            return ToolResult(error=ve.to_error_text(), is_error=True)
        except Exception as exc:
            return ToolResult(
                error=f"{type(exc).__name__} while transforming: {exc}",
                is_error=True,
            )

        # 2. Validate (pre-save)
        try:
            self.validate(payload, args)
        except ValidationError as ve:
            return ToolResult(
                error=ve.to_error_text(),
                is_error=True,
                metadata={"phase": "validate"},
            )
        except Exception as exc:
            return ToolResult(
                error=f"{type(exc).__name__} during validation: {exc}",
                is_error=True,
            )

        # 3. Atomic save
        path = Path(getattr(args, "file_path")).expanduser().resolve()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            mode = "wb" if self.binary else "w"
            data = payload if self.binary else (
                payload if isinstance(payload, str) else str(payload)
            )
            with tempfile.NamedTemporaryFile(
                mode=mode,
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
                encoding=None if self.binary else "utf-8",
            ) as tf:
                tf.write(data)
                tmp_path = Path(tf.name)
            os.replace(tmp_path, path)
        except OSError as exc:
            return ToolResult(
                error=f"Failed to write {path}: {exc}",
                is_error=True,
            )

        size = path.stat().st_size
        return ToolResult(
            output=f"Wrote {size} bytes to {path}",
            metadata={
                "file_path": str(path),
                "size": size,
                "validated": True,
                "tool": self._tool_name,
            },
        )
```

---

## Decisões de Design

1. **`validate` levanta exceção em vez de retornar bool**: força o autor da subclasse a
   carregar contexto (linha/col/snippet) sempre que possível.
2. **`transform` separado de `validate`**: tools binárias (`WriteDocx`, `WritePdf`) constroem
   o payload em `transform`, e o validador chama parsers (e.g. `python-docx` reabrindo o tmp)
   para confirmar que o resultado é bem-formado.
3. **Sem retry interno**: o loop de reparo é responsabilidade do agente — devolver erro bem
   descrito basta. Isso mantém a tool pura e fácil de testar.
4. **Sem confirmação aqui**: cada subclasse declara `requires_confirm=True` no `@tool` se
   quiser passar pelo `PermissionManager`. Comportamento default é `True` (gravação é
   destrutiva).
5. **Atomic save**: o `.tmp` no MESMO diretório do destino (não `/tmp`) — `os.replace`
   garante atomicidade só dentro do mesmo filesystem.

---

## Etapas

### Etapa 1 — Criar `src/vulpcode/tools/_validated_write.py`

Implementar `ValidationError`, `format_snippet`, `ValidatedWriteTool` conforme spec.

### Etapa 2 — Tests em `tests/test_tools/test_validated_write_base.py`

Usar uma subclasse fake na hora do teste:

```python
import pytest
from pydantic import BaseModel

from vulpcode.tools._validated_write import (
    ValidatedWriteTool, ValidationError, format_snippet,
)
from vulpcode.tools.base import tool, ToolResult


@tool(name="_Fake", description="fake for tests", requires_confirm=False)
class _FakeWrite(ValidatedWriteTool):
    class Input(BaseModel):
        file_path: str
        content: str

    def validate(self, content, args):
        if "BAD" in content:
            raise ValidationError(
                "marker BAD found",
                line=1, col=content.index("BAD") + 1,
                snippet=format_snippet(content, 1, content.index("BAD") + 1),
            )


@pytest.mark.asyncio
async def test_atomic_save_happy_path(tmp_path):
    target = tmp_path / "x.txt"
    res = await _FakeWrite().run(_FakeWrite.Input(file_path=str(target), content="ok"))
    assert res.is_error is False
    assert target.read_text() == "ok"
    assert not list(tmp_path.glob(".x.txt.*.tmp"))


@pytest.mark.asyncio
async def test_validation_error_blocks_save(tmp_path):
    target = tmp_path / "x.txt"
    res = await _FakeWrite().run(_FakeWrite.Input(file_path=str(target), content="BAD"))
    assert res.is_error is True
    assert "marker BAD found" in res.error
    assert "line 1" in res.error
    assert not target.exists()


@pytest.mark.asyncio
async def test_no_partial_file_on_validation_error(tmp_path):
    target = tmp_path / "x.txt"
    await _FakeWrite().run(_FakeWrite.Input(file_path=str(target), content="BAD"))
    leftovers = list(tmp_path.glob(".x.txt.*.tmp"))
    assert leftovers == []


def test_format_snippet_renders_caret():
    out = format_snippet("a\nb = 1 2\nc", line=2, col=7)
    assert "> 2 | b = 1 2" in out
    assert "^" in out


def test_format_snippet_handles_edges():
    out = format_snippet("only", line=1, col=1, context=5)
    assert "only" in out
```

### Etapa 3 — Atualizar `src/vulpcode/tools/__init__.py`

Não importar `_validated_write` aqui — é só base; o importador correto são as subclasses.

---

## Critérios de Aceite

- [x] `src/vulpcode/tools/_validated_write.py` exposto com `ValidatedWriteTool`,
      `ValidationError`, `format_snippet`
- [x] `validate` é abstrato — força implementação na subclasse
- [x] `transform` tem default que devolve `args.content`
- [x] `ValidationError.to_error_text()` produz texto com linha/col/snippet quando presentes
- [x] Gravação atômica funciona: tmp no mesmo diretório, `os.replace` no final
- [x] Sem tmp residual após falha de validação
- [x] >= 5 testes passando

---

## Riscos

| Risco | Probabilidade | Mitigação |
|-------|---------------|-----------|
| `tmp` em FS diferente do destino → `os.replace` falha cross-device | Baixa (tmp no mesmo dir) | `dir=path.parent` no NamedTemporaryFile |
| Snippet fica gigante em arquivo grande | Média | `context=2` por default; subclasses escolhem |
| Permissão de escrita negada no diretório pai | Baixa | OSError tratado, mensagem clara |

---

**End of Specification**
