# Quickstart

Tutorial de 5 minutos: do zero ate um agente respondendo no terminal e
executando tools. Voce vai usar dois modos do CLI (one-shot e REPL) e trocar
de provider em runtime.

> **Pressuposto**: Voce ja tem o `vulp` instalado. Se nao, volte para
> [Instalacao](installation.md).

---

## Passo 1 — Confirmar instalacao

```bash
vulp --version
# vulpcode 0.1.0
```

Se voce ve a versao, esta pronto. Caso contrario, [revise a instalacao](installation.md).

---

## Passo 2 — Configurar uma chave de API

Vulpcode descobre credenciais em duas ordens: variaveis de ambiente **ou**
`~/.vulpcode/config.toml`. O caminho mais rapido e variavel de ambiente.

Escolha **um** provider para comecar:

=== "Anthropic (Claude)"

    ```bash
    export ANTHROPIC_API_KEY=sk-ant-...
    ```

    Cole no `~/.bashrc`/`~/.zshrc` para tornar permanente.

=== "OpenAI"

    ```bash
    export OPENAI_API_KEY=sk-...
    ```

=== "Gemini"

    ```bash
    export GEMINI_API_KEY=AIza...
    # ou GOOGLE_API_KEY — ambos sao reconhecidos
    ```

=== "Ollama (local, sem API key)"

    Em outro terminal, deixe rodando:

    ```bash
    ollama serve
    ollama pull qwen2.5-coder:7b
    ```

    Nada precisa ser exportado: o Vulpcode fala HTTP com o daemon em
    `http://localhost:11434`.

Outras opcoes (`DEEPSEEK_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`) tambem
sao reconhecidas — veja a [pagina de cada provider](#proximos-passos).

---

## Passo 3 — Primeiro chat one-shot

O modo `--print` roda o agente, imprime a resposta em stdout e sai. Combinado
com `--auto`, todas as tools sao aprovadas automaticamente (perfeito para
scripts):

```bash
vulp --print --auto "diga oi em uma palavra"
```

Saida esperada:

```
oi
```

> Se voce nao definiu um provider em `config.toml`, o Vulpcode escolhe o
> primeiro com chave disponivel. Force com `--provider`:
>
> ```bash
> vulp --provider anthropic --print --auto "diga oi"
> ```

---

## Passo 4 — REPL interativo

Sem `--print`, o `vulp` abre um REPL com prompt-toolkit, autocomplete de slash
commands e historico persistente em `~/.vulpcode/history`:

```bash
vulp --auto
```

Voce vera algo como:

```
Vulpcode REPL  (type /help for commands, /exit to quit)
> liste os arquivos em /tmp em ordem alfabetica
```

O agente vai chamar a tool `Bash` (ou `Read`/`Glob`, dependendo do modelo) e
mostrar o resultado.

Comandos uteis dentro do REPL:

```text
> /tools
> /cost
> /help
> /exit
```

`/tools` mostra a lista de ferramentas disponiveis; `/cost` resume tokens e
custo da sessao; `/help` lista todos os slash commands.

---

## Passo 5 — Pedir para criar um arquivo

Os tools de escrita exigem aprovacao por padrao. Com `--auto`, o agente cria o
arquivo direto:

```text
> use a tool Write para criar /tmp/teste.txt com "hello vulpcode"
```

Confira:

```bash
cat /tmp/teste.txt
# hello vulpcode
```

> Sem `--auto`, o REPL pergunta antes de cada escrita. Modo `--safe` exige
> confirmacao ate para leituras (`Read`, `Glob`).

---

## Passo 6 — Trocar de provider em runtime

No REPL, voce pode trocar de provider e modelo a qualquer momento:

```text
> /provider ollama
provider switched to ollama
> /model qwen2.5-coder:7b
model set to qwen2.5-coder:7b
> escreva uma funcao Python que inverte uma string
```

Sem argumentos, `/provider` e `/model` listam as opcoes:

```text
> /provider
+--------------+--------+
| name         | active |
+--------------+--------+
| anthropic    |        |
| deepseek     |        |
| gemini       |        |
| groq         |        |
| internal-llm |        |
| lmstudio     |        |
| ollama       | *      |
| openai       |        |
| openrouter   |        |
| vllm         |        |
+--------------+--------+
```

---

## Resumo das flags do CLI

| Flag                    | Efeito                                               |
| ----------------------- | ---------------------------------------------------- |
| `--provider, -p <name>` | Force um provider                                    |
| `--model, -m <id>`      | Force um modelo                                      |
| `--print`               | Modo headless (stdout-only, sai apos resposta)       |
| `--resume, -r`          | Retome a ultima sessao                               |
| `--auto`                | Aprove todas as tool calls automaticamente           |
| `--safe`                | Pergunte antes de qualquer tool, mesmo leituras      |
| `--plan`                | Modo planejamento (sem execucao real de tools)       |
| `--version, -V`         | Imprime a versao e sai                               |

E os subcomandos:

| Subcomando      | Efeito                                       |
| --------------- | -------------------------------------------- |
| `vulp config`   | Abre `~/.vulpcode/config.toml` no `$EDITOR`  |
| `vulp providers`| Lista providers conhecidos                   |
| `vulp models`   | Lista modelos do provider atual (FASE 03)    |

---

## Proximos passos

- [Primeira configuracao](first-config.md) — gerar o `config.toml`, definir
  provider default, perfis e timeouts.
- [Conceitos principais](core-concepts.md) — o ciclo agente -> tool -> resposta,
  permissoes, sessoes.
- [Slash commands](../user-guide/slash-commands.md) — referencia completa de
  `/provider`, `/model`, `/cost`, `/compact`, `/save`, `/load`, `/mcp`.
