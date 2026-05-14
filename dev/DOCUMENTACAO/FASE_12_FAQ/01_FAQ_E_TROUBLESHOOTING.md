# Tarefa 12.01 - FAQ + Troubleshooting

**Status**: PENDENTE
**Fase**: 12 - FAQ
**Dependencias**: 11.02
**Bloqueia**: nada

---

## Objetivo

Criar `faq.md` consolidado com perguntas frequentes e troubleshooting
das pegadinhas conhecidas.

---

## Arquivos a criar

- `docs/faq.md`

---

## Estrutura

### Geral

- **O que vulpcode faz que claude code nao faz?**
  Multi-provider (Ollama, OpenAI, internal endpoints), open-source MIT.

- **Vulpcode usa minha chave de API?**
  Sim, voce fornece. Cada provider tem sua propria chave/config.

- **Funciona offline?**
  Sim, com Ollama rodando local. Veja [receita](recipes/offline-with-ollama.md).

- **Funciona no Windows?**
  Recomenda WSL. Bash tool depende de `bash` no PATH.

- **Quanto custa?**
  A biblioteca e MIT (gratis). Os provedores cobram via API. Ollama e gratis e local.

### Instalacao

- **`pip install` falha por conflito de deps?**
  Use venv: `python -m venv .venv && source .venv/bin/activate && pip install vulpcode`.

- **`vulp: command not found` apos install?**
  Venv nao ativado, OU `~/.local/bin` nao no PATH (instalacao com `--user`).

- **`pip install` reclama "externally-managed-environment"?**
  Distribuicao moderna (Debian/Ubuntu 24.04+) bloqueia install global. Use venv.

### Providers

- **Como sei quais modelos meu provider suporta?**
  `vulp models` (com provider configurado), ou veja docs do provider.

- **Tokens muito altos / cortou no meio?**
  `max_tokens` default e 16384. Para mais, ajuste em config.toml:
  ```toml
  [model_settings]
  max_tokens = 32768
  ```

- **`tokens: in=0`?**
  Bug ja corrigido — atualize para v0.1.0+ que reporta input tokens via
  `RawMessageStartEvent`.

- **Stop reason "max_tokens" o que significa?**
  Modelo bateu o limite. Considere aumentar ou reformular o pedido em chunks.

- **WebSearch retorna "WebSearch backend unavailable: HTTP 302"?**
  DuckDuckGo bloqueia scrapers. Solucoes:
  - Set `TAVILY_API_KEY` (free tier 1000 buscas/mes)
  - Use WebFetch com URL conhecida
  - Aceitar e seguir sem busca

- **Glob com padrao absoluto da NotImplementedError?**
  Bug ja corrigido — vulpcode 0.1.0+ aceita padroes absolutos.

### REPL e UI

- **Spinner congela / nao consigo digitar quando aparece [permission]?**
  Bug ja corrigido — REPL agora pausa o spinner antes de pedir input.

- **Como sair do REPL?**
  `/exit`, `/quit`, `Ctrl+D`. Para abortar turn em andamento: `Ctrl+C`.

- **Historico de comandos persiste?**
  Sim, em `~/.vulpcode/history` (prompt_toolkit).

- **Como ver tokens consumidos na sessao?**
  `/cost`.

- **Como salvar uma conversa?**
  `/save nome`. Para retomar: `/load nome` ou `vulp --resume`.

### Permissoes

- **REPL pergunta `[y/a/n]` toda hora — como evito?**
  - Para a sessao toda: `vulp --auto`
  - Para tools especificas: `[permissions] always_allow_tools = [...]` em config.toml
  - Por enquanto so: aperte `a` em vez de `y` quando pedir

- **Usei `--auto` e o agente fez algo nao esperado?**
  `--auto` confia totalmente. Use `--safe` para revisar TUDO.

- **Modo `--plan` o que faz?**
  Bloqueia execucao de toda tool. So o LLM "planeja" via texto.

### Configuracao

- **Onde e meu config.toml?**
  `~/.vulpcode/config.toml` (global) ou `<projeto>/.vulpcode/config.toml`
  (por projeto). Comando `vulp config` abre o global no `$EDITOR`.

- **Hierarquia de prioridade?**
  CLI > env vars > config.toml local > config.toml global > defaults.

- **Posso ter multiple chaves de provider configuradas?**
  Sim. `[providers.X]` para cada um. Trocar em runtime: `/provider X`.

### MCP

- **Servidor MCP nao inicia?**
  Veja stderr ao iniciar `vulp` — falhas individuais sao logadas mas nao
  bloqueiam o REPL.

- **Como ver tools fornecidas por MCP?**
  `/mcp` — lista servidores e tools.

- **Tools MCP tem prefixo no nome?**
  Sim, `mcp__<server>__<tool>`. Ex: `mcp__filesystem__read_file`.

### Desenvolvimento

- **Quero adicionar suporte a um novo provider — como?**
  Veja [Adicionando provider](contributing/add-provider.md).

- **Como rodar testes?**
  `pytest tests/ -v` (depois de `pip install -e '.[dev]'`).

- **Como rodar a doc localmente?**
  `pip install -e '.[docs]' && mkdocs serve`.

### Limitacoes

- **O agente roda em loop infinito?**
  Nao — `_max_iters = 25` no `agent.py`.

- **Cada turn re-envia o historico inteiro? Nao e caro?**
  Sim, e e por isso que `/compact` existe — sumariza historico para reduzir.
  Anthropic prompt caching pode reduzir custo (TODO em fase futura).

- **Posso usar como SDK em outro projeto?**
  Sim. Veja [API Reference](api/index.md).

---

## Atualizar `mkdocs.yml`

```yaml
- FAQ: faq.md
```

(no final, antes de Contributing ou separado)

---

## INSTRUCAO CRITICA

- Cada Q deve ter A objetiva (1-3 frases). Nao reproduzir docs longas — linkar.
- Inclua os bugs jq corrigidos como nota historica (`Bug ja corrigido`),
  para usuarios em versoes antigas.

---

## Etapas de Implementacao

### Etapa 1: Criar `docs/faq.md`
### Etapa 2: Atualizar `mkdocs.yml`
### Etapa 3: `mkdocs build`

---

## Criterios de Aceite

- [ ] `docs/faq.md` criado com >=25 perguntas
- [ ] Categorias: Geral, Instalacao, Providers, REPL, Permissoes, Configuracao, MCP, Desenvolvimento, Limitacoes
- [ ] Cada resposta linka para a pagina detalhada quando aplicavel
- [ ] `mkdocs.yml` atualizado
- [ ] `mkdocs build` continua passando

---

**End of Specification**
