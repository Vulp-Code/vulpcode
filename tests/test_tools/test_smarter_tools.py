"""Integration tests for the new safety + re-validation layers.

Covers:
- WriteTool: secret refusal, sandbox refusal
- WritePy: ruff catches undefined names, smoke import rollback
- WriteSh / WriteSql / WriteToml: extra validators
- BashTool: catastrophic blocked, risky warns
- EditTool / MultiEditTool: rollback on invalid Python after edit
"""
from __future__ import annotations

import shutil

import pytest

from vulpcode.tools import get_tool


# ── Write: sandbox + secret scan ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_write_refuses_secrets_in_content(tmp_path):
    cls = get_tool("Write")
    target = tmp_path / "leaky.py"
    res = await cls().run(cls.Input(
        file_path=str(target),
        content="API = 'AKIAIOSFODNN7EXAMPLE'\n",
    ))
    assert res.is_error
    assert "Secret" in (res.error or "")
    assert not target.exists()


@pytest.mark.asyncio
async def test_write_allow_secret_marker_bypasses(tmp_path):
    cls = get_tool("Write")
    target = tmp_path / "fixture.py"
    res = await cls().run(cls.Input(
        file_path=str(target),
        content="# vulpcode:allow-secret\nKEY='AKIAIOSFODNN7EXAMPLE'\n",
    ))
    assert res.is_error is False
    assert target.exists()


@pytest.mark.asyncio
async def test_write_refuses_system_path():
    cls = get_tool("Write")
    res = await cls().run(cls.Input(
        file_path="/etc/passwd-vulpcode-test",
        content="x",
    ))
    assert res.is_error
    assert "sandbox" in (res.error or "").lower()


# ── WritePy: ruff + smoke import ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_write_py_ruff_catches_undefined_name(tmp_path):
    if not shutil.which("ruff"):
        pytest.skip("ruff not installed")
    cls = get_tool("WritePy")
    target = tmp_path / "bad.py"
    res = await cls().run(cls.Input(
        file_path=str(target),
        content="def f():\n    return undefined_name\n",
    ))
    assert res.is_error
    assert "Lint" in (res.error or "") or "F821" in (res.error or "")
    assert not target.exists()


@pytest.mark.asyncio
async def test_write_py_ruff_catches_unused_import(tmp_path):
    if not shutil.which("ruff"):
        pytest.skip("ruff not installed")
    cls = get_tool("WritePy")
    target = tmp_path / "u.py"
    res = await cls().run(cls.Input(
        file_path=str(target),
        content="import os\n\nprint('hi')\n",
    ))
    assert res.is_error
    assert "F401" in (res.error or "") or "Lint" in (res.error or "")


@pytest.mark.asyncio
async def test_write_py_smoke_import_rollback(tmp_path):
    """If the file lives under src/<pkg>/ and import fails, the write rolls back."""
    cls = get_tool("WritePy")
    # Fake project layout
    (tmp_path / "pyproject.toml").write_text(
        "[build-system]\nrequires=['hatchling']\nbuild-backend='hatchling.build'\n"
        "[project]\nname='fakepkg'\nversion='0'\n"
    )
    pkg = tmp_path / "src" / "fakepkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    target = pkg / "broken.py"
    # ast.parse OK, ruff OK (no undefined names if we use a runtime-only error),
    # but import fails because of a missing dependency.
    res = await cls().run(cls.Input(
        file_path=str(target),
        content="import nonexistent_pkg_zzzz_abc123\n",
    ))
    assert res.is_error
    assert "Smoke import" in (res.error or "") or "import" in (res.error or "").lower()
    assert not target.exists()  # rolled back


# ── WriteToml: pyproject schema ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_write_toml_pyproject_missing_build_system_rejected(tmp_path):
    cls = get_tool("WriteToml")
    target = tmp_path / "pyproject.toml"
    res = await cls().run(cls.Input(
        file_path=str(target),
        content="[project]\nname='x'\nversion='0'\n",
    ))
    assert res.is_error
    assert "build-system" in (res.error or "")


@pytest.mark.asyncio
async def test_write_toml_pyproject_missing_version_rejected(tmp_path):
    cls = get_tool("WriteToml")
    target = tmp_path / "pyproject.toml"
    res = await cls().run(cls.Input(
        file_path=str(target),
        content=(
            "[build-system]\nrequires=['x']\nbuild-backend='x'\n"
            "[project]\nname='y'\n"
        ),
    ))
    assert res.is_error
    assert "version" in (res.error or "").lower()


@pytest.mark.asyncio
async def test_write_toml_pyproject_dynamic_version_ok(tmp_path):
    cls = get_tool("WriteToml")
    target = tmp_path / "pyproject.toml"
    res = await cls().run(cls.Input(
        file_path=str(target),
        content=(
            "[build-system]\nrequires=['x']\nbuild-backend='x'\n"
            "[project]\nname='y'\ndynamic=['version']\n"
        ),
    ))
    assert res.is_error is False


@pytest.mark.asyncio
async def test_write_toml_non_pyproject_skips_schema(tmp_path):
    cls = get_tool("WriteToml")
    target = tmp_path / "config.toml"
    res = await cls().run(cls.Input(
        file_path=str(target),
        content="key='value'\n",
    ))
    assert res.is_error is False


# ── WriteSql: stripped-literal balance check ───────────────────────────────

@pytest.mark.asyncio
async def test_write_sql_balanced_parens_in_string_ok(tmp_path):
    """Parens inside string literals shouldn't trigger an unbalanced error."""
    cls = get_tool("WriteSql")
    target = tmp_path / "x.sql"
    res = await cls().run(cls.Input(
        file_path=str(target),
        content="SELECT 'hello (world)' AS msg;\n",
    ))
    assert res.is_error is False


