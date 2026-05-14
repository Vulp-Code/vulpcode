# Configuracao

Esta secao documenta **toda** a superficie de configuracao do Vulpcode em
detalhe: cada chave do `config.toml`, cada variavel de ambiente reconhecida
e o sistema de permissoes avancado.

> Se voce esta comecando, va para
> [Primeira configuracao](../getting-started/first-config.md) primeiro — esta
> secao e a referencia completa, nao um tutorial.

---

## Hierarquia de precedencia

O Vulpcode resolve a configuracao final aplicando **cinco camadas**, da mais
fraca para a mais forte. Cada camada faz `_deep_merge` sobre a anterior:
chaves nao mencionadas sao preservadas; listas sao **substituidas**, nao
concatenadas.

| # | Fonte                                  | Caminho / origem                              |
|---|----------------------------------------|-----------------------------------------------|
| 1 | Defaults internos                      | `vulpcode.config.DEFAULTS`                    |
| 2 | Config global                          | `~/.vulpcode/config.toml`                     |
| 3 | Config de projeto                      | `<projeto>/.vulpcode/config.toml` (sobe a arvore a partir do `cwd`) |
| 4 | Variaveis de ambiente                  | `vulpcode.config.ENV_MAP`                     |
| 5 | Flags da CLI                           | `vulp --provider ... --model ...`             |

A descoberta de config de projeto sobe a arvore de diretorios a partir do
`cwd`: a primeira pasta com `.vulpcode/config.toml` vence.

### Diagrama de prioridade

```text
DEFAULTS                              (mais fraco)
    |
    v  _deep_merge
~/.vulpcode/config.toml               (global, por usuario)
    |
    v  _deep_merge
<projeto>/.vulpcode/config.toml       (projeto, sobrescreve global)
    |
    v  _set_path por chave de ENV_MAP
variaveis de ambiente                 (so as listadas em ENV_MAP)
    |
    v  _deep_merge
flags de CLI (cli_overrides)          (mais forte)
```

A logica vive em `load_config()` em
[`src/vulpcode/config.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/config.py).

---

## Como descobrir a config efetiva

Use o slash command no REPL ou um snippet Python para ver o resultado final
do merge:

=== "REPL"

    ```text
    /config
    ```

=== "Python"

    ```python
    import json
    from vulpcode.config import load_config

    cfg = load_config()
    print(json.dumps(cfg, indent=2, default=str))
    ```

---

## Paginas desta secao

- [config.toml](config-toml.md) — referencia completa de todas as chaves do
  `DEFAULTS`, com tipo, default e exemplo realista para cada uma.
- [Variaveis de ambiente](env-vars.md) — tabela completa do `ENV_MAP` (mais
  `TAVILY_API_KEY`, lida diretamente pela tool `WebSearch`).
- [Permissoes (avancado)](permissions.md) — `always_allow_tools`, prompter
  customizado e integracao com o `PermissionManager`.

---

## Veja tambem

- [Primeira configuracao](../getting-started/first-config.md) — tutorial introdutorio.
- [Modos de permissao](../user-guide/permission-modes.md) — visao geral dos modos.
- [Providers](../providers/index.md) — chaves especificas de cada provider.
