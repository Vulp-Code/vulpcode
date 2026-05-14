# Adicionar um provider

Este guia mostra como suportar um novo modelo ou API no vulpcode. Antes de
comecar, vale a pena ler:

- [Provider translation](../architecture/provider-translation.md) — como o
  loop do agente fala com qualquer adapter.
- [API: Providers](../api/providers.md) — referencia gerada do
  [`Provider`](../api/providers.md) ABC.

A fonte da verdade e `src/vulpcode/providers/base.py`. Os exemplos neste
guia foram conferidos contra esse arquivo.

## Tres caminhos

A escolha depende do formato da API que voce quer adicionar:

| Caminho | Quando usar | Esforco |
| --- | --- | --- |
| **OpenAI-compatible** | A API segue o padrao `/v1/chat/completions` da OpenAI (DeepSeek, Groq, OpenRouter, vLLM, LM Studio...). | Adicionar 1 preset. |
| **Provider dedicado** | A API tem formato proprio (Anthropic Messages, Gemini `generateContent`, JSON-RPC interno...). | Subclasse de `Provider`. |
| **Customizacao** | Voce quer tweakar um provider que ja existe (ex: header extra, tradicao de mensagens diferente). | Subclasse do provider existente. |

---

## Caminho 1 — OpenAI-compatible (mais facil)

Se a API responde em `/v1/chat/completions` no formato OpenAI, basta adicionar
um preset. Nenhuma classe nova e necessaria — o
[`OpenAIProvider`](../api/providers.md) cuida de tudo.

### 1. Adicionar o preset

Em `src/vulpcode/providers/registry.py`:

```python
OPENAI_COMPATIBLE_PRESETS: dict[str, str | None] = {
    "openai": None,
    "deepseek": "https://api.deepseek.com/v1",
    "groq": "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "lmstudio": "http://localhost:1234/v1",
    "vllm": "http://localhost:8000/v1",
    "minha-empresa": "https://meu-llm.empresa.com/v1",  # novo
}
```

`None` como valor significa "use o `base_url` padrao do SDK" (so a OpenAI
canonica usa). Qualquer `base_url` passado em `config.toml` sempre vence o
preset.

### 2. (Opcional) Mapear a env var

Em `src/vulpcode/config.py`, no `ENV_MAP`:

```python
ENV_MAP: dict[str, tuple[str, ...]] = {
    ...
    "MINHA_EMPRESA_API_KEY": ("providers", "minha-empresa", "api_key"),
}
```

Pulando este passo, o usuario ainda pode configurar via TOML ou
`VULPCODE_PROVIDER` + `OPENAI_API_KEY` (que e o que o `OpenAIProvider` le
por default).

### 3. (Opcional) Default model

Em `src/vulpcode/app.py`, na funcao `_default_model_for`:

```python
def _default_model_for(provider_name):
    return {
        "anthropic": "claude-sonnet-4-7",
        ...
        "minha-empresa": "modelo-default",
    }.get(provider_name, "")
```

Pular este passo significa que o usuario tera que passar `--model` ou
configurar `default_model` na config dele.

### 4. Tests

Em `tests/test_providers/test_registry.py`:

```python
def test_minha_empresa_preset():
    p = build_provider("minha-empresa", {"api_key": "sk-..."})
    assert p.base_url == "https://meu-llm.empresa.com/v1"
    assert "minha-empresa" in list_provider_names()
```

Pronto. O usuario ja pode usar `vulpcode --provider minha-empresa --model modelo-default`.

---

## Caminho 2 — Provider dedicado

Se a API tem formato proprio (payload, eventos de streaming, schema de
tools), voce precisa de um adapter dedicado. Ele traduz entre os tipos
canonicos do vulpcode e o formato nativo do provider.

### Contrato a implementar

O contrato e o ABC [`Provider`](../api/providers.md). Em resumo:

```python
class Provider(ABC):
    name: str  # identificador no registry, ex: "seu"

    def __init__(self, api_key=None, base_url=None, timeout=120.0, **extra): ...

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        model: str,
        system: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]: ...

    def supports_tools(self) -> bool: ...
    def supports_vision(self) -> bool: ...
    async def list_models(self) -> list[str]: ...   # default: []
    async def aclose(self) -> None: ...             # default: no-op
```

`stream` deve ser um generator assincrono que yield `StreamChunk` na ordem
em que os eventos chegam. Os tipos canonicos relevantes sao:

| Tipo | Quando emitir | Campos |
| --- | --- | --- |
| `text` | Delta de texto incremental. | `delta=str` |
| `tool_call` | Tool call ja parseada. | `tool_call=ToolCall(id, name, arguments)` |
| `usage` | Contagem de tokens (uma vez por turno). | `usage=Usage(...)` |
| `stop` | Fim do turno. | `stop_reason="end_turn" \| "tool_use" \| "max_tokens" \| ...` |
| `error` | Erro recuperavel (logar e continuar). | `error=str` |

