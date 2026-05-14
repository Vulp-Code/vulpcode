# Slash commands

Referencia completa dos comandos que o REPL reconhece quando voce digita uma
linha que comeca com `/`.

> **De onde vem cada comando?** `/help`, `/clear`, `/exit` e `/quit` sao
> **builtins** do `Repl` — ficam em
> [`Repl._handle_slash`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/ui/repl.py).
> Os demais sao registrados via `build_default_commands()` em
> [`commands/__init__.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/commands/__init__.py),
> cada um implementando a ABC `SlashCommand` em
> [`commands/_base.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/commands/_base.py).

## Tabela de comandos

| Comando             | Argumentos    | Funcao                                       |
| ------------------- | ------------- | -------------------------------------------- |
| `/help`             | -             | Lista comandos                               |
| `/clear`            | -             | Apaga historico do contexto (nao da tela)    |
| `/exit` ou `/quit`  | -             | Sai do REPL                                  |
| `/tools`            | -             | Tabela de tools registradas                  |
| `/cost`             | -             | Tokens acumulados na sessao                  |
| `/compact`          | -             | Resume historico para economizar contexto    |
| `/provider`         | `[nome]`      | Lista ou troca o provider ativo              |
| `/model`            | `[nome]`      | Lista ou troca o modelo ativo                |
| `/save`             | `[nome]`      | Salva sessao em `~/.vulpcode/sessions/`      |
| `/load`             | `[nome]`      | Carrega sessao salva                         |
| `/mcp`              | -             | Lista servidores MCP configurados            |

> Argumentos entre `[colchetes]` sao opcionais. `/save` e `/load` aceitam o
> nome opcional — se omitido, usam `default`.

---

## `/help`

Lista todos os comandos disponiveis.

**Sintaxe**

```text
/help
```

**Exemplo de uso**

```text
> /help
```

**O que voce ve**

```text
+----------+-------------------------------------------------+
| Commands                                                   |
+----------+-------------------------------------------------+
| command  | description                                     |
+----------+-------------------------------------------------+
| /help    | Show this help                                  |
| /clear   | Clear conversation history                      |
| /exit    | Quit                                            |
| /tools   | List currently registered tools                 |
| /cost    | Show accumulated token usage for this session   |
| /compact | Summarize the conversation history into a ...   |
| /provider| List providers, or switch with /provider <name> |
| /model   | List models, or switch with /model <name>       |
| /save    | Save current session messages: /save <name>     |
| /load    | Load a saved session: /load <name>              |
| /mcp     | List MCP servers and the tools they provide     |
+----------+-------------------------------------------------+
```

**Notas**

- A descricao de cada comando vem do atributo `help_text` da classe
  `SlashCommand` correspondente.
- `/help` e um builtin do `Repl`; nao aparece na lista
  `build_default_commands()`.

---

## `/clear`

Apaga o historico de mensagens do agente, mas **nao** limpa a tela.

**Sintaxe**

```text
/clear
```

**Exemplo de uso**

```text
> /clear
```

**O que voce ve**

```text
history cleared
```

**Notas**

- Internamente chama `agent.reset()`, que zera `agent._messages`.
- Util quando o agente "ficou contaminado" com contexto irrelevante ou se voce
  quer comecar uma nova tarefa sem fechar o REPL.
- Se quiser limpar a tela tambem, use ++ctrl+l++ depois.
- Diferente de `/compact`, que **resume** o historico em vez de joga-lo fora.

---

## `/exit` e `/quit`

Encerra o REPL.

**Sintaxe**

```text
/exit
/quit
```

**O que voce ve**

```text
bye
```

**Notas**

- Tambem podem ser disparados por ++ctrl+d++ (EOF).
- Servidores MCP iniciados pela sessao sao parados via `stop_servers()` no
  `finally` de [`app.start_repl`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/app.py).

---

## `/tools`

Mostra todas as tools registradas no agente, indicando se exigem confirmacao.

**Sintaxe**

```text
/tools
```

**Exemplo de uso**

```text
> /tools
```

