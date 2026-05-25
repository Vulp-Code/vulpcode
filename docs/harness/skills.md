# Skills

## Quando usar

Skills são playbooks especializados carregados sob demanda no contexto do agente. Use quando quiser dar instruções detalhadas de domínio (convenções de código de um projeto, fluxos de refatoração, regras de review) sem poluir o system prompt padrão. O modelo só recebe o corpo da skill quando a invoca explicitamente com `LoadSkill`.

## Formato do SKILL.md

Cada skill vive em seu próprio subdiretório com um arquivo `SKILL.md`:

```markdown
---
name: refactor-python
description: Applies safe refactoring to Python code (rename, extract, inline) preserving
  behavior. Use when the user asks to "refactor", "extract function", or "rename" in a .py file.
tools_allow: [Read, Edit, Write, Grep, Glob, Bash]
---

# Refactor Python

1. Sempre leia o arquivo antes de editar.
2. Execute `python -m pytest` antes e depois para confirmar que o comportamento é preservado.
3. Para renames: use Grep para encontrar todos os call sites antes de alterar a definição.
```

### Campos do frontmatter

| Campo         | Obrigatório | Descrição                                                  |
|---------------|:-----------:|------------------------------------------------------------|
| `name`        | sim         | Identificador único; usado em `LoadSkill(name="...")`      |
| `description` | sim         | Resumo exibido no bloco "Skills disponíveis" do prompt     |
| `tools_allow` | não         | Lista de tools permitidas durante a skill; `null` = todas  |

Requer PyYAML para frontmatter completo. Sem ele, apenas `name` e `description` são lidos via regex. Instale com `pip install "vulpcode[docs-tools]"`.

## Estrutura de diretórios

```
~/.vulpcode/skills/              # global
│── refactor-python/
│   └── SKILL.md
└── sql-migration/
    └── SKILL.md

.vulpcode/skills/                # por projeto (tem precedência)
└── deploy-checklist/
    └── SKILL.md
```

Diretórios alternativos podem ser configurados em `config.toml`:

```toml
[skills]
enabled = true
search_dirs = ["/opt/company/skills", "~/.vulpcode/skills"]
```

## Como o agente descobre e carrega skills

1. No `before_send`, o `SkillRegistry` injeta um bloco "Skills disponíveis" no system prompt (nomes + descrições, sem o corpo).
2. Quando a tarefa combina com uma skill, o modelo chama `LoadSkill(name="...")`.
3. O `LoadSkill` tool retorna o corpo da skill e — se `tools_allow` estiver definido — ativa o filtro de tools para o restante da sessão.

## Uso via API Python

```python
from pathlib import Path
from vulpcode.harness.skills import Skill, SkillRegistry, SkillsConfig

cfg = SkillsConfig(search_dirs=[Path(".vulpcode/skills")])
registry = SkillRegistry(cfg)

for skill in registry.all():
    print(skill.name, "—", skill.description)

skill = registry.get("refactor-python")
print(skill.body)          # corpo completo do SKILL.md
print(skill.tools_allow)   # ["Read", "Edit", "Write", "Grep", "Glob", "Bash"]
```

## Troubleshooting

**Skill não aparece no `/skill list`**
Verifique se o diretório contém `SKILL.md` com `name` e `description` no frontmatter. Skills com frontmatter inválido são ignoradas com um `WARNING` no log.

**Nomes duplicados**
A primeira ocorrência vence (ordem: projeto > global > search_dirs em sequência). Um `WARNING` é emitido para as duplicatas ignoradas.

**Tool bloqueada após carregar skill**
A skill tem `tools_allow` que não inclui a tool necessária. Adicione-a à lista ou remova `tools_allow` do frontmatter para liberar todas as tools.

**`LoadSkill` retorna "Skill registry not configured"**
O `SkillRegistry` não foi registrado na sessão. Ative via `config.toml`:

```toml
[skills]
enabled = true
```
