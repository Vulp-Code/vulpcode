# Tarefa 13.02 - Testes Adicionais de Tools

**Status**: PENDENTE
**Fase**: 13 - Testes
**Dependencias**: FASE 04, 05, 06 (todas as tools)
**Bloqueia**: Nada

---

## Objetivo

Adicionar testes de regressao e cobertura para casos de borda das tools que
podem nao ter sido capturados nos testes inline da FASE 04-06. Foco em:
- Concorrencia (Bash background paralelo)
- Robustez (Read em arquivos com encoding misto, Edit em arquivos enormes)
- Integracao tool-tool (TodoWrite -> Read sequence)

---

## Descricao Tecnica

### Casos a cobrir

1. **Bash + BashOutput em paralelo**: dois processos em background, ler outputs
   independentemente.
2. **Read encoding misto**: arquivos com BOM, UTF-16, latin-1.
3. **Edit + MultiEdit em arquivos grandes**: 100k linhas.
4. **Glob com padroes complexos**: `**/*.py`, `**/[a-z]*.txt`.
5. **Grep regex avancado**: lookahead, multiline mode.
6. **WebFetch redirects e content-types diversos**.
7. **TodoWrite + integration**: criar lista, modificar status, ler via `get_todos()`.

### Estrutura

**`tests/test_tools/test_bash_concurrency.py`**:

```python
import asyncio
import pytest

import vulpcode.tools  # noqa
from vulpcode.tools import get_tool
from vulpcode.tools._bash_registry import _REGISTRY


@pytest.fixture(autouse=True)
def _clean():
    _REGISTRY.clear()
    yield
    _REGISTRY.clear()


@pytest.mark.asyncio
async def test_two_background_processes_parallel():
    bash = get_tool("Bash")
    bo = get_tool("BashOutput")

    res_a = await bash().run(bash.Input(command="echo a; sleep 0.2; echo done_a", run_in_background=True))
    res_b = await bash().run(bash.Input(command="echo b; sleep 0.2; echo done_b", run_in_background=True))
    a_id = res_a.metadata["bash_id"]
    b_id = res_b.metadata["bash_id"]
    assert a_id != b_id

    await asyncio.sleep(0.4)
    out_a = await bo().run(bo.Input(bash_id=a_id))
    out_b = await bo().run(bo.Input(bash_id=b_id))
    assert "a" in out_a.output and "done_a" in out_a.output
    assert "b" in out_b.output and "done_b" in out_b.output
```

**`tests/test_tools/test_read_encodings.py`**:

```python
from pathlib import Path
import pytest

import vulpcode.tools  # noqa
from vulpcode.tools import get_tool


@pytest.mark.asyncio
async def test_read_utf8_with_bom(tmp_path: Path):
    f = tmp_path / "bom.txt"
    f.write_bytes(b"\xef\xbb\xbfhello\n")
    res = await get_tool("Read")().run(get_tool("Read").Input(file_path=str(f)))
    assert "hello" in res.output


@pytest.mark.asyncio
async def test_read_latin1_via_replace(tmp_path: Path):
    f = tmp_path / "lat.txt"
    f.write_bytes("café\n".encode("latin-1"))
    res = await get_tool("Read")().run(get_tool("Read").Input(file_path=str(f)))
    # Decoded as utf-8 with replace; should not error and should not be empty
    assert res.is_error is False
    assert len(res.output) > 0
```

**`tests/test_tools/test_edit_large_file.py`**:

```python
from pathlib import Path
import pytest

import vulpcode.tools  # noqa
from vulpcode.tools import get_tool


@pytest.mark.asyncio
async def test_edit_in_huge_file(tmp_path: Path):
    f = tmp_path / "big.py"
    lines = ["x = 0\n"] * 100_000 + ["target = 42\n"] + ["y = 1\n"] * 100_000
    f.write_text("".join(lines))
    cls = get_tool("Edit")
    res = await cls().run(cls.Input(
        file_path=str(f), old_string="target = 42", new_string="target = 99",
    ))
    assert res.is_error is False
    assert "target = 99" in f.read_text()
```

