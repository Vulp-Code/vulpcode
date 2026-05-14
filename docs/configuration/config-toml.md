# Referencia de `config.toml`

Esta pagina lista **todas** as chaves reconhecidas pelo `config.toml`, na
mesma estrutura que `vulpcode.config.DEFAULTS` produz apos o `_deep_merge`.

> **Onde fica:** `~/.vulpcode/config.toml` (global) e/ou
> `<projeto>/.vulpcode/config.toml` (projeto). A descoberta sobe a arvore de
> diretorios — a primeira pasta com `.vulpcode/config.toml` vence.
>
> **Source of truth:** `DEFAULTS` em
> [`src/vulpcode/config.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/config.py).

---

## Estrutura completa (anotada)

```toml
# ━━━ Top-level ━━━
default_provider = "anthropic"      # nome do provider default
default_model = ""                  # se vazio, vulpcode usa _default_model_for(provider)

# ━━━ Por provider ━━━
[providers.anthropic]
api_key = "sk-ant-..."
# base_url = "https://api.anthropic.com"   # opcional
# timeout  = 120.0

[providers.openai]
api_key = "sk-..."
# base_url = "https://api.openai.com/v1"   # opcional
# timeout  = 120.0

[providers.gemini]
api_key = "..."

[providers.deepseek]
api_key = "sk-..."
# base_url default = "https://api.deepseek.com/v1"

[providers.groq]
api_key = "gsk_..."
# base_url default = "https://api.groq.com/openai/v1"

[providers.openrouter]
api_key = "sk-or-..."
# base_url default = "https://openrouter.ai/api/v1"

[providers.ollama]
# base_url = "http://localhost:11434"

[providers.lmstudio]
# base_url default = "http://localhost:1234/v1"

[providers.vllm]
# base_url default = "http://localhost:8000/v1"

[providers."internal-llm"]
base_url   = "http://example.corp/chatCompletion"
user_uuid  = "00000000-0000-0000-0000-000000000000"
# timeout     = 120.0
# max_retries = 3
# retry_delay = 5.0

# ━━━ Configuracoes do modelo ━━━
[model_settings]
max_tokens = 16384

# ━━━ UI ━━━
[ui]
theme = "monokai"           # "default", "monokai" ou "light"
show_token_usage = true

# ━━━ Permissoes ━━━
[permissions]
auto_approve_read = true
auto_approve_glob = true
auto_approve_grep = true
require_confirm_bash = true
require_confirm_write = true
require_confirm_edit = true
always_allow_tools = ["Read", "Glob", "Grep"]

# ━━━ MCP (servers externos) ━━━
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

---

## Top-level

| Chave              | Tipo  | Default      | Descricao |
|--------------------|-------|--------------|-----------|
| `default_provider` | str   | `"anthropic"` | Nome do provider default. Aceita os nomes registrados em [`OPENAI_COMPATIBLE_PRESETS` / `_DEDICATED`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/providers/registry.py): `anthropic`, `openai`, `gemini`, `deepseek`, `groq`, `openrouter`, `ollama`, `lmstudio`, `vllm`, `internal-llm`. |
| `default_model`    | str   | `""`         | Modelo default. Se vazio, `_default_model_for(provider_name)` em `app.py` escolhe um sensato (ex.: `claude-sonnet-4-6` para Anthropic, `gpt-4o-mini` para OpenAI). |

**Quando alterar:** sempre que voce trabalha consistentemente com um provider
ou modelo diferente do default. Para um override pontual, prefira as flags
`--provider` / `--model` na CLI.

---

## `[providers.<nome>]`

Cada subchave de `providers` e o nome do provider. As tres chaves
universais sao herdadas de `Provider.__init__` em
[`providers/base.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/providers/base.py):

| Chave      | Tipo  | Default | Descricao |
|------------|-------|---------|-----------|
| `api_key`  | str   | `None`  | Chave de API. Se ausente, o provider tenta a env var equivalente (ex.: `ANTHROPIC_API_KEY`). |
| `base_url` | str   | `None`  | Override de endpoint. Para os presets OpenAI-compativeis (`deepseek`, `groq`, `openrouter`, `lmstudio`, `vllm`), o registry preenche automaticamente — voce so seta para apontar a um proxy/observabilidade local. |
| `timeout`  | float | `120.0` | Timeout do client HTTP em segundos. |

> **Default model:** o `default_model` global e usado para todos os providers.
> Se voce alternar de provider sem trocar tambem o modelo, o
> `_default_model_for()` cobre.

### Especifico do `[providers."internal-llm"]`

O provider corporativo aceita extras alem das tres chaves universais (veja
[`providers/internal_llm.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/providers/internal_llm.py)):

| Chave         | Tipo  | Default | Descricao |
|---------------|-------|---------|-----------|
| `base_url`    | str   | (obrigatorio) | URL completa do endpoint `/chatCompletion`. |
| `user_uuid`   | str   | (obrigatorio) | Vai no header `user-uuid` em cada request. |
| `timeout`     | float | `120.0` | Timeout do cliente `httpx`. |
| `max_retries` | int   | `3`     | Tentativas em caso de erro de rede/HTTP 5xx/`data=null`. |
| `retry_delay` | float | `5.0`   | Atraso base (s); o backoff e `retry_delay * (attempt + 1)`. |

> O nome `internal-llm` contem hifen, entao no TOML ele precisa ficar entre
> aspas: `[providers."internal-llm"]`.

**Quando alterar:** ao integrar com um endpoint corporativo proprio. Veja a
pagina [Endpoint corporativo](../providers/internal-llm.md) para o setup
completo.