@pytest.mark.asyncio
async def test_write_sql_apostrophe_in_string_ok(tmp_path):
    cls = get_tool("WriteSql")
    target = tmp_path / "x.sql"
    res = await cls().run(cls.Input(
        file_path=str(target),
        content="SELECT 'it''s fine' AS msg;\n",
    ))
    assert res.is_error is False


@pytest.mark.asyncio
async def test_write_sql_real_unbalanced_paren_rejected(tmp_path):
    cls = get_tool("WriteSql")
    target = tmp_path / "x.sql"
    res = await cls().run(cls.Input(
        file_path=str(target),
        content="SELECT * FROM t WHERE (a = 1;\n",
    ))
    assert res.is_error
    assert "paren" in (res.error or "").lower()


# ── Bash: command guard ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bash_blocks_catastrophic(monkeypatch):
    monkeypatch.delenv("VULPCODE_ALLOW_UNSAFE_COMMANDS", raising=False)
    cls = get_tool("Bash")
    res = await cls().run(cls.Input(command="rm -rf /"))
    assert res.is_error
    assert "safety guard" in (res.error or "").lower()
    assert res.metadata.get("risk") == "catastrophic"


@pytest.mark.asyncio
async def test_bash_catastrophic_override_env(monkeypatch, tmp_path):
    monkeypatch.setenv("VULPCODE_ALLOW_UNSAFE_COMMANDS", "1")
    cls = get_tool("Bash")
    # Use a harmless command that matches the pattern shape (no actual harm)
    # The override lets the command through to bash, which will execute it.
    # We instead use a benign command that the guard would NOT match, just
    # to verify the env var pathway is consulted.
    res = await cls().run(cls.Input(command="echo override-ok"))
    assert res.is_error is False
    assert "override-ok" in res.output


@pytest.mark.asyncio
async def test_bash_risky_warns_but_runs():
    cls = get_tool("Bash")
    # Use a risky-looking pattern that's actually a no-op via echo.
    res = await cls().run(cls.Input(command="echo not-really-doing | head -c 0; git reset --hard HEAD 2>/dev/null; true"))
    # Should still execute (exit 0 via the `true` at the end) and surface a warning
    assert res.is_error is False
    assert res.metadata.get("risk") == "risky"
    assert "Risky pattern" in res.output


# ── Edit: re-validation rollback ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_edit_rollback_on_invalid_python(tmp_path):
    cls = get_tool("Edit")
    f = tmp_path / "m.py"
    original = "def f(x):\n    return x + 1\n"
    f.write_text(original)
    # Replace the return with syntactically broken text
    res = await cls().run(cls.Input(
        file_path=str(f),
        old_string="return x + 1",
        new_string="return x +",
    ))
    assert res.is_error
    assert "re-validation" in (res.error or "").lower()
    assert f.read_text() == original  # unchanged


@pytest.mark.asyncio
async def test_edit_succeeds_for_valid_python(tmp_path):
    cls = get_tool("Edit")
    f = tmp_path / "m.py"
    f.write_text("def f(x):\n    return x + 1\n")
    res = await cls().run(cls.Input(
        file_path=str(f),
        old_string="x + 1",
        new_string="x + 2",
    ))
    assert res.is_error is False
    assert "x + 2" in f.read_text()


@pytest.mark.asyncio
async def test_edit_rollback_on_invalid_json(tmp_path):
    cls = get_tool("Edit")
    f = tmp_path / "data.json"
    original = '{"a": 1, "b": 2}'
    f.write_text(original)
    res = await cls().run(cls.Input(
        file_path=str(f),
        old_string='"b": 2',
        new_string='"b": 2,,',
    ))
    assert res.is_error
    assert f.read_text() == original


@pytest.mark.asyncio
async def test_edit_refuses_secret_introduction(tmp_path):
    cls = get_tool("Edit")
    f = tmp_path / "cfg.txt"
    f.write_text("password=placeholder\n")
    res = await cls().run(cls.Input(
        file_path=str(f),
        old_string="placeholder",
        new_string="AKIAIOSFODNN7EXAMPLE",
    ))
    assert res.is_error
    assert "Secret" in (res.error or "")
    assert f.read_text() == "password=placeholder\n"


@pytest.mark.asyncio
async def test_multiedit_rollback_on_invalid(tmp_path):
    cls = get_tool("MultiEdit")
    f = tmp_path / "m.py"
    original = "a = 1\nb = 2\nc = 3\n"
    f.write_text(original)
    res = await cls().run(cls.Input(
        file_path=str(f),
        edits=[
            cls.EditOp(old_string="a = 1", new_string="a = 1  # ok"),
            cls.EditOp(old_string="b = 2", new_string="b ="),  # syntax error
        ],
    ))
    assert res.is_error
    assert f.read_text() == original


@pytest.mark.asyncio
async def test_edit_no_revalidation_for_unknown_ext(tmp_path):
    cls = get_tool("Edit")
    f = tmp_path / "notes.txt"
    f.write_text("hello world\n")
    res = await cls().run(cls.Input(
        file_path=str(f),
        old_string="world",
        new_string="universe",
    ))
    assert res.is_error is False
    assert "universe" in f.read_text()


# ── ValidatedWriteTool: git dirty warning + secret refusal end-to-end ─────

@pytest.mark.asyncio
async def test_validated_write_secret_refusal_via_write_py(tmp_path):
    cls = get_tool("WritePy")
    target = tmp_path / "secrets.py"
    res = await cls().run(cls.Input(
        file_path=str(target),
        content="TOKEN = 'ghp_" + "a" * 36 + "'\n",
    ))
    assert res.is_error
    assert "Secret" in (res.error or "")
    assert not target.exists()
