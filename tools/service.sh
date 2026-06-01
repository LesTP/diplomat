#!/bin/bash
# tools/service.sh — Start, stop, and check the Diplomat bot
#
# Usage:
#   bash tools/service.sh start              # start bot in background
#   bash tools/service.sh stop               # stop bot
#   bash tools/service.sh status             # check if running
#   bash tools/service.sh logs [N]           # show last N lines of log (default 50)
#   bash tools/service.sh restart            # stop + start
#
# Configuration:
#   DIPLOMAT_PIPELINE_CONFIG  env var or default config/pipeline_smoke.yaml
#   BOT_TMUX_SESSION          tmux session name, default bot
#
# When run inside an Incus container (e.g., via `incus exec`), paths
# resolve relative to the project directory. When run from the host,
# wrap with: incus exec claude-code -- bash /home/claude/workspace/diplomat/tools/service.sh start

set -euo pipefail

# Resolve project root relative to this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PIPELINE_CONFIG="${DIPLOMAT_PIPELINE_CONFIG:-config/pipeline_smoke.yaml}"
PID_FILE="$PROJECT_DIR/.diplomat.pid"
LOG_FILE="$PROJECT_DIR/logs/diplomat.log"
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"
TMUX_SESSION="${BOT_TMUX_SESSION:-bot}"
TMUX_WINDOW="diplomat"

tmux_as_service_user() {
    if [[ "$(id -un)" == "claude" ]]; then
        tmux "$@"
    else
        sudo -u claude tmux "$@"
    fi
}

require_tmux_session() {
    if tmux_as_service_user has-session -t "$TMUX_SESSION" 2>/dev/null; then
        return 0
    fi

    echo "tmux session '$TMUX_SESSION' not found; create with: sudo -u claude tmux new-session -d -s $TMUX_SESSION" >&2
    return 1
}

is_tmux_running() {
    tmux_as_service_user list-windows -t "$TMUX_SESSION" -F '#{window_name}' 2>/dev/null \
        | grep -Fxq "$TMUX_WINDOW"
}

start() {
    require_tmux_session

    if is_tmux_running; then
        echo "Diplomat is already running (tmux window $TMUX_SESSION:$TMUX_WINDOW)"
        return 0
    fi

    mkdir -p "$PROJECT_DIR/logs"

    local command
    printf -v command 'cd %q && PYTHONPATH=src DIPLOMAT_PIPELINE_CONFIG=%q %q -u src/main.py 2>&1 | tee -a %q' \
        "$PROJECT_DIR" "$PIPELINE_CONFIG" "$VENV_PYTHON" "$LOG_FILE"

    tmux_as_service_user new-window -t "$TMUX_SESSION" -n "$TMUX_WINDOW" "$command"
    rm -f "$PID_FILE"
    echo "Diplomat started (tmux window $TMUX_SESSION:$TMUX_WINDOW, config=$PIPELINE_CONFIG)"
    echo "Log: $LOG_FILE"
}

stop() {
    if ! is_running; then
        echo "Diplomat is not running"
        rm -f "$PID_FILE"
        return 0
    fi

    local pid
    pid=$(cat "$PID_FILE")
    kill "$pid" 2>/dev/null
    # Wait up to 5 seconds for graceful shutdown
    for _ in 1 2 3 4 5; do
        if ! kill -0 "$pid" 2>/dev/null; then
            break
        fi
        sleep 1
    done
    # Force kill if still alive
    if kill -0 "$pid" 2>/dev/null; then
        kill -9 "$pid" 2>/dev/null
    fi
    rm -f "$PID_FILE"
    echo "Diplomat stopped (was PID $pid)"
}

status() {
    if is_running; then
        echo "Diplomat is running (PID $(cat "$PID_FILE"))"
    else
        echo "Diplomat is not running"
        rm -f "$PID_FILE"
    fi
}

logs() {
    local lines="${1:-50}"
    if [[ -f "$LOG_FILE" ]]; then
        tail -n "$lines" "$LOG_FILE"
    else
        echo "No log file at $LOG_FILE"
    fi
}

is_running() {
    [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null
}

case "${1:-}" in
    start)   start ;;
    stop)    stop ;;
    status)  status ;;
    logs)    logs "${2:-50}" ;;
    restart) stop; start ;;
    *)
        echo "Usage: $0 {start|stop|status|logs [N]|restart}"
        exit 1
        ;;
esac
