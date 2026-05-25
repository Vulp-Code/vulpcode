"""Re-validation dispatchers for the ``Edit`` / ``MultiEdit`` tools.

After an edit we want the same safety guarantees the Write* tools provide:
if a Python file gets a SyntaxError, JSON loses a brace, TOML stops parsing,
etc., the edit is rolled back rather than landing on disk.

This module dispatches by file extension to a lightweight validator that
returns an error string (or ``None`` on success). The validators are
intentionally a subset of what the matching Write* tool runs — we keep the
cheap, deterministic checks (parsers) and skip the optional external linters
(ruff, shellcheck, sqlfluff) so an Edit doesn't suddenly fail because of an
unrelated style issue elsewhere in the file.
"""
from __future__ import annotations

import ast
import json
import shutil
import subprocess
import tempfile
import tomllib
from pathlib import Path
from typing import Callable


def _py(content: str, file_path: str) -> str | None:
    try:
        ast.parse(content, filename=file_path)
    except SyntaxError as exc:
        line = exc.lineno or 1
        col = exc.offset or 0
        return f"SyntaxError at line {line}, col {col}: {exc.msg}"
    return None


def _json(content: str, _file_path: str) -> str | None:
    if not content.strip():
        return None
    try:
        json.loads(content)
    except json.JSONDecodeError as exc:
        return f"JSONDecodeError at line {exc.lineno}, col {exc.colno}: {exc.msg}"
    return None


def _yaml(content: str, _file_path: str) -> str | None:
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        return None
    try:
        yaml.safe_load(content)
    except yaml.YAMLError as exc:
        return f"YAMLError: {exc}"
    return None


def _toml(content: str, _file_path: str) -> str | None:
    try:
        tomllib.loads(content)
    except tomllib.TOMLDecodeError as exc:
        return f"TOMLDecodeError: {exc}"
    return None


def _sh(content: str, _file_path: str) -> str | None:
    bash = shutil.which("bash")
    if bash is None:
        return None
    with tempfile.NamedTemporaryFile(
        "w", suffix=".sh", delete=False, encoding="utf-8"
    ) as tf:
        tf.write(content)
        tf_path = tf.name
    try:
        proc = subprocess.run(
            [bash, "-n", tf_path],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    finally:
        Path(tf_path).unlink(missing_ok=True)
    if proc.returncode != 0:
        return f"bash -n failed: {proc.stderr.strip()}"
    return None


def _xml(content: str, _file_path: str) -> str | None:
    if not content.strip():
        return None
    from xml.etree import ElementTree as ET
    try:
        ET.fromstring(content)
    except ET.ParseError as exc:
        return f"XML ParseError: {exc}"
    return None


_DISPATCH: dict[str, Callable[[str, str], str | None]] = {
    ".py": _py,
    ".json": _json,
    ".ipynb": _json,
    ".yaml": _yaml,
    ".yml": _yaml,
    ".toml": _toml,
    ".sh": _sh,
    ".bash": _sh,
    ".xml": _xml,
    ".svg": _xml,
}


def validate_after_edit(file_path: str, content: str) -> str | None:
    """Return an error string if ``content`` is invalid for the file's type.

    Unknown extensions return ``None`` (no validator → nothing to check).
    """
    ext = Path(file_path).suffix.lower()
    validator = _DISPATCH.get(ext)
    if validator is None:
        return None
    try:
        return validator(content, file_path)
    except Exception as exc:
        return f"{type(exc).__name__} during re-validation: {exc}"