**O que voce ve**

```text
+--------------+----------+--------------------------------------+
| Active tools                                                   |
+--------------+----------+--------------------------------------+
| name         | confirm? | description                          |
+--------------+----------+--------------------------------------+
| Read         | no       | Read a file from the local filesystem|
| Write        | yes      | Write a file to the local filesystem |
| Edit         | yes      | Performs exact string replacements   |
| Bash         | yes      | Executes a given bash command and... |
| Glob         | no       | Fast file pattern matching tool      |
| Grep         | no       | A powerful search tool built on rip..|
| ...                                                            |
+--------------+----------+--------------------------------------+
```

**Notas**

- A lista vem de `vulpcode.tools.list_tools()`. Tools de MCP aparecem com
  prefixo `mcp__<server>__<tool>`.
- A coluna `confirm?` reflete a flag `_requires_confirm` da tool — se `yes`,
  o REPL pergunta antes de executar (no modo `default`).
- Descricoes longas sao truncadas em 60 caracteres na tabela.

---

## `/cost`

Imprime o uso acumulado de tokens da sessao atual.

**Sintaxe**

```text
/cost
```

**Exemplo de uso**

```text
> /cost
```

**O que voce ve**

```text
+--------------+--------+
| Session usage         |
+--------------+--------+
| metric       | tokens |
+--------------+--------+
| input        | 12453  |
| output       |  2810  |
| cache_read   |  9100  |
| cache_create |   450  |
+--------------+--------+
```

**Notas**

- Os valores sao acumulados em `agent._session_usage` a cada `UsageEvent`.
- `/clear` **nao** zera os contadores — eles refletem o consumo real da
  sessao, util pra cobrancas.
- Antes do primeiro turn, o REPL mostra `no usage data tracked (will populate
  after first turn)`.
- Custos em USD nao sao calculados aqui; combine com a tabela de precos do
  provider.

---

## `/compact`

Resume o historico inteiro num unico paragrafo e descarta as mensagens
originais. Util para conversas longas que estao se aproximando do limite de
contexto.

**Sintaxe**

```text
/compact
```

**Exemplo de uso**

```text
> /compact
```

**O que voce ve**

```text
requesting summary...
history compacted
Discutimos a refatoracao de src/foo.py: o usuario pediu para extrair
a funcao parse_args para um modulo separado, decidimos manter os
argumentos posicionais, e ainda falta atualizar tests/test_foo.py.
```

**Notas**

- Faz uma chamada extra ao provider para gerar o resumo (consome tokens).
- O system prompt usado e `"You are a concise summarizer."`.
- Se o historico tem menos de 4 mensagens, o comando e no-op com
  `history too short to compact`.
- Apos compactar, `agent._messages` contem so duas entradas: um placeholder
  `<previous conversation summary>` e o resumo gerado.
- Em caso de erro no provider, mostra `compact failed: <exc>` e mantem o
  historico original.

---

## `/provider`

Sem argumentos, lista os providers conhecidos. Com argumento, troca o provider
ativo em runtime.

**Sintaxe**

```text
/provider           # lista
/provider <nome>    # troca
```

**Exemplo — listar**

```text
> /provider
+--------------+--------+
| Providers             |
+--------------+--------+
| name         | active |
+--------------+--------+
| anthropic    | *      |
| deepseek     |        |
| gemini       |        |
| groq         |        |
| internal-llm |        |
| lmstudio     |        |
| ollama       |        |
| openai       |        |
| openrouter   |        |
| vllm         |        |
+--------------+--------+
current: AnthropicProvider
```

**Exemplo — trocar**

```text
> /provider ollama
provider switched to ollama
```

**Notas**

- A configuracao usada para construir o novo provider vem de
  `config["providers"][<nome>]` (definida em `~/.vulpcode/config.toml`).
- O provider antigo e fechado via `aclose()` antes da troca.
- Em caso de falha (`Failed to build provider <nome>: ...`), o provider antigo
  permanece ativo.
