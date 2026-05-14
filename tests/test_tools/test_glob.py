import os
import time
from pathlib import Path

import pytest

import vulpcode.tools  # noqa
from vulpcode.tools import get_tool


@pytest.mark.asyncio
async def test_glob_absolute_pattern(tmp_path: Path):
    """LLMs often pass absolute patterns; Path.glob raises NotImplementedError on those."""
    (tmp_path / "a.py").write_text("a")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.py").write_text("b")
    cls = get_tool("Glob")
    # Absolute pattern with **
    res = await cls().run(cls.Input(pattern=f"{tmp_path}/**/*.py"))
    assert res.is_error is False, res.error
    assert "a.py" in res.output
    assert "b.py" in res.output
    # Absolute pattern without **
    res2 = await cls().run(cls.Input(pattern=f"{tmp_path}/*.py"))
    assert res2.is_error is False, res2.error
    assert "a.py" in res2.output


@pytest.mark.asyncio
async def test_glob_finds_files(tmp_path: Path):
    (tmp_path / "a.py").write_text("a")
    (tmp_path / "b.py").write_text("b")
    (tmp_path / "c.txt").write_text("c")
    cls = get_tool("Glob")
    res = await cls().run(cls.Input(pattern="*.py", path=str(tmp_path)))
    assert res.is_error is False
    assert "a.py" in res.output
    assert "b.py" in res.output
    assert "c.txt" not in res.output


@pytest.mark.asyncio
async def test_glob_recursive(tmp_path: Path):
    (tmp_path / "x").mkdir()
    (tmp_path / "x" / "deep.py").write_text("z")
    (tmp_path / "top.py").write_text("z")
    cls = get_tool("Glob")
    res = await cls().run(cls.Input(pattern="**/*.py", path=str(tmp_path)))
    assert "deep.py" in res.output
    assert "top.py" in res.output


@pytest.mark.asyncio
async def test_glob_sorted_by_mtime(tmp_path: Path):
    a = tmp_path / "a.py"
    b = tmp_path / "b.py"
    a.write_text("a")
    time.sleep(0.05)
    b.write_text("b")
    new_b = time.time()
    os.utime(b, (new_b, new_b))
    new_a = new_b - 10
    os.utime(a, (new_a, new_a))
    cls = get_tool("Glob")
    res = await cls().run(cls.Input(pattern="*.py", path=str(tmp_path)))
    lines = res.output.splitlines()
    assert lines[0].endswith("b.py")
    assert lines[1].endswith("a.py")


@pytest.mark.asyncio
async def test_glob_no_matches(tmp_path: Path):
    cls = get_tool("Glob")
    res = await cls().run(cls.Input(pattern="*.nope", path=str(tmp_path)))
    assert res.is_error is False
    assert "No files match" in res.output


@pytest.mark.asyncio
async def test_glob_invalid_path(tmp_path: Path):
    cls = get_tool("Glob")
    res = await cls().run(cls.Input(pattern="*", path=str(tmp_path / "nope")))
    assert res.is_error


@pytest.mark.asyncio
async def test_glob_excludes_directories(tmp_path: Path):
    (tmp_path / "subdir").mkdir()
    (tmp_path / "f.txt").write_text("x")
    cls = get_tool("Glob")
    res = await cls().run(cls.Input(pattern="*", path=str(tmp_path)))
    assert "f.txt" in res.output
    assert "subdir" not in res.output


@pytest.mark.asyncio
async def test_glob_truncation(tmp_path: Path):
    for i in range(105):
        (tmp_path / f"f{i:03d}.py").write_text(str(i))
    cls = get_tool("Glob")
    res = await cls().run(cls.Input(pattern="*.py", path=str(tmp_path)))
    assert res.is_error is False
    assert res.metadata["truncated"] is True
    assert res.metadata["matches"] == 100
    assert "[truncated to 100 most recent matches]" in res.output


@pytest.mark.asyncio
async def test_glob_default_path_is_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    (tmp_path / "hello.md").write_text("hi")
    monkeypatch.chdir(tmp_path)
    cls = get_tool("Glob")
    res = await cls().run(cls.Input(pattern="*.md"))
    assert res.is_error is False
    assert "hello.md" in res.output


def test_glob_does_not_require_confirm():
    cls = get_tool("Glob")
    assert cls._requires_confirm is False
