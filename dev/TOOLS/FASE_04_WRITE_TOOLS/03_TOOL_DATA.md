# Tarefa 04.03 — Tools de dados: JSON, YAML, TOML, CSV, XML

**Status**: CONCLUÍDO
**Fase**: 04 - Write Tools
**Dependências**: FASE_03 (`ValidatedWriteTool`)
**Bloqueia**: FASE_06_TESTES

---

## Objetivo

Cinco tools, todas com validação via parser nativo:

| Tool | Validador | Dependência |
|------|-----------|-------------|
| `WriteJson` | `json.loads` | stdlib |
| `WriteYaml` | `yaml.safe_load` | `PyYAML` (extra) |
| `WriteToml` | `tomllib.loads` | stdlib (3.11+) |
| `WriteCsv` | `csv.reader` + check column count uniformity | stdlib |
| `WriteXml` | `xml.etree.ElementTree.fromstring` | stdlib |

Cada arquivo do source segue o mesmo padrão; vou dar o esqueleto completo só do `WriteJson`
e parametrizações para os outros.

---

## `src/vulpcode/tools/write_json.py`

```python
"""WriteJson tool: write a .json file, validated via json.loads."""
from __future__ import annotations

import json

from pydantic import BaseModel

from vulpcode.tools._validated_write import (
    ValidatedWriteTool, ValidationError, format_snippet,
)
from vulpcode.tools.base import tool


@tool(
    name="WriteJson",
    description=(
        "Create or overwrite a JSON file. Validates with json.loads BEFORE saving. "
        "On JSONDecodeError the file is NOT written and the line/column of the "
        "failure are returned for you to fix and resubmit."
    ),
    requires_confirm=True,
)
class WriteJsonTool(ValidatedWriteTool):
    class Input(BaseModel):
        file_path: str
        content: str
        indent: int | None = 2  # pretty-print on save (only if content is JSON-serializable)

    def transform(self, args):
        # Round-trip pretty-print if requested AND content already parses
        if args.indent is None:
            return args.content
        try:
            obj = json.loads(args.content)
        except json.JSONDecodeError:
            return args.content  # let validate() emit the real error
        return json.dumps(obj, indent=args.indent, ensure_ascii=False) + "\n"

    def validate(self, content, args):
        try:
            json.loads(content)
        except json.JSONDecodeError as e:
            raise ValidationError(
                f"JSONDecodeError: {e.msg}",
                line=e.lineno, col=e.colno,
                snippet=format_snippet(content, e.lineno, e.colno),
            )
```

---

## `src/vulpcode/tools/write_yaml.py`

Mesmo padrão. Tool name `WriteYaml`. Validator:

```python
try:
    import yaml
except ImportError:
    raise ValidationError("WriteYaml requires PyYAML. pip install vulpcode[docs-tools]")
try:
    yaml.safe_load(content)
except yaml.YAMLError as e:
    line = getattr(getattr(e, 'problem_mark', None), 'line', None)
    col = getattr(getattr(e, 'problem_mark', None), 'column', None)
    raise ValidationError(
        f"YAMLError: {e}",
        line=(line + 1) if line is not None else None,
        col=(col + 1) if col is not None else None,
        snippet=format_snippet(content, (line or 0) + 1, (col or 0) + 1) if line is not None else None,
    )
```

---

## `src/vulpcode/tools/write_toml.py`

Tool name `WriteToml`. Validator:

```python
import tomllib
try:
    tomllib.loads(content)
except tomllib.TOMLDecodeError as e:
    raise ValidationError(f"TOMLDecodeError: {e}")
```

`tomllib` não expõe linha/coluna numa propriedade fixa — o `str(e)` geralmente carrega
algo como `"Expected ... (at line 4 column 7)"`. Fazer regex em cima do `str(e)` para
extrair, com fallback `line=None`.

---

## `src/vulpcode/tools/write_csv.py`

Aceitar dois modos:

```python
class Input(BaseModel):
    file_path: str
    rows: list[list[str]] | None = None      # structured
    content: str | None = None               # raw CSV text
    delimiter: str = ","
    quotechar: str = '"'
    has_header: bool = True
```

Validador:

```python
import csv, io
if args.rows is not None:
    # Build content from rows then validate column-count uniformity
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=args.delimiter, quotechar=args.quotechar)
    for row in args.rows:
        w.writerow(row)
    text = buf.getvalue()
else:
    text = args.content or ""

# Validate parseable AND uniform column count
reader = csv.reader(io.StringIO(text), delimiter=args.delimiter, quotechar=args.quotechar)
col_count: int | None = None
for i, row in enumerate(reader):
    if col_count is None:
        col_count = len(row)
    elif len(row) != col_count:
        raise ValidationError(
            f"CSV row {i} has {len(row)} cols, expected {col_count}",
            line=i + 1,
            snippet=format_snippet(text, i + 1),
        )
```

