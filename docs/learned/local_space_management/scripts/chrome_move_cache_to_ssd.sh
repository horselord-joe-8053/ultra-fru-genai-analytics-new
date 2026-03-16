#!/usr/bin/env bash
# Move Chrome's cache (~/Library/Caches/Google) to an external SSD via symlink.
# - SSD assumed at /Volumes/Doc-Bk-JJ-SDD-1-APFS
# - Run with Chrome fully quit.
set -euo pipefail

SSD_BASE="/Volumes/Doc-Bk-JJ-SDD-1-APFS/caches/Chrome"
LOCAL_CACHE="$HOME/Library/Caches/Google"

step() { echo "[chrome_move_cache_to_ssd] $*"; }

step "Checking SSD mount..."
if [[ ! -d /Volumes/Doc-Bk-JJ-SDD-1-APFS ]]; then
  echo "SSD is not mounted at /Volumes/Doc-Bk-JJ-SDD-1-APFS" >&2
  exit 1
fi

step "Pre-move disk usage (root and Chrome cache)..."
df -h /
if [[ -e "$LOCAL_CACHE" ]]; then
  du -sh "$LOCAL_CACHE" 2>/dev/null || true
else
  echo "No local ~/Library/Caches/Google directory yet."
fi

step "Ensuring Chrome is not running..."
if pgrep -fl "Chrome|Google Chrome" >/dev/null 2>&1; then
  echo "Chrome appears to be running. Please quit it completely and rerun." >&2
  exit 1
fi

step "Preparing SSD target at $SSD_BASE..."
mkdir -p "$SSD_BASE"

if [[ -L "$LOCAL_CACHE" ]]; then
  step "Local cache is already a symlink:"
  ls -la "$LOCAL_CACHE"
else
  if [[ -d "$SSD_BASE/Google" ]]; then
    step "Backing up existing SSD Google cache to Google_pre_migration_$(date +%Y%m%d_%H%M%S)..."
    mv "$SSD_BASE/Google" "$SSD_BASE/Google_pre_migration_$(date +%Y%m%d_%H%M%S)"
  fi

  if [[ -d "$LOCAL_CACHE" ]]; then
    step "Moving local cache → SSD..."
    mv "$LOCAL_CACHE" "$SSD_BASE/Google"
  else
    step "No local ~/Library/Caches/Google directory found; creating empty SSD folder..."
    mkdir -p "$SSD_BASE/Google"
  fi

  ln -s "$SSD_BASE/Google" "$LOCAL_CACHE"
fi

step "Post-move verification:"
ls -la "$LOCAL_CACHE" || true

du -sh "$SSD_BASE/Google" 2>/dev/null || true

echo
step "Post-move root disk usage:"
df -h /

step "Done. Start Chrome; it will now cache under the SSD path via the symlink."
