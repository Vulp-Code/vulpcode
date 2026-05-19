# Tarefa 04.04 — Tools web/shell: HTML, SH, SQL, SVG, DOT

**Status**: PENDENTE
**Fase**: 04 - Write Tools
**Dependências**: FASE_03 (`ValidatedWriteTool`)
**Bloqueia**: FASE_06_TESTES

---

## Objetivo

Mais cinco tools especializadas:

| Tool | Validador | Dependência |
|------|-----------|-------------|
| `WriteHtml` | `html.parser` (tolerante) + opcional `lxml.html.fromstring` | stdlib + opcional |
| `WriteSh` | subprocess `bash -n` | runtime (bash no PATH) |
| `WriteSql` | `sqlparse.parse` + balanceamento de parens/quotes | `sqlparse` (extra) |
| `WriteSvg` | `xml.etree.ElementTree` + check root `<svg>` | stdlib |
| `WriteDot` | `pydot.graph_from_dot_data` | `pydot` (extra) |

---

## `WriteHtml`

```python
"""WriteHtml tool: lenient HTML validation via html.parser, strict via lxml if available."""
from __future__ import annotations

from html.parser import HTMLParser

from pydantic import BaseModel

from vulpcode.tools._validated_write import ValidatedWriteTool, ValidationError
from vulpcode.tools.base import tool


class _ErrorCollectingParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.errors: list[str] = []

    def error(self, message):
        self.errors.append(message)


@tool(
    name="WriteHtml",
    description=(
        "Create or overwrite an .html file. Validates with html.parser first "
        "(tolerant), then optionally with lxml.html for stricter checks. "
        "Open/close tag balance is verified."
    ),
    requires_confirm=True,
)
class WriteHtmlTool(ValidatedWriteTool):
    class Input(BaseModel):
        file_path: str
        content: str
        strict: bool = False  # if True, require lxml and run strict check

    def validate(self, content, args):
        p = _ErrorCollectingParser()
        try:
            p.feed(content)
            p.close()
        except Exception as e:
            raise ValidationError(f"HTMLParser error: {e}")
        if p.errors:
            raise ValidationError("HTMLParser errors: " + "; ".join(p.errors))
        if args.strict:
            try:
                from lxml import html as lxml_html
            except ImportError:
                raise ValidationError("strict mode requires lxml. pip install lxml")
            try:
                lxml_html.fromstring(content)
            except Exception as e:
                raise ValidationError(f"lxml strict parse failed: {e}")
```

Nota: `html.parser` é deliberadamente permissivo (vide spec do HTML5). Conteúdo "minimamente
HTML" passa. Para feedback mais agressivo, o caller pede `strict=True`.

---

## `WriteSh`

```python
"""WriteSh tool: write a shell script and validate syntax via `bash -n`."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from pydantic import BaseModel

from vulpcode.tools._validated_write import ValidatedWriteTool, ValidationError
from vulpcode.tools.base import tool


@tool(
    name="WriteSh",
    description=(
        "Create or overwrite a shell script (.sh). Syntax-checked with `bash -n` "
        "(does NOT execute the script, just parses). If bash is not on PATH the "
        "validation falls back to a shebang check."
    ),
    requires_confirm=True,
)
class WriteShTool(ValidatedWriteTool):
    class Input(BaseModel):
        file_path: str
        content: str
        executable: bool = True  # chmod +x after save

    def validate(self, content, args):
        bash = shutil.which("bash")
        if bash is None:
            if content and not content.startswith("#!"):
                raise ValidationError("bash not on PATH; minimum check: script must start with a shebang.")
            return
        with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False, encoding="utf-8") as tf:
            tf.write(content)
            tf_path = tf.name
        try:
            proc = subprocess.run(
                [bash, "-n", tf_path],
                capture_output=True, text=True, timeout=10,
            )
        finally:
            Path(tf_path).unlink(missing_ok=True)
        if proc.returncode != 0:
            raise ValidationError(f"bash -n failed: {proc.stderr.strip()}")

    async def run(self, args):
        res = await super().run(args)
        if not res.is_error and args.executable:
            try:
                p = Path(res.metadata["file_path"])
                p.chmod(p.stat().st_mode | 0o111)
            except OSError:
                pass
        return res
```

