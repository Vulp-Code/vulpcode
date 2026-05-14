# Variaveis de ambiente

O Vulpcode reconhece um conjunto fixo de variaveis de ambiente. Elas sao
aplicadas apos os arquivos `config.toml` e antes das flags da CLI — ou seja,
**ganham do `config.toml`** mas **perdem para `--provider` / `--model`**.

> **Source of truth:** `ENV_MAP` em
> [`src/vulpcode/config.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/config.py).
> Se voce nao ve uma chave aqui, ela nao e lida — defina no `config.toml`.

---

## Tabela completa

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
| `TAVILY_API_KEY`          | (lido pela tool `WebSearch`)             | str  |

> `GOOGLE_API_KEY` e `GEMINI_API_KEY` apontam para o **mesmo destino**
> (`providers.gemini.api_key`). Se ambas estiverem definidas, a iteracao
> sobre `ENV_MAP` aplica `GOOGLE_API_KEY` por ultimo (ela vence). Em duvida,
> defina apenas uma.

> `TAVILY_API_KEY` **nao esta no `ENV_MAP`** — a tool `WebSearch` le
> diretamente do ambiente em
> [`tools/web.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/tools/web.py).
> Se ausente, `WebSearch` cai no backend DuckDuckGo (sem chave).

---

## Detalhe por variavel

### `VULPCODE_PROVIDER`

Define o provider default sem mexer no `config.toml`. Equivalente a setar
`default_provider` na raiz do TOML.

```bash
export VULPCODE_PROVIDER=openai
vulp
```

Valores aceitos: `anthropic`, `openai`, `gemini`, `deepseek`, `groq`,
`openrouter`, `ollama`, `lmstudio`, `vllm`, `internal-llm`.

### `VULPCODE_MODEL`

Sobrescreve o modelo default. Se nao definida, `app._default_model_for()`
escolhe um modelo sensato para o provider corrente.

```bash
export VULPCODE_PROVIDER=anthropic
export VULPCODE_MODEL=claude-opus-4-7
vulp
```

### Chaves de API por provider

Cada chave abaixo seta `providers.<nome>.api_key`. Sao a forma idiomatica
de carregar credenciais em CI/CD e em Docker.

| Variavel              | Provider                                                 |
|-----------------------|----------------------------------------------------------|
| `ANTHROPIC_API_KEY`   | Anthropic (Claude)                                       |
| `OPENAI_API_KEY`      | OpenAI                                                   |
| `GEMINI_API_KEY`      | Google Gemini                                            |
| `GOOGLE_API_KEY`      | Google Gemini (alias — mesmo destino)                    |
| `DEEPSEEK_API_KEY`    | DeepSeek (preset OpenAI-compativel)                      |
| `GROQ_API_KEY`        | Groq (preset OpenAI-compativel)                          |
| `OPENROUTER_API_KEY`  | OpenRouter (preset OpenAI-compativel)                    |

> **Sem chave para `ollama`, `lmstudio`, `vllm`:** sao locais e nao
> requerem credencial. Para customizar a URL, edite
> `[providers.<nome>] base_url` no `config.toml`.

### `INTERNAL_LLM_ENDPOINT` e `INTERNAL_LLM_USER_UUID`

Configuram o provider corporativo sem precisar de `config.toml`. Ambas sao
**obrigatorias** para que `internal-llm` funcione — sem elas, a primeira
chamada lanca `ProviderError`.

```bash
export VULPCODE_PROVIDER=internal-llm
export INTERNAL_LLM_ENDPOINT=http://example.corp/chatCompletion
export INTERNAL_LLM_USER_UUID=00000000-0000-0000-0000-000000000000
vulp
```

### `TAVILY_API_KEY`

Lida diretamente pela tool `WebSearch` (nao passa pelo `load_config`).
Habilita o backend Tavily, que retorna resultados estruturados; sem ela,
`WebSearch` usa DuckDuckGo.

```bash
export TAVILY_API_KEY=tvly-...
vulp -p "pesquise por novas releases do mkdocs material"
```

---

## Ordem entre env vars e o resto

```text
DEFAULTS  ->  ~/.vulpcode/config.toml  ->  <proj>/.vulpcode/config.toml
                                                   |
                                                   v
                                          variaveis de ambiente (ENV_MAP)
                                                   |
                                                   v
                                          flags da CLI (--provider, --model)
```

A iteracao sobre `ENV_MAP` so aplica a chave **se a env var estiver setada
e nao vazia** (`if val:`). Logo, exportar uma variavel vazia nao apaga o
valor que veio do `config.toml`.

---

## Boas praticas

- **CI/CD e producao:** prefira env vars (ou secrets do orquestrador) para
  passar chaves. Nada de credencial em arquivos versionados.
- **Desenvolvimento local:** use `~/.vulpcode/config.toml` (fora do repo) ou
  `<proj>/.vulpcode/config.toml` adicionado ao `.gitignore`.
- **Nunca commite chaves.** Adicione `.vulpcode/` ao `.gitignore` do projeto
  ou versione apenas um `config.example.toml` sem segredos.
- **Auditoria rapida** (mostra quais chaves de API estao setadas, sem expor
  o valor):

```bash
env | grep -E "API_KEY|UUID|VULPCODE_" | sed 's/=.*/=<set>/' | sort
```

- **Docker / shells** que ja exportam `GOOGLE_API_KEY` para outras
  ferramentas: consciente de que ela ira preencher `providers.gemini.api_key`
  no Vulpcode.

---

## Veja tambem

- [config.toml](config-toml.md) — equivalente em arquivo, com mais chaves.
- [Modos de permissao](../user-guide/permission-modes.md) — controle de
  execucao de tools.
- [Providers](../providers/index.md) — paginas dedicadas com setup
  passo-a-passo de cada provider.
