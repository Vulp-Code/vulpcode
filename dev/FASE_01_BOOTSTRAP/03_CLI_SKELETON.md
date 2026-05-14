# Tarefa 01.03 - CLI Skeleton com Typer

**Status**: PENDENTE
**Fase**: 01 - Bootstrap
**Dependencias**: 01.01 (estrutura), 01.02 (pyproject)
**Bloqueia**: FASE 09 (REPL), FASE 10 (slash commands)

---

## Objetivo

Substituir o stub de `cli.py` por um esqueleto Typer real com flags principais
(`--provider`, `--model`, `--print`, `--resume`, `--auto`, `--safe`, `--plan`)
e subcomandos (`config`, `providers`, `models`). O fluxo de chat ainda nao e
implementado — apenas o esqueleto da CLI esta presente.

---

## Descricao Tecnica

**Arquivo a editar**: `/home/guhaase/projetos/vulpcode/src/vulpcode/cli.py`

**Funcionalidades nesta fase**:
- `vulp --help` mostra ajuda formatada por Typer/Rich
- `vulp --version` imprime a versao e sai
- `vulp config` abre `$EDITOR ~/.vulpcode/config.toml` (cria diretorio se nao existir)
- `vulp providers` lista provedores conhecidos (lista hardcoded por enquanto)
- `vulp models` exibe mensagem "no provider configured yet" (sera real em FASE 03)
- `vulp [QUERY]` aceita prompt one-shot mas apenas imprime "REPL not implemented yet" (FASE 09)
- Exit code 0 em comandos que rodaram, 1 em erro

**Estrutura recomendada**:

```python
"""Typer CLI entry point."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from vulpcode import __version__

app = typer.Typer(
    name="vulp",
    help="Vulpcode - terminal coding agent, multi-provider.",
    no_args_is_help=False,
    add_completion=False,
    rich_markup_mode="rich",
)
console = Console()
err_console = Console(stderr=True)


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"vulpcode {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def root(
    ctx: typer.Context,
    query: Optional[str] = typer.Argument(None, help="One-shot prompt for the agent"),
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="Provider name"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model id"),
    print_mode: bool = typer.Option(False, "--print", help="Headless stdout-only mode"),
    resume: bool = typer.Option(False, "--resume", "-r", help="Resume last session"),
    auto: bool = typer.Option(False, "--auto", help="Auto-approve all tool calls"),
    safe: bool = typer.Option(False, "--safe", help="Confirm even reads"),
    plan: bool = typer.Option(False, "--plan", help="Plan-only mode (no execution)"),
    version: bool = typer.Option(
        False, "--version", "-V",
        callback=_version_callback, is_eager=True, help="Show version and exit",
    ),
) -> None:
    """Vulpcode entry point. Without subcommand, opens REPL or runs one-shot query."""
    if ctx.invoked_subcommand is not None:
        return
    # Store options on context for child subcommands or future REPL
    ctx.obj = {
        "provider": provider, "model": model, "print_mode": print_mode,
        "resume": resume, "auto": auto, "safe": safe, "plan": plan,
        "query": query,
    }
    # Phase 01: REPL not implemented yet
    if query or print_mode or resume:
        err_console.print("[yellow]REPL/one-shot mode not implemented yet (FASE 09).[/]")
        raise typer.Exit(code=1)
    err_console.print("[yellow]Interactive REPL not implemented yet (FASE 09).[/]")
    raise typer.Exit(code=1)


@app.command()
def config() -> None:
    """Open ~/.vulpcode/config.toml in $EDITOR."""
    config_dir = Path.home() / ".vulpcode"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.toml"
    if not config_path.exists():
        config_path.write_text("# Vulpcode config\n", encoding="utf-8")
    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL") or "vi"
    os.execvp(editor, [editor, str(config_path)])


@app.command()
def providers() -> None:
    """List known providers."""
    table = Table(title="Vulpcode providers")
    table.add_column("name", style="cyan")
    table.add_column("backend")
    table.add_column("status")
    known = [
        ("anthropic", "Anthropic API", "supported"),
        ("openai", "OpenAI API", "supported"),
        ("deepseek", "DeepSeek (OpenAI-compatible)", "supported"),
        ("groq", "Groq (OpenAI-compatible)", "supported"),
        ("openrouter", "OpenRouter (OpenAI-compatible)", "supported"),
        ("gemini", "Google Gemini", "supported"),
        ("ollama", "Ollama (localhost)", "supported"),
    ]
    for name, backend, status in known:
        table.add_row(name, backend, status)
    console.print(table)


@app.command()
def models() -> None:
    """List available models for the current provider."""
    err_console.print(
        "[yellow]Model listing requires provider integration (FASE 03).[/]"
    )
    raise typer.Exit(code=1)


def main() -> None:
    """Entry point for ``vulp`` and ``vulpcode`` console scripts."""
    app()


if __name__ == "__main__":
    main()
```

