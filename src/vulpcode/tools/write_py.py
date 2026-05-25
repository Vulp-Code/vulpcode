"""WritePy tool: create or overwrite a .py file, validating syntax via ast.parse."""
from __future__ import annotations
import ast
import shutil
import subprocess
import sys
from pathlib import Path
from pydantic import BaseModel
from vulpcode.tools._validated_write import ValidatedWriteTool, ValidationError, format_snippet
from vulpcode.tools.base import tool


def _run_ruff(content, filename):
    ruff = shutil.which("ruff")
    if ruff is None:
        return None
    try:
        proc = subprocess.run([ruff, "check", "--stdin-filename", filename, "-"], input=content, capture_output=True, text=True, timeout=15)
        if proc.returncode != 0 and proc.stdout.strip():
            return "Lint error(s):\n" + proc.stdout.strip()
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None


def _smoke_import(file_path, content):
    p = Path(file_path).resolve()
    if not (p.parent / "__init__.py").exists():
        return None
    root = p
    while root.parent != root:
        if (root / "pyproject.toml").exists():
            break
        root = root.parent
    if not (root / "pyproject.toml").exists():
        return None
    try:
        result = subprocess.run([sys.executable, "-c", content], capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            err = result.stderr.strip()
            if "ModuleNotFoundError" in err or "ImportError" in err:
                lines = err.splitlines()
                return "Smoke import failed: " + (lines[-1] if lines else err)
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None


@tool(name="WritePy", description="Create or overwrite a Python (.py) file. Validates with ast.parse() before saving.", requires_confirm=True)
class WritePyTool(ValidatedWriteTool):
    class Input(BaseModel):
        file_path: str
        content: str

    def validate(self, content, args):
        try:
            ast.parse(content, filename=args.file_path)
        except SyntaxError as exc:
            line = exc.lineno or 1
            col = exc.offset or None
            raise ValidationError(f"SyntaxError: {exc.msg}", line=line, col=col, snippet=format_snippet(content, line, col))
        lint_err = _run_ruff(content, getattr(args, "file_path", "<unknown>"))
        if lint_err:
            raise ValidationError(lint_err)
        smoke_err = _smoke_import(getattr(args, "file_path", ""), content)
        if smoke_err:
            raise ValidationError(smoke_err)
