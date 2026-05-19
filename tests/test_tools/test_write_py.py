import pytest
from vulpcode.tools import get_tool
import vulpcode.tools.write_py  # noqa: F401  (registers WritePy)


@pytest.mark.asyncio
async def test_write_py_valid(tmp_path):
    cls = get_tool("WritePy")
    target = tmp_path / "ok.py"
    res = await cls().run(cls.Input(
        file_path=str(target),
        content="def f(x):\n    return x + 1\n",
    ))
    assert res.is_error is False
    assert target.exists()


@pytest.mark.asyncio
async def test_write_py_syntax_error_blocks_save(tmp_path):
    cls = get_tool("WritePy")
    target = tmp_path / "bad.py"
    res = await cls().run(cls.Input(
        file_path=str(target),
        content="def f(x):\n    return x +\n",  # incomplete expression
    ))
    assert res.is_error is True
    assert "SyntaxError" in res.error
    assert "line" in res.error.lower()
    assert not target.exists()


@pytest.mark.asyncio
async def test_write_py_error_includes_snippet(tmp_path):
    cls = get_tool("WritePy")
    res = await cls().run(cls.Input(
        file_path=str(tmp_path / "bad.py"),
        content="a = 1\nb = 2 3\nc = 4\n",
    ))
    assert res.is_error is True
    assert "b = 2 3" in res.error  # snippet line should appear


@pytest.mark.asyncio
async def test_write_py_empty_file_is_valid(tmp_path):
    cls = get_tool("WritePy")
    target = tmp_path / "empty.py"
    res = await cls().run(cls.Input(file_path=str(target), content=""))
    assert res.is_error is False
    assert target.read_text() == ""


@pytest.mark.asyncio
async def test_write_py_only_comments_is_valid(tmp_path):
    cls = get_tool("WritePy")
    target = tmp_path / "c.py"
    res = await cls().run(cls.Input(
        file_path=str(target),
        content="# just a comment\n# nothing else\n",
    ))
    assert res.is_error is False
