# Guia do Usuario

Como usar o vulpcode no dia a dia: REPL, slash commands, modos de permissao e
sessoes persistentes.

## Topicos

- [Usando o REPL](using-the-repl.md) — anatomia da tela, input, historico,
  streaming de tokens e tool calls.
- [Slash commands](slash-commands.md) — referencia completa dos comandos
  `/help`, `/clear`, `/tools`, `/cost`, `/compact`, `/provider`, `/model`,
  `/save`, `/load`, `/mcp`.
- [Modos de permissao](permission-modes.md) — `default`, `--auto`, `--safe`,
  `--plan` e como o REPL pergunta antes de executar tools.
- [Sessoes e historico](sessions.md) — `/save`, `/load` e `--resume` para
  retomar conversas entre execucoes.

## Por onde comecar?

Se voce ja seguiu o [Quickstart](../getting-started/quickstart.md) e tem o
`vulp` rodando, [Usando o REPL](using-the-repl.md) e o proximo passo natural —
ele explica todo o ciclo de input, streaming e o que aparece na tela enquanto
o agente trabalha.

Se voce so precisa lembrar **o que cada slash command faz**, va direto para
[Slash commands](slash-commands.md).

## Cheat-sheet

| Acao                                  | Como                                |
| ------------------------------------- | ----------------------------------- |
| Iniciar REPL                          | `vulp`                              |
| Modo headless / one-shot              | `vulp --print "sua pergunta"`       |
| Aprovar tudo                          | `vulp --auto`                       |
| Pedir confirmacao ate em leituras     | `vulp --safe`                       |
| Plano sem executar tools              | `vulp --plan`                       |
| Retomar a ultima sessao               | `vulp --resume`                     |
| Sair do REPL                          | `/exit`, `/quit` ou ++ctrl+d++      |
| Limpar contexto (sem fechar)          | `/clear`                            |
| Ver tokens da sessao                  | `/cost`                             |
| Listar comandos                       | `/help`                             |
