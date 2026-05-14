# Tarefa 01.01 - MkDocs Setup (mkdocs.yml + dependencias)

**Status**: PENDENTE
**Fase**: 01 - Bootstrap MkDocs
**Dependencias**: Nenhuma
**Bloqueia**: Todas as demais tarefas (sem mkdocs.yml nao tem nav)

---

## Objetivo

Criar `mkdocs.yml` na raiz do projeto, adicionar grupo `[project.optional-dependencies].docs`
em `pyproject.toml`, e instalar as dependencias. Apos esta tarefa, `mkdocs build` deve
rodar sem erros (mesmo com poucas paginas).

---

## Arquivos a criar/editar

- **Criar**: `/home/guhaase/projetos/vulpcode/mkdocs.yml`
- **Editar**: `/home/guhaase/projetos/vulpcode/pyproject.toml` (adicionar group `docs`)
- **Criar**: `/home/guhaase/projetos/vulpcode/docs/index.md` (placeholder minimo, real
  vem na 01.03)

---

## Conteudo do `mkdocs.yml`

```yaml
site_name: Vulpcode
site_description: Terminal coding agent — multi-provider, agentic, written in Python.
site_author: Vulpcode Authors
site_url: https://vulpcode.readthedocs.io/

repo_name: vulpcode/vulpcode
repo_url: https://github.com/vulpcode/vulpcode
edit_uri: edit/main/docs/

copyright: Copyright &copy; 2026 Vulpcode Authors

docs_dir: docs

theme:
  name: material
  language: pt-BR
  palette:
    - media: "(prefers-color-scheme: light)"
      scheme: default
      primary: deep purple
      accent: deep orange
      toggle:
        icon: material/brightness-7
        name: Modo escuro
    - media: "(prefers-color-scheme: dark)"
      scheme: slate
      primary: black
      accent: deep orange
      toggle:
        icon: material/brightness-4
        name: Modo claro
  font:
    text: Inter
    code: JetBrains Mono
  features:
    - navigation.instant
    - navigation.tracking
    - navigation.tabs
    - navigation.tabs.sticky
    - navigation.sections
    - navigation.expand
    - navigation.top
    - navigation.footer
    - navigation.indexes
    - search.suggest
    - search.highlight
    - content.code.copy
    - content.code.annotate
    - content.tabs.link
    - toc.integrate
  icon:
    repo: fontawesome/brands/github
    edit: material/pencil
    view: material/eye
  logo: assets/images/logo.svg
  favicon: assets/images/logo.svg

plugins:
  - search:
      lang:
        - pt
        - en
  - mkdocstrings:
      handlers:
        python:
          paths: [src]
          options:
            docstring_style: google
            docstring_section_style: table
            show_root_heading: true
            show_source: true
            show_signature_annotations: true
            separate_signature: true
            merge_init_into_class: true
            members_order: source
            show_if_no_docstring: false

markdown_extensions:
  - abbr
  - admonition
  - attr_list
  - def_list
  - footnotes
  - md_in_html
  - tables
  - toc:
      permalink: true
      toc_depth: 3

  - pymdownx.betterem:
      smart_enable: all
  - pymdownx.caret
  - pymdownx.details
  - pymdownx.highlight:
      anchor_linenums: true
      line_spans: __span
      pygments_lang_class: true
  - pymdownx.inlinehilite
  - pymdownx.keys
  - pymdownx.mark
  - pymdownx.smartsymbols
  - pymdownx.superfences
  - pymdownx.tabbed:
      alternate_style: true
  - pymdownx.tasklist:
      custom_checkbox: true
  - pymdownx.tilde

extra_css:
  - stylesheets/extra.css

extra:
  social:
    - icon: fontawesome/brands/github
      link: https://github.com/vulpcode/vulpcode
    - icon: fontawesome/brands/python
      link: https://pypi.org/project/vulpcode/

# A nav e ATUALIZADA INCREMENTALMENTE pelas tarefas seguintes.
# Por enquanto, so a landing.
nav:
  - Home: index.md
```

---

## Adicao em `pyproject.toml`

Localize `[project.optional-dependencies]` e adicione (mantenha os grupos existentes
`dev` e `search`):

```toml
docs = [
    "mkdocs>=1.6",
    "mkdocs-material>=9.5",
    "mkdocstrings[python]>=0.26",
    "pymdown-extensions>=10.7",
]
```

---

## Conteudo placeholder de `docs/index.md`

Crie um arquivo MINIMO so para o build funcionar — sera substituido na 01.03:

```markdown
# Vulpcode

> Documentacao em construcao. Veja o [README](https://github.com/vulpcode/vulpcode).
```

---

## INSTRUCAO CRITICA

- **Idioma do site**: Portugues (pt-BR). Mas `mkdocs.yml` em ingles.
- Nao remover os grupos `dev` e `search` do `[project.optional-dependencies]`.
- A `nav:` no mkdocs.yml e atualizada incrementalmente — esta tarefa deixa apenas
  `Home: index.md`. As tarefas seguintes vao ADICIONAR entradas.
- Apos editar `pyproject.toml`, instalar as deps: `pip install -e '.[docs]'`.
- O comando final de validacao e: `mkdocs build --strict`. Deve completar
  com 0 warnings.

---

## Etapas de Implementacao

### Etapa 1: Editar `pyproject.toml` adicionando `docs` em optional-dependencies

### Etapa 2: Criar `mkdocs.yml`

### Etapa 3: Criar `docs/index.md` placeholder

### Etapa 4: Instalar deps e validar build

```bash
cd /home/guhaase/projetos/vulpcode
pip install -e '.[docs]'
mkdocs build --strict
```

Deve terminar com `INFO - Documentation built` e zero warnings.

---

## Criterios de Aceite

- [x] `pyproject.toml` tem grupo `[project.optional-dependencies].docs` com mkdocs, mkdocs-material, mkdocstrings[python], pymdown-extensions
- [x] `pip install -e '.[docs]'` instala sem erro
- [x] `mkdocs.yml` criado na raiz com `site_name`, `theme: material`, `language: pt-BR`, paleta light+dark, plugins search e mkdocstrings, todas as `markdown_extensions` listadas, e `nav: [Home: index.md]`
- [x] `mkdocstrings` configurado com `paths: [src]` (para encontrar `vulpcode`)
- [x] `docs/index.md` criado com conteudo placeholder
- [x] `docs/stylesheets/extra.css` criado (pode estar vazio — sera preenchido em 01.02)
- [x] `mkdocs build --strict` completa sem warnings
- [x] `site/index.html` foi gerado (existe apos build)

---

## Riscos

| Risco | Mitigacao |
|-------|-----------|
| mkdocstrings nao acha modulos | `paths: [src]` direciona para `src/vulpcode` |
| Build falha por nav vazio | `nav` precisa ter pelo menos uma entrada — `index.md` resolve |
| Tema Material muda API entre versoes | Pinar `>=9.5` no pyproject |

---

**End of Specification**
