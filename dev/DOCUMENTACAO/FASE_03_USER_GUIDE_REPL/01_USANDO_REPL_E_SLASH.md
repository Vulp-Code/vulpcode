# Tarefa 03.01 - Usando o REPL + Slash Commands

**Status**: PENDENTE
**Fase**: 03 - User Guide
**Dependencias**: 02.03
**Bloqueia**: 03.02

---

## Objetivo

Criar duas paginas:
- `user-guide/index.md` (indice da secao)
- `user-guide/using-the-repl.md` (uso do REPL)
- `user-guide/slash-commands.md` (todos os slash commands)

---

## Arquivos a criar

- `docs/user-guide/index.md`
- `docs/user-guide/using-the-repl.md`
- `docs/user-guide/slash-commands.md`

---

## Source de verdade

- `src/vulpcode/ui/repl.py` — `Repl` class, `_DEFAULT_SLASH_COMMANDS`
- `src/vulpcode/commands/__init__.py` — `build_default_commands()`
- `src/vulpcode/commands/_base.py` — `SlashCommand` ABC
- `src/vulpcode/commands/*.py` — uma classe por comando
- `src/vulpcode/ui/streaming.py` — fluxo de eventos visuais
- `src/vulpcode/ui/render.py` — renderer Rich
- `src/vulpcode/cli.py` — flags

---

## Conteudo de `user-guide/index.md`

Indice/landing da secao com 5 cards:

```markdown
# Guia do Usuario

Como usar o vulpcode no dia a dia.

- [Usando o REPL](using-the-repl.md) — input multi-linha, historico, streaming.
- [Slash commands](slash-commands.md) — referencia completa.
- [Modos de permissao](permission-modes.md) — `default`, `--auto`, `--safe`, `--plan`.
- [Sessoes e historico](sessions.md) — `/save`, `/load`, `--resume`.
```

---

## Conteudo de `user-guide/using-the-repl.md`

Cobrir:

1. **Iniciar o REPL**: `vulp` (default), `vulp --auto`, `vulp --provider X`.
2. **Anatomia da tela**: prompt `>`, painel de tool call (titulo + JSON dos args),
   painel de tool result (verde=ok, vermelho=erro), linha de tokens (`tokens: in=N out=M`),
   stop_reason em cinza ao fim.
3. **Input**:
   - Linha unica: digite + Enter
   - Multi-linha: actualmente nao suportado nativo (mencione como limitacao)
   - Historico persistente em `~/.vulpcode/history`
   - Setas ↑/↓ navegam historico
   - Ctrl+R busca no historico
   - Tab autocompleta `/comandos`
4. **One-shot vs interativo**:
   - `vulp "diga oi"` — ja entra em modo one-shot/interativo dependendo do tty
   - `vulp --print "diga oi"` — modo headless (apenas stdout, sem spinner)
5. **Permissao em runtime**: como responder `y`/`a`/`n` quando aparece `[permission]`.
   Explicar que o spinner pausa para o prompt aparecer limpo.
6. **Streaming visual**: tokens chegam progressivamente; tool calls aparecem em
   panels Rich; ao final do turn, linha de uso de tokens.
7. **Sair**: `/exit`, `/quit`, `Ctrl+D`, `Ctrl+C` (interrompe turn atual).

---

## Conteudo de `user-guide/slash-commands.md`

Referencia completa, uma secao por comando. Itens sao auto-descobertos via
`build_default_commands()`. Lista atual:

| Comando             | Argumentos    | Funcao                                      |
|---------------------|---------------|---------------------------------------------|
| `/help`             | -             | Lista comandos                              |
| `/clear`            | -             | Apaga historico do contexto (nao da tela)   |
| `/exit` ou `/quit`  | -             | Sai do REPL                                 |
| `/tools`            | -             | Tabela de tools registradas                 |
| `/cost`             | -             | Tokens acumulados na sessao                 |
| `/compact`          | -             | Resume historico para economizar contexto   |
| `/provider`         | `[nome]`      | Lista ou troca o provider ativo             |
| `/model`            | `[nome]`      | Lista ou troca o modelo ativo               |
| `/save`             | `<nome>`      | Salva sessao em `~/.vulpcode/sessions/`     |
| `/load`             | `<nome>`      | Carrega sessao salva                        |
| `/mcp`              | -             | Lista servidores MCP configurados           |

Para cada comando, escrever uma secao com:
- O que faz
- Sintaxe (`/comando [args]`)
- Exemplo de uso
- O que o usuario ve em retorno
- Notas de comportamento (ex: `/clear` reseta `agent._messages` mas nao apaga
  a tela)

---

## Atualizar `mkdocs.yml`

Adicionar bloco `Guia do Usuario`:

```yaml
nav:
  - Home: index.md
  - Comece aqui:
      - getting-started/index.md
      - Instalacao: getting-started/installation.md
      - Quickstart: getting-started/quickstart.md
      - Primeira configuracao: getting-started/first-config.md
      - Conceitos principais: getting-started/core-concepts.md
  - Guia do Usuario:
      - user-guide/index.md
      - Usando o REPL: user-guide/using-the-repl.md
      - Slash commands: user-guide/slash-commands.md
      - Modos de permissao: user-guide/permission-modes.md       # 03.02
      - Sessoes: user-guide/sessions.md                          # 03.03
```

---

## INSTRUCAO CRITICA

- Confira a lista REAL de slash commands em `commands/__init__.py` (`build_default_commands`)
  e `ui/repl.py` (`_DEFAULT_SLASH_COMMANDS`) — pode ter mudado.
- `/help`, `/clear`, `/exit`, `/quit` sao **builtins do Repl** (em `_handle_slash`),
  nao comandos do registry. Os outros vem do registry.
- Mostre exemplos reais. Para `/save mytest`, o resultado e `saved session to
  /home/.../.vulpcode/sessions/mytest.json`.

---

## Etapas de Implementacao

### Etapa 1: Ler `commands/`, `ui/repl.py`, `ui/streaming.py`
### Etapa 2: Criar 3 arquivos `user-guide/*.md`
### Etapa 3: Atualizar `mkdocs.yml`
### Etapa 4: `mkdocs build`

---

## Criterios de Aceite

- [x] `docs/user-guide/index.md` criado com indice
- [x] `docs/user-guide/using-the-repl.md` criado cobrindo: anatomia da tela, input, historico, one-shot vs interativo, prompt de permissao, sair
- [x] `docs/user-guide/slash-commands.md` criado com tabela de comandos + secao por comando (>=11 comandos)
- [x] `mkdocs.yml` atualizado com bloco "Guia do Usuario"
- [x] Lista de comandos bate com `commands/__init__.py` e builtins do `Repl._handle_slash`
- [x] `mkdocs build` continua passando

---

## Riscos

| Risco | Mitigacao |
|-------|-----------|
| Slash command renomeado | Reler `commands/` antes de fechar |
| Comportamento real divergir do documentado | Testar comandos no REPL durante a escrita |

---

**End of Specification**
