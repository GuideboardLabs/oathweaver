#!/usr/bin/env bash
# Oathweaver installer — Linux equivalent of install_oathweaver.ps1
# Windows equivalent: install_oathweaver.ps1
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"
INSTALL_LIB="$REPO_ROOT/tools/install/lib.sh"
if [[ -f "$INSTALL_LIB" ]]; then
    # shellcheck disable=SC1090
    source "$INSTALL_LIB"
fi
DEFAULT_OLLAMA_INSTALL_URL="https://raw.githubusercontent.com/ollama/ollama/v0.18.0/scripts/install.sh"
DEFAULT_OLLAMA_INSTALL_SHA256="25f64b810b947145095956533e1bdf56eacea2673c55a7e586be4515fc882c9f"

SKIP_NODE=0
SKIP_PREREQ_INSTALL=0
SKIP_MODEL_PULL=0

usage() {
    echo "Usage: $0 [--skip-node] [--skip-prereq-install] [--skip-model-pull]"
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --skip-node)            SKIP_NODE=1;            shift ;;
        --skip-prereq-install)  SKIP_PREREQ_INSTALL=1;  shift ;;
        --skip-model-pull)      SKIP_MODEL_PULL=1;      shift ;;
        -h|--help) usage ;;
        *) echo "Unknown option: $1"; usage ;;
    esac
done

step()  { echo "[Oathweaver Installer] $*"; }
item()  { echo "  - $*"; }
warn()  { echo "WARNING: $*" >&2; }
die()   { echo "ERROR: $*" >&2; exit 1; }

confirm() {
    local MSG="$1"
    local DEFAULT="${2:-y}"  # y or n
    local HINT
    [[ "$DEFAULT" == "y" ]] && HINT="[Y/n]" || HINT="[y/N]"
    read -r -p "$MSG $HINT " REPLY
    REPLY="${REPLY:-$DEFAULT}"
    [[ "${REPLY,,}" =~ ^y(es)?$ ]]
}

# --- Python ---
PYTHON_CMD=""

resolve_python() {
    for cmd in python3 python; do
        if command -v "$cmd" > /dev/null 2>&1; then
            local VER
            VER="$("$cmd" -c 'import sys; print(sys.version_info >= (3,10))' 2>/dev/null || echo False)"
            if [[ "$VER" == "True" ]]; then
                echo "$cmd"
                return 0
            fi
        fi
    done
    return 1
}

ensure_python() {
    PYTHON_CMD="$(resolve_python)" || true
    if [[ -z "$PYTHON_CMD" ]]; then
        if [[ "$SKIP_PREREQ_INSTALL" -eq 1 ]]; then
            die "Python 3.10+ is required but was not found."
        fi
        echo "Python 3.10+ is required but was not found."
        if confirm "Install Python 3 now using your system package manager?"; then
            if command -v apt-get > /dev/null 2>&1; then
                sudo apt-get update -qq && sudo apt-get install -y python3 python3-pip python3-venv
            elif command -v dnf > /dev/null 2>&1; then
                sudo dnf install -y python3 python3-pip
            elif command -v pacman > /dev/null 2>&1; then
                sudo pacman -S --noconfirm python python-pip
            else
                die "Could not detect package manager. Install Python 3.10+ manually then rerun."
            fi
            PYTHON_CMD="$(resolve_python)" || die "Python install completed but python3 still not found. Open a new terminal and rerun."
        else
            die "Python is required to run Oathweaver."
        fi
    fi
    item "Python: $PYTHON_CMD ($("$PYTHON_CMD" --version 2>&1))"
}

# --- Ollama ---
OLLAMA_EXE=""

resolve_ollama() {
    if command -v ollama > /dev/null 2>&1; then
        command -v ollama
        return 0
    fi
    for c in "$HOME/.local/bin/ollama" "$HOME/.ollama/bin/ollama" "/usr/local/bin/ollama" "/usr/bin/ollama"; do
        [[ -x "$c" ]] && echo "$c" && return 0
    done
    return 1
}

