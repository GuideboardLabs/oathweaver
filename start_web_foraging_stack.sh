#!/usr/bin/env bash
# Web foraging stack launcher — Linux equivalent of start_web_foraging_stack.ps1
# Windows equivalent: start_web_foraging_stack.ps1
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SEARX_SETTINGS_PATH="$REPO_ROOT/Runtime/services/searxng/settings.yml"
RECREATE=0

usage() {
    echo "Usage: $0 [--recreate]"
    echo "  --recreate   Remove and recreate containers from scratch"
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --recreate) RECREATE=1; shift ;;
        -h|--help) usage ;;
        *) echo "Unknown option: $1"; usage ;;
    esac
done

# --- Ensure Docker daemon is running ---
if ! command -v docker > /dev/null 2>&1; then
    echo "ERROR: Docker CLI not found. Install Docker: https://docs.docker.com/engine/install/"
    exit 1
fi

if ! docker info > /dev/null 2>&1; then
    echo "ERROR: Docker daemon is not running."
    echo "Start it with: sudo systemctl start docker"
    echo "(To enable at boot: sudo systemctl enable docker)"
    exit 1
fi

# --- Ensure SearXNG settings file exists and has JSON format enabled ---
ensure_searx_settings() {
    local settings_dir
    settings_dir="$(dirname "$SEARX_SETTINGS_PATH")"
    mkdir -p "$settings_dir"

    if [[ ! -f "$SEARX_SETTINGS_PATH" || "$RECREATE" -eq 1 ]]; then
        echo "Creating baseline SearXNG settings file..."
        docker run -d --name searxng_seed_tmp searxng/searxng > /dev/null
        sleep 5
        docker cp "searxng_seed_tmp:/etc/searxng/settings.yml" "$SEARX_SETTINGS_PATH"
        docker rm -f searxng_seed_tmp > /dev/null
    fi

    # Patch JSON format in using Python (handles multiline cleanly cross-platform)
    python3 - "$SEARX_SETTINGS_PATH" <<'PYEOF'
import sys
from pathlib import Path

p = Path(sys.argv[1])
text = p.read_text(encoding="utf-8")

if "formats:" in text and "- json" not in text:
    # Insert "- json" after "- html" under the formats key
    text = text.replace(
        "  formats:\n    - html\n",
        "  formats:\n    - html\n    - json\n"
    )
    p.write_text(text, encoding="utf-8")
    print("Enabled JSON format in SearXNG settings.")
else:
    print("SearXNG settings already have JSON format enabled.")
PYEOF
}

# --- Create or start a container ---
ensure_container() {
    local NAME="$1"
    local RUN_ARGS="$2"

    local EXISTS
    EXISTS="$(docker ps -a --format '{{.Names}}' | grep -x "$NAME" || true)"

    if [[ "$RECREATE" -eq 1 && -n "$EXISTS" ]]; then
        echo "Removing container: $NAME"
        docker rm -f "$NAME" > /dev/null
        EXISTS=""
    fi

    if [[ -z "$EXISTS" ]]; then
        echo "Creating container: $NAME"
        # shellcheck disable=SC2086
        docker run -d $RUN_ARGS > /dev/null
    else
        local RUNNING
        RUNNING="$(docker ps --format '{{.Names}}' | grep -x "$NAME" || true)"
        if [[ -z "$RUNNING" ]]; then
            echo "Starting container: $NAME"
            docker start "$NAME" > /dev/null
        else
            echo "Container already running: $NAME"
        fi
    fi
}

# --- Health check ---
test_url() {
    local URL="$1"
    local TIMEOUT="${2:-20}"
    local HTTP_CODE
    HTTP_CODE="$(curl -o /dev/null -sf --max-time "$TIMEOUT" -w '%{http_code}' "$URL" 2>/dev/null || echo "ERR")"
    echo "$HTTP_CODE"
}

# --- Main ---
ensure_searx_settings

ensure_container "searxng" \
    "-p 8080:8080 --name searxng -v ${SEARX_SETTINGS_PATH}:/etc/searxng/settings.yml searxng/searxng"

ensure_container "crawl4ai" \
    "--platform linux/amd64 -p 11235:11235 --name crawl4ai --shm-size=2g --cpus=4 --memory=4g -e MAX_CONCURRENT_TASKS=5 -e BROWSER_POOL_SIZE=10 unclecode/crawl4ai:latest"

sleep 4

echo ""
echo "Container status:"
docker ps --filter "name=searxng" --filter "name=crawl4ai" \
    --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "Health checks:"
echo "SearXNG /search json: $(test_url 'http://127.0.0.1:8080/search?q=oathweaver&format=json')"
echo "Crawl4AI /health:     $(test_url 'http://127.0.0.1:11235/health')"
echo ""
echo "Web foraging stack ready."
