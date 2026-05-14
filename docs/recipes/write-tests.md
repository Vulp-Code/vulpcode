# Escrever testes

> **Cenario**: voce quer adicionar testes para um arquivo existente — seja
> para preencher cobertura, antes de um refactor, ou para fixar
> comportamento de um bug.
> **Tempo estimado**: 15-45 minutos para um modulo pequeno.
> **Provider recomendado**: Anthropic (Claude Sonnet/Opus) para testes
> de qualidade; OpenAI (`gpt-5`) para baterias mecanicas; Ollama
> (`qwen2.5-coder:7b`) quando o codigo nao pode sair da maquina.

## Contexto

Testes gerados por LLM tendem a duas falhas opostas: ou sao copy-paste do
codigo (testando que `f(1)` retorna `f(1)`), ou inventam comportamento. O
fluxo aqui forca o agente a ler primeiro, identificar risco, escrever
proposito, e so entao gerar codigo. Resultado: menos teste, mais sinal.

## Passos

### 1. Analise de risco

Comece pedindo um diagnostico antes de escrever uma linha:

```text
> leia src/foo.py e me diga quais funcoes carecem de teste, em ordem de risco. para cada uma: 1) o que ela faz em uma frase, 2) o que pode dar errado (edge cases, inputs malformados, race conditions), 3) por que merece teste agora vs depois. nao escreva codigo ainda.
```

A resposta vira o roteiro. Se vierem 12 funcoes, pegue as 3-4 mais
arriscadas — testar tudo de uma vez gera ruido e estoura tokens.

### 2. Conferir o setup de testes

```text
> leia pyproject.toml, conftest.py (se existir) e tests/test_*.py mais recente. me diga: 1) qual runner (pytest, unittest), 2) fixtures e plugins ja em uso, 3) convencao de nomes (test_foo / test_bar), 4) onde colocar mocks/stubs. nao gere codigo ainda.
```

Esse passo evita o agente reinventar fixtures que ja existem ou usar
`unittest.TestCase` num projeto pytest puro.

### 3. Escrever os testes

```text
> escreva tests/test_foo.py cobrindo as 3 funcoes mais criticas que voce listou. use pytest. use fixtures se ja existirem em conftest.py. nao mocke alem do necessario — prefira inputs reais e arquivos temporarios via tmp_path. cada teste deve ter um nome que descreve o cenario (test_<funcao>_<cenario>_<resultado>). nao agrupe varios cenarios numa funcao so.
```

Pontos importantes do prompt:

- `nao mocke alem do necessario`: testes mockados demais quebram em
  refactor sem detectar bugs reais.
- `tmp_path`: fixture nativa do pytest, evita poluir o disco.
- Nome `test_<funcao>_<cenario>_<resultado>`: pytest-style. Faz a saida
  com `-v` ler como uma documentacao.

### 4. Rodar e iterar ate verde

```text
> rode `pytest tests/test_foo.py -v`. para cada falha, mostre a saida bruta antes de tentar corrigir. corrija um teste por vez — apos cada correcao, rode novamente apenas aquele teste com `pytest tests/test_foo.py::test_X -v`. nao mexa em src/foo.py — se um teste falha por bug em foo.py, me avise antes de mudar qualquer coisa.
```

A frase **"nao mexa em src/foo.py"** e crucial. Sem ela, o agente
ajusta o codigo de producao para o teste passar — o que e o oposto do
que voce quer.

### 5. Cobertura por linha

```text
> rode `pytest --cov=src.foo --cov-report=term-missing tests/test_foo.py`. me mostre o relatorio bruto e destaque: 1) linhas nao cobertas que importam (logica de negocio, branches), 2) linhas nao cobertas que sao guard-rails defensivos (raise XError, logging) e podem ficar.
```

> Sem `pytest-cov`? Instale com `pip install pytest-cov` ou peca:
> `> instale pytest-cov no ambiente atual e refaca`.

### 6. Adicionar os testes que faltam (opcional)

Se a cobertura mostrou ramos importantes sem teste:

