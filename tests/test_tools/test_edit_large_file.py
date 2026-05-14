from pathlib import Path

import pytest

import vulpcode.tools  # noqa: F401  (registers tools)
from vulpcode.tools import get_tool


@pytest.mark.asyncio
async def test_edit_in_huge_file(tmp_path: Path):
    f = tmp_path / "big.py"
    lines = ["x = 0\n"] * 100_000 + ["target = 42\n"] + ["y = 1\n"] * 100_000
    f.write_text("".join(lines))
    cls = get_tool("Edit")
    res = await cls().run(
        cls.Input(
            file_path=str(f),
            old_string="target = 42",
            new_string="target = 99",
        )
    )
    assert res.is_error is False
    assert "target = 99" in f.read_text()


@pytest.mark.asyncio
async def test_multiedit_in_large_file(tmp_path: Path):
    f = tmp_path / "huge.py"
    lines = (
        ["a = 0\n"] * 50_000
        + ["alpha = 1\n", "beta = 2\n"]
        + ["b = 0\n"] * 50_000
    )
    f.write_text("".join(lines))
    cls = get_tool("MultiEdit")
    EditOp = cls.EditOp
    res = await cls().run(
        cls.Input(
            file_path=str(f),
            edits=[
                EditOp(old_string="alpha = 1", new_string="alpha = 100"),
                EditOp(old_string="beta = 2", new_string="beta = 200"),
            ],
        )
    )
    assert res.is_error is False
    text = f.read_text()
    assert "alpha = 100" in text
    assert "beta = 200" in text
    assert res.metadata["edits_applied"] == 2
