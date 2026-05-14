"""SlashCommand base class."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vulpcode.ui.repl import Repl


class SlashCommand(ABC):
    """Base class for REPL slash commands."""

    name: str
    help_text: str = ""

    @abstractmethod
    async def run(self, repl: "Repl", args: str) -> None: ...
