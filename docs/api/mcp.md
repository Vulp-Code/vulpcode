# MCP

Cliente Python para o
[Model Context Protocol](https://modelcontextprotocol.io). Cada servidor
MCP roda como subprocesso (stdio) e suas tools sao expostas para o
[`Agent`](agent.md) via adapters dinamicos registrados em
`TOOL_REGISTRY` sob o nome `mcp__<server>__<tool>`.

Para o uso operacional — quais servidores ja existem na comunidade,
como configurar `[[mcp.servers]]` no `config.toml`, troubleshooting —
veja [MCP Guide](../mcp/index.md).

## Cliente

::: vulpcode.mcp.client.McpServer
    options:
      heading_level: 3
      show_root_heading: true
      show_root_full_path: false
      members:
        - name
        - tools
        - tool_classes
        - call
        - aclose
      merge_init_into_class: true

::: vulpcode.mcp.client.connect_mcp_server
    options:
      heading_level: 3
      show_root_heading: true
      show_root_full_path: false

::: vulpcode.mcp.client.list_active_servers
    options:
      heading_level: 3
      show_root_heading: true
      show_root_full_path: false

## Loader

`loader.py` envolve `connect_mcp_server` para consumir o array
`mcp.servers` do [`config`](config.md). E o caminho usado pelo CLI no
boot do REPL.

::: vulpcode.mcp.loader.start_configured_servers
    options:
      heading_level: 3
      show_root_heading: true
      show_root_full_path: false

::: vulpcode.mcp.loader.stop_servers
    options:
      heading_level: 3
      show_root_heading: true
      show_root_full_path: false

## Exemplo: spawn manual

```python
import asyncio

from vulpcode.mcp import (
    connect_mcp_server,
    list_active_servers,
    stop_servers,
)

async def main() -> None:
    server = await connect_mcp_server(
        name="filesystem",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
    )
    # `server.tools` lista os nomes qualificados que ja estao no
    # TOOL_REGISTRY -- o Agent pode chama-los como qualquer outro tool.
    print("tools:", server.tools)

    # Chamada direta (raramente preciso -- o Agent faz isso)
    output = await server.call("read_file", {"path": "/tmp/exemplo.txt"})
    print(output)

    print("active:", [s.name for s in list_active_servers()])
    await stop_servers([server])

asyncio.run(main())
```

## Exemplo: boot a partir do config

```python
import asyncio

from vulpcode.config import load_config
from vulpcode.mcp import start_configured_servers, stop_servers

async def main() -> None:
    cfg = load_config()
    servers = await start_configured_servers(cfg)
    try:
        # ... rodar o Agent normalmente ...
        pass
    finally:
        await stop_servers(servers)

asyncio.run(main())
```

Com um `config.toml` parecido com:

```toml
[[mcp.servers]]
name = "filesystem"
command = "npx"
args = ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]

[[mcp.servers]]
name = "github"
command = "uvx"
args = ["mcp-server-github"]
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }
```

!!! note "Expansao de `${VAR}`"
    Em `[[mcp.servers]].env` valores no formato `"${VAR}"` sao trocados
    pelo conteudo de `os.environ["VAR"]` no momento do boot. Se a
    variavel nao existir o valor vira string vazia — o servidor pode
    quebrar logo de cara, e o erro fica visivel via
    `[mcp] failed to start <name>: ...`.

!!! warning "Sempre `aclose`"
    `McpServer` mantem um subprocesso vivo. Se voce esquecer de chamar
    `aclose()` (ou `stop_servers`) o processo do servidor continua
    rodando depois do seu programa terminar. Em scripts curtos use
    `try/finally`.

Veja tambem:

- [MCP Guide](../mcp/index.md) — visao operacional.
- [Tools API](tools.md#vulpcode.tools.base.TOOL_REGISTRY) — onde os
  adapters `mcp__*` sao registrados.
- [Config](config.md) — chave `mcp.servers` consumida pelo loader.