`transform` retorna `text` (o CSV serializado quando `rows` foi usado).

---

## `src/vulpcode/tools/write_xml.py`

Tool name `WriteXml`. Validator:

```python
import xml.etree.ElementTree as ET
try:
    ET.fromstring(content)
except ET.ParseError as e:
    # e.position is (line, col), 1-based
    line, col = e.position if hasattr(e, 'position') else (None, None)
    raise ValidationError(
        f"XML ParseError: {e}",
        line=line, col=col,
        snippet=format_snippet(content, line, col) if line else None,
    )
```

---

## Atualizar `tools/__init__.py`

```python
from vulpcode.tools import write_json as _wj  # noqa
from vulpcode.tools import write_yaml as _wy  # noqa
from vulpcode.tools import write_toml as _wt  # noqa
from vulpcode.tools import write_csv as _wc  # noqa
from vulpcode.tools import write_xml as _wx  # noqa
```

---

## Tests

`tests/test_tools/test_write_data.py`:

Padronizar: para cada tool, 3 testes — happy path, syntax error, atomicidade (sem arquivo
após falha).

```python
import pytest
from vulpcode.tools import get_tool
import vulpcode.tools.write_json
import vulpcode.tools.write_yaml
import vulpcode.tools.write_toml
import vulpcode.tools.write_csv
import vulpcode.tools.write_xml


@pytest.mark.asyncio
async def test_write_json_valid(tmp_path):
    cls = get_tool("WriteJson")
    res = await cls().run(cls.Input(
        file_path=str(tmp_path / "x.json"),
        content='{"a": 1, "b": [1,2,3]}',
    ))
    assert res.is_error is False

@pytest.mark.asyncio
async def test_write_json_invalid(tmp_path):
    cls = get_tool("WriteJson")
    target = tmp_path / "bad.json"
    res = await cls().run(cls.Input(
        file_path=str(target),
        content='{"a": 1, "b": [1,2,3}',  # missing ]
    ))
    assert res.is_error is True
    assert "JSONDecodeError" in res.error
    assert not target.exists()

@pytest.mark.asyncio
async def test_write_toml_valid(tmp_path):
    cls = get_tool("WriteToml")
    res = await cls().run(cls.Input(
        file_path=str(tmp_path / "x.toml"),
        content='[tool.poetry]\nname = "foo"\nversion = "1.0"\n',
    ))
    assert res.is_error is False

@pytest.mark.asyncio
async def test_write_csv_uniform_rows(tmp_path):
    cls = get_tool("WriteCsv")
    res = await cls().run(cls.Input(
        file_path=str(tmp_path / "x.csv"),
        rows=[["a","b","c"], ["1","2","3"]],
    ))
    assert res.is_error is False

@pytest.mark.asyncio
async def test_write_csv_inconsistent_columns(tmp_path):
    cls = get_tool("WriteCsv")
    target = tmp_path / "bad.csv"
    res = await cls().run(cls.Input(
        file_path=str(target),
        rows=[["a","b","c"], ["1","2"]],
    ))
    assert res.is_error is True
    assert "expected 3" in res.error
    assert not target.exists()

@pytest.mark.asyncio
async def test_write_xml_malformed(tmp_path):
    cls = get_tool("WriteXml")
    target = tmp_path / "bad.xml"
    res = await cls().run(cls.Input(
        file_path=str(target),
        content="<root><child></root>",
    ))
    assert res.is_error is True
    assert not target.exists()
```

---

## Critérios de Aceite

- [x] Cinco tools registradas: `WriteJson`, `WriteYaml`, `WriteToml`, `WriteCsv`, `WriteXml`
- [x] `WriteJson` faz pretty-print quando `indent` é dado e o content parseia
- [x] `WriteCsv` aceita `rows` estruturadas ou `content` cru
- [x] `WriteCsv` rejeita linhas com contagem de colunas diferente
- [x] Cada tool extrai linha/coluna do erro do parser quando disponível
- [x] Sem arquivo gerado em falha
- [x] >= 10 testes no total, todos passando (com skip pra `WriteYaml` se `PyYAML` ausente)

---

## Riscos

| Risco | Probabilidade | Mitigação |
|-------|---------------|-----------|
| `tomllib` só existe em 3.11+ | Já é o requisito do projeto | Documentado |
| `yaml.safe_load` aceita YAML "vazio" como None | Baixa | Não considerar erro |
| CSV com BOM UTF-8 | Baixa | Aceitar (parser tolera) |

---

**End of Specification**
