"""Boot MCP servers configured in vulpcode config."""
from __future__ import annotations

import os
from typing import Any

from vulpcode.mcp.client import McpServer, connect_mcp_server


async def start_configured_servers(config: dict[str, Any]) -> list[McpServer]:
    """Spawn every MCP server declared in ``config["mcp"]["servers"]``.

    Each entry must define ``name`` and ``command``; ``args`` and ``env``
    are optional. Values inside ``env`` of the form ``"${VAR}"`` are
    expanded from the current process environment. Failures are logged
    to stdout and skipped — one bad server never blocks the rest.

    Args:
        config: A loaded vulpcode config dict (see
            [`load_config`][vulpcode.config.load_config]).

    Returns:
        Every server that booted successfully. Pair with
        [`stop_servers`][vulpcode.mcp.loader.stop_servers] on shutdown.
    """
    servers_cfg = (config.get("mcp", {}) or {}).get("servers", []) or []
    started: list[McpServer] = []
    for s in servers_cfg:
        name = s.get("name")
        command = s.get("command")
        if not name or not command:
            continue
        try:
            server = await connect_mcp_server(
                name=name,
                command=command,
                args=s.get("args", []),
                env=_resolve_env(s.get("env", {})),
            )
        except Exception as exc:
            print(f"[mcp] failed to start {name}: {exc}")
            continue
        started.append(server)
    return started


async def stop_servers(servers: list[McpServer]) -> None:
    """Close every server in ``servers``, swallowing per-server errors.

    Designed for shutdown paths — calling this twice or on already-closed
    servers is safe.

    Args:
        servers: The list returned by
            [`start_configured_servers`][vulpcode.mcp.loader.start_configured_servers]
            (or any other source of [`McpServer`][vulpcode.mcp.client.McpServer]
            instances).
    """
    for s in servers:
        try:
            await s.aclose()
        except Exception:
            pass


def _resolve_env(env: dict[str, Any]) -> dict[str, str]:
    """Expand ${VAR} references in env values."""
    out: dict[str, str] = {}
    for k, v in (env or {}).items():
        if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
            out[k] = os.environ.get(v[2:-1], "")
        else:
            out[k] = str(v)
    return out
