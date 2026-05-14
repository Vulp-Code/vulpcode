# Revisar pull request

> **Cenario**: voce vai revisar um PR de outra pessoa e quer um diagnostico
> rapido com bullets acionaveis.
> **Tempo estimado**: 10-20 minutos para um PR pequeno-medio.
> **Provider recomendado**: Anthropic (Claude Sonnet/Opus) — qualidade alta
> em revisao critica e bom controle de tom. OpenAI (`gpt-5`) tambem
> funciona bem; Ollama serve quando o codigo nao pode sair da maquina.

## Contexto

Code review feito a mao costuma travar entre "ler o diff" e "escrever o
comentario". O agente faz a leitura sequencial dos arquivos, executa testes e
linters, e devolve uma sintese pronta para colar no GitHub. Voce ainda decide
o que vai pro comentario — o agente apenas tira o atrito.

## Passos

### 1. Checkout do PR

```bash
gh pr checkout 123
cd /caminho/do/repo
```

> Sem o `gh` CLI? Use `git fetch origin pull/123/head:pr-123 && git checkout pr-123`.

### 2. Iniciar o REPL em modo `--auto`

```bash
vulp --auto
```

`--auto` aprova as tools sem perguntar, o que e seguro **localmente** e
acelera o fluxo. Se preferir granularidade, use o modo `default` e digite
`a` para "always" nas tools que voce confia. Veja
[Modos de permissao](../user-guide/permission-modes.md).

### 3. Resumo das mudancas

```text
> resuma as mudancas dessa branch comparado a main: rode `git log main..HEAD --oneline` e depois leia os arquivos modificados (use `git diff --name-only main...HEAD` para listar). responda com 1) one-liner do PR, 2) lista de arquivos tocados agrupados por area, 3) intencao de cada commit.
```

O agente vai usar `Bash` (para `git log` e `git diff`) e `Read` para abrir os
arquivos. Se ele tentar abrir um diff gigantesco, interrompa com ++esc++ e
peca uma versao mais focada.

### 4. Code review focado

```text
> faca um code review focando em: bugs potenciais, edge cases nao tratados, design questionavel, mudancas que quebram contrato publico, e seguranca. seja conciso. liste como bullets agrupados por arquivo. ignore estilo se houver linter automatico.
```

Pedir para "ignorar estilo" evita ruido — `ruff`/`black` ja fazem isso. O
agente fica livre para focar no que importa.

### 5. Rodar testes e linters

```text
> rode os testes (pytest -q) e me diga se algum falha. depois rode `ruff check .` e `mypy src/` se estiverem configurados (cheque pyproject.toml e setup.cfg primeiro). resuma falhas por categoria.
```

Pedir o `pyproject.toml` antes evita o agente inventar comandos. Se o repo
usa Makefile (`make test`), troque por isso.

### 6. Procurar pegadinhas em git

```text
> rode `git diff main...HEAD -- 'src/**/migrations/*.py'` e `git diff main...HEAD -- 'pyproject.toml' 'requirements*.txt'`. me alerte sobre: novas dependencias, mudancas de schema, changes em CI (.github/workflows/), arquivos grandes binarios.
```

Esses sao os tres focos que costumam passar batido em review.

### 7. Comentario para colar no GitHub

```text
> escreva um comentario de review em portugues, em formato markdown, com tres secoes: 1) o que esta bom (1-2 bullets), 2) sugestoes nao-bloqueadoras (lista numerada com arquivo:linha), 3) bloqueadores (apenas se houver). use tom colaborativo, primeira pessoa do plural ("podemos", "vamos"). nao inclua o codigo na resposta — so o comentario.
```

> Pedir explicitamente "primeira pessoa do plural" estabiliza o tom. Sem
> isso, o agente as vezes solta um "you should" agressivo.

Copie a resposta e cole em `gh pr comment 123 --body-file -` ou na UI.

---

## Variantes

### PRs grandes (50+ arquivos)

Use o subagente [`Task`](../tools/agent.md) para quebrar a revisao por area:

```text
> use a tool Task com subagent_type="Explore" para revisar src/api/ separadamente, e outra Task para revisar src/db/. depois consolide os achados.
```

Cada subagente roda com contexto isolado, evitando estourar o
[token budget](../user-guide/using-the-repl.md). Veja
[`tools/agent.md`](../tools/agent.md) para limites.

### Comparar Claude vs Ollama

Roda a mesma sessao com o codigo localmente para validacao cruzada (ou
quando o repo nao pode sair da maquina):

```bash
vulp --auto --provider anthropic --model claude-sonnet-4-5
# salve o resumo
> /save review-claude
# troque o provider e refaca
> /provider ollama
> /model qwen2.5-coder:7b
```

Compare os dois reviews — se Claude flagar algo que Ollama nao pegou (ou
vice-versa), provavelmente vale investigar.

### Review com `--plan`

Quando voce quer **so o plano de revisao** sem que o agente execute nada
(util em CI ou quando voce so quer roteiro):

```bash
vulp --plan
> proponha um roteiro de revisao para esse PR. nao execute nada.
```

No modo `--plan`, **nenhuma tool roda** — nem mesmo `Read`/`Grep`. Veja
[Modos de permissao](../user-guide/permission-modes.md).

---

## Anti-patterns / armadilhas

- **Pedir "revise o PR" sem mais contexto**: o agente pode perder tempo
  reabrindo arquivos nao tocados. Sempre limite o escopo com `git diff`
  ou `git log main..HEAD`.
- **Cole o diff inteiro no prompt**: estoura o `max_tokens` rapido,
  especialmente em providers com janela menor. Deixe o agente ler os
  arquivos via tool — a leitura e segmentada.
- **Confiar no review automatico para mudancas de seguranca**: use o agente
  como primeira passada, mas valide manualmente alteracoes em auth,
  criptografia, queries SQL e parsing de input externo.
- **`vulp --auto` em PR de terceiro com codigo nao-confiavel**: o `--auto`
  aprova `Bash` automaticamente. Se o PR adiciona um `Makefile` malicioso,
  o agente pode rodar `make test` e executar codigo arbitrario. Para PRs
  externos, prefira o modo `default` e revise cada `Bash`.
- **Esperar `WebSearch` para procurar issues parecidas**: a tool
  `WebSearch` pode ficar indisponivel sem `TAVILY_API_KEY` configurado;
  voce vera uma mensagem `WebSearch backend unavailable`. Use
  [`WebFetch`](../tools/web.md) com URL conhecida ou rode a busca a mao.

---

## Veja tambem

- [Refatorar codigo](refactor-code.md) — quando a review virar "isso aqui
  precisa ser refeito".
- [Escrever testes](write-tests.md) — quando o PR introduz logica sem
  cobertura.
- [Tools / Agente](../tools/agent.md) — detalhes do `Task` (subagente).
- [Modos de permissao](../user-guide/permission-modes.md) — quando usar
  `--auto`, `--safe` ou `--plan`.
- [Slash commands](../user-guide/slash-commands.md) — `/save`, `/cost`.
