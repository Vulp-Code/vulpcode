"""Tests for the ContentStore."""
from vulpcode.providers._content_store import ContentStore, get_default_store


def test_put_and_get():
    store = ContentStore()
    store.put("id-1", "Read", "hello\nworld")
    stored = store.get("id-1")
    assert stored is not None
    assert stored.full_body == "hello\nworld"
    assert stored.tool_name == "Read"
    assert stored.is_error is False


def test_size_and_line_count():
    store = ContentStore()
    body = "a\nbb\nccc"
    stored = store.put("id-1", "Read", body)
    assert stored.size_chars == len(body)
    assert stored.line_count == 3


def test_get_missing_returns_none():
    store = ContentStore()
    assert store.get("nope") is None


def test_has():
    store = ContentStore()
    store.put("id-1", "Read", "x")
    assert store.has("id-1")
    assert not store.has("id-2")


def test_lru_eviction():
    store = ContentStore(max_entries=3)
    store.put("a", "Read", "1")
    store.put("b", "Read", "2")
    store.put("c", "Read", "3")
    store.put("d", "Read", "4")  # evicts "a"
    assert not store.has("a")
    assert store.has("b")
    assert store.has("c")
    assert store.has("d")


def test_get_marks_recent():
    store = ContentStore(max_entries=3)
    store.put("a", "Read", "1")
    store.put("b", "Read", "2")
    store.put("c", "Read", "3")
    store.get("a")  # bumps "a" to most recent
    store.put("d", "Read", "4")  # evicts "b", not "a"
    assert store.has("a")
    assert not store.has("b")


def test_list_ids_most_recent_first():
    store = ContentStore()
    store.put("a", "Read", "1")
    store.put("b", "Read", "2")
    store.put("c", "Read", "3")
    assert store.list_ids() == ["c", "b", "a"]


def test_clear():
    store = ContentStore()
    store.put("a", "Read", "1")
    store.clear()
    assert len(store) == 0


def test_default_store_is_singleton():
    a = get_default_store()
    b = get_default_store()
    assert a is b


def test_put_overwrites_existing():
    store = ContentStore()
    store.put("id-1", "Read", "first")
    store.put("id-1", "Read", "second")
    stored = store.get("id-1")
    assert stored is not None
    assert stored.full_body == "second"
