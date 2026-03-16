## LOCAL_CURSOR_SPACE_MANAGEMENT

**Goal:** keep Cursor’s footprint small on the Mac SSD by:

- Offloading heavy `globalStorage` to an external SSD.
- Knowing what still lives under `~/Library/Application Support/Cursor`.
- Providing quick commands to inspect and clean up space.

### 1. Where Cursor stores data on macOS

Main locations:

- **Application support (large)**  
  - Root: `~/Library/Application Support/Cursor`  
  - Notable heavy subdirectories:
    - `User` – settings, extensions, state.
    - `CachedExtensionVSIXs` – downloaded VSIX extension packages.
    - `WebStorage` – workspace/webview storage.
    - `CachedData` – miscellaneous cache files.
    - `snapshots` – internal snapshots.
    - `blob_storage` – large binary blobs.
    - `logs`, `Cache`.

- **Caches (small-ish)**  
  - `~/Library/Caches/Cursor`

- **Per-user global storage**  
  - From Cursor’s perspective: `~/Library/Application Support/Cursor/User/globalStorage`  
  - This folder can grow large over time and is safe to remap via a symlink.

### 2. Current “good” layout using external SSD

We offloaded `globalStorage` to an SSD mounted at `/Volumes/Doc-Bk-JJ-SDD-1-APFS`:

- On SSD:
  - Base: `/Volumes/Doc-Bk-JJ-SDD-1-APFS/cursor-storage`
  - Active storage: `/Volumes/Doc-Bk-JJ-SDD-1-APFS/cursor-storage/globalStorage`
  - Backup: `/Volumes/Doc-Bk-JJ-SDD-1-APFS/cursor-storage/globalStorage_bk1`

- On Mac internal disk:
  - `~/Library/Application Support/Cursor` ≈ 1.5 GB, but:
    - `User/globalStorage` is **not** a real folder; it is a symlink:
      - `~/Library/Application Support/Cursor/User/globalStorage -> /Volumes/Doc-Bk-JJ-SDD-1-APFS/cursor-storage/globalStorage`

### 3. One‑time migration of `globalStorage` to SSD

Assume:

- SSD mount: `/Volumes/Doc-Bk-JJ-SDD-1-APFS`
- Target base: `/Volumes/Doc-Bk-JJ-SDD-1-APFS/cursor-storage`

> It’s safest to run this while Cursor is **quit** so it does not write during the move.

1. **Quit Cursor** (Cmd+Q, or from the menu).

2. **Create the SSD target and backup any existing content**

   ```bash
   SSD_BASE=/Volumes/Doc-Bk-JJ-SDD-1-APFS/cursor-storage
   mkdir -p \"$SSD_BASE\"

   # If a previous migration exists, keep a backup
   if [[ -d \"$SSD_BASE/globalStorage\" && ! -d \"$SSD_BASE/globalStorage_bk1\" ]]; then
     mv \"$SSD_BASE/globalStorage\" \"$SSD_BASE/globalStorage_bk1\"
   fi
   ```

3. **Move current `globalStorage` off the Mac disk**

   ```bash
   LOCAL_GS=\"$HOME/Library/Application Support/Cursor/User/globalStorage\"

   # If it's already a symlink, you likely migrated before
   if [[ -L \"$LOCAL_GS\" ]]; then
     echo \"Already a symlink → $LOCAL_GS\" >&2
   else
     mv \"$LOCAL_GS\" \"$SSD_BASE/globalStorage\"
   fi
   ```

4. **Create the symlink Cursor will follow**

   ```bash
   ln -s \"$SSD_BASE/globalStorage\" \"$LOCAL_GS\"
   ```

5. **Verify**

   ```bash
   ls -la \"$LOCAL_GS\"
   du -sh \"$SSD_BASE/globalStorage\" 2>/dev/null
   ```

   Expected:

   - `globalStorage` under `Application Support` is `lrwxr-xr-x ... -> /Volumes/.../cursor-storage/globalStorage`.
   - The heavy data size appears on the SSD, not on the Mac disk.

### 4. Inspecting Cursor disk usage

Quick overview:

```bash
du -sh ~/Library/Application\\ Support/Cursor 2>/dev/null
du -sh ~/Library/Application\\ Support/Cursor/* 2>/dev/null | sort -hr | head -20
```

Look for:

- `CachedExtensionVSIXs` – can grow >400 MB.
- `blob_storage`, `snapshots`, `WebStorage`, `CachedData`.

Most of these are **safe to delete with Cursor quit**; Cursor will recreate what it needs:

```bash
CursorApp=\"Cursor\"  # Close first (Cmd+Q)
rm -rf ~/Library/Application\\ Support/Cursor/CachedExtensionVSIXs
rm -rf ~/Library/Application\\ Support/Cursor/CachedData
rm -rf ~/Library/Application\\ Support/Cursor/Cache
rm -rf ~/Library/Application\\ Support/Cursor/logs/*
```

Then restart Cursor; it will re-download extensions and rebuild caches as needed.

### 5. Verifying SSD usage and free space

Check SSD:

```bash
du -sh /Volumes/Doc-Bk-JJ-SDD-1-APFS/cursor-storage 2>/dev/null
df -h /Volumes/Doc-Bk-JJ-SDD-1-APFS
```

Check Mac root:

```bash
df -h /
```

If globalStorage is correctly offloaded, growing Cursor usage should primarily show up on the SSD, not on `Macintosh HD`.

### 6. Quick scripts

- See `docs/learned/local_space_management/scripts/cursor_move_global_storage_to_ssd.sh` for:
  - Creating `/Volumes/.../cursor-storage`.
  - Moving `globalStorage` there.
  - Creating the symlink under `Application Support`.
  - Printing a before/after summary.

