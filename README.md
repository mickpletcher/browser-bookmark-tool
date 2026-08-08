# Browser Bookmark Tool

Browser Bookmark Tool is a Windows desktop and command-line application for backing up, exporting, and synchronizing bookmarks between Google Chrome and Microsoft Edge.

The synchronization uses a conservative union. A bookmark found in either browser is retained. Deletions are not propagated.

## Project status

Version: 0.1.0

Release readiness: Ready

Packaging, the batch launcher, automated tests, transactional cross-browser writes, browser process detection, collision-resistant HTML backups, and unique imported-node GUID generation are working.

- [Current assessment](assessment.md)
- [Changelog](changelog.md)

## Features

- Detects Chrome and Edge `Default` and `Profile *` profiles.
- Creates timestamped copies of both original `Bookmarks` JSON files.
- Exports the merged bookmark collection to portable Netscape bookmark HTML.
- Synchronizes unique bookmarks between Chrome and Edge when requested.
- Deduplicates bookmarks using a normalized URL.
- Optionally removes duplicate URLs already present within the merged bookmark collection.
- Optionally alphabetizes folders and bookmarks recursively.
- Prepares and validates both replacement files before changing either browser.
- Restores Chrome automatically if the Edge replacement fails.
- Detects `chrome.exe` and `msedge.exe` before synchronization and blocks writes while either browser is running.
- Keeps raw backups and the merged HTML export when synchronization is blocked by a running browser.
- Optionally force-closes Chrome and Edge process trees before synchronization through the CLI.
- Creates a portable HTML backup during every run.
- Retains up to 50 backup sets, with 50 as the default.
- Uses microsecond timestamps so rapid runs do not overwrite previous backups.
- Generates a new unique Chromium GUID for every imported bookmark and folder.
- Validates that the merged bookmark collection contains no duplicate GUID values.
- Supports a Tkinter desktop interface and command-line execution.
- Includes a Windows batch launcher that installs the project in editable mode and starts the app.

## Current synchronization behavior

Chrome is used as the primary bookmark structure. Unique Edge bookmarks are copied into an `Imported from other browser` folder under Chrome's `Other bookmarks` root. The resulting merged structure is then written to both browsers.

Existing Chrome GUID values are preserved. Every imported Edge bookmark, imported folder, and generated import wrapper receives a new UUID. The merge stops before export or synchronization if duplicate GUID values remain. Repeated synchronization preserves the generated GUIDs and does not create another import folder when no new URLs exist.

URL comparison currently:

- Removes surrounding whitespace.
- Ignores letter case.
- Treats most URLs with and without one trailing slash as the same bookmark.

If the same URL exists in both browsers with different names or folder locations, the Chrome copy is retained. The Edge duplicate is not imported.

Cross-browser URL matching is always applied while building the merged union. The optional **Remove duplicate bookmarks** setting also removes repeated URLs already present within Chrome's retained structure. The first occurrence is kept.

The optional **Alphabetize bookmarks** setting sorts every folder recursively. Folders are placed first and sorted by name. Bookmarks follow and are sorted by their displayed name, or by URL when they have no name. Sorting ignores letter case.

This version does not propagate deletions. If a bookmark is deleted from one browser but still exists in the other, synchronization restores it. This behavior is intentional to reduce accidental data loss.

## Safety requirements

Close Chrome and Edge completely before synchronization. Include background browser processes. An open browser can overwrite the synchronized file when it exits.

Before writing, the tool checks the Windows process list for `chrome.exe` and `msedge.exe`. If either executable is running, synchronization is blocked. The GUI error lists the detected executable names. The CLI prints the same error and exits with code `1`.

Process detection occurs after the raw backups and merged HTML export are created. A blocked synchronization therefore leaves both browser files unchanged while keeping the backup and export results. Backup-only and export-only runs do not check browser processes and remain available while either browser is open.

The tool creates raw backups before changing either browser file. It then prepares the Chrome and Edge replacement files in their respective profile directories and parses both files back as JSON. Neither browser is changed unless both prepared files match the merged data.

Chrome is replaced first. If that replacement fails, Edge remains unchanged. If the Edge replacement fails, the original Chrome file is restored automatically. If automatic restoration also fails, the error identifies the preserved rollback file and the raw timestamped backups remain available for manual recovery.

The CLI-only `--force` option bypasses browser process detection. Use it only after independently confirming that Chrome and Edge are completely closed. It does not close browsers or prevent an open browser from overwriting the synchronized files.

The CLI-only `--close-browsers` option takes the opposite approach. After backups and the HTML export are created, it force-terminates the detected `chrome.exe` and `msedge.exe` process trees using Windows `taskkill /T /F`. It verifies that both executables stopped before writing bookmarks. If either remains, synchronization is blocked.

