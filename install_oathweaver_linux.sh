#!/usr/bin/env bash
# =============================================================================
# Oathweaver — Linux Setup Script
# Tested on: Ubuntu 24.04 LTS, Ubuntu 22.04 LTS
#
# Usage:
#   chmod +x install_oathweaver_linux.sh
#   ./install_oathweaver_linux.sh
#
# GPU options (prompted interactively):
#   AMD  — installs ROCm 6.x  (RX 5700 XT, RX 6000/7000 series, etc.)
#   NVIDIA — installs CUDA toolkit (RTX/GTX series)
#   None — CPU-only; slower inference, no extra drivers needed
#
# Re-running this script is safe — all steps check before acting.
# =============================================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SEARX_SETTINGS="$REPO_ROOT/Runtime/services/searxng/settings.yml"
UBUNTU_CODENAME="$(lsb_release -cs 2>/dev/null || echo 'noble')"
INSTALL_LIB="$REPO_ROOT/tools/install/lib.sh"
if [[ -f "$INSTALL_LIB" ]]; then
    # shellcheck disable=SC1090
    source "$INSTALL_LIB"
fi
DEFAULT_OLLAMA_INSTALL_URL="https://raw.githubusercontent.com/ollama/ollama/v0.18.0/scripts/install.sh"
DEFAULT_OLLAMA_INSTALL_SHA256="25f64b810b947145095956533e1bdf56eacea2673c55a7e586be4515fc882c9f"

# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------

step()    { echo ""; echo "==> $*"; }
info()    { echo "    $*"; }
warn()    { echo "    [WARN] $*"; }
success() { echo "    [OK] $*"; }
die()     { echo ""; echo "[ERROR] $*" >&2; exit 1; }
sep()     { echo "    ----------------------------------------------------"; }

confirm() {
    local msg="$1" default="${2:-y}" prompt reply
    [[ "$default" == "y" ]] && prompt="[Y/n]" || prompt="[y/N]"
    read -rp "    $msg $prompt: " reply
    reply="${reply:-$default}"
    [[ "${reply,,}" == "y" || "${reply,,}" == "yes" ]]
}

command_exists() { command -v "$1" &>/dev/null; }

# Docker command — may need sudo if the user isn't in the docker group yet
if docker info &>/dev/null 2>&1; then
    DOCKER_CMD="docker"
else
    DOCKER_CMD="sudo docker"
fi

# ------------------------------------------------------------------------------
# GPU selection — asked once, used throughout
# ------------------------------------------------------------------------------

echo ""
echo "======================================================================="
echo " Oathweaver Linux Setup"
echo "======================================================================="
echo ""
echo " What GPU does this machine have?"
echo ""
echo "   1) AMD   — RX 5000/6000/7000 series, Radeon Pro"
echo "              Installs ROCm for GPU-accelerated inference"
echo ""
echo "   2) NVIDIA — GTX/RTX series"
echo "              Installs CUDA toolkit for GPU-accelerated inference"
echo ""
echo "   3) None / CPU only"
echo "              No GPU drivers installed. Inference will be slower"
echo "              but everything else works the same."
echo ""
read -rp "    Enter 1, 2, or 3: " GPU_CHOICE
echo ""

case "$GPU_CHOICE" in
    1) GPU_TYPE="amd" ;;
    2) GPU_TYPE="nvidia" ;;
    3) GPU_TYPE="none" ;;
    *) warn "Unrecognised choice — defaulting to CPU only."; GPU_TYPE="none" ;;
esac

# ------------------------------------------------------------------------------
# 1. System packages
# ------------------------------------------------------------------------------

step "Step 1/9 — Installing system packages..."

# Remove any stale ROCm source list written by a prior failed run with the wrong
# version or codename (e.g. rocm/apt/6.0 on noble) — it would break apt-get update.
if [[ -f /etc/apt/sources.list.d/rocm.list ]]; then
    if grep -qE "apt/6\.[01]" /etc/apt/sources.list.d/rocm.list && [[ "$UBUNTU_CODENAME" == "noble" ]]; then
        warn "Removing stale ROCm source list (6.0/6.1 not compatible with noble/24.04)."
        sudo rm -f /etc/apt/sources.list.d/rocm.list
    fi
fi

