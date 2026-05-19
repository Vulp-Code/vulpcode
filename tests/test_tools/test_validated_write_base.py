import pytest
from pydantic import BaseModel

from vulpcode.tools._validated_write import (
    ValidatedWriteTool,
    ValidationError,
    format_snippet,
)
from vulpcode.tools.base import tool, ToolResult, clear_registry


@pytest.fixture(autouse=True)
def _isolate_registry():
    """Ensure the fake tool does not leak into other test modules."""
    yield
    # Remove only the fake tool so real tools are unaffected
    from vulpcode.tools.base import TOOL_REGISTRY
    TOOL_REGISTRY.pop("_Fake", None)
    TOOL_REGISTRY.pop("_FakeBinary", None)
    TOOL_REGISTRY.pop("_FakeTransformError", None)


def _make_fake_write():
    """Build and return a fresh _FakeWrite class (avoids duplicate-name error)."""
    from vulpcode.tools.base import TOOL_REGISTRY
    TOOL_REGISTRY.pop("_Fake", None)

    @tool(name="_Fake", description="fake for tests", requires_confirm=False)
    class _FakeWrite(ValidatedWriteTool):
        class Input(BaseModel):
            file_path: str
            content: str

        def validate(self, content, args):
            if "BAD" in content:
                raise ValidationError(
                    "marker BAD found",
                    line=1,
                    col=content.index("BAD") + 1,
                    snippet=format_snippet(content, 1, content.index("BAD") + 1),
                )

    return _FakeWrite


@pytest.mark.asyncio
async def test_atomic_save_happy_path(tmp_path):
    _FakeWrite = _make_fake_write()
    target = tmp_path / "x.txt"
    res = await _FakeWrite().run(_FakeWrite.Input(file_path=str(target), content="ok"))
    assert res.is_error is False
    assert target.read_text() == "ok"
    assert not list(tmp_path.glob(".x.txt.*.tmp"))


@pytest.mark.asyncio
async def test_validation_error_blocks_save(tmp_path):
    _FakeWrite = _make_fake_write()
    target = tmp_path / "x.txt"
    res = await _FakeWrite().run(_FakeWrite.Input(file_path=str(target), content="BAD"))
    assert res.is_error is True
    assert "marker BAD found" in res.error
    assert "line 1" in res.error
    assert not target.exists()


@pytest.mark.asyncio
async def test_no_partial_file_on_validation_error(tmp_path):
    _FakeWrite = _make_fake_write()
    target = tmp_path / "x.txt"
    await _FakeWrite().run(_FakeWrite.Input(file_path=str(target), content="BAD"))
    leftovers = list(tmp_path.glob(".x.txt.*.tmp"))
    assert leftovers == []


def test_format_snippet_renders_caret():
    out = format_snippet("a\nb = 1 2\nc", line=2, col=7)
    assert "> 2 | b = 1 2" in out
    assert "^" in out


def test_format_snippet_handles_edges():
    out = format_snippet("only", line=1, col=1, context=5)
    assert "only" in out


def test_validation_error_to_error_text_full():
    err = ValidationError("bad syntax", line=5, col=3, snippet="  5 | code\n      ^")
    text = err.to_error_text()
    assert "bad syntax" in text
    assert "line 5" in text
    assert "col 3" in text
    assert "code" in text


def test_validation_error_to_error_text_line_only():
    err = ValidationError("no column info", line=10)
    text = err.to_error_text()
    assert "line 10" in text
    assert ", col" not in text


def test_validation_error_to_error_text_message_only():
    err = ValidationError("generic error")
    assert err.to_error_text() == "generic error"


@pytest.mark.asyncio
async def test_metadata_on_success(tmp_path):
    _FakeWrite = _make_fake_write()
    target = tmp_path / "sub" / "file.txt"
    res = await _FakeWrite().run(_FakeWrite.Input(file_path=str(target), content="hello"))
    assert res.is_error is False
    assert res.metadata["validated"] is True
    assert res.metadata["size"] == 5
    assert res.metadata["file_path"] == str(target.resolve())


@pytest.mark.asyncio
async def test_creates_parent_directories(tmp_path):
    _FakeWrite = _make_fake_write()
    target = tmp_path / "deep" / "nested" / "dir" / "file.txt"
    res = await _FakeWrite().run(_FakeWrite.Input(file_path=str(target), content="data"))
    assert res.is_error is False
    assert target.exists()


@pytest.mark.asyncio
async def test_transform_error_returns_tool_result_error(tmp_path):
    from vulpcode.tools.base import TOOL_REGISTRY
    TOOL_REGISTRY.pop("_FakeTransformError", None)

    @tool(name="_FakeTransformError", description="fake transform error", requires_confirm=False)
    class FakeTransformError(ValidatedWriteTool):
        class Input(BaseModel):
            file_path: str
            content: str

        def validate(self, content, args):
            pass

        def transform(self, args):
            raise ValidationError("transform failed", line=1)

    target = tmp_path / "x.txt"
    res = await FakeTransformError().run(FakeTransformError.Input(file_path=str(target), content="x"))
    assert res.is_error is True
    assert "transform failed" in res.error