Force-closing browsers can discard unsaved form entries, downloads, private-window state, and other active work. Use `--close-browsers` only when that loss is acceptable. It cannot be combined with `--force`.

Use **Back Up + Export HTML** first if you want to inspect the merged result without changing either browser.

## Requirements

- Windows 11 or another supported Windows version.
- Python 3.10 or newer from [python.org](https://www.python.org/downloads/windows/).
- The Python launcher available as `py` in PowerShell.
- Read and write access to the selected browser profiles and backup directory.

Confirm Python is available:

```powershell
py --version
```

## Install the application

Install the project in editable mode from PowerShell:

```powershell
py -m pip install -e .
```

The installation provides the `browser-bookmark-tool` console command. Some Python installations do not add their `Scripts` directory to `PATH`. The documented `py -m browser_bookmark_sync` commands and the batch launcher work without that PATH entry.

## Run the desktop app

1. Close Chrome and Edge if you intend to synchronize.
2. Start the application using either method:

   Double-click:

   ```text
   Run Browser Bookmark Tool.bat
   ```

   Or open PowerShell in the project directory and run:

   ```powershell
   py .\browser_bookmark_sync.py --gui
   ```

3. Select the Chrome profile.
4. Select the Edge profile.
5. Confirm or change the backup folder.
6. Set the number of backup sets to retain, from 1 through 50. The default is 50.
7. Select either optional organization setting when required:

   - **Remove duplicate bookmarks** removes repeated normalized URLs from the merged output.
   - **Alphabetize bookmarks** sorts folders first and bookmarks second at every folder level.

8. Choose one of the following actions:

   - **Back Up + Export HTML** creates raw browser backups and a merged HTML export without changing either browser.
   - **Back Up + Sync** creates backups and the HTML export, then writes the merged bookmarks to both browsers.
   - **Open Backup Folder** opens the configured backup directory.

The app automatically selects the first detected profile for each browser. Review both selections before running an action.

The organization settings affect the merged HTML export on both actions. They change Chrome and Edge only when **Back Up + Sync** is selected.

## Profile locations

The tool searches these standard locations:

```text
Chrome: %LOCALAPPDATA%\Google\Chrome\User Data\Default
Edge:   %LOCALAPPDATA%\Microsoft\Edge\User Data\Default
```

It also detects directories named `Profile *` under each browser's `User Data` directory when they contain a `Bookmarks` file.

## Command-line use

### Back up and export without synchronization

Omit `--sync` to leave both browser files unchanged:

```powershell
py .\browser_bookmark_sync.py `
  --chrome-profile "$env:LOCALAPPDATA\Google\Chrome\User Data\Default" `
  --edge-profile "$env:LOCALAPPDATA\Microsoft\Edge\User Data\Default" `
  --backup-dir "$env:USERPROFILE\Documents\Browser Bookmark Backups" `
  --keep 50
```

### Back up, export, and synchronize

Close both browsers, then add `--sync`:

```powershell
py .\browser_bookmark_sync.py `
  --sync `
  --chrome-profile "$env:LOCALAPPDATA\Google\Chrome\User Data\Default" `
  --edge-profile "$env:LOCALAPPDATA\Microsoft\Edge\User Data\Default" `
  --backup-dir "$env:USERPROFILE\Documents\Browser Bookmark Backups" `
  --keep 50
```

### Remove duplicates and alphabetize

Add either option independently or use both together:

```powershell
py .\browser_bookmark_sync.py `
  --sync `
  --deduplicate `
  --alphabetize `
  --chrome-profile "$env:LOCALAPPDATA\Google\Chrome\User Data\Default" `
  --edge-profile "$env:LOCALAPPDATA\Microsoft\Edge\User Data\Default" `
  --backup-dir "$env:USERPROFILE\Documents\Browser Bookmark Backups"
```

Omit `--sync` to apply the selected organization options only to the HTML export. The raw Chrome and Edge files remain unchanged.

### Force synchronization

Process detection is a write-safety control. If detection itself is unavailable and you have independently confirmed that both browsers are closed, advanced users can bypass it:

```powershell
py .\browser_bookmark_sync.py `
  --sync `
  --force `
  --chrome-profile "$env:LOCALAPPDATA\Google\Chrome\User Data\Default" `
  --edge-profile "$env:LOCALAPPDATA\Microsoft\Edge\User Data\Default"
```

Do not use `--force` merely because synchronization reported `chrome.exe` or `msedge.exe`. Close the detected processes first.

### Close browsers automatically

Use the explicit close parameter when forced process termination is acceptable:

```powershell
py .\browser_bookmark_sync.py `
  --sync `
  --close-browsers `
  --chrome-profile "$env:LOCALAPPDATA\Google\Chrome\User Data\Default" `
  --edge-profile "$env:LOCALAPPDATA\Microsoft\Edge\User Data\Default" `
  --backup-dir "$env:USERPROFILE\Documents\Browser Bookmark Backups" `
  --keep 50
```

Backups and the HTML export are created before process termination. The command returns an error without writing either browser if Chrome or Edge remains running after the close attempt.

### Command-line options

| Option | Required | Description |
| --- | --- | --- |
| `--gui` | No | Opens the desktop interface. |
| `--sync` | No | Writes the merged bookmarks to both browsers. Without it, the run only backs up and exports. |
| `--chrome-profile` | CLI operations | Path to a Chrome profile containing `Bookmarks`. |
| `--edge-profile` | CLI operations | Path to an Edge profile containing `Bookmarks`. |
| `--backup-dir` | No | Output directory. Defaults to `Documents\Browser Bookmark Backups`. |
| `--keep` | No | Number of backup sets to retain. Accepts `1` through `50` and defaults to `50`. |
| `--deduplicate` | No | Removes repeated normalized URLs from the merged collection. |
| `--alphabetize` | No | Sorts folders first and bookmarks second, recursively and without case sensitivity. |
| `--force` | No | Bypasses browser process detection during synchronization. It has no effect on export-only runs. |
| `--close-browsers` | No | Force-terminates detected Chrome and Edge process trees, verifies closure, then synchronizes. Cannot be combined with `--force`. |

If neither profile argument is supplied, the application opens the GUI. If only one profile argument is supplied, the command exits because both profiles are required.

## Backup files

Each run creates one portable HTML backup and two raw JSON recovery snapshots in the backup directory:

```text
Chrome_YYYY-MM-DD_HH-MM-SS_microseconds.json
Edge_YYYY-MM-DD_HH-MM-SS_microseconds.json
Bookmarks_YYYY-MM-DD_HH-MM-SS_microseconds.html
```

The HTML file is the portable bookmark backup. It contains the merged collection and can be imported into browsers that support Netscape bookmark HTML. The JSON files are retained as recovery snapshots because HTML does not preserve all Chromium bookmark metadata.

Retention is applied separately to Chrome JSON recovery snapshots, Edge JSON recovery snapshots, and merged HTML backups. The tool accepts 1 through 50 backup sets and defaults to 50. Microsecond timestamps prevent repeated runs during the same second from overwriting earlier files.

## Restore a backup

1. Close Chrome and Edge completely.
2. Open `Documents\Browser Bookmark Backups`, or the custom backup directory used for the run.
3. Choose the required `Chrome_*.json` or `Edge_*.json` backup.
4. Make a copy of that backup.
5. Rename the copy to `Bookmarks` with no file extension.
6. Go to the matching browser profile directory.
7. Preserve the current `Bookmarks` file under a different name.
8. Place the restored `Bookmarks` file in the profile directory.
9. Start the browser and verify the restored bookmarks before deleting the preserved file.

Do not restore a Chrome backup into Edge or an Edge backup into Chrome unless you have independently verified the file contents and accept the risk.

## Known limitations

- The tool detects running browsers but does not close them automatically.
- Automatic closure uses forceful process-tree termination and is available only through the explicit `--close-browsers` CLI option.
- Only standard `Default` and `Profile *` profile directory names are auto-detected.
- Deletions are intentionally not synchronized.
- Duplicate removal and alphabetization are disabled by default.
- There is no automatic scheduled-task creation or background service.

Track fixes and release-readiness changes in the [assessment](assessment.md) and [changelog](changelog.md).

## Development

Run the test suite:

```powershell
py -m pip install pytest
py -m pytest -q
```

Run a syntax check:

```powershell
py -m py_compile browser_bookmark_sync.py test_sync.py
```

Current verification results are recorded in [assessment.md](assessment.md).

The current test suite contains 27 passing cases covering merge behavior, GUID regeneration and validation, repeated synchronization, optional organization, portable HTML backups, collision-resistant filenames, 50-backup pruning, retention validation, transactional writes, process detection and blocking, export-only behavior, forced synchronization, automatic browser closure, CLI error handling, and GUI process-error display.

## Documentation maintenance requirement

Every project change must include a review and update of:

- [README.md](README.md) for installation, operation, behavior, limitations, or development guidance affected by the change.
- [assessment.md](assessment.md) for current status, open findings, release readiness, and verification results.
- [changelog.md](changelog.md) for a concise entry under `[Unreleased]`.

This requirement applies to code, tests, documentation, configuration, packaging, and workflow changes. Do not leave instructions or status statements that describe behavior the application no longer has.