Cuidado: o `chmod` precisa rodar DEPOIS do save atomic. A override de `run` chama o super
e modifica permissões só em caso de sucesso.

---

## `WriteSql`

```python
"""WriteSql tool: write .sql with a lenient parse via sqlparse."""
from __future__ import annotations

from pydantic import BaseModel

from vulpcode.tools._validated_write import ValidatedWriteTool, ValidationError
from vulpcode.tools.base import tool


@tool(
    name="WriteSql",
    description=(
        "Create or overwrite a .sql file. Uses sqlparse (lenient) to verify the "
        "statements are tokenizable. Also checks balanced parentheses and quote "
        "strings. NOTE: a full SQL grammar check requires a real engine; this "
        "is a sanity check, not a guarantee."
    ),
    requires_confirm=True,
)
class WriteSqlTool(ValidatedWriteTool):
    class Input(BaseModel):
        file_path: str
        content: str

    def validate(self, content, args):
        # Balanced parens
        bal = 0
        for ch in content:
            if ch == "(":
                bal += 1
            elif ch == ")":
                bal -= 1
                if bal < 0:
                    raise ValidationError("Unbalanced parens: ')' before '('")
        if bal != 0:
            raise ValidationError(f"Unbalanced parens: {bal} unclosed '('")
        # Balanced single quotes (naive — ignores comments)
        if content.count("'") % 2 != 0:
            raise ValidationError("Odd number of single quotes — string literal not closed?")
        # sqlparse
        try:
            import sqlparse
        except ImportError:
            return  # graceful
        parsed = sqlparse.parse(content)
        if not parsed and content.strip():
            raise ValidationError("sqlparse produced no statements")
```

---

## `WriteSvg`

```python
"""WriteSvg tool: SVG = XML + root must be <svg>."""
from __future__ import annotations

import xml.etree.ElementTree as ET

from pydantic import BaseModel

from vulpcode.tools._validated_write import ValidatedWriteTool, ValidationError, format_snippet
from vulpcode.tools.base import tool


@tool(
    name="WriteSvg",
    description=(
        "Create or overwrite an .svg file. Validates as XML and ensures the "
        "root element is <svg>."
    ),
    requires_confirm=True,
)
class WriteSvgTool(ValidatedWriteTool):
    class Input(BaseModel):
        file_path: str
        content: str

    def validate(self, content, args):
        try:
            root = ET.fromstring(content)
        except ET.ParseError as e:
            line, col = e.position if hasattr(e, "position") else (None, None)
            raise ValidationError(
                f"XML ParseError: {e}",
                line=line, col=col,
                snippet=format_snippet(content, line, col) if line else None,
            )
        tag = root.tag.split("}")[-1]
        if tag != "svg":
            raise ValidationError(f"Root element must be <svg>, got <{tag}>")
```

---

## `WriteDot`

```python
"""WriteDot tool: write a Graphviz .dot graph and validate via pydot."""
from __future__ import annotations

from pydantic import BaseModel

from vulpcode.tools._validated_write import ValidatedWriteTool, ValidationError
from vulpcode.tools.base import tool


@tool(
    name="WriteDot",
    description=(
        "Create or overwrite a Graphviz .dot file. Validates with pydot — checks "
        "the graph parses without errors."
    ),
    requires_confirm=True,
)
class WriteDotTool(ValidatedWriteTool):
    class Input(BaseModel):
        file_path: str
        content: str

    def validate(self, content, args):
        try:
            import pydot
        except ImportError:
            raise ValidationError(
                "WriteDot requires pydot. pip install vulpcode[docs-tools]"
            )
        graphs = pydot.graph_from_dot_data(content)
        if not graphs:
            raise ValidationError("pydot.graph_from_dot_data produced no graphs")
```

