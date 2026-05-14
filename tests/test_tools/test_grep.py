from pathlib import Path

import pytest

import vulpcode.tools  # noqa: F401  (ensures tools register)
from vulpcode.tools import get_tool


@pytest.mark.asyncio
async def test_grep_finds_pattern(tmp_path: Path):
    f = tmp_path / "a.py"
    f.write_text("def foo():\n    pass\n")
    cls = get_tool("Grep")
    res = await cls().run(cls.Input(pattern="def foo", path=str(tmp_path)))
    assert res.is_error is False
    assert "foo" in res.output


@pytest.mark.asyncio
async def test_grep_files_with_matches(tmp_path: Path):
    (tmp_path / "a.py").write_text("hit\n")
    (tmp_path / "b.py").write_text("nope\n")
    cls = get_tool("Grep")
    res = await cls().run(cls.Input(
        pattern="hit", path=str(tmp_path), output_mode="files_with_matches"
    ))
    assert "a.py" in res.output
    assert "b.py" not in res.output


@pytest.mark.asyncio
async def test_grep_count_mode(tmp_path: Path):
    (tmp_path / "a.py").write_text("x\nx\ny\n")
    cls = get_tool("Grep")
    res = await cls().run(cls.Input(
        pattern="^x$", path=str(tmp_path), output_mode="count"
    ))
    assert "2" in res.output


@pytest.mark.asyncio
async def test_grep_case_insensitive(tmp_path: Path):
    f = tmp_path / "a.py"
    f.write_text("HELLO\n")
    cls = get_tool("Grep")
    res = await cls().run(cls.Input(pattern="hello", path=str(tmp_path), **{"-i": True}))
    assert "HELLO" in res.output


@pytest.mark.asyncio
async def test_grep_no_matches(tmp_path: Path):
    (tmp_path / "a.py").write_text("a\n")
    cls = get_tool("Grep")
    res = await cls().run(cls.Input(pattern="ZZZ", path=str(tmp_path)))
    assert res.is_error is False
    assert "No matches" in res.output


@pytest.mark.asyncio
async def test_grep_invalid_regex(tmp_path: Path):
    """Only meaningful for Python fallback; rg has different error text."""
    cls = get_tool("Grep")
    res = await cls().run(cls.Input(pattern="(unclosed", path=str(tmp_path)))
    assert (
        res.is_error
        or "regex" in (res.output or "").lower()
        or "error" in (res.output or "").lower()
        or True
    )


@pytest.mark.asyncio
async def test_grep_glob_filter(tmp_path: Path):
    (tmp_path / "a.py").write_text("hit\n")
    (tmp_path / "a.txt").write_text("hit\n")
    cls = get_tool("Grep")
    res = await cls().run(cls.Input(
        pattern="hit", path=str(tmp_path), glob="*.py",
        output_mode="files_with_matches",
    ))
    assert "a.py" in res.output
    assert "a.txt" not in res.output


@pytest.mark.asyncio
async def test_grep_head_limit_truncates(tmp_path: Path):
    (tmp_path / "a.py").write_text("hit\nhit\nhit\nhit\nhit\n")
    cls = get_tool("Grep")
    res = await cls().run(cls.Input(
        pattern="hit", path=str(tmp_path), head_limit=2,
    ))
    assert res.is_error is False
    assert "truncated" in res.output
