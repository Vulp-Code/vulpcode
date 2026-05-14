# Tarefa 13.01 - Verificar Links + Build Strict

**Status**: PENDENTE
**Fase**: 13 - Build Final
**Dependencias**: 12.01
**Bloqueia**: 13.02

---

## Objetivo

Garantir que `mkdocs build --strict` passa sem nenhum warning. Resolver
todos os links quebrados acumulados das fases anteriores. Adicionar
`docs/changelog.md` integrado.

---

## Arquivos a criar/editar

- `docs/changelog.md` (novo)
- Possiveis ajustes em qualquer arquivo do `docs/` para resolver links

---

## Source de verdade

- `CHANGELOG.md` (raiz) — para integrar em `docs/changelog.md`
- Todos os arquivos em `docs/`

---

## Estrutura

### 1. Integrar CHANGELOG

`docs/changelog.md`:

```markdown
---
title: Changelog
---

# Changelog

{!../CHANGELOG.md!}
```

(usa o include do `pymdownx.snippets` se habilitado, ou simplesmente copiar
conteudo)

ALTERNATIVA mais robusta: copy explicito do conteudo da raiz, com nota:

```markdown
# Changelog

> Espelho de [`CHANGELOG.md`](https://github.com/vulpcode/vulpcode/blob/main/CHANGELOG.md) na raiz do repo.

## [0.1.0] - 2026-05-06

(conteudo)
```

### 2. Habilitar snippets (se for usar include)

Em `mkdocs.yml`, adicionar em `markdown_extensions`:

```yaml
- pymdownx.snippets:
    base_path: ['.', 'docs']
    check_paths: true
```

### 3. Adicionar entrada no nav

```yaml
nav:
  ...
  - Changelog: changelog.md
```

### 4. Rodar build estrito

```bash
cd /home/guhaase/projetos/vulpcode
mkdocs build --strict
```

Se aparecer warning de:
- **Link quebrado**: ajustar o link ou criar pagina faltante
- **Anchor invalido** (`#secao-x`): ajustar para anchor real
- **Imagem nao encontrada**: criar ou ajustar caminho

### 5. Verificar manualmente

```bash
mkdocs serve
```

Navegar:
- Home -> cada link funciona?
- Cada provider -> conteudo renderiza?
- API reference -> mkdocstrings expande tudo?
- Diagramas mermaid renderizam?
- Logo aparece?
- Theme toggle funciona?

### 6. Verificar SEO basico

Cada pagina deve ter:
- `title` no front matter (ou H1 unico)
- `description` no front matter
- Estrutura de headings hierarquica (sem pular niveis)

### 7. Resolver os warnings

Lista comum esperada:

- "Doc file 'X.md' contains a link 'Y.md' that is not found" → criar Y.md ou
  ajustar link
- "Doc file 'X.md' contains an unrecognized relative link" → caminho
  relativo errado

Ler cada warning e resolver. Iterar ate `--strict` passar.

---

## INSTRUCAO CRITICA

- `mkdocs build --strict` deve passar com **zero warnings**.
- Se algum link aponta para algo planejado mas nao criado (ex:
  `recipes/some-future.md`), ou cria a pagina ou remove o link.
- `pymdownx.snippets` precisa estar em markdown_extensions se for usar `{!path!}`.

---

## Etapas de Implementacao

### Etapa 1: Rodar `mkdocs build --strict` e capturar todos os warnings
### Etapa 2: Resolver cada warning
### Etapa 3: Criar `docs/changelog.md`
### Etapa 4: Atualizar `mkdocs.yml` (snippets + nav)
### Etapa 5: Rodar build novamente — passar com zero warnings
### Etapa 6: `mkdocs serve` e verificar visualmente

---

## Criterios de Aceite

- [ ] `mkdocs build --strict` completa com zero warnings
- [ ] `docs/changelog.md` criado e linkado
- [ ] `mkdocs.yml` atualizado com `Changelog` no nav
- [ ] Todos os links internos resolvem
- [ ] Logo, favicon, CSS extra funcionando
- [ ] mkdocstrings renderiza todas as classes/funcoes referenciadas
- [ ] Diagramas mermaid renderizam
- [ ] `mkdocs serve` exibe nav completo (todas as 10+ secoes)

---

**End of Specification**
