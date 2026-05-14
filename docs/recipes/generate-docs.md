# Gerar documentacao

> **Cenario**: voce quer gerar ou atualizar docs de um modulo — preencher
> docstrings ausentes, padronizar estilo, ou criar um README inicial para
> uma pasta sem documentacao.
> **Tempo estimado**: 10-30 minutos para um modulo pequeno-medio.
> **Provider recomendado**: Anthropic (Claude Sonnet/Opus) para docs
> claros e ingles natural; OpenAI (`gpt-5`) bom em docstrings mecanicas;
> Ollama (`qwen2.5-coder:7b`) quando o codigo nao pode sair da maquina.

## Contexto

Docstrings geradas por LLM falham de duas formas: ou parafraseiam a
assinatura (`"Returns the result of the function"`), ou inventam
comportamento que o codigo nao implementa. O fluxo aqui obriga o agente a
**inventariar** primeiro o que falta, **padronizar** num estilo unico, e
**verificar** com `mkdocs build --strict` para que warnings nao escapem.

> **Modo recomendado:** `--auto` para esse fluxo — sao varias edits
> em sequencia, e cada confirmacao manual interrompe. Veja
> [Modos de permissao](../user-guide/permission-modes.md).

## Passos

### 1. Inventario do que falta

Antes de escrever qualquer docstring, mapeie o terreno:

```text
> liste as funcoes/classes publicas em src/foo/ que tem docstring vazia ou ausente. use Grep para achar `^\s*(def|class) ` e Read para inspecionar cada uma. me devolva uma tabela: arquivo | linha | nome | tipo (funcao/classe/metodo) | tem docstring? (sim/nao/parcial).
```

Tabela serve de checklist. Se ela tem 50+ linhas, **pare aqui** e divida
o trabalho por submodulo — gerar 50 docstrings de uma vez estoura
`max_tokens` e produz qualidade irregular.

> Privadas (`_foo`) podem ficar sem docstring. Foque no que aparece em
> `__all__` ou no que e importado de fora.

### 2. Padronizar (gerar docstrings)

```text
> adicione docstrings no formato Google style em todas as funcoes/classes listadas. cada docstring deve ter: 1) one-liner (imperativo, sem repetir o nome), 2) Args com tipos quando relevante, 3) Returns, 4) Raises se a funcao lanca explicitamente. NAO invente comportamento — leia a implementacao antes. mantenha consistencia entre todos os arquivos.
```

Pontos importantes:

- **Google style** combina com `mkdocstrings` (config padrao em
  `mkdocs.yml`: `docstring_style: google`).
- **"NAO invente comportamento"** e crucial — o agente as vezes
  documenta uma excecao que a funcao na verdade nao lanca.
- **One-liner imperativo**: "Parse the ISO duration..." — nao
  "This function parses...".

### 3. Verificar com `mkdocs build --strict`

Se o projeto usa `mkdocstrings`:

```text
> rode `mkdocs build --strict` na raiz do projeto e me devolva a saida bruta. para cada warning ou erro, me diga: 1) qual docstring causou, 2) por que (ex: referencia quebrada, secao malformada), 3) correcao proposta.
```

`--strict` falha em qualquer warning — e o jeito de garantir que
nenhuma docstring escapa silenciosamente. Se `mkdocs` nao esta no
ambiente, peca: `> instale mkdocs e mkdocstrings[python] e refaca`.

### 4. Iterar ate verde

```text
> para cada warning do passo anterior, corrija a docstring correspondente. apos cada correcao, rode `mkdocs build --strict` novamente. nao agrupe varias correcoes — uma de cada vez para ficar facil de bisectar se algo piorar.
```

O agente as vezes "corrige" uma docstring quebrando outra adjacente
(indentacao TAB/space, parentes desbalanceados). Iterar uma de cada
vez resolve.

### 5. Visual check no site

```text
> rode `mkdocs serve` em background. me devolva a URL local. nao mate o processo — vou conferir manualmente. depois te aviso para parar.
```

Build limpo nao garante render bonito — uma tabela mal formatada passa
no `--strict` mas vira sopa de letras na pagina. Olhar o site renderizado
no navegador eh o ultimo gate.

---

## Variantes

### Gerar README de zero

Para um modulo sem documentacao alguma:

