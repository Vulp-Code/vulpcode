# Tarefa 10.02 - Slash Commands /provider e /model

**Status**: PENDENTE
**Fase**: 10 - Slash Commands
**Dependencias**: 10.01, 03.05 (registry de providers)
**Bloqueia**: 10.03

---

## Objetivo

Adicionar comandos `/provider [nome]` e `/model [nome]` ao registry de slash
commands. Sem argumentos, listam disponivel; com argumento, trocam.

---

## Descricao Tecnica

### /provider

```python
class ProviderCommand(SlashCommand):
    name = "provider"
    help_text = "List or switch the active provider"
```

- Sem args: lista providers conhecidos via `list_provider_names()`.
- Com arg `name`: substitui `repl.agent.provider` por `build_provider(name, ...)`,
  pega config atual.

### /model

```python
class ModelCommand(SlashCommand):
    name = "model"
    help_text = "List or switch the active model"
```

- Sem args: chama `await provider.list_models()` e tabula.
- Com arg: atualiza `repl.agent.model` para o nome dado.

### Estrutura

**`src/vulpcode/commands/provider_model.py`**:

```python
"""/provider and /model commands."""
from __future__ import annotations

from vulpcode.commands._base import SlashCommand
from vulpcode.providers import build_provider, list_provider_names


class ProviderCommand(SlashCommand):
    name = "provider"
    help_text = "List providers, or switch with /provider <name>"

    async def run(self, repl, args: str) -> None:
        if not args:
            current = type(repl.agent.provider).__name__
            rows = []
            for n in list_provider_names():
                marker = "*" if n == repl.agent.provider.name else ""
                rows.append([n, marker])
            repl.renderer.render_table("Providers", ["name", "active"], rows)
            repl.renderer.console.print(f"[muted]current: {current}[/]")
            return

        name = args.strip()
        if name not in list_provider_names():
            repl.renderer.render_error(f"Unknown provider: {name}")
            return
        cfg = repl.config.get("providers", {}).get(name, {})
        try:
            new_provider = build_provider(name, cfg)
        except Exception as exc:
            repl.renderer.render_error(f"Failed to build provider {name}: {exc}")
            return

        # Close previous if it has aclose
        old = repl.agent.provider
        try:
            await old.aclose()
        except Exception:
            pass
        repl.agent.provider = new_provider
        repl.renderer.console.print(f"[green]provider switched to {name}[/]")


class ModelCommand(SlashCommand):
    name = "model"
    help_text = "List models, or switch with /model <name>"

    async def run(self, repl, args: str) -> None:
        if not args:
            try:
                models = await repl.agent.provider.list_models()
            except Exception as exc:
                repl.renderer.render_error(f"list_models failed: {exc}")
                return
            current = repl.agent.model
            if not models:
                repl.renderer.console.print(
                    f"[muted]no models reported by provider; current: {current}[/]"
                )
                return
            rows = [[m, "*" if m == current else ""] for m in models]
            repl.renderer.render_table("Models", ["name", "active"], rows)
            return
        repl.agent.model = args.strip()
        repl.renderer.console.print(f"[green]model set to {repl.agent.model}[/]")
```

### Atualizar `commands/__init__.py`

```python
from vulpcode.commands.provider_model import ModelCommand, ProviderCommand


def build_default_commands() -> dict[str, SlashCommand]:
    cmds = [
        ToolsCommand(),
        CostCommand(),
        CompactCommand(),
        ProviderCommand(),
        ModelCommand(),
    ]
    return {c.name: c for c in cmds}
```

---

## INSTRUCAO CRITICA

- Trocar provider em runtime requer fechar o anterior (`aclose`) — mesmo que
  ele falhe, continuar.
- O modelo trocado fica em `repl.agent.model` (string). Validacao real do nome
  acontece na proxima chamada `provider.stream(model=...)`.
- `list_provider_names()` ja existe no registry da FASE 03.05.

---

## Etapas de Implementacao

### Etapa 1: Criar `commands/provider_model.py`

### Etapa 2: Atualizar `commands/__init__.py`

### Etapa 3: Atualizar `tests/test_commands.py`

```python
@pytest.mark.asyncio
async def test_provider_command_lists():
    from vulpcode.commands import ProviderCommand
    from vulpcode.providers.anthropic import AnthropicProvider
    class Agent:
        provider = AnthropicProvider(api_key="x")
        model = ""
    repl = FakeRepl(agent=Agent())
    repl.config = {"providers": {}}
    await ProviderCommand().run(repl, "")
    assert "anthropic" in repl.buf.getvalue()


@pytest.mark.asyncio
async def test_model_command_set():
    from vulpcode.commands import ModelCommand
    class P:
        name = "x"
        async def list_models(self): return ["m1", "m2"]
    class Agent:
        provider = P()
        model = ""
    repl = FakeRepl(agent=Agent())
    await ModelCommand().run(repl, "m1")
    assert repl.agent.model == "m1"
```

(Adicionar `repl.config = {...}` quando faltar.)

### Etapa 4: Rodar testes

```bash
pytest tests/test_commands.py -v
```

---

## Criterios de Aceite

- [x] `src/vulpcode/commands/provider_model.py` define `ProviderCommand` e `ModelCommand`
- [x] `/provider` (sem args) lista providers; `/provider <name>` troca o provider
- [x] `/model` (sem args) lista modelos do provider; `/model <name>` define o modelo
- [x] Trocar provider chama `aclose()` no antigo
- [x] `commands/__init__.py` inclui ambos em `build_default_commands()`
- [x] `tests/test_commands.py` com >=2 testes adicionais, passando

---

## Riscos Tecnicos

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|---------------|---------|-----------|
| API key ausente para novo provider | Alta | Medio | build_provider falha graciosamente |
| Modelo novo invalido nao detectado ate stream | Alta | Baixo | Aceitar — usuario corrige na hora |

---

**End of Specification**
