"""Test infrastructure for tests/test_tools/.

`test_base.py` deliberately calls ``clear_registry()`` around every test to
exercise the ``@tool`` decorator from a clean slate. Because the tool modules
are only imported once (decorators register at import time), once those tests
run, ``TOOL_REGISTRY`` ends up empty for every subsequent test file. This
conftest restores the registry by re-binding the production tool classes that
remain attached to their already-imported modules.
"""
from __future__ import annotations

import pytest

import vulpcode.tools  # noqa: F401  (ensures tool modules are imported)
from vulpcode.tools.base import TOOL_REGISTRY, Tool


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
    """Re-register tools defined under ``vulpcode.tools.*`` if missing."""
    for cls in _walk_subclasses(Tool):
        module = getattr(cls, "__module__", "")
        if not module.startswith("vulpcode.tools."):
            continue
        name = getattr(cls, "_tool_name", None)
        if not isinstance(name, str):
            continue
        TOOL_REGISTRY.setdefault(name, cls)


@pytest.fixture(autouse=True)
def _ensure_production_tools_registered(request: pytest.FixtureRequest):
    """Restore production tools before each test outside test_base.py."""
    module_name = request.module.__name__
    if module_name.endswith(".test_base") or module_name == "test_base":
        yield
        return
    _restore_production_tools()
    yield