Para falhas terminais (auth, 5xx repetidos, payload malformado), levante
`ProviderError` em vez de yieldar.

### Esqueleto

Crie `src/vulpcode/providers/seu.py`:

```python
"""Adapter para a API do Provedor Seu."""
from __future__ import annotations

from typing import Any, AsyncIterator

import httpx

from vulpcode.providers.base import (
    Message,
    Provider,
    ProviderError,
    StreamChunk,
    ToolCall,
    Usage,
)


class SeuProvider(Provider):
    """Adapter para a API do Provedor Seu."""

    name = "seu"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 120.0,
        **extra: Any,
    ) -> None:
        super().__init__(api_key=api_key, base_url=base_url, timeout=timeout, **extra)
        self._client = httpx.AsyncClient(
            base_url=base_url or "https://api.seu-provider.com/v1",
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
        )

    def supports_tools(self) -> bool:
        return True

    def supports_vision(self) -> bool:
        return False

    async def aclose(self) -> None:
        await self._client.aclose()

    async def list_models(self) -> list[str]:
        return ["seu-modelo-1", "seu-modelo-2"]

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        model: str,
        system: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        # 1. Traduzir messages canonicos -> formato do seu provider.
        api_messages = self._translate_messages(messages, system)

        # 2. Traduzir tools canonicos -> formato do seu provider.
        api_tools = [self._translate_tool(t) for t in tools]

        payload = {
            "model": model,
            "messages": api_messages,
            "tools": api_tools or None,
            "stream": True,
            "max_tokens": kwargs.get("max_tokens", 4096),
            "temperature": kwargs.get("temperature", 0.7),
        }

        try:
            async with self._client.stream("POST", "/chat", json=payload) as resp:
                if resp.status_code >= 400:
                    body = await resp.aread()
                    raise ProviderError(
                        f"HTTP {resp.status_code}: {body.decode(errors='replace')[:200]}"
                    )

                # 3. Iterar eventos de streaming e yield StreamChunk por evento.
                async for event in self._iter_events(resp):
                    if event["type"] == "text":
                        yield StreamChunk(type="text", delta=event["delta"])
                    elif event["type"] == "tool_use":
                        yield StreamChunk(
                            type="tool_call",
                            tool_call=ToolCall(
                                id=event["id"],
                                name=event["name"],
                                arguments=event["arguments"],
                            ),
                        )
                    elif event["type"] == "usage":
                        yield StreamChunk(
                            type="usage",
                            usage=Usage(
                                input_tokens=event["input_tokens"],
                                output_tokens=event["output_tokens"],
                            ),
                        )

            # 4. Fim do turno.
            yield StreamChunk(type="stop", stop_reason="end_turn")

        except httpx.HTTPError as exc:
            raise ProviderError(f"network error: {exc}") from exc

    @staticmethod
    def _translate_messages(
        messages: list[Message], system: str | None
    ) -> list[dict[str, Any]]:
        """Converte Message canonico -> formato do provider."""
        out: list[dict[str, Any]] = []
        if system:
            out.append({"role": "system", "content": system})
        for m in messages:
            out.append({"role": m.role, "content": m.content})
        return out

    @staticmethod
    def _translate_tool(tool_schema: dict[str, Any]) -> dict[str, Any]:
        """Converte schema canonico (Tool.to_schema) -> formato do provider."""
        return {
            "name": tool_schema["name"],
            "description": tool_schema["description"],
            "parameters": tool_schema["input_schema"],
        }

    async def _iter_events(self, resp):
        """Parser SSE / JSON-lines do seu provider."""
        async for line in resp.aiter_lines():
            ...  # parsing especifico do provider
```

### Retry e erros

Para APIs que retornam 5xx transientes ou payloads incompletos, faca retry
com backoff. O padrao do
[`InternalLLMProvider`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/providers/internal_llm.py)
e um bom ponto de partida — `max_retries` + `retry_delay` no construtor,
loop com `await asyncio.sleep(self.retry_delay * (attempt + 1))` entre
tentativas, e `ProviderError` na ultima falha.

```python
async def stream(self, ...):
    last_error: str | None = None
    for attempt in range(self.max_retries):
        try:
            resp = await self._client.post(...)
        except httpx.HTTPError as exc:
            last_error = f"network error: {exc}"
            if attempt < self.max_retries - 1:
                await asyncio.sleep(self.retry_delay * (attempt + 1))
                continue
            raise ProviderError(last_error) from exc

        if resp.status_code >= 500:
            last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
            if attempt < self.max_retries - 1:
                await asyncio.sleep(self.retry_delay * (attempt + 1))
                continue
            raise ProviderError(last_error)

        # ... processar response, yield chunks ...
        return

    raise ProviderError(last_error or "provider failed after retries")
```

