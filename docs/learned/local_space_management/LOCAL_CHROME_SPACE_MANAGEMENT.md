## LOCAL_CHROME_SPACE_MANAGEMENT

**Goal:** prevent Chrome caches from quietly consuming tens of GB on the Mac SSD by:

- Moving `~/Library/Caches/Google` to an external SSD.
- Ensuring Chrome uses the SSD path via a symlink.
- Providing commands to verify and, if needed, clean up.

### 1. Where Chrome eats disk space

On macOS, Chrome caches live under:

- `~/Library/Caches/Google/Chrome/...`

We observed:

- `~/Library/Caches/Google` ≈ **8 GB**+
- Multiple profiles (e.g. `Profile 1`, `Profile 2`, `Profile 3`, etc.) each with:
  - `Cache/Cache_Data`
  - `Code Cache`
  - Other cache folders.

This cache is **safe to move or delete**; Chrome will recreate it as needed.

### 2. Strategy: move caches to SSD via symlink

Assume:

- SSD mount: `/Volumes/Doc-Bk-JJ-SDD-1-APFS`
- Chrome cache base on SSD: `/Volumes/Doc-Bk-JJ-SDD-1-APFS/caches/Chrome/Google`

Plan:

- While Chrome is **fully quit**, move the entire `~/Library/Caches/Google` folder to the SSD.
- Replace it with a symlink pointing to the SSD location.

### 3. One‑time migration to SSD

> Important: Chrome must be **completely quit** (no background processes) or the move will be partial and slow.

1. **Quit Chrome**

   - Chrome menu → Quit.
   - Confirm no Chrome processes:

     ```bash
     pgrep -fl \"Chrome|Google Chrome\" || echo \"Chrome is not running (good)\"
     ```

2. **Create SSD target**

   ```bash
   SSD_CHROME_BASE=/Volumes/Doc-Bk-JJ-SDD-1-APFS/caches/Chrome
   mkdir -p \"$SSD_CHROME_BASE\"
   ```

3. **Move the cache**

   ```bash
   LOCAL_CACHE=\"$HOME/Library/Caches/Google\"

   # Optionally keep a safety copy name
   if [[ -d \"$SSD_CHROME_BASE/Google\" ]]; then
     mv \"$SSD_CHROME_BASE/Google\" \"$SSD_CHROME_BASE/Google_pre_migration_$(date +%Y%m%d_%H%M%S)\"
   fi

   mv \"$LOCAL_CACHE\" \"$SSD_CHROME_BASE/Google\"
   ln -s \"$SSD_CHROME_BASE/Google\" \"$LOCAL_CACHE\"
   ```

4. **Verify**

   ```bash
   # On Mac disk, Google should be a symlink
   ls -la \"$HOME/Library/Caches/Google\"

   # Actual size lives on SSD
   du -sh \"$SSD_CHROME_BASE/Google\" 2>/dev/null
   df -h /   # root disk free space
   df -h /Volumes/Doc-Bk-JJ-SDD-1-APFS
   ```

5. **Restart Chrome**

   - Start Chrome as usual.
   - It will write new cache data under the SSD path through the symlink.

### 4. Troubleshooting partial moves and permission issues

During our initial attempts, we saw:

- `cp` commands taking a long time and printing `No such file or directory` (files vanishing mid-copy).
- `rm -rf` on the SSD path returning `Permission denied` for some subdirectories.

Key fixes:

- **Always fully quit Chrome first.** Any running Chrome process can:
  - Modify `Cache_Data` while it is being copied.
  - Lock files, causing partial copies and permission issues.
- Prefer **`mv` + symlink** over recursive `cp` for the initial move; it is faster and avoids copying files that Chrome rewrites anyway.
- If a partial SSD copy exists and you want to reset:

  ```bash
  rm -rf /Volumes/Doc-Bk-JJ-SDD-1-APFS/caches/Chrome/Google
  ```

  (Use `sudo` only if strictly necessary.)

### 5. Inspecting Chrome cache usage

Quick view:

```bash
du -sh ~/Library/Caches/Google 2>/dev/null   # follows symlink
du -sh /Volumes/Doc-Bk-JJ-SDD-1-APFS/caches/Chrome/Google 2>/dev/null
```

Per-profile breakdown:

```bash
du -sh /Volumes/Doc-Bk-JJ-SDD-1-APFS/caches/Chrome/Google/Chrome/* 2>/dev/null | sort -hr | head -20
```

### 6. Freeing space without the SSD move (optional)

If you just want to free space quickly (and are okay with Chrome re-downloading data):

1. Quit Chrome completely.
2. Delete the cache:

   ```bash
   rm -rf ~/Library/Caches/Google
   ```

3. Start Chrome again; it will create a fresh cache from scratch.

This is simpler but does not keep future cache growth off the system disk.

### 7. Quick scripts

- See `docs/learned/local_space_management/scripts/chrome_move_cache_to_ssd.sh` for:
  - Pre/post `df -h /` snapshot.
  - Moving `~/Library/Caches/Google` to the SSD.
  - Creating the symlink on the Mac disk.
  - Basic safety checks (Chrome not running, SSD mounted).

