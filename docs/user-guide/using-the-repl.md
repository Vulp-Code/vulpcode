# Usando o REPL

O REPL e a interface principal do vulpcode. Ele acopla o `Agent`, o `Renderer`
Rich e o `prompt_toolkit` num loop interativo: voce digita, o agente responde
em streaming, tool calls aparecem em painels e o historico fica salvo entre
sessoes.

> Implementacao em [`src/vulpcode/ui/repl.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/ui/repl.py).
> Streaming visual em [`src/vulpcode/ui/streaming.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/ui/streaming.py).

---

## Iniciar o REPL

A forma mais curta e simplesmente:

```bash
vulp
```

Sem argumentos, o `vulp` carrega `~/.vulpcode/config.toml`, escolhe o provider
e o modelo default e abre o REPL no modo `default` de permissoes (cada tool
de escrita pergunta antes).

Variacoes comuns:

```bash
vulp --auto                   # aprova todas as tool calls automaticamente
vulp --safe                   # confirma ate leituras (Read, Glob, Grep)
vulp --plan                   # plan-only: nao executa tools de fato
vulp --provider ollama        # forca um provider especifico
vulp --model claude-sonnet-4-6 # forca um modelo
vulp --resume                 # retoma a ultima sessao salva
```

Detalhes de cada flag estao em [Modos de permissao](permission-modes.md) e
[Sessoes](sessions.md).

A primeira tela que voce ve:

```text
Vulpcode REPL  (type /help for commands, /exit to quit)
>
```

---

## Anatomia da tela

Durante uma conversa, o REPL renderiza varios elementos. Numa sequencia tipica:

```text
> liste os .py em /tmp e diga quantos sao

[spinner] Thinking...

╭───────── Glob ──────────╮
│ {                       │
│   "pattern": "/tmp/*.py"│
│ }                       │
╰───────── running... ────╯

╭───────── Glob -> ok ─────────╮
│ /tmp/foo.py                  │
│ /tmp/bar.py                  │
╰──────────────────────────────╯

Encontrei 2 arquivos `.py` em `/tmp`.
tokens: in=1421 out=58
```

Componentes:

| Elemento                        | O que e                                                 |
| ------------------------------- | ------------------------------------------------------- |
| `>`                             | prompt do `prompt_toolkit`, onde voce digita            |
| Spinner `Thinking...`           | mostrado enquanto o provider gera tokens                |
| Painel com titulo `<tool>`      | `ToolStartEvent` — argumentos JSON formatados           |
| Painel `<tool> -> ok`           | `ToolEndEvent` em sucesso, borda verde                  |
| Painel `<tool> -> error`        | mesmo evento, mas borda vermelha quando `is_error=True` |
| Texto livre fluindo             | resposta do assistente em streaming                     |
| `tokens: in=N out=M`            | linha cinza com `UsageEvent` apos o turn                |
| `(stopped: <reason>)`           | aparece quando `stop_reason != "end_turn"`              |

Saidas longas das tools sao truncadas em **1500 caracteres** com a marca
`[...truncated...]` (veja `Renderer.render_tool_end`).

---

## Input

### Linha unica

