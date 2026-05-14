# Tarefa 03.02 - Modos de Permissao

**Status**: PENDENTE
**Fase**: 03 - User Guide
**Dependencias**: 03.01
**Bloqueia**: 03.03

---

## Objetivo

Criar `user-guide/permission-modes.md` explicando os 4 modos (`default`, `auto`,
`safe`, `plan`), o fluxo `y/a/n`, allowlist por sessao, e a interacao com
`always_allow_tools`.

---

## Arquivos a criar

- `docs/user-guide/permission-modes.md`

---

## Source de verdade

- `src/vulpcode/permissions.py` — `Mode`, `PermissionManager`, `stdin_prompter`
- `src/vulpcode/cli.py` — flags `--auto`, `--safe`, `--plan`
- `src/vulpcode/app.py` — `_make_permissions`
- `src/vulpcode/tools/*.py` — quais tools tem `requires_confirm=True`

---

## Estrutura sugerida

### 1. Visao geral

Tabela comparativa:

| Modo      | Flag CLI   | Read | Write | Edit | Bash | Tool nao-destrutiva |
|-----------|------------|------|-------|------|------|----------------------|
| `default` | (sem flag) | OK   | pede  | pede | pede | OK                   |
| `auto`    | `--auto`   | OK   | OK    | OK   | OK   | OK                   |
| `safe`    | `--safe`   | pede | pede  | pede | pede | pede                 |
| `plan`    | `--plan`   | NAO  | NAO   | NAO  | NAO  | NAO                  |

### 2. Quais tools sao destrutivas?

Lista tools com `requires_confirm=True`:
- Bash
- Write
- Edit
- MultiEdit
- KillBash
- NotebookEdit

(confirmar lendo cada arquivo em `src/vulpcode/tools/`)

### 3. Modo default — explicado

Como `[permission]` aparece, opcoes `y/a/n`, comportamento de cada uma.

```
[permission] Tool 'Write' wants to run.
Tool args: {'file_path': '/tmp/x.txt', 'content': '...'}
[y] yes once  [a] always for this tool  [n] no
```

Explicar:
- `y`: aprova esta vez. Se a mesma tool aparecer em outra chamada na mesma
  sessao, vai perguntar de novo.
- `a`: adiciona ao session allowlist. Toda chamada subsequente dessa tool
  passa direto. Allowlist morre quando o REPL termina.
- `n`: rejeita. O agente recebe um erro de tool e pode tentar outra abordagem.

### 4. Modo auto

Casos de uso:
- Headless / pipeline / `--print` mode
- Voce ja revisou o pedido e confia
- Fluxos automatizados

Aviso: nunca usar com input nao confiavel (ex: chat publico).

### 5. Modo safe

Pede confirmacao para TUDO, ate Read. Util para:
- Auditoria
- Demonstracao para terceiros
- Quando voce ainda nao confia no agente

### 6. Modo plan

Bloqueia execucao de TODAS as tools. O agente so consegue conversar — util para:
- Pedir um plano antes de executar
- Dry-run

### 7. Allowlist persistente

Em `~/.vulpcode/config.toml`:

```toml
[permissions]
always_allow_tools = ["Read", "Glob", "Grep"]
```

Adiciona essas tools ao allowlist em cada sessao. Equivalente a apertar `a`
em cada uma.

### 8. Padrao de uso recomendado

- **Iniciante**: `vulp` (default) — o sistema te ensina o que cada tool faz.
- **Desenvolvedor experiente**: `vulp --auto` ou `always_allow_tools` na config.
- **Demo**: `vulp --safe`.
- **Brainstorm**: `vulp --plan`.

---

## Atualizar `mkdocs.yml`

A entrada `Modos de permissao` ja foi adicionada em 03.01. Nao mexer.

---

## INSTRUCAO CRITICA

- Conferir a lista de tools destrutivas lendo o decorator `@tool(...,
  requires_confirm=True)` em cada arquivo `src/vulpcode/tools/*.py`. NAO
  invente.
- O fluxo `[permission]` e do `stdin_prompter` em `permissions.py`. A UI
  `streaming.py` tem um wrapper que pausa o spinner — mencionar.

---

## Etapas de Implementacao

### Etapa 1: Inventario de tools com `requires_confirm=True`
### Etapa 2: Criar `user-guide/permission-modes.md`
### Etapa 3: `mkdocs build`

---

## Criterios de Aceite

- [x] `docs/user-guide/permission-modes.md` criado
- [x] Tabela comparativa dos 4 modos
- [x] Lista de tools com `requires_confirm=True` (verificada contra source)
- [x] Explicacao de `y/a/n`
- [x] Secao sobre `always_allow_tools` no config.toml
- [x] Padrao de uso recomendado por perfil
- [x] `mkdocs build` continua passando

---

## Riscos

| Risco | Mitigacao |
|-------|-----------|
| Lista de tools destrutivas desatualizada | grep `requires_confirm=True` em src/vulpcode/tools/ |
| Mode names em portugues confundindo | Manter em ingles (sao os valores reais do enum) |

---

**End of Specification**
