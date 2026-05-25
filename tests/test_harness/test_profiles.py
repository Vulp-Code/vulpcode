"""Tests for the Profile system (harness/profiles.py)."""
from __future__ import annotations

import copy
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from vulpcode.harness.profiles import (
    Profile,
    ProfileNotFound,
    apply_profile,
    list_profiles,
)


# ---------------------------------------------------------------------------
# Profile loading
# ---------------------------------------------------------------------------


def test_load_from_toml_file(tmp_path: Path) -> None:
    """Profile.load finds NAME.toml in search_dirs and parses it correctly."""
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "myprofile.toml").write_text(
        'description = "My test profile"\ntools_allow = ["Read", "Grep"]\n',
        encoding="utf-8",
    )
    p = Profile.load("myprofile", search_dirs=[profiles_dir])
    assert p.name == "myprofile"
    assert p.description == "My test profile"
    assert p.data["tools_allow"] == ["Read", "Grep"]


def test_load_from_config_section() -> None:
    """Profile.load falls back to config_sections when no file is found."""
    config_sections = {
        "foo": {"description": "Foo profile", "provider": "openai", "model": "gpt-4o"}
    }
    p = Profile.load("foo", search_dirs=[], config_sections=config_sections)
    assert p.name == "foo"
    assert p.description == "Foo profile"
    assert p.data["provider"] == "openai"
    assert p.data["model"] == "gpt-4o"


def test_load_missing_raises(tmp_path: Path) -> None:
    """Profile.load raises ProfileNotFound for unknown profile names."""
    with pytest.raises(ProfileNotFound) as exc_info:
        Profile.load("nonexistent-xyz-999", search_dirs=[tmp_path])
    assert "nonexistent-xyz-999" in str(exc_info.value)


def test_load_missing_includes_available_names() -> None:
    """ProfileNotFound lists available profiles when raised."""
    with pytest.raises(ProfileNotFound) as exc_info:
        Profile.load("no-such-profile", search_dirs=[])
    # Built-ins should appear in the error message
    err = str(exc_info.value)
    assert "research" in err or "code" in err or "safe" in err


def test_load_file_takes_priority_over_config_section(tmp_path: Path) -> None:
    """A .toml file in search_dirs wins over a same-named config_section."""
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "conflict.toml").write_text(
        'description = "From file"\n', encoding="utf-8"
    )
    config_sections = {"conflict": {"description": "From config section"}}
    p = Profile.load("conflict", search_dirs=[profiles_dir], config_sections=config_sections)
    assert p.description == "From file"


# ---------------------------------------------------------------------------
# list_profiles
# ---------------------------------------------------------------------------


def test_list_profiles_includes_builtin() -> None:
    """list_profiles always includes the three built-in profiles."""
    profiles = list_profiles(search_dirs=[])
    names = {p.name for p in profiles}
    assert "research" in names
    assert "code" in names
    assert "safe" in names


def test_list_profiles_user_overrides_builtin(tmp_path: Path) -> None:
    """A user profile with the same name shadows the built-in."""
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "research.toml").write_text(
        'description = "Custom research"\n', encoding="utf-8"
    )
    profiles = list_profiles(search_dirs=[profiles_dir])
    research = next(p for p in profiles if p.name == "research")
    assert research.description == "Custom research"


# ---------------------------------------------------------------------------
# apply_profile
# ---------------------------------------------------------------------------


def test_apply_overrides_provider() -> None:
    """Profile provider field maps to default_provider in the merged config."""
    global_config = {"default_provider": "anthropic", "default_model": "claude-sonnet-4-6"}
    profile = Profile(name="test", description="test", data={"provider": "openai"})
    result = apply_profile(global_config, profile)
    assert result["default_provider"] == "openai"


def test_apply_overrides_model() -> None:
    """Profile model field maps to default_model in the merged config."""
    global_config = {"default_provider": "anthropic", "default_model": "sonnet"}
    profile = Profile(name="test", description="test", data={"model": "opus"})
    result = apply_profile(global_config, profile)
    assert result["default_model"] == "opus"


def test_apply_is_pure() -> None:
    """apply_profile does not mutate global_config."""
    global_config = {"default_provider": "anthropic", "tools_allow": ["A", "B"]}
    original = copy.deepcopy(global_config)
    profile = Profile(
        name="test", description="test", data={"provider": "openai", "tools_allow": ["C"]}
    )
    apply_profile(global_config, profile)
    assert global_config == original


def test_apply_tools_allow_replaces_not_union() -> None:
    """tools_allow in profile replaces the global list entirely."""
    global_config = {"tools_allow": ["A", "B"]}
    profile = Profile(name="test", description="test", data={"tools_allow": ["C"]})
    result = apply_profile(global_config, profile)
    assert result["tools_allow"] == ["C"]
    assert global_config["tools_allow"] == ["A", "B"]


