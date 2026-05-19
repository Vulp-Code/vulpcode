# internal-llm-agentic Provider

**Classe:** `InternalLLMAgenticProvider`
**Nome no registry:** `"internal-llm-agentic"`
**Suporte:** ferramentas SIM (via protocolo de texto) · visao NAO · streaming NAO (resposta inteira de uma vez)
**Codigo fonte:** [`src/vulpcode/providers/internal_llm_agentic.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/providers/internal_llm_agentic.py)

Provider para empresas que expoem um endpoint corporativo `/chatCompletion` **sem** suporte a
tool calling nativo. Diferente de [`internal-llm`](internal-llm.md), este provider implementa um
**protocolo de tool calling baseado em texto** (XML-ish embutido na resposta do modelo) que
permite ao agente criar arquivos, rodar comandos e executar o loop agentico completo.

---

## 1. Overview

O endpoint corporativo suportado pelo `internal-llm` basico funciona apenas como chat puro:
o modelo so gera texto, entao acoes como criar arquivos ou executar comandos sao ignoradas.
O `internal-llm-agentic` resolve isso fazendo o modelo emitir chamadas de tool em formato
texto (tags XML) dentro da propria resposta, e o provider faz o parse e emite eventos
`tool_call` sinteticos para o agent loop existente.

**Diferencas praticas em relacao a `internal-llm`:**

| Caracteristica               | `internal-llm`        | `internal-llm-agentic`         |
|------------------------------|-----------------------|--------------------------------|
| Tool calling                 | NAO                   | SIM (via protocolo de texto)   |
| Cria arquivos                | NAO                   | SIM                            |
| Loop agentico                | NAO                   | SIM                            |
| Streaming progressivo        | NAO                   | NAO (resposta inteira)         |
| Visao (imagens)              | NAO                   | NAO                            |
| Depende do modelo obedecer   | —                     | SIM (modelo deve emitir as tags)|

Use `internal-llm-agentic` sempre que precisar que o agente realize acoes (criar arquivos,
ler disco, rodar comandos) atraves de um endpoint corporativo.

---

## 2. Configuration

### Variaveis de ambiente

```bash
export INTERNAL_LLM_ENDPOINT="https://internal.example.com/v1/chat"
export INTERNAL_LLM_USER_UUID="00000000-0000-0000-0000-000000000000"

vulp --provider internal-llm-agentic
```

### config.toml

```toml
default_provider = "internal-llm-agentic"
default_model    = "internal-llm-agentic"

[providers.internal-llm-agentic]
base_url  = "https://internal.example.com/v1/chat"
user_uuid = "00000000-0000-0000-0000-000000000000"
timeout   = 120.0
```

As mesmas variaveis de ambiente de `internal-llm` sao lidas — `INTERNAL_LLM_ENDPOINT` e
`INTERNAL_LLM_USER_UUID` — portanto nenhuma mudanca de ambiente e necessaria para quem ja
usava o provider basico.

### Parametros do construtor

| Parametro   | Obrigatorio | Default | Descricao                                            |
|-------------|-------------|---------|------------------------------------------------------|
| `base_url`  | sim         | `None`  | URL completa do endpoint (POST direto).              |
| `user_uuid` | sim         | `None`  | UUID enviado no header `user-uuid`.                  |
| `timeout`   | nao         | `120.0` | Timeout em segundos para cada chamada ao endpoint.   |

---

## 3. The text protocol

O protocolo usa um subconjunto de tags XML com namespace `vulp:`. O modelo deve emitir
chamadas de tool **dentro** do texto de resposta, no seguinte formato:

```xml
<vulp:tool name="WritePy">
  <vulp:arg name="file_path">/tmp/fib.py</vulp:arg>
  <vulp:content>
def fibonacci(n):
    a, b = 0, 1
    for _ in range(n):
        print(a)
        a, b = b, a + b

fibonacci(10)
  </vulp:content>
</vulp:tool>
```

Apos o provider executar a tool, o resultado e injetado de volta na conversa como:

```xml
<vulp:tool_result name="WritePy" is_error="false">
Wrote 98 bytes to /tmp/fib.py (validated OK)
</vulp:tool_result>
```

### Tags do protocolo

| Tag                  | Papel                                                                     |
|----------------------|---------------------------------------------------------------------------|
| `<vulp:tool>`        | Envolve a chamada inteira; atributo `name` e o nome da tool.             |
| `<vulp:arg>`         | Argumento escalar; atributo `name` e o campo do Input da tool.           |
| `<vulp:content>`     | Conteudo de arquivo (substituindo `<vulp:arg name="content">`).          |
| `<vulp:tool_result>` | Injetado pelo provider; atributo `is_error` indica sucesso ou falha.     |

O parser standalone esta em
[`src/vulpcode/providers/_text_tool_protocol.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/providers/_text_tool_protocol.py).
Ele e tolerante a texto livre fora das tags — o modelo pode escrever prosa antes ou depois
da chamada sem quebrar o parse.