---

## INSTRUCAO CRITICA

- Nao importar nada de `providers/`, `tools/`, `agent.py` — esses ainda sao placeholders.
  Importar apenas `__version__` do `vulpcode/__init__.py`.
- O comando padrao (sem subcomando) deve sair com exit code 1 informando que o
  REPL ainda nao foi implementado. Nao tentar simular ou implementar parte dele.
- O subcomando `config` usa `os.execvp` para substituir o processo. Em testes
  evitar chamar este caminho diretamente — usar mock ou pular.
- `providers` exibe tabela hardcoded — sera substituida pelo registry real em FASE 03.
- Usar `rich_markup_mode="rich"` para formatacao bonita do --help.
- Garantir que `vulp --version` e `vulp -V` imprimam `vulpcode 0.1.0`.

---

## Etapas de Implementacao

### Etapa 1: Reescrever `cli.py`

Substituir o stub atual (que apenas levanta `NotImplementedError`) pelo conteudo
descrito acima.

### Etapa 2: Verificacao manual

```bash
cd /home/guhaase/projetos/vulpcode
vulp --help
# Deve listar comandos: config, providers, models, e flags

vulp --version
# Deve imprimir: vulpcode 0.1.0

vulp providers
# Deve mostrar tabela com 7 providers

vulp models
# Deve avisar "Model listing requires provider integration"

vulp
# Deve avisar "Interactive REPL not implemented yet"
```

### Etapa 3: Teste minimo

Criar `tests/test_cli_skeleton.py`:

```python
"""Smoke tests for the FASE 01 CLI skeleton."""
from typer.testing import CliRunner

from vulpcode.cli import app

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "vulpcode" in result.stdout
    assert "0.1.0" in result.stdout


def test_help_lists_subcommands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for sub in ("config", "providers", "models"):
        assert sub in result.stdout


def test_providers_table() -> None:
    result = runner.invoke(app, ["providers"])
    assert result.exit_code == 0
    assert "anthropic" in result.stdout
    assert "ollama" in result.stdout


def test_repl_not_implemented_yet() -> None:
    result = runner.invoke(app, [])
    assert result.exit_code == 1
    assert "not implemented" in result.stdout.lower() or "not implemented" in (result.stderr or "").lower()


def test_models_not_implemented_yet() -> None:
    result = runner.invoke(app, ["models"])
    assert result.exit_code == 1
```

### Etapa 4: Rodar tests

```bash
pytest tests/test_cli_skeleton.py -v
```

Deve passar todos os 5 testes.

---

## Criterios de Aceite

- [x] `vulp --help` exibe ajuda com subcomandos config/providers/models
- [x] `vulp --version` imprime `vulpcode 0.1.0`
- [x] `vulp providers` exibe tabela com pelo menos 7 entradas
- [x] `vulp` (sem args) sai com exit code 1 e mensagem "REPL not implemented yet"
- [x] `vulp models` sai com exit code 1 e aviso de FASE 03
- [x] `cli.py` nao importa de modulos ainda nao implementados (apenas `__version__`)
- [x] `tests/test_cli_skeleton.py` criado e passa todos os testes (`pytest tests/test_cli_skeleton.py -v`)

---

## Riscos Tecnicos

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|---------------|---------|-----------|
| Typer mudou API recente | Baixa | Medio | Pinar `typer>=0.12` no pyproject |
| `os.execvp` impede teste do `config` | Alta | Baixo | Nao testar este comando diretamente |
| CliRunner nao captura stderr | Baixa | Baixo | Verificar `result.stdout` ou `mix_stderr=False` |

---

**End of Specification**
