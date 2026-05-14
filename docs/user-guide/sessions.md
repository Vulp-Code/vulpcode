# Sessoes e historico

O vulpcode mantem **dois historicos diferentes** com proposito e ciclo de vida
distintos. Esta pagina explica cada um, mostra como salvar/carregar uma
conversa com o LLM, como retomar a sessao mais recente com `--resume` e como
encolher o contexto com `/compact`.

> Implementacao em
> [`src/vulpcode/session.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/session.py),
> [`src/vulpcode/commands/session_cmds.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/commands/session_cmds.py),
> [`src/vulpcode/commands/compact.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/commands/compact.py)
> e [`src/vulpcode/app.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/app.py).

---

## Dois historicos diferentes

Nao confunda esses dois — eles vivem em arquivos diferentes e respondem a
comandos diferentes.

| Historico                  | O que armazena                         | Onde fica                          | Quem gerencia              | Como interagir                       |
| -------------------------- | -------------------------------------- | ---------------------------------- | -------------------------- | ------------------------------------ |
| **Linhas que voce digitou** | input bruto do prompt (plain text)     | `~/.vulpcode/history`              | `prompt_toolkit.FileHistory` | ++up++ / ++down++, ++ctrl+r++        |
| **Conversa com o LLM**     | `Message` objects do agente            | memoria + JSON via `/save`         | `Agent._messages`          | `/save`, `/load`, `--resume`         |

