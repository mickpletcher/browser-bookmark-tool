# Browser Bookmark Tool

A small Windows desktop app that backs up Chrome and Microsoft Edge bookmarks, exports them to a standard HTML file, and safely synchronizes unique links between the two browsers.

## Safety model

- Creates timestamped copies of both original `Bookmarks` JSON files before syncing.
- Exports the merged collection as a portable Netscape bookmark HTML file.
- Uses a conservative union: a bookmark found in either browser is retained.
- Deduplicates bookmarks by normalized URL.
- Writes each browser file atomically.
- Keeps the newest 30 backup sets by default (configurable).

This first version does **not** propagate deletions. That is intentional: a deleted bookmark in one browser will be restored if it still exists in the other. This avoids accidental data loss.

## Run on Windows

1. Install Python 3.10 or newer from <https://python.org> and enable **Add Python to PATH**.
2. Open PowerShell in this project folder.
3. Run:

   ```powershell
   py -m pip install -e .
   browser-bookmark-tool --gui
   ```

The app auto-detects the `Default` and `Profile *` profiles in Chrome and Edge.

Before selecting **Back Up + Sync**, fully close both browsers, including background processes. If a browser is open during the write, it may overwrite the synchronized file when it exits.

## Backup-only mode

Use **Back Up + Export HTML** in the GUI. It reads both bookmark stores and creates backups plus a merged HTML export without changing either browser.

## Command-line use

This is useful with Windows Task Scheduler. Close both browsers before an automated synchronization.

```powershell
browser-bookmark-tool `
  --sync `
  --chrome-profile "$env:LOCALAPPDATA\Google\Chrome\User Data\Default" `
  --edge-profile "$env:LOCALAPPDATA\Microsoft\Edge\User Data\Default" `
  --backup-dir "$env:USERPROFILE\Documents\Browser Bookmark Backups" `
  --keep 30
```

Omit `--sync` to create backups and an HTML export without modifying the browsers.

## Restore a backup

1. Close Chrome and Edge.
2. Go to `Documents\Browser Bookmark Backups`.
3. Copy the desired `Chrome_*.json` or `Edge_*.json` file.
4. Rename the copy to `Bookmarks` (no extension).
5. Replace the corresponding profile's current `Bookmarks` file.

Keep the original current file until the restored browser has been verified.

## Development

```powershell
py -m pip install pytest
py -m pytest
```
