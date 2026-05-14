# OpenAI e compatibles

**Classe:** `OpenAIProvider`
**Nomes no registry:** `"openai"`, `"deepseek"`, `"groq"`, `"openrouter"`, `"lmstudio"`, `"vllm"`
**Suporte:** ferramentas SIM · visao SIM (depende do modelo) · streaming SIM
**Codigo fonte:** [`src/vulpcode/providers/openai.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/providers/openai.py)
**Presets:** [`src/vulpcode/providers/registry.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/providers/registry.py)

Esta pagina cobre **seis** providers de uma so vez. Todos compartilham o mesmo
adapter — `OpenAIProvider` — e diferem apenas em URL, chave e modelos
suportados.

---

## Por que uma pagina so?

`openai`, `deepseek`, `groq`, `openrouter`, `lmstudio` e `vllm` falam o
**dialeto Chat Completions** da OpenAI (mesmo formato de mensagens, mesmo
schema de tools, mesmo streaming SSE). O Vulpcode trata isso de forma
literal: existe **uma unica classe** (`OpenAIProvider`) parametrizada com
`base_url`. O `registry.py` mantem um dicionario de presets para preencher
a URL automaticamente quando voce chama `build_provider("deepseek", ...)`:

```python
# src/vulpcode/providers/registry.py
OPENAI_COMPATIBLE_PRESETS: dict[str, str | None] = {
    "openai": None,
    "deepseek": "https://api.deepseek.com/v1",
    "groq": "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "lmstudio": "http://localhost:1234/v1",
    "vllm": "http://localhost:8000/v1",
}
```

Resultado: para adicionar suporte a um novo backend OpenAI-compatible,
basta um par `(nome, base_url)` aqui. Nenhuma logica nova de mensagens,
tools ou streaming precisa ser escrita.

---

## Tabela de presets

| Nome         | `base_url` default              | Chave                          | Notas                                                    |
|--------------|---------------------------------|--------------------------------|----------------------------------------------------------|
| `openai`     | (default do SDK)                | `OPENAI_API_KEY`               | Familia GPT (gpt-4o, gpt-4o-mini, o1, ...)               |
| `deepseek`   | `https://api.deepseek.com/v1`   | `DEEPSEEK_API_KEY`             | Barato, forte em codigo. `deepseek-chat`, `deepseek-coder`. |
| `groq`       | `https://api.groq.com/openai/v1`| `GROQ_API_KEY`                 | LPUs proprias — latencia muito baixa. Tools dependem do modelo. |
| `openrouter` | `https://openrouter.ai/api/v1`  | `OPENROUTER_API_KEY`           | Meta-provider; roteia para 100+ modelos com 1 unica chave. |
| `lmstudio`   | `http://localhost:1234/v1`      | nao usa                        | Servidor local da app LM Studio.                          |
| `vllm`       | `http://localhost:8000/v1`      | opcional                       | Servidor de inferencia local de alta vazao.               |

> O default da `openai` e `None` porque o SDK oficial ja conhece
> `https://api.openai.com/v1`. Quando voce nao setar `base_url`, o cliente
> usa esse endpoint.

---

## Setup por provider

### OpenAI

=== "Env var"

    ```bash
    export OPENAI_API_KEY=sk-...
    vulp --provider openai --model gpt-4o-mini
    ```

=== "config.toml"

    ```toml
    default_provider = "openai"
    default_model = "gpt-4o-mini"

    [providers.openai]
    api_key = "sk-..."
    # base_url e opcional; o SDK usa https://api.openai.com/v1 por default
    # base_url = "https://api.openai.com/v1"
    # timeout  = 120.0
    ```

=== "Programatico"

    ```python
    from vulpcode.providers import build_provider

    provider = build_provider("openai", {
        "api_key": "sk-...",
        "timeout": 120.0,
    })
    ```

---

### DeepSeek

