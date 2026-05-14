"""Extended CLI tests using Typer's CliRunner."""
from __future__ import annotations

from typer.testing import CliRunner

from vulpcode.cli import app


runner = CliRunner()


def test_cli_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.stdout


def test_cli_providers_after_registry():
    result = runner.invoke(app, ["providers"])
    assert result.exit_code == 0
    assert "anthropic" in result.stdout
    assert "ollama" in result.stdout


def test_cli_help_lists_subcommands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "config" in result.stdout
    assert "providers" in result.stdout


def test_cli_providers_via_bare_dispatch():
    """``vulp providers`` is also reachable through the root callback's
    fallback dispatch (when Typer parses the subcommand name as the bare query
    argument)."""
    result = runner.invoke(app, ["providers"])
    assert result.exit_code == 0
    assert "Vulpcode providers" in result.stdout


def test_cli_models_not_implemented():
    result = runner.invoke(app, ["models"])
    assert result.exit_code == 1
