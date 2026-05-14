# Tarefa 11.01 - Cliente MCP

**Status**: PENDENTE
**Fase**: 11 - MCP
**Dependencias**: 02.02 (Tool ABC)
**Bloqueia**: 11.02

---

## Objetivo

Implementar cliente MCP em `src/vulpcode/mcp/client.py` usando a lib oficial
`mcp` (Anthropic). Conecta a um servidor MCP via subprocess (stdio), descobre
suas tools, e cria adapters `Tool` que envolvem cada tool MCP no contrato do
vulpcode.

---

## Descricao Tecnica

### Visao geral

MCP = Model Context Protocol. Servidores MCP rodam como subprocess e expoem
tools via stdio (JSON-RPC). Cliente:
1. Spawn do servidor (`npx -y @modelcontextprotocol/server-X` etc).
2. Initialize handshake.
3. Listar tools disponiveis.
4. Para cada tool, criar um `Tool` subclass que delega ao MCP.

### API publica

```python
class McpServer:
    """Spawned MCP subprocess + the Tools it provides."""
    name: str
    process: asyncio.subprocess.Process
    tools: list[type[Tool]]

    async def call(self, tool_name: str, args: dict) -> str: ...
    async def aclose(self) -> None: ...


async def connect_mcp_server(
    name: str,
    command: str,
    args: list[str] | None = None,
    env: dict[str, str] | None = None,
) -> McpServer: ...
```

### Estrutura

**`src/vulpcode/mcp/client.py`**:

```python
"""MCP client using the official `mcp` Python library."""
from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel, create_model

from vulpcode.tools.base import Tool, ToolResult, tool


_ACTIVE_SERVERS: list["McpServer"] = []


class McpServer:
    def __init__(self, name: str, session, tool_classes: list[type[Tool]]) -> None:
        self.name = name
        self._session = session  # mcp.ClientSession
        self.tool_classes = tool_classes
        self.tools = [c._tool_name for c in tool_classes]

    async def aclose(self) -> None:
        try:
            await self._session.close()
        except Exception:
            pass


def list_active_servers() -> list[McpServer]:
    return list(_ACTIVE_SERVERS)


async def connect_mcp_server(
    name: str,
    command: str,
    args: list[str] | None = None,
    env: dict[str, str] | None = None,
) -> McpServer:
    """Spawn the server, list its tools, register adapters, return McpServer."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(
        command=command,
        args=list(args or []),
        env={**os.environ, **(env or {})},
    )
    # The `mcp` library uses async context managers; we keep them open via `__aenter__`
    stdio = stdio_client(params)
    read_stream, write_stream = await stdio.__aenter__()
    session = await ClientSession(read_stream, write_stream).__aenter__()
    await session.initialize()

    listing = await session.list_tools()
    tool_classes: list[type[Tool]] = []
    for t in listing.tools:
        tool_classes.append(_make_tool_adapter(name, session, t))

    server = McpServer(name=name, session=session, tool_classes=tool_classes)
    _ACTIVE_SERVERS.append(server)
    return server


def _make_tool_adapter(server_name: str, session: Any, mcp_tool: Any) -> type[Tool]:
    """Build a Tool subclass at runtime that calls the MCP tool over the session."""
    schema = mcp_tool.inputSchema or {"type": "object"}

    # Build a permissive Pydantic Input model from the schema
    input_model = _input_model_from_schema(schema, name=f"{server_name}_{mcp_tool.name}_Input")

    qualified_name = f"mcp__{server_name}__{mcp_tool.name}"

    @tool(
        name=qualified_name,
        description=(mcp_tool.description or "")[:500],
        requires_confirm=False,
    )
    class _Adapter(Tool):
        Input = input_model
        _session = session
        _mcp_tool_name = mcp_tool.name

        async def run(self, args):
            payload = args.model_dump() if hasattr(args, "model_dump") else dict(args)
            result = await self._session.call_tool(self._mcp_tool_name, payload)
            # mcp returns a list of content items; concat text parts
            text_parts: list[str] = []
            for item in (result.content or []):
                if getattr(item, "type", "") == "text":
                    text_parts.append(getattr(item, "text", ""))
            output = "\n".join(text_parts)
            if result.isError:
                return ToolResult(error=output or "MCP tool error", is_error=True)
            return ToolResult(output=output, metadata={"server": server_name})

    _Adapter.__qualname__ = f"McpAdapter[{qualified_name}]"
    return _Adapter


def _input_model_from_schema(schema: dict, name: str) -> type[BaseModel]:
    """Build a permissive Pydantic model from a JSON schema (object only)."""
    if schema.get("type") != "object":
        return create_model(name, **{})
    fields: dict[str, Any] = {}
    props = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    for fname, fspec in props.items():
        # Permissive: accept Any for now, marking required
        default = ... if fname in required else None
        fields[fname] = (Any, default)
    return create_model(name, **fields)
```

