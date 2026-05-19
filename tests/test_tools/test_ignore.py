"""Tests for the shared ignore-filtering utility."""
from pathlib import Path

from vulpcode.tools._ignore import (
    DEFAULT_IGNORE_PATTERNS,
    build_matcher,
    should_ignore,
)


def test_default_patterns_cover_common_noise():
    patterns = set(DEFAULT_IGNORE_PATTERNS)
    expected = {
        "node_modules/",
        "__pycache__/",
        ".venv/",
        ".git/",
        "dist/",
        "build/",
        "target/",
        ".pytest_cache/",
        ".mypy_cache/",
        ".ruff_cache/",
        ".terraform/",
    }
    assert expected.issubset(patterns), f"Missing: {expected - patterns}"


def test_should_ignore_node_modules(tmp_path: Path):
    nm = tmp_path / "node_modules"
    nm.mkdir()
    inside = nm / "lib.js"
    inside.write_text("x")
    assert should_ignore(inside, tmp_path)
    assert should_ignore(nm, tmp_path)


def test_should_ignore_pyc(tmp_path: Path):
    pyc = tmp_path / "a.pyc"
    pyc.write_text("x")
    assert should_ignore(pyc, tmp_path)


def test_should_not_ignore_regular_source(tmp_path: Path):
    src = tmp_path / "main.py"
    src.write_text("x")
    assert not should_ignore(src, tmp_path)


def test_use_defaults_false_disables_filter(tmp_path: Path):
    nm = tmp_path / "node_modules" / "lib.js"
    nm.parent.mkdir()
    nm.write_text("x")
    assert not should_ignore(nm, tmp_path, use_defaults=False, use_gitignore=False)


def test_gitignore_is_honored(tmp_path: Path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".gitignore").write_text("secrets.json\n*.local\n")
    (tmp_path / "secrets.json").write_text("x")
    (tmp_path / "config.local").write_text("x")
    (tmp_path / "public.py").write_text("y")

    matcher = build_matcher(tmp_path)
    assert matcher(tmp_path / "secrets.json")
    assert matcher(tmp_path / "config.local")
    assert not matcher(tmp_path / "public.py")


def test_extra_patterns(tmp_path: Path):
    (tmp_path / "ignoreme.txt").write_text("x")
    (tmp_path / "keepme.txt").write_text("y")
    matcher = build_matcher(tmp_path, extra_patterns=["ignoreme.txt"])
    assert matcher(tmp_path / "ignoreme.txt")
    assert not matcher(tmp_path / "keepme.txt")


def test_path_outside_base_not_filtered(tmp_path: Path):
    """A path outside the matcher's base should not be ignored (no info to decide)."""
    other = tmp_path / "other"
    other.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    matcher = build_matcher(other)
    assert not matcher(elsewhere / "file.py")
