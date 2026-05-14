"""UI themes."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    name: str
    primary: str
    accent: str
    success: str
    warning: str
    danger: str
    muted: str
    code_theme: str


THEMES: dict[str, Theme] = {
    "default": Theme(
        name="default",
        primary="cyan",
        accent="magenta",
        success="green",
        warning="yellow",
        danger="red",
        muted="bright_black",
        code_theme="monokai",
    ),
    "monokai": Theme(
        name="monokai",
        primary="bright_cyan",
        accent="bright_magenta",
        success="bright_green",
        warning="bright_yellow",
        danger="bright_red",
        muted="bright_black",
        code_theme="monokai",
    ),
    "light": Theme(
        name="light",
        primary="blue",
        accent="magenta",
        success="green",
        warning="yellow",
        danger="red",
        muted="grey50",
        code_theme="default",
    ),
}


def get_theme(name: str) -> Theme:
    return THEMES.get(name, THEMES["default"])
