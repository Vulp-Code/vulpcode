# Plano de Desenvolvimento — Vulpcode

**Status**: PENDENTE
**Data**: 2026-05-06
**Target**: `/home/guhaase/projetos/vulpcode/`

---

## Contexto

**Vulpcode** e uma CLI agentica de programacao inspirada no Claude Code, distribuida via PyPI,
escrita em Python 3.11+, multi-provedor (Claude, OpenAI, Gemini, Ollama, etc.) com paridade
funcional de tools (Bash, Read, Write, Edit, Grep, Glob, WebFetch, WebSearch, Task, TodoWrite, MCP).

Especificacao completa: `/home/guhaase/projetos/vulpcode/vulpcode-projeto.md`

**Estado inicial**: pasta vazia (apenas o documento de especificacao).
**Estado final**: pacote Python instalavel via `pip install -e .` com REPL `vulp` funcional.

---

## Princípios de Execucao

1. **Cada arquivo de tarefa e auto-contido** — contem objetivo, descricao tecnica, etapas e
   criterios de aceite com checkboxes.
2. **Dependencias explicitas** — cada arquivo declara o que precisa estar pronto antes.
3. **Avanco por checkbox** — Claude marca `- [ ]` -> `- [x]` ao concluir cada criterio.
4. **Iteracao ate zero pendentes** — `prompt.sh` repete a chamada ate todos os checkboxes
   estarem marcados.
5. **Sem documentacao da biblioteca nesta fase** — foco em codigo + testes minimos.

---

## Resumo das Fases

| Fase | Pasta | Descricao | Tarefas |
|------|-------|-----------|---------|
| 01 | FASE_01_BOOTSTRAP | Estrutura do pacote, pyproject, CLI skeleton | 3 |
| 02 | FASE_02_NUCLEO | Provider ABC, Tool ABC, tipos de mensagem | 2 |
| 03 | FASE_03_PROVIDERS | Anthropic, OpenAI, Gemini, Ollama, registry | 5 |
| 04 | FASE_04_TOOLS_FILESYSTEM | Read, Write, Edit, MultiEdit, Glob | 4 |
| 05 | FASE_05_TOOLS_BUSCA_SHELL | Grep, Bash, Bash background | 3 |
| 06 | FASE_06_TOOLS_WEB_AGENTE | WebFetch/Search, TodoWrite, Task, Notebook | 4 |
| 07 | FASE_07_CONFIG_PERMISSOES | Config TOML hierarquico + permissoes | 2 |
| 08 | FASE_08_AGENT_LOOP | Loop principal LLM <-> tools | 1 |
| 09 | FASE_09_UI | Theme/render, streaming, REPL | 3 |
| 10 | FASE_10_SLASH_COMMANDS | /help /provider /model /clear /tools etc. | 3 |
| 11 | FASE_11_MCP | Cliente MCP + loader de servidores | 2 |
| 12 | FASE_12_SESSION | Persistencia de sessao | 1 |
| 13 | FASE_13_TESTES | Pytest providers / tools / agent / cli | 3 |
| 14 | FASE_14_BUILD_SMOKE | Build hatchling + smoke tests end-to-end | 1 |

**Total**: 14 fases, ~37 tarefas.

---

## Ordem de Execucao e Dependencias

```
FASE_01 (bootstrap)
   |
FASE_02 (nucleo) -------- depende de 01
   |
FASE_03 (providers) ----- depende de 02
   |
FASE_04 (fs tools)       depende de 02
FASE_05 (busca/shell)    depende de 02
FASE_06 (web/agente)     depende de 02 (Task depende de FASE_08 mas pode ser stub)
   |
FASE_07 (config/perm) -- depende de 02
   |
FASE_08 (agent loop) --- depende de 03 + 04 + 05 + 06 + 07
   |
FASE_09 (UI) ----------- depende de 08
   |
FASE_10 (slash) -------- depende de 09
   |
FASE_11 (MCP) ---------- depende de 02 + 08
FASE_12 (session) ------ depende de 02 + 08
   |
FASE_13 (testes) ------- depende de tudo
   |
FASE_14 (build/smoke) -- ultimo passo
```

A ordem na lista `TASK_FILES` no `prompt.sh` respeita estas dependencias.

---

## Automacao

| Arquivo | Funcao |
|---------|--------|
| `prompt.sh` | Itera por todas as tarefas e chama Claude CLI ate zero pendentes |
| `LOG/` | Logs por iteracao + status atual |

Para acompanhar:

```bash
# log em tempo real
tail -f /home/guhaase/projetos/vulpcode/dev/LOG/latest.log

# status rapido
cat /home/guhaase/projetos/vulpcode/dev/LOG/status.txt
```

---

## Criterio de Sucesso (Final)

- [ ] Todas as 14 fases concluidas (`grep -c "^- \[ \]" dev/**/*.md` retorna 0)
- [ ] `pip install -e /home/guhaase/projetos/vulpcode` instala sem erro
- [ ] `vulp --help` exibe ajuda
- [ ] `vulp` abre REPL e responde com pelo menos um provider configurado
- [ ] `pytest tests/ -v` passa todos os testes
- [ ] `python -m build` produz wheel + sdist validos

---

**End of Document**
