#!/usr/bin/env bash
# ============================================================
# clean_uninstall_dockerdesktop.sh
#
# Purpose
#   Completely remove Docker Desktop from macOS for a clean reinstall.
#   Based on docs/todos/TODO_Reinstall_Docker_Clean.md
#
# What it does
#   Phase A: Quit and kill Docker processes
#   Phase B: Uninstall app + privileged helpers (sudo)
#   Phase C: Remove user data (~/Library, ~/.docker)
#   Phase D: Remove disk image on SSD (configurable path)
#   Phase E: Verify cleanup
#
# Usage
#   chmod +x tools/cloud_shared/docker/clean_uninstall_dockerdesktop.sh
#   ./tools/cloud_shared/docker/clean_uninstall_dockerdesktop.sh
#   ./tools/cloud_shared/docker/clean_uninstall_dockerdesktop.sh --non-interactive
#
# Options
#   --non-interactive    Skip all prompts; assume yes (use with caution)
#   --skip-ssd-cleanup   Skip Phase D (SSD disk image removal)
#   --help               Show this help
#
# For full non-interactive (Phases B–D; Phase C may need sudo on some macOS):
#   sudo $0 --non-interactive
#
# Optional environment variables
#   DOCKER_SSD_PATH    Disk image location (default: /Volumes/Doc-Bk-JJ-SDD-1-APFS/DockerDesktop_raw)
#   SKIP_SSD_CLEANUP   Set to 1 to skip Phase D (SSD removal)
#   NON_INTERACTIVE    Set to 1 to skip all prompts (use with caution)
# ============================================================

set -euo pipefail

# --- Config ---
DOCKER_SSD_PATH="${DOCKER_SSD_PATH:-/Volumes/Doc-Bk-JJ-SDD-1-APFS/DockerDesktop_raw}"
SKIP_SSD_CLEANUP="${SKIP_SSD_CLEANUP:-0}"
NON_INTERACTIVE="${NON_INTERACTIVE:-0}"
# When run with sudo, target the invoking user's home
TARGET_HOME="${SUDO_USER:+$(eval echo ~$SUDO_USER)}"
TARGET_HOME="${TARGET_HOME:-$HOME}"

# --- Parse args ---
while [[ $# -gt 0 ]]; do
  case "$1" in
    --non-interactive) NON_INTERACTIVE=1; shift ;;
    --skip-ssd-cleanup) SKIP_SSD_CLEANUP=1; shift ;;
    --help)
      echo "Usage: $0 [--non-interactive] [--skip-ssd-cleanup] [--help]"
      echo "  --non-interactive    Skip all prompts (assume yes)"
      echo "  --skip-ssd-cleanup   Skip Phase D (SSD disk image removal)"
      exit 0
      ;;
    *) echo "[ERROR] Unknown option: $1" >&2; exit 1 ;;
  esac
done

# --- Logging ---
_log()  { echo "[$(date '+%H:%M:%S')] $*"; }
_info() { _log "INFO  $*"; }
_warn() { _log "WARN  $*"; }
_err()  { _log "ERROR $*"; }
_ok()   { _log "OK    $*"; }

# --- Heartbeat (runs in background, prints every N seconds) ---
_heartbeat_pid=""
_heartbeat_start() {
  local interval="${1:-5}"
  local label="${2:-Working}"
  ( while true; do sleep "$interval"; _log "HEARTBEAT $label..."; done ) &
  _heartbeat_pid=$!
  disown 2>/dev/null || true
}
_heartbeat_stop() {
  if [[ -n "${_heartbeat_pid}" ]]; then
    kill "$_heartbeat_pid" 2>/dev/null || true
    wait "$_heartbeat_pid" 2>/dev/null || true
  fi
  _heartbeat_pid=""
}

# --- Prompt ---
_confirm() {
  local msg="$1"
  local default="${2:-n}"
  if [[ "${NON_INTERACTIVE}" == "1" ]]; then
    _info "NON_INTERACTIVE=1, assuming yes: $msg"
    return 0
  fi
  if [[ "$default" == "y" ]]; then
    read -r -p "$msg [Y/n]: " ans
  else
    read -r -p "$msg [y/N]: " ans
  fi
  ans_lower="$(echo "${ans:-}" | tr '[:upper:]' '[:lower:]')"
  case "$ans_lower" in
    y|yes) return 0 ;;
    "") [[ "$default" == "y" ]] && return 0 || return 1 ;;
    *) return 1 ;;
  esac
}