=== "Env var"

    ```bash
    export DEEPSEEK_API_KEY=sk-...
    vulp --provider deepseek --model deepseek-chat
    ```

=== "config.toml"

    ```toml
    default_provider = "deepseek"
    default_model = "deepseek-chat"

    [providers.deepseek]
    api_key = "sk-..."
    # base_url default: https://api.deepseek.com/v1
    ```

=== "Programatico"

    ```python
    from vulpcode.providers import build_provider

    provider = build_provider("deepseek", {
        "api_key": "sk-...",
    })
    # build_provider preenche base_url=https://api.deepseek.com/v1 a partir do preset
    ```

---

### Groq

=== "Env var"

    ```bash
    export GROQ_API_KEY=gsk_...
    vulp --provider groq --model llama-3.1-70b-versatile
    ```

=== "config.toml"

    ```toml
    default_provider = "groq"
    default_model = "llama-3.1-70b-versatile"

    [providers.groq]
    api_key = "gsk_..."
    # base_url default: https://api.groq.com/openai/v1
    ```

=== "Programatico"

    ```python
    from vulpcode.providers import build_provider

    provider = build_provider("groq", {
        "api_key": "gsk_...",
    })
    ```

---

### OpenRouter

=== "Env var"

    ```bash
    export OPENROUTER_API_KEY=sk-or-...
    vulp --provider openrouter --model openrouter/auto
    ```

=== "config.toml"

    ```toml
    default_provider = "openrouter"
    default_model = "openrouter/auto"

    [providers.openrouter]
    api_key = "sk-or-..."
    # base_url default: https://openrouter.ai/api/v1
    ```

=== "Programatico"

    ```python
    from vulpcode.providers import build_provider

    provider = build_provider("openrouter", {
        "api_key": "sk-or-...",
    })
    ```

---

### LM Studio

LM Studio e uma app desktop (macOS/Windows/Linux) que carrega modelos
GGUF/GGML e expoe um servidor compativel com OpenAI. Antes de apontar o
Vulpcode, abra o LM Studio, baixe um modelo e ative o **Local Server**
(porta `1234` por default).

=== "Env var"

    ```bash
    # LM Studio nao exige chave; basta apontar o provider
    export VULPCODE_PROVIDER=lmstudio
    export VULPCODE_MODEL=local-model
    vulp
    ```

=== "config.toml"

    ```toml
    default_provider = "lmstudio"
    default_model = "local-model"   # o nome exato vem do que voce carregou na app

    [providers.lmstudio]
    # base_url default: http://localhost:1234/v1
    timeout = 300.0   # modelos locais costumam ser lentos no primeiro carregamento
    ```

=== "Programatico"

    ```python
    from vulpcode.providers import build_provider

    provider = build_provider("lmstudio", {
        "timeout": 300.0,
    })
    ```

---

### vLLM

