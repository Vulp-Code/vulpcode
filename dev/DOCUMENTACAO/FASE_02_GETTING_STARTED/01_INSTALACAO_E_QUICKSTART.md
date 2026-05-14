# Tarefa 02.01 - Instalacao e Quickstart

**Status**: PENDENTE
**Fase**: 02 - Getting Started
**Dependencias**: 01.03 (landing)
**Bloqueia**: 02.02

---

## Objetivo

Criar paginas `getting-started/index.md`, `getting-started/installation.md` e
`getting-started/quickstart.md` cobrindo: instalacao via pip + venv, opcoes de
instalacao (basic, dev, docs, search), e um tutorial de 5 minutos.

---

## Arquivos a criar

- `docs/getting-started/index.md`
- `docs/getting-started/installation.md`
- `docs/getting-started/quickstart.md`

---

## Source de verdade

- `pyproject.toml` (raiz) — para extras `dev`, `docs`, `search`
- `src/vulpcode/cli.py` — para flags do CLI
- `README.md` — para qualquer informacao adicional

---

## Conteudo de `getting-started/index.md`

Pagina indice da secao com 4 cards/links:

```markdown
# Comece aqui

Bem-vindo a documentacao do **Vulpcode**. Esta secao guia voce do zero ate o
primeiro chat funcional, em qualquer provider.

## Roteiro sugerido

1. [Instalacao](installation.md) — `pip install vulpcode`, virtualenv, extras opcionais.
2. [Quickstart](quickstart.md) — primeiro chat em 5 minutos.
3. [Primeira configuracao](first-config.md) — `~/.vulpcode/config.toml`.
4. [Conceitos principais](core-concepts.md) — agente, tools, permissoes.

## Pre-requisitos

- Python 3.11 ou superior (`python --version`)
- `pip` recente (`pip install --upgrade pip`)
- Linux ou macOS (Windows: WSL recomendado)
- Pelo menos uma chave de API (Anthropic, OpenAI, Gemini, ...) **OU** Ollama
  rodando localmente
```

---

## Conteudo de `getting-started/installation.md`

Cobrir:

1. **Recomendado: virtualenv**
   ```bash
   python -m venv ~/.venv/vulpcode
   source ~/.venv/vulpcode/bin/activate
   pip install vulpcode
   ```
2. **Instalacao basica**: `pip install vulpcode`
3. **Extras opcionais** (puxar de `pyproject.toml`):
   - `[dev]`: pytest, ruff, mypy — para contribuintes
   - `[docs]`: mkdocs, mkdocs-material — para gerar este site
   - `[search]`: duckduckgo-search — para WebSearch sem Tavily
4. **Instalacao a partir do source** (clonar repo + `pip install -e .`)
5. **Verificacao**:
   ```bash
   vulp --version
   # vulpcode 0.1.0
   vulp providers
   # tabela com 10 providers
   ```
6. **Desinstalar**: `pip uninstall vulpcode`

---

## Conteudo de `getting-started/quickstart.md`

Tutorial sequencial:

1. **Passo 1**: Instalar (link para installation.md).
2. **Passo 2**: Configurar uma API key (escolher um caminho):
   - Anthropic (`ANTHROPIC_API_KEY`)
   - OpenAI (`OPENAI_API_KEY`)
   - Ollama (sem chave, mas precisa de daemon rodando + modelo baixado)
3. **Passo 3**: Primeiro chat one-shot:
   ```bash
   vulp --print --auto "diga oi em uma palavra"
   ```
4. **Passo 4**: REPL interativo:
   ```bash
   vulp --auto
   > liste os arquivos em /tmp em ordem alfabetica
   > /tools
   > /exit
   ```
5. **Passo 5**: Criar/editar arquivo (Write tool):
   ```
   > use a tool Write para criar /tmp/teste.txt com "hello vulpcode"
   ```
6. **Passo 6**: Trocar provider em runtime:
   ```
   > /provider ollama
   > /model qwen2.5-coder:7b
   ```
7. **Proximos passos**: links para `first-config.md`, `core-concepts.md`,
   `user-guide/slash-commands.md`.

Use a sintaxe Material `=== "Aba"` para mostrar comandos por sistema operacional
(Linux/macOS/WSL) onde fizer sentido.

---

## Atualizar `mkdocs.yml`

Adicionar em `nav:` (logo apos `Home`):

```yaml
nav:
  - Home: index.md
  - Comece aqui:
      - getting-started/index.md
      - Instalacao: getting-started/installation.md
      - Quickstart: getting-started/quickstart.md
      - Primeira configuracao: getting-started/first-config.md       # criada em 02.02
      - Conceitos principais: getting-started/core-concepts.md       # criada em 02.03
```

---

## INSTRUCAO CRITICA

- **NAO** invente flags do CLI. Conferir em `src/vulpcode/cli.py` quais sao
  reais. Atual: `--provider`, `--model`, `--print`, `--resume`, `--auto`,
  `--safe`, `--plan`, `--version`.
- Os arquivos `first-config.md` e `core-concepts.md` ainda nao existem (vem nas
  tarefas 02.02 e 02.03). Os links no nav vao quebrar no `--strict` ate la —
  use `mkdocs build` sem `--strict`.
- Use comandos reais que funcionam. Ao escrever exemplos, mentalmente execute
  cada comando contra o codigo real.

---

## Etapas de Implementacao

### Etapa 1: Criar `getting-started/index.md`
### Etapa 2: Criar `getting-started/installation.md`
### Etapa 3: Criar `getting-started/quickstart.md`
### Etapa 4: Atualizar `mkdocs.yml` adicionando nav
### Etapa 5: `mkdocs build` (sem --strict)

---

## Criterios de Aceite

- [x] `docs/getting-started/index.md` criado com roteiro de 4 itens
- [x] `docs/getting-started/installation.md` cobre venv, basic, extras, source, verificacao
- [x] `docs/getting-started/quickstart.md` tem tutorial sequencial de 5+ passos
- [x] Comandos do quickstart sao COPY-PASTE friendly (testaveis)
- [x] `mkdocs.yml` atualizado com nav `Comece aqui` (incluindo paginas que serao criadas em 02.02 e 02.03)
- [x] `mkdocs build` completa (warnings de links quebrados aceitaveis nesta fase)

---

## Riscos

| Risco | Mitigacao |
|-------|-----------|
| Comandos divergem do CLI real | Sempre conferir `cli.py` antes de documentar |
| Versao do Python no `installation.md` errada | Olhar `requires-python` em pyproject.toml |

---

**End of Specification**