sudo apt-get update -qq
sudo apt-get install -y \
    python3 python3-pip python3-venv \
    git curl wget \
    docker.io \
    lsb-release \
    software-properties-common

sudo systemctl enable --now docker

if ! groups "$USER" | grep -q docker; then
    sudo usermod -aG docker "$USER"
    warn "Added $USER to the 'docker' group."
    warn "This only takes effect after a log out / log back in."
    warn "Until then the script will use 'sudo docker' for this session."
    DOCKER_CMD="sudo docker"
fi

success "System packages ready."

# ------------------------------------------------------------------------------
# 2. GPU drivers  (AMD = ROCm, NVIDIA = CUDA)
# ------------------------------------------------------------------------------

if [[ "$GPU_TYPE" == "amd" ]]; then

    step "Step 2/9 — AMD GPU: Installing ROCm..."
    echo ""
    echo "    ROCm gives Ollama direct access to your AMD GPU for inference."
    echo "    Without it, Ollama falls back to CPU-only mode."
    echo "    Supported cards: RX 5000/6000/7000 series, Radeon Pro W-series."
    echo "    Download size: ~2 GB."
    sep

    if command_exists rocm-smi; then
        success "ROCm already installed: $(rocm-smi --version 2>/dev/null | head -1 || echo 'found')"
    else
        if confirm "Install ROCm now?"; then
            info "Using AMD's amdgpu-install tool (avoids conflicts with Ubuntu's built-in ROCm packages)..."

            # ROCm 6.2 is the first release with Ubuntu 24.04 (noble) support.
            # amdgpu-install is AMD's recommended installer — it pins the correct
            # package versions and avoids conflicts with Ubuntu's own rocminfo/hipcc.
            if [[ "$UBUNTU_CODENAME" == "noble" ]]; then
                AMDGPU_DEB_URL="https://repo.radeon.com/amdgpu-install/6.2/ubuntu/noble/amdgpu-install_6.2.60200-1_all.deb"
            else
                # jammy (22.04) fallback
                AMDGPU_DEB_URL="https://repo.radeon.com/amdgpu-install/6.0/ubuntu/jammy/amdgpu-install_6.0.60000-1_all.deb"
            fi

            wget -qO /tmp/amdgpu-install.deb "$AMDGPU_DEB_URL"
            sudo apt-get install -y /tmp/amdgpu-install.deb
            rm -f /tmp/amdgpu-install.deb

            sudo amdgpu-install --usecase=rocm --no-dkms -y

            # GPU device access requires these groups
            sudo usermod -aG render,video "$USER"

            success "ROCm installed."
            warn "You must log out and back in for GPU group membership (render, video) to take effect."
            warn "After relogging, verify with: rocm-smi"
        else
            warn "ROCm install skipped. Ollama will run in CPU-only mode."
        fi
    fi

elif [[ "$GPU_TYPE" == "nvidia" ]]; then

    step "Step 2/9 — NVIDIA GPU: Installing CUDA toolkit..."
    echo ""
    echo "    CUDA gives Ollama direct access to your NVIDIA GPU for inference."
    echo "    Without it, Ollama falls back to CPU-only mode."
    echo "    Supported cards: GTX 10xx and newer, any RTX series."
    echo "    Download size: ~3-4 GB."
    sep

    # Check for an existing NVIDIA driver first
    NVIDIA_DRIVER_OK=false
    if command_exists nvidia-smi && nvidia-smi &>/dev/null; then
        NVIDIA_DRIVER_OK=true
        success "NVIDIA driver already installed: $(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -1 || echo 'found')"
    fi

    # Check for existing CUDA
    CUDA_OK=false
    if command_exists nvcc || [[ -f /usr/local/cuda/bin/nvcc ]]; then
        CUDA_OK=true
        success "CUDA already installed."
    fi

    if [[ "$NVIDIA_DRIVER_OK" == false ]] || [[ "$CUDA_OK" == false ]]; then
        if confirm "Install NVIDIA driver and CUDA toolkit now?"; then

            if [[ "$NVIDIA_DRIVER_OK" == false ]]; then
                info "Installing NVIDIA driver via ubuntu-drivers..."
                sudo apt-get install -y ubuntu-drivers-common
                # ubuntu-drivers autoinstall picks the recommended driver for your card
                sudo ubuntu-drivers autoinstall
            fi

            if [[ "$CUDA_OK" == false ]]; then
                info "Adding NVIDIA CUDA APT repository..."
                # Official NVIDIA CUDA repo — newer versions than apt default
                CUDA_KEYRING_URL="https://developer.download.nvidia.com/compute/cuda/repos"
                if [[ "$UBUNTU_CODENAME" == "noble" ]]; then
                    CUDA_PKG_URL="$CUDA_KEYRING_URL/ubuntu2404/x86_64/cuda-keyring_1.1-1_all.deb"
                else
                    # Fallback for 22.04 jammy
                    CUDA_PKG_URL="$CUDA_KEYRING_URL/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb"
                fi
                wget -qO /tmp/cuda-keyring.deb "$CUDA_PKG_URL"
                sudo dpkg -i /tmp/cuda-keyring.deb
                rm -f /tmp/cuda-keyring.deb

                sudo apt-get update -qq
                sudo apt-get install -y cuda-toolkit
            fi

            success "NVIDIA driver and CUDA installed."
            warn "A reboot may be required before Ollama can use the GPU."
            warn "After rebooting, verify with: nvidia-smi"
        else
            warn "NVIDIA driver / CUDA install skipped. Ollama will run in CPU-only mode."
        fi
    fi