# --- Phase A: Quit and kill processes ---
_phase_a() {
  _info "═══ Phase A: Quit and kill Docker processes ═══"

  _info "Asking Docker Desktop to quit..."
  osascript -e 'quit app "Docker"' 2>/dev/null || true
  _heartbeat_start 3 "Waiting for Docker to quit"
  sleep 3
  _heartbeat_stop
  _ok "Quit signal sent"

  _info "Force-killing Docker processes..."
  pkill -9 -f "com.docker.backend" 2>/dev/null || true
  pkill -9 -f "com.docker.virtualization" 2>/dev/null || true
  pkill -9 -f "com.docker.build" 2>/dev/null || true
  sleep 2
  _ok "Processes killed"

  _info "Killing privileged helper (sudo required)..."
  if sudo -n true 2>/dev/null; then
    sudo pkill -9 -f "com.docker.vmnetd" 2>/dev/null || true
    _ok "Privileged helper killed"
  elif [[ "${NON_INTERACTIVE}" == "1" ]]; then
    _warn "Passwordless sudo not available; vmnetd may still run. Run manually: sudo pkill -9 -f com.docker.vmnetd"
  else
    _warn "Sudo not available; you may need to run: sudo pkill -9 -f com.docker.vmnetd"
    if _confirm "Run sudo pkill now? (will prompt for password)"; then
      sudo pkill -9 -f "com.docker.vmnetd" 2>/dev/null || true
      _ok "Privileged helper killed"
    fi
  fi
  sleep 1

  _info "Verifying no process holds Docker.raw..."
  if lsof 2>/dev/null | grep -i Docker.raw; then
    _warn "Some process still holds Docker.raw. Retry Phase A or reboot."
  else
    _ok "No process holds Docker.raw"
  fi

  _ok "Phase A complete"
}

# --- Phase B: Uninstall application ---
_phase_b() {
  _info "═══ Phase B: Uninstall application ═══"

  if [[ ! -d /Applications/Docker.app ]]; then
    _ok "Docker.app not found, skipping"
    return 0
  fi

  if [[ "${NON_INTERACTIVE}" == "1" ]] && [[ "${SUDO_AVAILABLE:-0}" == "0" ]]; then
    _warn "Skipping Phase B (no passwordless sudo in non-interactive mode)"
    return 0
  fi

  if ! _confirm "Remove /Applications/Docker.app? (requires sudo)"; then
    _warn "Skipping Phase B"
    return 0
  fi

  _info "Removing Docker.app..."
  sudo rm -rf /Applications/Docker.app
  _ok "Docker.app removed"

  _info "Removing privileged helpers and launch daemons..."
  sudo rm -f /Library/PrivilegedHelperTools/com.docker.socket 2>/dev/null || true
  sudo rm -f /Library/PrivilegedHelperTools/com.docker.vmnetd 2>/dev/null || true
  sudo rm -f /Library/LaunchDaemons/com.docker.socket.plist 2>/dev/null || true
  sudo rm -f /Library/LaunchDaemons/com.docker.vmnetd.plist 2>/dev/null || true
  _ok "Helpers removed"

  _info "Unloading launch daemons..."
  sudo launchctl unload /Library/LaunchDaemons/com.docker.vmnetd.plist 2>/dev/null || true
  _ok "Phase B complete"
}

# --- Phase C: Remove user data ---
_phase_c() {
  _info "═══ Phase C: Remove user data ═══"

  if ! _confirm "Remove ~/Library/Containers/com.docker.docker, group.com.docker, ~/.docker?"; then
    _warn "Skipping Phase C"
    return 0
  fi

  _info "Removing app container data..."
  if rm -rf "$TARGET_HOME/Library/Containers/com.docker.docker" 2>/dev/null; then
    _ok "App container data removed"
  elif [[ "${SUDO_AVAILABLE:-0}" == "1" ]]; then
    _warn "rm failed (Operation not permitted); trying sudo..."
    sudo rm -rf "$TARGET_HOME/Library/Containers/com.docker.docker" && _ok "App container data removed" || _warn "sudo rm also failed"
  else
    _warn "rm failed (Operation not permitted). Run: sudo rm -rf ~/Library/Containers/com.docker.docker"
  fi

  _info "Removing group container..."
  if ! rm -rf "$TARGET_HOME/Library/Group Containers/group.com.docker" 2>/dev/null; then
    if [[ "${SUDO_AVAILABLE:-0}" == "1" ]]; then
      sudo rm -rf "$TARGET_HOME/Library/Group Containers/group.com.docker"
    else
      _warn "rm failed. Run: sudo rm -rf \"\$HOME/Library/Group Containers/group.com.docker\""
    fi
  fi
  _ok "Group container removed"

  _info "Removing CLI config..."
  rm -rf "$TARGET_HOME/.docker" 2>/dev/null || true
  _ok "CLI config removed"

  _info "Removing Docker caches..."
  rm -rf "$TARGET_HOME/Library/Caches/com.docker.docker" 2>/dev/null || true
  _ok "Phase C complete"
}

