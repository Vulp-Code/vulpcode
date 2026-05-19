"""WriteIpynb tool: build and write a Jupyter .ipynb with validation."""
from __future__ import annotations

import ast
import json
import uuid
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from vulpcode.tools._validated_write import (
    ValidatedWriteTool,
    ValidationError,
    format_snippet,
)
from vulpcode.tools.base import tool


class _Cell(BaseModel):
    type: Literal["code", "markdown"] = "code"
    source: str = ""


@tool(
    name="WriteIpynb",
    description=(
        "Create or overwrite a Jupyter notebook (.ipynb). Prefer passing `cells` "
        "as a list of {type, source} — the tool assembles the JSON for you. "
        "Each code cell is validated with ast.parse(); the whole notebook is "
        "validated with nbformat.validate(). On any error the file is NOT "
        "written and the precise failure is returned for you to fix and resubmit."
    ),
    requires_confirm=True,
)
class WriteIpynbTool(ValidatedWriteTool):
    class Input(BaseModel):
        file_path: str
        cells: list[_Cell] | None = None
        content: str | None = None  # raw JSON fallback
        metadata: dict = Field(default_factory=dict)

        @model_validator(mode="after")
        def _need_one(self):
            if self.cells is None and self.content is None:
                raise ValueError("provide either `cells` or `content`")
            return self

    def transform(self, args):
        if args.cells is not None:
            nb = {
                "cells": [
                    {
                        "cell_type": c.type,
                        "id": uuid.uuid4().hex[:8],
                        "metadata": {},
                        "source": c.source.splitlines(keepends=True),
                        **({"outputs": [], "execution_count": None}
                           if c.type == "code" else {}),
                    }
                    for c in args.cells
                ],
                "metadata": {
                    "kernelspec": {
                        "display_name": "Python 3",
                        "language": "python",
                        "name": "python3",
                    },
                    "language_info": {"name": "python"},
                    **args.metadata,
                },
                "nbformat": 4,
                "nbformat_minor": 5,
            }
            return json.dumps(nb, indent=1)
        return args.content  # raw JSON path

    def validate(self, content, args):
        # JSON parse
        try:
            nb = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValidationError(
                f"Notebook is not valid JSON: {e.msg}",
                line=e.lineno,
                col=e.colno,
                snippet=format_snippet(content, e.lineno, e.colno),
            )
        # nbformat structural validation
        try:
            import nbformat
        except ImportError:
            raise ValidationError(
                "WriteIpynb requires nbformat. Install with: pip install vulpcode[docs-tools]"
            )
        try:
            nbformat.validate(nb)
        except Exception as e:
            raise ValidationError(f"nbformat.validate failed: {e}")
        # AST check on each code cell
        for i, cell in enumerate(nb.get("cells", [])):
            if cell.get("cell_type") != "code":
                continue
            src = cell.get("source", "")
            if isinstance(src, list):
                src = "".join(src)
            try:
                ast.parse(src, filename=f"<cell {i}>")
            except SyntaxError as exc:
                raise ValidationError(
                    f"SyntaxError in code cell #{i}: {exc.msg}",
                    line=exc.lineno or 1,
                    col=exc.offset,
                    snippet=format_snippet(src, exc.lineno or 1, exc.offset),
                )
