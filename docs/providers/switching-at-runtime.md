# Trocar provider em runtime

Dois slash commands controlam qual backend o REPL fala — sem reiniciar:

- `/provider` — listar providers configurados, ou trocar o provider ativo.
- `/model` — listar modelos do provider atual, ou trocar o modelo ativo.

Os dois sao implementados em
[`src/vulpcode/commands/provider_model.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/commands/provider_model.py).

---

## `/provider`

### Sem args — listar

```text
> /provider
        Providers
name           active
anthropic      *
deepseek
gemini
groq
internal-llm
lmstudio
ollama
openai
openrouter
vllm
current: AnthropicProvider
```

A coluna **`active`** marca com `*` o provider em uso. A linha
`current: ...` mostra o **nome da classe Python** subjacente (vem de
`type(repl.agent.provider).__name__` em `provider_model.py:14`).

!!! warning "Pegadinha dos OpenAI-compatibles"

    Todos os seis providers OpenAI-compatibles (`openai`, `deepseek`,
    `groq`, `openrouter`, `lmstudio`, `vllm`) compartilham a mesma
    classe `OpenAIProvider`, e essa classe tem `name = "openai"`. O
    marcador `*` casa o nome listado contra `provider.name`
    (`provider_model.py:19`), entao **se voce esta em `deepseek`, o
    `*` vai aparecer ao lado de `openai` na tabela** — nao de
    `deepseek`. A linha `current: OpenAIProvider` confirma a classe,
    mas nao distingue qual preset.

    Para saber com certeza qual preset esta ativo, olhe o `base_url`
    do `repl.agent.provider`.

### Com arg — trocar

```text
> /provider ollama
provider switched to ollama
```

O fluxo do comando (`provider_model.py:24`):

1. Valida que `name` esta em `list_provider_names()`.
2. Le `repl.config["providers"][name]` para construir a config.
3. Chama `build_provider(name, cfg)` — que aplica o preset de
   `base_url` se for um OpenAI-compatible sem URL explicita.
4. Fecha o provider antigo com `await old.aclose()` (silencia falhas).
5. Substitui `repl.agent.provider` pelo novo.

Se algo falha — por exemplo, voce trocou para `deepseek` mas nao tem
`DEEPSEEK_API_KEY` setada — o REPL imprime um erro vermelho e mantem
o provider antigo:

```text
> /provider deepseek
Failed to build provider deepseek: ...
```

> Voce pode setar config inline em `~/.vulpcode/config.toml` antes de
> trocar, ou exportar a env var no terminal e rodar `vulp` novamente.

---

## `/model`

### Sem args — listar

```text
> /model
       Models
name                    active
claude-haiku-4-5
claude-opus-4-7
claude-sonnet-4-6       *
```

Por baixo, chama `await repl.agent.provider.list_models()`. O resultado
varia por provider:

- **Anthropic:** lista curada hardcoded.
- **OpenAI/DeepSeek/Groq/...:** chama `GET /v1/models` no servidor.
- **Gemini:** consulta `client.aio.models.list()` (com fallback
  hardcoded se a chamada falhar).
- **Ollama:** consulta `GET /api/tags` no servidor local.
- **internal-llm:** geralmente retorna lista vazia.

Se a lista vier vazia, o REPL imprime so o modelo atual:

```text
no models reported by provider; current: gpt-4o-mini
```

### Com arg — trocar

```text
> /model gpt-4o
model set to gpt-4o
```

O comando apenas seta `repl.agent.model = args.strip()`
(`provider_model.py:64`). **Nao ha validacao** — qualquer string e
aceita. Se voce digitar errado, a falha so aparece na proxima chamada
do provider, com a mensagem original do backend.

---

## Historico e preservado ao trocar

`/provider` substitui apenas `repl.agent.provider`. O array de
mensagens canonicas (`Message`) que o agente carrega **nao e tocado**.
A proxima chamada `provider.stream(messages, ...)` traduz tudo para o
formato nativo do novo backend.

Isso significa que voce pode comecar uma conversa com Claude, mudar
para Ollama no meio e seguir conversando — o contexto inteiro vai
junto.

### Quando o historico pode confundir o novo provider

O tipo canonico `Message` e neutro, mas as **referencias entre tool
calls** dependem do dialeto:

- **Tool calls antigos com nomes que o novo provider nao expoe como
  tools.** Raramente quebra — o LLM tipicamente ignora o turno
  anterior. Em pior caso, ele pode tentar repetir a chamada.
- **Mensagens `role="tool"` com `tool_call_id` cunhado pelo provider
  antigo.** Cada provider trata o id de forma diferente:
    - **Anthropic** correlaciona por `tool_use_id` (string opaca).
    - **OpenAI / DeepSeek / Groq / OpenRouter / LM Studio / vLLM**
      correlacionam por `tool_call_id`. Mantem a mensagem mas pode
      nao "casar" com nenhuma chamada visivel.
    - **Gemini** correlaciona por **nome da funcao**, nao por id —
      ids sintetizados (`gemini_<hex>`) sao locais e descartados.
    - **Ollama** aceita `tool_call_id` opcional; gera `ollama_<hex>`
      quando ausente.

Em casos extremos — se o novo provider comecar a repetir tool calls
ou se confundir com o contexto anterior — limpe o historico antes de
trocar:

```text
> /clear
history cleared
> /provider gemini
provider switched to gemini
```

`/clear` e um comando builtin do REPL (`ui/repl.py:81`) que chama
`repl.agent.reset()`.

---

## Cenarios praticos

### Comecar caro, terminar barato

Use Claude para a parte criativa (planejamento, refactor complexo) e
caia para Ollama na fase mecanica (ajustes pontuais, formatacao):

```text
> Quero refatorar o modulo X em Y...
[Claude faz o trabalho pesado]

> /provider ollama
provider switched to ollama
> /model qwen2.5-coder:7b
model set to qwen2.5-coder:7b

> Agora aplique o mesmo padrao no arquivo Z
[Ollama termina, sem custo]
```

### Comparar a mesma pergunta em N modelos

Combine `/save`, `/provider` e `/load` (de
[`session_cmds.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/commands/session_cmds.py)):

```text
> Qual a melhor forma de implementar X em Python?
[anthropic responde]

> /save baseline-x

> /provider deepseek
> Qual a melhor forma de implementar X em Python?
[deepseek responde]

> /load baseline-x       # volta ao estado anterior
> /provider openrouter
> /model meta-llama/llama-3.1-70b-instruct
> Qual a melhor forma de implementar X em Python?
[llama responde]
```

`/load` restaura o snapshot inteiro — incluindo o provider que estava
ativo no momento de `/save`, entao voce nao precisa lembrar de voltar
manualmente.

### Cair para offline

Internet caiu? Servidor da OpenAI fora?

```text
> /provider ollama
provider switched to ollama
> /model qwen2.5-coder:7b
model set to qwen2.5-coder:7b
```

Voce mantem o contexto e continua trabalhando contra o modelo local.

---

## Veja tambem

- [Visao geral dos providers](index.md)
- [OpenAI e compatibles](openai-family.md)
- [Anthropic](anthropic.md) · [Gemini](gemini.md) · [Ollama](ollama.md)
- [Slash commands](../user-guide/slash-commands.md) — referencia completa
  de `/save`, `/load`, `/clear`, `/compact`, ...
- [Sessoes e historico](../user-guide/sessions.md)
