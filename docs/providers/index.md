# Providers

Vulpcode fala com modelos de linguagem por meio de **providers**. Cada provider
encapsula um backend (API SaaS, servidor local ou endpoint corporativo) e
expoe a mesma interface — converter mensagens, chamar tools, fazer streaming.
Trocar de provider e uma flag de CLI ou um `/provider` no REPL.

> **Onde mora isso no codigo?** As classes vivem em
> [`src/vulpcode/providers/`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/providers/),
> e o roteamento de nome -> classe e feito por
> [`registry.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/providers/registry.py).

---

## Categorias

Vulpcode tem 3 categorias de provider:

- **Dedicados** — uma classe propria por API, com mapeamento de mensagens,
  tools e streaming feito sob medida. Sao eles: `anthropic`, `gemini`,
  `ollama`, `internal-llm`.
- **OpenAI-compatibles** — todos sao instancias de `OpenAIProvider`,
  parametrizadas por `base_url`. Cobre `openai`, `deepseek`, `groq`,
  `openrouter`, `lmstudio`, `vllm`. Os presets de URL ficam em
  `OPENAI_COMPATIBLE_PRESETS`.
- **Externos via MCP** — nao sao providers no sentido estrito; sao tools
  vindas de servidores [MCP](https://modelcontextprotocol.io/) que entram no
  agente com prefixo `mcp__<servidor>__<nome>`. Veja
  [Slash commands -> /mcp](../user-guide/slash-commands.md).

---

## Tabela comparativa

| Provider       | Categoria       | Backend                        | Tools     | Vision | Streaming | Modelo default              |
| -------------- | --------------- | ------------------------------ | --------- | ------ | --------- | --------------------------- |
| `anthropic`    | dedicado        | `api.anthropic.com`            | OK        | OK     | OK        | `claude-sonnet-4-6`         |
| `openai`       | OpenAI-compat.  | `api.openai.com`               | OK        | OK     | OK        | `gpt-4o-mini`               |
| `gemini`       | dedicado        | Google AI Studio               | OK        | OK     | OK        | `gemini-2.5-pro`            |
| `ollama`       | dedicado        | `localhost:11434`              | OK        | OK     | OK        | `qwen2.5-coder:7b`          |
| `deepseek`     | OpenAI-compat.  | `api.deepseek.com/v1`          | OK        | -      | OK        | `deepseek-chat`             |
| `groq`         | OpenAI-compat.  | `api.groq.com/openai/v1`       | OK        | -      | OK        | `llama-3.1-70b-versatile`   |
| `openrouter`   | OpenAI-compat.  | `openrouter.ai/api/v1`         | OK        | -      | OK        | `openrouter/auto`           |
| `lmstudio`     | OpenAI-compat.  | `localhost:1234/v1`            | depende   | -      | OK        | `local-model`               |
| `vllm`         | OpenAI-compat.  | `localhost:8000/v1`            | OK        | -      | OK        | `local-model`               |
| `internal-llm` | dedicado        | URL configuravel               | -         | -      | -         | `internal-llm`              |

> "depende" em `lmstudio` significa que o suporte a tools vem do **modelo
> carregado** dentro do LM Studio, nao do provider — o cliente OpenAI envia
> as tools normalmente, mas o servidor pode ignora-las.
>
> `internal-llm` declara `supports_tools=False` e `supports_vision=False`
> (veja
> [`internal_llm.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/providers/internal_llm.py)).
> O endpoint retorna o texto inteiro de uma vez — sem streaming.

---

## Como escolher

Mapa de decisao por necessidade:

| Cenario                                       | Provider recomendado                                   |
| --------------------------------------------- | ------------------------------------------------------ |
| Melhor qualidade geral em codigo              | `anthropic` (Sonnet 4.6 / Opus 4.7)                    |
| Mais barato pago, ainda assim com tools       | `deepseek` ou `groq`                                   |
| Velocidade extrema (LPUs)                     | `groq`                                                 |
| Sem custo por token, totalmente offline       | `ollama` (`qwen2.5-coder`, `deepseek-coder`)           |
| Multiplos modelos com 1 unica chave           | `openrouter`                                           |
| Privacidade total / dados sensiveis           | `ollama` (local) ou `internal-llm` (proxy interno)     |
| Vision (analisar imagens)                     | `anthropic`, `openai`, `gemini`, `ollama` (com `llava`) |
| Compliance corporativo / proxy interno        | `internal-llm`                                         |
| Servir um modelo open-source com alta vazao   | `vllm`                                                 |
| Experimentacao local com UI grafica           | `lmstudio`                                             |

Em duvida? Comece com `anthropic` (default do projeto) e troque depois com
`/provider` se quiser comparar.

---

## Como configurar

Tres caminhos, em ordem de prioridade (do mais alto para o mais baixo):

1. **Flag CLI** — sobrepoe tudo:

    ```bash
    vulp --provider ollama --model qwen2.5-coder:7b
    ```

2. **Variavel de ambiente** — uma camada acima do config persistido:

    ```bash
    export VULPCODE_PROVIDER=deepseek
    export VULPCODE_MODEL=deepseek-chat
    export DEEPSEEK_API_KEY=sk-...
    vulp
    ```

    Cada provider que precisa de chave usa o prefixo correspondente:
    `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`,
    `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `GEMINI_API_KEY`. O
    `internal-llm` usa `INTERNAL_LLM_ENDPOINT` e `INTERNAL_LLM_USER_UUID`.

3. **`~/.vulpcode/config.toml`** — base persistida do usuario:

    ```toml
    default_provider = "anthropic"
    default_model = "claude-sonnet-4-6"

    [providers.anthropic]
    api_key = "sk-ant-..."

    [providers.ollama]
    base_url = "http://localhost:11434"
    ```

Detalhes em
[Primeira configuracao](../getting-started/first-config.md).

---

## Trocar provider em runtime

Dentro do REPL, sem reiniciar:

```text
> /provider ollama
provider switched to ollama
> /model qwen2.5-coder:7b
model set to qwen2.5-coder:7b
```

A sessao continua — o historico de mensagens e preservado, mesmo com modelo
e provider novos. [Detalhes ->](switching-at-runtime.md)

---

## Adicionar um provider customizado

Se o seu backend nao se encaixa em nenhuma das categorias acima (e nem
mesmo via OpenAI-compatible), implemente uma subclasse de `Provider` e
registre em `_DEDICATED`. Veja
[Adicionando provider](../contributing/add-provider.md) (FASE 11).

---

## Paginas de cada provider

- [Anthropic (Claude)](anthropic.md) — Sonnet, Opus, Haiku
- [OpenAI e compatibles](openai-family.md) — `openai`, `deepseek`, `groq`, `openrouter`, `lmstudio`, `vllm`
- [Gemini](gemini.md) — Google AI Studio
- [Ollama](ollama.md) — modelos locais, sem custo
- [Endpoint corporativo (internal-llm)](internal-llm.md) — proxy interno
- [Trocar em runtime](switching-at-runtime.md) — `/provider` e `/model`
