from pathlib import Path
import pytest

import vulpcode.tools  # noqa
from vulpcode.tools import get_tool


@pytest.mark.asyncio
async def test_edit_unique_replacement(tmp_path: Path):
    f = tmp_path / "a.py"
    f.write_text("x = 1\nfoo()\nx = 1\n")
    cls = get_tool("Edit")
    res = await cls().run(cls.Input(file_path=str(f), old_string="foo()", new_string="bar()"))
    assert res.is_error is False
    assert "bar()" in f.read_text()


@pytest.mark.asyncio
async def test_edit_ambiguous_fails(tmp_path: Path):
    f = tmp_path / "a.txt"
    f.write_text("aa\naa\n")
    cls = get_tool("Edit")
    res = await cls().run(cls.Input(file_path=str(f), old_string="aa", new_string="bb"))
    assert res.is_error
    assert "unique" in (res.error or "").lower()


@pytest.mark.asyncio
async def test_edit_replace_all(tmp_path: Path):
    f = tmp_path / "a.txt"
    f.write_text("aa\naa\n")
    cls = get_tool("Edit")
    res = await cls().run(cls.Input(file_path=str(f), old_string="aa", new_string="bb", replace_all=True))
    assert res.is_error is False
    assert f.read_text() == "bb\nbb\n"


@pytest.mark.asyncio
async def test_edit_old_equals_new(tmp_path: Path):
    f = tmp_path / "a.txt"
    f.write_text("x")
    cls = get_tool("Edit")
    res = await cls().run(cls.Input(file_path=str(f), old_string="x", new_string="x"))
    assert res.is_error


@pytest.mark.asyncio
async def test_edit_not_found(tmp_path: Path):
    f = tmp_path / "a.txt"
    f.write_text("hello")
    cls = get_tool("Edit")
    res = await cls().run(cls.Input(file_path=str(f), old_string="zzz", new_string="qq"))
    assert res.is_error
    assert "not found" in (res.error or "")


@pytest.mark.asyncio
async def test_multiedit_atomic_success(tmp_path: Path):
    f = tmp_path / "a.txt"
    f.write_text("a\nb\nc\n")
    cls = get_tool("MultiEdit")
    res = await cls().run(cls.Input(
        file_path=str(f),
        edits=[
            cls.EditOp(old_string="a", new_string="A"),
            cls.EditOp(old_string="b", new_string="B"),
        ],
    ))
    assert res.is_error is False
    assert f.read_text() == "A\nB\nc\n"


@pytest.mark.asyncio
async def test_multiedit_rolls_back_on_failure(tmp_path: Path):
    f = tmp_path / "a.txt"
    original = "a\nb\nc\n"
    f.write_text(original)
    cls = get_tool("MultiEdit")
    res = await cls().run(cls.Input(
        file_path=str(f),
        edits=[
            cls.EditOp(old_string="a", new_string="A"),
            cls.EditOp(old_string="DOES_NOT_EXIST", new_string="X"),
        ],
    ))
    assert res.is_error
    assert f.read_text() == original  # rollback


@pytest.mark.asyncio
async def test_multiedit_empty_list_fails(tmp_path: Path):
    f = tmp_path / "a.txt"
    f.write_text("x")
    cls = get_tool("MultiEdit")
    res = await cls().run(cls.Input(file_path=str(f), edits=[]))
    assert res.is_error