```text
> escreva tests para as linhas X-Y de src/foo.py que voce identificou como criticas. mantenha o estilo dos testes ja presentes em tests/test_foo.py. rode novamente para confirmar.
```

---

## Variantes

### TDD reverso (teste antes da funcao existir)

Para feature nova, comece pelos testes:

```text
> a funcao `parse_iso_duration(s: str) -> timedelta` ainda nao existe em src/foo.py. escreva tests/test_foo.py com 5-7 cenarios cobrindo: input valido, vazio, malformado, com semanas, negativo. NAO implemente a funcao — quero rodar os testes e ver todos falharem primeiro.
```

Depois implemente em outra rodada:

```text
> agora implemente `parse_iso_duration` em src/foo.py para passar todos os testes em tests/test_foo.py. nao mude os testes — se algum esta errado, me avise antes.
```

### Property-based com hypothesis

Para funcoes puras, properties cobrem espacos imensos com poucos testes:

```text
> use hypothesis para gerar tests baseados em propriedades para a funcao `normalize` em src/foo.py. propriedades: 1) idempotencia (normalize(normalize(x)) == normalize(x)), 2) preservacao de comprimento sob certa condicao, 3) nunca lanca para input str. configure `@settings(max_examples=200)`.
```

> Hypothesis precisa estar nas dependencias. Confirme com
> `> rode "pip show hypothesis"` antes.

### Snapshot tests

Util para output formatado (HTML, JSON, CLI):

```text
> use `syrupy` para criar snapshot tests de `render_report(data)`. crie tres fixtures: vazia, normal, com erro. revise o snapshot inicial — depois disso, qualquer mudanca no output dispara revisao manual.
```

### Fixture compartilhada em conftest.py

Quando varios arquivos vao precisar do mesmo setup:

```text
> mova a fixture `sample_payload` de tests/test_foo.py para tests/conftest.py para reuso. atualize os imports e rode `pytest -q` para confirmar.
```

---

## Anti-patterns / armadilhas

- **Pedir "100% de cobertura"**: o agente vai criar testes para getters
  triviais e branches inalcancaveis. 100% de coverage **nao** e qualidade
  — pe especificamente o que merece teste.
- **Testes que dependem de ordem**: se `test_b` precisa que `test_a` rode
  antes, **isso e bug**. Pytest pode rodar em paralelo (`pytest-xdist`),
  random (`pytest-randomly`), ou um teste so. Cada teste deve ser
  independente.
- **Mockar tudo**: `mock.patch("src.foo.requests")` que retorna o que voce
  quer = teste que sempre passa, mesmo com a logica errada. Mocke so o que
  e externo (rede, relogio, FS quando inviavel via `tmp_path`).
- **Asserts vagos**: `assert result is not None` nao testa nada. Prefira
  asserts especificos: `assert result.status == "ok"`, `assert len(items) == 3`.
- **Estourar `max_tokens` em arquivo grande**: se `src/foo.py` tem 1000
  linhas, peca para o agente **ler em chunks** ou foque por classe:
  "leia somente a classe `Parser` em src/foo.py". Para listar metodos
  primeiro: "use Grep com `^\s*def ` em src/foo.py".
- **Testes que dependem de timezone do CI**: `datetime.now()` muda entre
  maquinas. Use `freezegun` ou injetar relogio.
- **Esperar `WebSearch` para "como mocar lib X"**: a tool pode estar
  indisponivel (`WebSearch backend unavailable`). Use
  [`WebFetch`](../tools/web.md) com URL da doc oficial.

---

## Veja tambem

- [Refatorar codigo](refactor-code.md) — testes sao pre-requisito.
- [Revisar pull request](review-pr.md) — peca testes em PRs sem
  cobertura.
- [Tools / Filesystem](../tools/filesystem.md) — `Read`, `Write`, `Edit`
  usadas pelo agente para gerar e ajustar `tests/`.
- [Tools / Busca e Shell](../tools/search-and-shell.md) — `Grep` para
  mapear funcoes, `Bash` para rodar pytest.
- [Slash commands](../user-guide/slash-commands.md) — `/cost` em sessoes
  longas com cobertura completa.
