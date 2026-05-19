# Tarefa 05.01 — System prompt + loop de reparo

**Status**: PENDENTE
**Fase**: 05 - System Prompt
**Dependências**: FASE_02 (provider), FASE_04 (tools registradas)
**Bloqueia**: FASE_06_TESTES

---

## Objetivo

Definir o system prompt que o `InternalLLMAgenticProvider` injeta — a peça que ensina o
modelo a **(a)** emitir tool calls no protocolo XML-ish e **(b)** persistir corrigindo
erros de sintaxe em vez de desistir. Também ajustar o `_max_iters` do agent quando este
provider está em uso (modelos pequenos podem precisar de mais iterações pra convergir).

---

## System Prompt

Implementar em `src/vulpcode/providers/_text_tool_protocol.py::render_protocol_help(tools)`.
Estrutura:

```
# Tool calling protocol

You are running against an endpoint that does NOT support native tool calling.
To invoke a tool, emit one or more blocks in this exact format inside your response:

<vulp:tool name="ToolName">
  <vulp:arg name="key">scalar value</vulp:arg>
  <vulp:content name="content">
multi-line
content goes here
verbatim
  </vulp:content>
</vulp:tool>

Rules:
- Tag names are case-sensitive: lowercase `vulp:tool`, `vulp:arg`, `vulp:content`.
- Use `<vulp:arg>` for short scalar values (paths, numbers, single words).
- Use `<vulp:content>` for multi-line or code-containing values.
- The content of `<vulp:content>` is taken literally — do NOT escape special chars.
- Indentation of the `<vulp:content>` body is preserved relative to the block (common
  leading whitespace is stripped, so you can indent the XML naturally).
- Emit ZERO prose between tool blocks. Prose goes BEFORE the first block or AFTER the
  last one. Brief is best.

Tool results return as:

<vulp:tool_result name="X" id="..." is_error="true|false">
... body / error message ...
</vulp:tool_result>

# Repair loop — CRITICAL

If a `<vulp:tool_result is_error="true">` arrives, you MUST:
  1. Read the error message carefully — it includes line, column, and a code snippet.
  2. Identify the exact cause (often a typo, missing colon, unbalanced brace, etc.).
  3. Re-emit the SAME tool with corrected content. Do NOT switch tools or apologise.
  4. Repeat. Most syntax errors are fixed in 1–2 retries.

Do NOT respond with prose like "Sorry, let me try again". Just emit the corrected tool
call. The user only cares about the final working file.

If after 3 retries the same error persists, then explain to the user what is blocking
you and ask for guidance. Otherwise, keep iterating.

# Available tools

{TOOL_CATALOG}
```

Onde `{TOOL_CATALOG}` é renderizado dinamicamente a partir das tools registradas:

```python
def render_protocol_help(tools: list[dict]) -> str:
    catalog = []
    for t in tools:
        schema = t["input_schema"]
        props = schema.get("properties", {})
        req = set(schema.get("required", []))
        args_lines = []
        for k, v in props.items():
            kind = v.get("type", "any")
            marker = "*" if k in req else " "
            desc = v.get("description", "")
            args_lines.append(f"  {marker} {k}: {kind}{(' — ' + desc) if desc else ''}")
        catalog.append(
            f"## {t['name']}\n{t['description']}\nArgs:\n" + "\n".join(args_lines)
        )
    return _PROMPT_TEMPLATE.replace("{TOOL_CATALOG}", "\n\n".join(catalog))
```

**Cuidado com tamanho**: o catálogo pode estourar input do endpoint. Mitigação:

- Truncar descrições de args a 80 chars.
- Para tools com schema profundo (e.g. `WriteIpynb` com `cells: list[_Cell]`), substituir
  por uma forma simplificada manualmente curada (manter no código uma `dict[str, str]` de
  "short description" como override).

---

## Ajuste de `_max_iters` no Agent

Modelos pequenos exigem mais ciclos de reparo. Em `src/vulpcode/agent.py`:

- Manter o default `25`.
- Adicionar no `__init__` do `Agent` um parâmetro `max_iters: int = 25` que sobrepõe.
- Em `src/vulpcode/app.py` (ou onde quer que o `Agent` seja instanciado), checar o nome do
  provider; se `internal-llm-agentic`, passar `max_iters=50`. Isso dá folga para 20+
  ciclos de reparo.

---

## Few-shot inline (opcional mas recomendado)

Modelos pequenos seguem o protocolo muito melhor com um exemplo. Adicionar ao template:

```
# Example

User: create a file /tmp/hello.py that prints "hello"

You (correct response — NO prose):
<vulp:tool name="WritePy">
  <vulp:arg name="file_path">/tmp/hello.py</vulp:arg>
  <vulp:content name="content">
print("hello")
  </vulp:content>
</vulp:tool>

(tool result arrives)
<vulp:tool_result name="WritePy" id="..." is_error="false">
Wrote 15 bytes to /tmp/hello.py
</vulp:tool_result>

You (final ack — short):
Done.
```

---

## Etapas

### Etapa 1 — Implementar `render_protocol_help` em `_text_tool_protocol.py`

Conforme spec.

### Etapa 2 — Aplicar override de descrições de tool

Criar `_TOOL_HELP_OVERRIDES: dict[str, str]` no mesmo módulo, com versões compactas das
descrições de tools que normalmente seriam longas demais.

### Etapa 3 — Aumentar `_max_iters` quando o provider é agêntico

Editar `src/vulpcode/agent.py::Agent.__init__` para aceitar `max_iters`.
Editar `src/vulpcode/app.py` para passar `max_iters=50` quando `provider.name == "internal-llm-agentic"`.

### Etapa 4 — Tests

`tests/test_providers/test_protocol_prompt.py`:

```python
from vulpcode.providers._text_tool_protocol import render_protocol_help

def test_protocol_help_lists_all_provided_tools():
    tools = [
        {"name": "WritePy", "description": "Write a .py", "input_schema": {
            "properties": {"file_path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["file_path", "content"],
        }},
    ]
    out = render_protocol_help(tools)
    assert "WritePy" in out
    assert "file_path" in out
    assert "<vulp:tool name=\"" in out

def test_protocol_help_marks_required_args():
    tools = [{"name": "X", "description": "y", "input_schema": {
        "properties": {"a": {"type": "string"}, "b": {"type": "string"}},
        "required": ["a"],
    }}]
    out = render_protocol_help(tools)
    assert "* a:" in out  # required
    assert "  b:" in out  # optional
```

---

## Critérios de Aceite

- [x] `render_protocol_help` retorna prompt completo (regras + catálogo) determinístico
- [x] Catálogo lista todas as tools passadas e indica args required vs optional
- [x] Prompt inclui exemplo few-shot do protocolo
- [x] Prompt inclui instruções explícitas do loop de reparo (CRITICAL section)
- [x] `Agent.__init__` aceita `max_iters` opcional
- [x] `app.py` passa `max_iters=50` para `internal-llm-agentic`
- [x] Tests do render passando

---

## Riscos

| Risco | Probabilidade | Mitigação |
|-------|---------------|-----------|
| Catálogo gigante estoura input do endpoint | Alta | Overrides curtos por tool; possivelmente paginação no futuro |
| Modelo continua misturando prosa entre blocos | Média | System prompt é explícito; few-shot ajuda; `temperature=0.3` ajuda |
| Modelo desiste depois do 1º erro | Média | "CRITICAL" + frase "Do NOT respond with apologies" no prompt |
| Loop infinito se reparo nunca converge | Baixa | `_max_iters=50` é o limite |

---

**End of Specification**
