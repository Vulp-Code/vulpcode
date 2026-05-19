"""Tests for data-format Write* tools: WriteJson, WriteYaml, WriteToml, WriteCsv, WriteXml."""
import pytest
from vulpcode.tools import get_tool
import vulpcode.tools.write_json  # noqa: F401  (ensure registration)
import vulpcode.tools.write_yaml  # noqa: F401
import vulpcode.tools.write_toml  # noqa: F401
import vulpcode.tools.write_csv  # noqa: F401
import vulpcode.tools.write_xml  # noqa: F401


# ---------------------------------------------------------------------------
# WriteJson
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_write_json_valid(tmp_path):
    cls = get_tool("WriteJson")
    res = await cls().run(cls.Input(
        file_path=str(tmp_path / "x.json"),
        content='{"a": 1, "b": [1,2,3]}',
    ))
    assert res.is_error is False


@pytest.mark.asyncio
async def test_write_json_pretty_print(tmp_path):
    cls = get_tool("WriteJson")
    out = tmp_path / "pretty.json"
    res = await cls().run(cls.Input(
        file_path=str(out),
        content='{"z":1,"a":2}',
        indent=2,
    ))
    assert res.is_error is False
    text = out.read_text()
    assert "\n" in text


@pytest.mark.asyncio
async def test_write_json_no_indent(tmp_path):
    cls = get_tool("WriteJson")
    out = tmp_path / "compact.json"
    original = '{"z":1,"a":2}'
    res = await cls().run(cls.Input(
        file_path=str(out),
        content=original,
        indent=None,
    ))
    assert res.is_error is False
    assert out.read_text() == original


@pytest.mark.asyncio
async def test_write_json_invalid(tmp_path):
    cls = get_tool("WriteJson")
    target = tmp_path / "bad.json"
    res = await cls().run(cls.Input(
        file_path=str(target),
        content='{"a": 1, "b": [1,2,3}',
    ))
    assert res.is_error is True
    assert "JSONDecodeError" in res.error
    assert not target.exists()


# ---------------------------------------------------------------------------
# WriteYaml
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_write_yaml_valid(tmp_path):
    yaml = pytest.importorskip("yaml")  # skip if PyYAML not installed
    cls = get_tool("WriteYaml")
    res = await cls().run(cls.Input(
        file_path=str(tmp_path / "x.yaml"),
        content="key: value\nlist:\n  - a\n  - b\n",
    ))
    assert res.is_error is False


@pytest.mark.asyncio
async def test_write_yaml_invalid(tmp_path):
    pytest.importorskip("yaml")
    cls = get_tool("WriteYaml")
    target = tmp_path / "bad.yaml"
    res = await cls().run(cls.Input(
        file_path=str(target),
        content="key: :\n  bad indent\n",
    ))
    assert res.is_error is True
    assert not target.exists()


@pytest.mark.asyncio
async def test_write_yaml_atomic_on_error(tmp_path):
    pytest.importorskip("yaml")
    cls = get_tool("WriteYaml")
    target = tmp_path / "atomic.yaml"
    res = await cls().run(cls.Input(
        file_path=str(target),
        content="key: :\n",
    ))
    assert res.is_error is True
    assert not target.exists()


# ---------------------------------------------------------------------------
# WriteToml
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_write_toml_valid(tmp_path):
    cls = get_tool("WriteToml")
    res = await cls().run(cls.Input(
        file_path=str(tmp_path / "x.toml"),
        content='[tool.poetry]\nname = "foo"\nversion = "1.0"\n',
    ))
    assert res.is_error is False


@pytest.mark.asyncio
async def test_write_toml_invalid(tmp_path):
    cls = get_tool("WriteToml")
    target = tmp_path / "bad.toml"
    res = await cls().run(cls.Input(
        file_path=str(target),
        content="[section]\nkey = \n",
    ))
    assert res.is_error is True
    assert "TOMLDecodeError" in res.error
    assert not target.exists()


@pytest.mark.asyncio
async def test_write_toml_atomic_on_error(tmp_path):
    cls = get_tool("WriteToml")
    target = tmp_path / "atomic.toml"
    res = await cls().run(cls.Input(
        file_path=str(target),
        content="bad = = value\n",
    ))
    assert res.is_error is True
    assert not target.exists()


# ---------------------------------------------------------------------------
# WriteCsv
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_write_csv_uniform_rows(tmp_path):
    cls = get_tool("WriteCsv")
    res = await cls().run(cls.Input(
        file_path=str(tmp_path / "x.csv"),
        rows=[["a", "b", "c"], ["1", "2", "3"]],
    ))
    assert res.is_error is False


@pytest.mark.asyncio
async def test_write_csv_raw_content(tmp_path):
    cls = get_tool("WriteCsv")
    out = tmp_path / "raw.csv"
    res = await cls().run(cls.Input(
        file_path=str(out),
        content="a,b,c\n1,2,3\n",
    ))
    assert res.is_error is False
    assert out.exists()


@pytest.mark.asyncio
async def test_write_csv_inconsistent_columns(tmp_path):
    cls = get_tool("WriteCsv")
    target = tmp_path / "bad.csv"
    res = await cls().run(cls.Input(
        file_path=str(target),
        rows=[["a", "b", "c"], ["1", "2"]],
    ))
    assert res.is_error is True
    assert "expected 3" in res.error
    assert not target.exists()


# ---------------------------------------------------------------------------
# WriteXml
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_write_xml_valid(tmp_path):
    cls = get_tool("WriteXml")
    res = await cls().run(cls.Input(
        file_path=str(tmp_path / "x.xml"),
        content="<root><child attr='1'>text</child></root>",
    ))
    assert res.is_error is False


@pytest.mark.asyncio
async def test_write_xml_malformed(tmp_path):
    cls = get_tool("WriteXml")
    target = tmp_path / "bad.xml"
    res = await cls().run(cls.Input(
        file_path=str(target),
        content="<root><child></root>",
    ))
    assert res.is_error is True
    assert not target.exists()


@pytest.mark.asyncio
async def test_write_xml_atomic_on_error(tmp_path):
    cls = get_tool("WriteXml")
    target = tmp_path / "atomic.xml"
    res = await cls().run(cls.Input(
        file_path=str(target),
        content="<unclosed>",
    ))
    assert res.is_error is True
    assert not target.exists()
