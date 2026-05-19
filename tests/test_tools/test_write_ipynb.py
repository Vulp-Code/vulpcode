import json
import pytest
from vulpcode.tools import get_tool
import vulpcode.tools.write_ipynb  # noqa: F401  (registers WriteIpynb)

pytest.importorskip("nbformat")


@pytest.mark.asyncio
async def test_write_ipynb_from_cells(tmp_path):
    cls = get_tool("WriteIpynb")
    target = tmp_path / "nb.ipynb"
    res = await cls().run(cls.Input(
        file_path=str(target),
        cells=[
            {"type": "markdown", "source": "# Title"},
            {"type": "code", "source": "x = 1\nprint(x)"},
        ],
    ))
    assert res.is_error is False
    nb = json.loads(target.read_text())
    assert nb["nbformat"] == 4
    assert len(nb["cells"]) == 2


@pytest.mark.asyncio
async def test_write_ipynb_code_syntax_error_blocks(tmp_path):
    cls = get_tool("WriteIpynb")
    target = tmp_path / "bad.ipynb"
    res = await cls().run(cls.Input(
        file_path=str(target),
        cells=[{"type": "code", "source": "x = 1 2"}],
    ))
    assert res.is_error is True
    assert "SyntaxError in code cell #0" in res.error
    assert not target.exists()


@pytest.mark.asyncio
async def test_write_ipynb_raw_json(tmp_path):
    nb = {
        "cells": [],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    cls = get_tool("WriteIpynb")
    target = tmp_path / "empty.ipynb"
    res = await cls().run(cls.Input(file_path=str(target), content=json.dumps(nb)))
    assert res.is_error is False
