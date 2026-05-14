# Tarefa 04.04 - Endpoint Corporativo (internal-llm)

**Status**: PENDENTE
**Fase**: 04 - Providers
**Dependencias**: 04.03
**Bloqueia**: nada

---

## Objetivo

Criar `providers/internal-llm.md` documentando o `InternalLLMProvider`:
formato do payload, autenticacao por header, retry em `data=null`, limitacoes.

---

## Arquivos a criar

- `docs/providers/internal-llm.md`

---

## Source de verdade

- `src/vulpcode/providers/internal_llm.py` — `InternalLLMProvider`
- `src/vulpcode/config.py` — env vars `INTERNAL_LLM_*`
- `tests/test_providers/test_internal_llm.py` — exemplos de chamada

---

## Estrutura

### 1. O que e

Provider para empresas que expoem um microsservico interno de LLM com formato
proprio: header `user-uuid` para auth, payload JSON aninhado em
`data.solicitacao.messages`, resposta direta em `data["data"]`.

O nome `internal-llm` e um rotulo do registry — o codigo e completamente
agnostico a qual empresa fornece o endpoint. Voce passa URL e UUID por config
ou env var, e a biblioteca **nunca** os hardcoda.

### 2. Limitacoes importantes

| Recurso         | Suportado |
|-----------------|-----------|
| Tool calling    | NAO       |
| Vision          | NAO       |
| Streaming real  | NAO (resposta inteira de uma vez) |

Implicacoes praticas:
- O agente do vulpcode NAO consegue chamar `Read`, `Write`, `Bash`, etc.
  quando esse provider esta ativo.
- Quando tools sao passadas no `stream()`, retorna texto: "this endpoint does
  not support tool calling; tools were ignored".
- A saida nao chega progressivamente — o usuario espera a resposta completa
  e ela aparece toda de uma vez.

Use `internal-llm` apenas para chat puro (perguntas / explicacoes / sumarios).
Para tarefas que envolvem ler/escrever arquivos, troque para outro provider
em runtime: `/provider anthropic`.

### 3. Setup

3 abas:

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

### 4. Parametros

| Parametro     | Obrigatorio | Default | Descricao |
|---------------|-------------|---------|-----------|
| `base_url`    | sim         | None    | URL completa do endpoint |
| `user_uuid`   | sim         | None    | UUID enviado no header `user-uuid` |
| `timeout`     | nao         | 120.0   | Segundos                |
| `max_retries` | nao         | 3       | Tentativas em caso de erro 5xx ou `data=null` |
| `retry_delay` | nao         | 5.0     | Atraso base (com backoff linear: delay * (attempt + 1)) |

### 5. Variaveis de ambiente

| Env var                   | Mapeia para                            |
|---------------------------|----------------------------------------|
| `INTERNAL_LLM_ENDPOINT`   | `providers.internal-llm.base_url`      |
| `INTERNAL_LLM_USER_UUID`  | `providers.internal-llm.user_uuid`     |

### 6. Wire format

#### Request

POST para `base_url` com:

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

#### Response esperada

```json
{ "data": "<texto da resposta>" }
```

#### Comportamento de retry

- Se HTTP 5xx: retry ate `max_retries`
- Se HTTP 200 mas `data=null`: retry ate `max_retries` (falha transitoria do
  upstream)
- Se HTTP 4xx: falha imediata (`ProviderError`)
- Se rede caiu: retry ate `max_retries`

### 7. Como o agente "achata" o historico

Como nao ha tool calling, mensagens com `role="tool"` sao convertidas para
`role="user"` com prefixo `[tool <name> result]`. Isso permite que o modelo
veja resultados de ferramentas anteriores quando voce trocou de provider no
meio da sessao.

Exemplo: se voce comecou com Anthropic, o agente leu um arquivo via Read,
e voce trocou para internal-llm, o historico vira:

```
user: leia /etc/hostname
assistant: ok (tool_call_id: t1)
user: [tool Read result]
1\thostname-da-maquina
user: <sua proxima pergunta>
```

### 8. Quando usar

- Compliance corporativo exige passar pelo proxy interno
- Acesso aos modelos so via API interna (sem chave Anthropic/OpenAI direto)
- Auditoria de uso de IA centralizada

### 9. Quando NAO usar

- Quando voce precisa que o agente edite arquivos / rode comandos shell
- Quando voce precisa de streaming visual rico
- Para vision (analise de imagens)

Para esses casos, troque em runtime: `/provider anthropic` ou outro.

---

## Atualizar `mkdocs.yml`

A entrada ja foi adicionada em 04.01. Nao mexer.

---

## INSTRUCAO CRITICA

- **NUNCA** colocar URLs reais ou UUIDs reais no markdown. Use sempre os
  placeholders `internal.example.com` e `00000000-...`.
- O field `solicitacao` e literal do wire protocol — nao traduzir nem mudar.
- Ressalte a limitacao de tools logo no inicio (antes de detalhes tecnicos)
  para o usuario nao ser surpreendido.

---

## Etapas de Implementacao

### Etapa 1: Ler `providers/internal_llm.py` e `tests/test_providers/test_internal_llm.py`
### Etapa 2: Criar `providers/internal-llm.md`
### Etapa 3: `mkdocs build`

---

## Criterios de Aceite

- [x] `docs/providers/internal-llm.md` criado
- [x] Limitacoes (sem tools, sem vision, sem streaming) destacadas no inicio
- [x] 3 abas de setup
- [x] Tabela de parametros completa (5 parametros)
- [x] Tabela de env vars (2)
- [x] Wire format (request + response) documentado em JSON
- [x] Comportamento de retry explicado (5xx, data=null, 4xx)
- [x] Secao explicando o "achatamento" de historico de tools
- [x] Secao "quando usar / quando nao usar"
- [x] Nenhuma URL ou UUID real no documento — apenas placeholders
- [x] `mkdocs build` continua passando

---

**End of Specification**
