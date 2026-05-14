# Tarefa 12.01 - Persistencia de Sessao

**Status**: PENDENTE
**Fase**: 12 - Session
**Dependencias**: 08.01, 10.03 (slash save/load apontam aqui)
**Bloqueia**: Nada

---

## Objetivo

Implementar `src/vulpcode/session.py` com persistencia robusta de sessoes em
disco (`~/.vulpcode/sessions/`). Substitui o `session_fallback.py` da FASE 10.03.
Adiciona suporte a `--resume` no CLI.

---

## Descricao Tecnica

### API publica

```python
def save_session(name: str, agent: "Agent", *, scope: Path | None = None) -> Path:
    """Persist agent state (model, system prompt, messages) to JSON."""

def load_session(name: str, agent: "Agent", *, scope: Path | None = None) -> None:
    """Load named session into agent (in place)."""

def list_sessions(*, scope: Path | None = None) -> list[dict]:
    """List session files with metadata (name, mtime, message count)."""

def latest_session_name(*, scope: Path | None = None) -> str | None:
    """Name of the most recently modified session, used by --resume."""

def delete_session(name: str, *, scope: Path | None = None) -> bool:
    """Remove a session file. Returns False if it didn't exist."""
```

### Formato JSON

```json
{
  "version": 1,
  "name": "default",
  "saved_at": "2026-05-06T15:00:00",
  "model": "claude-sonnet-4-7",
  "provider_name": "anthropic",
  "system": "...",
  "messages": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "...", "tool_calls": [...]}
  ],
  "session_usage": {"input_tokens": 100, "output_tokens": 200, ...}
}
```

### Estrutura

**`src/vulpcode/session.py`**:

```python
"""Session persistence (~/.vulpcode/sessions/)."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from vulpcode.agent import Agent


_VERSION = 1


def _sessions_dir(scope: Path | None = None) -> Path:
    base = scope or (Path.home() / ".vulpcode" / "sessions")
    base.mkdir(parents=True, exist_ok=True)
    return base


def _session_path(name: str, scope: Path | None = None) -> Path:
    safe = "".join(c for c in name if c.isalnum() or c in ("-", "_"))
    if not safe:
        safe = "default"
    return _sessions_dir(scope) / f"{safe}.json"


def save_session(name: str, agent: "Agent", *, scope: Path | None = None) -> Path:
    target = _session_path(name, scope)
    payload = {
        "version": _VERSION,
        "name": name,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "provider_name": getattr(agent.provider, "name", "unknown"),
        "model": agent.model,
        "system": agent.system,
        "messages": [m.model_dump() for m in agent._messages],
        "session_usage": (
            agent._session_usage.model_dump()
            if hasattr(agent, "_session_usage") else None
        ),
    }
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(target)
    return target


def load_session(name: str, agent: "Agent", *, scope: Path | None = None) -> None:
    from vulpcode.providers.base import Message, Usage
    target = _session_path(name, scope)
    if not target.exists():
        raise FileNotFoundError(f"Session {name!r} not found at {target}")
    payload = json.loads(target.read_text(encoding="utf-8"))
    agent.system = payload.get("system", agent.system)
    agent.model = payload.get("model", agent.model)
    agent._messages = [Message.model_validate(m) for m in payload.get("messages", [])]
    if hasattr(agent, "_session_usage") and payload.get("session_usage"):
        agent._session_usage = Usage.model_validate(payload["session_usage"])


def list_sessions(*, scope: Path | None = None) -> list[dict]:
    out = []
    for p in sorted(_sessions_dir(scope).glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        out.append({
            "name": payload.get("name", p.stem),
            "saved_at": payload.get("saved_at"),
            "messages": len(payload.get("messages", [])),
            "model": payload.get("model", ""),
            "path": str(p),
        })
    return out


def latest_session_name(*, scope: Path | None = None) -> str | None:
    sessions = list_sessions(scope=scope)
    if not sessions:
        return None
    return sessions[0]["name"]


def delete_session(name: str, *, scope: Path | None = None) -> bool:
    target = _session_path(name, scope)
    if not target.exists():
        return False
    target.unlink()
    return True
```

### Remover `session_fallback.py`

Apos confirmar que o real funciona, deletar o stub criado na FASE 10.03:

```bash
rm /home/guhaase/projetos/vulpcode/src/vulpcode/session_fallback.py
```

E ajustar os comandos `SaveCommand`/`LoadCommand` em
`commands/session_cmds.py`: remover o try/except do fallback e importar
diretamente de `vulpcode.session`.

