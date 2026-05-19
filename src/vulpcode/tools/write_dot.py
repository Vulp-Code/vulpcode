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