---

## 4. Repair loop

O loop de reparo acontece de forma transparente sempre que uma `Write*` especializada
detecta um erro de validacao. Exemplo com `WritePy` e um `SyntaxError`:

**Passo 1 — Modelo emite codigo com erro:**

```xml
<vulp:tool name="WritePy">
  <vulp:arg name="file_path">/tmp/fib.py</vulp:arg>
  <vulp:content>
def fibonacci(n)
    print(n)
  </vulp:content>
</vulp:tool>
```

**Passo 2 — `WritePy` valida, detecta `SyntaxError`, retorna `is_error=True`:**

```xml
<vulp:tool_result name="WritePy" is_error="true">
SyntaxError at line 1, col 16: expected ':'
  def fibonacci(n)
                ^
File was NOT written. Fix the syntax error and try again.
</vulp:tool_result>
```

**Passo 3 — Agent loop devolve o erro ao modelo; modelo emite versao corrigida:**

```xml
<vulp:tool name="WritePy">
  <vulp:arg name="file_path">/tmp/fib.py</vulp:arg>
  <vulp:content>
def fibonacci(n):
    a, b = 0, 1
    for _ in range(n):
        print(a)
        a, b = b, a + b

fibonacci(10)
  </vulp:content>
</vulp:tool>
```

**Passo 4 — `WritePy` valida OK, grava atomicamente, retorna sucesso:**

```xml
<vulp:tool_result name="WritePy" is_error="false">
Wrote 98 bytes to /tmp/fib.py (validated OK)
</vulp:tool_result>
```

O arquivo so toca o disco no passo 4. Enquanto a validacao falha, o disco permanece intacto.

---

## 5. Caveats

- **Sem streaming progressivo:** a resposta chega inteira de uma vez do endpoint corporativo.
  A saida aparece no terminal apos o modelo terminar de responder.
- **Sem visao:** o endpoint nao aceita imagens ou conteudo multimodal.
- **Depende do modelo seguir o protocolo:** o system prompt injeta instrucoes detalhadas sobre
  as tags, mas modelos menores ou mal-ajustados podem ignorar ou malformar as tags. Verifique
  o comportamento do modelo especifico do seu endpoint.
- **`max_iters` elevado para 50:** cada tentativa de reparo consome uma iteracao. O provider
  solicita `max_iters=50` por default (vs 25 dos outros providers) para acomodar ciclos de
  reparo sem cortar o agente prematuramente.
- **Sem tool calling paralelo:** o protocolo de texto nao suporta chamadas concorrentes. O
  modelo emite uma tool por vez; o loop aguarda o resultado antes de continuar.

---

## 6. Troubleshooting

### Modelo emite prosa entre as tags

O parser ignora texto fora das tags `<vulp:tool>...</vulp:tool>`. Se o modelo escrever
apenas prosa sem tags, nenhuma tool sera chamada e o agent loop tratara a resposta como
texto puro. Verifique se o system prompt do protocolo esta sendo injetado corretamente.

### `<vulp:content>` contem `</vulp:content>` literal

Conteudo que inclui a string `</vulp:content>` literalmente (ex.: um arquivo de documentacao
que exemplifica o protocolo) ira fechar a tag prematuramente. O parser usa a **primeira**
ocorrencia do fechamento de tag. Para casos extremos, encode o conteudo em base64 ou
quebre o arquivo em partes.

### Tool result nao aparece no proximo turno

Se o model continua sem ver o resultado da tool, verifique se `_flatten_messages` esta
convertendo corretamente mensagens `role="tool"` para o formato de texto aceito pelo
endpoint. Habilite logging de debug (`VULPCODE_LOG_LEVEL=debug`) para inspecionar o
payload enviado.

### Erro `ProviderError: base_url is required`

Exporte `INTERNAL_LLM_ENDPOINT` ou adicione `base_url` em `[providers.internal-llm-agentic]`
no `config.toml`.

### Reparo nao converge (max_iters atingido)

Se o modelo nao corrige o codigo apos varias tentativas, o erro provavelmente nao esta
claro o suficiente, ou o modelo nao tem capacidade de corrigir esse tipo de problema. Tente:

1. Aumentar `max_iters` via parametro do `Agent`.
2. Simplificar o prompt — pedir um arquivo menor.
3. Trocar para um provider com tool calling nativo (`/provider anthropic`).

---

## Veja tambem

- [internal-llm](internal-llm.md) — modo chat puro para o mesmo endpoint
- [Validated Write family](../tools/validated-write.md) — todas as tools Write* com validacao
- [Visao geral dos providers](index.md)
- [Trocar provider em runtime](switching-at-runtime.md)
