# Tarefa 08.01 - Receitas de Desenvolvimento

**Status**: PENDENTE
**Fase**: 08 - Receitas
**Dependencias**: 07.01
**Bloqueia**: 08.02

---

## Objetivo

Criar `recipes/index.md` (overview) + paginas com receitas pra tarefas comuns
de desenvolvimento: revisar PR, refatorar codigo, escrever testes.

---

## Arquivos a criar

- `docs/recipes/index.md`
- `docs/recipes/review-pr.md`
- `docs/recipes/refactor-code.md`
- `docs/recipes/write-tests.md`

---

## Estrutura geral de cada receita

````markdown
# <Titulo da receita>

> Cenario: <quando voce usaria>
> Tempo estimado: <X minutos>
> Provider recomendado: <X — porque>

## Contexto

<2-3 frases descrevendo o problema>

## Passos

### 1. <Setup>
```bash
cd /seu/projeto
vulp --auto    # ou outro modo
```

### 2. <Pedido inicial>
```
> <prompt exato copy-paste-friendly>
```

### 3. <Itera>
...

## Variantes

- ...

## Anti-patterns / armadilhas

- ...

## Veja tambem

- ...
````

---

## Conteudo de `recipes/index.md`

Lista de receitas com card por receita:
- [Revisar pull request](review-pr.md)
- [Refatorar codigo](refactor-code.md)
- [Escrever testes](write-tests.md)
- [Debugar bug](debug-bug.md) — em 08.02
- [Gerar documentacao](generate-docs.md) — em 08.02
- [Trabalhar offline com Ollama](offline-with-ollama.md) — em 08.02

---

## Conteudo de `recipes/review-pr.md`

Cenario: voce vai revisar um PR de outra pessoa.

Passos:
1. Fazer checkout da branch do PR (`gh pr checkout 123`)
2. Iniciar `vulp --auto`
3. Pedir resumo das mudancas:
   ```
   > resuma as mudancas dessa branch comparado a main: rode `git log main..HEAD --oneline` e depois leia os arquivos modificados
   ```
4. Pedir review focado:
   ```
   > faca um code review focando em: bugs potenciais, edge cases, design questionavel. seja conciso. liste como bullets.
   ```
5. Verificar qualidade:
   ```
   > rode os testes (pytest) e me diga se algum falha
   > rode ruff/mypy se configurados
   ```
6. Sumario para colar no GitHub:
   ```
   > escreva um comentario de review em portugues, em formato markdown, listando 1) o que esta bom, 2) sugestoes, 3) bloqueadores
   ```

Variantes:
- Para PRs grandes: usar `Task` (subagente) para explorar areas separadamente
- Para code review com Claude vs Ollama: comparar resultados

---

## Conteudo de `recipes/refactor-code.md`

Cenario: voce quer refatorar um modulo (ex: extrair logica duplicada, renomear,
mover arquivo).

Passos:
1. Identificar onde:
   ```
   > use Glob para listar src/**/*.py e Grep para encontrar usos de funcao_X
   ```
2. Pedir plano:
   ```
   > /plan (use --plan ou pergunte sem aprovar nada)
   > proponha um plano para extrair lógica duplicada de a.py e b.py para um helper
   ```
3. Aprovar plano e executar:
   ```
   > execute o plano. apos cada mudança, rode os testes
   ```
4. Verificar:
   ```
   > rode pytest e ruff. se algo quebrou, corrija
   ```

Anti-patterns:
- Pedir refactor de 100 arquivos de uma vez (estoura tokens)
- Refactor sem testes (impossivel verificar)

---

## Conteudo de `recipes/write-tests.md`

Cenario: voce quer adicionar testes para um arquivo existente.

Passos:
1. Pedir analise:
   ```
   > leia src/foo.py e me diga quais funcoes carecem de teste, em ordem de risco
   ```
2. Pedir testes:
   ```
   > escreva tests/test_foo.py cobrindo as 3 funcoes mais criticas. use pytest, fixtures se fizer sentido. nao mocke alem do necessario.
   ```
3. Rodar:
   ```
   > rode pytest tests/test_foo.py -v. se algum falhar, corrija ate passar.
   ```
4. Cobertura:
   ```
   > rode pytest --cov=src/foo tests/test_foo.py. mostre quais linhas faltam cobertura.
   ```

Variantes:
- TDD reverso: pedir teste antes de funcao existir
- Property-based: `> use hypothesis para gerar tests baseados em propriedades`

---

## Atualizar `mkdocs.yml`

```yaml
- Receitas:
    - recipes/index.md
    - Revisar PR: recipes/review-pr.md
    - Refatorar codigo: recipes/refactor-code.md
    - Escrever testes: recipes/write-tests.md
    - Debugar bug: recipes/debug-bug.md             # 08.02
    - Gerar documentacao: recipes/generate-docs.md  # 08.02
    - Offline com Ollama: recipes/offline-with-ollama.md  # 08.02
```

---

## INSTRUCAO CRITICA

- Receitas devem ter prompts COPY-PASTE-FRIENDLY (entre crases). O usuario
  vai copiar literalmente.
- Use marcadores claros (1, 2, 3) para passos.
- Comente armadilhas com base no que aprendemos: max_tokens, websearch quebrado,
  etc.

---

## Etapas de Implementacao

### Etapa 1: Criar 4 arquivos de receita
### Etapa 2: Atualizar `mkdocs.yml`
### Etapa 3: `mkdocs build`

---

## Criterios de Aceite

- [x] `docs/recipes/index.md` com overview e cards
- [x] `docs/recipes/review-pr.md` com 6+ passos numerados
- [x] `docs/recipes/refactor-code.md` com plan + execute + verify
- [x] `docs/recipes/write-tests.md` com analise + tests + rodar + cobertura
- [x] Cada receita tem secoes "Variantes" e "Anti-patterns"
- [x] Prompts sao copy-paste-friendly
- [x] `mkdocs.yml` atualizado
- [x] `mkdocs build` continua passando

---

**End of Specification**
