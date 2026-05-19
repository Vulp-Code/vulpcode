# Tarefa 01.01 — Protocolo de tool calling baseado em texto

**Status**: CONCLUÍDO
**Fase**: 01 - Protocolo
**Dependências**: nenhuma (base do plano)
**Bloqueia**: FASE_02_PROVIDER

---

## Objetivo

Especificar e implementar o **protocolo XML-ish** que o `InternalLLMAgenticProvider` usa para
trocar tool calls e resultados via texto puro. Entregar também o parser standalone (testável
sem rede) em `src/vulpcode/providers/_text_tool_protocol.py`.

---

## Design do Protocolo

### Chamada de tool (modelo → agente)

```
<vulp:tool name="WritePy">
  <vulp:arg name="file_path">/tmp/fib.py</vulp:arg>
  <vulp:content name="content">
def fib(n):
    a, b = 0, 1
    for _ in range(n):
        print(a)
        a, b = b, a + b
  </vulp:content>
</vulp:tool>
```

Regras:

- **Tag de abertura**: `<vulp:tool name="NOME">` numa linha sozinha. `NOME` deve casar com
  `[A-Za-z_][A-Za-z0-9_]*`.
- **Argumentos escalares** (`<vulp:arg name="K">VALUE</vulp:arg>`): valor é trim'd e tratado
  como string. Conversão de tipo fica a cargo do `Input` pydantic da tool.
- **Argumentos com conteúdo grande / multi-linha** (`<vulp:content name="K">...</vulp:content>`):
  conteúdo é **literal** (não interpretado). Whitespace de indentação inicial (apenas o nível
  comum do bloco) é removido — facilita pro modelo indentar o XML sem quebrar o Python.
- **Tag de fechamento**: `</vulp:tool>` numa linha sozinha.
- **Múltiplas tool calls por resposta**: permitidas; cada uma é um bloco independente.
- **Texto fora dos blocos**: tratado como `delta` (raciocínio livre do modelo, mostrado ao
  usuário). Recomendação no system prompt: minimizar prosa.

### Resultado de tool (agente → modelo, na próxima turn)

Como o endpoint não tem `role="tool"` nativo, o resultado é injetado como mensagem
`role="user"` com o seguinte envelope:

```
<vulp:tool_result name="WritePy" id="abc123" is_error="false">
Wrote 124 bytes to /tmp/fib.py
</vulp:tool_result>
```

Em caso de erro:

```
<vulp:tool_result name="WritePy" id="abc123" is_error="true">
SyntaxError at line 3, col 11: expected ':'
  2 | def fib(n):
> 3 |     a, b = 0 1
                  ^
  4 |     for _ in range(n):
</vulp:tool_result>
```

A injeção do envelope **substitui** o fluxo atual do `_flatten_messages` (que usa
`[tool X result]`) só para o provider agêntico.

---

## Implementação

### Arquivo `src/vulpcode/providers/_text_tool_protocol.py`

Funções públicas:

```python
@dataclass
class ParsedResponse:
    """Resultado do parsing de uma resposta-texto do endpoint."""
    text: str                 # tudo que NÃO está dentro de <vulp:tool>...</vulp:tool>
    tool_calls: list[ToolCall]
    parse_errors: list[str]   # blocos malformados; o caller decide o que fazer


def parse_response(raw: str) -> ParsedResponse: ...


def render_tool_result(
    *,
    name: str,
    call_id: str,
    is_error: bool,
    body: str,
) -> str:
    """Renderiza o envelope <vulp:tool_result> para injetar como user message."""


def render_protocol_help(tools: list[dict]) -> str:
    """
    Renderiza o catálogo de tools + exemplo do protocolo, para injeção no
    system prompt. Recebe a saída de cada Tool.to_schema() do registry.
    """
```

### Estratégia do parser

Use **regex** + scanner linear, não um parser XML real (a) é mais tolerante a texto solto
em volta dos blocos, (b) evita acoplar `lxml`/`xml.etree`, (c) lida com `<` literal dentro
de `<vulp:content>` (que é frequente em código).

Algoritmo:

1. Compile `_TOOL_OPEN = re.compile(r"<vulp:tool\s+name=\"([A-Za-z_][A-Za-z0-9_]*)\"\s*>", re.M)`.
2. Compile `_TOOL_CLOSE = "</vulp:tool>"`.
3. Para cada match de abertura, ache o `</vulp:tool>` mais próximo **depois** dela. Se não
   houver: registra `parse_errors.append("unclosed <vulp:tool>")` e continua do próximo.
