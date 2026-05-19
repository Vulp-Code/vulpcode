"""WriteXml tool: write a .xml file, validated via xml.etree.ElementTree."""
from __future__ import annotations

import xml.etree.ElementTree as ET

from pydantic import BaseModel

from vulpcode.tools._validated_write import (
    ValidatedWriteTool,
    ValidationError,
    format_snippet,
)
from vulpcode.tools.base import tool


@tool(
    name="WriteXml",
    description=(
        "Create or overwrite an XML file. Validates with xml.etree.ElementTree BEFORE "
        "saving. On ParseError the file is NOT written and the line/column of the "
        "failure are returned for you to fix and resubmit."
    ),
    requires_confirm=True,
)
class WriteXmlTool(ValidatedWriteTool):
    class Input(BaseModel):
        file_path: str
        content: str

    def validate(self, content, args):
        try:
            ET.fromstring(content)
        except ET.ParseError as e:
            line, col = e.position if hasattr(e, "position") else (None, None)
            raise ValidationError(
                f"XML ParseError: {e}",
                line=line,
                col=col,
                snippet=format_snippet(content, line, col) if line else None,
            )
