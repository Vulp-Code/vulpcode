# Tarefa 13.02 - Deploy GitHub Pages

**Status**: PENDENTE
**Fase**: 13 - Build Final
**Dependencias**: 13.01
**Bloqueia**: nada (ultima tarefa)

---

## Objetivo

Configurar deploy automatico para GitHub Pages via GitHub Actions. Cada push
em `main` gera o site e publica em `gh-pages` branch.

---

## Arquivos a criar

- `.github/workflows/docs.yml`

---

## Conteudo do workflow

```yaml
name: Build and deploy docs

on:
  push:
    branches: [main]
    paths:
      - 'docs/**'
      - 'mkdocs.yml'
      - 'src/vulpcode/**'   # mkdocstrings usa as docstrings
      - 'pyproject.toml'
      - '.github/workflows/docs.yml'
  workflow_dispatch: {}

permissions:
  contents: write   # para push em gh-pages

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
          persist-credentials: true

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'

      - name: Configure Git
        run: |
          git config user.name 'github-actions[bot]'
          git config user.email '41898282+github-actions[bot]@users.noreply.github.com'

      - name: Install package + docs dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e '.[docs]'

      - name: Build site (strict)
        run: mkdocs build --strict

      - name: Deploy to gh-pages
        run: mkdocs gh-deploy --force
```

---

## Configuracao no GitHub

Apos o primeiro push do workflow:

1. **Settings → Pages** no repo do GitHub.
2. Source: **Deploy from a branch**.
3. Branch: `gh-pages` / `(root)`.
4. Save.

Apos o primeiro deploy bem-sucedido (~30s), o site estara disponivel em
`https://<owner>.github.io/<repo>/`.

---

## Atualizar `mkdocs.yml`

Setar `site_url` final:

```yaml
site_url: https://vulpcode.github.io/vulpcode/
```

(ou o owner real do repo)

---

## Boas praticas

- **Build local antes de pushar**: `mkdocs build --strict` para evitar quebrar
  CI.
- **Versionamento**: para multiplas versoes da doc, usar `mike` (plugin):
  `pip install mike && mike deploy --push 0.1.0`. Documentar isso quando o
  projeto chegar a 1.0.
- **Custom domain**: criar arquivo `docs/CNAME` com o dominio.
- **Robots.txt**: criar `docs/robots.txt` se quiser controlar crawlers.

---

## Alternativa: ReadTheDocs

ReadTheDocs.org hospeda MkDocs gratuitamente com versionamento e PR previews.
Configuracao mais simples mas customizacao limitada do tema. Se preferir:

1. Cadastrar repo em https://readthedocs.org/
2. `.readthedocs.yaml`:
   ```yaml
   version: 2
   build:
     os: ubuntu-22.04
     tools:
       python: "3.12"
   mkdocs:
     configuration: mkdocs.yml
   python:
     install:
       - method: pip
         path: .
         extra_requirements:
           - docs
   ```

Ambos funcionam. GitHub Pages e mais "vanilla".

---

## INSTRUCAO CRITICA

- Permissions `contents: write` no workflow e essencial — senao gh-deploy
  falha sem mensagem clara.
- O primeiro deploy precisa que a branch `gh-pages` exista — `mkdocs gh-deploy
  --force` cria se nao existir.

---

## Etapas de Implementacao

### Etapa 1: Criar `.github/workflows/docs.yml`
### Etapa 2: Atualizar `site_url` em `mkdocs.yml` para o owner real
### Etapa 3: Validar local com `mkdocs build --strict`
### Etapa 4: Commit + push (depende do usuario fazer)
### Etapa 5: Configurar GitHub Pages no repo (depende do usuario)

(Esta ultima etapa nao pode ser totalmente automatizada — depende de acao no
GitHub UI. Documente como fazer.)

---

## Criterios de Aceite

- [ ] `.github/workflows/docs.yml` criado com checkout, setup-python, install, build, deploy
- [ ] `site_url` atualizado em mkdocs.yml
- [ ] Workflow valido (yaml-lint passa)
- [ ] Documentacao de "como configurar GitHub Pages" presente como comentario
  ou doc separado
- [ ] `mkdocs build --strict` continua passando localmente
- [ ] (Opcional, manual) Push e Pages configurado pelo usuario

---

## Pos-deploy

Apos primeiro deploy bem-sucedido:

- Atualizar `README.md` com link para o site
- Adicionar badge de docs no `index.md`:
  `[![docs](https://img.shields.io/badge/docs-online-brightgreen)](https://vulpcode.github.io/vulpcode/)`

---

**End of Specification**
