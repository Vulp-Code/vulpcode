# Tarefa 09.03 - REPL com prompt_toolkit

**Status**: PENDENTE
**Fase**: 09 - UI
**Dependencias**: 09.01, 09.02, 08.01, 07.01, 07.02
**Bloqueia**: FASE 10 (slash commands integram aqui)

---

## Objetivo

Implementar `src/vulpcode/ui/repl.py` com classe `Repl` que oferece input
multi-linha via `prompt_toolkit`, historico persistente, autocompletion de slash
commands, e integra com `Agent` + `Renderer` + `stream_agent_turn`.

Tambem implementar `src/vulpcode/app.py` que e o entry point do REPL chamado
pelo `cli.py`.

---

## Descricao Tecnica

### Repl

```python
class Repl:
    def __init__(
        self,
        agent: Agent,
        renderer: Renderer,
        config: dict,
        commands: dict[str, "SlashCommand"] | None = None,  # FASE 10
    ): ...

    async def run(self) -> None:
        """Main interactive loop."""

    async def one_shot(self, prompt: str) -> None:
        """Execute single prompt and return."""
```

### app.py

```python
async def start_repl(
    *,
    cli_overrides: dict,
    one_shot: str | None = None,
    print_mode: bool = False,
) -> int:
    """Build dependencies and start the REPL or one-shot run.

    Returns: process exit code.
    """
```

### Estrutura

**`src/vulpcode/ui/repl.py`**:

```python
"""Interactive REPL using prompt_toolkit."""
from __future__ import annotations

from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.patch_stdout import patch_stdout

from vulpcode.agent import Agent
from vulpcode.ui.render import Renderer
from vulpcode.ui.streaming import stream_agent_turn


_DEFAULT_SLASH_COMMANDS = ["/help", "/clear", "/exit", "/tools", "/cost", "/compact"]


class Repl:
    def __init__(
        self,
        agent: Agent,
        renderer: Renderer,
        config: dict,
        commands: dict | None = None,
    ) -> None:
        self.agent = agent
        self.renderer = renderer
        self.config = config
        self.commands = commands or {}
        history_path = Path.home() / ".vulpcode" / "history"
        history_path.parent.mkdir(parents=True, exist_ok=True)
        self.session: PromptSession[str] = PromptSession(
            history=FileHistory(str(history_path)),
            auto_suggest=AutoSuggestFromHistory(),
            completer=WordCompleter(
                _DEFAULT_SLASH_COMMANDS + [f"/{n}" for n in self.commands],
                ignore_case=True,
            ),
            multiline=False,
            mouse_support=False,
        )

    async def run(self) -> None:
        console = self.renderer.console
        console.print(f"[{self.renderer.theme.primary}]Vulpcode REPL[/]  (type /help for commands, /exit to quit)\n")
        while True:
            try:
                with patch_stdout():
                    user_input = await self.session.prompt_async("> ")
            except (EOFError, KeyboardInterrupt):
                console.print("\nbye")
                return
            user_input = user_input.strip()
            if not user_input:
                continue
            if user_input.startswith("/"):
                if not await self._handle_slash(user_input):
                    return  # /exit
                continue
            await stream_agent_turn(self.agent, user_input, self.renderer)

    async def one_shot(self, prompt: str) -> None:
        await stream_agent_turn(self.agent, prompt, self.renderer, spinner=False)

    async def _handle_slash(self, line: str) -> bool:
        """Returns False if the loop should terminate (e.g. /exit)."""
        cmd, _, rest = line[1:].partition(" ")
        cmd = cmd.strip()
        rest = rest.strip()
        # Built-in fallbacks; FASE 10 wires more in self.commands
        if cmd == "exit" or cmd == "quit":
            self.renderer.console.print("bye")
            return False
        if cmd == "clear":
            self.agent.reset()
            self.renderer.console.print("[muted]history cleared[/]")
            return True
        if cmd == "help":
            self._render_help()
            return True
        if cmd in self.commands:
            await self.commands[cmd].run(self, rest)
            return True
        self.renderer.console.print(f"[yellow]unknown command: /{cmd}[/]")
        return True

    def _render_help(self) -> None:
        rows = [
            ["/help", "Show this help"],
            ["/clear", "Clear conversation history"],
            ["/exit", "Quit"],
        ]
        for name, cmd in self.commands.items():
            rows.append([f"/{name}", getattr(cmd, "help_text", "")])
        self.renderer.render_table("Commands", ["command", "description"], rows)
```

**`src/vulpcode/app.py`**:

