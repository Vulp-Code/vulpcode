# Modos de permissao

Toda chamada de tool no vulpcode passa por um `PermissionManager` antes de
executar. O modo de permissao decide **se a tool roda direto, se voce e
perguntado, ou se a execucao esta inteiramente desligada**.

> Implementacao em [`src/vulpcode/permissions.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/permissions.py).
> Wiring entre CLI e manager em [`src/vulpcode/app.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/app.py).

---

## Visao geral

Quatro modos, exclusivos entre si, escolhidos por flag no `vulp`:

| Modo      | Flag CLI   | Read / Glob / Grep | Write | Edit / MultiEdit | Bash / KillBash | NotebookEdit | Outras (nao-destrutivas) |
|-----------|------------|--------------------|-------|-------------------|------------------|--------------|---------------------------|
| `default` | (sem flag) | OK                 | pede  | pede              | pede             | pede         | OK                        |
| `auto`    | `--auto`   | OK                 | OK    | OK                | OK               | OK           | OK                        |
| `safe`    | `--safe`   | pede               | pede  | pede              | pede             | pede         | pede                      |
| `plan`    | `--plan`   | NAO                | NAO   | NAO               | NAO              | NAO          | NAO                       |

- **OK** = roda sem perguntar.
- **pede** = aparece o prompt `[permission]` (a menos que esteja na allowlist).
- **NAO** = a tool nunca executa; o agente recebe um `ToolDeniedEvent`.

Os nomes dos modos sao os valores literais do enum
[`Mode`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/permissions.py)
(`default`, `auto`, `safe`, `plan`) — sempre em ingles, mesmo na config.

---

## Quais tools sao destrutivas?

A flag por classe e `requires_confirm=True` no decorator `@tool(...)`. Hoje sao
**seis** tools nativas:

| Tool           | Arquivo                                                                                                          | Por que pede confirmacao                |
|----------------|------------------------------------------------------------------------------------------------------------------|------------------------------------------|
| `Bash`         | [`tools/bash.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/tools/bash.py)                     | executa shell arbitrario                 |
| `KillBash`     | [`tools/bash_background.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/tools/bash_background.py) | termina processo background              |
| `Write`        | [`tools/write.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/tools/write.py)                   | cria/sobrescreve arquivo                 |
| `Edit`         | [`tools/edit.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/tools/edit.py)                     | substitui texto em arquivo               |
| `MultiEdit`    | [`tools/edit.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/tools/edit.py)                     | aplica varias edicoes atomicamente       |
| `NotebookEdit` | [`tools/notebook.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/tools/notebook.py)             | modifica celulas de `.ipynb`             |

As demais (`Read`, `Glob`, `Grep`, `TodoWrite`, `Task`, `WebFetch`, `WebSearch`,
`BashOutput`) tem `requires_confirm=False` e passam direto no modo `default`.

Para auditar a lista atual:

```bash
grep -rn "requires_confirm=True" src/vulpcode/tools/
```

---

## Modo `default`

Modo selecionado quando nenhuma flag e passada. Tools nao-destrutivas rodam em
silencio; tools destrutivas pausam o spinner e perguntam.

```text
[permission] Tool 'Write' wants to run.
Tool args: {'file_path': '/tmp/x.txt', 'content': '...'}
[y] yes once  [a] always for this tool  [n] no
```

Tres respostas possiveis:

| Resposta | Comportamento                                                                                                                                              |
|----------|------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `y`      | aprova **so esta chamada**. Se a mesma tool aparecer de novo no mesmo turn ou no proximo, voce sera perguntado outra vez.                                   |
| `a`      | aprova e adiciona a tool ao **session allowlist**. Toda chamada subsequente desta tool nesta sessao passa direto. A allowlist e perdida quando o REPL sai. |
| `n`      | recusa. O agente recebe um `ToolDeniedEvent` com `reason="user rejected"` e tipicamente reformula a abordagem.                                              |

