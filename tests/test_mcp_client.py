"""Unit tests for the MCP client (no real server required)."""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from vulpcode.mcp import McpServer, list_active_servers
from vulpcode.mcp.client import _input_model_from_schema, _make_tool_adapter
from vulpcode.tools.base import TOOL_REGISTRY, ToolResult


@pytest.fixture
def _isolated_registry():
    """Snapshot and restore the global tool registry for each test."""
    saved = dict(TOOL_REGISTRY)
    TOOL_REGISTRY.clear()
    TOOL_REGISTRY.update(saved)
    snapshot = dict(TOOL_REGISTRY)
    yield
    TOOL_REGISTRY.clear()
    TOOL_REGISTRY.update(snapshot)


def test_input_model_required_field():
    schema = {
        "type": "object",
        "properties": {
            "file_path": {"type": "string"},
            "limit": {"type": "integer"},
        },
        "required": ["file_path"],
    }
    model = _input_model_from_schema(schema, "Test")
    inst = model(file_path="/a")
    assert inst.file_path == "/a"
    assert inst.limit is None
    with pytest.raises(Exception):
        model()  # missing required


def test_input_model_object_no_props():
    schema = {"type": "object"}
    model = _input_model_from_schema(schema, "Empty")
    inst = model()
    assert inst is not None


def test_input_model_non_object_returns_empty_model():
    schema = {"type": "string"}
    model = _input_model_from_schema(schema, "Scalar")
    inst = model()
    assert inst is not None


def test_active_servers_starts_as_list():
    assert isinstance(list_active_servers(), list)


def test_make_tool_adapter_qualifies_name(_isolated_registry):
    TOOL_REGISTRY.clear()
    mcp_tool = MagicMock()
    mcp_tool.name = "search"
    mcp_tool.description = "search the index"
    mcp_tool.inputSchema = {
        "type": "object",
        "properties": {"q": {"type": "string"}},
        "required": ["q"],
    }
    session = MagicMock()
    adapter = _make_tool_adapter("brave", session, mcp_tool)
    assert adapter._tool_name == "mcp__brave__search"
    assert adapter._tool_description == "search the index"
    assert adapter._requires_confirm is False
    assert TOOL_REGISTRY["mcp__brave__search"] is adapter
    schema = adapter.to_schema()
    assert schema["name"] == "mcp__brave__search"
    assert "q" in schema["input_schema"]["properties"]


async def test_adapter_run_returns_text_output(_isolated_registry):
    TOOL_REGISTRY.clear()
    mcp_tool = MagicMock()
    mcp_tool.name = "echo"
    mcp_tool.description = "echo"
    mcp_tool.inputSchema = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "hello world"
    fake_result = MagicMock()
    fake_result.content = [text_block]
    fake_result.isError = False

    session = MagicMock()
    session.call_tool = AsyncMock(return_value=fake_result)

    adapter = _make_tool_adapter("srv", session, mcp_tool)
    args = adapter.parse_args({"text": "hi"})
    out = await adapter().run(args)
    assert isinstance(out, ToolResult)
    assert out.is_error is False
    assert out.output == "hello world"
    assert out.metadata == {"server": "srv"}
    session.call_tool.assert_awaited_once_with("echo", {"text": "hi"})


async def test_adapter_run_wraps_mcp_error(_isolated_registry):
    TOOL_REGISTRY.clear()
    mcp_tool = MagicMock()
    mcp_tool.name = "failer"
    mcp_tool.description = "always fails"
    mcp_tool.inputSchema = {"type": "object"}
    err_block = MagicMock()
    err_block.type = "text"
    err_block.text = "boom"
    fake_result = MagicMock()
    fake_result.content = [err_block]
    fake_result.isError = True

    session = MagicMock()
    session.call_tool = AsyncMock(return_value=fake_result)

    adapter = _make_tool_adapter("srv2", session, mcp_tool)
    args = adapter.parse_args({})
    out = await adapter().run(args)
    assert out.is_error is True
    assert out.error == "boom"
    assert out.metadata == {"server": "srv2"}


async def test_adapter_run_wraps_call_exception(_isolated_registry):
    TOOL_REGISTRY.clear()
    mcp_tool = MagicMock()
    mcp_tool.name = "broken"
    mcp_tool.description = "raises"
    mcp_tool.inputSchema = {"type": "object"}

    session = MagicMock()
    session.call_tool = AsyncMock(side_effect=RuntimeError("disconnected"))

    adapter = _make_tool_adapter("srv3", session, mcp_tool)
    args = adapter.parse_args({})
    out = await adapter().run(args)
    assert out.is_error is True
    assert "RuntimeError" in (out.error or "")
    assert "disconnected" in (out.error or "")


async def test_mcp_server_call_concatenates_text_content():
    block_a = MagicMock()
    block_a.type = "text"
    block_a.text = "alpha"
    block_b = MagicMock()
    block_b.type = "text"
    block_b.text = "beta"
    block_other = MagicMock()
    block_other.type = "image"
    block_other.text = "ignored"

    fake_result = MagicMock()
    fake_result.content = [block_a, block_other, block_b]

    session = MagicMock()
    session.call_tool = AsyncMock(return_value=fake_result)

    server = McpServer(name="x", session=session, tool_classes=[])
    out = await server.call("anything", {"k": 1})
    assert out == "alpha\nbeta"
    session.call_tool.assert_awaited_once_with("anything", {"k": 1})


async def test_mcp_server_aclose_swallows_errors():
    session = MagicMock()
    session.close = AsyncMock(side_effect=RuntimeError("ignored"))
    server = McpServer(name="y", session=session, tool_classes=[])
    await server.aclose()  # must not raise


@pytest.mark.skip(
    reason="requires actual MCP server; covered by integration smoke tests in FASE 14"
)
async def test_connect_real_server() -> None:
    pass


def test_input_model_marks_required_default_sentinel():
    schema = {
        "type": "object",
        "properties": {"a": {"type": "string"}, "b": {"type": "string"}},
        "required": ["a"],
    }
    model = _input_model_from_schema(schema, "Sentinel")
    fields: dict[str, Any] = model.model_fields
    assert fields["a"].is_required() is True
    assert fields["b"].is_required() is False
