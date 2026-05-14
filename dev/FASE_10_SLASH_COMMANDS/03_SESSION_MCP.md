# Tarefa 10.03 - Slash Commands /save /load /mcp

**Status**: PENDENTE
**Fase**: 10 - Slash Commands
**Dependencias**: 10.02
**Bloqueia**: Nada

---

## Objetivo

Adicionar comandos `/save <nome>`, `/load <nome>`, `/mcp` ao registry. `/save` e
`/load` ainda nao tem implementacao real de persistencia (vem na FASE 12 — esta
tarefa cria stubs). `/mcp` lista servidores MCP conhecidos (consume FASE 11).

---

## Descricao Tecnica

### Estrutura

**`src/vulpcode/commands/session_cmds.py`**:

```python
"""/save and /load slash commands.

Stubs in this phase — real persistence implemented in FASE 12.
"""
from __future__ import annotations

from pathlib import Path

from vulpcode.commands._base import SlashCommand


def _sessions_dir() -> Path:
    p = Path.home() / ".vulpcode" / "sessions"
    p.mkdir(parents=True, exist_ok=True)
    return p


class SaveCommand(SlashCommand):
    name = "save"
    help_text = "Save current session messages: /save <name>"

    async def run(self, repl, args: str) -> None:
        name = args.strip() or "default"
        try:
            from vulpcode.session import save_session
        except ImportError:
            # FASE 12 not yet implemented; do raw json fallback
            from vulpcode.session_fallback import save_session  # type: ignore
        path = save_session(name, repl.agent)
        repl.renderer.console.print(f"[green]saved session to {path}[/]")


class LoadCommand(SlashCommand):
    name = "load"
    help_text = "Load a saved session: /load <name>"

    async def run(self, repl, args: str) -> None:
        name = args.strip() or "default"
        try:
            from vulpcode.session import load_session
        except ImportError:
            from vulpcode.session_fallback import load_session  # type: ignore
        try:
            load_session(name, repl.agent)
        except FileNotFoundError:
            repl.renderer.render_error(f"no saved session named {name!r}")
            return
        repl.renderer.console.print(f"[green]loaded session {name}[/]")
```

**`src/vulpcode/commands/mcp_cmd.py`**:

```python
"""/mcp slash command."""
from __future__ import annotations

from vulpcode.commands._base import SlashCommand


class McpCommand(SlashCommand):
    name = "mcp"
    help_text = "List MCP servers and the tools they provide"

    async def run(self, repl, args: str) -> None:
        servers = repl.config.get("mcp", {}).get("servers", []) or []
        if not servers:
            repl.renderer.console.print("[muted]no MCP servers configured[/]")
            return
        rows = []
        for s in servers:
            rows.append([
                s.get("name", "?"),
                s.get("command", ""),
                " ".join(s.get("args", [])),
            ])
        repl.renderer.render_table("MCP servers", ["name", "command", "args"], rows)
        # Optional: list active tools provided by mcp (depends on FASE 11)
        try:
            from vulpcode.mcp import list_active_servers
            active = list_active_servers()
        except ImportError:
            active = []
        if active:
            tool_rows = [[s.name, ", ".join(s.tools)] for s in active]
            repl.renderer.render_table("MCP tools", ["server", "tools"], tool_rows)
```

### Stub temporario (`src/vulpcode/session_fallback.py`)

Como `session.py` real vem na FASE 12, fazemos um stub minimo aqui para que
/save e /load funcionem:

```python
"""Temporary fallback session persistence (replaced by FASE 12)."""
from __future__ import annotations

import json
from pathlib import Path


def _sessions_dir() -> Path:
    p = Path.home() / ".vulpcode" / "sessions"
    p.mkdir(parents=True, exist_ok=True)
    return p


def save_session(name: str, agent) -> Path:
    target = _sessions_dir() / f"{name}.json"
    payload = {
        "model": agent.model,
        "system": agent.system,
        "messages": [m.model_dump() for m in agent._messages],
    }
    target.write_text(json.dumps(payload, indent=2))
    return target


def load_session(name: str, agent) -> None:
    from vulpcode.providers.base import Message
    target = _sessions_dir() / f"{name}.json"
    if not target.exists():
        raise FileNotFoundError(name)
    payload = json.loads(target.read_text())
    agent.model = payload.get("model", agent.model)
    agent.system = payload.get("system", agent.system)
    agent._messages = [Message.model_validate(m) for m in payload.get("messages", [])]
```

### Atualizar `commands/__init__.py`

```python
from vulpcode.commands.mcp_cmd import McpCommand
from vulpcode.commands.session_cmds import LoadCommand, SaveCommand


def build_default_commands() -> dict[str, SlashCommand]:
    cmds = [
        ToolsCommand(),
        CostCommand(),
        CompactCommand(),
        ProviderCommand(),
        ModelCommand(),
        SaveCommand(),
        LoadCommand(),
        McpCommand(),
    ]
    return {c.name: c for c in cmds}
```

---

## INSTRUCAO CRITICA

- O fallback `session_fallback.py` e descartavel — quando FASE 12 implementar
  `vulpcode/session.py`, o try/except em `save_command/load_command` ira
  preferir o real.
- `/mcp` em FASE 11 ganha listagem real de tools ativas. Por enquanto so lista
  servidores configurados.

---

## Etapas de Implementacao

### Etapa 1: Criar `commands/session_cmds.py` e `commands/mcp_cmd.py`

### Etapa 2: Criar stub `session_fallback.py`

### Etapa 3: Atualizar `commands/__init__.py`

### Etapa 4: Adicionar testes em `tests/test_commands.py`

```python
@pytest.mark.asyncio
async def test_save_and_load_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    from vulpcode.commands import SaveCommand, LoadCommand
    from vulpcode.providers.base import Message

    class Agent:
        model = "m"
        system = "s"
        _messages = [Message(role="user", content="hi")]
        provider = type("P", (), {"name": "x"})()

    repl = FakeRepl(agent=Agent())
    await SaveCommand().run(repl, "test1")
    repl.agent._messages = []
    await LoadCommand().run(repl, "test1")
    assert repl.agent._messages[0].content == "hi"


@pytest.mark.asyncio
async def test_mcp_lists_servers():
    from vulpcode.commands import McpCommand
    repl = FakeRepl()
    repl.config = {"mcp": {"servers": [{"name": "fs", "command": "npx", "args": ["-y", "x"]}]}}
    await McpCommand().run(repl, "")
    assert "fs" in repl.buf.getvalue()
```

### Etapa 5: Rodar testes

```bash
pytest tests/test_commands.py -v
```

---

## Criterios de Aceite

- [x] `src/vulpcode/commands/session_cmds.py` com `SaveCommand` e `LoadCommand`
- [x] `src/vulpcode/commands/mcp_cmd.py` com `McpCommand`
- [x] `src/vulpcode/session_fallback.py` stub funcional para save/load
- [x] `commands/__init__.py` adiciona os tres comandos em `build_default_commands()`
- [x] `/save <name>` e `/load <name>` round-trip via JSON
- [x] `/mcp` lista servers do config (vazio se nada configurado)
- [x] `tests/test_commands.py` com >=2 testes adicionais, passando

---

## Riscos Tecnicos

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|---------------|---------|-----------|
| Mensagens nao roundtripiveis | Baixa | Medio | Pydantic dump/validate cobre |
| FASE 12 mudando o formato | Media | Baixo | session_fallback.py sera substituido |

---

**End of Specification**
