"""Token counting utility with optional tiktoken acceleration."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_enc = None
_tiktoken_unavailable = False


def _get_encoding():
    global _enc, _tiktoken_unavailable
    if _enc is not None:
        return _enc
    if _tiktoken_unavailable:
        return None
    try:
        import tiktoken  # type: ignore[import]

        _enc = tiktoken.get_encoding("o200k_base")
        return _enc
    except Exception:
        _tiktoken_unavailable = True
        return None


def count_tokens(text: str, model: str | None = None) -> int:
    """Count tokens in *text*.

    Uses tiktoken with the ``o200k_base`` encoding when available (accurate
    within ~10% for all modern models). Falls back to ``max(1, len(text) // 4)``
    when tiktoken is not installed.

    Args:
        text: Input text to count.
        model: Unused — reserved for future per-model encoding selection.

    Returns:
        Estimated token count, always >= 1.
    """
    enc = _get_encoding()
    if enc is not None:
        return len(enc.encode(text))
    return max(1, len(text) // 4)
