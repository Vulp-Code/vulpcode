# Gemini Provider

**Classe:** `GeminiProvider`
**Nome no registry:** `"gemini"`
**Suporte:** ferramentas SIM · visao SIM · streaming SIM
**Codigo fonte:** [`src/vulpcode/providers/gemini.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/providers/gemini.py)

Provider para a familia **Gemini** do Google AI Studio (Flash, Pro). A
integracao usa o SDK oficial [`google-genai`](https://pypi.org/project/google-genai/)
em modo `aio` (async) e fala diretamente com o endpoint do Google.

---

## Setup rapido

=== "Env var"

    ```bash
    # ANTERIOR ou GOOGLE_API_KEY funcionam — os dois mapeiam para o mesmo lugar
    export GEMINI_API_KEY=AIza...
    vulp --provider gemini --model gemini-2.5-pro
    ```

=== "config.toml"

    ```toml
    default_provider = "gemini"
    default_model = "gemini-2.5-pro"

    [providers.gemini]
    api_key = "AIza..."
    # base_url e timeout sao opcionais (o SDK aceita os defaults do Google)
    # timeout = 120.0
    ```

=== "Programatico"

    ```python
    from vulpcode.providers import build_provider

    provider = build_provider("gemini", {
        "api_key": "AIza...",
        "timeout": 120.0,
    })
    ```

Tanto `GEMINI_API_KEY` quanto `GOOGLE_API_KEY` apontam para o mesmo destino
em `ENV_MAP` (`src/vulpcode/config.py:38`) — basta uma das duas estar
definida.

---

## Parametros

Construtor em `gemini.py:23`:

| Parametro  | Tipo  | Default | Descricao                                                 |
|------------|-------|---------|-----------------------------------------------------------|
| `api_key`  | str   | `None`  | Chave do Google AI Studio. Le `GEMINI_API_KEY`/`GOOGLE_API_KEY`. |
| `base_url` | str   | `None`  | Aceito por compatibilidade. O SDK `google-genai` usa o endpoint do Google por padrao. |
| `timeout`  | float | `120.0` | Timeout do client (segundos).                             |

`max_tokens`, `temperature` e companhia podem ser passados como `kwargs`
para `provider.stream(...)` se necessario.

---

## Modelos disponiveis

`list_models()` (em `gemini.py:151`) consulta a API com
`client.aio.models.list()`. Quando a chamada falha (offline, chave invalida,
quota), a funcao tem **fallback hardcoded**:

```python
[
    "gemini-2.0-flash",
    "gemini-2.5-pro",
]
```

| Modelo               | Forte em                          | Notas                                      |
|----------------------|-----------------------------------|--------------------------------------------|
| `gemini-2.5-pro`     | Raciocinio, contexto longo        | Default recomendado para coding agentic.   |
| `gemini-2.0-flash`   | Velocidade, custo                 | Bom para tarefas curtas e iteracao rapida. |

Liste os modelos da sua conta:

```bash
vulp --provider gemini --list-models
```

---

## Notas e limitacoes

!!! warning "Tool call ids correlacionam por **nome**, nao por id"

    O Gemini **nao retorna `id` em function calls** — ele correla a resposta
    da tool com a chamada pelo **nome da funcao**.

    O Vulpcode mantem o tipo canonico `ToolCall` com `id` obrigatorio, entao
    o provider **sintetiza** um id no formato `gemini_<hex>` (ver
    `gemini.py:140`). Esse id e descartado quando o agent loop traduz a
    resposta de volta — `_msg_to_gemini` (`gemini.py:39`) usa
    `Message.name` (que o agent loop seta) para preencher o
    `function_response.name` esperado pelo Gemini.

    Implicacoes praticas:

    - **Nao** assuma que o `tool_call.id` retornado pelo Gemini e estavel
      ou inspecionavel pelo lado do servidor. Ele e local.
    - Se voce estiver estendendo o provider ou debugando uma tool call que
      "nao volta", verifique o **nome da funcao**, nao o id.
    - Se voce despachar varias chamadas com o mesmo `name` em paralelo,
      o protocolo Gemini nao consegue distingui-las pela resposta — e
      uma limitacao do backend, nao do Vulpcode.

- **System prompt vai como `system_instruction`.** Mensagens com
  `role="system"` sao **filtradas** do array `contents` (retornam `None`
  em `_msg_to_gemini`) e o `system` propriamente dito e injetado em
  `GenerateContentConfig(system_instruction=...)`. Manter o system como
  um turno regular **nao funciona** no Gemini.
- **Vision.** Aceita imagens em `parts`. Use o formato nativo do
  `google-genai` ao construir `Message.content` como lista.
- **Tools** vao para o SDK como `function_declarations` agrupadas em uma
  unica entrada de `tools` (`gemini.py:72`).

---

## Como funciona por baixo

O `stream()` (em `gemini.py:89`) chama `client.aio.models.generate_content_stream(...)`
e itera os `chunks` retornados:

| Campo no chunk                  | StreamChunk emitido                                    |
|---------------------------------|--------------------------------------------------------|
| `usage_metadata`                | `type="usage"` com `input_tokens`/`output_tokens`      |
| `part.text`                     | `type="text"` com o `delta`                            |
| `part.function_call`            | `type="tool_call"` com `id="gemini_<hex>"` sintetico   |
| fim do stream                   | `type="stop"`                                          |

Cada `chunk` pode conter zero, um ou varios `parts` — texto e function_call
podem aparecer no mesmo chunk. O provider emite um `StreamChunk` por part.

Mensagens com `tool_calls` (assistant) viram parts `function_call`;
respostas de tool (role `tool`) viram parts `function_response` cujo `name`
e o `Message.name` setado pelo agent loop. O `result` da tool e empacotado
como `{"result": <texto>}`.

Erros do SDK sao convertidos em `ProviderError` para nao vazarem detalhes
internos do `google-genai`.

---

## Veja tambem

- [Trocar provider em runtime](switching-at-runtime.md)
- [Conceitos principais](../getting-started/core-concepts.md)
- [Primeira configuracao](../getting-started/first-config.md)
- [Visao geral dos providers](index.md)
