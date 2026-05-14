# Agent

O coracao do vulpcode: orquestra o loop LLM <-> tools, aplica permissoes e
emite eventos para a UI consumir. Use esta API quando voce quer embutir o
agente em outro programa Python (script, web app, teste); para usar pelo
terminal veja [Quickstart](../getting-started/quickstart.md).

Pecas relacionadas:

- [Providers](providers.md) — `Provider`, `Message`, `ToolCall`, `Usage`.
- [Tools](tools.md) — `Tool`, `ToolResult`, registry.
- [Permissions](permissions.md) — `PermissionManager`, `Mode`.

## Eventos

Cada chamada a [`Agent.turn`](#vulpcode.agent.Agent.turn) e um *async generator*
que devolve uma sequencia destes eventos. A UI escolhe o que renderizar.

::: vulpcode.agent
    options:
      heading_level: 3
      show_root_heading: false
      show_root_full_path: false
      members:
        - TextEvent
        - ToolStartEvent
        - ToolEndEvent
        - ToolDeniedEvent
        - UsageEvent
        - TurnEndEvent
        - ErrorEvent
        - Event

## Classe Agent

::: vulpcode.agent.Agent
    options:
      heading_level: 3
      show_root_heading: true
      show_root_full_path: false
      show_source: true
      merge_init_into_class: true
      members_order: source

## Exemplo

```python
import asyncio

from vulpcode.agent import Agent, TextEvent, ToolEndEvent
from vulpcode.permissions import Mode, PermissionManager
from vulpcode.providers import build_provider
from vulpcode.tools import list_tools
import vulpcode.tools  # noqa: F401  — registra os tools embutidos

async def main() -> None:
    provider = build_provider("anthropic", {"api_key": "sk-ant-..."})
    tools = [cls() for cls in list_tools()]
    perms = PermissionManager(config={}, mode=Mode.AUTO)
    agent = Agent(
        provider=provider,
        tools=tools,
        model="claude-sonnet-4-6",
        permissions=perms,
    )

    # 1) Stream evento-a-evento (UI rica):
    async for ev in agent.turn("liste os arquivos em /tmp"):
        if isinstance(ev, TextEvent):
            print(ev.text, end="", flush=True)
        elif isinstance(ev, ToolEndEvent):
            print(f"\n[tool {ev.tool_call.name} done]")

    # 2) Ou apenas consuma o texto final (script/teste):
    text = await agent.run_to_completion("explique async/await em 2 frases")
    print(text)

asyncio.run(main())
```

!!! tip "Modo `PLAN` para revisao"
    Construa o agente com `PermissionManager(config={}, mode=Mode.PLAN)` para
    deixar o modelo *raciocinar* sobre a tarefa sem permitir nenhuma execucao
    de tool — todos os pedidos viram `ToolDeniedEvent`. Util para auditar o
    que o agente *iria* fazer antes de liberar a execucao real.
