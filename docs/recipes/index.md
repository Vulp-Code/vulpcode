# Receitas

Tarefas concretas resolvidas com prompts copy-paste-friendly. Cada receita
mostra:

- **Cenario**: quando voce usaria.
- **Tempo estimado**: ordem de magnitude para o caminho feliz.
- **Provider recomendado**: e por que.
- **Passos numerados** com prompts entre crases.
- **Variantes** e **anti-patterns** colhidos na pratica.

> Antes de seguir uma receita, confirme o setup minimo no
> [Quickstart](../getting-started/quickstart.md) e leia
> [Modos de permissao](../user-guide/permission-modes.md). As receitas
> assumem que voce sabe a diferenca entre `--auto`, `--safe` e `--plan`.

---

## Catalogo

### Desenvolvimento

- [Revisar pull request](review-pr.md) — checkout, resumo, code review focado
  e comentario pronto para colar no GitHub.
- [Refatorar codigo](refactor-code.md) — mapear, planejar (`--plan`),
  executar com testes em loop e verificar.
- [Escrever testes](write-tests.md) — analise de risco, geracao com pytest,
  rodada e cobertura por linha.

### Operacao

- [Debugar bug](debug-bug.md) — reproduzir, formular hipoteses,
  validar e fixar com teste de regressao.
- [Gerar documentacao](generate-docs.md) — inventariar, padronizar
  em Google style e verificar com `mkdocs build --strict`.
- [Trabalhar offline com Ollama](offline-with-ollama.md) — setup
  completo, tabela de modelos por tarefa e notas de performance.

---

## Como ler uma receita

Cada pagina segue o mesmo formato:

| Secao              | O que esperar                                                    |
| ------------------ | ---------------------------------------------------------------- |
| Cabecalho          | cenario, tempo estimado, provider sugerido                       |
| **Contexto**       | 2-3 frases sobre o problema e por que vale automatizar           |
| **Passos**         | numerados, com prompts dentro de blocos `code` para copiar       |
| **Variantes**      | quando o caminho feliz nao se aplica                             |
| **Anti-patterns**  | armadilhas reais (max_tokens, websearch fora do ar, etc.)        |
| **Veja tambem**    | links para tools e guias relacionados                            |

Os prompts comecam com `>` para imitar o REPL — copie **sem o `>`**.

---

## Veja tambem

- [Slash commands](../user-guide/slash-commands.md) — referencia de `/cost`,
  `/compact`, `/save`, `/load`.
- [Tools](../tools/index.md) — o que cada tool nativa faz.
- [Providers](../providers/index.md) — escolha entre Anthropic, OpenAI,
  Gemini, Ollama.