else
    step "Step 2/9 — GPU drivers: Skipped (CPU-only mode)."
    info "Ollama will use your CPU for inference. This is slower but fully functional."
fi

# ------------------------------------------------------------------------------
# 3. Ollama
# ------------------------------------------------------------------------------

step "Step 3/9 — Installing Ollama..."

if ! command_exists ollama; then
    info "Downloading and running the official Ollama install script..."
    info "(Ollama auto-detects CUDA or ROCm if installed — no extra config needed.)"
    OLLAMA_INSTALL_URL="${OATHWEAVER_OLLAMA_INSTALL_URL:-$DEFAULT_OLLAMA_INSTALL_URL}"
    OLLAMA_INSTALL_SHA256="${OATHWEAVER_OLLAMA_INSTALL_SHA256:-$DEFAULT_OLLAMA_INSTALL_SHA256}"
    info "Default pinned installer source: $DEFAULT_OLLAMA_INSTALL_URL"
    info "Override with OATHWEAVER_OLLAMA_INSTALL_URL and OATHWEAVER_OLLAMA_INSTALL_SHA256 if needed."
    if [[ -n "$OLLAMA_INSTALL_SHA256" ]] && ! declare -F ow_verify_sha256 >/dev/null 2>&1; then
        die "Checksum pinning requested but tools/install/lib.sh is unavailable."
    fi
    if declare -F ow_install_ollama_script >/dev/null 2>&1; then
        ow_install_ollama_script "$OLLAMA_INSTALL_URL" "$OLLAMA_INSTALL_SHA256" || die "Ollama installer failed."
    else
        curl -fsSL "$OLLAMA_INSTALL_URL" | sh
    fi
    success "Ollama installed."
else
    success "Ollama already installed: $(ollama --version 2>/dev/null || echo 'unknown version')"
fi

# Ensure the Ollama systemd service is running
if ! systemctl is-active --quiet ollama 2>/dev/null; then
    info "Starting Ollama service..."
    sudo systemctl enable --now ollama
fi

info "Applying Ollama loopback-only bind (127.0.0.1:11434) for safer default access..."
sudo mkdir -p /etc/systemd/system/ollama.service.d
sudo tee /etc/systemd/system/ollama.service.d/oathweaver.conf >/dev/null <<'EOF'
[Service]
Environment="OLLAMA_HOST=127.0.0.1:11434"
EOF
sudo systemctl daemon-reload
sudo systemctl restart ollama

# Wait for the Ollama API to be reachable
info "Waiting for Ollama API to be ready..."
for i in $(seq 1 30); do
    if curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
        success "Ollama API is ready."
        break
    fi
    sleep 2
    if [[ $i -eq 30 ]]; then
        die "Ollama API did not respond in time. Check: sudo journalctl -u ollama -n 30"
    fi
done

# ------------------------------------------------------------------------------
# 4. Python dependencies
# ------------------------------------------------------------------------------

step "Step 4/9 — Installing Python dependencies..."

