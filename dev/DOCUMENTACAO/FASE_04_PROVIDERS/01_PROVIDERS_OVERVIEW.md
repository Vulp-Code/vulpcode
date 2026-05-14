# Tarefa 04.01 - Providers Overview

**Status**: PENDENTE
**Fase**: 04 - Providers
**Dependencias**: 03.03
**Bloqueia**: 04.02, 04.03, 04.04

---

## Objetivo

Criar `providers/index.md` com visao geral dos 10 providers, tabela comparativa
detalhada (suporte a tools, vision, streaming, custo, casos de uso), e link para
a pagina de cada um.

---

## Arquivos a criar

- `docs/providers/index.md`

---

## Source de verdade

- `src/vulpcode/providers/registry.py` — `_DEDICATED`, `OPENAI_COMPATIBLE_PRESETS`, `list_provider_names()`
- `src/vulpcode/providers/*.py` — cada provider
- `src/vulpcode/app.py` — `_default_model_for()` (default model por provider)

---

## Estrutura sugerida

### 1. Visao geral

Vulpcode tem 3 categorias de provider:

- **Dedicados**: classe propria por API (Anthropic, Gemini, Ollama, internal-llm)
- **OpenAI-compativeis**: `OpenAIProvider` parametrizada por `base_url` (OpenAI,
  DeepSeek, Groq, OpenRouter, LM Studio, vLLM)
- **Externos via MCP**: tools de servidores MCP entram com prefixo `mcp__<srv>__<name>`

### 2. Tabela comparativa

| Provider     | Categoria | Backend                                  | Tools | Vision | Streaming | Modelo default              |
|--------------|-----------|------------------------------------------|-------|--------|-----------|-----------------------------|
| `anthropic`  | dedicado  | Anthropic API                            | OK    | OK     | OK        | `claude-sonnet-4-6`         |
| `openai`     | OpenAI-c. | api.openai.com                           | OK    | OK     | OK        | `gpt-4o-mini`               |
| `gemini`     | dedicado  | Google AI Studio                         | OK    | OK     | OK        | `gemini-2.5-pro`            |
| `ollama`     | dedicado  | localhost:11434                          | OK    | OK     | OK        | `qwen2.5-coder:7b`          |
| `deepseek`   | OpenAI-c. | api.deepseek.com/v1                      | OK    | -      | OK        | `deepseek-chat`             |
| `groq`       | OpenAI-c. | api.groq.com/openai/v1                   | OK    | -      | OK        | `llama-3.1-70b-versatile`   |
| `openrouter` | OpenAI-c. | openrouter.ai/api/v1                     | OK    | -      | OK        | `openrouter/auto`           |
| `lmstudio`   | OpenAI-c. | localhost:1234/v1                        | depende | -    | OK        | `local-model`               |
| `vllm`       | OpenAI-c. | localhost:8000/v1                        | OK    | -      | OK        | `local-model`               |
| `internal-llm`| dedicado | URL configuravel                         | -     | -      | -         | `internal-llm`              |

### 3. Como escolher

Tabela de decisao por necessidade:

- **Melhor qualidade geral**: `anthropic` (Sonnet 4.6 / Opus 4.7)
- **Mais barato pago**: `deepseek` ou `groq`
- **Sem custo, offline**: `ollama` (qwen2.5-coder, deepseek-coder)
- **Multi-modelo via 1 chave**: `openrouter` (acessa centenas de modelos)
- **Privacidade total / dados sensiveis**: `ollama` ou `internal-llm`
- **Velocidade extrema**: `groq` (LPU custom)
- **Vision (analisar imagens)**: `anthropic`, `openai`, `gemini`, `ollama` (com llava)
- **Compliance corporativo**: `internal-llm` (passa por proxy interno)

### 4. Como configurar

3 caminhos, ordem de prioridade (do mais alto):

1. **Flag CLI**: `vulp --provider X --model Y`
2. **Env var**: `VULPCODE_PROVIDER`, `VULPCODE_MODEL`, `<PROVIDER>_API_KEY`
3. **`~/.vulpcode/config.toml`**: secao `[providers.<name>]`

Para detalhes, [Primeira configuracao](../getting-started/first-config.md).

### 5. Trocar provider em runtime

```
> /provider ollama
provider switched to ollama
> /model qwen2.5-coder:7b
model set to qwen2.5-coder:7b
```

[Detalhes →](switching-at-runtime.md)

### 6. Adicionar provider customizado

Veja [Adicionando provider](../contributing/add-provider.md) (FASE 11).

### 7. Paginas de cada provider

Cards/links para:
- [Anthropic (Claude)](anthropic.md)  — em 04.02
- [OpenAI e compatibles](openai-family.md) — em 04.03
- [Gemini](gemini.md) — em 04.02
- [Ollama](ollama.md) — em 04.02
- [Endpoint corporativo (internal-llm)](internal-llm.md) — em 04.04

---

## Atualizar `mkdocs.yml`

Adicionar secao `Providers`:

```yaml
nav:
  ...
  - Providers:
      - providers/index.md
      - Anthropic (Claude): providers/anthropic.md         # 04.02
      - OpenAI e compatibles: providers/openai-family.md   # 04.03
      - Gemini: providers/gemini.md                        # 04.02
      - Ollama: providers/ollama.md                        # 04.02
      - Endpoint corporativo: providers/internal-llm.md    # 04.04
      - Trocar em runtime: providers/switching-at-runtime.md  # 04.03
```

---

## INSTRUCAO CRITICA

- Confirmar a tabela contra `_DEDICATED`, `OPENAI_COMPATIBLE_PRESETS` em
  `registry.py` e `_default_model_for()` em `app.py`.
- Internal-llm declara `supports_tools=False` e `supports_vision=False` —
  honesta limitacao.
- LM Studio `tools` depende do modelo carregado — escrever "depende" na tabela.

---

## Etapas de Implementacao

### Etapa 1: Ler `registry.py` e `app.py`
### Etapa 2: Criar `providers/index.md`
### Etapa 3: Atualizar `mkdocs.yml`
### Etapa 4: `mkdocs build`

---

## Criterios de Aceite

- [x] `docs/providers/index.md` criado
- [x] Tabela com 10 providers e colunas: categoria, backend, tools, vision, streaming, modelo default
- [x] Secao "Como escolher" com >=6 cenarios mapeados a provider
- [x] Secao "Como configurar" com hierarquia (flag > env > config.toml)
- [x] Links para paginas individuais (que serao criadas nas tarefas seguintes)
- [x] `mkdocs.yml` atualizado com bloco `Providers`
- [x] `mkdocs build` continua passando

---

**End of Specification**
