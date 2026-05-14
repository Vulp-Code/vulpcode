# Tarefa 11.02 - MCP Loader e Integracao com app.py

**Status**: PENDENTE
**Fase**: 11 - MCP
**Dependencias**: 11.01 (cliente MCP)
**Bloqueia**: Nada

---

## Objetivo

Implementar `src/vulpcode/mcp/loader.py` com `start_configured_servers()` que
le `config["mcp"]["servers"]` e levanta cada servidor via `connect_mcp_server`.
Integrar no `app.py` para que servidores configurados sejam levantados antes
do REPL iniciar e fechados ao sair.

---

## Descricao Tecnica

### Estrutura

**`src/vulpcode/mcp/loader.py`**:

```python
"""Boot MCP servers configured in vulpcode config."""
from __future__ import annotations

from typing import Any

from vulpcode.mcp.client import McpServer, connect_mcp_server


async def start_configured_servers(config: dict[str, Any]) -> list[McpServer]:
    """Spawn every server listed under config['mcp']['servers']."""
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
            # Log but keep going — one bad server should not block REPL.
            print(f"[mcp] failed to start {name}: {exc}")
            continue
        started.append(server)
    return started


async def stop_servers(servers: list[McpServer]) -> None:
    for s in servers:
        try:
            await s.aclose()
        except Exception:
            pass


def _resolve_env(env: dict[str, Any]) -> dict[str, str]:
    """Expand ${VAR} references in env values."""
    import os
    out: dict[str, str] = {}
    for k, v in (env or {}).items():
        if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
            out[k] = os.environ.get(v[2:-1], "")
        else:
            out[k] = str(v)
    return out
```

### Atualizar `mcp/__init__.py`

```python
from vulpcode.mcp.client import (
    McpServer,
    connect_mcp_server,
    list_active_servers,
)
from vulpcode.mcp.loader import start_configured_servers, stop_servers

__all__ = [
    "McpServer",
    "connect_mcp_server",
    "list_active_servers",
    "start_configured_servers",
    "stop_servers",
]
```

### Atualizar `app.py`

```python
# inside start_repl, after building agent and renderer, before running:
from vulpcode.mcp import start_configured_servers, stop_servers

mcp_servers = await start_configured_servers(cfg)
# Add MCP-provided tools to the agent
for s in mcp_servers:
    for tcls in s.tool_classes:
        agent.tools[tcls._tool_name] = tcls()

try:
    if one_shot is not None:
        await repl.one_shot(one_shot)
        return 0
    await repl.run()
    return 0
finally:
    await stop_servers(mcp_servers)
```

---

## INSTRUCAO CRITICA

- Falhas individuais nao bloqueiam o REPL — outros servidores sao tentados.
- `${VAR}` em valores de env e expandido a partir do environment do processo.
- MCP-provided tools sao adicionadas ao agent.tools usando o nome qualificado
  `mcp__<server>__<name>` (ja gerado pelo cliente).
- Limpeza no `finally` garante que servidores sao fechados mesmo em
  excecao.

---

## Etapas de Implementacao

### Etapa 1: Criar `mcp/loader.py`

### Etapa 2: Atualizar `mcp/__init__.py`

### Etapa 3: Atualizar `app.py` (start_configured_servers + stop_servers + integracao com agent)

### Etapa 4: Criar `tests/test_mcp_loader.py`

```python
import pytest

from vulpcode.mcp.loader import _resolve_env


def test_resolve_env_basic(monkeypatch):
    monkeypatch.setenv("FOO", "bar")
    out = _resolve_env({"X": "${FOO}", "Y": "literal"})
    assert out["X"] == "bar"
    assert out["Y"] == "literal"


def test_resolve_env_missing(monkeypatch):
    monkeypatch.delenv("MISSING", raising=False)
    out = _resolve_env({"X": "${MISSING}"})
    assert out["X"] == ""


@pytest.mark.asyncio
async def test_start_configured_servers_empty_config():
    from vulpcode.mcp.loader import start_configured_servers
    servers = await start_configured_servers({})
    assert servers == []


@pytest.mark.asyncio
async def test_start_configured_servers_no_servers_key():
    from vulpcode.mcp.loader import start_configured_servers
    servers = await start_configured_servers({"mcp": {}})
    assert servers == []
```

### Etapa 5: Rodar testes

```bash
pytest tests/test_mcp_loader.py -v
```

---

## Criterios de Aceite

- [x] `src/vulpcode/mcp/loader.py` implementa `start_configured_servers` e `stop_servers`
- [x] `_resolve_env` expande `${VAR}` references
- [x] Falha em um servidor nao bloqueia outros (try/except por server)
- [x] `app.py` integra: levanta MCP antes do REPL, registra tools no agent, fecha no `finally`
- [x] `mcp/__init__.py` re-exporta `start_configured_servers`, `stop_servers`
- [x] `tests/test_mcp_loader.py` com >=4 testes, todos passando

---

## Riscos Tecnicos

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|---------------|---------|-----------|
| MCP servers demoram a iniciar | Media | Baixo | Aceitar; usuario espera |
| Falha do server prossegue silenciosamente | Media | Baixo | Print no stderr |
| Tools do MCP duplicam nome de nativa | Baixa | Medio | Prefixo `mcp__` previne |

---

**End of Specification**