---

## `[model_settings]`

Argumentos passados como `kwargs` para `provider.stream(...)`. O agente
faz `kwargs.update(model_settings)` em cada turno.

| Chave        | Tipo | Default | Descricao |
|--------------|------|---------|-----------|
| `max_tokens` | int  | `16384` | Limite de tokens da resposta. Sonnet 4.6 aceita ate 64K, GPT-4o aceita ate 16K, etc. — verifique o limite do modelo antes de subir. |

**Quando alterar:** se as respostas estao sendo cortadas (resposta longa) ou
se voce quer reduzir custo limitando o tamanho.

> Outras chaves (ex.: `temperature`, `top_p`) tambem sao aceitas e repassadas
> ao provider — o `DEFAULTS` lista somente `max_tokens`, mas qualquer chave
> em `[model_settings]` vira `kwargs` no `stream()`.

---

## `[ui]`

Configuracao do renderizador Rich. Veja
[`ui/theme.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/ui/theme.py).

| Chave              | Tipo | Default      | Descricao |
|--------------------|------|--------------|-----------|
| `theme`            | str  | `"monokai"`  | Tema visual. Valores aceitos: `"default"`, `"monokai"`, `"light"`. Qualquer outro nome cai no `"default"`. |
| `show_token_usage` | bool | `true`       | Mostra o contador de tokens (input/output/cache) ao final de cada turno. |

**Quando alterar:** trocar o tema se voce usa terminal claro (`light`) ou se
o realce padrao do `monokai` colide com sua paleta.

---

## `[permissions]`

Controla o que precisa de confirmacao antes de executar. Aplicado em
[`permissions.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/permissions.py).

| Chave                    | Tipo      | Default | Descricao |
|--------------------------|-----------|---------|-----------|
| `auto_approve_read`      | bool      | `true`  | Aprova automaticamente a tool `Read`. |
| `auto_approve_glob`      | bool      | `true`  | Aprova automaticamente a tool `Glob`. |
| `auto_approve_grep`      | bool      | `true`  | Aprova automaticamente a tool `Grep`. |
| `require_confirm_bash`   | bool      | `true`  | Pede confirmacao antes de cada `Bash`. |
| `require_confirm_write`  | bool      | `true`  | Pede confirmacao antes de `Write`. |
| `require_confirm_edit`   | bool      | `true`  | Pede confirmacao antes de `Edit`. |
| `always_allow_tools`     | list[str] | `[]`    | Whitelist persistente de tools que nunca pedem confirmacao na sessao. Use os nomes registrados (`Read`, `Glob`, `Grep`, `Bash`, `Write`, `Edit`, `WebSearch`, ...). |

> A flag de modo na CLI sobrescreve estas chaves quase sempre: `--auto`
> aprova tudo, `--safe` pede confirmacao em tudo (mesmo nas tools acima),
> `--plan` recusa qualquer execucao. Veja
> [Modos de permissao](../user-guide/permission-modes.md).

**Quando alterar:** afrouxar (`require_confirm_bash = false`) em uma sessao
controlada onde voce confia nos comandos; reforcar adicionando nomes a
`always_allow_tools` para evitar prompts repetidos.

---

## `[[mcp.servers]]`

Lista de **MCP servers** lancados como subprocesso ao iniciar o REPL. Cada
entrada vai para `start_configured_servers()` em
[`mcp/loader.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/mcp/loader.py).

| Chave     | Tipo               | Obrigatorio | Descricao |
|-----------|--------------------|-------------|-----------|
| `name`    | str                | sim         | Identificador unico. As tools expostas pelo servidor sao registradas como `mcp__<name>__<tool>`. |
| `command` | str                | sim         | Executavel a lancar (ex.: `npx`, `uvx`, caminho absoluto). |
| `args`    | list[str]          | nao         | Lista de argumentos. Default `[]`. |
| `env`     | table (str -> str) | nao         | Vars de ambiente injetadas no subprocesso. Valores em `${VAR}` sao expandidos a partir do ambiente do processo `vulp` (`_resolve_env`). |

Exemplos:

```toml
# Servidor de filesystem (Node)
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

**Quando alterar:** sempre que voce quer expor um servidor MCP novo. Servers
sem `name` ou sem `command` sao silenciosamente ignorados pelo loader.

---

## Como `load_config` resolve as camadas

O algoritmo, simplificado:

```python
cfg = copy.deepcopy(DEFAULTS)
cfg = _deep_merge(cfg, _load_toml("~/.vulpcode/config.toml"))
cfg = _deep_merge(cfg, _load_toml("<proj>/.vulpcode/config.toml"))

for env_var, path in ENV_MAP.items():
    if val := os.environ.get(env_var):
        _set_path(cfg, path, val)

cfg = _deep_merge(cfg, cli_overrides)
```

- `_deep_merge`: recursivo para dicts; **listas sao substituidas, nao
  concatenadas**. Logo, redefinir `[[mcp.servers]]` no projeto substitui
  inteiramente a lista do global.
- `_set_path`: cria sub-tabelas faltantes ao posicionar o valor da env var.

---

## Veja tambem

- [Variaveis de ambiente](env-vars.md) — atalhos do `ENV_MAP`.
- [Modos de permissao](../user-guide/permission-modes.md) — visao geral
  dos modos e da chave `[permissions]`.
- [Providers](../providers/index.md) — chaves especificas de cada provider.
- [Primeira configuracao](../getting-started/first-config.md) — tutorial.