Digite e pressione ++enter++ para enviar. O REPL e configurado com
`multiline=False` em [`repl.py:42`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/ui/repl.py#L42).

### Multi-linha

**Atualmente nao ha suporte nativo a multi-linha** (++enter++ envia
imediatamente). Workarounds:

- Cole o texto inteiro de uma vez: `prompt_toolkit` aceita newlines coladas
  como conteudo da linha.
- Use heredoc no shell para one-shot:

  ```bash
  vulp --print --auto "$(cat <<'EOF'
  refatore esta funcao:

  def add(a, b):
      return a + b
  EOF
  )"
  ```

### Historico persistente

Tudo que voce digita e salvo em `~/.vulpcode/history` (criado automaticamente
em [`repl.py:33`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/ui/repl.py#L33)).

Atalhos do `prompt_toolkit`:

| Tecla           | Acao                                                          |
| --------------- | ------------------------------------------------------------- |
| ++up++ / ++down++ | navegam o historico                                         |
| ++ctrl+r++      | busca incremental no historico                                |
| ++tab++         | autocompleta `/comandos` (ver `WordCompleter`)                |
| ++ctrl+a++ / ++ctrl+e++ | inicio / fim da linha                                |
| ++ctrl+u++      | apaga ate o inicio                                            |
| ++ctrl+l++      | limpa a tela (nao mexe no contexto, diferente de `/clear`)    |

`AutoSuggestFromHistory` exibe sugestoes "fantasma" enquanto voce digita —
++right++ aceita.

### Autocomplete de slash commands

A `WordCompleter` lista os comandos builtins (`/help`, `/clear`, `/exit`,
`/tools`, `/cost`, `/compact`) e tudo que `build_default_commands()` registrar
em runtime. Comece com `/` e pressione ++tab++.

---

## One-shot vs interativo

| Como invocar                       | Comportamento                                          |
| ---------------------------------- | ------------------------------------------------------ |
| `vulp`                             | REPL interativo                                        |
| `vulp "diga oi"`                   | one-shot via `Repl.one_shot()`, com Rich + spinner     |
| `vulp --print "diga oi"`           | headless: console sem cores forcadas, **sem spinner**  |
| `vulp --print --auto "..."`        | ideal para scripts/CI                                  |

Em [`app.py:78`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/app.py#L78),
`--print` faz `Console(force_terminal=False)`, util quando a saida vai para um
arquivo ou pipe.

Exemplo combinando one-shot com `jq`:

```bash
vulp --print --auto "liste 3 verbos em ingles separados por virgula" \
  | tr ',' '\n' \
  | head -3
```

---

## Permissao em runtime

Quando uma tool exige confirmacao (modo `default`, `--safe`, ou tool com
`requires_confirm=True`), o agente emite um evento e o `streaming.py` instala
um **prompter consciente do spinner**. O fluxo e:

1. O spinner `Running <tool>...` esta ativo.
2. Antes de pedir resposta ao usuario, o spinner para (`stop_spinner()`).
3. O REPL imprime algo como:

   ```text
   Permission required for Bash:
     command: rm -rf /tmp/test
   Approve? (y=yes once, a=yes always, n=no): _
   ```

4. Voce responde:
   - `y` — aprova so esta chamada
   - `a` — aprova esta tool para o resto da sessao (passa a entrar na "allowlist")
   - `n` — recusa; o agente recebe um `ToolDeniedEvent` e segue sem o resultado

5. O spinner e reinstalado e a execucao continua.

Detalhes do contrato de permissoes em [Modos de permissao](permission-modes.md).

> Em modo `--auto`, esse prompt nunca aparece. Em modo `--plan`, nenhuma tool
> e executada de verdade — o agente apenas descreve o que faria.

---

## Streaming visual

`stream_agent_turn()` consome os eventos do `Agent.turn()` e os despacha para
o `Renderer`:

| Evento              | Renderer                  | Efeito visual                              |
| ------------------- | ------------------------- | ------------------------------------------ |
| `TextEvent`         | `render_text_chunk`       | tokens aparecem caractere a caractere      |
| `ToolStartEvent`    | `render_tool_start`       | painel com nome da tool + JSON dos args    |
| `ToolEndEvent`      | `render_tool_end`         | painel verde (ok) ou vermelho (erro)       |
| `ToolDeniedEvent`   | `render_tool_denied`      | linha amarela `Tool 'X' denied: <reason>`  |
| `UsageEvent`        | `render_usage`            | `tokens: in=N out=M` (cinza)               |
| `ErrorEvent`        | `render_error`            | `error: <msg>` (vermelho)                  |
| `TurnEndEvent`      | `render_turn_end`         | encerra o turn; mostra `(stopped: ...)` se anormal |

O spinner e ligado/desligado entre eventos para que tool calls e prompts de
permissao apareçam sem competir com o `Live` do Rich.

---

## Sair do REPL

| Como                | Efeito                                                          |
| ------------------- | --------------------------------------------------------------- |
| `/exit` ou `/quit`  | sai limpo, imprime `bye`                                        |
| ++ctrl+d++          | EOF — captado pelo `try/except`, sai limpo com `bye`            |
| ++ctrl+c++          | KeyboardInterrupt — interrompe o turn atual e sai                |

Se o agente esta no meio de uma chamada de tool, ++ctrl+c++ interrompe a
execucao corrente. Para apenas **limpar o contexto** sem fechar o REPL, use
`/clear` (veja [Slash commands](slash-commands.md#clear)).

---

## Proximos passos

- [Slash commands](slash-commands.md) — referencia detalhada de cada `/comando`.
- [Modos de permissao](permission-modes.md) — `default`, `--auto`, `--safe`,
  `--plan`.
- [Sessoes](sessions.md) — `/save`, `/load` e `--resume`.
