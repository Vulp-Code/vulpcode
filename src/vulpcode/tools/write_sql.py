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
