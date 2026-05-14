# Provider translation

O Vulpcode conversa com cada modelo atraves de uma classe **`Provider`** que
traduz um contrato canonico (mensagens, tools, eventos de streaming) para o
SDK nativo do fornecedor — e de volta. Esta pagina documenta exatamente o
que cada adaptador faz nessa traducao.

> Codigo-fonte: [`src/vulpcode/providers/`](https://github.com/vulpcode/vulpcode/tree/main/src/vulpcode/providers).
> Contrato canonico: [`api/providers`](../api/providers.md).

---

## 1. Forma canonica

O agent loop fala apenas em tipos canonicos. Nenhum SDK de fornecedor vaza
para o nucleo.

| Tipo                                                                     | Papel                                                                            |
|--------------------------------------------------------------------------|----------------------------------------------------------------------------------|
| [`Message`][vulpcode.providers.base.Message]                             | Um turno (`role`, `content`, `tool_calls`, `tool_call_id`, `name`).              |
| [`ToolCall`][vulpcode.providers.base.ToolCall]                           | Pedido de execucao de tool (`id`, `name`, `arguments`).                          |
| [`StreamChunk`][vulpcode.providers.base.StreamChunk]                     | Um evento emitido por `Provider.stream` (`text` / `tool_call` / `usage` / ...). |
| [`Usage`][vulpcode.providers.base.Usage]                                 | Contagem de tokens do turno (input/output/cache).                                |
| `dict[str, Any]` no formato `{name, description, input_schema}`          | Schema de tool (gerado por [`Tool.to_schema`][vulpcode.tools.base.Tool.to_schema]). |

O **system prompt** **nao** faz parte da lista de mensagens — e passado
separadamente em `Provider.stream(system=...)` e cada adaptador acomoda no
lugar correto da API nativa.

---

## 2. Schema de tool — traducao por provider

Toda tool e exposta ao modelo via `Tool.to_schema()`:

```python
{
    "name": "Read",
    "description": "Read a file from disk...",
    "input_schema": { ... },  # Pydantic model_json_schema()
}
```

Cada adaptador converte essa lista para o formato esperado pelo SDK:

| Provider       | Formato nativo                                                                                         | Origem                                          |
|----------------|--------------------------------------------------------------------------------------------------------|-------------------------------------------------|
| Anthropic      | `{name, description, input_schema}` — **igual ao canonico**                                            | `AnthropicProvider._tools_to_anthropic`         |
| OpenAI         | `{type: "function", function: {name, description, parameters}}`                                        | `OpenAIProvider._tools_to_openai`               |
| Gemini         | `[{function_declarations: [{name, description, parameters}, ...]}]` (lista com um dict envelope)       | `GeminiProvider._tools_to_gemini`               |
| Ollama         | `{type: "function", function: {name, description, parameters}}` — igual OpenAI                        | `OllamaProvider._tools_to_ollama`               |
| internal-llm   | _Nao suporta._ Tools sao silenciosamente ignoradas e o adaptador injeta um aviso textual no primeiro chunk de texto. | `InternalLLMProvider.stream`                    |

O `input_schema` canonico e usado **literalmente** como `parameters` em
OpenAI/Ollama/Gemini, e como `input_schema` em Anthropic — a Pydantic ja
emite JSON Schema padrao, que e o que esses SDKs esperam.

---

## 3. Mensagens — traducao por provider

A funcao `_msg_to_<provider>` em cada adaptador define a transformacao. As
subsecoes a seguir descrevem cada caso (`role` x presenca de `tool_calls` /
`tool_call_id`).

### Anthropic

```python
# providers/anthropic.py
@staticmethod
def _msg_to_anthropic(msg: Message) -> dict[str, Any]:
    if msg.role == "tool":
        return {
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": msg.tool_call_id,
                "content": msg.content if isinstance(msg.content, str) else "",
            }],
        }
    if msg.role == "assistant" and msg.tool_calls:
        blocks = []
        if isinstance(msg.content, str) and msg.content:
            blocks.append({"type": "text", "text": msg.content})
        for tc in msg.tool_calls:
            blocks.append({
                "type": "tool_use",
                "id": tc.id,
                "name": tc.name,
                "input": tc.arguments,
            })
        return {"role": "assistant", "content": blocks}
    return {"role": msg.role, "content": msg.content}
```

| Caso canonico                                  | Saida Anthropic                                                                                          |
|-----------------------------------------------|----------------------------------------------------------------------------------------------------------|
| `role="user"` / `role="assistant"` (sem tools) | direto: `{role, content}`                                                                                |
| `role="assistant"` com `tool_calls`            | `content` vira lista de blocos: `text` (se houver) + um `tool_use(id, name, input)` por chamada          |
| `role="tool"`                                  | `role="user"` com bloco `tool_result(tool_use_id, content)`                                              |
| `system`                                       | **Nao** vai na lista — passa como parametro top-level `system=...` em `client.messages.stream(...)`      |

### OpenAI (e compativeis: DeepSeek, Groq, OpenRouter, LM Studio, vLLM)

```python
# providers/openai.py
@staticmethod
def _msg_to_openai(msg: Message) -> dict[str, Any]:
    if msg.role == "tool":
        return {
            "role": "tool",
            "tool_call_id": msg.tool_call_id,
            "content": msg.content if isinstance(msg.content, str) else "",
        }
    if msg.role == "assistant" and msg.tool_calls:
        return {
            "role": "assistant",
            "content": msg.content if isinstance(msg.content, str) else "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments or {}),
                    },
                }
                for tc in msg.tool_calls
            ],
        }
    return {"role": msg.role, "content": msg.content}
```

| Caso canonico                                  | Saida OpenAI                                                                                                                  |
|-----------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------|
| `role="user"` / `role="assistant"` (sem tools) | direto: `{role, content}`                                                                                                     |
| `role="assistant"` com `tool_calls`            | `tool_calls=[{id, type:"function", function:{name, arguments: <json string>}}]` (atencao: `arguments` e **string JSON**)      |
| `role="tool"`                                  | `{role:"tool", tool_call_id, content}`                                                                                        |
| `system`                                       | Inserido como **primeira** mensagem da lista: `{"role":"system", "content": <prompt>}`                                       |

### Gemini

```python
# providers/gemini.py
@staticmethod
def _msg_to_gemini(msg: Message) -> dict[str, Any] | None:
    if msg.role == "system":
        return None
    if msg.role == "tool":
        tool_name = msg.name or msg.tool_call_id or "tool"
        return {
            "role": "user",
            "parts": [{
                "function_response": {
                    "name": tool_name,
                    "response": {"result": msg.content if isinstance(msg.content, str) else ""},
                }
            }],
        }
    if msg.role == "assistant":
        parts = []
        if isinstance(msg.content, str) and msg.content:
            parts.append({"text": msg.content})
        for tc in msg.tool_calls or []:
            parts.append({"function_call": {"name": tc.name, "args": tc.arguments or {}}})
        return {"role": "model", "parts": parts}
    return {
        "role": "user",
        "parts": [{"text": msg.content if isinstance(msg.content, str) else ""}],
    }
```

| Caso canonico                                  | Saida Gemini                                                                                          |
|-----------------------------------------------|-------------------------------------------------------------------------------------------------------|
| `role="user"`                                  | `{role:"user", parts:[{text: ...}]}`                                                                  |
| `role="assistant"` (sem tools)                 | `{role:"model", parts:[{text: ...}]}` — Gemini chama o assistente de **`model`**                      |
| `role="assistant"` com `tool_calls`            | `parts=[..., {function_call:{name, args}}]` — note: **sem id**                                        |
| `role="tool"`                                  | `{role:"user", parts:[{function_response:{name, response:{result: ...}}}]}`                          |
| `system`                                       | Filtrado da lista (`return None`) e passado como `config.system_instruction=...` em `generate_content_stream(...)` |

!!! warning "Correlacionamento por nome, nao por id"
    Gemini **nao tem** um campo `id` para correlacionar `function_call` com
    `function_response` — usa o **nome da tool**. O adaptador sintetiza ids
    no formato `gemini_<8 hex>` apenas para satisfazer o contrato canonico
    (`ToolCall.id` obrigatorio); esses ids **nao** sao enviados de volta para
    o modelo. Se duas tools com o mesmo nome forem chamadas em paralelo no
    mesmo turno, a correlacao Gemini fica ambigua — em geral nao e um
    problema porque o modelo nao chama a mesma tool duas vezes em um turno.

### Ollama

```python
# providers/ollama.py
@staticmethod
def _msg_to_ollama(msg: Message) -> dict[str, Any]:
    if msg.role == "tool":
        return {
            "role": "tool",
            "content": msg.content if isinstance(msg.content, str) else "",
            "tool_call_id": msg.tool_call_id or "",
        }
    if msg.role == "assistant" and msg.tool_calls:
        return {
            "role": "assistant",
            "content": msg.content if isinstance(msg.content, str) else "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": tc.arguments or {}},
                }
                for tc in msg.tool_calls
            ],
        }
    return {"role": msg.role, "content": msg.content if isinstance(msg.content, str) else ""}
```

Praticamente identico ao OpenAI, com uma diferenca importante:

- `function.arguments` e **dict** em Ollama, **string JSON** em OpenAI.
- `system` tambem entra como primeira mensagem da lista.
- O transporte e NDJSON sobre `/api/chat` (uma linha por evento), nao SSE.

### internal-llm

```python
# providers/internal_llm.py
@staticmethod
def _flatten_messages(messages, system):
    out = []
    if system:
        out.append({"role": "system", "content": system})
    for m in messages:
        if m.role == "tool":
            tag = m.name or m.tool_call_id or "tool"
            out.append({"role": "user",
                        "content": f"[tool {tag} result]\n{m.content}"})
        elif m.role == "assistant":
            text = m.content if isinstance(m.content, str) else ""
            if text:
                out.append({"role": "assistant", "content": text})
        else:
            out.append({"role": m.role, "content": m.content})
    return out
```

| Caso canonico                                  | Saida internal-llm                                                                                       |
|-----------------------------------------------|----------------------------------------------------------------------------------------------------------|
| `role="user"` / `role="assistant"` (sem tools) | direto: `{role, content}`                                                                                |
| `role="assistant"` com `tool_calls`            | apenas o texto do `content` e preservado; os `tool_calls` sao **descartados** (endpoint nao suporta)     |
| `role="tool"`                                  | vira `{role:"user", content:"[tool <name> result]\n<content>"}` para o modelo ainda enxergar o resultado |
| `system`                                       | Primeira mensagem `{role:"system", content: <prompt>}`                                                   |

O endpoint corporativo recebe a lista achatada em
`{"data": {"solicitacao": {"messages": [...]}, "config": {...}}}` com
header `user-uuid: <uuid>`. Ver
[`providers/internal-llm`](../providers/internal-llm.md) para o wire format
completo.

---

## 4. Streaming — agregacao de chunks por provider

Cada adaptador consome eventos do SDK e emite [`StreamChunk`][vulpcode.providers.base.StreamChunk]
canonicos. As regras de agregacao sao especificas porque cada SDK fragmenta
de um jeito.

### Anthropic

| Evento SDK                       | Campos relevantes                                  | Acao do adaptador                                                                |
|----------------------------------|----------------------------------------------------|----------------------------------------------------------------------------------|
| `RawMessageStartEvent`           | `message.usage`                                    | emite `StreamChunk(type="usage", usage=...)` com `input_tokens`, `cache_*`       |
| `RawContentBlockStartEvent`      | `content_block.type == "tool_use"` + `id`/`name`   | abre slot em `pending[event.index]` com `id`, `name`, `json=""`                  |
| `RawContentBlockDeltaEvent`      | `delta.type == "text_delta"`                       | emite `StreamChunk(type="text", delta=delta.text)`                               |
| `RawContentBlockDeltaEvent`      | `delta.type == "input_json_delta"`                 | concatena `partial_json` no slot pendente (sem emitir nada)                      |
| `RawContentBlockStopEvent`       | `event.index`                                      | parseia o JSON acumulado e emite `StreamChunk(type="tool_call", tool_call=...)` |
| `RawMessageDeltaEvent`           | `delta.stop_reason`                                | guarda `stop_reason` para o chunk final                                          |
| `RawMessageDeltaEvent`           | `event.usage` (output incremental)                 | emite `StreamChunk(type="usage", usage=...)` com apenas `output_tokens`         |
| (fim do stream)                  | —                                                  | emite `StreamChunk(type="stop", stop_reason=...)`                                |

### OpenAI

OpenAI fragmenta tool calls em pedacos por **indice** — chega `index=0`,
depois `index=0` de novo com mais um pedaco do nome ou dos `arguments`,
etc. O adaptador buffera tudo em `pending: dict[int, slot]` e so emite o
`StreamChunk(type="tool_call")` quando `finish_reason ∈ {tool_calls, stop, length}`.

```python
# providers/openai.py — esqueleto
async for chunk in stream:
    if chunk.usage is not None:
        yield StreamChunk(type="usage", usage=Usage(...))
    delta = chunk.choices[0].delta
    if delta.content:
        yield StreamChunk(type="text", delta=delta.content)
    if delta.tool_calls:
        for tc_chunk in delta.tool_calls:
            slot = pending.setdefault(tc_chunk.index, {"id": "", "name": "", "args": ""})
            if tc_chunk.id:                       slot["id"]   = tc_chunk.id
            if tc_chunk.function.name:            slot["name"] = tc_chunk.function.name
            if tc_chunk.function.arguments:       slot["args"] += tc_chunk.function.arguments
    if chunk.choices[0].finish_reason in ("tool_calls", "stop", "length"):
        for idx in sorted(pending):
            yield StreamChunk(type="tool_call", tool_call=ToolCall(...))
        pending.clear()
yield StreamChunk(type="stop")
```

!!! note "Usage so chega se include_usage=True"
    O adaptador **sempre** envia `stream_options={"include_usage": True}`.
    Sem isso, o SDK do OpenAI nao retorna `chunk.usage` no fim do stream e a
    contabilidade de tokens fica zerada.

### Gemini

A SDK do Gemini ja entrega `function_call` **completo** em uma so
`Part` — nao ha agregacao incremental. Mesma coisa para `text`.

```python
# providers/gemini.py — esqueleto
async for chunk in stream:
    if chunk.usage_metadata is not None:
        yield StreamChunk(type="usage", usage=Usage(...))
    for part in chunk.candidates[0].content.parts:
        if part.text:
            yield StreamChunk(type="text", delta=part.text)
        if part.function_call is not None:
            yield StreamChunk(
                type="tool_call",
                tool_call=ToolCall(
                    id=f"gemini_{uuid.uuid4().hex[:8]}",
                    name=part.function_call.name,
                    arguments=dict(part.function_call.args or {}),
                ),
            )
yield StreamChunk(type="stop")
```

### Ollama

Cada **linha NDJSON** ja traz a mensagem completa do passo (texto e/ou
`tool_calls` ja parseaveis). O adaptador apenas re-emite no formato canonico.

- `function.arguments` pode vir como **string** ou **dict** dependendo do
  modelo — o adaptador decodifica string JSON com try/except e cai em `{}` em
  caso de erro.
- O evento `done=true` carrega `prompt_eval_count` / `eval_count`, virando
  um `StreamChunk(type="usage")`.

### internal-llm

Sem streaming real. O endpoint retorna o texto inteiro em uma resposta JSON,
e o adaptador emite na ordem:

1. `StreamChunk(type="text", delta=<aviso de tools ignoradas>)` se o turno
   trazia tools (uma unica vez).
2. `StreamChunk(type="text", delta=<resposta inteira>)`.
3. `StreamChunk(type="usage", usage=Usage(output_tokens=len(content.split())))` —
   contagem aproximada por palavras, ja que o endpoint nao reporta tokens.
4. `StreamChunk(type="stop", stop_reason="end_turn", raw={"model_requested": model})`.

---

## 5. Wrapping de erros

Todo adaptador envolve excecoes do SDK em
[`ProviderError`][vulpcode.providers.base.ProviderError]:

```python
try:
    async with self._client.messages.stream(**params) as stream:
        ...
except ProviderError:
    raise
except Exception as exc:
    raise ProviderError(f"Anthropic stream failed: {exc}") from exc
```

A regra:

- `ProviderError` ja levantado **passa adiante** (re-raise sem re-wrap).
- Qualquer outra excecao (`anthropic.APIError`, `openai.APIError`,
  `httpx.HTTPError`, `ValueError` em parse, etc.) e **convertida** em
  `ProviderError` com mensagem prefixada pelo nome do provider.

O agent loop captura `ProviderError` e emite `ErrorEvent` no stream
canonico, sem matar o REPL — o usuario ve a falha e pode tentar de novo.

---

## Veja tambem

- [Agent loop](agent-loop.md) — quem consome esses `StreamChunk`.
- [Streaming](streaming.md) — como os chunks viram UI.
- [Tool registry](tool-registry.md) — de onde vem o `input_schema` que
  cada provider re-empacota.
- [API: Provider](../api/providers.md) — assinaturas formais e tipos.
- [Providers / Anthropic](../providers/anthropic.md), [OpenAI](../providers/openai-family.md),
  [Gemini](../providers/gemini.md), [Ollama](../providers/ollama.md),
  [internal-llm](../providers/internal-llm.md) — guias do usuario.
