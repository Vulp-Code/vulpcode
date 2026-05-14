"""Provider adapters and abstractions."""
from vulpcode.providers.base import (
    Message,
    Provider,
    ProviderError,
    StreamChunk,
    ToolCall,
    Usage,
)
from vulpcode.providers.registry import (
    OPENAI_COMPATIBLE_PRESETS,
    build_provider,
    get_provider_class,
    list_provider_names,
)

__all__ = [
    "Message",
    "Provider",
    "ProviderError",
    "StreamChunk",
    "ToolCall",
    "Usage",
    "OPENAI_COMPATIBLE_PRESETS",
    "build_provider",
    "get_provider_class",
    "list_provider_names",
]
