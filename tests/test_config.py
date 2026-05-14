from pathlib import Path

from vulpcode.config import (
    config_paths,
    load_config,
    save_config,
)


def test_defaults_loaded(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg = load_config(cwd=tmp_path, env={})
    assert cfg["default_provider"] == "anthropic"
    assert cfg["permissions"]["auto_approve_read"] is True


def test_global_config_file(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".vulpcode").mkdir()
    (tmp_path / ".vulpcode" / "config.toml").write_text(
        'default_provider = "openai"\n[providers.openai]\napi_key = "abc"\n'
    )
    cfg = load_config(cwd=tmp_path, env={})
    assert cfg["default_provider"] == "openai"
    assert cfg["providers"]["openai"]["api_key"] == "abc"


def test_project_config_overrides_global(tmp_path: Path, monkeypatch):
    home = tmp_path / "h"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    (home / ".vulpcode").mkdir()
    (home / ".vulpcode" / "config.toml").write_text('default_provider = "openai"\n')

    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / ".vulpcode").mkdir()
    (proj / ".vulpcode" / "config.toml").write_text('default_provider = "ollama"\n')

    cfg = load_config(cwd=proj, env={})
    assert cfg["default_provider"] == "ollama"


def test_project_config_in_ancestor(tmp_path: Path, monkeypatch):
    home = tmp_path / "h"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    repo_root = tmp_path / "repo"
    nested = repo_root / "src" / "deep"
    nested.mkdir(parents=True)
    (repo_root / ".vulpcode").mkdir()
    (repo_root / ".vulpcode" / "config.toml").write_text('default_provider = "ollama"\n')

    cfg = load_config(cwd=nested, env={})
    assert cfg["default_provider"] == "ollama"


def test_env_var_overrides_file(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".vulpcode").mkdir()
    (tmp_path / ".vulpcode" / "config.toml").write_text('default_provider = "openai"\n')
    cfg = load_config(cwd=tmp_path, env={"VULPCODE_PROVIDER": "anthropic"})
    assert cfg["default_provider"] == "anthropic"


def test_anthropic_api_key_from_env(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg = load_config(cwd=tmp_path, env={"ANTHROPIC_API_KEY": "sk-x"})
    assert cfg["providers"]["anthropic"]["api_key"] == "sk-x"


def test_empty_env_var_is_ignored(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".vulpcode").mkdir()
    (tmp_path / ".vulpcode" / "config.toml").write_text('default_provider = "openai"\n')
    cfg = load_config(cwd=tmp_path, env={"VULPCODE_PROVIDER": ""})
    assert cfg["default_provider"] == "openai"


def test_cli_overrides_win(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg = load_config(
        cwd=tmp_path,
        env={"VULPCODE_PROVIDER": "openai"},
        cli_overrides={"default_provider": "ollama"},
    )
    assert cfg["default_provider"] == "ollama"


def test_lists_are_replaced_not_merged(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".vulpcode").mkdir()
    (tmp_path / ".vulpcode" / "config.toml").write_text(
        "[permissions]\nalways_allow_tools = [\"Read\", \"Glob\"]\n"
    )
    cfg = load_config(
        cwd=tmp_path,
        env={},
        cli_overrides={"permissions": {"always_allow_tools": ["Bash"]}},
    )
    assert cfg["permissions"]["always_allow_tools"] == ["Bash"]


def test_save_global(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    target = save_config({"default_provider": "openai"}, scope="global", cwd=tmp_path)
    assert target == tmp_path / ".vulpcode" / "config.toml"
    assert target.exists()
    assert "default_provider" in target.read_text()


def test_save_project(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    proj = tmp_path / "proj"
    proj.mkdir()
    target = save_config({"default_provider": "ollama"}, scope="project", cwd=proj)
    assert target == proj / ".vulpcode" / "config.toml"
    assert target.exists()
    assert "ollama" in target.read_text()


def test_save_then_load_roundtrip(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    save_config(
        {"default_provider": "openai", "providers": {"openai": {"api_key": "k"}}},
        scope="global",
        cwd=tmp_path,
    )
    cfg = load_config(cwd=tmp_path, env={})
    assert cfg["default_provider"] == "openai"
    assert cfg["providers"]["openai"]["api_key"] == "k"


def test_config_paths_includes_global(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    paths = config_paths(cwd=tmp_path)
    assert any(".vulpcode" in str(p) for p in paths)
    assert paths[0] == tmp_path / ".vulpcode" / "config.toml"


def test_defaults_not_mutated_across_calls(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    load_config(cwd=tmp_path, env={"ANTHROPIC_API_KEY": "sk-x"})
    cfg2 = load_config(cwd=tmp_path, env={})
    assert cfg2["providers"] == {}