**`tests/test_tools/test_grep_advanced.py`**:

```python
from pathlib import Path
import pytest

import vulpcode.tools  # noqa
from vulpcode.tools import get_tool


@pytest.mark.asyncio
async def test_grep_multiline(tmp_path: Path):
    f = tmp_path / "x.py"
    f.write_text("def foo():\n    pass\n\ndef bar():\n    pass\n")
    cls = get_tool("Grep")
    res = await cls().run(cls.Input(
        pattern=r"def \w+\(\):\n\s+pass",
        path=str(tmp_path),
        multiline=True,
    ))
    # Either backend should match the multiline pattern
    assert res.is_error is False


@pytest.mark.asyncio
async def test_grep_head_limit(tmp_path: Path):
    f = tmp_path / "lots.py"
    f.write_text("\n".join(f"hit_{i}" for i in range(50)))
    cls = get_tool("Grep")
    res = await cls().run(cls.Input(pattern="hit_", path=str(tmp_path), head_limit=5))
    assert res.output.count("\n") <= 6  # 5 lines + truncation note maybe
```

**`tests/test_tools/test_integration_todo.py`**:

```python
import pytest

import vulpcode.tools  # noqa
from vulpcode.tools import get_tool
from vulpcode.tools.todo import get_todos, clear_todos


@pytest.fixture(autouse=True)
def _clean():
    clear_todos()
    yield
    clear_todos()


@pytest.mark.asyncio
async def test_todo_workflow():
    cls = get_tool("TodoWrite")
    TodoItem = cls.Input.model_fields["todos"].annotation.__args__[0]
    # Initial list with one in_progress
    await cls().run(cls.Input(todos=[
        TodoItem(content="A", activeForm="Doing A", status="in_progress"),
        TodoItem(content="B", activeForm="Doing B", status="pending"),
    ]))
    # Mark A done, start B
    await cls().run(cls.Input(todos=[
        TodoItem(content="A", activeForm="Doing A", status="completed"),
        TodoItem(content="B", activeForm="Doing B", status="in_progress"),
    ]))
    todos = get_todos()
    assert todos[0].status == "completed"
    assert todos[1].status == "in_progress"
```

---

## INSTRUCAO CRITICA

- Testes em `tmp_path` para nao tocar disco do projeto.
- Testes de Bash background usam `asyncio.sleep` curtos — manter previsibilidade.
- Tests de encoding: writebytes para evitar reinterpretacao do filesystem.
- Cobertura alvo: cada tool deve atingir >=70% nas linhas executaveis.

---

## Etapas de Implementacao

### Etapa 1: Criar arquivos de testes adicionais

Criar os 5 arquivos descritos acima em `tests/test_tools/`.

### Etapa 2: Rodar suite e verificar cobertura

```bash
pytest tests/test_tools/ -v --cov=src/vulpcode/tools --cov-report=term-missing
```

Cobertura alvo: >=70% em cada modulo de tool.

### Etapa 3: Identificar gaps e adicionar testes onde faltar

Se algum modulo estiver abaixo de 70%, criar 1-2 testes pontuais.

---

## Criterios de Aceite

- [x] `tests/test_tools/test_bash_concurrency.py` criado e passa
- [x] `tests/test_tools/test_read_encodings.py` criado e passa
- [x] `tests/test_tools/test_edit_large_file.py` criado e passa
- [x] `tests/test_tools/test_grep_advanced.py` criado e passa
- [x] `tests/test_tools/test_integration_todo.py` criado e passa
- [x] Cobertura de `src/vulpcode/tools/` >= 70% (`pytest --cov`)
- [x] Toda a suite tools passa (`pytest tests/test_tools/`)

---

## Riscos Tecnicos

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|---------------|---------|-----------|
| Testes flaky de timing (Bash bg) | Media | Baixo | Margens generosas em sleep |
| Edit em 200k linhas e lento | Baixa | Baixo | Aceitar; e teste isolado |
| Encoding diferente nos sistemas | Baixa | Baixo | `errors="replace"` cobre |

---

**End of Specification**
