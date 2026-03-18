#!/usr/bin/env bash
# usage_cursor_docker_chrome.sh
#
# Print disk usage for the items we migrated off the internal disk:
# - Cursor (internal Application Support + SSD globalStorage)
# - Docker Desktop (internal docker metadata + SSD Docker.raw)
# - Chrome cache (internal symlink + SSD cache target)
#
# This is a *verification* script you can run occasionally to ensure the SSD is still the backing store.
#
# Usage:
#   ./usage_cursor_docker_chrome.sh
#
# Optional env vars:
#   SSD_MOUNT=/Volumes/Doc-Bk-JJ-SDD-1-APFS
#
# Output includes:
# - df free space for `/` and SSD mount
# - Cursor internal size breakdown (top dirs)
# - Cursor globalStorage symlink and SSD target size
# - Docker sizes (internal + SSD disk image)
# - Chrome cache symlink target and sizes

set -euo pipefail

SSD_MOUNT="${SSD_MOUNT:-/Volumes/Doc-Bk-JJ-SDD-1-APFS}"
HOME_DIR="$HOME"

print_section() {
  echo
  echo "=== $* ==="
}

human_du() {
  local path="$1"
  if [[ -e "$path" ]]; then
    du -sh "$path" 2>/dev/null | awk '{print $1}'
  else
    echo "0B (missing)"
  fi
}

if [[ ! -d "$SSD_MOUNT" ]]; then
  echo "Warning: SSD mount not found: $SSD_MOUNT" >&2
fi

print_section "Disk free space"
df -h / | tail -1 || true
if [[ -d "$SSD_MOUNT" ]]; then
  df -h "$SSD_MOUNT" | tail -1 || true
fi

print_section "Cursor disk usage"
CURSOR_INTERNAL_ROOT="$HOME_DIR/Library/Application Support/Cursor"
CURSOR_INTERNAL_USER_ROOT="$CURSOR_INTERNAL_ROOT/User"
CURSOR_INTERNAL_GLOBALSTORAGE="$CURSOR_INTERNAL_USER_ROOT/globalStorage"
CURSOR_SSD_BASE="$SSD_MOUNT/cursor-storage"
CURSOR_SSD_GLOBALSTORAGE="$CURSOR_SSD_BASE/globalStorage"

echo "Cursor internal root: $CURSOR_INTERNAL_ROOT -> $(human_du "$CURSOR_INTERNAL_ROOT")"
echo "Cursor internal globalStorage symlink (if any):"
if [[ -L "$CURSOR_INTERNAL_GLOBALSTORAGE" ]]; then
  readlink "$CURSOR_INTERNAL_GLOBALSTORAGE" || true
  echo "Cursor SSD globalStorage: $CURSOR_SSD_GLOBALSTORAGE -> $(human_du "$CURSOR_SSD_GLOBALSTORAGE")"
else
  echo "  $CURSOR_INTERNAL_GLOBALSTORAGE is not a symlink (check manually)."
  echo "  Actual on internal disk: $(human_du "$CURSOR_INTERNAL_GLOBALSTORAGE")"
fi

echo
echo "Cursor internal Application Support top dirs:"
du -sh "$CURSOR_INTERNAL_ROOT"/* 2>/dev/null | sort -hr | head -15 || true

print_section "Docker Desktop disk usage"
DOCKER_INTERNAL_ROOT="$HOME_DIR/Library/Containers/com.docker.docker"
DOCKER_INTERNAL_VMS_DIR="$DOCKER_INTERNAL_ROOT/Data/vms/0/data"

# Docker’s disk image location may be one of a few nested paths on SSD depending on how it was configured.
DOCKER_SSD_CANDIDATES=(
  "$SSD_MOUNT/DockerDesktop_raw"
  "$SSD_MOUNT/DockerDesktop_raw/DockerDesktop"
  "$SSD_MOUNT/DockerDesktop_raw/DockerDesktop/DockerDesktop"
  "$SSD_MOUNT/DockerDesktop_raw/DockerDesktop/DockerDesktop/Docker.raw"
  "$SSD_MOUNT/DockerDesktop_raw/DockerDesktop/Docker.raw"
  "$SSD_MOUNT/DockerDesktop_raw/DockerDesktop/DockerDesktop/Docker.raw"
)

echo "Docker internal metadata root: $(human_du "$DOCKER_INTERNAL_ROOT")"
if [[ -d "$DOCKER_INTERNAL_VMS_DIR" ]]; then
  echo "Docker internal vms/0/data: $(human_du "$DOCKER_INTERNAL_VMS_DIR")"
  if [[ -f "$DOCKER_INTERNAL_VMS_DIR/Docker.raw" ]]; then
    echo "Docker.raw still exists on internal disk: $(human_du "$DOCKER_INTERNAL_VMS_DIR/Docker.raw")"
  else
    echo "Docker.raw not present in internal vms/0/data (good)."
  fi
else
  echo "Docker internal vms dir missing: $DOCKER_INTERNAL_VMS_DIR"
fi

echo
echo "Docker SSD disk image candidates (Docker.raw sizes):"
found_any=0
for c in "${DOCKER_SSD_CANDIDATES[@]}"; do
  if [[ -f "$c" && "$c" == *"Docker.raw"* ]]; then
    found_any=1
    echo "  $c -> $(human_du "$c")"
  fi
done
if [[ "$found_any" -eq 0 ]]; then
  # fallback: known “base” directory size
  echo "  Could not locate Docker.raw via known SSD candidates. You may need to check Docker settings."
fi

print_section "Chrome cache disk usage"
CHROME_INTERNAL_CACHE_LINK="$HOME_DIR/Library/Caches/Google"
CHROME_SSD_BASE="$SSD_MOUNT/caches/Chrome"
CHROME_SSD_GOOGLE_DEFAULT="$CHROME_SSD_BASE/Google"
CHROME_SSD_GOOGLE_MOVED="$CHROME_SSD_BASE/Google_moved"

echo "Chrome internal cache path: $CHROME_INTERNAL_CACHE_LINK"
symlink_target=""
if [[ -L "$CHROME_INTERNAL_CACHE_LINK" ]]; then
  echo "  Symlink target:"
  symlink_target="$(readlink "$CHROME_INTERNAL_CACHE_LINK" 2>/dev/null || true)"
  echo "  $symlink_target"
fi

echo
echo "Chrome internal cache apparent size (no deref):"
du -sh -P "$CHROME_INTERNAL_CACHE_LINK" 2>/dev/null || true

echo
echo "Chrome SSD cache (expected target) size:"
if [[ -n "$symlink_target" ]]; then
  # Resolve relative targets (should be absolute in our case, but keep it robust).
  if [[ "$symlink_target" == /* ]]; then
    target_abs="$symlink_target"
  else
    target_abs="$(cd "$(dirname "$CHROME_INTERNAL_CACHE_LINK")" && pwd)/$symlink_target"
  fi
  echo "  symlink target -> $target_abs -> $(human_du "$target_abs")"
else
  echo "  (no symlink detected) Default candidates:"
  echo "    $CHROME_SSD_GOOGLE_DEFAULT -> $(human_du "$CHROME_SSD_GOOGLE_DEFAULT")"
  echo "    $CHROME_SSD_GOOGLE_MOVED -> $(human_du "$CHROME_SSD_GOOGLE_MOVED")"
fi

print_section "DONE"
echo "Interpretation hints:"
echo "  - Cursor/Chrome/Docker should show large sizes on the SSD targets."
echo "  - Internal disk should remain mostly small for these paths."

