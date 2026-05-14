# Tarefa 01.02 - Logo e Assets

**Status**: PENDENTE
**Fase**: 01 - Bootstrap MkDocs
**Dependencias**: 01.01 (mkdocs setup)
**Bloqueia**: 01.03 (landing usa o logo)

---

## Objetivo

Criar logo SVG da Vulpcode (raposa estilizada + simbolo de codigo, usando paleta
roxo/laranja do tema), favicon, e CSS extra com customizacoes leves (cor da home,
classes auxiliares).

---

## Arquivos a criar

- `/home/guhaase/projetos/vulpcode/docs/assets/images/logo.svg`
- `/home/guhaase/projetos/vulpcode/docs/assets/images/logo_text.svg` (com nome ao lado)
- `/home/guhaase/projetos/vulpcode/docs/assets/images/favicon.svg`
- `/home/guhaase/projetos/vulpcode/docs/stylesheets/extra.css`

---

## Logo SVG — design

- **Conceito**: cabeca/silhueta de raposa estilizada + chaves `{}` ou prompt `>` indicando codigo.
- **Paleta**: `#673AB7` (deep purple, primary do tema) + `#FF5722` (deep orange, accent).
- **Estilo**: flat, geometrico, viewBox 256x256.
- **Sem texto** no `logo.svg` (so o icone). O `logo_text.svg` tem o nome "vulpcode" ao lado.

Conteudo sugerido para `logo.svg` (ajustar se necessario):

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" fill="none">
  <!-- Cabeca de raposa em forma de losango invertido -->
  <path d="M128 32 L208 96 L168 192 L128 224 L88 192 L48 96 Z"
        fill="#673AB7"/>
  <!-- Orelhas -->
  <path d="M48 96 L72 32 L96 80 Z" fill="#FF5722"/>
  <path d="M208 96 L184 32 L160 80 Z" fill="#FF5722"/>
  <!-- Olhos -->
  <circle cx="100" cy="120" r="8" fill="#fff"/>
  <circle cx="156" cy="120" r="8" fill="#fff"/>
  <!-- Focinho -->
  <path d="M128 144 L116 168 L140 168 Z" fill="#fff"/>
  <!-- Prompt > -->
  <path d="M104 196 L120 184 L104 172"
        stroke="#fff" stroke-width="6" stroke-linecap="round"
        stroke-linejoin="round" fill="none"/>
</svg>
```

> Se o resultado visual ficar pobre, refine. O importante e que seja legivel
> em 32x32 (favicon size) e em 192x192 (header).

`favicon.svg` pode ser uma copia simplificada do `logo.svg` (removendo detalhes
finos) ou o mesmo arquivo.

`logo_text.svg` adiciona "vulpcode" em JetBrains Mono ao lado do icone (viewBox
mais largo, ~640x256). E usado na landing (FASE 01.03).

---

## Conteudo de `extra.css`

```css
/* Vulpcode — small visual tweaks on top of Material. */

/* Bigger landing logo */
.home-logo img {
  max-width: 280px;
  margin: 1rem auto 0.5rem;
  display: block;
}

/* Code block fine-tune */
.md-typeset .highlight pre {
  font-size: 0.85rem;
  line-height: 1.5;
}

/* Provider/tool badge */
.vulp-badge {
  display: inline-block;
  padding: 0.1rem 0.5rem;
  border-radius: 0.25rem;
  font-size: 0.75rem;
  font-weight: 600;
  background: var(--md-accent-fg-color--transparent);
  color: var(--md-accent-fg-color);
  margin-right: 0.25rem;
}
.vulp-badge.warn   { background: #FFEB3B33; color: #F57F17; }
.vulp-badge.danger { background: #FF522233; color: #BF360C; }
.vulp-badge.ok     { background: #4CAF5033; color: #1B5E20; }

/* Compact admonitions on dark theme */
[data-md-color-scheme="slate"] .md-typeset .admonition {
  background: #1e1e1e;
}

/* Footer credit accent */
.md-footer-meta {
  background: var(--md-primary-fg-color);
}
```

---

## INSTRUCAO CRITICA

- O SVG do logo pode ser **simples** mas precisa carregar/renderizar corretamente.
  Apos criar, abra com browser ou `xdg-open` para verificar.
- `mkdocs.yml` ja referencia `logo: assets/images/logo.svg` na FASE 01.01 —
  NAO precisa editar mkdocs.yml de novo.
- O `extra.css` ja foi listado em `extra_css` na FASE 01.01 — apenas preencher.
- Mantenha tamanhos pequenos (logo svg < 5KB, css < 3KB). Sao incluidos em todas
  as paginas.

---

## Etapas de Implementacao

### Etapa 1: Criar diretorios

```bash
mkdir -p /home/guhaase/projetos/vulpcode/docs/assets/images
mkdir -p /home/guhaase/projetos/vulpcode/docs/stylesheets
```

### Etapa 2: Criar `logo.svg`, `logo_text.svg`, `favicon.svg`

### Etapa 3: Criar `extra.css`

### Etapa 4: Validar build

```bash
cd /home/guhaase/projetos/vulpcode
mkdocs build --strict
```

E abrir `mkdocs serve` para verificar que o logo aparece no header.

---

## Criterios de Aceite

- [x] `docs/assets/images/logo.svg` criado, valido (abre em browser)
- [x] `docs/assets/images/logo_text.svg` criado (icone + nome "vulpcode")
- [x] `docs/assets/images/favicon.svg` criado
- [x] `docs/stylesheets/extra.css` criado com os blocos descritos
- [x] `mkdocs build --strict` continua passando
- [x] Logo visivel ao rodar `mkdocs serve` (no header superior esquerdo)
- [x] Cores do CSS compativeis com tema light e dark

---

## Riscos

| Risco | Mitigacao |
|-------|-----------|
| SVG complexo nao renderiza no Safari/Edge | Manter formas simples (paths basicos) |
| Logo apaga em dark mode | Cor primaria roxa funciona em ambos os schemes |

---

**End of Specification**
