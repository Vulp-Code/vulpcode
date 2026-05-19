"""WriteYaml tool: write a .yaml file, validated via yaml.safe_load."""
from __future__ import annotations

from pydantic import BaseModel

from vulpcode.tools._validated_write import (
    ValidatedWriteTool,
    ValidationError,
    format_snippet,
)
from vulpcode.tools.base import tool


@tool(
    name="WriteYaml",
    description=(
        "Create or overwrite a YAML file. Validates with yaml.safe_load BEFORE saving. "
        "On YAMLError the file is NOT written and the line/column of the failure are "
        "returned for you to fix and resubmit. Requires PyYAML (pip install vulpcode[docs-tools])."
    ),
    requires_confirm=True,
)
class WriteYamlTool(ValidatedWriteTool):
    class Input(BaseModel):
        file_path: str
        content: str

    def validate(self, content, args):
        try:
            import yaml
        except ImportError:
            raise ValidationError(
                "WriteYaml requires PyYAML. pip install vulpcode[docs-tools]"
            )
        try:
            yaml.safe_load(content)
        except yaml.YAMLError as e:
            line = getattr(getattr(e, "problem_mark", None), "line", None)
            col = getattr(getattr(e, "problem_mark", None), "column", None)
            raise ValidationError(
                f"YAMLError: {e}",
                line=(line + 1) if line is not None else None,
                col=(col + 1) if col is not None else None,
                snippet=format_snippet(content, (line or 0) + 1, (col or 0) + 1)
                if line is not None
                else None,
            )