O primeiro **persiste sempre** entre execucoes do `vulp` — o `prompt_toolkit`
le e escreve o arquivo automaticamente
([`repl.py:33`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/ui/repl.py#L33)).
O segundo so persiste se voce explicitamente **salva** uma sessao.

---

## `/save` e `/load`

Persistem o estado do agente em `~/.vulpcode/sessions/<nome>.json`.

```text
> /save trabalho-backup
saved session to /home/usuario/.vulpcode/sessions/trabalho-backup.json

> /clear
history cleared

> /load trabalho-backup
loaded session trabalho-backup
```

Sem argumento, ambos operam sobre o nome `default`:

```text
> /save               # equivalente a /save default
> /load               # equivalente a /load default
```

Em caso de nome inexistente, `/load` reporta o erro **sem** bagunçar o
historico atual:

```text
> /load nao-existe
error: no saved session named 'nao-existe'
```

### Sanitizacao de nomes

A funcao `_safe_name()` filtra o nome para conter **apenas** caracteres
alfanumericos e `-`/`_`. Tudo o mais e descartado. Se o resultado ficar vazio,
vira `"default"`.

```python
_safe_name("trabalho/backup #1")   # -> "trabalhobackup1"
_safe_name("!!!")                  # -> "default"
```

Ou seja: `/save trabalho/backup #1` grava em `trabalhobackup1.json`. Para
evitar surpresas, use so `[A-Za-z0-9_-]`.

### Formato do arquivo JSON

Versao atual: `_VERSION = 1`. Estrutura completa de
`~/.vulpcode/sessions/<nome>.json`:

```json
{
  "version": 1,
  "name": "trabalho-backup",
  "saved_at": "2026-05-06T15:00:00",
  "provider_name": "anthropic",
  "model": "claude-sonnet-4-6",
  "system": "You are a helpful coding assistant...",
  "messages": [
    {"role": "user", "content": "liste os .py em /tmp"},
    {"role": "assistant", "content": "..."}
  ],
  "session_usage": {
    "input_tokens": 1234,
    "output_tokens": 567,
    "cache_read_input_tokens": 0,
    "cache_creation_input_tokens": 0
  }
}
```

| Campo            | Origem (em `Agent`)                  | Observacao                                     |
| ---------------- | ------------------------------------ | ---------------------------------------------- |
| `version`        | constante `_VERSION`                 | Atualmente `1`                                 |
| `name`           | argumento de `/save`                 | Nome **antes** da sanitizacao do path          |
| `saved_at`       | `datetime.now().isoformat(...)`      | Hora local do host, sem timezone               |
| `provider_name`  | `agent.provider.name`                | Ex.: `anthropic`, `openai`, `ollama`           |
| `model`          | `agent.model`                        | Id do modelo ativo                             |
| `system`         | `agent.system`                       | System prompt                                  |
| `messages`       | `agent._messages`                    | Lista serializada via `model_dump()`           |
| `session_usage`  | `agent._session_usage`               | `null` se ainda nao houve turn                 |

A escrita e atomica: o conteudo vai para `<nome>.json.tmp` e e renomeado para
`<nome>.json` — um `Ctrl+C` durante `/save` nao corrompe arquivos existentes.

> **Aviso**: `load_session` aplica `system` e `model` do JSON sobre o agente,
> ou seja, **carregar uma sessao pode trocar o modelo**. Se voce mudou de
> modelo via `/model` e quer manter, salve novamente apos carregar.

---

## `--resume`

Atalho da CLI que carrega a sessao **mais recente por mtime**, sem voce
precisar lembrar o nome:

```bash
vulp --resume         # ou vulp -r
```

Saidas possiveis logo apos o banner:

```text
Vulpcode REPL  (type /help for commands, /exit to quit)
resumed session trabalho-backup
>
```

Ou, se a pasta de sessoes esta vazia:

```text
no saved session to resume
```

Internamente, `app.start_repl(resume=True)` chama
`latest_session_name()` (= primeiro item de `list_sessions()`, ordenado por
`mtime` decrescente) e em seguida `load_session(...)`.

> Util para "fechei o terminal sem querer, quero continuar de onde parei".
> Para escolher uma sessao especifica, abra o REPL normalmente e use
> `/load <nome>`.

---

## Listar e excluir programaticamente

A CLI ainda **nao** expoe um `vulp sessions list`, mas o modulo
`vulpcode.session` oferece a API publica:

```python
from vulpcode.session import list_sessions, delete_session

for s in list_sessions():
    print(s["name"], s["saved_at"], s["messages"], s["model"])
# trabalho-backup 2026-05-06T15:00:00 12 claude-sonnet-4-6
# rascunho        2026-05-06T11:42:11  4 gpt-4o-mini

delete_session("rascunho")   # True se removeu, False se nao existia
```

Cada item retornado por `list_sessions()` e um dict com:

| Chave       | Tipo          | Descricao                                        |
| ----------- | ------------- | ------------------------------------------------ |
| `name`      | `str`         | Nome original gravado no JSON                    |
| `saved_at`  | `str` (ISO)   | Timestamp de quando foi salvo                    |
| `messages`  | `int`         | Quantidade de mensagens no historico             |
| `model`     | `str`         | Id do modelo no momento do `/save`               |
| `path`      | `str`         | Caminho absoluto do `.json`                      |

Arquivos com JSON corrompido sao silenciosamente pulados (try/except em
`list_sessions()`).

Para inspecionar diretamente:

```bash
ls -lt ~/.vulpcode/sessions/
cat ~/.vulpcode/sessions/trabalho-backup.json | jq '.messages | length'
```

---

## `/compact`

Sumariza o historico atual usando o **proprio LLM** e substitui as mensagens
originais por uma versao condensada. Util quando o turno fica longo e o
contexto comeca a ficar caro.

```text
> /compact
requesting summary...
history compacted
Discutimos a refatoracao de src/foo.py: o usuario pediu para extrair
a funcao parse_args para um modulo separado, decidimos manter os
argumentos posicionais, e ainda falta atualizar tests/test_foo.py.
```

O que acontece por baixo:

1. Se `len(agent._messages) < 4`, e no-op (`history too short to compact`).
2. Faz uma chamada extra ao provider com system prompt
   `"You are a concise summarizer."` e instrucao para preservar paths,
   decisoes e TODOs.
3. Substitui `agent._messages` por **duas** entradas:
    - `{"role": "user", "content": "<previous conversation summary>"}`
    - `{"role": "assistant", "content": <resumo gerado>}`
4. Se o provider falha, mostra `compact failed: <exc>` e **mantem** o
   historico original.

> **Aviso**: detalhes podem ser perdidos no resumo. Se a conversa for
> delicada, faca `/save` antes — ai voce pode `/load` se o resumo descartar
> algo importante.

---

## Boas praticas

- **Salve antes de `/compact` ou `/clear`.** Os dois sao destrutivos para o
  historico em memoria; um `/save backup-pre-compact` te da um plano de
  rollback.
- **Use nomes curtos e simples.** A sanitizacao
  ([`_safe_name`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/session.py#L23))
  permite apenas alfanumerico, `-` e `_`. Espaços, `/` e acentos viram
  silenciosamente outro nome de arquivo.
- **Nao commite `~/.vulpcode/sessions/`.** O `.gitignore` do projeto ja
  ignora todo o diretorio `.vulpcode/` — sessoes podem conter trechos de
  codigo, paths absolutos da sua maquina e ate caracteres sensiveis que voce
  colou no prompt.
- **Sessoes servem para auditoria.** Como o JSON contem o historico completo
  de mensagens (incluindo tool calls), e util para rastrear depois "o que o
  agente fez na terca passada quando me pediu para deletar `X`?". Para isso,
  habitue-se a `/save` ao final de tarefas relevantes.
- **`--resume` so retoma a ultima sessao salva.** Se voce sai do REPL sem
  `/save`, perde o historico em memoria — `~/.vulpcode/history` so guarda as
  linhas que voce digitou, nao as respostas do modelo.

---

## Referencia rapida

| Acao                                       | Como                                |
| ------------------------------------------ | ----------------------------------- |
| Salvar sessao atual                        | `/save <nome>`                      |
| Carregar uma sessao salva                  | `/load <nome>`                      |
| Retomar a mais recente ao iniciar          | `vulp --resume` (ou `-r`)           |
| Resumir o historico em duas mensagens      | `/compact`                          |
| Apagar o historico em memoria              | `/clear`                            |
| Listar sessoes                             | `list_sessions()` em Python         |
| Excluir uma sessao                         | `delete_session(<nome>)` em Python  |
| Inspecionar arquivos de sessao             | `ls ~/.vulpcode/sessions/`          |
| Inspecionar historico de comandos          | `cat ~/.vulpcode/history`           |

Veja tambem:

- [Slash commands](slash-commands.md#save) — referencia individual de
  `/save`, `/load`, `/compact`, `/clear`.
- [Usando o REPL](using-the-repl.md#input) — atalhos do `prompt_toolkit` e
  navegacao no historico de comandos.
- [Modos de permissao](permission-modes.md) — combinar `--resume` com
  `--auto`/`--safe`/`--plan`.
