# Tarefa 06.01 - Configuracao Detalhada (config.toml + env vars)

**Status**: PENDENTE
**Fase**: 06 - Configuracao
**Dependencias**: 05.03
**Bloqueia**: 06.02

---

## Objetivo

Criar 2 paginas:
- `configuration/index.md` — overview
- `configuration/config-toml.md` — referencia completa do config.toml
- `configuration/env-vars.md` — todas as env vars reconhecidas

---

## Arquivos a criar

- `docs/configuration/index.md`
- `docs/configuration/config-toml.md`
- `docs/configuration/env-vars.md`

---

## Source de verdade

- `src/vulpcode/config.py` — `DEFAULTS`, `ENV_MAP`, `load_config`
- `src/vulpcode/app.py` — uso da config no bootstrap

---

## Conteudo de `configuration/index.md`

Indice da secao. Resumo da hierarquia (1: defaults, 2: ~/.vulpcode/config.toml,
3: <projeto>/.vulpcode/config.toml, 4: env vars, 5: flags CLI). Diagrama de
prioridade. Links para as outras paginas.

---

## Conteudo de `configuration/config-toml.md`

Documentacao completa de todas as chaves do `DEFAULTS`. Estrutura:

```toml
# ━━━ Top-level ━━━
default_provider = "anthropic"      # nome do provider default
default_model = ""                  # se vazio, vulpcode usa _default_model_for(provider)

# ━━━ Por provider ━━━
[providers.anthropic]
api_key = "sk-ant-..."
base_url = "..."  # opcional
timeout = 120.0

[providers.openai]
api_key = "sk-..."
# ... idem

# ━━━ Configuracoes do modelo ━━━
[model_settings]
max_tokens = 16384

# ━━━ UI ━━━
[ui]
theme = "monokai"           # ou "default", "light"
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

# ━━━ MCP ━━━
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

Para cada secao explicar:
- Tipo de cada chave
- Default
- Exemplo realista
- Quando alterar

Cobrir TODAS as chaves do `DEFAULTS` em `config.py`. Conferir antes de fechar.

---

## Conteudo de `configuration/env-vars.md`

Tabela completa do `ENV_MAP`:

| Env var                   | Mapeia para (path no config)             | Tipo |
|---------------------------|------------------------------------------|------|
| `VULPCODE_PROVIDER`       | `default_provider`                       | str  |
| `VULPCODE_MODEL`          | `default_model`                          | str  |
| `ANTHROPIC_API_KEY`       | `providers.anthropic.api_key`            | str  |
| `OPENAI_API_KEY`          | `providers.openai.api_key`               | str  |
| `GEMINI_API_KEY`          | `providers.gemini.api_key`               | str  |
| `GOOGLE_API_KEY`          | `providers.gemini.api_key`               | str  |
| `DEEPSEEK_API_KEY`        | `providers.deepseek.api_key`             | str  |
| `GROQ_API_KEY`            | `providers.groq.api_key`                 | str  |
| `OPENROUTER_API_KEY`      | `providers.openrouter.api_key`           | str  |
| `INTERNAL_LLM_ENDPOINT`   | `providers.internal-llm.base_url`        | str  |
| `INTERNAL_LLM_USER_UUID`  | `providers.internal-llm.user_uuid`       | str  |
| `TAVILY_API_KEY`          | (lido pela tool WebSearch)               | str  |

Boas praticas:
- Use env vars para chaves em CI/CD
- Use config.toml local em desenvolvimento
- Nunca commite chaves
- Para auditar: `env | grep -E "API_KEY|UUID" | sed 's/=.*/=<set>/'`

---

## Atualizar `mkdocs.yml`

Adicionar bloco `Configuracao`:

```yaml
- Configuracao:
    - configuration/index.md
    - config.toml: configuration/config-toml.md
    - Variaveis de ambiente: configuration/env-vars.md
    - Permissoes (avancado): configuration/permissions.md   # 06.02
```

---

## INSTRUCAO CRITICA

- A lista de env vars DEVE bater com `ENV_MAP` em config.py — confira na hora.
- A estrutura do TOML deve refletir o que `load_config` retorna apos
  `_deep_merge(DEFAULTS, ...)`.
- Se houver chaves novas em DEFAULTS que voce nao reconhece, leia a logica
  associada antes de documentar.

---

## Etapas de Implementacao

### Etapa 1: Ler `config.py` (DEFAULTS, ENV_MAP, load_config)
### Etapa 2: Criar 3 arquivos
### Etapa 3: Atualizar `mkdocs.yml`
### Etapa 4: `mkdocs build`

---

## Criterios de Aceite

- [x] `docs/configuration/index.md` criado com diagrama da hierarquia
- [x] `docs/configuration/config-toml.md` cobre TODAS as chaves de DEFAULTS
- [x] `docs/configuration/env-vars.md` lista todas as env vars de ENV_MAP + TAVILY_API_KEY
- [x] Tabelas batem com source
- [x] `mkdocs.yml` atualizado
- [x] `mkdocs build` continua passando

---

**End of Specification**
