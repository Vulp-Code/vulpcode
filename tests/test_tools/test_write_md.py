import pytest
from vulpcode.tools import get_tool
import vulpcode.tools.write_md  # noqa: F401  (registers WriteMd)


@pytest.mark.asyncio
async def test_write_md_valid(tmp_path):
    cls = get_tool("WriteMd")
    target = tmp_path / "doc.md"
    res = await cls().run(cls.Input(
        file_path=str(target),
        content="# Title\n\nSome paragraph.\n\n```python\nprint('hi')\n```\n",
    ))
    assert res.is_error is False
    assert target.exists()
    assert "# Title" in target.read_text()


@pytest.mark.asyncio
async def test_write_md_unbalanced_fences_blocked(tmp_path):
    cls = get_tool("WriteMd")
    target = tmp_path / "bad.md"
    res = await cls().run(cls.Input(
        file_path=str(target),
        content="# Title\n\n```python\nprint('unclosed')\n",
    ))
    assert res.is_error is True
    assert "Unbalanced code fences" in res.error
    assert not target.exists()


@pytest.mark.asyncio
async def test_write_md_empty_content_valid(tmp_path):
    cls = get_tool("WriteMd")
    target = tmp_path / "empty.md"
    res = await cls().run(cls.Input(file_path=str(target), content=""))
    assert res.is_error is False
    assert target.exists()


@pytest.mark.asyncio
async def test_write_md_multiple_balanced_fences(tmp_path):
    cls = get_tool("WriteMd")
    target = tmp_path / "multi.md"
    content = "```python\nx = 1\n```\n\n```bash\necho hi\n```\n"
    res = await cls().run(cls.Input(file_path=str(target), content=content))
    assert res.is_error is False
    assert target.exists()
