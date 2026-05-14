# Providers API

Tipos canonicos, classe base `Provider` e o registry — toda a superficie de
integracao com modelos vive aqui. Para o uso operacional (qual provider
configurar, quais variaveis de ambiente, etc.), veja
[Providers](../providers/index.md).

## Tipos canonicos e classe base

::: vulpcode.providers.base
    options:
      heading_level: 3
      show_root_heading: false
      show_root_full_path: false
      members:
        - Message
        - ToolCall
        - Usage
        - StreamChunk
        - Provider
        - ProviderError

## Registry

Funcoes de lookup e construcao por nome. O caso comum e
`build_provider(name, config)`.

::: vulpcode.providers.registry
    options:
      heading_level: 3
      show_root_heading: false
      show_root_full_path: false
      members:
        - OPENAI_COMPATIBLE_PRESETS
        - build_provider
        - get_provider_class
        - list_provider_names

## Classes concretas

Cada classe abaixo e um adaptador para um SDK ou endpoint especifico. Em
codigo de aplicacao, prefira [`build_provider`](#vulpcode.providers.registry.build_provider)
em vez de instanciar diretamente.

### AnthropicProvider

::: vulpcode.providers.anthropic.AnthropicProvider
    options:
      heading_level: 4
      show_root_full_path: false

### OpenAIProvider

::: vulpcode.providers.openai.OpenAIProvider
    options:
      heading_level: 4
      show_root_full_path: false

### GeminiProvider

::: vulpcode.providers.gemini.GeminiProvider
    options:
      heading_level: 4
      show_root_full_path: false

### OllamaProvider

::: vulpcode.providers.ollama.OllamaProvider
    options:
      heading_level: 4
      show_root_full_path: false

### InternalLLMProvider

::: vulpcode.providers.internal_llm.InternalLLMProvider
    options:
      heading_level: 4
      show_root_full_path: false
