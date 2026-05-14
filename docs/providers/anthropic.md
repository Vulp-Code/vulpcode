# Anthropic Provider

**Classe:** `AnthropicProvider`
**Nome no registry:** `"anthropic"`
**Suporte:** ferramentas SIM · visao SIM · streaming SIM
**Codigo fonte:** [`src/vulpcode/providers/anthropic.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/providers/anthropic.py)

A familia Claude (Sonnet, Opus, Haiku) e o provider **default** do Vulpcode.
A integracao usa o SDK oficial `anthropic` em modo assincrono e fala diretamente
com `api.anthropic.com` via SSE.

---

## Setup rapido

=== "Env var"

    ```bash
    export ANTHROPIC_API_KEY=sk-ant-...
    vulp --provider anthropic --model claude-sonnet-4-6
    ```

=== "config.toml"

    ```toml
    default_provider = "anthropic"
    default_model = "claude-sonnet-4-6"

    [providers.anthropic]
    api_key = "sk-ant-..."
    # base_url e timeout sao opcionais
    # base_url = "https://api.anthropic.com"
    # timeout  = 120.0
    ```

=== "Programatico"

    ```python
    from vulpcode.providers import build_provider

    provider = build_provider("anthropic", {
        "api_key": "sk-ant-...",
        "timeout": 120.0,
    })
    ```

A chave pode vir de qualquer um dos tres canais — env var, `config.toml` ou
parametro direto. Veja a [tabela de precedencia](../getting-started/first-config.md).

---

## Parametros

Os parametros aceitos pelo construtor sao herdados de `Provider` e repassados
ao `AsyncAnthropic` do SDK oficial (veja `src/vulpcode/providers/anthropic.py:30`).

| Parametro    | Tipo   | Default                       | Descricao                                                              |
|--------------|--------|-------------------------------|------------------------------------------------------------------------|
| `api_key`    | str    | `None` (le `ANTHROPIC_API_KEY`) | Chave secreta da API.                                                  |
| `base_url`   | str    | `None` (usa `api.anthropic.com`) | Override util para proxies/observabilidade local.                      |
| `timeout`    | float  | `120.0`                        | Timeout global do client HTTP (segundos).                              |
| `max_tokens` | int    | `16384` (passado a `stream`)   | Maximo de tokens na resposta. Sonnet 4.6 aceita ate 64K. Vai como `kwargs`. |

`max_tokens` nao e parametro de construtor — voce passa em `kwargs` em
`provider.stream(...)` ou via `model_settings` no config:

```toml
[model_settings]
max_tokens = 32768
```

---

## Modelos disponiveis

`list_models()` retorna uma lista **curada** com os modelos atuais da familia
Claude 4.x:

```python
[
    "claude-opus-4-7",
    "claude-sonnet-4-6",
    "claude-haiku-4-5",
]
```

| Modelo               | Forte em                         | Notas                                       |
|----------------------|----------------------------------|---------------------------------------------|
| `claude-opus-4-7`    | Tarefas longas, raciocinio agentic | Mais caro; melhor escolha para refactors complexos. |
| `claude-sonnet-4-6`  | Equilibrio custo/qualidade       | Default recomendado. Suporta `max_tokens` ate 64K. |
| `claude-haiku-4-5`   | Velocidade, low-latency          | Bom para iteracoes rapidas em arquivos pequenos. |

Use o modelo via flag, env var ou `/model` no REPL:

```bash
vulp --provider anthropic --model claude-opus-4-7
```

---

## Notas e limitacoes

- **Tool calling nativo.** Tools sao traduzidas para o formato Anthropic
  `{name, description, input_schema}` (`anthropic.py:84`). O agent loop
  recebe os argumentos ja como `dict` Python.
- **Vision.** Imagens sao suportadas via `content` em formato lista. Veja a
  documentacao do [SDK Anthropic](https://docs.anthropic.com/) para o
  formato exato de blocos de imagem.
- **Cache de prompt.** O provider expoe `cache_read_tokens` e
  `cache_creation_tokens` via `Usage`. Ative o caching nas suas mensagens
  conforme [a documentacao da Anthropic](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching).
- **`stop_reason`** e capturado de `RawMessageDeltaEvent` e propagado no
  chunk final `type="stop"` — util para distinguir `end_turn`, `tool_use`,
  `max_tokens`, `stop_sequence`.

---

## Como funciona por baixo

O `stream()` (em `anthropic.py:97`) abre um contexto SSE com
`client.messages.stream(...)` e converte cada evento bruto da API em um
`StreamChunk` canonico:

| Evento Anthropic            | StreamChunk emitido                      |
|-----------------------------|------------------------------------------|
| `RawMessageStartEvent`      | `type="usage"` (input + cache tokens)    |
| `RawContentBlockDeltaEvent` (texto) | `type="text"` com `delta`           |
| `RawContentBlockStartEvent` (`tool_use`) | nada — abre buffer interno      |
| `RawContentBlockDeltaEvent` (`input_json_delta`) | nada — agrega JSON parcial |
| `RawContentBlockStopEvent`  | `type="tool_call"` com argumentos parseados |
| `RawMessageDeltaEvent`      | `type="usage"` (output_tokens) + captura `stop_reason` |
| fim do stream               | `type="stop"` com o `stop_reason` final  |

Os argumentos das tool calls chegam como **JSON streaming** (um delta por
chunk). O provider acumula em um buffer indexado pelo `index` do bloco e so
emite o `tool_call` ao receber `RawContentBlockStopEvent`. Se o JSON estiver
malformado por algum motivo, o provider emite `arguments={}` em vez de
quebrar a sessao.

Mensagens com `tool_calls` viram blocos `tool_use` no formato nativo;
respostas de tool (role `tool`) viram blocos `tool_result` correlacionados
por `tool_use_id`. A traducao esta em `_msg_to_anthropic` (`anthropic.py:55`).

---

## Veja tambem

- [Trocar provider em runtime](switching-at-runtime.md)
- [Conceitos principais](../getting-started/core-concepts.md)
- [Primeira configuracao](../getting-started/first-config.md)
- [Visao geral dos providers](index.md)
