#!/bin/bash

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Script para executar TAREFAS do Plano de Desenvolvimento do Vulpcode
# Objetivo: Construir a CLI agentica multi-provedor inteiramente via Claude
# Execucao automatizada via Claude CLI
# COM LOGGING COMPLETO para acompanhamento em tempo real
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# --- CONFIGURACOES ---
TARGET_TIME="00:01"
MAX_ITERATIONS=50

# --- DIRETORIO BASE ---
DEV_DIR="/home/guhaase/projetos/vulpcode/dev"
PROJECT_ROOT="/home/guhaase/projetos/vulpcode"
SPEC_FILE="${DEV_DIR}/00_OVERVIEW.md"

# --- DIRETORIO DE LOG ---
LOG_DIR="${DEV_DIR}/LOG"
mkdir -p "$LOG_DIR"

# Log principal com timestamp no nome
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
MAIN_LOG="${LOG_DIR}/vulpcode_plan_${TIMESTAMP}.log"
LATEST_LOG="${LOG_DIR}/latest.log"

# Criar link simbolico para o log mais recente
ln -sf "$MAIN_LOG" "$LATEST_LOG"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ARQUIVOS DE TAREFAS (ordem topologica respeitando dependencias)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TASK_FILES=(
    # FASE 01 - Bootstrap
    "${DEV_DIR}/FASE_01_BOOTSTRAP/01_ESTRUTURA_PACOTE.md"
    "${DEV_DIR}/FASE_01_BOOTSTRAP/02_PYPROJECT.md"
    "${DEV_DIR}/FASE_01_BOOTSTRAP/03_CLI_SKELETON.md"

    # FASE 02 - Nucleo (tipos, ABCs)
    "${DEV_DIR}/FASE_02_NUCLEO/01_PROVIDER_ABC.md"
    "${DEV_DIR}/FASE_02_NUCLEO/02_TOOL_ABC.md"

    # FASE 03 - Providers
    "${DEV_DIR}/FASE_03_PROVIDERS/01_ANTHROPIC.md"
    "${DEV_DIR}/FASE_03_PROVIDERS/02_OPENAI.md"
    "${DEV_DIR}/FASE_03_PROVIDERS/03_GEMINI.md"
    "${DEV_DIR}/FASE_03_PROVIDERS/04_OLLAMA.md"
    "${DEV_DIR}/FASE_03_PROVIDERS/05_REGISTRY.md"

    # FASE 04 - Tools Filesystem
    "${DEV_DIR}/FASE_04_TOOLS_FILESYSTEM/01_READ.md"
    "${DEV_DIR}/FASE_04_TOOLS_FILESYSTEM/02_WRITE.md"
    "${DEV_DIR}/FASE_04_TOOLS_FILESYSTEM/03_EDIT_E_MULTIEDIT.md"
    "${DEV_DIR}/FASE_04_TOOLS_FILESYSTEM/04_GLOB.md"

    # FASE 05 - Tools Busca + Shell
    "${DEV_DIR}/FASE_05_TOOLS_BUSCA_SHELL/01_GREP.md"
    "${DEV_DIR}/FASE_05_TOOLS_BUSCA_SHELL/02_BASH.md"
    "${DEV_DIR}/FASE_05_TOOLS_BUSCA_SHELL/03_BASH_BACKGROUND.md"

    # FASE 06 - Tools Web + Agente
    "${DEV_DIR}/FASE_06_TOOLS_WEB_AGENTE/01_WEB.md"
    "${DEV_DIR}/FASE_06_TOOLS_WEB_AGENTE/02_TODOWRITE.md"
    "${DEV_DIR}/FASE_06_TOOLS_WEB_AGENTE/03_TASK_SUBAGENT.md"
    "${DEV_DIR}/FASE_06_TOOLS_WEB_AGENTE/04_NOTEBOOK_EDIT.md"

    # FASE 07 - Config + Permissoes
    "${DEV_DIR}/FASE_07_CONFIG_PERMISSOES/01_CONFIG.md"
    "${DEV_DIR}/FASE_07_CONFIG_PERMISSOES/02_PERMISSIONS.md"

    # FASE 08 - Agent Loop
    "${DEV_DIR}/FASE_08_AGENT_LOOP/01_AGENT.md"

    # FASE 09 - UI
    "${DEV_DIR}/FASE_09_UI/01_THEME_RENDER.md"
    "${DEV_DIR}/FASE_09_UI/02_STREAMING.md"
    "${DEV_DIR}/FASE_09_UI/03_REPL.md"

    # FASE 10 - Slash Commands
    "${DEV_DIR}/FASE_10_SLASH_COMMANDS/01_BASIC.md"
    "${DEV_DIR}/FASE_10_SLASH_COMMANDS/02_PROVIDER_MODEL.md"
    "${DEV_DIR}/FASE_10_SLASH_COMMANDS/03_SESSION_MCP.md"

    # FASE 11 - MCP
    "${DEV_DIR}/FASE_11_MCP/01_MCP_CLIENT.md"
    "${DEV_DIR}/FASE_11_MCP/02_MCP_LOADER.md"

    # FASE 12 - Session
    "${DEV_DIR}/FASE_12_SESSION/01_SESSION.md"

    # FASE 13 - Testes
    "${DEV_DIR}/FASE_13_TESTES/01_TEST_PROVIDERS.md"
    "${DEV_DIR}/FASE_13_TESTES/02_TEST_TOOLS.md"
    "${DEV_DIR}/FASE_13_TESTES/03_TEST_AGENT_CLI.md"

    # FASE 14 - Build + Smoke
    "${DEV_DIR}/FASE_14_BUILD_SMOKE/01_BUILD_E_SMOKE.md"
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
=== STATUS DA EXECUCAO - VULPCODE ===
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
# FUNCAO DE AGENDAMENTO
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
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
    local task_relpath="${task_file#${DEV_DIR}/}"

    cat <<PROMPT_EOF
You are building **Vulpcode**, a Python CLI coding agent inspired by Claude Code, multi-provider
(Anthropic, OpenAI, Gemini, Ollama, etc.). The full specification is in \`${SPEC_FILE}\`.

## Project Context

- **Project root**: \`${PROJECT_ROOT}/\`
- **Source code goes in**: \`${PROJECT_ROOT}/src/vulpcode/\`
- **Tests go in**: \`${PROJECT_ROOT}/tests/\`
- **Specification**: \`${SPEC_FILE}\` (read it once at the start of each task to refresh context)
- **Development plan**: \`${DEV_DIR}/\`
- **This task file**: \`${task_file}\`

## Architecture (high level)

\`\`\`
src/vulpcode/
    cli.py            # Typer entry point
    app.py            # REPL orchestration
    agent.py          # LLM <-> tools loop
    config.py         # ~/.vulpcode/config.toml loader
    session.py        # History persistence
    permissions.py    # Confirmation flow

    providers/        # Provider adapters (Anthropic, OpenAI, Gemini, Ollama)
        base.py       # Provider ABC + Message/StreamChunk types
        registry.py
        anthropic.py
        openai.py     # also covers DeepSeek/Groq/OpenRouter via base_url
        gemini.py
        ollama.py

    tools/            # Native tools (Bash, Read, Write, Edit, etc.)
        base.py       # Tool ABC + @tool decorator + registry

    mcp/              # Model Context Protocol client
    ui/               # Rich + prompt_toolkit
    commands/         # Slash commands
\`\`\`

## Development Conventions

- **Python**: 3.11+ only. Use \`from __future__ import annotations\` only when needed for forward refs.
- **Type hints**: required on public functions. Use modern syntax (\`str | None\`, \`list[X]\`).
- **Async**: \`asyncio\` everywhere. Provider streams are \`AsyncIterator\`.
- **Pydantic v2** for tool input validation and config schemas.
- **Formatting**: 4-space indent, \`ruff\` defaults (line length 100).
- **Language**: code, docstrings, identifiers in **English**. Task spec files are in Portuguese.
- **No emojis** in code or commit messages.
- **No CLAUDE.md / README updates** in this phase — focus on code + tests only.
- **Stubs are OK** for cross-phase dependencies as long as the task spec allows it.

## Your Task

1. Read \`${SPEC_FILE}\` (skim sections relevant to this task).
2. Read the task specification below carefully — it contains objective, technical description,
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
- This is iteration #${iteration} for this task. Focus on uncompleted items (unmarked checkboxes).

## Task Specification: ${task_relpath}

---
$(cat "$task_file")
---

REMEMBER: Mark each checkbox (\`- [ ]\` -> \`- [x]\`) in \`${task_file}\` as you complete each criterion.
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
log "Modulo: VULPCODE - CLI agentica multi-provedor"
log "Objetivo: Construir vulpcode end-to-end via Claude CLI"
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
    log_file "  OK: ${TASK_FILE#${DEV_DIR}/}"
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
    TASK_RELPATH="${TASK_FILE#${DEV_DIR}/}"
    TASK_BASENAME=$(basename "$TASK_FILE" .md)

    log ""
    log "======================================================"
    log "INICIANDO ${TASK_NAME} - ${TASK_RELPATH}"
    log "Arquivo: ${TASK_FILE}"
    log "======================================================"

    # Log especifico para cada tarefa
    TASK_LOG="${LOG_DIR}/vulpcode_step${TASK_NUM}_${TASK_BASENAME}_${TIMESTAMP}.log"
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

        # Arquivos para esta iteracao
        CLAUDE_RAW="${LOG_DIR}/claude_raw_step${TASK_NUM}_iter${ITERATION}.jsonl"
        CLAUDE_READABLE="${LOG_DIR}/claude_readable_step${TASK_NUM}_iter${ITERATION}.log"
        > "$CLAUDE_RAW"
        > "$CLAUDE_READABLE"

        # Links simbolicos para acompanhamento em tempo real
        ln -sf "$CLAUDE_RAW" "${LOG_DIR}/claude_current_raw.jsonl"
        ln -sf "$CLAUDE_READABLE" "${LOG_DIR}/claude_current.log"

        update_status "$TASK_NAME" "$TASK_RELPATH" "$ITERATION" "$PENDING" "$COMPLETED" \
            "CLAUDE EXECUTANDO (inicio: ${CLAUDE_START}) -- tail -f ${LOG_DIR}/claude_current.log"

        # Rodar claude com prompt completo
        log "[CLAUDE] Modo: prompt completo (spec + instrucoes) - iteracao ${ITERATION} (stream-json)"
        build_prompt "$TASK_FILE" "$ITERATION" | claude -p --dangerously-skip-permissions --verbose --output-format stream-json > "$CLAUDE_RAW" 2>&1 &
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

        # Claude terminou
        wait $CLAUDE_PID
        CLAUDE_EXIT_CODE=$?

        sleep 2
        kill $PARSER_PID 2>/dev/null
        wait $PARSER_PID 2>/dev/null

        CLAUDE_END=$(date '+%Y-%m-%d %H:%M:%S')
        FINAL_RAW_LINES=$(wc -l < "$CLAUDE_RAW" 2>/dev/null || echo 0)
        FINAL_RAW_SIZE=$(wc -c < "$CLAUDE_RAW" 2>/dev/null || echo 0)
        log "[CLAUDE] Fim da chamada: ${CLAUDE_END} (exit: ${CLAUDE_EXIT_CODE}, ${FINAL_RAW_LINES} eventos JSONL, ${FINAL_RAW_SIZE} bytes)"

        # Copiar logs
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
log "TODAS AS TAREFAS CONCLUIDAS COM SUCESSO!"
log "Inicio: ${EXEC_START_TIME}"
log "Fim:    ${EXEC_END_TIME}"
log "======================================================"
log ""
log "Executando verificacao final..."
log "  pip install -e ${PROJECT_ROOT}"
log "  pytest ${PROJECT_ROOT}/tests/ -v"
log "  vulp --help"

update_status "TODAS" "N/A" "N/A" "0" "N/A" "CONCLUIDO - ${EXEC_END_TIME}"
exit 0
