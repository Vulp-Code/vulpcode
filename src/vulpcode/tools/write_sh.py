"""WriteSh tool: write a shell script and validate syntax via `bash -n`."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from pydantic import BaseModel

from vulpcode.tools._validated_write import ValidatedWriteTool, ValidationError
from vulpcode.tools.base import tool


@tool(
    name="WriteSh",
    description=(
        "Create or overwrite a shell script (.sh). Syntax-checked with `bash -n` "
        "(does NOT execute the script, just parses). If bash is not on PATH the "
        "validation falls back to a shebang check."
    ),
    requires_confirm=True,
)
class WriteShTool(ValidatedWriteTool):
    class Input(BaseModel):
        file_path: str
        content: str
        executable: bool = True  # chmod +x after save

    def validate(self, content, args):
        bash = shutil.which("bash")
        if bash is None:
            if content and not content.startswith("#!"):
                raise ValidationError(
                    "bash not on PATH; minimum check: script must start with a shebang."
                )
            return
        with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False, encoding="utf-8") as tf:
            tf.write(content)
            tf_path = tf.name
        try:
            proc = subprocess.run(
                [bash, "-n", tf_path],
                capture_output=True, text=True, timeout=10,
            )
        finally:
            Path(tf_path).unlink(missing_ok=True)
        if proc.returncode != 0:
            raise ValidationError(f"bash -n failed: {proc.stderr.strip()}")

    async def run(self, args):
        res = await super().run(args)
        if not res.is_error and args.executable:
            try:
                p = Path(res.metadata["file_path"])
                p.chmod(p.stat().st_mode | 0o111)
            except OSError:
                pass
        return res
