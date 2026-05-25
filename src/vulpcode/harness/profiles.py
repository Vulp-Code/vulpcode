"""Profile system: named pre-packaged configurations for the agent."""
from __future__ import annotations

import copy
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


_BUILTIN_PROFILES_DIR = Path(__file__).parent / "_builtin_profiles"


class ProfileNotFound(Exception):
    """Raised when a named profile cannot be found in any search location."""

    def __init__(self, name: str, available: list[str] | None = None) -> None:
        self.profile_name = name
        self.available = available or []
        avail_str = f" Available: {self.available}" if self.available else ""
        super().__init__(f"Profile {name!r} not found.{avail_str}")


@dataclass
class Profile:
    name: str
    description: str
    data: dict  # raw parsed TOML

    @classmethod
    def load(
        cls,
        name: str,
        *,
        search_dirs: list[Path],
        config_sections: dict | None = None,
    ) -> "Profile":
        """Load a profile by name.

        Search order:
        1. Each dir in ``search_dirs`` for ``NAME.toml``
        2. ``config_sections`` dict (from ``[profiles.NAME]`` in config.toml)
        3. Built-in profiles bundled with the package

        Raises:
            ProfileNotFound: When the profile is not found in any location.
        """
        for d in search_dirs:
            candidate = d / f"{name}.toml"
            if candidate.exists():
                return cls._from_file(name, candidate)

        if config_sections and name in config_sections:
            data = dict(config_sections[name])
            return cls(name=name, description=data.get("description", ""), data=data)

        builtin = _BUILTIN_PROFILES_DIR / f"{name}.toml"
        if builtin.exists():
            return cls._from_file(name, builtin)

        all_profiles = list_profiles(search_dirs, config_sections=config_sections)
        available = [p.name for p in all_profiles]
        raise ProfileNotFound(name, available=available)

    @classmethod
    def _from_file(cls, name: str, path: Path) -> "Profile":
        with path.open("rb") as fh:
            data = tomllib.load(fh)
        return cls(name=name, description=data.get("description", ""), data=data)


def list_profiles(
    search_dirs: list[Path],
    *,
    config_sections: dict | None = None,
) -> list[Profile]:
    """Return all profiles from search_dirs, config_sections, and built-ins.

    User-defined profiles take precedence over built-ins; first occurrence
    of a given name wins (same priority order as ``Profile.load``).
    """
    seen: dict[str, Profile] = {}

    def _add(profile: Profile) -> None:
        if profile.name not in seen:
            seen[profile.name] = profile

    for d in search_dirs:
        if not d.exists():
            continue
        for path in sorted(d.glob("*.toml")):
            name = path.stem
            try:
                _add(Profile._from_file(name, path))
            except Exception:
                pass

    if config_sections:
        for name, data in config_sections.items():
            if isinstance(data, dict):
                _add(
                    Profile(
                        name=name,
                        description=data.get("description", ""),
                        data=dict(data),
                    )
                )

    if _BUILTIN_PROFILES_DIR.exists():
        for path in sorted(_BUILTIN_PROFILES_DIR.glob("*.toml")):
            name = path.stem
            try:
                _add(Profile._from_file(name, path))
            except Exception:
                pass

    return list(seen.values())


def apply_profile(global_config: dict[str, Any], profile: Profile) -> dict[str, Any]:
    """Return a new config dict with profile settings merged in.

    This is a pure function — ``global_config`` is never mutated.

    Merge rules:
    - ``provider`` maps to ``default_provider``, ``model`` to ``default_model``.
    - ``tools_allow`` and ``tools_deny``: replace (not union) the global values.
    - ``system_prompt_extra``, ``skills_priority``: added as top-level keys.
    - ``middleware.X`` subsections: each subsection is replaced entirely
      (no field-by-field merge) when present in the profile.
    - All other dict fields: recursively merged with the global.
    - ``description`` is not propagated into the result config.
    """
    result = copy.deepcopy(global_config)

    for key, value in profile.data.items():
        if key == "provider":
            result["default_provider"] = value
        elif key == "model":
            result["default_model"] = value
        elif key == "middleware":
            if "middleware" not in result or not isinstance(result["middleware"], dict):
                result["middleware"] = {}
            if isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    result["middleware"][sub_key] = copy.deepcopy(sub_value)
        elif key == "description":
            pass  # metadata only; not propagated
        else:
            result[key] = copy.deepcopy(value)

    return result
