# Profiles

## Quando usar

Use profiles quando quiser ativar um conjunto pré-configurado de ferramentas, middleware e instrução de sistema sem editar o `config.toml` manualmente. Útil para alternar entre contextos (auditoria somente-leitura, desenvolvimento intenso, pesquisa) ou para distribuir configurações padronizadas para uma equipe.

## Ativar um profile

Passe `--profile NAME` na linha de comando ou use `/profile switch NAME` dentro do REPL e reinicie:

```bash
vulp --profile safe         # inicia com o profile built-in "safe"
vulp --profile code "refatore o módulo auth"
```

Dentro do REPL:

```
/profile list               # lista todos os profiles disponíveis
/profile switch research    # instrui a reiniciar com --profile research
/profile                    # mostra qual profile está ativo
```

## Profiles built-in

| Profile    | Descrição                                                               |
|------------|-------------------------------------------------------------------------|
| `safe`     | Apenas ferramentas de leitura (Read, Grep, Glob, Tree). Sem Bash/Write. |
| `code`     | Edição completa + Bash. Ativa summarization, context_hub e eviction.    |
| `research` | Leitura + web search. Usa Opus, ativa summarization e context_hub.      |

## Definir um profile em `config.toml`

Seções `[profiles.NAME]` no `~/.vulpcode/config.toml` ou `.vulpcode/config.toml` do projeto:

```toml
[profiles.review]
description = "Code review: leitura + diff. Sem escrita."
tools_allow = ["Read", "Grep", "Glob", "Tree", "Bash"]
tools_deny  = ["Write", "Edit", "MultiEdit"]

system_prompt_extra = """
Você está fazendo code review. Aponte problemas concretos com referência de linha.
Não edite arquivos.
"""

[profiles.review.middleware.context_hub]
enabled = true
threshold_chars = 3000
```

## Profile como arquivo TOML separado

Crie `~/.vulpcode/profiles/review.toml` (ou `.vulpcode/profiles/review.toml` no projeto):

```toml
description = "Code review: leitura + diff."

tools_allow = ["Read", "Grep", "Glob", "Tree", "Bash"]
tools_deny  = ["Write", "Edit", "MultiEdit"]

system_prompt_extra = "Faça code review detalhado."
```

## Ordem de precedência

1. Diretórios em `search_dirs` (projeto > global)
2. Seção `[profiles.NAME]` no `config.toml`
3. Profiles built-in do pacote

## Campos reconhecidos num profile

| Campo               | Efeito                                            |
|---------------------|---------------------------------------------------|
| `description`       | Metadado; exibido no `/profile list`              |
| `provider`          | Sobrescreve `default_provider`                    |
| `model`             | Sobrescreve `default_model`                       |
| `tools_allow`       | Substitui (não une) a lista global                |
| `tools_deny`        | Substitui a lista global                          |
| `system_prompt_extra` | Texto extra injetado no system prompt           |
| `skills_priority`   | Lista de skills a carregar primeiro               |
| `[middleware.X]`    | Substitui a seção inteira de middleware X         |

## Carregando via API Python

```python
from pathlib import Path
from vulpcode.harness.profiles import Profile, apply_profile
from vulpcode.config import load_config

cfg = load_config()
profile = Profile.load("safe", search_dirs=[Path(".vulpcode/profiles")])
merged_cfg = apply_profile(cfg, profile)
```

## Troubleshooting

**`ProfileNotFound` ao iniciar**
Execute `/profile list` para ver os nomes disponíveis. O nome é o stem do arquivo TOML (sem extensão) ou a chave da seção `[profiles.NAME]`.

**Profile não altera o model/provider no REPL**
Provider e model são fixados na inicialização. Use `--profile NAME` ao abrir o Vulpcode — `/profile switch` só confirma o perfil para a próxima sessão.

**Middleware do profile não está ativando**
Seções `[middleware.X]` em profiles substituem a seção inteira. Se o profile define `[middleware.eviction]` sem `enabled = true`, o middleware fica desabilitado mesmo que o `config.toml` global o habilite.
