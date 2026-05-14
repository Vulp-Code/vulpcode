# MCP — Model Context Protocol

O **Model Context Protocol** ([modelcontextprotocol.io](https://modelcontextprotocol.io))
e um protocolo aberto, mantido pela Anthropic, para conectar LLMs a
ferramentas externas atraves de um subprocesso que fala JSON-RPC sobre
**stdio**. Existem servidores MCP prontos para filesystem, GitHub, GitLab,
Postgres, Slack, Puppeteer, AWS, Sentry, e [centenas de outros](https://github.com/modelcontextprotocol/servers).

O Vulpcode usa a [biblioteca oficial `mcp`](https://pypi.org/project/mcp/)
para falar com esses servidores. As tools expostas por cada server entram no
mesmo `TOOL_REGISTRY` das tools nativas, com nome qualificado
**`mcp__<server>__<tool>`** — o prefixo evita colisao com nomes nativos
(ex: `Read` vs `mcp__filesystem__read_file`).

> Source de verdade:
> [`src/vulpcode/mcp/`](https://github.com/vulpcode/vulpcode/tree/main/src/vulpcode/mcp/),
> com `client.py` (spawn + adapter) e `loader.py` (boot a partir do config).

---

## Configurar servidores

MCP servers sao declarados em
[`config.toml`](../configuration/config-toml.md#mcpservers) como uma lista
de tabelas `[[mcp.servers]]`. Cada entrada precisa pelo menos de `name` e
`command`; `args` e `env` sao opcionais.

```toml
# ~/.vulpcode/config.toml

# Filesystem expandido (Node)
[[mcp.servers]]
name = "filesystem"
command = "npx"
args = ["-y", "@modelcontextprotocol/server-filesystem", "/home/user/projects"]

# GitHub MCP, com token vindo do ambiente
[[mcp.servers]]
name = "github"
command = "npx"
args = ["-y", "@modelcontextprotocol/server-github"]
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }
```

A sintaxe `${VAR}` nos valores de `env` e expandida a partir do environment
do processo no momento da inicializacao — ver
[`_resolve_env`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/mcp/loader.py)
em `loader.py`. Variaveis ausentes viram string vazia.

| Chave     | Tipo        | Obrigatorio | Funcao                                              |
|-----------|-------------|-------------|-----------------------------------------------------|
| `name`    | str         | sim         | Identificador unico, vira prefixo das tools.        |
| `command` | str         | sim         | Executavel a lancar (ex: `npx`, `uvx`, path absoluto). |
| `args`    | list[str]   | nao         | Argumentos do comando. Default `[]`.                |
| `env`     | dict[str,str] | nao       | Vars adicionais; suporta `${VAR}`. Mesclado com `os.environ`. |

> Servidores sem `name` ou sem `command` sao ignorados silenciosamente pelo
> loader.

---

## Como funciona o boot

No startup do REPL ([`app.start_repl`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/app.py)),
logo apos a montagem do agente:

1. `start_configured_servers(cfg)` itera por `cfg["mcp"]["servers"]`.
2. Para cada server, `connect_mcp_server` lanca o processo via
   `mcp.client.stdio.stdio_client` com `StdioServerParameters(command, args, env)`.
3. `ClientSession.initialize()` faz o handshake MCP.
4. `session.list_tools()` retorna a lista de tools que o server oferece.
5. Para **cada** tool, `_make_tool_adapter` gera dinamicamente uma classe
   `Tool` que faz `session.call_tool(...)`, decora com `@tool(...)` e
   registra no `TOOL_REGISTRY` com o nome qualificado.
6. As classes geradas sao instanciadas e adicionadas em `agent.tools`,
   ficando indistinguiveis das tools nativas para o LLM.
7. No `finally` do REPL, `stop_servers()` fecha sessoes e subprocessos.

**Falhas de inicializacao** sao logadas no console como
`[mcp] failed to start <name>: <exc>` e o REPL **continua** sem o servidor
problematico — outros servers ainda sao tentados.

---

## Listar servers e tools — `/mcp`

Dentro do REPL:

```text
> /mcp
       MCP servers
+------------+---------+----------------------------------------------------------+
| name       | command | args                                                     |
+------------+---------+----------------------------------------------------------+
| filesystem | npx     | -y @modelcontextprotocol/server-filesystem /home/user/.. |
| github     | npx     | -y @modelcontextprotocol/server-github                   |
+------------+---------+----------------------------------------------------------+

       MCP tools
+------------+-----------------------------------------------+
| server     | tools                                         |
+------------+-----------------------------------------------+
| filesystem | read_file, write_file, list_directory, ...    |
| github     | get_pr, list_issues, ...                      |
+------------+-----------------------------------------------+
```

A primeira tabela vem direto de `config["mcp"]["servers"]`. A segunda so
aparece quando ha servers vivos no momento — a fonte e
`vulpcode.mcp.list_active_servers()`. Se nada estiver configurado, voce ve
`no MCP servers configured`.

Os mesmos nomes qualificados aparecem em [`/tools`](../user-guide/slash-commands.md#tools)
e podem ser referenciados em `permissions.always_allow_tools`.

[Mais detalhes do comando →](../user-guide/slash-commands.md#mcp)

---

## Servidores populares

Lista oficial mantida pela comunidade:
[github.com/modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers).

| Server       | Comando                                                      | Descricao                          |
|--------------|--------------------------------------------------------------|------------------------------------|
| `filesystem` | `npx -y @modelcontextprotocol/server-filesystem <dir>`       | Leitura/escrita em diretorios alem do CWD. |
| `github`     | `npx -y @modelcontextprotocol/server-github`                 | Issues, PRs, releases, search.     |
| `gitlab`     | `npx -y @modelcontextprotocol/server-gitlab`                 | Equivalente para GitLab.           |
| `postgres`   | `npx -y @modelcontextprotocol/server-postgres <DSN>`         | Query SQL em uma base Postgres.    |
| `slack`      | `npx -y @modelcontextprotocol/server-slack`                  | Mensagens, canais, threads.        |
| `puppeteer`  | `npx -y @modelcontextprotocol/server-puppeteer`              | Browser automation (headless Chrome). |
| `git`        | `uvx mcp-server-git --repository <path>`                     | Status, log, diff de um repo Git.  |
| `sqlite`     | `uvx mcp-server-sqlite --db-path <path>`                     | Query e schema de um arquivo `.sqlite`. |

> Servers em Node usam `npx -y <pacote>`; servers em Python sao tipicamente
> rodados via [`uvx`](https://docs.astral.sh/uv/guides/tools/) (`uv tool run`).

### Exemplo: stack tipica

```toml
[[mcp.servers]]
name = "filesystem"
command = "npx"
args = ["-y", "@modelcontextprotocol/server-filesystem", "/home/user/code"]

[[mcp.servers]]
name = "github"
command = "npx"
args = ["-y", "@modelcontextprotocol/server-github"]
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }

[[mcp.servers]]
name = "git"
command = "uvx"
args = ["mcp-server-git", "--repository", "/home/user/code/projeto-x"]
```

---

## Limitacoes atuais

- **Schemas de input permissivos.** O adapter constroi um modelo Pydantic a
  partir do `inputSchema` da tool, mas todos os campos viram `Any` —
  ver [`_input_model_from_schema`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/mcp/client.py).
  Validacao e mais leve que em tools nativas; o server e quem decide se o
  payload esta valido.
- **Sem OAuth.** Servers que exigem fluxo OAuth (alguns providers comerciais)
  nao sao suportados — apenas auth via env var (`${TOKEN}`) funciona.
- **Sem streaming.** O resultado da tool MCP e entregue de uma vez quando
  `session.call_tool` retorna; o output nao e propagado incrementalmente
  para o renderer.
- **Config so e lida no startup.** Adicionar/remover server requer
  reiniciar o REPL — nao ha hot-reload.
- **`requires_confirm=False` por padrao.** Tools MCP rodam sem prompt de
  confirmacao em modo `default`. Para forcar confirmacao, use modo
  [`safe`](../user-guide/permission-modes.md) ou block-list a tool em
  `permissions`.

---

## Adicionar/remover server

1. Edite `~/.vulpcode/config.toml` (ou o `.vulpcode/config.toml` do projeto).
2. Adicione/remova o bloco `[[mcp.servers]]`.
3. Reinicie o REPL (`Ctrl+D` ou `/quit`, depois `vulpcode`).
4. Confirme com `/mcp` que o server aparece e expoe as tools esperadas.

> **Atencao:** o `_deep_merge` do config **substitui** listas inteiras — se
> voce redefinir `[[mcp.servers]]` em um config de projeto, ele apaga a
> lista global. Use o config de projeto para a *uniao completa* dos servers
> que aquele projeto precisa.

---

## Escrever um servidor MCP customizado

Esta fora do escopo do Vulpcode — siga a
[documentacao oficial](https://modelcontextprotocol.io/quickstart/server),
que tem quickstarts em Python, TypeScript, Go e outras linguagens. Uma vez
publicado (ou rodando localmente), basta declarar em `[[mcp.servers]]`
apontando o `command` para o entrypoint.

---

## Veja tambem

- [Referencia de `[[mcp.servers]]`](../configuration/config-toml.md#mcpservers)
  — todas as chaves do bloco no `config.toml`.
- [Comando `/mcp`](../user-guide/slash-commands.md#mcp) — comportamento exato
  no REPL.
- [Tools](../tools/index.md) — onde tools MCP convivem com as nativas.
- [Modos de permissao](../user-guide/permission-modes.md) — como controlar
  o que o LLM pode chamar.
