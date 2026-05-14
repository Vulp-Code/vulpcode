# API Reference

Referencia auto-gerada da API publica do `vulpcode`. Use isso ao integrar
o vulpcode como biblioteca em outro projeto Python — todas as paginas desta
secao sao geradas em tempo real a partir das docstrings em
`src/vulpcode/`, entao o que voce le aqui sempre reflete o codigo da
versao instalada.

## Modulos

- [Providers](providers.md) — `Provider`, `build_provider`, types canonicos
  (`Message`, `ToolCall`, `Usage`, `StreamChunk`).
- [Tools](tools.md) — `Tool`, `@tool`, `ToolResult`, registry e helpers
  (`get_tool`, `list_tools`, `execute_tool_call`).
- [Agent](agent.md) — `Agent` class, eventos do loop, `run_to_completion`.
- [Permissions](permissions.md) — `PermissionManager`, `Mode`, `stdin_prompter`.
- **Config** *(em breve)* — `load_config`, `save_config`.
- **Session** *(em breve)* — `save_session`, `load_session`.
- **MCP** *(em breve)* — `connect_mcp_server`, `start_configured_servers`.

## Convencao

- Tudo neste site e gerado das docstrings em `src/vulpcode/` via
  [`mkdocstrings`](https://mkdocstrings.github.io/). Para abrir o codigo no
  GitHub, clique no link **Source** abaixo de cada simbolo.
- Os exemplos seguem o formato Google (campos `Args`, `Returns`, `Raises`,
  `Example`).
- Symbol references usam o caminho importavel completo, por exemplo
  `vulpcode.providers.registry.build_provider`.

## Como ler esta secao

Se voce quer:

- **Construir um provider em codigo**, va para
  [Providers](providers.md#registry) — comece por `build_provider`.
- **Escrever um novo tool**, va para [Tools](tools.md) — comece pela classe
  `Tool` e o decorator `@tool`.
- **Entender o tipo de evento que sai do streaming**, va para
  [Providers](providers.md) — `StreamChunk`.

## Uso como biblioteca

```python
from vulpcode.providers.registry import build_provider
from vulpcode.providers.base import Message

provider = build_provider("anthropic", {"api_key": "sk-ant-..."})

async for chunk in provider.stream(
    messages=[Message(role="user", content="ola")],
    tools=[],
    model="claude-sonnet-4-7",
    system="Voce e um assistente conciso.",
):
    if chunk.type == "text":
        print(chunk.delta, end="", flush=True)
```

Para um tour mais alto-nivel da arquitetura, veja
[Conceitos principais](../getting-started/core-concepts.md).
