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
