#!/usr/bin/env bash
# Move Docker Desktop VM disk (Docker.raw) from Mac internal disk to external SSD.
# - Assumes SSD is mounted at /Volumes/Doc-Bk-JJ-SDD-1-APFS
# - Safe to run multiple times; prints what it will do.
set -euo pipefail

SSD_BASE="/Volumes/Doc-Bk-JJ-SDD-1-APFS/DockerDesktop_raw"
LOCAL_VMS_DIR="$HOME/Library/Containers/com.docker.docker/Data/vms/0/data"
LOCAL_RAW="$LOCAL_VMS_DIR/Docker.raw"

step() { echo "[docker_move_to_ssd] $*"; }

step "Checking SSD mount..."
if [[ ! -d /Volumes/Doc-Bk-JJ-SDD-1-APFS ]]; then
  echo "SSD is not mounted at /Volumes/Doc-Bk-JJ-SDD-1-APFS" >&2
  exit 1
fi

step "Printing pre-move disk usage (root and Docker)..."
df -h / || true
du -sh "$LOCAL_VMS_DIR" 2>/dev/null || echo "No local vms/0/data dir yet"

echo
step "Quitting Docker Desktop (best effort)..."
osascript -e 'quit app "Docker"' >/dev/null 2>&1 || true
sleep 3

step "Ensuring target directory on SSD exists..."
mkdir -p "$SSD_BASE/DockerDesktop"

if [[ -f "$LOCAL_RAW" ]]; then
  step "Moving local Docker.raw to SSD..."
  mv "$LOCAL_RAW" "$SSD_BASE/DockerDesktop/"
else
  step "No local Docker.raw found at $LOCAL_RAW (maybe already moved)."
fi

step "Summary of Docker data on SSD:"
du -sh "$SSD_BASE" "$SSD_BASE/DockerDesktop" 2>/dev/null || true

cat << MSG

Next step (manual, in Docker Desktop UI):
  1) Open Docker Desktop → Settings → Resources → Advanced.
  2) Set "Disk image location" to:
       $SSD_BASE
  3) Click "Apply & Restart".

After Docker restarts, verify that no new Docker.raw appears under:
  $LOCAL_VMS_DIR

MSG

step "Post-move root disk usage:"
df -h /
