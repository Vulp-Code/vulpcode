"""Tests for the /skills slash command (FASE_05.02)."""
from __future__ import annotations

import io
from pathlib import Path

import pytest
from rich.console import Console

import vulpcode.session as _session
from vulpcode.commands.skills_cmd import SkillsCommand
from vulpcode.harness.skills import Skill, SkillRegistry, SkillsConfig
from vulpcode.ui import Renderer, get_theme


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeRepl:
    def __init__(self) -> None:
        buf = io.StringIO()
        console = Console(file=buf, width=80, force_terminal=False, color_system=None)
        self.renderer = Renderer(console, get_theme("default"))
        self.buf = buf
        self.config: dict = {}

    def output(self) -> str:
        return self.buf.getvalue()


def _make_skill(
    name: str,
    body: str = "skill body",
    tools_allow: list[str] | None = None,
    path: Path | None = None,
) -> Skill:
    return Skill(
        name=name,
        description=f"Description of {name}",
        body=body,
        tools_allow=tools_allow,
        path=path or Path("/tmp/skills") / name,
    )


def _make_registry(skills: list[Skill], search_dirs: list[Path] | None = None) -> SkillRegistry:
    cfg = SkillsConfig(enabled=True, search_dirs=search_dirs or [])
    registry = SkillRegistry(cfg)
    for s in skills:
        registry._skills[s.name] = s
    return registry


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cmd_skills_list():
    """/skills lists all skill names."""
    skills = [_make_skill(n) for n in ("alpha", "beta", "gamma")]
    registry = _make_registry(skills)
    _session.skill_registry = registry

    repl = FakeRepl()
    cmd = SkillsCommand()
    await cmd.run(repl, "")

    out = repl.output()
    assert "alpha" in out
    assert "beta" in out
    assert "gamma" in out

    _session.skill_registry = None


@pytest.mark.asyncio
async def test_cmd_skills_show():
    """/skills show NAME prints the skill body."""
    skill = _make_skill("foo", body="## Do the foo thing\n\nStep 1. Step 2.")
    registry = _make_registry([skill])
    _session.skill_registry = registry

    repl = FakeRepl()
    cmd = SkillsCommand()
    await cmd.run(repl, "show foo")

    out = repl.output()
    assert "Do the foo thing" in out

    _session.skill_registry = None


@pytest.mark.asyncio
async def test_cmd_skills_show_missing():
    """/skills show NONEXISTENT prints a friendly error."""
    skill = _make_skill("bar")
    registry = _make_registry([skill])
    _session.skill_registry = registry

    repl = FakeRepl()
    cmd = SkillsCommand()
    await cmd.run(repl, "show nope")

    out = repl.output()
    assert "not found" in out.lower() or "nope" in out

    _session.skill_registry = None


@pytest.mark.asyncio
async def test_cmd_skills_reload(tmp_path: Path):
    """/skills reload re-scans skill directories."""
    skill_dir = tmp_path / "mypkg"
    skill_dir.mkdir()
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(
        "---\nname: mypkg\ndescription: My package skill\n---\n\nBody.",
        encoding="utf-8",
    )

    cfg = SkillsConfig(enabled=True, search_dirs=[tmp_path])
    registry = SkillRegistry(cfg)
    assert len(registry.all()) == 1
    _session.skill_registry = registry

    # Add another skill on disk AFTER registry creation
    new_dir = tmp_path / "newskill"
    new_dir.mkdir()
    (new_dir / "SKILL.md").write_text(
        "---\nname: newskill\ndescription: A brand new skill\n---\n\nNew body.",
        encoding="utf-8",
    )

    repl = FakeRepl()
    cmd = SkillsCommand()
    await cmd.run(repl, "reload")

    out = repl.output()
    assert "reloaded" in out.lower()
    assert len(registry.all()) == 2
    assert registry.get("newskill") is not None

    _session.skill_registry = None


@pytest.mark.asyncio
async def test_cmd_skills_list_empty():
    """/skills with no skills shows a friendly message."""
    _session.skill_registry = None

    repl = FakeRepl()
    cmd = SkillsCommand()
    await cmd.run(repl, "")

    out = repl.output()
    assert "no skills" in out.lower()