```text
> escreva um README.md em src/foo/ baseado em src/foo/__init__.py e nos arquivos importados de la. estrutura: 1) one-liner do modulo, 2) instalacao/uso, 3) API publica (lista de funcoes/classes com one-liner cada), 4) exemplo runnable. mantenha curto — README nao e API reference.
```

Alvo: 50-100 linhas. Para mais, e melhor uma pagina dedicada em
`docs/`.

### Migrar de NumPy style para Google style

```text
> converta as docstrings de src/foo.py de NumPy style (Parameters/Returns com underline) para Google style (Args:/Returns: com indentacao). nao mude o conteudo — so o formato. depois rode `mkdocs build --strict` para confirmar.
```

> Configure o `mkdocstrings` para `docstring_style: google` em
> `mkdocs.yml` antes — caso contrario o renderer ainda espera NumPy.

### Docstrings com exemplos doctest

Para funcoes puras pequenas:

```text
> adicione um bloco Examples na docstring de cada funcao publica em src/foo/utils.py com 1-3 exemplos doctest (>>> entrada, saida na linha seguinte). depois rode `python -m pytest --doctest-modules src/foo/utils.py` para confirmar que cada exemplo funciona.
```

Doctest = teste **e** documentacao no mesmo lugar. Mas evita exemplos
que dependem de IO ou rede.

### Atualizar docstrings apos refactor

Para depois de um [refactor](refactor-code.md):

```text
> use `git diff main...HEAD -- src/foo.py` para ver as mudancas. para cada funcao com assinatura alterada, atualize a docstring correspondente (Args, Returns). funcoes com docstring "perdida" (que ainda descreve o comportamento antigo) sao prioridade.
```

Refactor que esquece de atualizar docstring e fonte recorrente de bug
de "documentacao mente".

### CHANGELOG a partir de commits

```text
> rode `git log --oneline v1.2.0..HEAD` e me devolva um CHANGELOG.md no estilo Keep a Changelog. agrupe por: Added, Changed, Fixed, Removed. omita commits triviais (typo, lint, ci). use os corpos dos commits para detalhe.
```

> Funciona melhor se voce ja escreve commits no estilo Conventional
> Commits — `feat:`, `fix:`, etc.

---

## Anti-patterns / armadilhas

- **Pedir "documente todo o projeto"**: estoura `max_tokens` e produz
  qualidade irregular. Quebre por modulo (`src/foo/`, `src/bar/`).
- **Aceitar docstrings que parafraseiam a assinatura**: `"add(a, b):
  Adds a and b."` nao agrega. Peca para o agente focar no **porque** e
  no **comportamento nao obvio** — efeitos colaterais, edge cases,
  invariantes.
- **Misturar estilos no mesmo projeto**: NumPy + Google + texto livre
  fica feio no `mkdocstrings`. Decida um (Google e o default deste
  projeto) e mantenha consistente. Veja `mkdocs.yml` `docstring_style`.
- **Pular o `--strict`**: warnings em `mkdocs build` sao **sempre**
  problemas reais que aparecerao na pagina renderizada. Nunca silencie
  com `--no-strict` em vez de corrigir.
- **Documentar privadas (`_foo`) com a mesma profundidade**: API publica
  precisa de docstring detalhada; privadas precisam **as vezes** de uma
  linha de "WHY non-obvio". Mais que isso vira manutencao morta.
- **Confiar em `WebSearch` para "como escrever docstring de X"**: a tool
  pode estar indisponivel. Use [`WebFetch`](../tools/web.md) na
  [Google style guide](https://google.github.io/styleguide/pyguide.html#383-functions-and-methods)
  diretamente.

---

## Veja tambem

- [Escrever testes](write-tests.md) — docs e testes andam juntos:
  exemplo na docstring vira doctest.
- [Refatorar codigo](refactor-code.md) — apos refactor, atualizar
  docstrings e parte do trabalho.
- [Tools / Filesystem](../tools/filesystem.md) — `Read`, `Edit`,
  `Write` que o agente usa para alterar docstrings.
- [Tools / Busca e Shell](../tools/search-and-shell.md) — `Grep` para
  inventario, `Bash` para rodar `mkdocs build`.
- [Modos de permissao](../user-guide/permission-modes.md) — `--auto` no
  loop padronizar/verificar.
- [Slash commands](../user-guide/slash-commands.md) — `/cost` em
  documentacao de modulo grande.
