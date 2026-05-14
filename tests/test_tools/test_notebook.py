import json
from pathlib import Path

import pytest

import vulpcode.tools  # noqa: F401
from vulpcode.tools import get_tool


def _make_nb(tmp_path: Path) -> Path:
    p = tmp_path / "n.ipynb"
    nb = {
        "cells": [
            {
                "id": "a",
                "cell_type": "code",
                "metadata": {},
                "source": ["print('hi')\n"],
                "outputs": [],
                "execution_count": None,
            },
            {
                "id": "b",
                "cell_type": "markdown",
                "metadata": {},
                "source": ["# Title\n"],
            },
        ],
        "metadata": {"kernelspec": {"name": "python3"}},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    p.write_text(json.dumps(nb))
    return p


@pytest.mark.asyncio
async def test_replace_by_id(tmp_path: Path):
    p = _make_nb(tmp_path)
    cls = get_tool("NotebookEdit")
    res = await cls().run(
        cls.Input(
            notebook_path=str(p),
            cell_id="a",
            new_source="print('updated')\n",
        )
    )
    assert res.is_error is False
    nb = json.loads(p.read_text())
    assert nb["cells"][0]["source"] == ["print('updated')\n"]
    assert nb["cells"][0]["id"] == "a"


@pytest.mark.asyncio
async def test_replace_by_number(tmp_path: Path):
    p = _make_nb(tmp_path)
    cls = get_tool("NotebookEdit")
    res = await cls().run(
        cls.Input(
            notebook_path=str(p),
            cell_number=1,
            new_source="# New\n",
            cell_type="markdown",
        )
    )
    assert res.is_error is False
    nb = json.loads(p.read_text())
    assert "New" in "".join(nb["cells"][1]["source"])
    assert nb["cells"][1]["cell_type"] == "markdown"


@pytest.mark.asyncio
async def test_insert(tmp_path: Path):
    p = _make_nb(tmp_path)
    cls = get_tool("NotebookEdit")
    res = await cls().run(
        cls.Input(
            notebook_path=str(p),
            edit_mode="insert",
            new_source="print(2)\n",
            cell_type="code",
        )
    )
    assert res.is_error is False
    nb = json.loads(p.read_text())
    assert len(nb["cells"]) == 3
    new_cell = nb["cells"][-1]
    assert new_cell["cell_type"] == "code"
    assert new_cell["source"] == ["print(2)\n"]
    assert isinstance(new_cell["id"], str)
    assert 0 < len(new_cell["id"]) <= 12


@pytest.mark.asyncio
async def test_delete(tmp_path: Path):
    p = _make_nb(tmp_path)
    cls = get_tool("NotebookEdit")
    res = await cls().run(
        cls.Input(
            notebook_path=str(p),
            edit_mode="delete",
            cell_id="b",
        )
    )
    assert res.is_error is False
    nb = json.loads(p.read_text())
    assert len(nb["cells"]) == 1
    assert nb["cells"][0]["id"] == "a"


@pytest.mark.asyncio
async def test_missing_locator_for_delete(tmp_path: Path):
    p = _make_nb(tmp_path)
    cls = get_tool("NotebookEdit")
    with pytest.raises(Exception):
        cls.Input(notebook_path=str(p), edit_mode="delete")


@pytest.mark.asyncio
async def test_unknown_id(tmp_path: Path):
    p = _make_nb(tmp_path)
    cls = get_tool("NotebookEdit")
    res = await cls().run(
        cls.Input(
            notebook_path=str(p),
            cell_id="zzz",
            new_source="x",
        )
    )
    assert res.is_error


@pytest.mark.asyncio
async def test_preserves_nbformat_and_metadata(tmp_path: Path):
    p = _make_nb(tmp_path)
    cls = get_tool("NotebookEdit")
    res = await cls().run(
        cls.Input(
            notebook_path=str(p),
            cell_id="a",
            new_source="print('x')\n",
        )
    )
    assert res.is_error is False
    nb = json.loads(p.read_text())
    assert nb["nbformat"] == 4
    assert nb["nbformat_minor"] == 5
    assert nb["metadata"] == {"kernelspec": {"name": "python3"}}


@pytest.mark.asyncio
async def test_replace_to_markdown_drops_outputs(tmp_path: Path):
    p = _make_nb(tmp_path)
    cls = get_tool("NotebookEdit")
    res = await cls().run(
        cls.Input(
            notebook_path=str(p),
            cell_id="a",
            new_source="# Now markdown\n",
            cell_type="markdown",
        )
    )
    assert res.is_error is False
    nb = json.loads(p.read_text())
    cell = nb["cells"][0]
    assert cell["cell_type"] == "markdown"
    assert "outputs" not in cell
    assert "execution_count" not in cell


@pytest.mark.asyncio
async def test_requires_confirm_flag():
    cls = get_tool("NotebookEdit")
    assert cls._requires_confirm is True


@pytest.mark.asyncio
async def test_missing_notebook(tmp_path: Path):
    cls = get_tool("NotebookEdit")
    res = await cls().run(
        cls.Input(
            notebook_path=str(tmp_path / "missing.ipynb"),
            cell_id="a",
            new_source="x",
        )
    )
    assert res.is_error