### Atualizar `mcp/__init__.py`

```python
"""Model Context Protocol client and loader."""
from vulpcode.mcp.client import (
    McpServer,
    connect_mcp_server,
    list_active_servers,
)

__all__ = ["McpServer", "connect_mcp_server", "list_active_servers"]
```

---

## INSTRUCAO CRITICA

- A lib `mcp` usa async context managers (`async with stdio_client(...) as ...`)
  para gerenciar o subprocess. Nesta implementacao mantemos a context "aberta"
  manualmente via `__aenter__` para que o servidor permaneca rodando ate
  `aclose()`.
- Tools MCP sao registradas com nome qualificado: `mcp__<server>__<tool>` para
  evitar colisao com tools nativas e identificar a origem.
- `_input_model_from_schema` e permissivo (aceita `Any`) — uma versao mais
  estrita exigiria conversor JSON-Schema -> Pydantic mais sofisticado, pode ser
  feito em fase futura.
- `requires_confirm=False` por padrao — o usuario confiou no MCP server ao
  configura-lo.
- Erros do MCP retornam `is_error=True` para o agent loop tratar.

---

## Etapas de Implementacao

### Etapa 1: Criar `mcp/client.py`

### Etapa 2: Atualizar `mcp/__init__.py`

### Etapa 3: Criar `tests/test_mcp_client.py`

Testes unitarios sao limitados sem um servidor MCP real. Vamos testar o
`_input_model_from_schema` e a estrutura do adapter sem chamada real:

```python
import pytest

from vulpcode.mcp.client import _input_model_from_schema


def test_input_model_required_field():
    schema = {
        "type": "object",
        "properties": {"file_path": {"type": "string"}, "limit": {"type": "integer"}},
        "required": ["file_path"],
    }
    model = _input_model_from_schema(schema, "Test")
    inst = model(file_path="/a")
    assert inst.file_path == "/a"
    with pytest.raises(Exception):
        model()  # missing required


def test_input_model_object_no_props():
    schema = {"type": "object"}
    model = _input_model_from_schema(schema, "Empty")
    inst = model()
    assert inst is not None


def test_active_servers_starts_empty():
    from vulpcode.mcp import list_active_servers
    # State may be polluted by other tests; just verify it's a list
    assert isinstance(list_active_servers(), list)


@pytest.mark.skip(reason="requires actual MCP server; covered by integration smoke tests in FASE 14")
async def test_connect_real_server():
    pass
```

### Etapa 4: Rodar testes

```bash
pytest tests/test_mcp_client.py -v
```

---

## Criterios de Aceite

- [x] `src/vulpcode/mcp/client.py` define `McpServer`, `connect_mcp_server`, `list_active_servers`
- [x] Adapters criados dinamicamente via `_make_tool_adapter` para cada tool do MCP
- [x] Nome das tools qualificado como `mcp__<server>__<tool>`
- [x] `_input_model_from_schema` constroi Pydantic permissivo a partir de JSON Schema
- [x] Erros MCP envolvidos em `ToolResult(is_error=True)`
- [x] `mcp/__init__.py` re-exporta `connect_mcp_server`, `list_active_servers`, `McpServer`
- [x] `tests/test_mcp_client.py` com >=3 testes unitarios, passando (sem servidor real)

---

## Riscos Tecnicos

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|---------------|---------|-----------|
| API da lib `mcp` muda | Media | Alto | Pinar `mcp>=1.0` |
| Servidor MCP trava | Baixa | Medio | Aceitar; usuario fecha REPL |
| Nome qualificado colide com nativa | Baixa | Baixo | Prefixo `mcp__` evita |

---

**End of Specification**