ensure_ollama() {
    OLLAMA_EXE="$(resolve_ollama)" || true
    if [[ -z "$OLLAMA_EXE" ]]; then
        if [[ "$SKIP_PREREQ_INSTALL" -eq 1 ]]; then
            die "Ollama is required but not found."
        fi
        echo "Ollama is required but was not found."
        if confirm "Install Ollama now?"; then
            local install_url="${OATHWEAVER_OLLAMA_INSTALL_URL:-$DEFAULT_OLLAMA_INSTALL_URL}"
            local expected_sha="${OATHWEAVER_OLLAMA_INSTALL_SHA256:-$DEFAULT_OLLAMA_INSTALL_SHA256}"
            item "Default pinned installer source: $DEFAULT_OLLAMA_INSTALL_URL"
            item "Override via OATHWEAVER_OLLAMA_INSTALL_URL and OATHWEAVER_OLLAMA_INSTALL_SHA256."
            if [[ -n "$expected_sha" ]] && ! declare -F ow_verify_sha256 >/dev/null 2>&1; then
                die "Checksum pinning requested but tools/install/lib.sh is unavailable."
            fi
            if declare -F ow_install_ollama_script >/dev/null 2>&1; then
                ow_install_ollama_script "$install_url" "$expected_sha" || die "Ollama installer failed."
            else
                curl -fsSL "$install_url" | sh
            fi
            # Refresh PATH in case the installer added a new location
            export PATH="$HOME/.local/bin:$PATH"
            OLLAMA_EXE="$(resolve_ollama)" || die "Ollama install completed but executable not found. Open a new terminal and rerun."
        else
            die "Ollama is required to run Oathweaver."
        fi
    fi
    item "Ollama: $OLLAMA_EXE"
}

# --- Node.js (optional) ---
ensure_node() {
    if [[ "$SKIP_NODE" -eq 1 ]]; then
        item "Skipping Node.js (--skip-node)."
        return
    fi
    if command -v node > /dev/null 2>&1; then
        item "Node.js: $(node --version)"
        return
    fi
    if [[ "$SKIP_PREREQ_INSTALL" -eq 1 ]]; then
        warn "Node.js not found. Optional for runtime, useful for dev workflows."
        return
    fi
    if confirm "Node.js is optional but recommended for dev tooling. Install Node.js LTS?" "n"; then
        if command -v apt-get > /dev/null 2>&1; then
            curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
            sudo apt-get install -y nodejs
        elif command -v dnf > /dev/null 2>&1; then
            sudo dnf install -y nodejs
        elif command -v pacman > /dev/null 2>&1; then
            sudo pacman -S --noconfirm nodejs npm
        else
            warn "Could not detect package manager. Install Node.js manually if needed."
            return
        fi
        command -v node > /dev/null 2>&1 && item "Node.js: $(node --version)" || warn "Node.js install completed but node not detected in this session."
    else
        item "Node.js install skipped."
    fi
}

