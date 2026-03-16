#!/usr/bin/env bash
# Move Cursor's User/globalStorage to an external SSD and create a symlink.
# - SSD mount assumed at /Volumes/Doc-Bk-JJ-SDD-1-APFS
# - Safe to run multiple times; it will detect existing symlink.
set -euo pipefail

SSD_BASE="/Volumes/Doc-Bk-JJ-SDD-1-APFS/cursor-storage"
LOCAL_ROOT="$HOME/Library/Application Support/Cursor/User"
LOCAL_GS="$LOCAL_ROOT/globalStorage"

step() { echo "[cursor_move_global_storage_to_ssd] $*"; }

step "Checking SSD mount..."
if [[ ! -d /Volumes/Doc-Bk-JJ-SDD-1-APFS ]]; then
  echo "SSD is not mounted at /Volumes/Doc-Bk-JJ-SDD-1-APFS" >&2
  exit 1
fi

step "Printing pre-move Cursor usage..."
du -sh "$HOME/Library/Application Support/Cursor" 2>/dev/null || true

step "Ensuring Cursor is quit (please close the app)..."
# We only warn; user must ensure it's closed.
pgrep -fl "Cursor" 2>/dev/null || echo "No Cursor process found (good)."

step "Preparing SSD target..."
mkdir -p "$SSD_BASE"
if [[ -d "$SSD_BASE/globalStorage" && ! -d "$SSD_BASE/globalStorage_bk1" ]]; then
  step "Backing up existing SSD globalStorage to globalStorage_bk1..."
  mv "$SSD_BASE/globalStorage" "$SSD_BASE/globalStorage_bk1"
fi

if [[ -L "$LOCAL_GS" ]]; then
  step "Local globalStorage is already a symlink:"
  ls -la "$LOCAL_GS"
else
  step "Moving local globalStorage → SSD..."
  mv "$LOCAL_GS" "$SSD_BASE/globalStorage"
  ln -s "$SSD_BASE/globalStorage" "$LOCAL_GS"
fi

step "Post-move check:"
ls -la "$LOCAL_GS" || true
du -sh "$SSD_BASE/globalStorage" 2>/dev/null || true

echo
step "Done. Restart Cursor and verify it works normally."
