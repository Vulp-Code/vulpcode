"""WritePdf tool: create a .pdf from markdown (weasyprint preferred, reportlab fallback)."""
from __future__ import annotations

from pydantic import BaseModel

from vulpcode.tools._validated_write import (
    ValidatedWriteTool,
    ValidationError,
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
        try:
            from weasyprint import HTML
            from markdown_it import MarkdownIt
            html = MarkdownIt().render(args.markdown)
            full = f"<html><head><title>{args.title}</title></head><body>{html}</body></html>"
            return HTML(string=full).write_pdf()
        except ImportError:
            pass
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
                    c.showPage()
                    y = height - 50
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
            import pypdf
            import io
            pypdf.PdfReader(io.BytesIO(content))
        except ImportError:
            raise ValidationError(
                "WritePdf validation requires pypdf. Install with: "
                "pip install vulpcode[docs-tools]"
            )
        except Exception as e:
            raise ValidationError(f"Generated PDF could not be reparsed: {e}")