# --- Python dependencies ---
install_python_deps() {
    step "Installing Python dependencies..."

    # On Debian/Ubuntu, newspaper4k needs build libs
    if command -v apt-get > /dev/null 2>&1; then
        MISSING_LIBS=()
        for pkg in python3-dev libxml2-dev libxslt1-dev libjpeg-dev; do
            dpkg -s "$pkg" > /dev/null 2>&1 || MISSING_LIBS+=("$pkg")
        done
        if [[ ${#MISSING_LIBS[@]} -gt 0 ]]; then
            warn "Some build libraries may be needed for newspaper4k: ${MISSING_LIBS[*]}"
            if confirm "Install these build libraries now? (recommended)"; then
                sudo apt-get install -y "${MISSING_LIBS[@]}"
            fi
        fi
    fi

    "$PYTHON_CMD" -m pip install --upgrade pip
    REQUIREMENTS="$REPO_ROOT/requirements.lock"
    if [[ ! -f "$REQUIREMENTS" ]]; then
        warn "requirements.lock not found — falling back to requirements.txt (some dependencies may be missing)"
        REQUIREMENTS="$REPO_ROOT/requirements.txt"
    fi
    [[ -f "$REQUIREMENTS" ]] || die "No requirements file found at $REPO_ROOT"
    if declare -F ow_install_python_requirements >/dev/null 2>&1; then
        if [[ "$REQUIREMENTS" == *"requirements.lock" ]] && ! grep -q -- "--hash=" "$REQUIREMENTS"; then
            warn "requirements.lock has no hashes. Regenerate via ./tools/install/regenerate_hashed_lock.sh (or set OATHWEAVER_ALLOW_UNHASHED_LOCK=1)."
        fi
        ow_install_python_requirements "$PYTHON_CMD" "$REQUIREMENTS" "0"
    else
        "$PYTHON_CMD" -m pip install -r "$REQUIREMENTS"
    fi
}

# --- Ollama readiness ---
wait_for_ollama() {
    local TIMEOUT="${1:-30}"
    for i in $(seq 1 "$TIMEOUT"); do
        curl -sf --max-time 2 "http://127.0.0.1:11434/api/tags" > /dev/null 2>&1 && return 0
        sleep 1
    done
    return 1
}

ensure_ollama_running() {
    if wait_for_ollama 3; then
        item "Ollama API already reachable on http://127.0.0.1:11434"
        return
    fi
    step "Starting Ollama service..."
    OLLAMA_HOST="127.0.0.1:11434" nohup "$OLLAMA_EXE" serve > /dev/null 2>&1 &
    wait_for_ollama 90 || die "Ollama did not become ready in time."
    item "Ollama is ready."
}

# --- Required models ---
get_required_models() {
    local CONFIG_PATH="$REPO_ROOT/SourceCode/configs/model_routing.json"
    [[ -f "$CONFIG_PATH" ]] || die "Model routing config not found: $CONFIG_PATH"

    "$PYTHON_CMD" - "$CONFIG_PATH" <<'PYEOF'
import json, sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
models: set[str] = set()

def walk(node):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "model" and isinstance(v, str) and v.strip():
                models.add(v.strip())
            elif k == "fallback_models" and isinstance(v, list):
                for item in v:
                    if isinstance(item, str) and item.strip():
                        models.add(item.strip())
            else:
                walk(v)
    elif isinstance(node, list):
        for item in node:
            walk(item)

walk(data)
for name in sorted(models):
    print(name)
PYEOF
}

get_installed_models() {
    "$OLLAMA_EXE" list 2>/dev/null | tail -n +2 | awk '{print $1}' | grep -v '^$' | sort -u || true
}

ensure_required_models() {
    step "Checking required models from routing config..."
    REQUIRED_MODELS=()
    while IFS= read -r line; do
        [[ -n "$line" ]] && REQUIRED_MODELS+=("$line")
    done < <(get_required_models)

    if [[ ${#REQUIRED_MODELS[@]} -eq 0 ]]; then
        die "No models found in model_routing.json."
    fi

    for m in "${REQUIRED_MODELS[@]}"; do item "$m"; done

    INSTALLED_MODELS=()
    while IFS= read -r line; do
        [[ -n "$line" ]] && INSTALLED_MODELS+=("$line")
    done < <(get_installed_models)

    MISSING_MODELS=()
    for req in "${REQUIRED_MODELS[@]}"; do
        local found=0
        for inst in "${INSTALLED_MODELS[@]}"; do
            [[ "${inst,,}" == "${req,,}" ]] && found=1 && break
        done
        [[ "$found" -eq 0 ]] && MISSING_MODELS+=("$req")
    done

    if [[ ${#MISSING_MODELS[@]} -eq 0 ]]; then
        item "All required models are already installed."
        return
    fi

    step "Missing models:"
    for m in "${MISSING_MODELS[@]}"; do item "$m"; done

    if [[ "$SKIP_MODEL_PULL" -eq 1 ]]; then
        warn "Skipping model pulls (--skip-model-pull). Oathweaver may fail until these are pulled."
        return
    fi

    if confirm "Pull missing models now? (Can take a while and use large disk space.)"; then
        for m in "${MISSING_MODELS[@]}"; do
            step "Pulling model: $m"
            "$OLLAMA_EXE" pull "$m" || die "Failed to pull model: $m"
        done
    else
        warn "Model pulls skipped. Oathweaver may fail to answer until these models are pulled."
    fi
}

# --- Owner account ---
test_owner_exists() {
    "$PYTHON_CMD" - "$REPO_ROOT" <<'PYEOF'
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root / "SourceCode"))
from shared_tools.family_auth import FamilyAuthStore

store = FamilyAuthStore(root)
rows = store.list_profiles()
print("1" if any(bool(row.get("is_owner")) for row in rows) else "0")
PYEOF
}

get_owner_credentials() {
    while true; do
        read -r -p "Enter owner username (letters/numbers/_/-): " USERNAME
        USERNAME="${USERNAME,,}"  # lowercase
        read -r -s -p "Enter owner 4-digit PIN: " PIN
        echo ""
        read -r -s -p "Confirm owner 4-digit PIN: " PIN_CONFIRM
        echo ""

        if ! [[ "$USERNAME" =~ ^[a-z0-9_-]{1,32}$ ]]; then
            warn "Username must be 1-32 chars using letters, numbers, underscore, or hyphen."
            continue
        fi
        if ! [[ "$PIN" =~ ^[0-9]{4}$ ]]; then
            warn "PIN must be exactly 4 digits."
            continue
        fi
        if [[ "$PIN" != "$PIN_CONFIRM" ]]; then
            warn "PIN values do not match."
            continue
        fi
        OWNER_USERNAME="$USERNAME"
        OWNER_PIN="$PIN"
        return 0
    done
}

ensure_owner_account() {
    local OWNER_EXISTS
    OWNER_EXISTS="$(test_owner_exists)"
    if [[ "$OWNER_EXISTS" == "1" ]]; then
        item "Owner account already exists. Skipping first-user creation."
        return
    fi

    step "No owner account found. Collecting owner username and PIN..."
    OWNER_USERNAME=""
    OWNER_PIN=""
    get_owner_credentials

    FINAL_USER="$("$PYTHON_CMD" - "$REPO_ROOT" "$OWNER_USERNAME" "$OWNER_PIN" <<'PYEOF'
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
username = sys.argv[2].strip()
pin = sys.argv[3].strip()
sys.path.insert(0, str(root / "SourceCode"))
from shared_tools.family_auth import FamilyAuthStore

store = FamilyAuthStore(root)
owner = store.ensure_owner(owner_password=pin, owner_username=username)
print(owner.get("username", username))
PYEOF
    )"
    item "Owner account created for username '${FINAL_USER}'."
}

# --- Runtime directory permissions ---
ensure_runtime_dirs() {
    mkdir -p \
        "$REPO_ROOT/Runtime/state" \
        "$REPO_ROOT/Runtime/logs" \
        "$REPO_ROOT/Runtime/memory" \
        "$REPO_ROOT/Runtime/handoff" \
        "$REPO_ROOT/Runtime/learning" \
        "$REPO_ROOT/Projects"
    chmod -R u+rw "$REPO_ROOT/Runtime" "$REPO_ROOT/Projects"
}

# --- Run ---
step "Starting setup in $REPO_ROOT"

ensure_python
ensure_ollama
ensure_node
ensure_runtime_dirs
install_python_deps
ensure_ollama_running
ensure_required_models
ensure_owner_account

echo ""
step "Setup complete."
echo ""
echo "Next step:"
echo "  bash ./start_oathweaver_web.sh"
echo ""
echo "Or to start as a systemd user service, see: docs/linux-service.md"
