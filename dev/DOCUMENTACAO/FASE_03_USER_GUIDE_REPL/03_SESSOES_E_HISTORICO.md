# Tarefa 03.03 - Sessoes e Historico

**Status**: PENDENTE
**Fase**: 03 - User Guide
**Dependencias**: 03.02
**Bloqueia**: nada (ultima da fase 03)

---

## Objetivo

Criar `user-guide/sessions.md` explicando: persistencia de sessao em
`~/.vulpcode/sessions/`, `/save`, `/load`, `--resume`, `/compact`, e o historico
do `prompt_toolkit` em `~/.vulpcode/history`.

---

## Arquivos a criar

- `docs/user-guide/sessions.md`

---

## Source de verdade

- `src/vulpcode/session.py` — `save_session`, `load_session`, `list_sessions`,
  `latest_session_name`, `delete_session`
- `src/vulpcode/commands/session_cmds.py` — `SaveCommand`, `LoadCommand`
- `src/vulpcode/commands/compact.py` — `/compact`
- `src/vulpcode/app.py` — `--resume` flow
- `src/vulpcode/ui/repl.py` — historico do prompt

---

## Estrutura sugerida

### 1. Dois historicos diferentes

Importante distinguir:

- **Historico de comandos do REPL** (linhas que voce digitou): `~/.vulpcode/history`,
  gerenciado pelo `prompt_toolkit`. Setas ↑/↓ navegam.
- **Historico da conversa com o LLM** (mensagens do agente): `Agent._messages`
  em memoria, persistivel via `/save`.

### 2. Salvar e carregar sessao

```
> /save trabalho-backup
saved session to /home/.../.vulpcode/sessions/trabalho-backup.json
> /clear
> /load trabalho-backup
loaded session trabalho-backup
```

Formato JSON em `~/.vulpcode/sessions/<name>.json`:

```json
{
  "version": 1,
  "name": "trabalho-backup",
  "saved_at": "2026-05-06T15:00:00",
  "provider_name": "anthropic",
  "model": "claude-sonnet-4-6",
  "system": "...",
  "messages": [...],
  "session_usage": {"input_tokens": 1234, "output_tokens": 567, ...}
}
```

### 3. `--resume`

```bash
vulp --resume
# resumed session trabalho-backup
```

Carrega a sessao **mais recente** (por `mtime`). Util para continuar logo
depois de fechar o terminal.

### 4. Listar e excluir

API publica do `vulpcode.session`:

- `list_sessions()` retorna lista de dicts com `name`, `saved_at`, `messages`,
  `model`, `path`
- `delete_session(name)` remove o arquivo

CLI ainda nao tem `vulp sessions list` — programaticamente:

```python
from vulpcode.session import list_sessions
for s in list_sessions():
    print(s["name"], s["saved_at"], s["messages"])
```

### 5. `/compact`

Sumariza o historico atual usando o proprio LLM, substitui por uma versao
condensada. Util quando o turno fica longo e o contexto comeca a ficar caro.

```
> /compact
requesting summary...
history compacted
(Resumo gerado pelo modelo)
```

Aviso: detalhes podem ser perdidos. Salve antes (`/save`) se for delicado.

### 6. Boas praticas

- Salvar antes de `/compact` ou `/clear`.
- Nomes sem caracteres especiais (sao sanitizados — apenas alfanumerico, `-`, `_`).
- Nao commitar `~/.vulpcode/sessions/` (ja no `.gitignore`).
- Para auditoria: as sessoes contem o que foi conversado, util para rastreio
  posterior.

---

## INSTRUCAO CRITICA

- Confirmar que o formato JSON da sessao bate com `save_session()` em
  `src/vulpcode/session.py`. Versao atual e `_VERSION = 1`.
- Mencionar a sanitizacao de nomes (apenas alfanumerico/-/_) — vem da funcao
  `_session_path()`.

---

## Etapas de Implementacao

### Etapa 1: Ler `src/vulpcode/session.py` e `commands/session_cmds.py`
### Etapa 2: Criar `user-guide/sessions.md`
### Etapa 3: `mkdocs build`

---

## Criterios de Aceite

- [x] `docs/user-guide/sessions.md` criado
- [x] Distincao clara entre historico do prompt e historico do agente
- [x] `/save`, `/load`, `--resume`, `/compact` documentados com exemplos
- [x] Formato JSON da sessao mostrado e bate com source
- [x] API publica de `vulpcode.session` mencionada (list/delete)
- [x] Boas praticas (salvar antes de compact, nao commitar)
- [x] `mkdocs build` continua passando

---

## Riscos

| Risco | Mitigacao |
|-------|-----------|
| Formato JSON da sessao mudou | Reler session.py |
| `_VERSION` foi bumpado | Atualizar exemplo |

---

**End of Specification**