Qualquer outra entrada (incluindo Enter vazio) e tratada como `n` — veja
`stdin_prompter` em [`permissions.py:35-45`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/permissions.py#L35).

> O prompt aparece **sem o spinner ativo** porque o `streaming.py` instala um
> wrapper `_spinner_aware_prompter` que para o `Live` do Rich antes de chamar
> `stdin_prompter`, e religa depois. Sem isso, o spinner sobrescreveria a sua
> resposta enquanto voce digita. Veja [`ui/streaming.py:50-95`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/ui/streaming.py#L50).

---

## Modo `auto` (`--auto`)

```bash
vulp --auto
```

`PermissionManager.check()` retorna `allow=True` para tudo, sem perguntar e
sem consultar o allowlist. Use quando:

- voce ja revisou o pedido e confia no que vai acontecer;
- esta rodando em pipeline / CI / `--print` headless onde nao ha humano para responder;
- a tarefa e repetitiva e voce esta combinando com `--print`:

```bash
vulp --print --auto "rode os testes unitarios e me diga se algum falhou"
```

!!! warning "Nunca use `--auto` com input nao confiavel"
    Em `--auto`, o agente pode executar `Bash`, `Write`, `Edit` em qualquer
    arquivo do seu sistema — incluindo apagar dados. Nao exponha esse modo a
    chat publico, webhook nao autenticado, ou qualquer fluxo onde o prompt
    venha de fora.

---

## Modo `safe` (`--safe`)

```bash
vulp --safe
```

Forca `requires=True` para **todas** as tools, inclusive `Read`, `Glob`,
`Grep`. Voce vai responder `y`/`a`/`n` para cada chamada. Util para:

- **Auditoria** — voce quer ver cada interacao do agente com o sistema antes
  dela acontecer.
- **Demo para terceiros** — mostrar como o agente pensa sem dar a ele
  movimento livre.
- **Quando voce ainda nao confia no agente** — primeiros minutos com um
  provider/modelo novo.

A allowlist continua valendo: aperte `a` em `Read` na primeira vez e ele para
de pedir para esse comando.

---

## Modo `plan` (`--plan`)

```bash
vulp --plan
```

`PermissionManager.check()` retorna `allow=False` com
`reason="plan mode (no execution)"` para **toda** chamada de tool. Nada e
executado. O agente recebe `ToolDeniedEvent` em sequencia e tipicamente
descreve em texto o que faria. Use para:

- **Pedir um plano antes de executar** — depois saia, abra um REPL normal e
  rode os passos manualmente ou com `--auto`.
- **Dry-run** — descobrir quais tools seriam usadas sem efeito colateral.
- **Brainstorm puro** — quando voce so quer conversar com o modelo.

---

## Allowlist persistente: `always_allow_tools`

Para evitar apertar `a` toda sessao, declare a allowlist no
`~/.vulpcode/config.toml`:

```toml
[permissions]
always_allow_tools = ["Read", "Glob", "Grep"]
```

Como funciona:

- Lido em [`permissions.py:60-62`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/permissions.py#L60)
  durante o construtor do `PermissionManager`.
- O conteudo e copiado para `_session_allowlist` no inicio de cada sessao.
- Equivale a apertar `a` em cada uma dessas tools assim que apareceriam.
- **Nao tem efeito em `--plan`** (que rejeita tudo) e **e redundante em `--auto`**
  (que aprova tudo).
- Em `--safe`, faz sentido: voce pode pre-aprovar `Read` e ainda pedir
  confirmacao para o resto.

> Use nomes exatos do registry (`Read`, nao `read`). A comparacao em
> `permissions.py:80` e case-sensitive.

Para abrir o `config.toml` rapido:

```bash
vulp config   # abre em $EDITOR
```

---

## Padrao de uso recomendado

| Perfil                          | Comando                          | Quando                                                      |
|---------------------------------|-----------------------------------|--------------------------------------------------------------|
| **Iniciante**                   | `vulp`                            | Modo `default` — o sistema te ensina o que cada tool faz.    |
| **Desenvolvedor confiante**     | `vulp --auto`                     | Voce ja conhece o agente e quer fluxo continuo.              |
| **Desenvolvedor cauteloso**     | `vulp` + `always_allow_tools`     | `default` com leituras pre-aprovadas; so escrita pergunta.   |
| **Demo / apresentacao**         | `vulp --safe`                     | Cada acao pausa para o publico ver e voce aprovar.           |
| **Brainstorm / planejamento**   | `vulp --plan`                     | Conversar sem deixar o agente tocar no sistema.              |
| **CI / script headless**        | `vulp --print --auto "..."`       | Sem TTY, sem spinner, sem prompt.                            |

Combine livremente com `--provider`, `--model` e `--resume` — modos de
permissao sao ortogonais ao resto da CLI.

---

## Como o REPL informa uma negacao

Quando uma tool e negada (por `n`, por `--plan`, ou por erro do prompter), o
agente emite um `ToolDeniedEvent` com a `reason` retornada pelo
`PermissionManager`:

```text
Tool 'Bash' denied: user rejected
Tool 'Write' denied: plan mode (no execution)
Tool 'Edit' denied: prompt failed
```

Renderizado em amarelo pelo `Renderer.render_tool_denied`. O agente pode
continuar o turn e escolher outra abordagem — uma negacao **nao termina** o
loop; apenas substitui o resultado da tool por um marcador de denegacao no
contexto.

---

## Proximos passos

- [Sessoes e historico](sessions.md) — como `--resume` e `/save` interagem
  com a allowlist (resposta curta: nao interagem; allowlist nao e persistida).
- [Slash commands](slash-commands.md) — `/tools` lista quais tools estao no
  registry da sessao atual.
- Codigo: `Mode` e `PermissionManager` em
  [`src/vulpcode/permissions.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/permissions.py).
