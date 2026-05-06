#!/bin/bash
# sync_release.sh
# Syncs this dev environment to Oathweaver-Release (public version).
# Respects .gitignore — Runtime credentials and personal data are never copied.

set -euo pipefail

SRC="/home/sc/Oathweaver"
DEST="/home/sc/Oathweaver-Release"

echo "=== Oathweaver Release Sync ==="
echo "  Source : $SRC"
echo "  Target : $DEST"
echo ""

mkdir -p "$DEST"

# ---------------------------------------------------------------------------
# 1. Sync files — honours .gitignore so Runtime/ secrets stay local
# ---------------------------------------------------------------------------
echo "[1/3] Syncing files..."

rsync -a --delete \
    --filter=':- .gitignore' \
    --exclude='.git/' \
    --exclude='.venv/' \
    --exclude='.claude/' \
    --exclude='*.db' \
    --exclude='*.db-shm' \
    --exclude='*.db-wal' \
    --exclude='*.log' \
    "$SRC/" "$DEST/"

# .gitignore itself is not self-excluded, copy it explicitly
cp "$SRC/.gitignore" "$DEST/.gitignore"

echo "  Done."
echo ""

# ---------------------------------------------------------------------------
# 2. Secrets safety scan — warn if anything slipped through
# ---------------------------------------------------------------------------
echo "[2/3] Scanning for leaked secrets..."

LEAKED=0

scan() {
    local label="$1"
    local pattern="$2"
    local hits
    hits=$(grep -rEn "$pattern" "$DEST" \
           --include="*.py" --include="*.js" --include="*.ts" \
           --include="*.json" --include="*.yaml" --include="*.yml" \
           --include="*.env" --include="*.cfg" --include="*.ini" \
           --include="*.txt" --include="*.sh" 2>/dev/null || true)
    if [[ -n "$hits" ]]; then
        echo "  WARNING [$label]:"
        echo "$hits" | head -5 | sed 's/^/    /'
        LEAKED=1
    fi
}

scan "Google API key"    'AIzaSy[0-9A-Za-z_-]{33}'
scan "Discord token"     '[A-Za-z0-9]{24}\.[A-Za-z0-9]{6}\.[A-Za-z0-9_-]{25,}'
scan "Slack token"       'xox[baprs]-[0-9A-Za-z-]+'
scan "GitHub token"      'gh[ps]_[0-9A-Za-z]{36}'
scan "OpenAI key"        'sk-[0-9A-Za-z]{20,}'
scan "Generic secret"    '(api_key|api_secret|secret_key|password|bot_token)\s*[=:]\s*"[^"]{8,}"'

if [[ $LEAKED -eq 0 ]]; then
    echo "  No secrets detected. You're clear."
else
    echo ""
    echo "  ACTION REQUIRED: Remove the items above before pushing!"
fi
echo ""

# ---------------------------------------------------------------------------
# 3. Git setup
# ---------------------------------------------------------------------------
echo "[3/3] Git status..."

if [[ ! -d "$DEST/.git" ]]; then
    echo "  No git repo found — initialising..."
    git -C "$DEST" init -b main
    git -C "$DEST" add -A
    git -C "$DEST" commit -m "Initial release sync"
    echo ""
    echo "  Connect to your public GitHub repo, then push:"
    echo "    git -C \"$DEST\" remote add origin <your-repo-url>"
    echo "    git -C \"$DEST\" push -u origin main"
else
    CHANGED=$(git -C "$DEST" status --porcelain 2>/dev/null | wc -l)
    if [[ $CHANGED -gt 0 ]]; then
        echo "  $CHANGED file(s) changed since last release commit."
        echo ""
        echo "  To publish:"
        echo "    cd \"$DEST\""
        echo "    git add -A"
        echo "    git commit -m 'Release update'"
        echo "    git push"
    else
        echo "  Release is already up to date with dev — nothing new to commit."
    fi
fi

echo ""
echo "=== Done ==="
