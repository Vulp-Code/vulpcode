"""Typer CLI entry point."""
from __future__ import annotations

import asyncio
import os
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


_SUBCOMMANDS = {"config", "providers", "models"}


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
        False,
        "--version",
        "-V",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
) -> None:
    """Vulpcode entry point. Without subcommand, opens REPL or runs one-shot query."""
    if ctx.invoked_subcommand is not None:
        return
    # Click's group parser consumes the first positional into ``query``, so a
    # bare ``vulp providers`` would otherwise fall through to the REPL stub.
    # Dispatch to the matching subcommand by name when that happens.
    if query in _SUBCOMMANDS:
        for cmd in app.registered_commands:
            callback = cmd.callback
            if callback is None:
                continue
            cmd_name = cmd.name or callback.__name__
            if cmd_name == query:
                callback()
                return
    ctx.obj = {
        "provider": provider,
        "model": model,
        "print_mode": print_mode,
        "resume": resume,
        "auto": auto,
        "safe": safe,
        "plan": plan,
        "query": query,
    }
    from vulpcode.app import start_repl

    return_code = asyncio.run(
        start_repl(
            cli_overrides={
                "provider": provider,
                "model": model,
                "auto": auto,
                "safe": safe,
                "plan": plan,
            },
            one_shot=query,
            print_mode=print_mode,
            resume=resume,
        )
    )
    raise typer.Exit(code=return_code)


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
    from vulpcode.providers import OPENAI_COMPATIBLE_PRESETS, list_provider_names

    table = Table(title="Vulpcode providers")
    table.add_column("name", style="cyan")
    table.add_column("backend")
    for name in list_provider_names():
        if name in OPENAI_COMPATIBLE_PRESETS:
            preset = OPENAI_COMPATIBLE_PRESETS[name]
            backend = f"OpenAI-compatible ({preset or 'default'})"
        else:
            backend = name.capitalize()
        table.add_row(name, backend)
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
