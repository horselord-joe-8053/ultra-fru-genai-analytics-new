#!/usr/bin/env bash
# remove_tm_snapshots.sh
#
# Delete local Time Machine (APFS) snapshots while keeping the newest N entries.
#
# IMPORTANT:
# - This only deletes *local* snapshots created on the internal disk.
# - Your remote/backup Time Machine history on the SSD/HDD destination is not directly modified.
# - This is potentially destructive. Use with care.
#
# Usage:
#   ./remove_tm_snapshots.sh --keep-last <num>
#
# Example (keep newest 2 snapshots, delete the rest):
#   ./remove_tm_snapshots.sh --keep-last 2
#
# Notes:
# - Requires `sudo` for deleting snapshots.
# - Snapshot dates are taken from:
#     tmutil listlocalsnapshotdates /
#   and deletions are performed using:
#     tmutil deletelocalsnapshots <snapshot_date>
#   (fallback to tmutil deletelocalsnapshots / <snapshot_date> if needed).
#
# What this script prints:
# - Free disk space on `/` before and after
# - Which snapshot dates were deleted
# - Approximate space reclaimed (based on `df -k /` availability)

set -euo pipefail

KEEP_LAST_DEFAULT=2
KEEP_LAST="$KEEP_LAST_DEFAULT"

usage() {
  cat <<'EOF'
Usage:
  remove_tm_snapshots.sh --keep-last <num>

Description:
  Deletes local Time Machine snapshots on internal disk, keeping the newest N snapshot dates.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ "${1:-}" != "--keep-last" ]]; then
  echo "Error: missing --keep-last <num> argument" >&2
  usage
  exit 1
fi

KEEP_LAST="${2:-$KEEP_LAST_DEFAULT}"
if ! [[ "$KEEP_LAST" =~ ^[0-9]+$ ]] || [[ "$KEEP_LAST" -lt 1 ]]; then
  echo "Error: --keep-last must be a positive integer, got: $KEEP_LAST" >&2
  exit 1
fi

get_avail_kb() {
  # df output is: Filesystem Size Used Avail Capacity iused ifree %iused Mounted on
  df -k / | awk 'NR==2 {print $4}'
}

kb_to_gb() {
  # prints with 2 decimals
  awk -v kb="$1" 'BEGIN { printf "%.2f", kb/1024/1024 }'
}

echo "==> Listing local Time Machine snapshot dates..."
mapfile -t dates < <(tmutil listlocalsnapshotdates / 2>/dev/null || true)

if [[ "${#dates[@]}" -le "$KEEP_LAST" ]]; then
  echo "Nothing to delete."
  echo "Found ${#dates[@]} snapshot(s); keep-last is ${KEEP_LAST}."
  exit 0
fi

echo "Found ${#dates[@]} local snapshot dates. Will keep the newest ${KEEP_LAST}."

echo
echo "==> Space before"
before_kb="$(get_avail_kb)"
before_gb="$(kb_to_gb "$before_kb")"
df -h / | tail -1 || true
echo "Free (Avail) before: ${before_gb} GB"

echo
echo "==> Computing deletions (oldest first)..."
to_delete_count=$(( ${#dates[@]} - KEEP_LAST ))
echo "Will delete ${to_delete_count} snapshot(s):"

delete_dates=("${dates[@]:0:$to_delete_count}")

for d in "${delete_dates[@]}"; do
  echo "  - $d"
done

echo
echo "==> Deleting snapshots (requires sudo)..."
for d in "${delete_dates[@]}"; do
  echo "Deleting snapshot: $d"
  if sudo tmutil deletelocalsnapshots "$d" >/dev/null 2>&1; then
    echo "  OK (tmutil deletelocalsnapshots $d)"
  elif sudo tmutil deletelocalsnapshots / "$d" >/dev/null 2>&1; then
    echo "  OK (tmutil deletelocalsnapshots / $d)"
  else
    echo "  FAILED to delete snapshot: $d" >&2
    exit 1
  fi
done

echo
echo "==> Space after (wait a moment for APFS to update)..."
sleep 2

after_kb="$(get_avail_kb)"
after_gb="$(kb_to_gb "$after_kb")"
df -h / | tail -1 || true
echo "Free (Avail) after: ${after_gb} GB"

saved_kb="$(( after_kb - before_kb ))"
saved_gb="$(kb_to_gb "$saved_kb")"

echo
echo "==> Approximate space reclaimed on /:"
echo "  Saved: ${saved_gb} GB (df avail_kb delta)"

echo
echo "==> Remaining local snapshot dates:"
tmutil listlocalsnapshotdates / 2>/dev/null || true