[vLLM](https://docs.vllm.ai/) e um servidor de inferencia open source de
alta vazao. Para habilitar tool calling, suba o servidor com a flag
correspondente:

```bash
vllm serve Qwen/Qwen2.5-Coder-7B-Instruct \
    --enable-auto-tool-choice \
    --tool-call-parser hermes
```

=== "Env var"

    ```bash
    export VULPCODE_PROVIDER=vllm
    export VULPCODE_MODEL=Qwen/Qwen2.5-Coder-7B-Instruct
    vulp
    ```

=== "config.toml"

    ```toml
    default_provider = "vllm"
    default_model = "Qwen/Qwen2.5-Coder-7B-Instruct"

    [providers.vllm]
    # base_url default: http://localhost:8000/v1
    # api_key e opcional; alguns deploys de vLLM exigem token
    # api_key = "EMPTY"
    timeout = 300.0
    ```

=== "Programatico"

    ```python
    from vulpcode.providers import build_provider

    provider = build_provider("vllm", {
        "timeout": 300.0,
    })
    ```

---

## Override de `base_url`

O preset existe para conveniencia. Se voce setar `base_url` explicitamente
em `config.toml`, o valor explicito **sempre vence**:

```python
# src/vulpcode/providers/registry.py
if key in OPENAI_COMPATIBLE_PRESETS:
    preset = OPENAI_COMPATIBLE_PRESETS[key]
    if preset and not cfg.get("base_url"):
        cfg["base_url"] = preset
```

Isso e util principalmente para **proxies corporativos** que reescrevem
chamadas para o backend oficial:

```toml
[providers.deepseek]
api_key = "..."
base_url = "https://meu-proxy.empresa.com/deepseek/v1"   # vence o preset
```

Tambem da para usar um nome OpenAI-compat com um endpoint completamente
diferente — por exemplo, um servidor `vllm` rodando em uma maquina remota:

```toml
[providers.vllm]
base_url = "http://gpu-box.lab.local:8000/v1"
```

---

## Parametros do construtor

Construtor em `openai.py:22`:

| Parametro  | Tipo  | Default                      | Descricao                                                                         |
|------------|-------|------------------------------|-----------------------------------------------------------------------------------|
| `api_key`  | str   | `None` (`"EMPTY"` no cliente) | Chave da API. Quando ausente, o adapter passa `"EMPTY"` ao SDK — bom para servidores locais. |
| `base_url` | str   | `None`                       | Endpoint do backend. Sem valor, o SDK usa o default oficial da OpenAI.            |
| `timeout`  | float | `120.0`                      | Timeout do client (segundos). Aumente para backends locais lentos.                 |

`max_tokens`, `temperature` e companhia sao passados como `kwargs` para
`provider.stream(...)` ou via `[model_settings]` no `config.toml`.

---

## Tool calling no formato OpenAI

Tools canonicas viram o formato OpenAI Chat Completions:

```python
{
    "type": "function",
    "function": {
        "name": "...",
        "description": "...",
        "parameters": { ...JSON Schema... },
    },
}
```

A traducao acontece em `_tools_to_openai` (`openai.py:71`) — sem mistura
com argumentos canonicos. O Vulpcode envia tambem `tool_choice="auto"`
sempre que houver tools (`openai.py:107`), deixando o modelo decidir
quando chamar.

### Como o streaming agrega tool calls

Em OpenAI-style, **tool calls chegam fragmentadas**. Cada chunk traz
`delta.tool_calls[*]` com um campo `index` indicando qual chamada do
batch esta sendo construida. O provider mantem um buffer indexado por
`index`:

```python
# openai.py:131
for tc_chunk in delta.tool_calls:
    idx = tc_chunk.index
    slot = pending.setdefault(idx, {"id": "", "name": "", "args": ""})
    if tc_chunk.id:
        slot["id"] = tc_chunk.id
    if tc_chunk.function and tc_chunk.function.name:
        slot["name"] = tc_chunk.function.name
    if tc_chunk.function and tc_chunk.function.arguments:
        slot["args"] += tc_chunk.function.arguments
```

Quando chega `finish_reason in ("tool_calls", "stop", "length")`, o buffer
e flushado: cada slot vira um `StreamChunk(type="tool_call", ...)` com
`arguments` parseados como JSON. Se o JSON estiver malformado por algum
motivo, o provider emite `arguments={}` em vez de quebrar a sessao.

### `stream_options` e usage

O Vulpcode pede a contagem de tokens via:

```python
"stream_options": {"include_usage": True}
```

Backends modernos (OpenAI, DeepSeek, Groq, OpenRouter, vLLM recente)
respeitam o campo e mandam um chunk final com `chunk.usage`. **LM Studio
antigo** e algumas builds de `vllm` ignoram silenciosamente — voce ainda
recebe a resposta completa, so nao ve a linha de usage.

---

## Notas por backend

### DeepSeek

- Otimo custo/qualidade — costuma sair em torno de 1/10 do preco do GPT-4o.
- Modelos mais usados: `deepseek-chat` (geral), `deepseek-coder` (codigo).
- Tool calling estavel; visao **nao** suportada.

### Groq

- Hardware proprio (LPUs) — gera tokens absurdamente rapido.
- Tool calling **depende do modelo**. Modelos com sufixo `-tool-use` ou
  `-versatile` (ex.: `llama-3.1-70b-versatile`, `llama3-groq-70b-tool-use`)
  costumam suportar; outros podem ignorar tools silenciosamente.
- Visao nao suportada.

### OpenRouter

- E um **meta-provider**: voce escolhe o modelo destino (`openai/gpt-4o`,
  `anthropic/claude-sonnet-4-6`, `meta-llama/llama-3.1-70b-instruct`,
  `openrouter/auto`, ...) e o OpenRouter roteia.
- Suporte a tools, vision e streaming **depende do modelo escolhido**, nao
  do OpenRouter em si. Confira a [tabela de modelos](https://openrouter.ai/models)
  do projeto.
- Util para experimentar varios modelos sem abrir conta em cada provedor.

### LM Studio

- Instale a app em [lmstudio.ai](https://lmstudio.ai/), baixe um modelo
  GGUF, abra a aba **Developer** e clique **Start Server** (porta 1234).
- Tool calling **depende do modelo carregado**: alguns Qwen, Llama 3.1 e
  DeepSeek-Coder funcionam; modelos de chat puro podem ignorar `tools`.
- Sem chave de autenticacao por padrao — proteja a porta no firewall se
  rodar em rede compartilhada.

### vLLM

- Para tools funcionarem voce precisa **subir o servidor com flags
  especificas** ou cair em fallback de prompt:

    ```bash
    vllm serve <modelo> \
        --enable-auto-tool-choice \
        --tool-call-parser hermes  # ou llama3_json, mistral, ...
    ```

- O parser correto depende do template de chat do modelo. Veja a
  [documentacao oficial de tool calling do vLLM](https://docs.vllm.ai/en/latest/features/tool_calling.html).
- Suporta `api_key` opcional caso voce tenha posto um proxy autenticado
  na frente.

---

## Como funciona por baixo

`OpenAIProvider.stream()` (`openai.py:85`) chama
`client.chat.completions.create(...)` em modo streaming e converte cada
chunk SSE em um `StreamChunk` canonico:

| Campo do chunk OpenAI                          | StreamChunk emitido                         |
|------------------------------------------------|---------------------------------------------|
| `chunk.usage` (chunk final com `include_usage`)| `type="usage"` com input/output tokens      |
| `delta.content`                                | `type="text"` com `delta`                   |
| `delta.tool_calls[*]`                          | acumulado no buffer interno (sem emitir)    |
| `finish_reason in {tool_calls, stop, length}`  | flush do buffer -> N x `type="tool_call"`   |
| fim do stream                                  | `type="stop"`                               |

Mensagens com `tool_calls` (assistant) viram a estrutura nativa OpenAI:

```python
{
    "role": "assistant",
    "content": "...",
    "tool_calls": [
        {
            "id": "...",
            "type": "function",
            "function": {"name": "...", "arguments": "<JSON string>"},
        },
        ...
    ],
}
```

Respostas de tool (role `tool`) viram `{"role": "tool", "tool_call_id": ..., "content": ...}`.
A traducao esta em `_msg_to_openai` (`openai.py:46`).

Erros do SDK e da rede sao convertidos em `ProviderError` com a mensagem
original, para nao vazarem detalhes do `openai.AsyncOpenAI` ao agent
loop.

---

## Veja tambem

- [Trocar provider em runtime](switching-at-runtime.md) — `/provider` e `/model`
- [Anthropic (Claude)](anthropic.md)
- [Gemini](gemini.md)
- [Ollama](ollama.md)
- [Conceitos principais](../getting-started/core-concepts.md)
- [Visao geral dos providers](index.md)
