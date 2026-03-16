## LOCAL_DOCKER_SPACE_MANAGEMENT

**Goal:** keep Docker Desktop usable on a small Mac SSD by:

- Moving `Docker.raw` (the VM disk image) to an external SSD.
- Making it *stay* there across reboots and upgrades.
- Debugging “phantom” disk usage when `Docker.raw` is deleted but space is not freed.

### 1. Facts worth remembering

- Docker Desktop stores all local images/containers/volumes in a **single sparse disk image**:
  - `~/Library/Containers/com.docker.docker/Data/vms/0/data/Docker.raw`
- On macOS/APFS, `Docker.raw` is a **sparse file**:
  - `ls -lh` may show 200+ GB logical size.
  - `du -sh` (or the filesystem free space) shows the *real* allocated blocks.
- Deleting a large file only frees space when **no process has it open**.
  - If `cp`, Docker, or anything else still holds `Docker.raw`, the disk space will not be reclaimed until that process exits.

### 2. Current “good” layout (MacBook Air + SSD)

- **Mac internal disk**:
  - `~/Library/Containers/com.docker.docker` ≈ 25 MB.
  - `~/Library/Application Support/Docker Desktop` ≈ 20–30 MB.
  - No `Docker.raw` on the internal disk.
- **External SSD (example)**:
  - Base: `/Volumes/Doc-Bk-JJ-SDD-1-APFS/DockerDesktop_raw`
  - Docker Desktop **Disk image location** (UI): same path as above.
  - Actual disk image: `/Volumes/Doc-Bk-JJ-SDD-1-APFS/DockerDesktop_raw/DockerDesktop/Docker.raw` (single copy).

### 3. One‑time migration to SSD

Assume the SSD is mounted at `/Volumes/Doc-Bk-JJ-SDD-1-APFS` and you want Docker data under `DockerDesktop_raw/`.

1. **Quit Docker Desktop completely**

   - Menu bar → Docker icon → **Quit Docker Desktop**.

2. **Move existing `Docker.raw` to SSD**

   ```bash
   # Create target dir on SSD
   mkdir -p /Volumes/Doc-Bk-JJ-SDD-1-APFS/DockerDesktop_raw/DockerDesktop

   # Move Docker VM disk image
   mv ~/Library/Containers/com.docker.docker/Data/vms/0/data/Docker.raw \
      /Volumes/Doc-Bk-JJ-SDD-1-APFS/DockerDesktop_raw/DockerDesktop/
   ```

3. **Point Docker Desktop at the SSD**

   Docker Desktop → **Settings → Resources → Advanced**:

   - Set **Disk image location** to:
     - `/Volumes/Doc-Bk-JJ-SDD-1-APFS/DockerDesktop_raw`
   - Click **Apply & Restart**.

   Docker will create (or reuse) `DockerDesktop/Docker.raw` under that base path.

4. **Verify**

   ```bash
   # On Mac disk – should be small
   du -sh ~/Library/Containers/com.docker.docker 2>/dev/null

   # On SSD – Docker data lives here
   du -sh /Volumes/Doc-Bk-JJ-SDD-1-APFS/DockerDesktop_raw \
         /Volumes/Doc-Bk-JJ-SDD-1-APFS/DockerDesktop_raw/DockerDesktop 2>/dev/null

   # Check where the VM actually points (from running processes)
   pgrep -fl com.docker.virtualization
   ```

### 4. Safely deleting a local `Docker.raw`

Deleting `Docker.raw` from the internal disk is safe **only when Docker is using the SSD image** and no process has the local file open.

#### 4.1 Procedure

1. **Confirm Docker’s disk location in the UI**

   - Docker Desktop → **Settings → Resources → Advanced**.  
   - Ensure the **Disk image location** points to the **SSD base path**, not `~/Library/...`.

2. **Quit Docker Desktop**

   - Menu bar → Quit Docker Desktop.

3. **Ensure no long‑running copies**

   ```bash
   # Look for cp or other processes touching vms/0/data
   lsof | grep 'com.docker.docker/Data/vms/0/data' || echo "no open handles"
   ```

   If you see `cp` or other processes still copying from `vms/0/data`, kill them:

   ```bash
   kill -9 <pid1> <pid2> ...
   ```

4. **Delete the local image**

   ```bash
   rm ~/Library/Containers/com.docker.docker/Data/vms/0/data/Docker.raw
   ```

5. **Verify freed space**

   ```bash
   df -h /
   ```

If the space does not appear immediately, check for open handles:

```bash
lsof +L1 | grep Docker.raw || echo "no deleted Docker.raw still open"
```

If nothing is holding it and free space still looks wrong, a reboot usually flushes any lingering references.

### 5. Detecting when Docker falls back to internal disk

Docker may revert to `~/Library/.../Docker.raw` when:

- The SSD is not mounted when Docker starts.
- Docker Desktop is upgraded or reset.
- The configured disk image path becomes invalid.

Quick check:

```bash
du -sh ~/Library/Containers/com.docker.docker 2>/dev/null
ls -la  ~/Library/Containers/com.docker.docker/Data/vms/0/data 2>/dev/null
```

If a new `Docker.raw` shows up there and grows, Docker has fallen back to the internal disk.

**Fix:**

1. Quit Docker Desktop.
2. Ensure SSD is mounted.
3. Re‑set **Disk image location** to the SSD base path.
4. Delete the accidental local `Docker.raw` as in section 4.

### 6. Handling a likely corrupted SSD `Docker.raw`

If a copy of `Docker.raw` was interrupted (e.g. `cp` was killed), Docker’s VM may hang or crash using that file.

Two options:

- **A. Try a healthier backup copy**
  - Keep an older `Docker.raw` backup on the SSD.
  - With Docker quit:
    - Replace the active file with the backup.
- **B. Start fresh (lose local images/containers)**
  - With Docker quit:

    ```bash
    rm -f /Volumes/Doc-Bk-JJ-SDD-1-APFS/DockerDesktop_raw/DockerDesktop/Docker.raw
    ```

  - Start Docker Desktop again; it will create a new, empty disk.

### 7. Quick scripts

- See `docs/learned/local_space_management/scripts/docker_move_to_ssd.sh` for:
  - Verifying SSD mount.
  - Moving `Docker.raw` off the internal disk.
  - Updating Docker’s disk image location.
  - Printing a before/after `df -h /` summary.