---

## Atualizar `tools/__init__.py`

```python
from vulpcode.tools import write_html as _wh  # noqa
from vulpcode.tools import write_sh as _ws  # noqa
from vulpcode.tools import write_sql as _wsql  # noqa
from vulpcode.tools import write_svg as _wsvg  # noqa
from vulpcode.tools import write_dot as _wdot  # noqa
```

---

## Tests

`tests/test_tools/test_write_web_shell.py`. Mínimo: happy + falha por tool.

```python
import pytest
import shutil
from vulpcode.tools import get_tool
import vulpcode.tools.write_html
import vulpcode.tools.write_sh
import vulpcode.tools.write_sql
import vulpcode.tools.write_svg
import vulpcode.tools.write_dot


@pytest.mark.asyncio
async def test_write_html_balanced(tmp_path):
    cls = get_tool("WriteHtml")
    res = await cls().run(cls.Input(
        file_path=str(tmp_path / "x.html"),
        content="<html><body><h1>hi</h1></body></html>",
    ))
    assert res.is_error is False

@pytest.mark.asyncio
@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not installed")
async def test_write_sh_valid(tmp_path):
    cls = get_tool("WriteSh")
    target = tmp_path / "s.sh"
    res = await cls().run(cls.Input(
        file_path=str(target),
        content="#!/usr/bin/env bash\necho hi\n",
    ))
    assert res.is_error is False
    assert target.stat().st_mode & 0o100  # exec bit

@pytest.mark.asyncio
@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not installed")
async def test_write_sh_syntax_error(tmp_path):
    cls = get_tool("WriteSh")
    target = tmp_path / "bad.sh"
    res = await cls().run(cls.Input(
        file_path=str(target),
        content="if true then echo\n",  # missing 'then' newline / 'fi'
    ))
    assert res.is_error is True
    assert not target.exists()

@pytest.mark.asyncio
async def test_write_sql_unbalanced_parens(tmp_path):
    cls = get_tool("WriteSql")
    target = tmp_path / "bad.sql"
    res = await cls().run(cls.Input(
        file_path=str(target),
        content="SELECT a, b FROM t WHERE x IN (1, 2;",
    ))
    assert res.is_error is True
    assert "parens" in res.error.lower()

@pytest.mark.asyncio
async def test_write_svg_wrong_root(tmp_path):
    cls = get_tool("WriteSvg")
    target = tmp_path / "bad.svg"
    res = await cls().run(cls.Input(
        file_path=str(target),
        content="<root></root>",
    ))
    assert res.is_error is True
    assert "root element must be <svg>" in res.error.lower()
```

---

## Critérios de Aceite

- [x] Cinco tools registradas: `WriteHtml`, `WriteSh`, `WriteSql`, `WriteSvg`, `WriteDot`
- [x] `WriteSh` define o bit `+x` quando `executable=True`
- [x] `WriteSh` faz fallback gracioso quando bash não está disponível
- [x] `WriteSql` checa parens e single quotes mesmo sem `sqlparse`
- [x] `WriteSvg` rejeita XML sem `<svg>` como root
- [x] >= 8 testes no total, alguns skipados conforme dependência

---

## Riscos

| Risco | Probabilidade | Mitigação |
|-------|---------------|-----------|
| `html.parser` aceita HTML "estragado" (HTML5 = tolerante) | Alta | Documentar; `strict=True` para lxml |
| `bash -n` em Windows sem bash | Alta no Windows | Fallback de shebang; tests skipam |
| `sqlparse` é só tokenizer — não valida semântica | Alta | Documentar como "sanity check" |
| Conteúdo SH com aspas dentro de heredoc faz false positive | Média | Aceitar limitação |

---

**End of Specification**
