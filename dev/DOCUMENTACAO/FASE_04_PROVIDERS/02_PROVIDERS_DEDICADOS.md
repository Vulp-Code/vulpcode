# Tarefa 04.02 - Providers Dedicados (Anthropic, Gemini, Ollama)

**Status**: PENDENTE
**Fase**: 04 - Providers
**Dependencias**: 04.01
**Bloqueia**: nada

---

## Objetivo

Criar uma pagina por provider dedicado: `providers/anthropic.md`,
`providers/gemini.md`, `providers/ollama.md`. Cada uma cobre: setup, env vars,
exemplos config.toml, chamada programatica, modelos suportados, limitacoes.

---

## Arquivos a criar

- `docs/providers/anthropic.md`
- `docs/providers/gemini.md`
- `docs/providers/ollama.md`

---

## Source de verdade

- `src/vulpcode/providers/anthropic.py` — `AnthropicProvider`
- `src/vulpcode/providers/gemini.py` — `GeminiProvider`
- `src/vulpcode/providers/ollama.py` — `OllamaProvider`
- `src/vulpcode/config.py` — env vars

---

## Template para cada provider

Toda pagina segue a mesma estrutura:

````markdown
# <Nome> Provider

**Classe:** `<NomeProvider>`
**Nome no registry:** `"<nome>"`
**Suporte:** ferramentas <X> · visao <X> · streaming <X>

## Setup rapido

=== "Env var"

    ```bash
    export <ENV_VAR>=<placeholder>
    vulp --provider <nome>
    ```

=== "config.toml"

    ```toml
    default_provider = "<nome>"
    default_model = "<modelo-default>"

    [providers.<nome>]
    api_key = "<placeholder>"
    ```

=== "Programatico"

    ```python
    from vulpcode.providers import build_provider
    provider = build_provider("<nome>", {"api_key": "..."})
    ```

## Parametros

| Parametro  | Tipo    | Default | Descricao |
|------------|---------|---------|-----------|
| `api_key`  | str     | None    | ...       |
| `base_url` | str     | None    | ...       |
| `timeout`  | float   | 120.0   | ...       |

## Modelos disponiveis

(`list_models()` retorna; ou lista hardcoded; ou via API).

## Notas e limitacoes

- ...

## Como funciona por baixo

(Explica resumidamente que tipos de eventos sao emitidos, como tool calls sao
agregados, etc.)

## Veja tambem

- [Trocar provider em runtime](switching-at-runtime.md)
- [Conceitos principais](../getting-started/core-concepts.md)
````

---

## Conteudo especifico — Anthropic

- Classe: `AnthropicProvider`
- Env: `ANTHROPIC_API_KEY`, modelos via `list_models()` (curated: opus-4-7,
  sonnet-4-6, haiku-4-5)
- Streaming: SSE via `client.messages.stream()`
- `max_tokens` configuravel (default 16384, suporta ate 64K em sonnet 4.6)
- Tool calling nativo (formato `{name, description, input_schema}`)
- Vision: SIM (passa imagens em `content` lista)
- Notas: input_tokens reportados via `RawMessageStartEvent`, stop_reason via
  `RawMessageDeltaEvent`

---

## Conteudo especifico — Gemini

- Classe: `GeminiProvider`
- Env: `GEMINI_API_KEY` ou `GOOGLE_API_KEY` (ambos funcionam)
- SDK: `google-genai`
- Streaming: `client.aio.models.generate_content_stream(...)`
- Tool calling via `function_declarations`
- ATENCAO: Gemini correlaciona tool calls por `name`, nao por `id`. O agent
  loop seta `Message.name` para a tool result.
- Tool call ids sao sintetizados (`gemini_<hex>`)
- Vision: SIM
- Notas: `system` vai como `system_instruction`, NAO como mensagem em contents

---

## Conteudo especifico — Ollama

- Classe: `OllamaProvider`
- Sem chave (servidor local)
- `base_url` default: `http://localhost:11434`
- Timeout default maior (300s) — modelos locais sao lentos
- API: POST `/api/chat` com NDJSON streaming
- Tool calling: depende do modelo (qwen2.5-coder, llama3.1, mistral funcionam)
- `arguments` pode chegar como string JSON ou dict — provider trata ambos
- Tool call ids sintetizados (`ollama_<hex>`)
- `list_models()` consulta `/api/tags`
- Notas: instalar Ollama localmente (`curl https://ollama.com/install.sh | sh`),
  depois `ollama pull <modelo>`

---

## Atualizar `mkdocs.yml`

As 3 entradas (`Anthropic`, `Gemini`, `Ollama`) ja foram adicionadas em 04.01.
Nao mexer.

---

## INSTRUCAO CRITICA

- Cada pagina deve ter pelo menos uma referencia ao codigo fonte (linha ou
  classe), ex: "ver `src/vulpcode/providers/anthropic.py`".
- Use placeholders para chaves: `sk-ant-...`, `AIza...`, etc. NUNCA chaves reais.
- Para Gemini, deixe claro o caso especial do `tool_call_id` — usuarios que
  queiram estender ou debugar precisam entender.

---

## Etapas de Implementacao

### Etapa 1: Ler os 3 arquivos source
### Etapa 2: Criar `providers/anthropic.md`
### Etapa 3: Criar `providers/gemini.md`
### Etapa 4: Criar `providers/ollama.md`
### Etapa 5: `mkdocs build`

---

## Criterios de Aceite

- [x] `docs/providers/anthropic.md` criado seguindo o template + secao Anthropic-especifica
- [x] `docs/providers/gemini.md` criado com nota sobre `tool_call_id` por nome
- [x] `docs/providers/ollama.md` criado com instrucao de instalar Ollama
- [x] Todas as 3 paginas tem 3 abas de setup (env, config.toml, programatico)
- [x] Todas tem tabela de parametros
- [x] Todas tem secao "Como funciona por baixo"
- [x] `mkdocs build` continua passando

---

## Riscos

| Risco | Mitigacao |
|-------|-----------|
| Nome do env var divergir | Conferir `ENV_MAP` em config.py |
| `list_models()` falhar para Gemini | Documentar fallback (gemini-2.0-flash, gemini-2.5-pro) |
| Ollama nao instalado no maquina do usuario | Instrucao explicita de install |

---

**End of Specification**