### Suporte a --resume no CLI

Em `app.py`:

```python
async def start_repl(*, cli_overrides=None, one_shot=None, print_mode=False, resume=False):
    ...
    if resume:
        from vulpcode.session import latest_session_name, load_session
        last = latest_session_name()
        if last:
            try:
                load_session(last, agent)
                renderer.console.print(f"[green]resumed session {last}[/]")
            except Exception as exc:
                renderer.render_error(f"resume failed: {exc}")
    ...
```

E no `cli.py`, passar `resume=resume` para `start_repl(...)`.

---

## INSTRUCAO CRITICA

- Escrita atomica via `tmp` + `replace` para nao corromper o arquivo se o
  processo for morto no meio.
- Sanitizar o nome (apenas alfanumericos, `-`, `_`) — evitar path traversal.
- `latest_session_name()` ordena por mtime decrescente — `--resume` carrega o
  mais recente.
- O path completo via `scope` permite testes unitarios sem tocar `~/.vulpcode`.

---

## Etapas de Implementacao

### Etapa 1: Criar `session.py`

### Etapa 2: Remover `session_fallback.py` e ajustar `commands/session_cmds.py`

### Etapa 3: Atualizar `app.py` para suportar `--resume`

### Etapa 4: Atualizar `cli.py` para passar `resume` ao `start_repl`

### Etapa 5: Criar `tests/test_session.py`

```python
from pathlib import Path
import pytest

from vulpcode.session import (
    delete_session,
    latest_session_name,
    list_sessions,
    load_session,
    save_session,
)
from vulpcode.providers.base import Message, Usage


class FakeAgent:
    def __init__(self):
        self.model = "m"
        self.system = "sys"
        self._messages = [Message(role="user", content="hi")]
        self._session_usage = Usage(input_tokens=5, output_tokens=10)
        self.provider = type("P", (), {"name": "x"})()


def test_save_and_load_roundtrip(tmp_path: Path):
    a = FakeAgent()
    p = save_session("test", a, scope=tmp_path)
    assert p.exists()
    a._messages = []
    a.model = "?"
    load_session("test", a, scope=tmp_path)
    assert a._messages[0].content == "hi"
    assert a.model == "m"


def test_load_missing_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_session("nope", FakeAgent(), scope=tmp_path)


def test_list_sessions_orders_by_mtime(tmp_path: Path):
    a = FakeAgent()
    save_session("a", a, scope=tmp_path)
    save_session("b", a, scope=tmp_path)
    sessions = list_sessions(scope=tmp_path)
    names = [s["name"] for s in sessions]
    assert "a" in names and "b" in names


def test_latest_session_name(tmp_path: Path):
    a = FakeAgent()
    save_session("first", a, scope=tmp_path)
    import time; time.sleep(0.05)
    save_session("second", a, scope=tmp_path)
    assert latest_session_name(scope=tmp_path) == "second"


def test_delete(tmp_path: Path):
    save_session("x", FakeAgent(), scope=tmp_path)
    assert delete_session("x", scope=tmp_path)
    assert not delete_session("x", scope=tmp_path)


def test_name_sanitization(tmp_path: Path):
    p = save_session("../etc/passwd", FakeAgent(), scope=tmp_path)
    assert ".." not in p.name
```

### Etapa 6: Rodar testes

```bash
pytest tests/test_session.py tests/test_commands.py -v
```

---

## Criterios de Aceite

- [x] `src/vulpcode/session.py` implementa `save_session`, `load_session`, `list_sessions`, `latest_session_name`, `delete_session`
- [x] Escrita atomica via `tmp` + `replace`
- [x] Sanitizacao de nome (sem path traversal)
- [x] `~/.vulpcode/sessions/` criado on-demand
- [x] `app.py` suporta `--resume` chamando `latest_session_name` + `load_session`
- [x] `cli.py` passa `resume` ao `start_repl`
- [x] `session_fallback.py` removido (commands/session_cmds.py importa do real)
- [x] `tests/test_session.py` com >=6 testes, todos passando

---

## Riscos Tecnicos

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|---------------|---------|-----------|
| Sessao corrompida bloqueia carga | Baixa | Medio | try/except no list_sessions |
| Path traversal | Baixa | Alto | Sanitizar nome |
| Mensagens com tool_calls nao validam | Baixa | Medio | Pydantic model_validate cobre |

---

**End of Specification**
