"""Skill loader: discovers, parses, and serves skills from ~/.vulpcode/skills/."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SkillLoadError(Exception):
    """Raised when a skill directory cannot be loaded."""


def _parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Split SKILL.md into (frontmatter_dict, body). Tries YAML, falls back to regex."""
    if not content.startswith("---"):
        return {}, content

    end = content.find("\n---", 3)
    if end == -1:
        return {}, content

    raw = content[3:end].strip()
    body = content[end + 4:].lstrip("\n")

    try:
        import yaml  # optional: PyYAML in docs-tools extra

        data = yaml.safe_load(raw)
        if isinstance(data, dict):
            return data, body
    except Exception:
        pass

    # Fallback: simple line-by-line regex for name: and description: only
    data: dict[str, Any] = {}
    for line in raw.splitlines():
        m = re.match(r"^([\w]+)\s*:\s*(.+)$", line.strip())
        if m and m.group(1) in ("name", "description"):
            data[m.group(1)] = m.group(2).strip().strip("\"'")
    return data, body


@dataclass
class Skill:
    name: str
    description: str
    body: str
    tools_allow: list[str] | None
    path: Path

    @classmethod
    def from_dir(cls, skill_dir: Path) -> "Skill":
        """Load SKILL.md from skill_dir, parse frontmatter, return Skill instance.

        Raises SkillLoadError if SKILL.md is missing, name or description absent,
        or frontmatter cannot be parsed at all.
        """
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            raise SkillLoadError(f"SKILL.md not found in {skill_dir}")

        content = skill_file.read_text(encoding="utf-8")
        frontmatter, body = _parse_frontmatter(content)

        name = frontmatter.get("name")
        description = frontmatter.get("description")

        if not name:
            raise SkillLoadError(f"Skill at {skill_dir}: missing required field 'name'")
        if not description:
            raise SkillLoadError(
                f"Skill at {skill_dir}: missing required field 'description'"
            )

        tools_allow: list[str] | None = frontmatter.get("tools_allow")
        if tools_allow is not None and not isinstance(tools_allow, list):
            tools_allow = None

        return cls(
            name=str(name),
            description=str(description),
            body=body.strip(),
            tools_allow=tools_allow,
            path=skill_dir,
        )


@dataclass
class SkillsConfig:
    enabled: bool = True
    search_dirs: list[Path] = field(
        default_factory=lambda: [
            Path.home() / ".vulpcode" / "skills",
            Path(".vulpcode") / "skills",
        ]
    )


class SkillRegistry:
    """Discovers skills in configured directories and exposes them as a hook.

    On construction, scans every path in ``config.search_dirs`` for subdirectories
    containing a ``SKILL.md`` file. Missing directories are silently skipped.
    Duplicate skill names (same ``name`` field): first occurrence wins, warning logged.
    """

    name: str = "skills_inject"
    reads: tuple[str, ...] = ("messages", "metadata")
    writes: tuple[str, ...] = ("messages", "metadata")

    def __init__(self, config: SkillsConfig) -> None:
        self._config = config
        self._skills: dict[str, Skill] = {}
        self._load(config.search_dirs)

    def reload(self) -> None:
        """Re-scan the configured search_dirs, replacing the current skill set."""
        self._skills.clear()
        self._load(self._config.search_dirs)

    def _load(self, search_dirs: list[Path]) -> None:
        for search_dir in search_dirs:
            if not search_dir.exists():
                continue
            try:
                subdirs = sorted(p for p in search_dir.iterdir() if p.is_dir())
            except OSError as exc:
                logger.warning("Cannot scan skill directory %s: %s", search_dir, exc)
                continue
            for subdir in subdirs:
                try:
                    skill = Skill.from_dir(subdir)
                except SkillLoadError as exc:
                    logger.warning("Skipping skill in %s: %s", subdir, exc)
                    continue
                if skill.name in self._skills:
                    logger.warning(
                        "Duplicate skill %r in %s — first occurrence (%s) wins",
                        skill.name,
                        subdir,
                        self._skills[skill.name].path,
                    )
                    continue
                self._skills[skill.name] = skill
                logger.debug("Loaded skill %r from %s", skill.name, subdir)

    def all(self) -> list[Skill]:
        """Return all loaded skills in discovery order."""
        return list(self._skills.values())

    def get(self, name: str) -> Skill | None:
        """Return the Skill with the given name, or None if not found."""
        return self._skills.get(name)

    def descriptor_block(self) -> str:
        """Render the descriptor block for injection into the system prompt.

        Contains only skill names and descriptions — never the full body.
        """
        lines = [
            "## Skills disponíveis",
            "",
            "Skills são playbooks especializados que você pode carregar sob demanda"
            ' chamando LoadSkill(name="..."). Não carregue uma skill sem necessidade'
            " explícita.",
            "",
        ]
        for skill in self._skills.values():
            lines.append(f"- **{skill.name}** — {skill.description}")
        return "\n".join(lines)

    def inject_into_system_prompt(self, state: Any, **_kwargs: Any) -> None:
        """Inject the skill descriptor block into state.messages (idempotent).

        Uses state.metadata['skills_injected'] to prevent re-injection across
        iterations. No-op when the registry is empty.
        """
        if state.metadata.get("skills_injected"):
            return
        skills = self.all()
        if not skills:
            return
        from vulpcode.providers.base import Message

        block = self.descriptor_block()
        state.messages.insert(0, Message(role="system", content=block))
        state.metadata["skills_injected"] = True

    def __call__(self, state: Any, **kwargs: Any) -> None:
        """Hook entrypoint for before_send."""
        self.inject_into_system_prompt(state, **kwargs)


def enforce_skill_tool_filter(state: Any, *, call: Any, **kwargs: Any) -> Any:
    """Block tool calls not in the active skill's allow-list.

    No-op when no skill is active (state.metadata has no 'active_skill_tools_allow').
    """
    allow = state.metadata.get("active_skill_tools_allow")
    if not allow:
        return None
    if call.name not in allow:
        from vulpcode.tools.base import ToolResult

        return ToolResult(
            error=f"Tool {call.name!r} blocked by active skill (allow: {allow}).",
            is_error=True,
        )
    return None


enforce_skill_tool_filter.name = "skill_tool_filter"  # type: ignore[attr-defined]
enforce_skill_tool_filter.reads = ("metadata",)  # type: ignore[attr-defined]
enforce_skill_tool_filter.writes = ()  # type: ignore[attr-defined]
