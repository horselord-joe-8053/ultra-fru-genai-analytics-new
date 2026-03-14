# TODO: Reinstall Docker Desktop Cleanly on MacBook Air

**Purpose:** Completely remove Docker Desktop and reinstall a fresh copy.  
**Context:** Current setup has nested `DockerDesktop/DockerDesktop/Docker.raw` path, disk limit ~15.64 GB (nearly full), and prior relocation to external SSD.

---

## 1. Current Configuration Snapshot

| Item | Value |
|------|-------|
| **Docker version** | 29.2.1 (Client) |
| **App location** | `/Applications/Docker.app` |
| **Disk image path** | `/Volumes/Doc-Bk-JJ-SDD-1-APFS/DockerDesktop_raw/DockerDesktop/DockerDesktop/Docker.raw` |
| **Disk image size** | 16 GB (15.64 GB limit, ~15 GB used) |
| **SSD volume** | `Doc-Bk-JJ-SDD-1-APFS` (333 GB, ~91 GB free) |
| **Backup file** | `Docker.raw.backup` (~926 MB) at same SSD path |

### Key paths to remove

| Path | Purpose |
|------|---------|
| `/Applications/Docker.app` | Docker Desktop application |
| `~/Library/Containers/com.docker.docker/` | App container data, settings, VM state |
| `~/Library/Group Containers/group.com.docker/` | Shared settings, auth |
| `~/.docker/` | CLI config, contexts |
| `/Volumes/Doc-Bk-JJ-SDD-1-APFS/DockerDesktop_raw/` | Disk image + backup on SSD |
| `/Library/PrivilegedHelperTools/com.docker.vmnetd` | Network helper (root) |
| `/Library/LaunchDaemons/com.docker.*` | Launch daemons |

---

## 2. Pre-removal Checklist

- [ ] **Quit Docker Desktop** – Menu bar → Docker icon → Quit
- [ ] **Stop all containers** – `docker stop $(docker ps -aq)` (if Docker still runs)
- [ ] **Unmount SSD?** – Optional: unmount `Doc-Bk-JJ-SDD-1-APFS` after quit so no process holds `Docker.raw`
- [ ] **Backup** – No need to backup `Docker.raw`; you are doing a clean reinstall. Images/containers will be lost.

---

## 3. Removal Steps

### <span style="color:#e74c3c">Phase A: Quit and kill processes</span>

```bash
# 1. Quit Docker Desktop (best effort)
osascript -e 'quit app "Docker"' 2>/dev/null || true
sleep 3

# 2. Force-kill Docker processes (handles respawn)
pkill -9 -f "com.docker.backend" 2>/dev/null || true
pkill -9 -f "com.docker.virtualization" 2>/dev/null || true
pkill -9 -f "com.docker.build" 2>/dev/null || true
sleep 2

# 3. Kill privileged helper (requires sudo)
sudo pkill -9 -f "com.docker.vmnetd" 2>/dev/null || true
sleep 1

# 4. Verify no process holds Docker.raw
lsof 2>/dev/null | grep -i Docker.raw || echo "None (good)"
```

### <span style="color:#e67e22">Phase B: Uninstall application</span>

```bash
# 5. Remove Docker app
sudo rm -rf /Applications/Docker.app

# 6. Remove privileged helper and launch daemons
sudo rm -f /Library/PrivilegedHelperTools/com.docker.socket
sudo rm -f /Library/PrivilegedHelperTools/com.docker.vmnetd
sudo rm -f /Library/LaunchDaemons/com.docker.socket.plist
sudo rm -f /Library/LaunchDaemons/com.docker.vmnetd.plist

# 7. Unload launch daemons (if still loaded)
sudo launchctl unload /Library/LaunchDaemons/com.docker.vmnetd.plist 2>/dev/null || true
```

### <span style="color:#f39c12">Phase C: Remove user data</span>

```bash
# 8. Remove app container data (settings, VM state, logs)
rm -rf ~/Library/Containers/com.docker.docker

# 9. Remove group container (shared settings)
rm -rf ~/Library/Group\ Containers/group.com.docker

# 10. Remove CLI config
rm -rf ~/.docker

# 11. Remove Docker caches (optional)
rm -rf ~/Library/Caches/com.docker.docker 2>/dev/null || true
```

