#!/usr/bin/env bash
# Oathweaver Web UI launcher — Linux equivalent of start_oathweaver_web.ps1
# Windows equivalent: start_oathweaver_web.ps1
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- Defaults (override via env or flags) ---
OLLAMA_HOST_VAL="${OLLAMA_HOST:-0.0.0.0:11434}"
OLLAMA_MODELS_VAL="${OLLAMA_MODELS:-}"
OLLAMA_LOG_LEVEL_VAL="${OLLAMA_LOG_LEVEL:-info}"
WEB_HOST="${OATHWEAVER_WEB_HOST:-0.0.0.0}"
WEB_PORT="${OATHWEAVER_WEB_PORT:-5050}"
WEB_PASSWORD="${OATHWEAVER_WEB_PASSWORD:-}"
NO_RESTART_OLLAMA=0

usage() {
    echo "Usage: $0 [--web-host <host>] [--web-port <port>] [--web-password <pw>]"
    echo "          [--ollama-models <path>] [--ollama-host <host:port>]"
    echo "          [--ollama-log-level <level>] [--no-restart-ollama]"
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --web-host)         WEB_HOST="$2";           shift 2 ;;
        --web-port)         WEB_PORT="$2";            shift 2 ;;
        --web-password)     WEB_PASSWORD="$2";        shift 2 ;;
        --ollama-models)    OLLAMA_MODELS_VAL="$2";  shift 2 ;;
        --ollama-host)      OLLAMA_HOST_VAL="$2";    shift 2 ;;
        --ollama-log-level) OLLAMA_LOG_LEVEL_VAL="$2"; shift 2 ;;
        --no-restart-ollama) NO_RESTART_OLLAMA=1;    shift ;;
        -h|--help) usage ;;
        *) echo "Unknown option: $1"; usage ;;
    esac
done

# --- Resolve Ollama binary ---
resolve_ollama() {
    if command -v ollama > /dev/null 2>&1; then
        command -v ollama
        return 0
    fi
    local candidates=(
        "$HOME/.local/bin/ollama"
        "$HOME/.ollama/bin/ollama"
        "/usr/local/bin/ollama"
        "/usr/bin/ollama"
    )
    for c in "${candidates[@]}"; do
        if [[ -x "$c" ]]; then
            echo "$c"
            return 0
        fi
    done
    return 1
}

OLLAMA_EXE="$(resolve_ollama)" || {
    echo "ERROR: Ollama executable not found."
    echo "Install Ollama: curl -fsSL https://ollama.ai/install.sh | sh"
    exit 1
}

# --- Resolve model directory ---
resolve_ollama_models() {
    local preferred="$1"
    local candidates=()
    [[ -n "$preferred" ]] && candidates+=("$preferred")
    [[ -n "${OLLAMA_MODELS:-}" ]] && candidates+=("$OLLAMA_MODELS")
    candidates+=("$HOME/.ollama/models")
    for c in "${candidates[@]}"; do
        [[ -d "$c" ]] && echo "$c" && return 0
    done
    echo "$HOME/.ollama/models"
}

RESOLVED_MODELS="$(resolve_ollama_models "$OLLAMA_MODELS_VAL")"
if [[ ! -d "$RESOLVED_MODELS" ]]; then
    mkdir -p "$RESOLVED_MODELS"
    echo "WARNING: Created model directory: $RESOLVED_MODELS"
fi
if [[ ! -d "$RESOLVED_MODELS/blobs" || ! -d "$RESOLVED_MODELS/manifests" ]]; then
    echo "WARNING: Model directory does not contain blobs/manifests. Pull models if this is first run."
fi

# --- Export env vars ---
export OLLAMA_MODELS="$RESOLVED_MODELS"
export OLLAMA_HOST="$OLLAMA_HOST_VAL"
export OLLAMA_LOG_LEVEL="$OLLAMA_LOG_LEVEL_VAL"
export OATHWEAVER_WEB_HOST="$WEB_HOST"
export OATHWEAVER_WEB_PORT="$WEB_PORT"
[[ -n "$WEB_PASSWORD" ]] && export OATHWEAVER_WEB_PASSWORD="$WEB_PASSWORD"

