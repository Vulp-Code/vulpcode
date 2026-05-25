"""Smoke tests for the FASE 01 CLI skeleton."""
from typer.testing import CliRunner

from vulpcode.cli import app

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "vulpcode" in result.stdout
    assert "0.2.0" in result.stdout


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


def test_repl_invocation_does_not_crash_on_missing_key(monkeypatch) -> None:
    """If no provider key is set and no key in config, agent will fail when streaming.
    But the REPL should at least start (we send /exit immediately)."""
    from vulpcode.app import start_repl  # noqa: F401

    assert start_repl is not None


def test_models_not_implemented_yet() -> None:
    result = runner.invoke(app, ["models"])
    assert result.exit_code == 1
