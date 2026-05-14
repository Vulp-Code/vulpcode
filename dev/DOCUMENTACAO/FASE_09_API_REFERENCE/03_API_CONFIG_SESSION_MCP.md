# Tarefa 09.03 - API Reference (Config + Session + MCP)

**Status**: PENDENTE
**Fase**: 09 - API Reference
**Dependencias**: 09.02
**Bloqueia**: nada (ultima da fase 09)

---

## Objetivo

Completar a API reference com config.py, session.py, mcp/.

---

## Arquivos a criar

- `docs/api/config.md`
- `docs/api/session.md`
- `docs/api/mcp.md`

---

## Pre-requisito: docstrings

Auditar e melhorar:
- `src/vulpcode/config.py` — `load_config`, `save_config`, `config_paths`,
  `DEFAULTS`, `ENV_MAP`
- `src/vulpcode/session.py` — `save_session`, `load_session`, `list_sessions`,
  `latest_session_name`, `delete_session`
- `src/vulpcode/mcp/client.py` — `McpServer`, `connect_mcp_server`,
  `list_active_servers`
- `src/vulpcode/mcp/loader.py` — `start_configured_servers`, `stop_servers`

---

## Conteudo de `api/config.md`

```markdown
# Config

Hierarquia: DEFAULTS < `~/.vulpcode/config.toml` < `<projeto>/.vulpcode/config.toml`
< env vars < CLI overrides.

Veja [Configuracao](../configuration/index.md) para uso operacional.

## Defaults e ENV_MAP

::: vulpcode.config.DEFAULTS
::: vulpcode.config.ENV_MAP

## Funcoes

::: vulpcode.config.load_config
::: vulpcode.config.save_config
::: vulpcode.config.config_paths

## Exemplo

```python
from vulpcode.config import load_config

cfg = load_config()
print(cfg["default_provider"])
print(cfg["providers"].get("anthropic", {}).get("api_key"))
```
```

---

## Conteudo de `api/session.md`

```markdown
# Session

Persistencia de sessoes em `~/.vulpcode/sessions/<name>.json`. Veja
[Sessoes](../user-guide/sessions.md) para uso operacional.

## Funcoes

::: vulpcode.session.save_session
::: vulpcode.session.load_session
::: vulpcode.session.list_sessions
::: vulpcode.session.latest_session_name
::: vulpcode.session.delete_session

## Exemplo

```python
from vulpcode.session import list_sessions, load_session

# Listar
for s in list_sessions():
    print(s["name"], s["saved_at"], s["messages"])

# Recarregar uma sessao em um Agent
# (requer um Agent ja construido — ver api/agent.md)
load_session("trabalho-backup", agent)
```
```

---

## Conteudo de `api/mcp.md`

```markdown
# MCP

Cliente Model Context Protocol. Veja [MCP Guide](../mcp/index.md) para
configuracao operacional.

## Cliente

::: vulpcode.mcp.client.McpServer
::: vulpcode.mcp.client.connect_mcp_server
::: vulpcode.mcp.client.list_active_servers

## Loader

::: vulpcode.mcp.loader.start_configured_servers
::: vulpcode.mcp.loader.stop_servers

## Exemplo

```python
import asyncio
from vulpcode.mcp import connect_mcp_server, list_active_servers

async def main():
    server = await connect_mcp_server(
        name="filesystem",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
    )
    print("tools:", server.tools)
    # ...usar tools via TOOL_REGISTRY com nomes mcp__filesystem__<name>

asyncio.run(main())
```
```

---

## Atualizar `mkdocs.yml`

Entradas ja foram adicionadas em 09.01. Nao mexer.

---

## INSTRUCAO CRITICA

- `DEFAULTS` e `ENV_MAP` sao constantes, nao funcoes — mkdocstrings as
  renderiza como modulo-level data (mostra o valor). Verificar visualmente.
- Para `McpServer`, mostrar atributos publicos (`name`, `tools`, `tool_classes`).

---

## Etapas de Implementacao

### Etapa 1: Auditar e melhorar docstrings dos modulos listados
### Etapa 2: Criar 3 arquivos
### Etapa 3: `mkdocs build`

---

## Criterios de Aceite

- [x] Docstrings em config.py, session.py, mcp/client.py, mcp/loader.py auditadas
- [x] `docs/api/config.md` criado
- [x] `docs/api/session.md` criado
- [x] `docs/api/mcp.md` criado
- [x] mkdocstrings renderiza tudo sem warning
- [x] `mkdocs build` continua passando

---

**End of Specification**
