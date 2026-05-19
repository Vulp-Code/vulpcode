# Plano TOOLS — Provider agêntico + ferramentas de criação de arquivos com auto-reparo

**Status**: PENDENTE
**Data**: 2026-05-15
**Target**: `/home/guhaase/projetos/vulpcode/`

---

## Contexto

O provider `internal-llm` atual (`src/vulpcode/providers/internal_llm.py`) fala com um endpoint
corporativo `/chatCompletion` que **não suporta tool calling nativo**. Isso transforma o agente
num chat puro: o modelo só consegue gerar texto, então ações como criar arquivos, ler do disco
ou rodar comandos são silenciosamente ignoradas (o provider injeta o aviso
`tools were ignored`). Para usuários corporativos isso quebra todo o fluxo agêntico.

Este plano adiciona um **segundo provider** (`internal-llm-agentic`) que:

1. Usa um **protocolo de tool calling baseado em texto** (XML-ish embutido na resposta).
2. Faz parser server-side da resposta do endpoint e emite eventos `tool_call` sintéticos.
3. Reaproveita todo o agent loop existente (`src/vulpcode/agent.py`) sem modificá-lo.

Junto, este plano introduz uma **família nova de tools de criação de arquivo com validação
embutida** (`WritePy`, `WriteIpynb`, `WriteMd`, `WriteDocx`, `WritePdf`, `WriteJson`, `WriteYaml`,
`WriteToml`, `WriteCsv`, `WriteXml`, `WriteHtml`, `WriteSh`, `WriteSql`, `WriteSvg`, `WriteDot`).

Cada Write* especializado:

- Valida o conteúdo **antes** de gravar (parse/compile, dependendo do tipo).
- Em caso de erro de sintaxe, retorna `ToolResult(is_error=True)` com mensagem precisa
  (linha, coluna, trecho do código).
- O agent loop existente já alimenta o erro de volta pro modelo, que pode emitir nova
  versão corrigida → repetir até validar OK ou atingir `_max_iters`.
- Só grava o arquivo final quando a validação passa (gravação atômica via tmp+rename).

Resultado: usuários do endpoint corporativo passam a ter um agente que **realmente** cria
arquivos, com correção automática de erros de sintaxe.

---

## Princípios

1. **Não alterar `internal-llm`**: ele continua como modo "chat puro" / fallback.
2. **Sem mexer no agent loop**: toda a inteligência mora no novo provider e nas novas tools.
3. **Tools são reutilizáveis por outros providers**: providers com tool calling nativo
   (Anthropic, OpenAI, etc.) também ganham as Write* especializadas de graça.
4. **Validação antes de gravação**: nenhum arquivo inválido toca o disco.
5. **Gravação atômica**: escreve em `<path>.tmp` e renomeia — não deixa arquivo half-written.
6. **Mensagens de erro acionáveis**: linha + coluna + snippet de 3 linhas em volta.

---

## Resumo das Fases

| Fase | Pasta | Descrição | Tarefas |
|------|-------|-----------|---------|
| 01 | `FASE_01_PROTOCOLO` | Design do protocolo XML-ish + parser standalone | 1 |
| 02 | `FASE_02_PROVIDER` | `InternalLLMAgenticProvider` + registry | 1 |
| 03 | `FASE_03_VALIDATION_BASE` | Base `ValidatedWriteTool` (atomic save + repair) | 1 |
| 04 | `FASE_04_WRITE_TOOLS` | 15 tools Write* especializadas | 4 |
| 05 | `FASE_05_SYSTEM_PROMPT` | System prompt do protocolo + iter cap | 1 |
| 06 | `FASE_06_TESTES` | Unit + integração + e2e mockado | 1 |
| 07 | `FASE_07_DOCS` | README + mkdocs + `vulp providers` | 1 |

**Total**: 7 fases, 10 tarefas.

---

## Ordem de Execução e Dependências

```
FASE_01 (protocolo)
   |
FASE_02 (provider) ----- depende de 01
   |
FASE_03 (validation base)  (pode rodar em paralelo a 01/02)
   |
FASE_04 (write tools) -- depende de 03
   |  (4 tarefas: py/ipynb, docs, data, web/shell)
   |
FASE_05 (system prompt) - depende de 02 + 04
   |
FASE_06 (testes) ------- depende de 01 a 05
   |
FASE_07 (docs) --------- último passo
```

A ordem na lista `TASK_FILES` no `prompt.sh` respeita essas dependências.

---

## Dependências externas (pyproject.toml)

A maior parte das validações usa stdlib (`ast`, `json`, `tomllib`, `csv`, `html.parser`,
`xml.etree.ElementTree`). Para os tipos não-stdlib, declarar como **extras opcionais**:

```toml
[project.optional-dependencies]
docs-tools = [
  "python-docx>=1.1",
  "reportlab>=4.0",
  "pypdf>=4.0",
  "markdown-it-py>=3.0",
  "nbformat>=5.10",
  "PyYAML>=6.0",
  "sqlparse>=0.4",
  "pydot>=2.0",
]
```

Tools relativas a `.docx`, `.pdf`, `.ipynb`, `.md`, `.yaml`, `.sql`, `.dot` checam o import
no `run()` e retornam `ToolResult(is_error=True, error="dependency X not installed; pip
install vulpcode[docs-tools]")` se não disponível — não quebram o import do pacote.

---

## Automação

| Arquivo | Função |
|---------|--------|
| `prompt.sh` | Itera por todas as tarefas e chama Claude CLI até zero pendentes |
| `LOG/` | Logs por iteração + status atual (criado em runtime) |

Para acompanhar:

```bash
# log em tempo real
tail -f /home/guhaase/projetos/vulpcode/dev/TOOLS/LOG/latest.log

# status rápido
cat /home/guhaase/projetos/vulpcode/dev/TOOLS/LOG/status.txt
```

Para executar:

```bash
bash /home/guhaase/projetos/vulpcode/dev/TOOLS/prompt.sh
```

---

## Critério de Sucesso

- [ ] Todas as 7 fases concluídas (checkboxes pendentes = 0)
- [ ] `vulp providers` lista `internal-llm-agentic`
- [ ] Smoke E2E: `vulp --provider internal-llm-agentic --print "crie um script Python que
      imprime a sequência de Fibonacci até 10"` cria o arquivo, valida AST, devolve ack
- [ ] Smoke E2E negativo: modelo emite código com `SyntaxError` na 1ª tentativa → agente
      recebe o erro com linha/coluna → modelo corrige → arquivo final é válido
- [ ] `pytest tests/` continua verde (não regredir nada)
- [ ] `pytest tests/test_tools/` passa com >= 30 testes novos
- [ ] README + mkdocs atualizados

---

**End of Document**