REQUIREMENTS="$REPO_ROOT/requirements.lock"
if [[ ! -f "$REQUIREMENTS" ]]; then
    warn "requirements.lock not found — falling back to requirements.txt (some dependencies may be missing)"
    REQUIREMENTS="$REPO_ROOT/requirements.txt"
fi
[[ -f "$REQUIREMENTS" ]] || die "No requirements file found at $REPO_ROOT"

VENV_DIR="$REPO_ROOT/.venv"
if [[ ! -d "$VENV_DIR" ]]; then
    info "Creating Python virtual environment at .venv ..."
    python3 -m venv "$VENV_DIR"
fi
PYTHON_BIN="$VENV_DIR/bin/python"
"$PYTHON_BIN" -m pip install --upgrade pip -q
if declare -F ow_install_python_requirements >/dev/null 2>&1; then
    if [[ "$REQUIREMENTS" == *"requirements.lock" ]] && ! grep -q -- "--hash=" "$REQUIREMENTS"; then
        warn "requirements.lock has no hashes. Regenerate via ./tools/install/regenerate_hashed_lock.sh (or set OATHWEAVER_ALLOW_UNHASHED_LOCK=1)."
    fi
    ow_install_python_requirements "$PYTHON_BIN" "$REQUIREMENTS" "1"
else
    "$PYTHON_BIN" -m pip install -r "$REQUIREMENTS" -q
fi
success "Python dependencies installed in .venv"

# ------------------------------------------------------------------------------
# 5. Pull required Ollama models
# ------------------------------------------------------------------------------

step "Step 5/9 — Checking required Ollama models..."

ROUTING_CONFIG="$REPO_ROOT/SourceCode/configs/model_routing.json"
if [[ -f "$ROUTING_CONFIG" ]]; then
    REQUIRED_MODELS=$(python3 - "$ROUTING_CONFIG" <<'PYEOF'
import json, sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
models = set()

def walk(node):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "model" and isinstance(v, str) and v.strip():
                models.add(v.strip())
            elif k == "fallback_models" and isinstance(v, list):
                for m in v:
                    if isinstance(m, str) and m.strip():
                        models.add(m.strip())
            else:
                walk(v)
    elif isinstance(node, list):
        for item in node:
            walk(item)

walk(data)
for m in sorted(models):
    print(m)
PYEOF
    )
else
    warn "model_routing.json not found — using default model list."
    REQUIRED_MODELS="dolphin3:8b
deepseek-r1:8b
qwen2.5-coder:7b
qwen3:4b
nomic-embed-text"
fi

INSTALLED_MODELS=$(ollama list 2>/dev/null | awk 'NR>1 {print $1}')

MISSING_MODELS=()
while IFS= read -r model; do
    [[ -z "$model" ]] && continue
    if ! echo "$INSTALLED_MODELS" | grep -qF "$model"; then
        MISSING_MODELS+=("$model")
    fi
done <<< "$REQUIRED_MODELS"

