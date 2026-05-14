"""MCP client using the official `mcp` Python library."""
from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel, create_model

from vulpcode.tools.base import Tool, ToolResult, tool

_ACTIVE_SERVERS: list["McpServer"] = []


class McpServer:
    """A spawned MCP subprocess plus the Tool adapters it exposes.

    A live ``McpServer`` owns the stdio streams to a subprocess implementing
    the Model Context Protocol. Each tool advertised by the server becomes
    a synthesized [`Tool`][vulpcode.tools.base.Tool] subclass registered in
    the global ``TOOL_REGISTRY`` under the qualified name
    ``mcp__<server>__<tool>``.

    Attributes:
        name: The local server name (used as the prefix in qualified tool
            names).
        tools: List of qualified tool names registered for this server,
            e.g. ``["mcp__filesystem__read_file", ...]``.
        tool_classes: The dynamic [`Tool`][vulpcode.tools.base.Tool]
            subclasses that wrap each MCP tool. Already added to
            ``TOOL_REGISTRY``; you usually do not instantiate them directly.
    """

    def __init__(
        self,
        name: str,
        session: Any,
        tool_classes: list[type[Tool]],
        stdio_ctx: Any | None = None,
        session_ctx: Any | None = None,
    ) -> None:
        self.name = name
        self._session = session
        self._stdio_ctx = stdio_ctx
        self._session_ctx = session_ctx
        self.tool_classes = tool_classes
        self.tools: list[str] = [c._tool_name for c in tool_classes]

    async def call(self, tool_name: str, args: dict[str, Any]) -> str:
        """Invoke an MCP tool directly, bypassing the Tool adapter.

        Args:
            tool_name: The *bare* tool name as advertised by the MCP server
                (without the ``mcp__<server>__`` prefix).
            args: The argument payload matching the tool's input schema.

        Returns:
            The concatenated text content of the tool's response. Non-text
            content blocks are dropped.
        """
        result = await self._session.call_tool(tool_name, args)
        text_parts: list[str] = []
        for item in result.content or []:
            if getattr(item, "type", "") == "text":
                text_parts.append(getattr(item, "text", ""))
        return "\n".join(text_parts)

    async def aclose(self) -> None:
        """Tear down the MCP session and reap the subprocess.

        Always safe to call (errors during shutdown are swallowed). Removes
        the server from
        [`list_active_servers`][vulpcode.mcp.client.list_active_servers].
        """
        try:
            if self._session_ctx is not None:
                await self._session_ctx.__aexit__(None, None, None)
            else:
                close = getattr(self._session, "close", None)
                if close is not None:
                    await close()
        except Exception:
            pass
        try:
            if self._stdio_ctx is not None:
                await self._stdio_ctx.__aexit__(None, None, None)
        except Exception:
            pass
        if self in _ACTIVE_SERVERS:
            _ACTIVE_SERVERS.remove(self)


def list_active_servers() -> list[McpServer]:
    """Return a snapshot of the MCP servers currently connected.

    The list is a copy: mutating it does not affect the registry. Servers
    are removed automatically when
    [`McpServer.aclose`][vulpcode.mcp.client.McpServer.aclose] runs.

    Returns:
        Every [`McpServer`][vulpcode.mcp.client.McpServer] returned by
        [`connect_mcp_server`][vulpcode.mcp.client.connect_mcp_server]
        whose ``aclose`` has not yet completed.
    """
    return list(_ACTIVE_SERVERS)


async def connect_mcp_server(
    name: str,
    command: str,
    args: list[str] | None = None,
    env: dict[str, str] | None = None,
) -> McpServer:
    """Spawn an MCP subprocess and register its tools.

    Boots the server over stdio, calls ``initialize`` and ``list_tools``,
    builds a [`Tool`][vulpcode.tools.base.Tool] adapter per advertised
    tool, and registers every adapter in ``TOOL_REGISTRY`` under the name
    ``mcp__<name>__<tool>``.

    Args:
        name: Local label for the server. Used as the prefix in qualified
            tool names; must be unique across active servers.
        command: Executable that implements the MCP server (e.g. ``"npx"``,
            ``"python"``, ``"uvx"``).
        args: CLI arguments for ``command``. Defaults to ``[]``.
        env: Extra environment variables merged on top of ``os.environ``
            for the subprocess. Use this to pass tokens or paths required
            by the server.

    Returns:
        The connected [`McpServer`][vulpcode.mcp.client.McpServer]. Remember
        to call ``aclose()`` when done — typically via
        [`stop_servers`][vulpcode.mcp.loader.stop_servers].
    """
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(
        command=command,
        args=list(args or []),
        env={**os.environ, **(env or {})},
    )
    stdio_ctx = stdio_client(params)
    read_stream, write_stream = await stdio_ctx.__aenter__()
    session_ctx = ClientSession(read_stream, write_stream)
    session = await session_ctx.__aenter__()
    await session.initialize()

    listing = await session.list_tools()
    tool_classes: list[type[Tool]] = []
    for t in listing.tools:
        tool_classes.append(_make_tool_adapter(name, session, t))

    server = McpServer(
        name=name,
        session=session,
        tool_classes=tool_classes,
        stdio_ctx=stdio_ctx,
        session_ctx=session_ctx,
    )
    _ACTIVE_SERVERS.append(server)
    return server


def _make_tool_adapter(server_name: str, session: Any, mcp_tool: Any) -> type[Tool]:
    """Build a Tool subclass at runtime that calls the MCP tool over the session."""
    schema = getattr(mcp_tool, "inputSchema", None) or {"type": "object"}

    input_model = _input_model_from_schema(
        schema, name=f"{server_name}_{mcp_tool.name}_Input"
    )

    qualified_name = f"mcp__{server_name}__{mcp_tool.name}"
    description = (getattr(mcp_tool, "description", None) or "")[:500]

    captured_session = session
    captured_mcp_name = mcp_tool.name

    @tool(
        name=qualified_name,
        description=description,
        requires_confirm=False,
    )
    class _Adapter(Tool):
        Input = input_model
        _session = captured_session
        _mcp_tool_name = captured_mcp_name

        async def run(self, args: BaseModel) -> ToolResult:
            payload = args.model_dump() if hasattr(args, "model_dump") else dict(args)
            try:
                result = await self._session.call_tool(self._mcp_tool_name, payload)
            except Exception as exc:
                return ToolResult(
                    error=f"{type(exc).__name__}: {exc}",
                    is_error=True,
                    metadata={"server": server_name},
                )
            text_parts: list[str] = []
            for item in result.content or []:
                if getattr(item, "type", "") == "text":
                    text_parts.append(getattr(item, "text", ""))
            output = "\n".join(text_parts)
            if getattr(result, "isError", False):
                return ToolResult(
                    error=output or "MCP tool error",
                    is_error=True,
                    metadata={"server": server_name},
                )
            return ToolResult(output=output, metadata={"server": server_name})

    _Adapter.__qualname__ = f"McpAdapter[{qualified_name}]"
    return _Adapter


def _input_model_from_schema(schema: dict[str, Any], name: str) -> type[BaseModel]:
    """Build a permissive Pydantic model from a JSON schema (object only)."""
    if schema.get("type") != "object":
        return create_model(name)
    fields: dict[str, Any] = {}
    props = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    for fname in props:
        default = ... if fname in required else None
        fields[fname] = (Any, default)
    return create_model(name, **fields)
