#!/bin/bash

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Script para executar o plano TOOLS (provider agentico + write tools)
# do Vulpcode. Itera tarefa por tarefa, marcando checkboxes ate zero.
# Modelo: dev/prompt.sh (mesma logica, escopo restrito a dev/TOOLS).
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# --- CONFIGURACOES ---
# TARGET_TIME: deixe vazio para iniciar imediatamente.
# Defina (ex: "00:01") se quiser agendar o inicio para um horario noturno.
TARGET_TIME=""
MAX_ITERATIONS=50

# --- DIRETORIO BASE ---
TOOLS_DIR="/home/guhaase/projetos/vulpcode/dev/TOOLS"
PROJECT_ROOT="/home/guhaase/projetos/vulpcode"
SPEC_FILE="${TOOLS_DIR}/00_OVERVIEW.md"

# --- DIRETORIO DE LOG ---
LOG_DIR="${TOOLS_DIR}/LOG"
mkdir -p "$LOG_DIR"

# Log principal com timestamp no nome
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
MAIN_LOG="${LOG_DIR}/tools_plan_${TIMESTAMP}.log"
LATEST_LOG="${LOG_DIR}/latest.log"

ln -sf "$MAIN_LOG" "$LATEST_LOG"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ARQUIVOS DE TAREFAS (ordem topologica respeitando dependencias)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TASK_FILES=(
    # FASE 01 - Protocolo
    "${TOOLS_DIR}/FASE_01_PROTOCOLO/01_PROTOCOLO_PARSER.md"

    # FASE 02 - Provider agentico
    "${TOOLS_DIR}/FASE_02_PROVIDER/01_PROVIDER_AGENTIC.md"

    # FASE 03 - Base de validacao
    "${TOOLS_DIR}/FASE_03_VALIDATION_BASE/01_VALIDATED_WRITE_TOOL.md"

    # FASE 04 - Write tools especializadas
    "${TOOLS_DIR}/FASE_04_WRITE_TOOLS/01_TOOL_PY_IPYNB.md"
    "${TOOLS_DIR}/FASE_04_WRITE_TOOLS/02_TOOL_DOCS.md"
    "${TOOLS_DIR}/FASE_04_WRITE_TOOLS/03_TOOL_DATA.md"
    "${TOOLS_DIR}/FASE_04_WRITE_TOOLS/04_TOOL_WEB_SHELL.md"

    # FASE 05 - System prompt + loop de reparo
    "${TOOLS_DIR}/FASE_05_SYSTEM_PROMPT/01_SYSTEM_PROMPT_REPAIR.md"

    # FASE 06 - Testes
    "${TOOLS_DIR}/FASE_06_TESTES/01_TESTES_INTEGRADOS.md"

    # FASE 07 - Documentacao
    "${TOOLS_DIR}/FASE_07_DOCS/01_DOCS_E_CHANGELOG.md"
)

# Cores para output no terminal
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FUNCOES DE LOG
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo -e "$msg" | tee -a "$MAIN_LOG"
}

log_file() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$MAIN_LOG"
}

log_separator() {
    local sep="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "$sep" | tee -a "$MAIN_LOG"
}