if [[ ${#MISSING_MODELS[@]} -eq 0 ]]; then
    success "All required models are already installed."
else
    echo ""
    info "Models required by model_routing.json:"
    while IFS= read -r m; do
        [[ -z "$m" ]] && continue
        if echo "$INSTALLED_MODELS" | grep -qF "$m"; then
            info "  [installed] $m"
        else
            info "  [missing]   $m"
        fi
    done <<< "$REQUIRED_MODELS"
    sep
    info "Total missing: ${#MISSING_MODELS[@]}"
    info "These can be several GB in total depending on which are needed."
    echo ""
    if confirm "Pull missing models now? (Recommended — Oathweaver will not work without them)"; then
        for model in "${MISSING_MODELS[@]}"; do
            step "Pulling: $model"
            ollama pull "$model" || die "Failed to pull model: $model"
            success "$model ready."
        done
    else
        warn "Model pulls skipped."
        warn "Pull manually later with:  ollama pull <model-name>"
    fi
fi

# ------------------------------------------------------------------------------
# 6. Create owner account (first-run only)
# ------------------------------------------------------------------------------

step "Step 6/9 — Checking owner account..."

OWNER_EXISTS=$(python3 - "$REPO_ROOT" <<'PYEOF'
import sys
from pathlib import Path
root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root / "SourceCode"))
try:
    from shared_tools.family_auth import FamilyAuthStore
    store = FamilyAuthStore(root)
    rows = store.list_profiles()
    print("1" if any(bool(r.get("is_owner")) for r in rows) else "0")
except Exception:
    print("0")
PYEOF
)

if [[ "$OWNER_EXISTS" == "1" ]]; then
    success "Owner account already exists. Skipping."
else
    info "No owner account found. You need to create one to log in."
    echo ""
    while true; do
        read -rp "    Owner username (letters/numbers/_/-): " GB_USERNAME
        GB_USERNAME="${GB_USERNAME,,}"
        if [[ ! "$GB_USERNAME" =~ ^[a-z0-9_-]{1,32}$ ]]; then
            warn "Username must be 1-32 characters: letters, numbers, _ or -"
            continue
        fi
        read -rsp "    Owner PIN (4 digits): " GB_PIN; echo ""
        read -rsp "    Confirm PIN:          " GB_PIN2; echo ""
        if [[ ! "$GB_PIN" =~ ^[0-9]{4}$ ]]; then
            warn "PIN must be exactly 4 digits."
            continue
        fi
        if [[ "$GB_PIN" != "$GB_PIN2" ]]; then
            warn "PINs do not match. Try again."
            continue
        fi
        break
    done

    python3 - "$REPO_ROOT" "$GB_USERNAME" "$GB_PIN" <<'PYEOF'
import sys
from pathlib import Path
root = Path(sys.argv[1]).resolve()
username, pin = sys.argv[2].strip(), sys.argv[3].strip()
sys.path.insert(0, str(root / "SourceCode"))
from shared_tools.family_auth import FamilyAuthStore
store = FamilyAuthStore(root)
owner = store.ensure_owner(owner_password=pin, owner_username=username)
print(f"    Owner account created: {owner.get('username', username)}")
PYEOF
    success "Owner account created."
fi

# ------------------------------------------------------------------------------
# 7. SearXNG + Crawl4AI Docker containers  (web research / forage stack)
# ------------------------------------------------------------------------------

step "Step 7/9 — Setting up SearXNG and Crawl4AI containers..."
info "These power the web research (Fieldbook) lane."
info "SearXNG runs a local search engine on port 8080."
info "Crawl4AI handles web page scraping on port 11235."

mkdir -p "$(dirname "$SEARX_SETTINGS")"

# Seed the SearXNG settings file from a temporary container if it doesn't exist
if [[ ! -f "$SEARX_SETTINGS" ]]; then
    info "Seeding SearXNG settings file from container (first run only)..."
    $DOCKER_CMD run -d --name searxng_seed_tmp searxng/searxng >/dev/null
    sleep 5
    $DOCKER_CMD cp "searxng_seed_tmp:/etc/searxng/settings.yml" "$SEARX_SETTINGS"
    $DOCKER_CMD rm -f searxng_seed_tmp >/dev/null
    success "Settings saved to Runtime/services/searxng/settings.yml"

    # Enable JSON output format so Oathweaver's research engine can parse results
    python3 - "$SEARX_SETTINGS" <<'PYEOF'
import re, sys
from pathlib import Path
p = Path(sys.argv[1])
text = p.read_text()
if "formats:" in text and "- json" not in text:
    text = re.sub(r"(  formats:\s*\n    - html)", r"\1\n    - json", text)
    p.write_text(text)
    print("    Enabled JSON format in SearXNG settings.")
PYEOF
fi

# Helper: create a container if absent, start it if stopped
ensure_container() {
    local name="$1"; shift
    local run_args=("$@")
    if $DOCKER_CMD ps -a --format '{{.Names}}' | grep -qx "$name"; then
        if ! $DOCKER_CMD ps --format '{{.Names}}' | grep -qx "$name"; then
            info "Starting stopped container: $name"
            $DOCKER_CMD start "$name" >/dev/null
        else
            success "Container already running: $name"
        fi
    else
        info "Creating container: $name"
        $DOCKER_CMD run -d "${run_args[@]}" >/dev/null
    fi
    # Mark container to restart automatically on system boot
    $DOCKER_CMD update --restart unless-stopped "$name" >/dev/null
}

ensure_container "searxng" \
    -p 127.0.0.1:8080:8080 \
    --name searxng \
    -v "$SEARX_SETTINGS:/etc/searxng/settings.yml" \
    searxng/searxng

ensure_container "crawl4ai" \
    --platform linux/amd64 \
    -p 127.0.0.1:11235:11235 \
    --name crawl4ai \
    --shm-size=1g \
    --cpus=4 \
    --memory=4g \
    -e MAX_CONCURRENT_TASKS=5 \
    -e BROWSER_POOL_SIZE=10 \
    unclecode/crawl4ai:latest

success "Forage stack containers are running."

# ------------------------------------------------------------------------------
# 8. Systemd service for Oathweaver (auto-start on boot)
# ------------------------------------------------------------------------------

step "Step 8/9 — Installing Oathweaver systemd service..."

# Use the venv Python set up in Step 4
PYTHON_BIN="$REPO_ROOT/.venv/bin/python"
SERVICE_FILE="/etc/systemd/system/oathweaver.service"

sudo tee "$SERVICE_FILE" >/dev/null <<UNIT
[Unit]
Description=Oathweaver Web UI
After=network.target ollama.service

[Service]
User=$USER
WorkingDirectory=$REPO_ROOT
Environment="OATHWEAVER_WEB_HOST=127.0.0.1"
Environment="OATHWEAVER_WEB_PORT=5050"
Environment="OATHWEAVER_HTTPS=true"
ExecStart=$PYTHON_BIN $REPO_ROOT/SourceCode/web_gui/app.py
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectKernelTunables=true
RestrictRealtime=true
ProtectSystem=strict
ReadWritePaths=$REPO_ROOT/Runtime $REPO_ROOT/Projects

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable oathweaver
success "Systemd service installed — Oathweaver will start automatically on boot."

# ------------------------------------------------------------------------------
# 9. Create a convenience start script for everyday use
# ------------------------------------------------------------------------------

step "Step 9/9 — Writing start_oathweaver.sh convenience script..."

START_SCRIPT="$REPO_ROOT/start_oathweaver.sh"
cat > "$START_SCRIPT" <<'STARTSCRIPT'
#!/usr/bin/env bash
# Quick start/restart script for Oathweaver and the forage stack.
# Run this any time you want to manually restart everything.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_CMD="docker"
! $DOCKER_CMD info &>/dev/null 2>&1 && DOCKER_CMD="sudo docker"

echo "Starting Ollama..."
sudo systemctl start ollama

echo "Starting forage stack (SearXNG + Crawl4AI)..."
$DOCKER_CMD start searxng crawl4ai 2>/dev/null || true

echo "Restarting Oathweaver..."
sudo systemctl restart oathweaver
sleep 2
sudo systemctl status oathweaver --no-pager -n 8

LOCAL_IP=$(hostname -I | awk '{print $1}')
echo ""
echo "  Open from this machine: http://127.0.0.1:5050"
echo "  Open from LAN:          http://$LOCAL_IP:5050"
STARTSCRIPT

chmod +x "$START_SCRIPT"
success "start_oathweaver.sh written."

# ------------------------------------------------------------------------------
# Done
# ------------------------------------------------------------------------------

echo ""
echo "======================================================================="
echo " Setup complete."
echo "======================================================================="
echo ""
echo " Start Oathweaver now:"
echo "   sudo systemctl start oathweaver"
echo ""
echo " Or use the convenience script:"
echo "   ./start_oathweaver.sh"
echo ""
echo " Open in browser:"
echo "   http://127.0.0.1:5050"
echo ""
echo " Forage stack ports:"
echo "   SearXNG   http://127.0.0.1:8080"
echo "   Crawl4AI  http://127.0.0.1:11235"
echo ""

if [[ "$GPU_TYPE" == "amd" ]]; then
echo " AMD GPU note:"
echo "   Log out and back in for ROCm group membership to take effect."
echo "   Verify GPU access with: rocm-smi"
echo ""
elif [[ "$GPU_TYPE" == "nvidia" ]]; then
echo " NVIDIA GPU note:"
echo "   A reboot may be required for CUDA to activate."
echo "   Verify GPU access with: nvidia-smi"
echo ""
fi

echo " Logs:"
echo "   sudo journalctl -u oathweaver -f    (Oathweaver)"
echo "   sudo journalctl -u ollama -f        (Ollama)"
echo "======================================================================="
