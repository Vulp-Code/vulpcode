"""WriteCsv tool: write a .csv file, validated for parseability and uniform column count."""
from __future__ import annotations

import csv
import io

from pydantic import BaseModel

from vulpcode.tools._validated_write import (
    ValidatedWriteTool,
    ValidationError,
    format_snippet,
)
from vulpcode.tools.base import tool


@tool(
    name="WriteCsv",
    description=(
        "Create or overwrite a CSV file. Accepts either structured rows (list of lists) "
        "or raw CSV text. Validates that all rows have the same number of columns BEFORE "
        "saving. On error the file is NOT written."
    ),
    requires_confirm=True,
)
class WriteCsvTool(ValidatedWriteTool):
    class Input(BaseModel):
        file_path: str
        rows: list[list[str]] | None = None
        content: str | None = None
        delimiter: str = ","
        quotechar: str = '"'
        has_header: bool = True

    def transform(self, args):
        if args.rows is not None:
            buf = io.StringIO()
            w = csv.writer(buf, delimiter=args.delimiter, quotechar=args.quotechar)
            for row in args.rows:
                w.writerow(row)
            return buf.getvalue()
        return args.content or ""

    def validate(self, content, args):
        reader = csv.reader(
            io.StringIO(content),
            delimiter=args.delimiter,
            quotechar=args.quotechar,
        )
        col_count: int | None = None
        for i, row in enumerate(reader):
            if col_count is None:
                col_count = len(row)
            elif len(row) != col_count:
                raise ValidationError(
                    f"CSV row {i} has {len(row)} cols, expected {col_count}",
                    line=i + 1,
                    snippet=format_snippet(content, i + 1),
                )