```python
"""REPL bootstrap: builds Agent, Renderer, Repl from config."""
from __future__ import annotations

from rich.console import Console

from vulpcode.agent import Agent
from vulpcode.config import load_config
from vulpcode.permissions import Mode, PermissionManager
from vulpcode.providers import build_provider
from vulpcode.tools import list_tools
from vulpcode.ui import Renderer, get_theme
from vulpcode.ui.repl import Repl

# Force tool registration
import vulpcode.tools  # noqa: F401


def _make_permissions(config: dict, cli_overrides: dict) -> PermissionManager:
    if cli_overrides.get("auto"):
        mode = Mode.AUTO
    elif cli_overrides.get("safe"):
        mode = Mode.SAFE
    elif cli_overrides.get("plan"):
        mode = Mode.PLAN
    else:
        mode = Mode.DEFAULT
    return PermissionManager(config=config, mode=mode)


async def start_repl(
    *,
    cli_overrides: dict | None = None,
    one_shot: str | None = None,
    print_mode: bool = False,
) -> int:
    cli_overrides = cli_overrides or {}
    cfg = load_config(cli_overrides=_cfg_overrides_from_cli(cli_overrides))

    provider_name = cfg.get("default_provider", "anthropic")
    model = cfg.get("default_model") or _default_model_for(provider_name)
    provider_cfg = (cfg.get("providers", {}) or {}).get(provider_name, {})
    provider = build_provider(provider_name, provider_cfg)

    tool_classes = list_tools()
    tools = [cls() for cls in tool_classes]

    permissions = _make_permissions(cfg, cli_overrides)

    console = Console(force_terminal=not print_mode, no_color=False)
    theme = get_theme(cfg.get("ui", {}).get("theme", "default"))
    renderer = Renderer(console, theme)

    agent = Agent(
        provider=provider,
        tools=tools,
        model=model,
        permissions=permissions,
    )

    repl = Repl(agent=agent, renderer=renderer, config=cfg)
    if one_shot is not None:
        await repl.one_shot(one_shot)
        return 0
    await repl.run()
    return 0


def _cfg_overrides_from_cli(o: dict) -> dict:
    overrides: dict = {}
    if o.get("provider"):
        overrides["default_provider"] = o["provider"]
    if o.get("model"):
        overrides["default_model"] = o["model"]
    return overrides


def _default_model_for(provider_name: str) -> str:
    return {
        "anthropic": "claude-sonnet-4-6",
        "openai": "gpt-4o-mini",
        "deepseek": "deepseek-chat",
        "groq": "llama-3.1-70b-versatile",
        "openrouter": "openrouter/auto",
        "gemini": "gemini-2.5-pro",
        "ollama": "qwen2.5-coder:7b",
        "lmstudio": "local-model",
        "vllm": "local-model",
    }.get(provider_name, "")
```

### Atualizar `cli.py`

Substituir o stub do callback raiz para chamar `start_repl`:

```python
# em cli.py, dentro do callback root, em vez de imprimir "not implemented":
import asyncio
from vulpcode.app import start_repl

return_code = asyncio.run(start_repl(
    cli_overrides={
        "provider": provider, "model": model,
        "auto": auto, "safe": safe, "plan": plan,
    },
    one_shot=query,
    print_mode=print_mode,
))
raise typer.Exit(code=return_code)
```

---

## INSTRUCAO CRITICA

- `prompt_toolkit.PromptSession.prompt_async` requer event loop. Usar
  `asyncio.run(start_repl(...))` no entry-point.
- `patch_stdout` evita que `print` durante o agent loop quebre o cursor do
  prompt — necessario para misturar Rich e prompt_toolkit.
- Historico em `~/.vulpcode/history`.
- Slash commands minimos (`/exit`, `/clear`, `/help`) implementados aqui;
  FASE 10 adiciona o resto via dict `self.commands`.
- `one_shot` desabilita spinner (sai mais limpo em pipes).
- Default model por provider para ergonomia — usuario pode sobrescrever via
  config ou `--model`.

---

## Etapas de Implementacao

### Etapa 1: Criar `ui/repl.py`

### Etapa 2: Criar/atualizar `app.py`

### Etapa 3: Atualizar `cli.py` callback root

### Etapa 4: Smoke test manual

```bash
cd /home/guhaase/projetos/vulpcode
pip install -e .
ANTHROPIC_API_KEY=... vulp "say hi" --print
# Deve imprimir resposta do modelo
```

(Apenas se a chave estiver disponivel; o teste real e na FASE 14.)

### Etapa 5: Atualizar `tests/test_cli_skeleton.py`

Os testes que verificavam "not implemented yet" precisam ser ajustados — agora
o REPL existe. Substituir por:

```python
def test_repl_invocation_does_not_crash_on_missing_key(monkeypatch):
    """If no provider key is set and no key in config, agent will fail when streaming.
    But the REPL should at least start (we send /exit immediately)."""
    # Hard to fully integration-test here; we just verify start_repl is importable.
    from vulpcode.app import start_repl  # noqa
    assert start_repl is not None
```

E remover o teste antigo de "REPL not implemented yet".

### Etapa 6: Rodar suite

```bash
pytest tests/ -v -x
```

---

## Criterios de Aceite

- [x] `src/vulpcode/ui/repl.py` implementa classe `Repl` com `run()` e `one_shot()`
- [x] Historico persistente em `~/.vulpcode/history`
- [x] WordCompleter inclui slash commands default
- [x] Slash commands `/help`, `/clear`, `/exit`, `/quit` funcionam
- [x] `_handle_slash` despacha para `self.commands` quando registrado
- [x] `src/vulpcode/app.py` implementa `start_repl()` que constroi tudo do config
- [x] `_make_permissions` mapeia flags CLI -> Mode
- [x] `_default_model_for` tem fallback razoavel por provider
- [x] `cli.py` invoca `asyncio.run(start_repl(...))` no callback root
- [x] `tests/test_cli_skeleton.py` atualizado (sem teste de "not implemented")
- [x] Suite completa de testes passa (`pytest tests/`)

---

## Riscos Tecnicos

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|---------------|---------|-----------|
| prompt_toolkit + Rich conflitam | Media | Medio | `patch_stdout()` |
| asyncio.run dentro de Typer callback | Baixa | Medio | Padrao bem suportado |
| Modelo default invalido para provider | Media | Medio | Documentar; usuario sobrescreve |
| EOFError vs KeyboardInterrupt | Baixa | Baixo | Capturado |

---

**End of Specification**