4. O segmento interno é parseado em loop por `<vulp:arg name="...">VALUE</vulp:arg>` e
   `<vulp:content name="...">BODY</vulp:content>`. Use regex multiline; para `<vulp:content>`,
   capture até o `</vulp:content>` mais próximo.
5. Dedent do `<vulp:content>` via `textwrap.dedent` + strip da primeira/última linha em branco.
6. Args duplicados: o último vence (e registrar warning em `parse_errors`).
7. Tool sem `<vulp:arg>` nem `<vulp:content>`: válida, `arguments={}`.
8. Gera `ToolCall(id=f"tt-{uuid4().hex[:8]}", name=NAME, arguments={...})`.
9. Constrói `text` removendo todos os blocos de tool da string original (substitui por
   `""`), depois `.strip()`.

### Tratamento de edge cases

| Caso | Comportamento |
|------|---------------|
| Resposta sem nenhum `<vulp:tool>` | `tool_calls=[]`, `text=raw` |
| `<vulp:tool>` aberto sem fechar | Ignora, registra `parse_errors` |
| `<vulp:content>` aberto sem fechar | Ignora a tool inteira, registra erro |
| `<vulp:arg>` com `=` no value (e.g. `python -m foo=bar`) | Aceita; só o `</vulp:arg>` fecha |
| `<vulp:content>` contém literal `</vulp:content>` | Quebra (limitação aceitável). Documentar no system prompt: "se o conteúdo precisa conter `</vulp:content>`, escape como `</vulp:content_literal>` e o agente reverte." |
| Tool com nome desconhecido | Parser aceita; a rejeição vem no `execute_tool_call` do agent loop |

### Atualizar `providers/__init__.py`

Nenhuma mudança — o módulo `_text_tool_protocol` é interno.

---

## Etapas

### Etapa 1 — Criar `src/vulpcode/providers/_text_tool_protocol.py`

Implementar `parse_response`, `render_tool_result`, `render_protocol_help` conforme spec.

### Etapa 2 — Tests em `tests/test_providers/test_text_tool_protocol.py`

Cobertura mínima:

```python
def test_parse_no_tool_block_returns_text_only(): ...
def test_parse_single_tool_with_args(): ...
def test_parse_single_tool_with_content_block(): ...
def test_parse_content_block_is_dedented(): ...
def test_parse_multiple_tool_blocks(): ...
def test_parse_unclosed_tool_recorded_as_error(): ...
def test_parse_unclosed_content_drops_whole_block(): ...
def test_render_tool_result_success(): ...
def test_render_tool_result_error_with_multiline_body(): ...
def test_render_protocol_help_lists_all_tools(): ...
def test_parse_text_strips_tool_blocks(): ...
def test_parse_text_preserves_prose_around_blocks(): ...
```

### Etapa 3 — Rodar `pytest tests/test_providers/test_text_tool_protocol.py -v`

---

## Critérios de Aceite

- [x] `src/vulpcode/providers/_text_tool_protocol.py` existe e expõe `parse_response`,
      `render_tool_result`, `render_protocol_help`
- [x] `ParsedResponse` carrega `text`, `tool_calls`, `parse_errors`
- [x] `<vulp:content>` é dedented corretamente
- [x] Múltiplos blocos `<vulp:tool>` na mesma resposta são todos extraídos
- [x] Blocos malformados não derrubam o parser — viram entradas em `parse_errors`
- [x] `render_tool_result` produz envelope determinístico (mesmas entradas → mesma saída)
- [x] >= 12 testes em `tests/test_providers/test_text_tool_protocol.py`, todos passando
- [x] Sem dependência nova no `pyproject.toml`

---

## Riscos

| Risco | Probabilidade | Mitigação |
|-------|---------------|-----------|
| Conteúdo do usuário contém `</vulp:content>` literal | Baixa | Documentar escape `</vulp:content_literal>` |
| Modelo emite `<vulp:tool>` sem fechar | Média | Parser registra erro; system prompt mostra exemplo correto |
| Modelo gera tool name desconhecido | Média | Tratado no `execute_tool_call`; erro volta como tool_result is_error=true |

---

**End of Specification**
