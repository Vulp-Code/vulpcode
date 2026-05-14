# Tarefa 04.03 - Providers OpenAI-Compatibles + Switching at Runtime

**Status**: PENDENTE
**Fase**: 04 - Providers
**Dependencias**: 04.02
**Bloqueia**: nada

---

## Objetivo

Criar 2 paginas:
- `providers/openai-family.md` — pagina unica cobrindo `openai`, `deepseek`,
  `groq`, `openrouter`, `lmstudio`, `vllm` (todos usam `OpenAIProvider`)
- `providers/switching-at-runtime.md` — uso de `/provider` e `/model`

---

## Arquivos a criar

- `docs/providers/openai-family.md`
- `docs/providers/switching-at-runtime.md`

---

## Source de verdade

- `src/vulpcode/providers/openai.py` — `OpenAIProvider`
- `src/vulpcode/providers/registry.py` — `OPENAI_COMPATIBLE_PRESETS`
- `src/vulpcode/commands/provider_model.py` — `ProviderCommand`, `ModelCommand`

---

## Conteudo de `openai-family.md`

### 1. Por que uma pagina so?

Os 6 providers `openai`, `deepseek`, `groq`, `openrouter`, `lmstudio`, `vllm`
usam a mesma classe `OpenAIProvider` por baixo, parametrizada com `base_url`.
A unica diferenca pratica e: URL, chave, e modelos suportados.

### 2. Tabela de presets

| Nome         | base_url default                            | Tem chave?              | Notas                          |
|--------------|---------------------------------------------|-------------------------|--------------------------------|
| `openai`     | (default do SDK, https://api.openai.com/v1) | sim — `OPENAI_API_KEY`  | Modelos GPT (gpt-4o, etc)      |
| `deepseek`   | https://api.deepseek.com/v1                 | sim — `DEEPSEEK_API_KEY`| Barato, bom em codigo          |
| `groq`       | https://api.groq.com/openai/v1              | sim — `GROQ_API_KEY`    | LPU custom, super rapido       |
| `openrouter` | https://openrouter.ai/api/v1                | sim — `OPENROUTER_API_KEY`| Acessa 100+ modelos via 1 chave|
| `lmstudio`   | http://localhost:1234/v1                    | nao                     | Servidor local LM Studio       |
| `vllm`       | http://localhost:8000/v1                    | opcional                | Inference server local         |

### 3. Setup por provider

Uma sub-secao por preset, mostrando 3 abas (env, config.toml, programatico)
seguindo o template da 04.02.

### 4. Override de base_url

Mostrar que `base_url` explicito sempre vence o preset:

```toml
[providers.deepseek]
api_key = "..."
base_url = "https://meu-proxy.com/v1"   # sobrescreve o preset oficial
```

Util para proxies corporativos que reescrevem chamadas.

### 5. Tool calling

Como funciona em OpenAI-style:
- Schema: `{"type": "function", "function": {"name", "description", "parameters"}}`
- Streaming: tool_calls fragmentos chegam por `index`, agregados ate `finish_reason`
- Nem todo backend suporta `stream_options` (LM Studio antigo ignora)

### 6. Notas por provider

- **DeepSeek**: bom custo-beneficio, modelo `deepseek-chat` para geral, `deepseek-coder` para codigo.
- **Groq**: rapido mas modelos as vezes nao suportam tool calling — checar.
- **OpenRouter**: meta-provider; pode rotear para Claude, GPT-4, modelos open source. Tool calling depende do modelo escolhido.
- **LM Studio**: instale o app, baixe um modelo, ative servidor (porta 1234). Nem todos os modelos suportam tools.
- **vLLM**: rode `vllm serve <model> --enable-auto-tool-choice` para ativar tools.

---

## Conteudo de `switching-at-runtime.md`

### 1. `/provider` — listar e trocar

Sem args:

```
> /provider
        Providers
name         active
anthropic    *
openai
gemini
...
current: AnthropicProvider
```

Com arg:

```
> /provider ollama
provider switched to ollama
```

Comportamento:
- Tenta `build_provider(name, repl.config['providers'][name])`
- Se faltar config, falha com erro vermelho
- Provider antigo e fechado (`aclose()`)
- Historico da conversa e PRESERVADO — so muda o backend

### 2. `/model` — listar e trocar

Sem args: chama `provider.list_models()` e tabula.

Com arg: `/model <name>` define `repl.agent.model`.

```
> /model gpt-4o
model set to gpt-4o
```

### 3. Compatibilidade do historico

O historico canonico (`Message`) e neutro. Quando voce troca de provider, a
proxima `provider.stream()` traduz tudo para o formato novo. Mas:

- **Tool calls antigos** podem usar nomes que o novo provider nao reconhece
  como tools (raramente um problema — o LLM ignora).
- **Mensagens role="tool"** com `tool_call_id` que o novo provider nao
  conhece: o Gemini ignora ids; OpenAI/Anthropic mantem mas nao "casam".
- Em casos extremos use `/clear` antes de trocar.

### 4. Cenarios praticos

- "Comecar com Claude (qualidade), terminar com Ollama (graca)" — `/provider ollama`
- "Testar mesma pergunta em 3 modelos" — `/save x`, `/provider y`, ..., `/load x`
- "Cair para offline" — `/provider ollama`

---

## Atualizar `mkdocs.yml`

As entradas ja foram adicionadas em 04.01. Nao mexer.

---

## INSTRUCAO CRITICA

- Reescreva a tabela de presets contra `OPENAI_COMPATIBLE_PRESETS` em registry.py.
- O comando `/provider` (sem args) usa o `provider.name` para marcar com `*`,
  nao `type(...).__name__`. Confira em `commands/provider_model.py`.
- Mencione que o REPL preserva historico ao trocar — o codigo confirma isso.

---

## Etapas de Implementacao

### Etapa 1: Ler `providers/openai.py`, `registry.py`, `commands/provider_model.py`
### Etapa 2: Criar `providers/openai-family.md`
### Etapa 3: Criar `providers/switching-at-runtime.md`
### Etapa 4: `mkdocs build`

---

## Criterios de Aceite

- [x] `docs/providers/openai-family.md` criado
- [x] Tabela de 6 presets com base_url, chave, notas
- [x] Sub-secao por preset (6 secoes) com 3 abas de setup
- [x] Mencao a override de base_url para proxies
- [x] Notas especificas por backend (DeepSeek, Groq, OpenRouter, LM Studio, vLLM)
- [x] `docs/providers/switching-at-runtime.md` criado
- [x] Documenta `/provider` e `/model` (com e sem args)
- [x] Discute compatibilidade de historico ao trocar
- [x] `mkdocs build` continua passando

---

**End of Specification**
