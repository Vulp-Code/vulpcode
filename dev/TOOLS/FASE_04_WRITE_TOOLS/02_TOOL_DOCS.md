# Tarefa 04.02 — Tools de documentação: `WriteMd`, `WriteDocx`, `WritePdf`

**Status**: PENDENTE
**Fase**: 04 - Write Tools
**Dependências**: FASE_03 (`ValidatedWriteTool`)
**Bloqueia**: FASE_06_TESTES

---

## Objetivo

Adicionar três tools para arquivos de documentação:

- **`WriteMd`** — `.md` com validação leve via `markdown-it-py`.
- **`WriteDocx`** — `.docx` montado via `python-docx` a partir de uma estrutura de seções
  (heading, paragraph, list, code) OU a partir de Markdown.
- **`WritePdf`** — `.pdf` gerado a partir de Markdown (`reportlab` para texto puro,
  ou `weasyprint` se disponível para HTML estilizado).

Todas as três pertencem ao extra `docs-tools` (declarado em `pyproject.toml`).

---

## `WriteMd`

### `src/vulpcode/tools/write_md.py`

```python
"""WriteMd tool: create or overwrite a Markdown (.md) file with sanity checks."""
from __future__ import annotations

from pydantic import BaseModel

from vulpcode.tools._validated_write import (
    ValidatedWriteTool, ValidationError,
)
from vulpcode.tools.base import tool


@tool(
    name="WriteMd",
    description=(
        "Create or overwrite a Markdown (.md) file. Validates with markdown-it-py: "
        "checks the parser tokenizes the document without exceptions and flags "
        "obvious problems like unclosed code fences."
    ),
    requires_confirm=True,
)
class WriteMdTool(ValidatedWriteTool):
    class Input(BaseModel):
        file_path: str
        content: str

    def validate(self, content, args):
        # Cheap rule first: unbalanced ``` fences
        fence_count = sum(1 for line in content.splitlines() if line.startswith("```"))
        if fence_count % 2 != 0:
            raise ValidationError(
                f"Unbalanced code fences: found {fence_count} '```' lines (must be even)."
            )
        # markdown-it parse — if installed
        try:
            from markdown_it import MarkdownIt
        except ImportError:
            return  # graceful degradation: the fence check is enough
        try:
            MarkdownIt().parse(content)
        except Exception as e:
            raise ValidationError(f"markdown-it failed to parse: {e}")
```

---

## `WriteDocx`

### Design da Input

Aceitar uma estrutura de seções (mais fácil pro modelo seguir do que escrever XML cru) E
um modo "from markdown" como conveniência.

```python
class _Block(BaseModel):
    kind: Literal["heading", "paragraph", "bullets", "numbered", "code", "image"]
    text: str | list[str] = ""
    level: int = 1     # for heading
    language: str = "" # for code

class Input(BaseModel):
    file_path: str
    title: str = ""
    blocks: list[_Block] | None = None     # structured mode
    markdown: str | None = None            # convenience mode