### 5. Registrar no registry

Em `src/vulpcode/providers/registry.py`:

```python
from vulpcode.providers.seu import SeuProvider

_DEDICATED: dict[str, type[Provider]] = {
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
    "internal-llm": InternalLLMProvider,
    "ollama": OllamaProvider,
    "seu": SeuProvider,  # novo
}
```

### 6. Default model + env vars

Mesmos passos do Caminho 1, secoes 2 e 3.

### 7. Tests

Em `tests/test_providers/test_seu.py`, espelhe o padrao de
`tests/test_providers/test_internal_llm.py`. No minimo:

- **Tests de traducao** sem chamar a API real (pure-Python, rapidos).
- **Tests de stream** com `httpx.MockTransport` ou `respx`.
- **Tests de erros** (4xx terminal, 5xx com retry, network error).
- **Test de registry**: `assert "seu" in list_provider_names()` e
  `assert build_provider("seu", {"api_key": "x"}).name == "seu"`.

Exemplo minimo:

```python
import pytest
from vulpcode.providers.base import Message
from vulpcode.providers.registry import build_provider, list_provider_names
from vulpcode.providers.seu import SeuProvider


def test_seu_registered():
    assert "seu" in list_provider_names()
    p = build_provider("seu", {"api_key": "test"})
    assert isinstance(p, SeuProvider)


def test_seu_translate_messages():
    p = SeuProvider(api_key="test")
    out = p._translate_messages(
        [Message(role="user", content="oi")],
        system="be helpful",
    )
    assert out[0] == {"role": "system", "content": "be helpful"}
    assert out[1] == {"role": "user", "content": "oi"}


@pytest.mark.asyncio
async def test_seu_stream_text(monkeypatch):
    # ... mock httpx, drive um stream text + stop, assert chunks ...
    ...
```

---

## Caminho 3 — Customizar um provider existente

Se voce so quer alterar um detalhe (header de auth, modelo default, parsing
de erro), subclasse o provider existente. Por exemplo, suportar um proxy
interno na frente da Anthropic:

```python
from vulpcode.providers.anthropic import AnthropicProvider


class AnthropicCorporateProvider(AnthropicProvider):
    name = "anthropic-corp"

    def __init__(self, *, tenant_id: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self.tenant_id = tenant_id
        # injetar header custom no client SDK, se aplicavel
```

E registre da mesma forma em `_DEDICATED`. Tudo o que voce nao sobrescrever
herda do pai.

---

## Decisoes comuns

- **A API nao suporta streaming?**
  Yield 1 chunk `text` com a resposta inteira + 1 chunk `stop`. Veja
  `internal_llm.py` como exemplo (POST sincrono, response monolitica,
  ainda assim adapta para o formato `AsyncIterator[StreamChunk]`).

- **A API nao suporta tool calling?**
  Retorne `supports_tools() -> False` e ignore a lista `tools` recebida em
  `stream`. Idealmente, yield 1 chunk `text` no inicio avisando o usuario
  ("(note: this endpoint does not support tool calling; tools were
  ignored)") — `internal_llm.py` faz exatamente isso.

- **Auth nao-padrao (header customizado)?**
  Aceite kwargs extras no construtor (ex: `user_uuid`, `tenant_id`),
  guarde-os como atributo, e injete no header do request. Esses extras
  fluem via `config.toml` na secao `[providers.<nome>]` ou via
  `**extra` no `build_provider`.

- **Modelos diferentes precisam de configuracao diferente?**
  Faca o tweak em `stream` baseado no `model` recebido. Por exemplo, ativar
  `supports_vision=True` so para certos modelos.

---

## Checklist final

- [ ] Provider em `src/vulpcode/providers/<seu>.py` (ou preset em
      `OPENAI_COMPATIBLE_PRESETS`).
- [ ] `_DEDICATED` atualizado em `registry.py` (so para Caminho 2/3).
- [ ] `_default_model_for` em `app.py` atualizado (opcional mas recomendado).
- [ ] `ENV_MAP` em `config.py` atualizado (opcional, para conveniencia).
- [ ] Tests >= 6 em `tests/test_providers/test_<seu>.py` cobrindo
      traducao, stream, erros e registro.
- [ ] Doc em `docs/providers/<seu>.md` seguindo o padrao da
      [FASE 04](../providers/index.md) (env vars, modelos, exemplo CLI,
      gotchas).
- [ ] Linha nova na tabela em `docs/providers/index.md`.
- [ ] Entrada nova na nav em `mkdocs.yml`.
- [ ] `pytest tests/` passa.
- [ ] `mkdocs build --strict` passa sem warnings.

Veja tambem: [Adicionar uma tool](add-tool.md),
[Setup de desenvolvimento](dev-setup.md),
[Convencoes de codigo](code-conventions.md).