# --- Phase D: Remove disk image on SSD ---
_phase_d() {
  _info "═══ Phase D: Remove disk image on SSD ═══"

  if [[ "${SKIP_SSD_CLEANUP}" == "1" ]]; then
    _warn "SKIP_SSD_CLEANUP=1, skipping Phase D"
    return 0
  fi

  if [[ ! -d "$(dirname "$DOCKER_SSD_PATH")" ]]; then
    _warn "SSD not mounted at $(dirname "$DOCKER_SSD_PATH"), skipping Phase D"
    return 0
  fi

  if [[ ! -e "$DOCKER_SSD_PATH" ]]; then
    _ok "SSD path $DOCKER_SSD_PATH does not exist, nothing to remove"
    return 0
  fi

  _info "SSD path: $DOCKER_SSD_PATH"
  if ! _confirm "Remove Docker disk image and backup from SSD? (all images/containers lost)"; then
    _warn "Skipping Phase D"
    return 0
  fi

  _info "Removing DockerDesktop folder and backup..."
  rm -rf "${DOCKER_SSD_PATH}/DockerDesktop"
  rm -f "${DOCKER_SSD_PATH}/Docker.raw.backup"
  _ok "SSD data removed"

  _info "Removing DockerDesktop_raw folder..."
  rm -rf "$DOCKER_SSD_PATH"
  _ok "Phase D complete"
}

# --- Phase E: Verify ---
_phase_e() {
  _info "═══ Phase E: Verify cleanup ═══"

  local failed=0

  _info "Checking for Docker Desktop processes..."
  if pgrep -fl "com\.docker\.(backend|vmnetd|virtualization|build)" 2>/dev/null || pgrep -fl "Docker\.app" 2>/dev/null; then
    _warn "Docker Desktop processes still running"
    failed=1
  else
    _ok "No Docker Desktop processes"
  fi

  _info "Checking paths..."
  [[ -d /Applications/Docker.app ]] && { _warn "Docker.app still exists"; failed=1; } || _ok "Docker.app gone"
  [[ -d "$TARGET_HOME/Library/Containers/com.docker.docker" ]] && { _warn "Container data still exists"; failed=1; } || _ok "Container data gone"
  [[ -d "$TARGET_HOME/.docker" ]] && { _warn "~/.docker still exists"; failed=1; } || _ok "~/.docker gone"
  if [[ -d "$(dirname "$DOCKER_SSD_PATH")" ]] && [[ -e "$DOCKER_SSD_PATH" ]]; then
    _warn "SSD path still exists: $DOCKER_SSD_PATH"
    failed=1
  else
    _ok "SSD path gone or not mounted"
  fi

  if [[ $failed -eq 1 ]]; then
    _warn "Some checks failed; review output above"
    return 1
  fi
  _ok "Phase E complete — cleanup verified"
  return 0
}

# --- Main ---
main() {
  _info "═══════════════════════════════════════════════════════"
  _info "Docker Desktop Clean Uninstall"
  _info "Based on docs/todos/TODO_Reinstall_Docker_Clean.md"
  _info "═══════════════════════════════════════════════════════"
  _info "DOCKER_SSD_PATH=$DOCKER_SSD_PATH"
  _info "SKIP_SSD_CLEANUP=$SKIP_SSD_CLEANUP"
  _info "NON_INTERACTIVE=$NON_INTERACTIVE"
  _info ""

  SUDO_AVAILABLE=0
  [[ "$(id -u)" == "0" ]] && SUDO_AVAILABLE=1 || sudo -n true 2>/dev/null && SUDO_AVAILABLE=1 || true
  if [[ "${NON_INTERACTIVE}" == "1" ]] && [[ "$SUDO_AVAILABLE" == "0" ]]; then
    _warn "Non-interactive mode but passwordless sudo not available."
    _warn "Phases B (app removal) and D (SSD cleanup) will be skipped."
    _warn "To run fully non-interactive: sudo $0 --non-interactive"
  fi

  if ! _confirm "Proceed with full Docker Desktop removal? (all images, containers, data will be lost)" "n"; then
    _info "Aborted by user"
    exit 0
  fi

  _phase_a
  _phase_b
  _phase_c
  _phase_d
  _phase_e

  _info ""
  _info "═══════════════════════════════════════════════════════"
  _info "Clean uninstall complete. Next steps:"
  _info "  1. Download Docker Desktop from https://www.docker.com/products/docker-desktop/"
  _info "  2. Install; do NOT launch yet"
  _info "  3. Create: mkdir -p $DOCKER_SSD_PATH"
  _info "  4. Launch Docker → Settings → Resources"
  _info "  5. Set Disk image location: $DOCKER_SSD_PATH"
  _info "  6. Set Disk usage limit: 64 GB or higher"
  _info "  7. Apply & restart"
  _info "═══════════════════════════════════════════════════════"
}

main "$@"
