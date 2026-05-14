# Tarefa 05.03 - Tools Agente + Web

**Status**: PENDENTE
**Fase**: 05 - Tools
**Dependencias**: 05.02
**Bloqueia**: nada (ultima da fase 05)

---

## Objetivo

Criar 2 paginas:
- `tools/agent.md` — Task (sub-agente), TodoWrite, NotebookEdit
- `tools/web.md` — WebFetch, WebSearch (com nota sobre 302/Tavily)

---

## Arquivos a criar

- `docs/tools/agent.md`
- `docs/tools/web.md`

---

## Source de verdade

- `src/vulpcode/tools/task.py`
- `src/vulpcode/tools/todo.py`
- `src/vulpcode/tools/notebook.py`
- `src/vulpcode/tools/web.py`

---

## Conteudo de `agent.md`

Seguindo template da 05.02. 3 secoes:

### Task (sub-agente)

- Lanca um Agent isolado com sua propria sequencia de mensagens
- `subagent_type`: `"general-purpose"` ou `"Explore"`
- ALLOWED_TOOLS por tipo (Explore so tem Read/Grep/Glob)
- Sub-agente nao pode chamar Task (sem recursao)
- Provider/modelo herdados da config (lazy import via `load_config`)
- Quando usar: pesquisas paralelas, tarefas independentes, evitar poluir
  contexto principal
- Limitacao: cada sub-agente faz outra chamada API completa, nao e gratis

Exemplo:

```
> use a tool Task com subagent_type="Explore" e prompt 
  "encontre todos os arquivos de teste que mencionam 'subprocess'"
```

### TodoWrite

- Lista de TODOs em memoria do processo (modulo-global por enquanto)
- Cada item: `content` (imperativo), `activeForm` (gerundio), `status`
  (pending/in_progress/completed)
- Validacao: maximo um in_progress simultaneo
- Substitui a lista inteira a cada chamada (paridade com Claude Code)
- Output renderizado: `1. [~] Doing X`, `2. [ ] Pending Y`, `3. [x] Done Z`

Quando o LLM usa: tarefas multi-step (3+ passos). Voce vai ver o painel Rich
da TodoWrite atualizando.

### NotebookEdit

- Edita celulas de Jupyter `.ipynb` (formato JSON)
- 3 modos: `replace`, `insert`, `delete`
- Localiza celula por `cell_id` ou `cell_number` (0-based)
- Preserva `id`, `metadata`, `nbformat` do notebook
- Source da celula sempre como lista de strings com `\n`

Exemplo:

```
> use a tool NotebookEdit para substituir a celula 3 do notebook 
  /tmp/analise.ipynb por "df = pd.read_csv('novo.csv')"
```

---

## Conteudo de `web.md`

2 secoes: WebFetch + WebSearch.

### WebFetch

- GET na URL com `User-Agent` custom
- Segue redirects
- Timeout 30s
- Converte HTML -> markdown via regex (best-effort, sem libs externas)
- Trunca a 100k chars
- Para conteudos binarios: retorna mensagem informativa, nao tenta converter

Schema: `url: str`, `prompt: str | None`. O `prompt` e ignorado localmente — o
LLM usa quando interpreta a saida.

### WebSearch

- Backend default: **DuckDuckGo HTML scrape** (sem chave necessaria)
- Backend opcional: **Tavily** se `TAVILY_API_KEY` esta no env
- Filtros `allowed_domains` e `blocked_domains`
- Limite: 10 resultados

#### Notas importantes sobre DuckDuckGo

A partir de 2024, o DDG passou a retornar HTTP 302 / 403 para scrapers em
muitas situacoes (anti-bot). Quando isso acontece:

- O vulpcode **NAO** trata como erro — retorna saida informativa explicando
  o que aconteceu e sugerindo:
  1. Setar `TAVILY_API_KEY` para usar backend alternativo
  2. Usar `WebFetch` direto numa URL conhecida
  3. Prosseguir sem busca (com info local)

Isso evita que o agente fique tentando re-executar a busca em loop.

#### Tavily

Plano gratuito da Tavily da 1000 buscas/mes:
1. Crie conta em https://tavily.com
2. Obtenha API key
3. `export TAVILY_API_KEY=tvly-...`
4. Reinicie o REPL — `WebSearch` vai usar Tavily automaticamente

---

## Atualizar `mkdocs.yml`

As entradas `Agente` e `Web` ja foram adicionadas em 05.01. Nao mexer.

---

## INSTRUCAO CRITICA

- Para WebSearch: enfatize o limite do DuckDuckGo. Muitos usuarios novos vao
  tentar e ver 302. A nota e importante.
- Para Task: nao deixe o usuario achar que e gratis — cada sub-agente custa
  uma chamada completa API.

---

## Etapas de Implementacao

### Etapa 1: Ler `task.py`, `todo.py`, `notebook.py`, `web.py`
### Etapa 2: Criar `agent.md` e `web.md`
### Etapa 3: `mkdocs build`

---

## Criterios de Aceite

- [x] `docs/tools/agent.md` criado com 3 secoes (Task, TodoWrite, NotebookEdit)
- [x] `docs/tools/web.md` criado com 2 secoes (WebFetch, WebSearch)
- [x] WebSearch documenta caso 302 do DDG e fallback Tavily
- [x] Task documenta `subagent_type` e ALLOWED_TOOLS
- [x] TodoWrite documenta validacao de "no maximo 1 in_progress"
- [x] NotebookEdit documenta os 3 modos (replace/insert/delete)
- [x] `mkdocs build` continua passando

---

**End of Specification**
