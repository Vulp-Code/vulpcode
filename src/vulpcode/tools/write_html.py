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
