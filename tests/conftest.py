"""Shared test infrastructure for the root ``tests/`` package.

Provides:

* ``ScriptedProvider`` and a ``scripted_provider`` fixture so multiple test
  files can drive ``Agent`` without redefining a mock provider.
* An autouse fixture that restores the production tool registry before each
  test that lives directly under ``tests/`` (excluding the ``test_tools/``
  subpackage, which manages its own registry lifecycle).

The registry restoration mirrors ``tests/test_tools/conftest.py`` and exists
to keep the suite stable when ``clear_registry()`` is called by other tests.
"""
from __future__ import annotations

from typing import Any, AsyncIterator

import pytest

import vulpcode.tools  # noqa: F401  (force import so tool decorators run)
from vulpcode.providers.base import Message, Provider, StreamChunk
from vulpcode.tools.base import TOOL_REGISTRY, Tool


class ScriptedProvider(Provider):
    """Provider that yields pre-recorded ``StreamChunk`` lists, one per turn."""

    name = "scripted"

    def __init__(self, scripts: list[list[StreamChunk]] | None = None) -> None:
        super().__init__()
        self.scripts: list[list[StreamChunk]] = list(scripts or [])

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        model: str,
        system: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        if not self.scripts:
            yield StreamChunk(type="stop")
            return
        for chunk in self.scripts.pop(0):
            yield chunk

    def supports_tools(self) -> bool:
        return True

    def supports_vision(self) -> bool:
        return False


@pytest.fixture
def scripted_provider():
    """Factory fixture: build a ``ScriptedProvider`` from a list of turn scripts."""

    def factory(scripts: list[list[StreamChunk]]) -> ScriptedProvider:
        return ScriptedProvider(scripts)

    return factory


def _walk_subclasses(root: type) -> list[type]:
    seen: set[type] = set()
    stack: list[type] = [root]
    out: list[type] = []
    while stack:
        cls = stack.pop()
        for sub in cls.__subclasses__():
            if sub in seen:
                continue
            seen.add(sub)
            out.append(sub)
            stack.append(sub)
    return out


def _restore_production_tools() -> None:
    for cls in _walk_subclasses(Tool):
        module = getattr(cls, "__module__", "")
        if not module.startswith("vulpcode.tools."):
            continue
        name = getattr(cls, "_tool_name", None)
        if not isinstance(name, str):
            continue
        TOOL_REGISTRY.setdefault(name, cls)


@pytest.fixture(autouse=True)
def _restore_tools_outside_tools_subpackage(request: pytest.FixtureRequest):
    """Restore production tools for tests directly under ``tests/``.

    The ``tests/test_tools/`` subpackage owns its own registry lifecycle via
    its local conftest, so we skip it here.
    """
    module_name = request.module.__name__
    if "test_tools" in module_name.split("."):
        yield
        return
    _restore_production_tools()
    yield