# --- Restart Ollama ---
if [[ "$NO_RESTART_OLLAMA" -eq 0 ]]; then
    pkill -x ollama 2>/dev/null || true
    sleep 1
fi

nohup "$OLLAMA_EXE" serve > /dev/null 2>&1 &

# --- Wait for Ollama ready ---
echo "Waiting for Ollama to be ready..."
READY=0
for i in $(seq 1 30); do
    if curl -sf --max-time 2 "http://127.0.0.1:11434/api/tags" > /dev/null 2>&1; then
        READY=1
        break
    fi
    sleep 1
done

if [[ "$READY" -eq 0 ]]; then
    echo "ERROR: Ollama did not become ready on http://127.0.0.1:11434"
    exit 1
fi

echo "Ollama started from: $OLLAMA_EXE"
echo "OLLAMA_MODELS: $OLLAMA_MODELS"
echo "OLLAMA_HOST: $OLLAMA_HOST"
echo "OATHWEAVER_WEB_PASSWORD set: $([ -n "${OATHWEAVER_WEB_PASSWORD:-}" ] && echo true || echo false)"
echo "Local models:"
"$OLLAMA_EXE" list

# --- Kill existing web app process ---
pkill -f "web_gui/app.py" 2>/dev/null || true

# --- Kill any process using the web port ---
kill_port() {
    local PORT="$1"
    if command -v fuser > /dev/null 2>&1; then
        fuser -k "${PORT}/tcp" 2>/dev/null || true
    elif command -v lsof > /dev/null 2>&1; then
        lsof -ti:"$PORT" 2>/dev/null | xargs kill -9 2>/dev/null || true
    fi
}
kill_port "$WEB_PORT"
sleep 0.4

# --- Verify web app entrypoint ---
WEB_APP="$REPO_ROOT/SourceCode/web_gui/app.py"
if [[ ! -f "$WEB_APP" ]]; then
    echo "ERROR: Web app not found: $WEB_APP"
    exit 1
fi

# --- Print access URLs ---
echo ""
echo "Starting Oathweaver Web UI..."
echo "OATHWEAVER_WEB_HOST: $OATHWEAVER_WEB_HOST"
echo "OATHWEAVER_WEB_PORT: $OATHWEAVER_WEB_PORT"

if [[ "$WEB_HOST" == "0.0.0.0" ]]; then
    echo "Open from this PC:  http://127.0.0.1:${WEB_PORT}"

    # Collect all non-loopback, non-link-local IPv4 addresses
    if command -v ip > /dev/null 2>&1; then
        ALL_IPS="$(ip -4 addr show scope global 2>/dev/null | grep -oE 'inet [0-9.]+' | awk '{print $2}')"
    else
        ALL_IPS="$(hostname -I 2>/dev/null | tr ' ' '\n' | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$' | grep -v '^127\.' | grep -v '^169\.254\.')"
    fi

    LAN_IPS="$(echo "$ALL_IPS" | grep -v '^100\.' | grep -v '^$' || true)"
    TAILSCALE_IPS="$(echo "$ALL_IPS" | grep '^100\.' | grep -v '^$' || true)"

    if [[ -n "$LAN_IPS" ]]; then
        echo "Open from LAN:"
        while IFS= read -r ip; do
            echo "  http://${ip}:${WEB_PORT}"
        done <<< "$LAN_IPS"
    fi

    if [[ -n "$TAILSCALE_IPS" ]]; then
        echo "Open via Tailscale (approved devices / cellular):"
        while IFS= read -r ip; do
            echo "  http://${ip}:${WEB_PORT}"
        done <<< "$TAILSCALE_IPS"
    else
        echo "Tailscale not detected — install Tailscale to enable remote/cellular access."
    fi
else
    echo "Open URL: http://${WEB_HOST}:${WEB_PORT}"
fi
echo "If phone cannot connect, allow inbound TCP port ${WEB_PORT} in your firewall."

# --- Launch web app (foreground) ---
python3 "$WEB_APP"
