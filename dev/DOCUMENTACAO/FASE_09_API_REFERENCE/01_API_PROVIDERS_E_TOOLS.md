# Tarefa 09.01 - API Reference (Providers + Tools)

**Status**: PENDENTE
**Fase**: 09 - API Reference (mkdocstrings)
**Dependencias**: 08.02
**Bloqueia**: 09.02

---

## Objetivo

Criar paginas auto-geradas via `mkdocstrings` para o modulo de providers e
tools. Resolve docstrings em runtime — nao copia o codigo.

---

## Arquivos a criar

- `docs/api/index.md`
- `docs/api/providers.md`
- `docs/api/tools.md`

---

## Pre-requisito: docstrings melhoradas

Antes de criar as paginas, **melhore as docstrings** dos seguintes arquivos
no formato Google (sem alterar comportamento):

- `src/vulpcode/providers/base.py` — `Provider`, `Message`, `StreamChunk`,
  `ToolCall`, `Usage`, `ProviderError`
- `src/vulpcode/providers/registry.py` — `build_provider`, `get_provider_class`,
  `list_provider_names`, `OPENAI_COMPATIBLE_PRESETS`
- Cada `src/vulpcode/providers/*.py` — classe `Provider` com docstring de classe
- `src/vulpcode/tools/base.py` — `Tool`, `ToolResult`, `tool` (decorator),
  `TOOL_REGISTRY`, `get_tool`, `list_tools`, `execute_tool_call`

Padrao:

```python
def build_provider(name: str, config: dict[str, Any] | None = None) -> Provider:
    """Build a Provider instance by name.

    Args:
        name: Provider name (e.g. "anthropic", "deepseek", "ollama").
            Case-insensitive.
        config: Configuration dict with keys like ``api_key``, ``base_url``,
            ``timeout``. If ``base_url`` is omitted and the name is an
            OpenAI-compatible preset, the preset URL is used.

    Returns:
        A configured ``Provider`` instance.

    Raises:
        ValueError: If ``name`` is not a known provider.

    Example:
        >>> p = build_provider("anthropic", {"api_key": "sk-ant-..."})
        >>> p.name
        'anthropic'
    """
```

---

## Conteudo de `api/index.md`

Indice da secao API:

```markdown
# API Reference

Referencia auto-gerada da API publica do `vulpcode`. Use isso ao integrar
o vulpcode como biblioteca em outro projeto Python.

## Modulos

- [Providers](providers.md) — `Provider`, `build_provider`, types canonicos
- [Tools](tools.md) — `Tool`, `@tool`, registry, helpers
- [Agent](agent.md) — `Agent` class, eventos, run_to_completion
- [Permissions](permissions.md) — `PermissionManager`, `Mode`
- [Config](config.md) — `load_config`, `save_config`
- [Session](session.md) — `save_session`, `load_session`
- [MCP](mcp.md) — `connect_mcp_server`, `start_configured_servers`

## Convencao

Tudo neste site e gerado das docstrings em `src/vulpcode/`. Para abrir o
codigo no GitHub, clique no link "Source" abaixo de cada simbolo.
```

---

## Conteudo de `api/providers.md`

```markdown
# Providers API

::: vulpcode.providers.base
    options:
      heading_level: 2
      show_root_full_path: false
      members:
        - Message
        - ToolCall
        - Usage
        - StreamChunk
        - Provider
        - ProviderError

## Registry

::: vulpcode.providers.registry
    options:
      heading_level: 2
      show_root_full_path: false
      members:
        - OPENAI_COMPATIBLE_PRESETS
        - build_provider
        - get_provider_class
        - list_provider_names

## Classes concretas

::: vulpcode.providers.anthropic.AnthropicProvider
::: vulpcode.providers.openai.OpenAIProvider
::: vulpcode.providers.gemini.GeminiProvider
::: vulpcode.providers.ollama.OllamaProvider
::: vulpcode.providers.internal_llm.InternalLLMProvider
```

---

## Conteudo de `api/tools.md`

```markdown
# Tools API

::: vulpcode.tools.base
    options:
      heading_level: 2
      show_root_full_path: false
      members:
        - Tool
        - ToolResult
        - tool
        - TOOL_REGISTRY
        - get_tool
        - list_tools
        - execute_tool_call
        - clear_registry

## Tools nativas

Cada tool e uma classe com `@tool` decorator. Veja [Tools](../tools/index.md)
para uso operacional. Aqui esta apenas o schema.

::: vulpcode.tools.read.ReadTool
::: vulpcode.tools.write.WriteTool
::: vulpcode.tools.edit.EditTool
::: vulpcode.tools.edit.MultiEditTool
::: vulpcode.tools.glob.GlobTool
::: vulpcode.tools.grep.GrepTool
::: vulpcode.tools.bash.BashTool
::: vulpcode.tools.bash_background.BashOutputTool
::: vulpcode.tools.bash_background.KillBashTool
::: vulpcode.tools.web.WebFetchTool
::: vulpcode.tools.web.WebSearchTool
::: vulpcode.tools.task.TaskTool
::: vulpcode.tools.todo.TodoWriteTool
::: vulpcode.tools.notebook.NotebookEditTool
```

---

## Atualizar `mkdocs.yml`

Adicionar bloco `API Reference`:

```yaml
- API Reference:
    - api/index.md
    - Providers: api/providers.md
    - Tools: api/tools.md
    - Agent: api/agent.md                 # 09.02
    - Permissions: api/permissions.md     # 09.02
    - Config: api/config.md               # 09.03
    - Session: api/session.md             # 09.03
    - MCP: api/mcp.md                     # 09.03
```

---

## INSTRUCAO CRITICA

- mkdocstrings precisa que `paths: [src]` esteja em `mkdocs.yml` (ja
  configurado em FASE 01.01).
- Se a docstring em algum simbolo estiver vazia / muito curta, melhore-a.
  Nao deixe `Returns: ...` sem conteudo real.
- O build com `--strict` no FASE 13 vai pegar simbolos sem docstring se
  `show_if_no_docstring: false` (que e o padrao).

---

## Etapas de Implementacao

### Etapa 1: Auditar docstrings de providers/base.py, registry.py, tools/base.py
### Etapa 2: Melhorar docstrings (adicionar Args, Returns, Raises, Example)
### Etapa 3: Criar `api/index.md`, `api/providers.md`, `api/tools.md`
### Etapa 4: Atualizar `mkdocs.yml`
### Etapa 5: `mkdocs build` — verificar que paginas geram conteudo

---

## Criterios de Aceite

- [x] Docstrings em providers/base.py melhoradas (formato Google)
- [x] Docstrings em registry.py melhoradas
- [x] Docstrings em tools/base.py melhoradas
- [x] `docs/api/index.md` criado
- [x] `docs/api/providers.md` criado com diretivas `:::` para todos os simbolos publicos
- [x] `docs/api/tools.md` criado com diretivas para 14 tools nativas
- [x] `mkdocs.yml` atualizado com bloco "API Reference"
- [x] `mkdocs build` gera conteudo nas paginas (verificar visualmente)
- [x] Sem warnings de mkdocstrings sobre simbolos nao encontrados

---

**End of Specification**
