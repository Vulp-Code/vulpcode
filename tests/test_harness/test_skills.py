"""Tests for the SkillRegistry middleware (FASE_05.01)."""
from __future__ import annotations

import logging
from pathlib import Path

import pytest

from vulpcode.harness.skills import Skill, SkillLoadError, SkillRegistry, SkillsConfig
from vulpcode.harness.state import LoopState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_SKILL_CONTENT = """\
---
name: test-skill
description: A skill for testing purposes
tools_allow: [Read, Edit]
---

# Test Skill

Body content here.
"""

_MINIMAL_SKILL_CONTENT = """\
---
name: minimal-skill
description: Minimal skill with no tools_allow
---

Body.
"""


def _write_skill(directory: Path, content: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "SKILL.md").write_text(content, encoding="utf-8")
    return directory


def _make_registry(search_dirs: list[Path]) -> SkillRegistry:
    cfg = SkillsConfig(enabled=True, search_dirs=search_dirs)
    return SkillRegistry(cfg)


# ---------------------------------------------------------------------------
# Skill.from_dir tests
# ---------------------------------------------------------------------------


def test_skill_from_dir_valid(tmp_path: Path) -> None:
    """Valid SKILL.md with all fields loads correctly."""
    skill_dir = tmp_path / "test-skill"
    _write_skill(skill_dir, _VALID_SKILL_CONTENT)

    skill = Skill.from_dir(skill_dir)

    assert skill.name == "test-skill"
    assert skill.description == "A skill for testing purposes"
    assert skill.tools_allow == ["Read", "Edit"]
    assert "Body content here" in skill.body
    assert skill.path == skill_dir


def test_skill_from_dir_missing_name_raises(tmp_path: Path) -> None:
    """Frontmatter without 'name' raises SkillLoadError."""
    skill_dir = tmp_path / "no-name"
    content = "---\ndescription: No name here\n---\n\nBody."
    _write_skill(skill_dir, content)

    with pytest.raises(SkillLoadError, match="name"):
        Skill.from_dir(skill_dir)


def test_skill_from_dir_missing_description_raises(tmp_path: Path) -> None:
    """Frontmatter without 'description' raises SkillLoadError."""
    skill_dir = tmp_path / "no-desc"
    content = "---\nname: no-desc-skill\n---\n\nBody."
    _write_skill(skill_dir, content)

    with pytest.raises(SkillLoadError, match="description"):
        Skill.from_dir(skill_dir)


def test_skill_from_dir_no_skill_md_raises(tmp_path: Path) -> None:
    """Directory without SKILL.md raises SkillLoadError."""
    skill_dir = tmp_path / "empty-dir"
    skill_dir.mkdir()

    with pytest.raises(SkillLoadError, match="SKILL.md not found"):
        Skill.from_dir(skill_dir)


def test_skill_from_dir_invalid_yaml_falls_back(tmp_path: Path) -> None:
    """Broken YAML with simple name/description lines falls back to regex parsing."""
    skill_dir = tmp_path / "broken-yaml"
    content = (
        "---\n"
        "name: fallback-skill\n"
        "description: Loaded via regex fallback\n"
        "tools_allow: [unclosed bracket\n"  # invalid YAML
        "---\n\n"
        "Body content.\n"
    )
    _write_skill(skill_dir, content)

    skill = Skill.from_dir(skill_dir)

    assert skill.name == "fallback-skill"
    assert skill.description == "Loaded via regex fallback"
    assert skill.tools_allow is None  # cannot parse invalid tools_allow without YAML


def test_skill_from_dir_tools_allow_none_when_absent(tmp_path: Path) -> None:
    """Skill without tools_allow field has tools_allow=None."""
    skill_dir = tmp_path / "minimal"
    _write_skill(skill_dir, _MINIMAL_SKILL_CONTENT)

    skill = Skill.from_dir(skill_dir)

    assert skill.tools_allow is None


# ---------------------------------------------------------------------------
# SkillRegistry tests
# ---------------------------------------------------------------------------


def test_registry_discovers_skills(tmp_path: Path) -> None:
    """Registry scans multiple search dirs and discovers all skills."""
    dirs = [tmp_path / f"skills{i}" for i in range(3)]
    for i, base in enumerate(dirs):
        skill_dir = base / f"skill-{i}"
        _write_skill(
            skill_dir,
            f"---\nname: skill-{i}\ndescription: Skill number {i}\n---\n\nBody.",
        )

    registry = _make_registry(dirs)
    skills = registry.all()

    assert len(skills) == 3
    names = {s.name for s in skills}
    assert names == {"skill-0", "skill-1", "skill-2"}


