# Permissions

Sistema de permissoes para execucao de tools. O [`Agent`](agent.md) consulta
um `PermissionManager` antes de cada chamada de tool e respeita o veredicto.

Para o lado operacional (qual modo usar no dia-a-dia, como persistir
allowlists em `config.toml`, etc.) veja:

- [Modos de permissao](../user-guide/permission-modes.md) — guia do usuario.
- [Configuracao avancada](../configuration/permissions.md) — `always_allow_tools`
  e politicas por arquivo.

## Mode

Os quatro modos suportados. `DEFAULT` e o seguro padrao interativo;
`AUTO` e para automacao confiavel; `SAFE` pede confirmacao em **todo**
tool; `PLAN` deixa o agente raciocinar sem executar nada.

::: vulpcode.permissions.Mode
    options:
      heading_level: 3
      show_root_heading: false
      show_root_full_path: false

## PermissionDecision

Resultado retornado por [`PermissionManager.check`](#vulpcode.permissions.PermissionManager.check).

::: vulpcode.permissions.PermissionDecision
    options:
      heading_level: 3
      show_root_heading: false
      show_root_full_path: false

## PermissionManager

::: vulpcode.permissions.PermissionManager
    options:
      heading_level: 3
      show_root_heading: true
      show_root_full_path: false
      merge_init_into_class: true
      members_order: source

## Prompter padrao

Implementacao referencia que le `y`/`a`/`n` da entrada padrao. Use-a como
modelo ao escrever um prompter custom.

::: vulpcode.permissions.stdin_prompter
    options:
      heading_level: 3
      show_root_heading: true
      show_root_full_path: false

::: vulpcode.permissions.PrompterFn
    options:
      heading_level: 4
      show_root_heading: true
      show_root_full_path: false

### Custom prompter

Substitua o prompter para integrar com uma TUI, web UI ou um teste
automatizado. O contrato e simples: receber a mensagem + contexto e devolver
`"y"`, `"a"` ou `"n"`.

```python
from vulpcode.permissions import Mode, PermissionManager

async def my_prompter(message: str, ctx: dict) -> str:
    # ctx: {"name": "<tool>", "arguments": {...}}
    # Decida (TUI, popup, regra de negocio) e devolva "y" / "a" / "n".
    print(f"Agente quer rodar {ctx['name']!r} com {ctx['arguments']!r}")
    return "y"

pm = PermissionManager(config={}, mode=Mode.DEFAULT, prompter=my_prompter)
```

!!! note "Allowlist da sessao"
    Quando o usuario responde `"a"` o `PermissionManager` adiciona o nome do
    tool em `_session_allowlist`, evitando perguntar de novo no mesmo
    processo. Para persistir entre sessoes, configure
    `permissions.always_allow_tools` no
    [`config.toml`](../configuration/config-toml.md).
