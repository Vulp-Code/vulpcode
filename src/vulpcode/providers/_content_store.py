"""In-memory keyed store for full tool-result bodies.

When the agentic provider sees a tool result whose body would blow the
128k-token input window, it stores the full body here keyed by the
``tool_call_id`` and sends only a head/tail preview to the LLM. The model
can pull specific slices back via the ``Retrieve`` tool, which reads from
this store.

The store is **process-global** and not shared across processes. Eviction
is LRU-style with a cap on entries. Thread-safe via a single lock.

Scope: this works because the CLI runs a single Agent per process. If
multi-tenant or multi-Agent isolation is ever needed, refactor to live on
the Agent (or provider instance) and pass it explicitly to the Retrieve
tool through some context mechanism.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from threading import Lock


_DEFAULT_MAX_ENTRIES = 50


@dataclass
class StoredContent:
    """A cached tool-result body and its metadata.

    Attributes:
        cache_id: The tool_call_id from the original ToolCall (e.g. "tt-abc123").
        tool_name: Name of the tool that produced the result (e.g. "Read").
        full_body: The complete body text (without the <vulp:tool_result> envelope).
        is_error: Whether the original result was an error.
        lines: Pre-split list of lines (cached on first slice for cheap re-slicing).
    """

    cache_id: str
    tool_name: str
    full_body: str
    is_error: bool = False
    lines: list[str] = field(default_factory=list)

    @property
    def size_chars(self) -> int:
        return len(self.full_body)

    @property
    def line_count(self) -> int:
        if not self.lines:
            self.lines = self.full_body.splitlines()
        return len(self.lines)


class ContentStore:
    """LRU-capped, thread-safe map of cache_id → StoredContent."""

    def __init__(self, max_entries: int = _DEFAULT_MAX_ENTRIES) -> None:
        self._max = max_entries
        self._data: OrderedDict[str, StoredContent] = OrderedDict()
        self._lock = Lock()

    def put(
        self,
        cache_id: str,
        tool_name: str,
        full_body: str,
        is_error: bool = False,
    ) -> StoredContent:
        """Store full body keyed by ``cache_id``, evicting oldest if full."""
        stored = StoredContent(
            cache_id=cache_id,
            tool_name=tool_name,
            full_body=full_body,
            is_error=is_error,
        )
        with self._lock:
            if cache_id in self._data:
                self._data.move_to_end(cache_id)
            self._data[cache_id] = stored
            while len(self._data) > self._max:
                self._data.popitem(last=False)
        return stored

    def get(self, cache_id: str) -> StoredContent | None:
        """Fetch and mark as recently used. Returns None when missing."""
        with self._lock:
            stored = self._data.get(cache_id)
            if stored is not None:
                self._data.move_to_end(cache_id)
            return stored

    def has(self, cache_id: str) -> bool:
        with self._lock:
            return cache_id in self._data

    def list_ids(self) -> list[str]:
        """List currently-cached ids, most recent first."""
        with self._lock:
            return list(reversed(self._data.keys()))

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)


# Process-global default store. Tools and providers share this instance.
_default_store = ContentStore()


def get_default_store() -> ContentStore:
    """Return the singleton :class:`ContentStore` used across the process."""
    return _default_store