def test_registry_ignores_missing_search_dir(tmp_path: Path) -> None:
    """Missing search_dir does not raise; registry loads fine with others."""
    existing = tmp_path / "existing"
    _write_skill(existing / "my-skill", _MINIMAL_SKILL_CONTENT)
    missing = tmp_path / "does-not-exist"

    registry = _make_registry([missing, existing])

    assert len(registry.all()) == 1
    assert registry.get("minimal-skill") is not None


def test_registry_duplicate_warns(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Duplicate skill name: first wins, warning is logged."""
    dir1 = tmp_path / "dir1"
    dir2 = tmp_path / "dir2"
    _write_skill(dir1 / "dup", "---\nname: dup-skill\ndescription: First\n---\n\nA.")
    _write_skill(dir2 / "dup", "---\nname: dup-skill\ndescription: Second\n---\n\nB.")

    with caplog.at_level(logging.WARNING, logger="vulpcode.harness.skills"):
        registry = _make_registry([dir1, dir2])

    assert len(registry.all()) == 1
    assert registry.get("dup-skill").description == "First"  # type: ignore[union-attr]
    assert any("dup-skill" in r.message for r in caplog.records)


def test_registry_get_returns_none_for_unknown(tmp_path: Path) -> None:
    """get() returns None for an unknown skill name."""
    registry = _make_registry([])
    assert registry.get("nonexistent") is None


# ---------------------------------------------------------------------------
# descriptor_block tests
# ---------------------------------------------------------------------------


def test_descriptor_block_format(tmp_path: Path) -> None:
    """descriptor_block() has correct header, bullets, and no body content."""
    base = tmp_path / "skills"
    _write_skill(
        base / "my-skill",
        "---\nname: my-skill\ndescription: Does something useful\n---\n\nSECRET BODY",
    )

    registry = _make_registry([base])
    block = registry.descriptor_block()

    assert "## Skills disponíveis" in block
    assert "- **my-skill** — Does something useful" in block
    assert "SECRET BODY" not in block
    assert 'LoadSkill(name="...")' in block


# ---------------------------------------------------------------------------
# inject_into_system_prompt tests
# ---------------------------------------------------------------------------


def test_inject_idempotent(tmp_path: Path) -> None:
    """Calling inject_into_system_prompt twice adds only one message."""
    base = tmp_path / "skills"
    _write_skill(base / "s", _MINIMAL_SKILL_CONTENT)

    registry = _make_registry([base])
    state = LoopState()

    registry.inject_into_system_prompt(state)
    registry.inject_into_system_prompt(state)

    assert len(state.messages) == 1
    assert state.metadata.get("skills_injected") is True


def test_inject_when_no_skills_is_noop(tmp_path: Path) -> None:
    """inject_into_system_prompt is no-op when the registry has no skills."""
    empty = tmp_path / "empty"
    empty.mkdir()

    registry = _make_registry([empty])
    state = LoopState()

    registry.inject_into_system_prompt(state)

    assert len(state.messages) == 0
    assert not state.metadata.get("skills_injected")


def test_inject_message_contains_descriptor(tmp_path: Path) -> None:
    """Injected message contains the descriptor block text."""
    base = tmp_path / "skills"
    _write_skill(
        base / "check-skill",
        "---\nname: check-skill\ndescription: Verifies injection content\n---\n\nBody.",
    )

    registry = _make_registry([base])
    state = LoopState()
    registry.inject_into_system_prompt(state)

    assert len(state.messages) == 1
    injected = state.messages[0]
    assert "check-skill" in str(injected.content)
    assert "Verifies injection content" in str(injected.content)
    assert "Body." not in str(injected.content)


def test_registry_callable_as_hook(tmp_path: Path) -> None:
    """SkillRegistry is callable (hook protocol) and has name/reads/writes attributes."""
    registry = _make_registry([])

    assert hasattr(registry, "name")
    assert hasattr(registry, "reads")
    assert hasattr(registry, "writes")
    assert callable(registry)

    # Calling it directly (as hook) should not raise even with an empty state.
    state = LoopState()
    registry(state)
    assert len(state.messages) == 0