update_status() {
    local status_file="${LOG_DIR}/status.txt"
    cat > "$status_file" <<EOF
=== STATUS DA EXECUCAO - VULPCODE TOOLS ===
Atualizado em: $(date '+%Y-%m-%d %H:%M:%S')
Tarefa atual:  $1
Arquivo:       $2
Iteracao:      $3
Pendentes:     $4
Completos:     $5
Estado:        $6
Log completo:  $MAIN_LOG
===========================
EOF
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FUNCAO DE AGENDAMENTO (so se TARGET_TIME estiver setado)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if [ -n "$TARGET_TIME" ]; then
    log "Verificando horario de inicio programado para: ${TARGET_TIME}..."

    CURRENT_EPOCH=$(date +%s)
    TARGET_EPOCH=$(date -d "$TARGET_TIME" +%s)

    if [ "$TARGET_EPOCH" -lt "$CURRENT_EPOCH" ]; then
        TARGET_EPOCH=$(date -d "tomorrow $TARGET_TIME" +%s)
    fi

    SLEEP_SECONDS=$((TARGET_EPOCH - CURRENT_EPOCH))

    if [ "$SLEEP_SECONDS" -gt 0 ]; then
        HOURS=$((SLEEP_SECONDS / 3600))
        MINS=$(((SLEEP_SECONDS % 3600) / 60))
        log "Entrando em modo sleep. O script iniciara em ${HOURS}h ${MINS}m."
        echo -e "${GREEN}Pressione ENTER para iniciar imediatamente!${NC}"
        echo -e "${BLUE}Ou pressione Ctrl+C para cancelar o agendamento.${NC}"

        ELAPSED=0
        while [ $ELAPSED -lt $SLEEP_SECONDS ]; do
            read -t 1 -n 1 && break
            ELAPSED=$((ELAPSED + 1))
        done
    fi
    log "Horario atingido! Iniciando rotinas..."
else
    log "TARGET_TIME vazio - iniciando imediatamente."
fi

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FUNCOES AUXILIARES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

count_pending_checkboxes() {
    local file="$1"
    local count=$(grep -c "^- \[ \]" "$file" 2>/dev/null || true)
    echo "${count:-0}"
}

count_completed_checkboxes() {
    local file="$1"
    local count=$(grep -c "^- \[x\]" "$file" 2>/dev/null || true)
    echo "${count:-0}"
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GERADOR DE PROMPT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

build_prompt() {
    local task_file="$1"
    local iteration="$2"
    local task_relpath="${task_file#${TOOLS_DIR}/}"

    cat <<PROMPT_EOF
You are extending **Vulpcode**, the Python multi-provider CLI coding agent. This task is
part of the **TOOLS plan** — adding a new agentic provider (\`internal-llm-agentic\`) and a
family of file-creation tools with built-in validation and an auto-repair loop. The plan
overview is in \`${SPEC_FILE}\`.

## Project Context

- **Project root**: \`${PROJECT_ROOT}/\`
- **Source code goes in**: \`${PROJECT_ROOT}/src/vulpcode/\`
- **Tests go in**: \`${PROJECT_ROOT}/tests/\`
- **Plan overview**: \`${SPEC_FILE}\` (skim relevant sections first)
- **Phase directory**: \`${TOOLS_DIR}/\`
- **This task file**: \`${task_file}\`

## Architecture recap

\`\`\`
src/vulpcode/
    providers/
        base.py                 # Provider ABC + Message/StreamChunk
        registry.py
        internal_llm.py         # existing — DO NOT modify
        internal_llm_agentic.py # NEW (FASE_02)
        _text_tool_protocol.py  # NEW (FASE_01) — parser standalone
    tools/
        base.py                 # Tool ABC + @tool decorator
        _validated_write.py     # NEW (FASE_03) — base for Write* family
        write_py.py             # NEW (FASE_04)
        write_ipynb.py          # NEW (FASE_04)
        write_md.py             # NEW (FASE_04)
        write_docx.py           # NEW (FASE_04)
        write_pdf.py            # NEW (FASE_04)
        write_json.py           # NEW (FASE_04)
        write_yaml.py           # NEW (FASE_04)
        write_toml.py           # NEW (FASE_04)
        write_csv.py            # NEW (FASE_04)
        write_xml.py            # NEW (FASE_04)
        write_html.py           # NEW (FASE_04)
        write_sh.py             # NEW (FASE_04)
        write_sql.py            # NEW (FASE_04)
        write_svg.py            # NEW (FASE_04)
        write_dot.py            # NEW (FASE_04)
    agent.py                    # existing — only \`max_iters\` opt-in tweak (FASE_05)
\`\`\`

## Development Conventions

- **Python**: 3.11+. \`from __future__ import annotations\` only when needed.
- **Type hints**: required on public functions. Modern syntax (\`str | None\`, \`list[X]\`).
- **Async**: \`asyncio\`. Provider streams are \`AsyncIterator\`.
- **Pydantic v2** for tool input validation.
- **Formatting**: 4-space indent, \`ruff\` defaults (line length 100).
- **Language**: code, docstrings, identifiers in **English**. Task spec files in Portuguese.
- **No emojis** in code or commit messages.
- **NEVER modify** \`src/vulpcode/providers/internal_llm.py\` — the existing chat-only
  provider must keep working as fallback.
- **NEVER modify** the agent loop in \`src/vulpcode/agent.py\` except for the explicit
  \`max_iters\` parameter addition in FASE_05.
- **Optional dependencies are lazy**: import inside \`validate\`/\`transform\`, not at
  module top. If missing, raise \`ValidationError\` with a clear pip-install hint.

## Your Task

1. Read \`${SPEC_FILE}\` (skim sections relevant to this task).
2. Read the task specification below carefully — it contains objective, design notes,
   implementation steps and acceptance criteria.
3. Read any existing source files referenced in the spec before changing them.
4. Follow the implementation steps in order.
5. **CRITICAL**: After completing each acceptance criterion, mark its checkbox:
   change \`- [ ]\` to \`- [x]\` in: \`${task_file}\`
6. Skip items already marked \`[x]\`.
7. Continue until ALL checkboxes in this task file are \`[x]\`.

## Important Notes

- Use absolute paths when creating files.
- Create any missing \`__init__.py\` files and parent directories.
- Do NOT delete existing files or modify passing tests from previous tasks.
- Run \`pytest <test_file> -v\` after writing each new test file to verify it passes.
- If a test fails, read the source code, fix the test or the code, and re-run.
- Use \`pytest.importorskip("X")\` for optional dependencies.
- For HTTP-related tests (FASE_02, FASE_06) use \`respx\` to mock httpx — never hit a real
  endpoint.
- This is iteration #${iteration} for this task. Focus on uncompleted items (unmarked
  checkboxes).

## Task Specification: ${task_relpath}

---
$(cat "$task_file")
---

REMEMBER: Mark each checkbox (\`- [ ]\` -> \`- [x]\`) in \`${task_file}\` as you complete
each criterion.
PROMPT_EOF
}

show_progress() {
    local pending=$1
    local completed=$2
    local task_name=$3
    local total=$((pending + completed))
    local percentage=0
    if [ $total -gt 0 ]; then
        percentage=$((completed * 100 / total))
    fi

    log_separator
    log "PROGRESSO ${task_name}"
    log "  Completos:  ${completed}"
    log "  Pendentes:  ${pending}"
    log "  Total:      ${total}"
    log "  Progresso:  ${percentage}%"
    log_separator
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# VERIFICACAO DE PRE-REQUISITOS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

log "============================================"
log "LOG DE EXECUCAO INICIADO"
log "Modulo: VULPCODE TOOLS - Provider agentico + Write* tools"
log "Arquivo de log: $MAIN_LOG"
log "Para acompanhar em tempo real:"
log "  tail -f $LATEST_LOG"
log "Para ver status rapido:"
log "  cat ${LOG_DIR}/status.txt"
log "============================================"

# Verificar se Claude CLI esta disponivel
if ! command -v claude &> /dev/null; then
    log "ERRO: Claude CLI nao encontrado. Instale com: npm install -g @anthropic-ai/claude-code"
    exit 1
fi

# Verificar se a especificacao do projeto existe
if [ ! -f "$SPEC_FILE" ]; then
    log "ERRO: Especificacao do projeto nao encontrada em $SPEC_FILE"
    exit 1
fi

# Verificar se todos os arquivos de tarefa existem
log "Verificando arquivos de tarefa..."
for TASK_FILE in "${TASK_FILES[@]}"; do
    if [ ! -f "$TASK_FILE" ]; then
        log "ERRO: Arquivo $TASK_FILE nao encontrado!"
        exit 1
    fi
    log_file "  OK: ${TASK_FILE#${TOOLS_DIR}/}"
done

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# INICIO DA EXECUCAO
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TOTAL_TASKS=${#TASK_FILES[@]}
EXEC_START_TIME=$(date '+%Y-%m-%d %H:%M:%S')
log "Iniciando execucao automatica de ${TOTAL_TASKS} tarefas"
log "Inicio: ${EXEC_START_TIME}"

# Loop externo: para cada tarefa
for TASK_INDEX in "${!TASK_FILES[@]}"; do
    TASK_FILE="${TASK_FILES[$TASK_INDEX]}"
    TASK_NUM=$((TASK_INDEX + 1))
    TASK_NAME="TAREFA ${TASK_NUM}/${TOTAL_TASKS}"
    TASK_RELPATH="${TASK_FILE#${TOOLS_DIR}/}"
    TASK_BASENAME=$(basename "$TASK_FILE" .md)

    log ""
    log "======================================================"
    log "INICIANDO ${TASK_NAME} - ${TASK_RELPATH}"
    log "Arquivo: ${TASK_FILE}"
    log "======================================================"

    TASK_LOG="${LOG_DIR}/tools_step${TASK_NUM}_${TASK_BASENAME}_${TIMESTAMP}.log"
    log "Log desta tarefa: ${TASK_LOG}"

    TASK_START_TIME=$(date '+%Y-%m-%d %H:%M:%S')
    ITERATION=0

    while [ $ITERATION -lt $MAX_ITERATIONS ]; do
        ITERATION=$((ITERATION + 1))
        PENDING=$(count_pending_checkboxes "$TASK_FILE")
        COMPLETED=$(count_completed_checkboxes "$TASK_FILE")

        show_progress "$PENDING" "$COMPLETED" "$TASK_NAME"
        update_status "$TASK_NAME" "$TASK_RELPATH" "$ITERATION" "$PENDING" "$COMPLETED" "EXECUTANDO"

        if [ "$PENDING" -eq 0 ]; then
            TASK_END_TIME=$(date '+%Y-%m-%d %H:%M:%S')
            log "SUCESSO! ${TASK_NAME} concluida!"
            log "  Inicio: ${TASK_START_TIME}"
            log "  Fim:    ${TASK_END_TIME}"
            update_status "$TASK_NAME" "$TASK_RELPATH" "$ITERATION" "0" "$COMPLETED" "CONCLUIDA"
            break
        fi

        CLAUDE_START=$(date '+%Y-%m-%d %H:%M:%S')
        CLAUDE_START_EPOCH=$(date +%s)
        log "[CLAUDE] Iniciando chamada #${ITERATION} - ${TASK_NAME} (pendentes: ${PENDING})"
        log "[CLAUDE] Inicio da chamada: ${CLAUDE_START}"

        CLAUDE_RAW="${LOG_DIR}/claude_raw_step${TASK_NUM}_iter${ITERATION}.jsonl"
        CLAUDE_READABLE="${LOG_DIR}/claude_readable_step${TASK_NUM}_iter${ITERATION}.log"
        > "$CLAUDE_RAW"
        > "$CLAUDE_READABLE"

        ln -sf "$CLAUDE_RAW" "${LOG_DIR}/claude_current_raw.jsonl"
        ln -sf "$CLAUDE_READABLE" "${LOG_DIR}/claude_current.log"

        update_status "$TASK_NAME" "$TASK_RELPATH" "$ITERATION" "$PENDING" "$COMPLETED" \
            "CLAUDE EXECUTANDO (inicio: ${CLAUDE_START}) -- tail -f ${LOG_DIR}/claude_current.log"

        log "[CLAUDE] Modo: prompt completo (spec + instrucoes) - iteracao ${ITERATION} (stream-json)"
        build_prompt "$TASK_FILE" "$ITERATION" | claude -p --model claude-sonnet-4-6 --dangerously-skip-permissions --verbose --output-format stream-json > "$CLAUDE_RAW" 2>&1 &
        CLAUDE_PID=$!

        # Processar stream JSONL em background -> log legivel
        (
            tail -f "$CLAUDE_RAW" --pid=$CLAUDE_PID 2>/dev/null | while IFS= read -r line; do
                TYPE=$(echo "$line" | grep -oP '"type"\s*:\s*"\K[^"]+' | head -1)

                case "$TYPE" in
                    assistant)
                        TEXT=$(echo "$line" | grep -oP '"content"\s*:\s*"\K[^"]*' | head -1)
                        if [ -n "$TEXT" ]; then
                            echo "[$(date '+%H:%M:%S')] [TEXTO] ${TEXT:0:300}" >> "$CLAUDE_READABLE"
                        fi
                        ;;
                    content_block_start)
                        TOOL=$(echo "$line" | grep -oP '"name"\s*:\s*"\K[^"]+' | head -1)
                        if [ -n "$TOOL" ]; then
                            echo "[$(date '+%H:%M:%S')] [TOOL START] $TOOL" >> "$CLAUDE_READABLE"
                        fi
                        ;;
                    content_block_delta)
                        TEXT=$(echo "$line" | grep -oP '"text"\s*:\s*"\K[^"]*' | head -1)
                        if [ -n "$TEXT" ] && [ ${#TEXT} -gt 2 ]; then
                            echo "[$(date '+%H:%M:%S')] [DELTA] ${TEXT:0:200}" >> "$CLAUDE_READABLE"
                        fi
                        ;;
                    result)
                        echo "[$(date '+%H:%M:%S')] [RESULTADO FINAL]" >> "$CLAUDE_READABLE"
                        ;;
                esac
            done
        ) &
        PARSER_PID=$!

        # Monitor: atualiza status a cada 15s enquanto claude roda
        LAST_RAW_SIZE=0
        while kill -0 $CLAUDE_PID 2>/dev/null; do
            RAW_SIZE=$(wc -c < "$CLAUDE_RAW" 2>/dev/null || echo 0)
            RAW_LINES=$(wc -l < "$CLAUDE_RAW" 2>/dev/null || echo 0)
            NOW_EPOCH=$(date +%s)
            ELAPSED_SECS=$((NOW_EPOCH - CLAUDE_START_EPOCH))
            ELAPSED_MIN=$((ELAPSED_SECS / 60))
            ELAPSED_SEC=$((ELAPSED_SECS % 60))

            LIVE_PENDING=$(count_pending_checkboxes "$TASK_FILE")
            LIVE_COMPLETED=$(count_completed_checkboxes "$TASK_FILE")
            LIVE_DONE=$((LIVE_COMPLETED - COMPLETED))

            if [ "$RAW_SIZE" -gt "$LAST_RAW_SIZE" ]; then
                ACTIVITY="ativo (stream crescendo)"
            else
                ACTIVITY="aguardando resposta API"
            fi
            LAST_RAW_SIZE=$RAW_SIZE

            update_status "$TASK_NAME" "$TASK_RELPATH" "$ITERATION" "$LIVE_PENDING" "$LIVE_COMPLETED" \
                "CLAUDE EXECUTANDO | ${ELAPSED_MIN}m${ELAPSED_SEC}s | ${RAW_LINES} eventos | ${ACTIVITY} | +${LIVE_DONE} checkboxes"

            log_file "[MONITOR] ${TASK_NAME} iter#${ITERATION} | ${ELAPSED_MIN}m${ELAPSED_SEC}s | ${RAW_LINES} eventos | ${RAW_SIZE} bytes | ${ACTIVITY} | checkboxes: ${LIVE_COMPLETED}/${LIVE_PENDING}"

            sleep 15
        done

        wait $CLAUDE_PID
        CLAUDE_EXIT_CODE=$?

        sleep 2
        kill $PARSER_PID 2>/dev/null
        wait $PARSER_PID 2>/dev/null

        CLAUDE_END=$(date '+%Y-%m-%d %H:%M:%S')
        FINAL_RAW_LINES=$(wc -l < "$CLAUDE_RAW" 2>/dev/null || echo 0)
        FINAL_RAW_SIZE=$(wc -c < "$CLAUDE_RAW" 2>/dev/null || echo 0)
        log "[CLAUDE] Fim da chamada: ${CLAUDE_END} (exit: ${CLAUDE_EXIT_CODE}, ${FINAL_RAW_LINES} eventos JSONL, ${FINAL_RAW_SIZE} bytes)"

        echo "--- CLAUDE READABLE: ${TASK_NAME} iter#${ITERATION} [${CLAUDE_START} -> ${CLAUDE_END}] ---" >> "$TASK_LOG"
        cat "$CLAUDE_READABLE" >> "$TASK_LOG"
        echo "--- END ---" >> "$TASK_LOG"

        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [CLAUDE READABLE ${TASK_NAME} iter#${ITERATION}]" >> "$MAIN_LOG"
        cat "$CLAUDE_READABLE" >> "$MAIN_LOG"

        if [ $CLAUDE_EXIT_CODE -ne 0 ]; then
            log "[ERRO] Claude retornou codigo ${CLAUDE_EXIT_CODE}. Tentando novamente em 2s..."
            update_status "$TASK_NAME" "$TASK_RELPATH" "$ITERATION" "$PENDING" "$COMPLETED" "ERRO (code ${CLAUDE_EXIT_CODE}) - retentativa em 2s"
            sleep 2
            continue
        fi

        # Verificar progresso
        NEW_PENDING=$(count_pending_checkboxes "$TASK_FILE")
        NEW_COMPLETED=$(count_completed_checkboxes "$TASK_FILE")
        CHECKBOXES_RESOLVIDOS=$((NEW_COMPLETED - COMPLETED))

        log "[PROGRESSO] Antes: ${COMPLETED} completos, ${PENDING} pendentes"
        log "[PROGRESSO] Depois: ${NEW_COMPLETED} completos, ${NEW_PENDING} pendentes"
        log "[PROGRESSO] Checkboxes resolvidos nesta iteracao: ${CHECKBOXES_RESOLVIDOS}"

        if [ "$NEW_PENDING" -eq "$PENDING" ]; then
            log "[ALERTA] Nenhum checkbox foi resolvido nesta iteracao!"
        fi

        sleep 3
    done

    if [ "$PENDING" -ne 0 ]; then
        log "LIMITE DE ITERACOES ATINGIDO para ${TASK_NAME}!"
        update_status "$TASK_NAME" "$TASK_RELPATH" "$ITERATION" "$PENDING" "$COMPLETED" "FALHA - limite de iteracoes"
        exit 1
    fi
done

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# VERIFICACAO FINAL
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EXEC_END_TIME=$(date '+%Y-%m-%d %H:%M:%S')
log ""
log "======================================================"
log "TODAS AS TAREFAS DO PLANO TOOLS CONCLUIDAS!"
log "Inicio: ${EXEC_START_TIME}"
log "Fim:    ${EXEC_END_TIME}"
log "======================================================"
log ""
log "Sugestoes de verificacao final:"
log "  pip install -e '${PROJECT_ROOT}[docs-tools,dev]'"
log "  pytest ${PROJECT_ROOT}/tests/ -v"
log "  vulp providers | grep internal-llm-agentic"

update_status "TODAS" "N/A" "N/A" "0" "N/A" "CONCLUIDO - ${EXEC_END_TIME}"
exit 0