```

Regra: se `markdown` está presente, converte para `blocks` via parser leve antes de
construir o docx. Se `blocks` está presente, usa direto.

### `src/vulpcode/tools/write_docx.py`

```python
"""WriteDocx tool: build a .docx via python-docx with structured input."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from vulpcode.tools._validated_write import (
    ValidatedWriteTool, ValidationError,
)
from vulpcode.tools.base import tool


class _Block(BaseModel):
    kind: Literal["heading", "paragraph", "bullets", "numbered", "code"]
    text: str | list[str] = ""
    level: int = 1
    language: str = ""


def _markdown_to_blocks(md: str) -> list[_Block]:
    """Tiny MD->blocks converter (headings, paragraphs, bullets, fenced code)."""
    blocks: list[_Block] = []
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            lang = line[3:].strip()
            code: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code.append(lines[i]); i += 1
            blocks.append(_Block(kind="code", text="\n".join(code), language=lang))
            i += 1; continue
        m = 0
        while m < len(line) and line[m] == "#": m += 1
        if 0 < m <= 6 and m < len(line) and line[m] == " ":
            blocks.append(_Block(kind="heading", text=line[m+1:].strip(), level=m))
            i += 1; continue
        if line.lstrip().startswith(("- ", "* ")):
            items: list[str] = []
            while i < len(lines) and lines[i].lstrip().startswith(("- ", "* ")):
                items.append(lines[i].lstrip()[2:]); i += 1
            blocks.append(_Block(kind="bullets", text=items))
            continue
        if line.strip():
            para: list[str] = []
            while i < len(lines) and lines[i].strip():
                para.append(lines[i]); i += 1
            blocks.append(_Block(kind="paragraph", text=" ".join(para)))
            continue
        i += 1
    return blocks


@tool(
    name="WriteDocx",
    description=(
        "Create or overwrite a Word document (.docx). Pass either `blocks` "
        "(structured: heading/paragraph/bullets/numbered/code) or `markdown` "
        "(converted internally). The file is validated by re-opening it with "
        "python-docx before commit."
    ),
    requires_confirm=True,
)
class WriteDocxTool(ValidatedWriteTool):
    binary = True

    class Input(BaseModel):
        file_path: str
        title: str = ""
        blocks: list[_Block] | None = None
        markdown: str | None = None

        @model_validator(mode="after")
        def _need_one(self):
            if self.blocks is None and self.markdown is None:
                raise ValueError("provide either `blocks` or `markdown`")
            return self

    def transform(self, args):
        try:
            from docx import Document
        except ImportError:
            raise ValidationError(
                "WriteDocx requires python-docx. Install with: pip install vulpcode[docs-tools]"
            )
        import io
        blocks = args.blocks if args.blocks is not None else _markdown_to_blocks(args.markdown or "")
        doc = Document()
        if args.title:
            doc.add_heading(args.title, level=0)
        for b in blocks:
            if b.kind == "heading":
                doc.add_heading(b.text if isinstance(b.text, str) else " ".join(b.text), level=b.level)
            elif b.kind == "paragraph":
                doc.add_paragraph(b.text if isinstance(b.text, str) else " ".join(b.text))
            elif b.kind == "bullets":
                items = b.text if isinstance(b.text, list) else [b.text]
                for it in items:
                    doc.add_paragraph(it, style="List Bullet")
            elif b.kind == "numbered":
                items = b.text if isinstance(b.text, list) else [b.text]
                for it in items:
                    doc.add_paragraph(it, style="List Number")
            elif b.kind == "code":
                code = b.text if isinstance(b.text, str) else "\n".join(b.text)
                p = doc.add_paragraph()
                run = p.add_run(code)
                run.font.name = "Courier New"
        buf = io.BytesIO()
        doc.save(buf)
        return buf.getvalue()

    def validate(self, content, args):
        # Re-open the bytes we just built to confirm validity
        try:
            from docx import Document
            import io
            Document(io.BytesIO(content))
        except Exception as e:
            raise ValidationError(f"Failed to re-open generated .docx: {e}")
```

---

## `WritePdf`

### Estratégia

Duas vias, em ordem de preferência:

1. **`weasyprint`** (se instalado): markdown → HTML (via `markdown-it`) → PDF estilizado.
2. **Fallback `reportlab`**: monta PDF de texto simples (headings em fonte maior, parágrafos
   em fonte normal, code em monospace). Sem CSS.

### `src/vulpcode/tools/write_pdf.py` (esqueleto)

```python
"""WritePdf tool: create a .pdf from markdown (weasyprint preferred, reportlab fallback)."""
from __future__ import annotations

from pydantic import BaseModel

from vulpcode.tools._validated_write import (
    ValidatedWriteTool, ValidationError,
)
from vulpcode.tools.base import tool


@tool(
    name="WritePdf",
    description=(
        "Create a PDF from Markdown. If `weasyprint` is available it produces a "
        "styled PDF; otherwise falls back to a plain-text reportlab render. "
        "Validates the result by re-parsing with pypdf."
    ),
    requires_confirm=True,
)
class WritePdfTool(ValidatedWriteTool):
    binary = True

    class Input(BaseModel):
        file_path: str
        markdown: str
        title: str = ""

    def transform(self, args):
        # Try weasyprint
        try:
            from weasyprint import HTML
            from markdown_it import MarkdownIt
            html = MarkdownIt().render(args.markdown)
            full = f"<html><head><title>{args.title}</title></head><body>{html}</body></html>"
            return HTML(string=full).write_pdf()
        except ImportError:
            pass
        # Fallback: reportlab plain text
        try:
            from reportlab.lib.pagesizes import LETTER
            from reportlab.pdfgen import canvas
            import io
            buf = io.BytesIO()
            c = canvas.Canvas(buf, pagesize=LETTER)
            width, height = LETTER
            y = height - 50
            for line in args.markdown.splitlines() or [""]:
                if y < 50:
                    c.showPage(); y = height - 50
                c.drawString(50, y, line[:120])
                y -= 14
            c.save()
            return buf.getvalue()
        except ImportError:
            raise ValidationError(
                "WritePdf needs weasyprint OR reportlab. Install with: "
                "pip install vulpcode[docs-tools]"
            )

    def validate(self, content, args):
        try:
            import pypdf, io
            pypdf.PdfReader(io.BytesIO(content))
        except Exception as e:
            raise ValidationError(f"Generated PDF could not be reparsed: {e}")
```

---

## Tests

Tests files: `tests/test_tools/test_write_md.py`, `test_write_docx.py`, `test_write_pdf.py`.

Cada um:

- 1–2 happy paths (valid input → arquivo é gravado e reabre OK)
- 1 failure path (no caso de `WriteMd`: fence ímpar)
- Skip via `pytest.importorskip(...)` quando dependência opcional faltar

---

## Atualizar `tools/__init__.py`

```python
from vulpcode.tools import write_md as _write_md  # noqa
from vulpcode.tools import write_docx as _write_docx  # noqa
from vulpcode.tools import write_pdf as _write_pdf  # noqa
```

---

## Critérios de Aceite

- [x] `WriteMd` registrado, detecta fences ímpares e devolve erro
- [x] `WriteDocx` aceita `blocks` estruturados e `markdown`; gera arquivo reabrível
- [x] `WritePdf` usa weasyprint se disponível, senão reportlab; pypdf reabre o resultado
- [x] Mensagens de "dependência faltando" são claras (sugerem `pip install vulpcode[docs-tools]`)
- [x] >= 6 testes no total entre os três (alguns skipados sem deps)

---

## Riscos

| Risco | Probabilidade | Mitigação |
|-------|---------------|-----------|
| weasyprint depende de libs nativas (cairo, pango) — pode falhar no Windows | Alta | reportlab é o fallback portátil |
| `_markdown_to_blocks` é simplista demais para tabelas/links | Alta | Aceitar limitação; modelo pode usar `blocks` direto |
| `python-docx` versão velha não tem `style="List Bullet"` | Baixa | Pinar `python-docx>=1.1` no extra |

---

**End of Specification**
