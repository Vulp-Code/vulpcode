# Ollama Provider

**Classe:** `OllamaProvider`
**Nome no registry:** `"ollama"`
**Suporte:** ferramentas SIM (depende do modelo) · visao SIM (depende do modelo) · streaming SIM
**Codigo fonte:** [`src/vulpcode/providers/ollama.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/providers/ollama.py)

Provider para [**Ollama**](https://ollama.com/) — um servidor local que serve
modelos open-source (Llama, Qwen, Mistral, DeepSeek-Coder, etc.). Roda 100%
offline, sem custo por token e sem chave de API.

---

## Pre-requisito: instalar Ollama

O Vulpcode **nao** instala o Ollama por voce. Instale e baixe pelo menos um
modelo antes de apontar o provider:

```bash
# Linux / macOS
curl https://ollama.com/install.sh | sh

# Baixe um modelo capaz de tool-calling (recomendado para coding agent)
ollama pull qwen2.5-coder:7b

# Verifique se o servidor esta rodando
curl http://localhost:11434/api/tags
```

No Windows, baixe o instalador em [ollama.com/download](https://ollama.com/download).

Apos instalar, o servidor escuta em `http://localhost:11434` por padrao —
exatamente o que o `OllamaProvider` espera.

---

## Setup rapido

=== "Env var"

    ```bash
    # Sem chave: o provider so precisa saber onde esta o servidor.
    # Se voce mudou a porta padrao do Ollama, exporte VULPCODE_PROVIDER e use
    # config.toml para o base_url.
    export VULPCODE_PROVIDER=ollama
    export VULPCODE_MODEL=qwen2.5-coder:7b
    vulp
    ```

=== "config.toml"

    ```toml
    default_provider = "ollama"
    default_model = "qwen2.5-coder:7b"

    [providers.ollama]
    # Default e http://localhost:11434 — so configure se mudou a porta
    # base_url = "http://localhost:11434"
    timeout  = 300.0  # modelos locais sao lentos; nao reduza demais
    ```

=== "Programatico"

    ```python
    from vulpcode.providers import build_provider

    provider = build_provider("ollama", {
        "base_url": "http://localhost:11434",
        "timeout": 300.0,
    })
    ```

---

## Parametros

Construtor em `ollama.py:23`:

| Parametro  | Tipo  | Default                     | Descricao                                                               |
|------------|-------|-----------------------------|-------------------------------------------------------------------------|
| `api_key`  | str   | `None`                      | Aceito por compatibilidade. **Ignorado** — Ollama nao usa autenticacao. |
| `base_url` | str   | `"http://localhost:11434"`  | URL do servidor Ollama. Mude se rodar em outra maquina/porta.           |
| `timeout`  | float | `300.0`                     | Timeout do client (segundos). **Maior que outros providers** — modelos locais costumam ser lentos no primeiro carregamento. |

---

## Modelos disponiveis

`list_models()` (`ollama.py:152`) consulta `GET /api/tags` no servidor local
e retorna os modelos efetivamente baixados:

```bash
$ vulp --provider ollama --list-models
qwen2.5-coder:7b
llama3.1:8b
mistral:latest
```

Modelos com **tool calling** comprovado para uso como agente:

| Modelo                  | Tool calling | Notas                                         |
|-------------------------|--------------|-----------------------------------------------|
| `qwen2.5-coder:7b`      | OK           | Recomendado. Bom equilibrio para hardware modesto. |
| `qwen2.5-coder:32b`     | OK           | Mais qualidade, requer GPU robusta.           |
| `llama3.1:8b`           | OK           | Tool calling estavel.                         |
| `llama3.1:70b`          | OK           | Para hardware potente.                        |
| `mistral:latest`        | OK           | Alternativa leve.                             |
| `deepseek-coder-v2`     | parcial      | Coding forte; tool calling depende do tag.    |

Baixe um modelo com `ollama pull <nome>`. A primeira execucao apos um pull
e mais lenta — o modelo precisa carregar na memoria.

---

## Notas e limitacoes

- **Sem chave.** Ollama nao tem autenticacao por padrao. Em redes
  compartilhadas, exponha o servico apenas via firewall/VPN.
- **Tool calling depende do modelo.** O provider envia tools no formato
  OpenAI-compatible (`{"type": "function", "function": {...}}`), mas o
  servidor so honra se o modelo subjacente foi treinado para tools.
  Modelos como `phi3` ou `gemma2` sem fine-tuning de tool-calling
  **ignoram** as tools silenciosamente.
- **Argumentos podem chegar como string ou dict.** O JSON Schema do Ollama
  varia entre versoes. O provider trata os dois casos:

    ```python
    args = fn.get("arguments")
    if isinstance(args, str):
        try:
            args = json.loads(args) if args else {}
        except json.JSONDecodeError:
            args = {}
    ```

    (`ollama.py:127`)

- **Tool call ids sao sintetizados.** Se o servidor nao mandar `id`, o
  provider gera `ollama_<hex>`. Como no Gemini, esse id e local — nao
  espere consistencia entre execucoes.
- **Vision.** Suportado nominalmente (`supports_vision=True`), mas requer
  um modelo de visao instalado (ex.: `llava`). Modelos texto-puros
  ignoram imagens.
- **Performance.** Tempo ate o primeiro token depende de carregar o modelo
  na VRAM. Em CPU pura, espere segundos ate dezenas de segundos por
  request — daqui o `timeout=300`.

---

## Como funciona por baixo

O `stream()` (em `ollama.py:84`) faz um `POST /api/chat` com
`stream: true` e itera o **NDJSON** (uma linha JSON por chunk):

| Campo no evento NDJSON                | StreamChunk emitido                                          |
|---------------------------------------|--------------------------------------------------------------|
| `message.content` (texto)             | `type="text"` com `delta`                                    |
| `message.tool_calls[*]`               | `type="tool_call"` com `id` real ou `ollama_<hex>` sintetico |
| `done: true` + `prompt_eval_count`/`eval_count` | `type="usage"` com `input_tokens`/`output_tokens` |
| fim do stream                         | `type="stop"`                                                |

Mensagens com `tool_calls` viram um array `tool_calls` no formato
OpenAI-compatible. Respostas de tool (role `tool`) viram entradas
`{role: "tool", content, tool_call_id}` no array `messages`. A traducao
esta em `_msg_to_ollama` (`ollama.py:47`).

O `system` prompt e adicionado como uma mensagem de role `system` no inicio
do array — formato natural para o `/api/chat` do Ollama.

Erros HTTP (servidor caido, modelo nao baixado, payload invalido) sao
convertidos em `ProviderError` com a mensagem original do `httpx`.

---

## Veja tambem

- [Trocar provider em runtime](switching-at-runtime.md)
- [Conceitos principais](../getting-started/core-concepts.md)
- [Primeira configuracao](../getting-started/first-config.md)
- [Visao geral dos providers](index.md)
- [Documentacao oficial do Ollama](https://github.com/ollama/ollama/blob/main/docs/api.md)
