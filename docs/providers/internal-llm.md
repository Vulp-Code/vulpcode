# internal-llm Provider (endpoint corporativo)

**Classe:** `InternalLLMProvider`
**Nome no registry:** `"internal-llm"`
**Suporte:** ferramentas NAO · visao NAO · streaming NAO (resposta inteira de uma vez)
**Codigo fonte:** [`src/vulpcode/providers/internal_llm.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/providers/internal_llm.py)

Provider para empresas que expoem um **microsservico interno de LLM** com
formato proprio: autenticacao via header `user-uuid`, payload JSON aninhado
em `data.solicitacao.messages` e resposta direta em `data["data"]`.

> O nome `internal-llm` e apenas um rotulo do registry — o codigo e
> **completamente agnostico** a qual empresa fornece o endpoint. Voce passa
> URL e UUID por config ou variavel de ambiente; a biblioteca **nunca** os
> hardcoda.

---

## Limitacoes importantes (leia primeiro)

| Recurso         | Suportado |
|-----------------|-----------|
| Tool calling    | NAO       |
| Vision          | NAO       |
| Streaming real  | NAO (resposta inteira de uma vez) |

Implicacoes praticas:

- **O agente nao consegue chamar ferramentas** (`Read`, `Write`, `Bash`,
  `Edit`, etc.) enquanto esse provider esta ativo. Sao desligadas pela
  flag `supports_tools=False`.
- Quando `tools` sao passadas para `stream()`, o provider injeta o texto
  `(note: this endpoint does not support tool calling; tools were ignored)`
  e segue adiante.
- A saida **nao chega progressivamente**: voce espera a resposta completa
  do upstream e ela aparece toda de uma vez na tela.

Use `internal-llm` apenas para **chat puro** (perguntas, explicacoes,
sumarios, brainstorming). Para tarefas que envolvem ler/escrever arquivos
ou rodar comandos, troque o provider em runtime — veja
[Trocar provider em runtime](switching-at-runtime.md):

```text
/provider anthropic
```

---

## Setup

=== "Env vars"

    ```bash
    export INTERNAL_LLM_ENDPOINT="http://internal.example.com/v1/chat"
    export INTERNAL_LLM_USER_UUID="00000000-0000-0000-0000-000000000000"
    vulp --provider internal-llm
    ```

=== "config.toml"

    ```toml
    default_provider = "internal-llm"
    default_model = "internal-llm"

    [providers.internal-llm]
    base_url = "http://internal.example.com/v1/chat"
    user_uuid = "00000000-0000-0000-0000-000000000000"
    max_retries = 3
    retry_delay = 5.0
    ```

=== "Programatico"

    ```python
    from vulpcode.providers import build_provider

    provider = build_provider("internal-llm", {
        "base_url": "http://internal.example.com/v1/chat",
        "user_uuid": "00000000-0000-0000-0000-000000000000",
    })
    ```

---

## Parametros

Construtor em `internal_llm.py:63`:

| Parametro     | Obrigatorio | Default | Descricao                                                                |
|---------------|-------------|---------|--------------------------------------------------------------------------|
| `base_url`    | sim         | `None`  | URL completa do endpoint (a chamada e um POST direto nele).              |
| `user_uuid`   | sim         | `None`  | UUID enviado no header `user-uuid` para autenticacao.                    |
| `timeout`     | nao         | `120.0` | Timeout do `httpx.AsyncClient`, em segundos.                             |
| `max_retries` | nao         | `3`     | Tentativas em caso de erro 5xx, falha de rede ou `data=null`.            |
| `retry_delay` | nao         | `5.0`   | Atraso base entre tentativas. Backoff linear: `delay * (attempt + 1)`.   |

Faltando `base_url` ou `user_uuid`, o provider levanta `ProviderError` com
mensagem indicando qual variavel/campo configurar.

---

## Variaveis de ambiente

Mapeamento em [`config.py:43-44`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/config.py):

| Env var                   | Mapeia para                            |
|---------------------------|----------------------------------------|
| `INTERNAL_LLM_ENDPOINT`   | `providers.internal-llm.base_url`      |
| `INTERNAL_LLM_USER_UUID`  | `providers.internal-llm.user_uuid`     |

Variaveis de ambiente sobrescrevem o `config.toml` e sao a forma recomendada
em ambientes corporativos onde a URL/UUID vem do gerenciador de segredos
(Vault, AWS Secrets Manager, etc.).

---

## Wire format

### Request

POST direto em `base_url`, sem path adicional.

**Headers:**

```http
user-uuid: <uuid>
Content-Type: application/json
Accept: application/json
```

**Body:**

```json
{
  "data": {
    "solicitacao": {
      "messages": [
        {"role": "system", "content": "..."},
        {"role": "user", "content": "..."}
      ]
    },
    "config": {
      "temperature": 0.7,
      "max_tokens": 3000,
      "top_p": 0.95
    }
  }
}
```

> O campo `solicitacao` e **literal do wire protocol** do endpoint
> corporativo — nao traduza nem renomeie. O provider envia exatamente esse
> nome em `internal_llm.py:156`.

`temperature`, `max_tokens` e `top_p` podem ser sobrescritos via `kwargs`
ao chamar `stream()`. Os defaults estao em `internal_llm.py:150-152`.

### Response esperada

```json
{ "data": "<texto da resposta do modelo>" }
```

O provider extrai `data["data"]` e emite um unico `StreamChunk` de texto,
seguido por `usage` (estimando `output_tokens` por contagem de palavras) e
`stop` com `stop_reason="end_turn"`.

### Comportamento de retry

Definido em `internal_llm.py:175-215`:

| Situacao                                  | Comportamento                                    |
|-------------------------------------------|--------------------------------------------------|
| HTTP 5xx                                  | Retry ate `max_retries`, com backoff linear.     |
| HTTP 200 mas `data=null`                  | Retry ate `max_retries` (falha transitoria).     |
| HTTP 4xx                                  | Falha imediata com `ProviderError`.              |
| Erro de rede (`httpx.HTTPError`)          | Retry ate `max_retries`.                         |
| Resposta nao-JSON                         | `ProviderError` imediato.                        |

Apos esgotar as tentativas, o provider levanta `ProviderError` com a
ultima mensagem de erro registrada.

---

## Como o agente "achata" o historico de tools

Como o endpoint **nao** tem tool calling nativo, o provider precisa
reduzir mensagens canonicas do agente (que incluem `role="tool"` e
`assistant.tool_calls`) para o formato plano do payload. A logica esta em
`_flatten_messages` (`internal_llm.py:89`):

- `role="tool"` vira `role="user"` com prefixo `[tool <name> result]\n<conteudo>`,
  onde `<name>` e `Message.name` ou `tool_call_id` como fallback.
- `role="assistant"` com `tool_calls` mantem **apenas a parte textual** —
  o array de tool calls e descartado (o endpoint nao saberia o que fazer
  com ele).
- Mensagens `system` viram a primeira entrada da lista.

Isso permite que o modelo **veja resultados de ferramentas anteriores**
quando voce trocou de provider no meio da sessao. Exemplo: voce comecou
com Anthropic, o agente leu `/etc/hostname` via `Read`, e voce trocou
para `internal-llm` com `/provider internal-llm`. O historico vira:

```text
user: leia /etc/hostname
assistant: ok
user: [tool Read result]
1\thostname-da-maquina
user: <sua proxima pergunta>
```

O modelo continua com contexto, mesmo que nao possa mais invocar a tool.

---

## Quando usar

- **Compliance corporativo** exige que todo trafego de IA passe por um proxy
  interno, com auditoria centralizada.
- O acesso aos modelos so existe via API interna — sem chave Anthropic /
  OpenAI / Gemini direto.
- Voce esta validando um POC de governanca de IA e quer um cliente CLI
  apontando para o endpoint da empresa.

## Quando NAO usar

- Voce precisa que o agente edite arquivos, rode comandos shell, ou faca
  qualquer coisa alem de gerar texto.
- Voce precisa de streaming visual progressivo (a resposta vem inteira).
- Voce precisa de visao (analise de imagens).

Para esses casos, troque em runtime: `/provider anthropic`, `/provider
gemini` ou outro. O historico e preservado, mas voce volta a ter tools.

---

## Exemplo programatico minimo

```python
import asyncio
from vulpcode.providers import Message, build_provider

async def main():
    provider = build_provider("internal-llm", {
        "base_url": "http://internal.example.com/v1/chat",
        "user_uuid": "00000000-0000-0000-0000-000000000000",
    })

    async for chunk in provider.stream(
        messages=[Message(role="user", content="Resuma o que e MCP em 3 linhas.")],
        tools=[],  # ignoradas mesmo se passadas
        model="internal-llm",
        system="Voce e um assistente conciso.",
    ):
        if chunk.type == "text":
            print(chunk.delta, end="", flush=True)

    await provider.aclose()

asyncio.run(main())
```

---

## Veja tambem

- [Visao geral dos providers](index.md)
- [Trocar provider em runtime](switching-at-runtime.md)
- [Anthropic](anthropic.md) — opcao com tools quando voce precisa do agente completo
- [Conceitos principais](../getting-started/core-concepts.md)