def test_apply_middleware_section_replaces() -> None:
    """Each middleware subsection is replaced, not merged field-by-field."""
    global_config: dict = {
        "middleware": {
            "summarization": {
                "enabled": True,
                "trigger_at_tokens": 60000,
                "extra_key": "preserved_in_global",
            },
            "eviction": {"enabled": True},
        }
    }
    profile = Profile(
        name="test",
        description="test",
        data={"middleware": {"summarization": {"enabled": True, "trigger_at_tokens": 80000}}},
    )
    result = apply_profile(global_config, profile)
    summ = result["middleware"]["summarization"]
    assert summ["trigger_at_tokens"] == 80000
    assert "extra_key" not in summ, "middleware section must be replaced, not merged"
    # Other middleware subsections remain untouched
    assert result["middleware"]["eviction"]["enabled"] is True


def test_apply_description_not_propagated() -> None:
    """The description field is not copied into the merged config."""
    global_config: dict = {}
    profile = Profile(name="x", description="hello", data={"description": "hello"})
    result = apply_profile(global_config, profile)
    assert "description" not in result


# ---------------------------------------------------------------------------
# Built-in profiles
# ---------------------------------------------------------------------------


def test_builtin_profiles_loadable() -> None:
    """All three built-in profiles parse without error and have a description."""
    for name in ("research", "code", "safe"):
        p = Profile.load(name, search_dirs=[])
        assert p.description, f"Built-in profile {name!r} has empty description"
        assert p.name == name


def test_builtin_research_has_tools_allow() -> None:
    """research.toml specifies a tools_allow list."""
    p = Profile.load("research", search_dirs=[])
    assert isinstance(p.data.get("tools_allow"), list)
    assert len(p.data["tools_allow"]) > 0


def test_builtin_safe_excludes_bash() -> None:
    """safe.toml tools_allow does not include Bash."""
    p = Profile.load("safe", search_dirs=[])
    tools_allow = p.data.get("tools_allow") or []
    assert "Bash" not in tools_allow


# ---------------------------------------------------------------------------
# CLI-level test: applying safe profile excludes Bash from tool set
# ---------------------------------------------------------------------------


def test_cli_profile_flag_applied() -> None:
    """Applying the 'safe' profile removes Bash from the resolved tools_allow."""
    from vulpcode.config import DEFAULTS

    global_config = copy.deepcopy(DEFAULTS)
    profile = Profile.load("safe", search_dirs=[])
    result = apply_profile(global_config, profile)

    tools_allow = result.get("tools_allow")
    assert tools_allow is not None, "safe profile must set tools_allow"
    assert "Bash" not in tools_allow


def test_cli_profile_flag_applied_system_prompt() -> None:
    """Applying a profile with system_prompt_extra sets that key in the config."""
    global_config: dict = {}
    profile = Profile(
        name="x",
        description="x",
        data={"system_prompt_extra": "Extra instructions."},
    )
    result = apply_profile(global_config, profile)
    assert result.get("system_prompt_extra") == "Extra instructions."


# ---------------------------------------------------------------------------
# Slash command test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cmd_profile_list() -> None:
    """/profile list output contains all three built-in profiles."""
    from vulpcode.commands.profile_cmd import ProfileCommand

    rows_captured: list[list[str]] = []
    mock_console = MagicMock()

    mock_renderer = MagicMock()
    mock_renderer.console = mock_console

    def _capture_table(title: str, cols: list[str], rows: list[list[str]]) -> None:
        rows_captured.extend(rows)

    mock_renderer.render_table = _capture_table

    mock_repl = MagicMock()
    mock_repl.renderer = mock_renderer
    mock_repl.config = {}

    cmd = ProfileCommand()
    await cmd.run(mock_repl, "list")

    all_names = {row[0] for row in rows_captured}
    assert "research" in all_names
    assert "code" in all_names
    assert "safe" in all_names


@pytest.mark.asyncio
async def test_cmd_profile_no_args_shows_none_active() -> None:
    """/profile with no args and no active profile reports no active profile."""
    from vulpcode.commands.profile_cmd import ProfileCommand

    printed: list[str] = []
    mock_console = MagicMock()
    mock_console.print = lambda msg, **kw: printed.append(str(msg))

    mock_renderer = MagicMock()
    mock_renderer.console = mock_console

    mock_repl = MagicMock()
    mock_repl.renderer = mock_renderer
    mock_repl.config = {}

    cmd = ProfileCommand()
    await cmd.run(mock_repl, "")

    assert any("No profile active" in line or "no profile" in line.lower() for line in printed)


@pytest.mark.asyncio
async def test_cmd_profile_switch_warns_next_session() -> None:
    """/profile switch NAME warns that changes apply next session."""
    from vulpcode.commands.profile_cmd import ProfileCommand

    printed: list[str] = []
    mock_console = MagicMock()
    mock_console.print = lambda msg, **kw: printed.append(str(msg))

    mock_renderer = MagicMock()
    mock_renderer.console = mock_console

    mock_repl = MagicMock()
    mock_repl.renderer = mock_renderer
    mock_repl.config = {}

    cmd = ProfileCommand()
    await cmd.run(mock_repl, "switch safe")

    combined = " ".join(printed).lower()
    assert "restart" in combined or "next session" in combined or "next" in combined
