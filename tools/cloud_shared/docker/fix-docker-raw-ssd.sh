#!/usr/bin/env bash
# Fix corrupted Docker.raw on SSD (e.g. after cp was killed mid-copy).
# Run with Docker Desktop QUIT.
set -euo pipefail

SSD_BASE="/Volumes/Doc-Bk-JJ-SDD-1-APFS/DockerDesktop_raw/DockerDesktop"
ACTIVE="${SSD_BASE}/DockerDesktop/Docker.raw"   # path Docker uses (nested)
BACKUP="${SSD_BASE}/Docker.raw"                # other copy (may be more complete)

if [[ ! -d /Volumes/Doc-Bk-JJ-SDD-1-APFS ]]; then
  echo "SSD not mounted at /Volumes/Doc-Bk-JJ-SDD-1-APFS"
  exit 1
fi

echo "==> Removing corrupted active Docker.raw (Docker must be quit)"
rm -f "$ACTIVE"

echo "==> Replacing with backup copy (if present)"
if [[ -f "$BACKUP" ]]; then
  mkdir -p "$(dirname "$ACTIVE")"
  cp -p "$BACKUP" "$ACTIVE"
  echo "Done. Start Docker Desktop and see if it boots."
else
  echo "No backup at $BACKUP. Docker will create a new empty disk on next start."
fi
