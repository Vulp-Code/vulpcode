"""Tests for the Tree tool."""
from pathlib import Path

import pytest

import vulpcode.tools  # noqa: F401  (ensures tools are registered)
from vulpcode.tools import get_tool


@pytest.mark.asyncio
async def test_tree_basic_layout(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("x")
    (tmp_path / "README.md").write_text("y")

    cls = get_tool("Tree")
    res = await cls().run(cls.Input(path=str(tmp_path)))
    assert res.is_error is False
    assert "main.py" in res.output
    assert "README.md" in res.output
    assert "src/" in res.output
    assert res.metadata["files"] >= 2
    assert res.metadata["dirs"] >= 1


@pytest.mark.asyncio
async def test_tree_skips_noise_dirs_by_default(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "lib.js").write_text("x")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "py.py").write_text("x")

    cls = get_tool("Tree")
    res = await cls().run(cls.Input(path=str(tmp_path)))
    assert "a.py" in res.output
    assert "node_modules" not in res.output
    assert ".venv" not in res.output
    assert res.metadata["ignored"] >= 2


@pytest.mark.asyncio
async def test_tree_respects_max_depth(tmp_path: Path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "b").mkdir()
    (tmp_path / "a" / "b" / "c").mkdir()
    (tmp_path / "a" / "b" / "c" / "deep.py").write_text("x")

    cls = get_tool("Tree")
    res = await cls().run(cls.Input(path=str(tmp_path), max_depth=2))
    assert "a/" in res.output
    assert "b/" in res.output
    # depth 3 (c/) and beyond must be hidden behind the "…" marker.
    assert "deep.py" not in res.output


@pytest.mark.asyncio
async def test_tree_max_entries_truncates(tmp_path: Path):
    for i in range(50):
        (tmp_path / f"f{i:02d}.txt").write_text("x")

    cls = get_tool("Tree")
    res = await cls().run(cls.Input(path=str(tmp_path), max_entries=10))
    assert res.metadata["truncated"] is True
    assert "[truncated at 10 entries]" in res.output


@pytest.mark.asyncio
async def test_tree_include_ignored(tmp_path: Path):
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "lib.js").write_text("x")
    (tmp_path / "src.py").write_text("y")

    cls = get_tool("Tree")
    res = await cls().run(cls.Input(path=str(tmp_path), include_ignored=True))
    assert "node_modules" in res.output
    assert "lib.js" in res.output
    assert "src.py" in res.output


@pytest.mark.asyncio
async def test_tree_invalid_path(tmp_path: Path):
    cls = get_tool("Tree")
    res = await cls().run(cls.Input(path=str(tmp_path / "missing")))
    assert res.is_error


@pytest.mark.asyncio
async def test_tree_path_must_be_dir(tmp_path: Path):
    f = tmp_path / "file.txt"
    f.write_text("x")
    cls = get_tool("Tree")
    res = await cls().run(cls.Input(path=str(f)))
    assert res.is_error


def test_tree_does_not_require_confirm():
    cls = get_tool("Tree")
    assert cls._requires_confirm is False


@pytest.mark.asyncio
async def test_tree_show_sizes(tmp_path: Path):
    (tmp_path / "small.txt").write_text("abc")
    cls = get_tool("Tree")
    res = await cls().run(cls.Input(path=str(tmp_path), show_sizes=True))
    assert "(3B)" in res.output