- A lista de providers vem de `vulpcode.providers.list_provider_names()`.
- Veja tambem [Providers suportados](../providers/index.md) para credenciais e
  defaults de cada um.

---

## `/model`

Sem argumentos, tenta listar os modelos disponiveis no provider atual via
`provider.list_models()`. Com argumento, define `agent.model`.

**Sintaxe**

```text
/model              # lista
/model <id>         # troca
```

**Exemplo — listar (Anthropic)**

```text
> /model
+----------------------+--------+
| Models                        |
+----------------------+--------+
| name                 | active |
+----------------------+--------+
| claude-opus-4-7      |        |
| claude-sonnet-4-6    | *      |
| claude-haiku-4-5     |        |
+----------------------+--------+
```

**Exemplo — trocar**

```text
> /model claude-opus-4-7
model set to claude-opus-4-7
```

**Notas**

- Nem todo provider implementa `list_models()`. Quando nao implementa ou
  retorna lista vazia, voce ve
  `no models reported by provider; current: <model_atual>`.
- O comando **nao valida** se o id existe no provider — se voce errar, o
  proximo turn vai falhar com `model not found` (ou equivalente).
- Trocar modelo nao reseta o historico; o novo modelo continua a conversa.

---

## `/save`

Persiste a sessao atual em `~/.vulpcode/sessions/<nome>.json`.

**Sintaxe**

```text
/save               # salva como "default"
/save <nome>
```

**Exemplo de uso**

```text
> /save mytest
saved session to /home/usuario/.vulpcode/sessions/mytest.json
```

**Notas**

- Sem argumento, usa `default`.
- O arquivo armazena `agent._messages`, o nome do provider, o modelo e
  metadados — formato detalhado em [Sessoes](sessions.md).
- O diretorio e criado automaticamente.
- Voce pode salvar varias vezes com o mesmo nome — o ultimo `/save`
  sobrescreve.

---

## `/load`

Restaura uma sessao salva, sobrescrevendo o historico atual do agente.

**Sintaxe**

```text
/load               # carrega "default"
/load <nome>
```

**Exemplo de uso**

```text
> /load mytest
loaded session mytest
```

**O que voce ve em caso de erro**

```text
> /load nao-existe
error: no saved session named 'nao-existe'
```

**Notas**

- `/load` mexe no `agent._messages`. Considere fazer `/save` antes se a
  conversa atual for valiosa.
- Para retomar a sessao mais recente sem precisar saber o nome, use
  `vulp --resume`.
- Veja [Sessoes](sessions.md) para o formato do JSON e como editar a mao.

---

## `/mcp`

Lista os servidores MCP (Model Context Protocol) declarados no
`config.toml` e, se houver servers ativos, as tools que eles expoem.

**Sintaxe**

```text
/mcp
```

**Exemplo de uso**

```text
> /mcp
+----------+----------+--------------------+
| MCP servers                              |
+----------+----------+--------------------+
| name     | command  | args               |
+----------+----------+--------------------+
| filesys  | uvx      | mcp-server-filesys |
| github   | npx      | -y mcp-github      |
+----------+----------+--------------------+

+---------+--------------------------+
| MCP tools                          |
+---------+--------------------------+
| server  | tools                    |
+---------+--------------------------+
| filesys | read_file, list_dir      |
| github  | list_repos, create_issue |
+---------+--------------------------+
```

**Notas**

- Lista `config["mcp"]["servers"]`. Se a chave nao existe ou esta vazia, voce
  ve `no MCP servers configured`.
- A segunda tabela so aparece quando ha servers em execucao no momento (via
  `vulpcode.mcp.list_active_servers()`).
- Tools de MCP entram no agente com o nome `mcp__<server>__<tool>` — voce
  pode confirmar isso em `/tools`.
- Para configurar servidores MCP, veja [Como usar MCP](../mcp/index.md).

---

## Comandos desconhecidos

Se voce digita um comando que nao existe nem entre os builtins nem no registry,
o REPL responde:

```text
> /foo
unknown command: /foo
```

Sem matar o REPL. ++tab++ no `/` lista o que esta disponivel.
