# Config

Carregamento e persistencia de configuracao com hierarquia bem definida:

> `DEFAULTS` < `~/.vulpcode/config.toml` < `<projeto>/.vulpcode/config.toml`
> < env vars < CLI overrides

Camadas posteriores sobrescrevem as anteriores via *deep-merge*; listas
sao **substituidas** (nao concatenadas). Para o uso operacional — onde
cada arquivo vive, quais chaves existem, exemplos prontos — veja
[Configuracao](../configuration/index.md).

## Defaults e ENV_MAP

`DEFAULTS` e `ENV_MAP` sao constantes de modulo. mkdocstrings as renderiza
inline com o valor — util para conferir rapidamente o esqueleto do config
e o conjunto de variaveis de ambiente reconhecidas.

::: vulpcode.config.DEFAULTS
    options:
      heading_level: 3
      show_root_heading: true
      show_root_full_path: false

::: vulpcode.config.ENV_MAP
    options:
      heading_level: 3
      show_root_heading: true
      show_root_full_path: false

## Funcoes

::: vulpcode.config.load_config
    options:
      heading_level: 3
      show_root_heading: true
      show_root_full_path: false

::: vulpcode.config.save_config
    options:
      heading_level: 3
      show_root_heading: true
      show_root_full_path: false

::: vulpcode.config.config_paths
    options:
      heading_level: 3
      show_root_heading: true
      show_root_full_path: false

## Exemplo

```python
from pathlib import Path

from vulpcode.config import config_paths, load_config, save_config

# Inspecionar a ordem de descoberta dos config.toml
for p in config_paths():
    print("would load:", p, "(exists)" if p.exists() else "(missing)")

# Carregar config aplicando todas as camadas
cfg = load_config()
print(cfg["default_provider"])
print(cfg["providers"].get("anthropic", {}).get("api_key"))

# Em testes: ignore env e use overrides explicitos
cfg = load_config(
    cli_overrides={"default_provider": "ollama"},
    cwd=Path("/tmp/projeto-fake"),
    env={},
)

# Persistir uma alteracao no config global
cfg["ui"]["show_token_usage"] = False
saved_to = save_config(cfg, scope="global")
print("saved to", saved_to)
```

!!! tip "Round-trip garantido"
    `save_config(load_config())` produz um arquivo equivalente — voce
    pode editar o dict em memoria, salvar, e o resultado volta intacto
    pelo `load_config` na proxima execucao.

!!! warning "Listas sobrescrevem"
    `permissions.always_allow_tools = ["X"]` no config global e
    `["Y"]` no projeto resulta em `["Y"]`, nao em `["X", "Y"]`. Defina
    a lista completa no nivel onde voce quer o efeito.

Veja tambem:

- [config.toml](../configuration/config-toml.md) — chaves disponiveis
  com exemplos.
- [Variaveis de ambiente](../configuration/env-vars.md) — referencia
  rapida de cada `VULPCODE_*` / `*_API_KEY`.
