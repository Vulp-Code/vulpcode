# Refatorar codigo

> **Cenario**: voce quer refatorar um modulo — extrair logica duplicada,
> renomear simbolos, mover arquivo ou quebrar uma funcao gigante.
> **Tempo estimado**: 20-60 minutos para um modulo pequeno-medio.
> **Provider recomendado**: Anthropic (Claude Opus/Sonnet) para mudancas
> com risco; OpenAI (`gpt-5`) e bom em renomeacoes mecanicas.

## Contexto

Refactor sem rede de seguranca quebra coisas. O fluxo aqui sempre alterna
**mudanca + teste + verificacao** — nunca tres mudancas seguidas sem rodar
nada. O agente segue esse loop melhor que voce sob pressao, mas voce dirige
o escopo: ele nao decide o que vale refatorar.

## Passos

### 1. Mapear o terreno

Primeiro descobrir **todos os usos** do simbolo ou padrao a refatorar:

```text
> use a tool Glob para listar src/**/*.py e tests/**/*.py. depois use Grep para encontrar todas as referencias a `funcao_X` (incluindo imports e strings). me devolva uma tabela: arquivo | linha | contexto curto.
```

A tabela vai virar o checklist do refactor. Se ela tem 100+ linhas,
**pare aqui** e quebre o trabalho em duas tarefas (veja
[anti-patterns](#anti-patterns-armadilhas)).

### 2. Pedir o plano sem executar

Use `--plan` para que o agente proponha sem tocar em nada:

```bash
vulp --plan
```

```text
> proponha um plano para extrair a logica duplicada de a.py e b.py para um helper em utils/shared.py. quero saber: 1) novo modulo e nome da funcao, 2) lista de arquivos modificados e como, 3) ordem das mudancas para nunca deixar o codigo quebrado, 4) testes que precisam ser ajustados.
```

No modo `--plan`, **nenhuma tool de escrita roda** (nem mesmo
`Edit`/`Write`/`Bash`). Veja
[Modos de permissao](../user-guide/permission-modes.md).

> Se o plano vier vago ("refatorar e ajustar"), peca para detalhar:
> "expanda o passo 2 com os trechos de codigo exatos antes/depois".

### 3. Aprovar e executar com testes em loop

Saia do `--plan` e abra o REPL com aprovacao manual:

```bash
vulp        # modo default — pede confirmacao em writes/edits
```

```text
> execute o plano que voce propos. apos cada arquivo modificado, rode `pytest tests/test_a.py tests/test_b.py -q`. se algum teste falhar, corrija antes de seguir para o proximo arquivo. nao agrupe varias mudancas — uma de cada vez.
```

A frase **"uma de cada vez"** e crucial. Sem ela, o agente tende a
mergulhar e fazer 5 edits antes de rodar os testes, dificultando o
diagnostico se algo quebrar.

> Quer aprovacao automatica? Troque por `vulp --auto`, mas reveja o
> diff ao final com `git diff`. Em refactor, o `--auto` e seguro **se**
> voce tem testes confiaveis.

### 4. Verificar a suite completa

```text
> rode `pytest -q` na suite inteira e `ruff check . && ruff format --check .`. se algo quebrou, mostre a saida bruta e corrija. nao reinterprete a falha — me mostre o erro real.
```

Pedir "saida bruta" reduz a chance de o agente esconder uma falha como
"ajustei tudo". Se o pyproject usa `mypy`, adicione `mypy src/`.

### 5. Verificar contrato publico

```text
> compare a API publica antes/depois: rode `git stash` e `python -c "import a; import b; print(dir(a)); print(dir(b))"`, depois `git stash pop` e repita. me diga o que sumiu, foi renomeado, ou mudou de assinatura.
```

Se algum nome publico mudou, voce precisa de um `__all__` atualizado, um
`from ... import *` ajustado, ou um deprecation shim.

### 6. Diff final

```text
> rode `git diff --stat` e `git diff` em chunks legiveis (use `git diff -- src/utils/shared.py` para abrir um arquivo por vez). me destaque qualquer mudanca acidental que escapou do plano original.
```

---

## Variantes

### Refactor multi-passo com `TodoWrite`

Para refactors com 5+ passos, peca uma todo list:

```text
> use a tool TodoWrite para criar a lista de mudancas. atualize o status (in_progress/completed) a cada passo concluido.
```

A lista aparece no REPL e fica visivel. E o mesmo padrao usado pelos
subagentes em [`tools/agent.md`](../tools/agent.md).

### Renomear simbolo "puro"

Quando e so um rename mecanico (sem mudanca de comportamento):

```text
> renomeie a funcao `process_data` para `transform_payload` em todos os arquivos do projeto. use Grep para confirmar que todos os usos foram trocados. rode `pytest -q` ao final.
```

Para renames mais cirurgicos, considere `ruff` ou `python -m libcst codemod`
fora do agente — ferramentas dedicadas tem AST robusto.

### Quebrar funcao gigante

```text
> a funcao `handle_request` em src/api/handler.py tem 200 linhas. proponha uma refatoracao em 3-4 funcoes menores com nomes que descrevam intencao. nao mude assinatura externa. depois execute, garantindo que `pytest tests/test_handler.py -v` continue passando a cada extracao.
```

---

## Anti-patterns / armadilhas

- **Refactor de 100 arquivos de uma vez**: estoura o `max_tokens` em
  qualquer provider (mesmo Claude). Quebre por subdiretorio ou por
  responsabilidade. Se a tabela do Passo 1 tem mais de 50 linhas, divida.
- **Refactor sem testes**: impossivel verificar correcao. Antes de
  refatorar, rode [Escrever testes](write-tests.md) para os modulos
  afetados.
- **Aceitar `--auto` sem revisar o diff final**: o agente pode aplicar uma
  mudanca certa **e** uma errada na mesma rodada. Sempre `git diff` no
  final.
- **Pedir "modernize esse codigo"**: prompt vago = mudancas inconsistentes.
  Especifique: "troque `os.path` por `pathlib.Path`", "extraia constantes
  magicas para `consts.py`", etc.
- **Refatorar logica de negocio sem o stakeholder**: testes verdes nao
  garantem que o comportamento desejado foi preservado se os testes nao
  cobrem a regra. Confirme casos limites antes.
- **Confiar em `WebSearch` para "boas praticas"**: a tool pode estar
  indisponivel (mensagem `WebSearch backend unavailable`). Use
  [`WebFetch`](../tools/web.md) com URL conhecida ou guie com seu
  proprio criterio.

---

## Veja tambem

- [Escrever testes](write-tests.md) — pre-requisito para refactor seguro.
- [Revisar pull request](review-pr.md) — para revisar o proprio refactor
  como se fosse de outra pessoa.
- [Modos de permissao](../user-guide/permission-modes.md) — `--plan` e
  central nesse fluxo.
- [Slash commands](../user-guide/slash-commands.md) — `/cost` para
  monitorar tokens em refactors longos, `/compact` quando o contexto
  enche.
- [Tools / Agente](../tools/agent.md) — `Task` para paralelizar exploracao.