### <span style="color:#27ae60">Phase D: Remove disk image on SSD</span>

> **Ensure SSD is mounted.** Run only after Phases A–C.

```bash
# 12. Remove Docker disk image and backup from SSD
rm -rf /Volumes/Doc-Bk-JJ-SDD-1-APFS/DockerDesktop_raw/DockerDesktop
rm -f /Volumes/Doc-Bk-JJ-SDD-1-APFS/DockerDesktop_raw/Docker.raw.backup

# 13. Remove parent folder if empty
rmdir /Volumes/Doc-Bk-JJ-SDD-1-APFS/DockerDesktop_raw 2>/dev/null || true
```

### <span style="color:#3498db">Phase E: Verify cleanup</span>

```bash
# 14. Confirm no Docker processes
pgrep -fl docker || echo "None (good)"

# 15. Confirm paths gone
ls /Applications/Docker.app 2>/dev/null && echo "WARN: App still exists" || echo "OK"
ls ~/Library/Containers/com.docker.docker 2>/dev/null && echo "WARN: Container data still exists" || echo "OK"
ls /Volumes/Doc-Bk-JJ-SDD-1-APFS/DockerDesktop_raw 2>/dev/null && echo "WARN: SSD data still exists" || echo "OK"
```

---

## 4. Fresh Install Steps

### <span style="color:#9b59b6">Step 1: Download and install</span>

1. Download Docker Desktop for Mac (Apple Silicon): https://www.docker.com/products/docker-desktop/
2. Open the `.dmg`, drag Docker to Applications.
3. **Do not launch yet.**

### <span style="color:#9b59b6">Step 2: Prepare SSD (recommended)</span>

1. Ensure `Doc-Bk-JJ-SDD-1-APFS` is mounted.
2. Create a clean folder:
   ```bash
   mkdir -p /Volumes/Doc-Bk-JJ-SDD-1-APFS/DockerDesktop_raw
   ```
3. Use a **flat** path: `/Volumes/Doc-Bk-JJ-SDD-1-APFS/DockerDesktop_raw` (no nested `DockerDesktop/DockerDesktop`).

### <span style="color:#9b59b6">Step 3: First launch and configure</span>

1. Launch Docker Desktop.
2. Accept terms; complete onboarding.
3. Go to **Settings → Resources**:
   - **Disk image location:** `/Volumes/Doc-Bk-JJ-SDD-1-APFS/DockerDesktop_raw`
   - **Disk usage limit:** 64 GB or higher (slider right).
4. Click **Apply & restart**.
5. Wait for Docker to create a new `Docker.raw` on the SSD.

### <span style="color:#9b59b6">Step 4: Verify</span>

```bash
docker version
docker run hello-world
docker system df
```

---

## 5. Post-install Best Practices

| Practice | Why |
|----------|-----|
| Mount SSD before starting Docker | Prevents fallback to internal disk |
| Use flat disk path | Avoids nested `DockerDesktop/DockerDesktop` confusion |
| Set disk limit ≥ 64 GB | Builds need space for apt cache, layers |
| After upgrades | Re-check Settings → Resources; Docker may revert |

---

## 6. One-liner removal script (reference)

For copy-paste (run from project root; review before executing):

```bash
# Full removal – review each block before running
osascript -e 'quit app "Docker"' 2>/dev/null; sleep 3
pkill -9 -f "com.docker" 2>/dev/null; sudo pkill -9 -f "com.docker.vmnetd" 2>/dev/null; sleep 2
sudo rm -rf /Applications/Docker.app
sudo rm -f /Library/PrivilegedHelperTools/com.docker.* /Library/LaunchDaemons/com.docker.*
rm -rf ~/Library/Containers/com.docker.docker ~/Library/Group\ Containers/group.com.docker ~/.docker
rm -rf /Volumes/Doc-Bk-JJ-SDD-1-APFS/DockerDesktop_raw
```

---

## 7. Related scripts in this repo

- `tools/cloud_shared/docker/docker-unstick-desktop-start.sh` – Unstick wedged Docker (kill + restart)
- `tools/cloud_shared/docker/fix-docker-raw-ssd.sh` – SSD relocation helper
- `docs/war_stories/WAR_STORIES_OTHER.md` §2 – Docker disk image, sparse files, relocation
