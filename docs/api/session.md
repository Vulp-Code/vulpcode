# Session

Persistencia de sessoes em `~/.vulpcode/sessions/<name>.json`. Cada
sessao e um snapshot completo do estado do
[`Agent`](agent.md) — modelo, system prompt, mensagens e *usage* —
serializado como JSON e gravado de forma atomica (tmp + rename).

Para o uso operacional pelo REPL (`/save`, `/load`, `--resume`) veja
[Sessoes](../user-guide/sessions.md).

## Funcoes

::: vulpcode.session.save_session
    options:
      heading_level: 3
      show_root_heading: true
      show_root_full_path: false

::: vulpcode.session.load_session
    options:
      heading_level: 3
      show_root_heading: true
      show_root_full_path: false

::: vulpcode.session.list_sessions
    options:
      heading_level: 3
      show_root_heading: true
      show_root_full_path: false

::: vulpcode.session.latest_session_name
    options:
      heading_level: 3
      show_root_heading: true
      show_root_full_path: false

::: vulpcode.session.delete_session
    options:
      heading_level: 3
      show_root_heading: true
      show_root_full_path: false

## Exemplo

```python
import asyncio

from vulpcode.agent import Agent
from vulpcode.permissions import Mode, PermissionManager
from vulpcode.providers import build_provider
from vulpcode.session import (
    delete_session,
    latest_session_name,
    list_sessions,
    load_session,
    save_session,
)
from vulpcode.tools import list_tools
import vulpcode.tools  # noqa: F401  -- registra os tools embutidos

async def main() -> None:
    # Listar sessoes existentes (mais recente primeiro)
    for s in list_sessions():
        print(s["name"], s["saved_at"], s["messages"], "msgs")

    # Construir um agente novo e restaurar a sessao mais recente
    provider = build_provider("anthropic", {"api_key": "sk-ant-..."})
    agent = Agent(
        provider=provider,
        tools=[cls() for cls in list_tools()],
        model="claude-sonnet-4-6",
        permissions=PermissionManager(config={}, mode=Mode.AUTO),
    )

    name = latest_session_name()
    if name:
        load_session(name, agent)  # restaura system, model, messages, usage
        print(f"resumed {name!r} ({len(agent._messages)} msgs)")

    # Continuar a conversa e salvar de volta
    await agent.run_to_completion("o que faltou?")
    save_session(name or "scratch", agent)

    # Limpeza
    delete_session("antigo")

asyncio.run(main())
```

!!! note "Nomes seguros"
    `save_session` e `delete_session` filtram o nome — apenas
    `[A-Za-z0-9_-]` sobrevivem. Um nome composto so de simbolos vira
    o arquivo `default.json`.

!!! warning "Provider nao e restaurado"
    `load_session` reescreve `system`, `model`, `_messages` e
    `_session_usage`, mas **nao** troca o provider do agente. Construa
    o `Agent` com o provider correto antes de chamar `load_session`.

Veja tambem:

- [Sessoes](../user-guide/sessions.md) — slash-commands do REPL.
- [Agent API](agent.md) — onde as mensagens sao guardadas.
