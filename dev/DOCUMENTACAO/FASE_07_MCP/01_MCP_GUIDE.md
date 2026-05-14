# Tarefa 07.01 - MCP Guide

**Status**: PENDENTE
**Fase**: 07 - MCP
**Dependencias**: 06.02
**Bloqueia**: nada

---

## Objetivo

Criar `mcp/index.md` cobrindo: o que e MCP, configurar servidores em config.toml,
debug, e listagem de tools providas.

---

## Arquivos a criar

- `docs/mcp/index.md`

---

## Source de verdade

- `src/vulpcode/mcp/client.py` — `connect_mcp_server`, `_make_tool_adapter`
- `src/vulpcode/mcp/loader.py` — `start_configured_servers`, `_resolve_env`
- `src/vulpcode/commands/mcp_cmd.py` — `/mcp` comando

---

## Estrutura

### 1. O que e MCP?

[Model Context Protocol](https://modelcontextprotocol.io) — protocolo aberto
da Anthropic para LLMs acessarem ferramentas externas via subprocess (stdio).
Servidores MCP existem para filesystem, GitHub, Postgres, AWS, e centenas de
outros.

Vulpcode usa a lib oficial `mcp` para conectar e expor as tools via prefixo
`mcp__<server>__<tool>` no registry.

### 2. Configurar servidores

Em `~/.vulpcode/config.toml`:

```toml
[[mcp.servers]]
name = "filesystem"
command = "npx"
args = ["-y", "@modelcontextprotocol/server-filesystem", "/home/user/projects"]

[[mcp.servers]]
name = "github"
command = "npx"
args = ["-y", "@modelcontextprotocol/server-github"]
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }
```

A sintaxe `${VAR}` em `env` e expandida do environment do processo no momento
da inicializacao (`_resolve_env` em `loader.py`).

### 3. Como funciona

No startup do REPL:

1. `start_configured_servers(cfg)` itera por `cfg["mcp"]["servers"]`.
2. Para cada server, spawn via stdio (`mcp.client.stdio.stdio_client`).
3. `ClientSession.initialize()` faz handshake.
4. `session.list_tools()` retorna tools disponiveis.
5. Para cada tool, gera dinamicamente uma classe Python wrapping a chamada,
   registrando no `TOOL_REGISTRY` com nome qualificado.

### 4. Listar e debugar

```
> /mcp
       MCP servers
name        command  args
filesystem  npx      -y @modelcontextprotocol/server-filesystem /home/user/projects
github      npx      -y @modelcontextprotocol/server-github

       MCP tools
server      tools
filesystem  read_file, write_file, list_directory, ...
github      get_pr, list_issues, ...
```

Falhas de inicializacao sao logadas com `print` no stderr, mas o REPL continua
sem o servidor problematico — outros sao tentados.

### 5. Servidores populares

Tabela com server name + comando + descricao + link:

| Server                   | Comando                                                                | Descricao                       |
|--------------------------|------------------------------------------------------------------------|---------------------------------|
| `filesystem`             | `npx -y @modelcontextprotocol/server-filesystem <dir>`                 | Filesystem expandido            |
| `github`                 | `npx -y @modelcontextprotocol/server-github`                           | Issues, PRs, releases           |
| `gitlab`                 | `npx -y @modelcontextprotocol/server-gitlab`                           | GitLab equivalente              |
| `postgres`               | `npx -y @modelcontextprotocol/server-postgres <DSN>`                   | Query SQL                       |
| `slack`                  | `npx -y @modelcontextprotocol/server-slack`                            | Mensagens, canais               |
| `puppeteer`              | `npx -y @modelcontextprotocol/server-puppeteer`                        | Browser automation              |

Lista oficial: https://github.com/modelcontextprotocol/servers

### 6. Limitacoes atuais

- Schema de input das tools MCP usa Pydantic permissivo (`Any` para campos)
  — validacao mais leve que tools nativas.
- Sem suporte a OAuth flow (alguns servers exigem).
- Streaming de output das tools MCP nao e propagado — voce ve resultado
  completo de uma vez.

### 7. Adicionar/remover server

- Editar `~/.vulpcode/config.toml`
- Reiniciar o REPL (config so e lida no startup)

### 8. Escrever um servidor MCP customizado

Esta fora do escopo do vulpcode — siga a [documentacao oficial do
MCP](https://modelcontextprotocol.io/quickstart/server) usando o SDK Python
ou TypeScript.

---

## Atualizar `mkdocs.yml`

```yaml
- MCP: mcp/index.md
```

---

## INSTRUCAO CRITICA

- Use exemplos REAIS de comandos MCP (npx + pacote oficial).
- A nomenclatura das tools no registry e `mcp__<server>__<tool>` — confirme
  em `_make_tool_adapter`.
- O prefixo evita colisao com tools nativas (ex: `Read` vs `mcp__filesystem__read_file`).

---

## Etapas de Implementacao

### Etapa 1: Ler `mcp/client.py` e `mcp/loader.py`
### Etapa 2: Criar `mcp/index.md`
### Etapa 3: Atualizar `mkdocs.yml`
### Etapa 4: `mkdocs build`

---

## Criterios de Aceite

- [x] `docs/mcp/index.md` criado
- [x] Explicacao do que e MCP + link para spec oficial
- [x] Exemplo de config.toml com 2 servers
- [x] Fluxo de inicializacao explicado
- [x] `/mcp` comando documentado
- [x] Tabela de >=5 servidores populares com comandos npx
- [x] Limitacoes documentadas
- [x] `mkdocs.yml` atualizado
- [x] `mkdocs build` continua passando

---

**End of Specification**
