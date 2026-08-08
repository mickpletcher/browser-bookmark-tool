# Browser Bookmark Tool

[![Windows CI](https://github.com/mickpletcher/browser-bookmark-tool/actions/workflows/ci.yml/badge.svg)](https://github.com/mickpletcher/browser-bookmark-tool/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Browser Bookmark Tool is a Windows desktop and command-line application for backing up, exporting, and synchronizing bookmarks between Google Chrome and Microsoft Edge.

The synchronization uses a conservative union. A bookmark found in either browser is retained. Deletions are not propagated.

## Project status

Version: 0.3.0

Release readiness: Source ready; trusted signing credential required for binary release

The GUI, CLI, standalone build, automated tests, transactional writes, dry-run reporting, restore workflow, multi-profile mappings, backup integrity manifests, privacy-safe logging, Task Scheduler generation, vendor-neutral local AI scheduling, privacy-safe health history, and optional rate-limited failure notifications are implemented for Windows. The current `main` branch passes Windows CI and CodeQL. Release automation now fails closed unless Azure Artifact Signing can sign and timestamp the executable, the workflow can verify the expected publisher and signature, and checksums, a CycloneDX SBOM, and GitHub provenance are published. No Azure signing account is currently configured, so broad binary distribution remains blocked. Native macOS Chrome and Edge compatibility and later Safari support are separate future upgrades and are not currently implemented.

- [Current assessment](assessment.md)
- [Changelog](changelog.md)
- [Future upgrades](future-upgrades.md)
- [Completed upgrades](completed-upgrades.md)
- [Scheduled AI execution](SCHEDULING.md)
- [Contributing](CONTRIBUTING.md)
- [Support](SUPPORT.md)

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
- Uses conservative URL matching by default and keeps aggressive matching opt-in.
- Provides five merge strategies and a no-write dry-run report.
- Restores Chrome or Edge independently from raw JSON recovery snapshots.
- Saves and loads private named profile mappings and processes several mappings from the CLI.
- Creates and validates SHA-256 backup manifests.
- Writes count-only logs that exclude bookmark URLs by default.
- Generates PowerShell scripts for Windows Task Scheduler with backup-only defaults.
- Builds a standalone Windows executable with PyInstaller.
- Runs tests and produces the executable through SHA-pinned Windows GitHub Actions.
- Validates versioned Windows release packages and requires Authenticode signing, checksums, a CycloneDX SBOM, and GitHub attestations before publication.
- Provides scheduler-safe configuration, readiness checks, concurrency locking, and privacy-safe JSON results for local Codex, Claude, Copilot, or deterministic schedulers.
- Supports a Tkinter desktop interface and command-line execution.
- Includes a Windows batch launcher that installs the project in editable mode and starts the app.

## Current synchronization behavior

Chrome is used as the primary bookmark structure. Unique Edge bookmarks are copied into an `Imported from other browser` folder under Chrome's `Other bookmarks` root. The resulting merged structure is then written to both browsers.

Existing Chrome GUID values are preserved. Every imported Edge bookmark, imported folder, and generated import wrapper receives a new UUID. The merge stops before export or synchronization if duplicate GUID values remain. Repeated synchronization preserves the generated GUIDs and does not create another import folder when no new URLs exist.

Conservative URL comparison is the default:

- Removes surrounding whitespace.
- Lowercases only the URL scheme and host.
- Preserves path, query, and fragment case.
- Treats trailing slashes as significant.

Aggressive comparison is opt-in. It lowercases the complete URL and treats most trailing slashes as equivalent. It can collapse distinct case-sensitive resources and should be used only after reviewing a dry-run report.

If the same URL exists in both browsers with different names or folder locations, the Chrome copy is retained. The Edge duplicate is not imported.

Available merge strategies:

- `chrome-wins` keeps the Chrome hierarchy and imports unique Edge items.
- `edge-wins` keeps the Edge hierarchy and imports unique Chrome items.
- `preserve-both` keeps Chrome primary and places unique Edge content under `Edge favorites`.
- `merge-folders` recursively combines folders whose names match without case sensitivity.
- `dated-folder` places unique Edge content under a dated import folder.

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

## Verify a Windows release

Do not run a downloaded executable unless all three checks pass.

Verify the Authenticode signature:

```powershell
$signature = Get-AuthenticodeSignature .\BrowserBookmarkTool-0.3.0.exe
$signature | Format-List Status, StatusMessage, SignerCertificate, TimeStamperCertificate
if ($signature.Status -ne 'Valid') { throw 'Authenticode signature validation failed.' }
```

Verify the published SHA-256 checksum:

```powershell
$fileName = 'BrowserBookmarkTool-0.3.0.exe'
$expected = ((Select-String -Path .\SHA256SUMS -Pattern "  $([regex]::Escape($fileName))$").Line -split '  ')[0]
$actual = (Get-FileHash -Algorithm SHA256 -Path ".\$fileName").Hash.ToLowerInvariant()
if ($actual -ne $expected) { throw 'SHA-256 checksum validation failed.' }
```

Verify GitHub build provenance with GitHub CLI:

```powershell
gh attestation verify .\BrowserBookmarkTool-0.3.0.exe `
    --repo mickpletcher/browser-bookmark-tool `
    --signer-workflow mickpletcher/browser-bookmark-tool/.github/workflows/release.yml
```

Each release also includes the versioned ZIP, `SHA256SUMS`, and a CycloneDX JSON SBOM. The release workflow publishes the files only after signature and checksum verification succeeds.

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

8. Select conservative or aggressive duplicate matching and the required merge strategy.
9. Choose one of the following actions:

   - **Preview Changes** displays counts, direction differences, duplicate removals, folder additions, reorder counts, and final totals without creating or changing files.
   - **Back Up + Export HTML** creates raw browser backups and a merged HTML export without changing either browser.
   - **Back Up + Sync** creates backups and the HTML export, then writes the merged bookmarks to both browsers.
   - **Open Backup Folder** opens the configured backup directory.
   - **Restore Chrome** or **Restore Edge** restores that browser independently from a selected raw JSON recovery snapshot after preserving its current file.
   - **Save Profile Mapping** and **Load Profile Mapping** manage named browser-profile pairs in a private JSON file.

The app automatically selects the first detected profile for each browser. Review both selections before running an action.

The organization settings affect the merged HTML export on both actions. They change Chrome and Edge only when **Back Up + Sync** is selected.

HTML backups are portable imports but cannot directly restore full Chromium metadata. Use the JSON recovery snapshots for direct restore.

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

### Preview changes

Dry-run mode reads both profiles and reports the planned changes. It does not create backups, exports, manifests, logs, or browser writes.

```powershell
py .\browser_bookmark_sync.py `
  --dry-run `
  --deduplicate `
  --alphabetize `
  --duplicate-mode conservative `
  --merge-strategy merge-folders `
  --chrome-profile "$env:LOCALAPPDATA\Google\Chrome\User Data\Default" `
  --edge-profile "$env:LOCALAPPDATA\Microsoft\Edge\User Data\Default"
```

Run this before aggressive duplicate matching, a new merge strategy, or a first synchronization.

### Named profile mappings

Copy [profile-mappings.example.json](profile-mappings.example.json) outside the repository and replace the placeholder paths. Mapping files contain private local paths and are ignored by Git.

Run one mapping:

```powershell
py .\browser_bookmark_sync.py `
  --dry-run `
  --profile-map "D:\Private\profile-mappings.json" `
  --mapping Personal
```

Repeat `--mapping` to run several named mappings. Omit `--mapping` to process every mapping in the file. Each mapping has its own Chrome profile, Edge profile, and backup directory, which reduces the risk of mixing work and personal profiles.

### Restore a JSON recovery snapshot

Close the target browser, then restore it independently:

```powershell
py .\browser_bookmark_sync.py `
  --restore-backup "D:\Browser Bookmark Backups\Chrome_2026-08-07_12-00-00_000001.json" `
  --restore-browser Chrome `
  --chrome-profile "$env:LOCALAPPDATA\Google\Chrome\User Data\Default" `
  --edge-profile "$env:LOCALAPPDATA\Microsoft\Edge\User Data\Default" `
  --backup-dir "D:\Browser Bookmark Backups"
```

The current `Bookmarks` file is copied to a `Chrome_PreRestore_*` or `Edge_PreRestore_*` recovery file first. HTML backups must be imported through the browser.

### Generate a Task Scheduler script

This writes a PowerShell registration script without registering a task automatically. Generated tasks are backup-only unless `--task-sync` is explicitly supplied.

```powershell
py .\browser_bookmark_sync.py `
  --write-task-script "D:\Private\register-bookmark-task.ps1" `
  --task-name "Browser Bookmark Backup" `
  --task-time "02:00" `
  --chrome-profile "$env:LOCALAPPDATA\Google\Chrome\User Data\Default" `
  --edge-profile "$env:LOCALAPPDATA\Microsoft\Edge\User Data\Default" `
  --backup-dir "D:\Browser Bookmark Backups"
```

Review the generated script before running it. Add `--task-sync` only when unattended synchronization is intended and browser-process behavior has been tested.

### Schedule through Codex, Claude, or Copilot

AI schedulers use the same local PowerShell entrypoint and private JSON configuration. The scheduling model does not directly parse or modify bookmark files.

Copy `automation-config.example.json` outside the repository, update its private paths, and validate it:

```powershell
.\Invoke-BrowserBookmarkAutomation.ps1 `
  -ConfigPath "D:\Private\browser-bookmark-automation.json" `
  -Mode Check
```

Run the reviewed configuration manually before creating a recurring schedule:

```powershell
.\Invoke-BrowserBookmarkAutomation.ps1 `
  -ConfigPath "D:\Private\browser-bookmark-automation.json" `
  -Mode Run
```

The default example is backup-only. Scheduled synchronization requires `operation` set to `sync`. Running browsers either block synchronization after backups and HTML export or are force-closed only when `browser_behavior` is explicitly set to `close`. Scheduled execution has no `--force` equivalent.

Every scheduled run appends an allowlisted record to the capped private `health_file`. Records contain only operation status, mapping names, numeric counts, duration, Chrome or Edge process names, and an error category. Optional failure notification delivery is disabled by default. When enabled, the configured local command receives only that sanitized record through standard input. Consecutive matching failures notify once until a successful run or a different failure resets suppression.

See [SCHEDULING.md](SCHEDULING.md) for the full private configuration schema, structured result format, concurrency behavior, security boundary, and copy-ready Codex, Claude, and Copilot prompts.

### Logging

Every backup or synchronization writes a count-only `browser-bookmark-tool.log` in the backup directory. It records timestamps, actions, counts, strategy, and process names. It does not record bookmark names or URLs. Use `--log-file` to select another private path and `--verbose` for additional count-only reporting.

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
| `--dry-run` | No | Reports planned counts and folder changes without creating or changing files. |
| `--check-automation` | AI or local scheduling | Validates a private automation configuration without creating backups or changing browser files. |
| `--run-automation` | AI or local scheduling | Executes a private automation configuration under a concurrency lock and writes a privacy-safe JSON result. |
| `--chrome-profile` | CLI operations | Path to a Chrome profile containing `Bookmarks`. |
| `--edge-profile` | CLI operations | Path to an Edge profile containing `Bookmarks`. |
| `--backup-dir` | No | Output directory. Defaults to `Documents\Browser Bookmark Backups`. |
| `--profile-map` | No | Private JSON file containing named profile mappings. |
| `--mapping` | No | Mapping name to process. Repeat for several mappings. |
| `--keep` | No | Number of backup sets to retain. Accepts `1` through `50` and defaults to `50`. |
| `--deduplicate` | No | Removes repeated normalized URLs from the merged collection. |
| `--alphabetize` | No | Sorts folders first and bookmarks second, recursively and without case sensitivity. |
| `--duplicate-mode` | No | `conservative` by default or explicit `aggressive` matching. |
| `--merge-strategy` | No | Selects `chrome-wins`, `edge-wins`, `preserve-both`, `merge-folders`, or `dated-folder`. |
| `--force` | No | Bypasses browser process detection during synchronization. It has no effect on export-only runs. |
| `--close-browsers` | No | Force-terminates detected Chrome and Edge process trees, verifies closure, then synchronizes. Cannot be combined with `--force`. |
| `--restore-backup` | Restore | Raw JSON recovery snapshot to restore. |
| `--restore-browser` | Restore | Target browser: `Chrome` or `Edge`. |
| `--log-file` | No | Overrides the private count-only log path. |
| `--verbose` | No | Prints and logs additional count-only details. |
| `--write-task-script` | Task generation | Destination PowerShell script. |
| `--task-name` | No | Scheduled task name. |
| `--task-time` | No | Daily task time in 24-hour `HH:MM` format. |
| `--task-sync` | No | Explicitly makes a generated task synchronize instead of backup only. |

If no CLI operation is supplied, the application opens the GUI. Direct CLI operations require both profile arguments unless a profile map supplies them.

## Backup files

Each run creates one portable HTML backup, two raw JSON recovery snapshots, a SHA-256 manifest, and a privacy-safe log in the backup directory:

```text
Chrome_YYYY-MM-DD_HH-MM-SS_microseconds.json
Edge_YYYY-MM-DD_HH-MM-SS_microseconds.json
Bookmarks_YYYY-MM-DD_HH-MM-SS_microseconds.html
Manifest_YYYY-MM-DD_HH-MM-SS_microseconds.json
browser-bookmark-tool.log
```

The HTML file is the portable bookmark backup. It contains the merged collection and can be imported into browsers that support Netscape bookmark HTML. The Chrome and Edge JSON files are retained as recovery snapshots because HTML does not preserve all Chromium bookmark metadata. The manifest records file names, sizes, SHA-256 hashes, and count-only operation data. The tool validates the manifest before retention pruning.

Retention is applied separately to Chrome JSON recovery snapshots, Edge JSON recovery snapshots, merged HTML backups, and manifests. The tool accepts 1 through 50 backup sets and defaults to 50. Microsecond timestamps prevent repeated runs during the same second from overwriting earlier files. The append-only operation log and pre-restore recovery files are not pruned automatically.

Retention is ordered by the timestamp in each generated filename. It does not rely on file modification times, which raw browser copies can inherit from the source file. Pruning only removes regular files that match the tool's generated Chrome JSON, Edge JSON, Bookmarks HTML, or Manifest JSON naming format.

## Privacy and security

Bookmark files, backups, profile mappings, automation configurations, and private scheduler outputs can expose browsing history, internal URLs, access tokens embedded in URLs, usernames, and private filesystem paths. Store them outside the repository and do not attach real data to issues, prompts, pull requests, or cloud artifacts. The project `.gitignore` blocks standard Chromium bookmark files, generated backups, logs, restore snapshots, task scripts, private profile mappings, automation results, health histories, and lock files as a secondary safeguard. Notification commands must obtain credentials from a private local mechanism instead of command arguments. Only the sanitized mapping and automation examples belong in Git.

Report security vulnerabilities privately through GitHub. See the [security policy](SECURITY.md) for the reporting process and evidence requirements.

The GitHub repository keeps Issues enabled and disables unused Projects, Wiki, Discussions, and Pages features. Pull requests use squash merge only and merged branches are deleted automatically. The protected `main` branch blocks force pushes and deletion, enforces linear history and resolved review conversations, and applies the rules to administrators. It does not currently require pull requests or status checks. GitHub Actions has read-only default permissions, requires full commit SHA pinning, and permits only GitHub-owned actions. Secret scanning, push protection, Dependabot alerts and security updates, weekly Dependabot version updates, private vulnerability reporting, and CodeQL default setup are enabled. Non-provider secret patterns and secret validity checks are unavailable for this account and remain disabled.

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

- The tool closes browsers only when the CLI `--close-browsers` option is explicitly used.
- Automatic closure uses forceful process-tree termination and is available only through the explicit `--close-browsers` CLI option.
- Only standard `Default` and `Profile *` profile directory names are auto-detected.
- Deletions are intentionally not synchronized.
- Duplicate removal and alphabetization are disabled by default.
- Direct restore requires JSON recovery snapshots. HTML restore uses the browser's import function.
- Task Scheduler support generates a reviewed PowerShell registration script. It does not silently register tasks.
- Cloud-hosted AI agents cannot access browser profiles on the local Windows computer. Scheduled browser operations require a local scheduler or a tightly controlled self-hosted Windows runner using the same Windows account.
- The standalone executable is Windows-only and is built as a console-capable application so CLI output remains available.
- No public executable release exists until a trusted Authenticode certificate is configured. Build from source until the signed release workflow succeeds.

Track fixes and release-readiness changes in the [assessment](assessment.md) and [changelog](changelog.md).

## Development

Run the test suite:

```powershell
py -m pip install -e ".[dev]"
py -m pytest -q
py -m ruff check .
```

Run a syntax check:

```powershell
py -m py_compile browser_bookmark_sync.py test_sync.py
```

Current verification results are recorded in [assessment.md](assessment.md).

Build the standalone executable:

```powershell
.\build.ps1
```

The executable is written to `dist\BrowserBookmarkTool.exe`. The SHA-pinned Windows workflow in [.github/workflows/ci.yml](.github/workflows/ci.yml) tests Python 3.10 through 3.13, runs lint, compilation, CLI, and dependency checks, builds the executable after the test matrix passes, and retains the workflow artifact for 14 days. Current live workflow status and any release blockers are recorded in [assessment.md](assessment.md).

Validate the release packaging locally without creating a distributable signed package:

```powershell
.\build-release.ps1 -Version 0.3.0 -OutputDirectory .\release -Mode Unsigned
```

The script creates an isolated temporary Python environment for PyInstaller and CycloneDX. This prevents unrelated global packages and local editable-install paths from entering the SBOM. `-Mode Unsigned` adds `-unsigned` to executable and ZIP names. It is for packaging validation only. The tag-triggered [.github/workflows/release.yml](.github/workflows/release.yml) uses separate prepare and finalize phases around Azure signing.

The `release` GitHub environment accepts only `v*` tags. Configure these values in that environment before creating `v0.3.0`:

- Secrets `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, and `AZURE_SUBSCRIPTION_ID`: the OIDC-enabled Azure app registration values.
- Variable `AZURE_ARTIFACT_SIGNING_ENDPOINT`: the regional Artifact Signing endpoint.
- Variable `AZURE_ARTIFACT_SIGNING_ACCOUNT`: the Artifact Signing account name.
- Variable `AZURE_ARTIFACT_SIGNING_PROFILE`: the public-trust certificate profile name.
- Variable `WINDOWS_SIGNING_SUBJECT`: the exact expected Authenticode signer subject.

Configure the Azure federated credential for the `repo:mickpletcher/browser-bookmark-tool:environment:release` subject and grant the identity the Artifact Signing Certificate Profile Signer role on the certificate profile. [Publicly trusted code-signing keys must remain hardware protected](https://cabforum.org/working-groups/code-signing/requirements/), so the workflow uses OIDC and [Azure Artifact Signing](https://learn.microsoft.com/en-us/azure/artifact-signing/how-to-signing-integrations) instead of storing an exportable private key in GitHub.

The workflow requires the tag version to match `pyproject.toml` and the tagged commit to be on `main`. It builds the unsigned executable and SBOM, signs with SHA-256 and an RFC 3161 timestamp, verifies `Valid` status, the code-signing EKU, the expected publisher subject, and the timestamp, generates and verifies `SHA256SUMS`, publishes provenance and SBOM attestations, and then creates the GitHub Release. Missing or invalid Azure configuration stops the job before publication.

The repository Actions allowlist still requires full commit SHA pinning. It permits GitHub-owned actions plus only the exact reviewed Azure Login 3.0.1 and Azure Artifact Signing 2.0.0 commits used by the release workflow.

The current test suite contains 80 passing cases covering conservative and aggressive URL matching, five merge strategies, dry-run reporting, named multi-profile execution, restore safety, SHA-256 manifests, manifest path validation, privacy-safe logging, Python and standalone Task Scheduler generation, scheduler configuration, absolute-path enforcement, readiness, active and stale locking, structured results, health history, failure rate limiting and recovery, notification redaction, process-override rejection, the PowerShell automation wrapper, failure artifact reporting, GUID handling, organization, retention, transactional writes, process controls, CLI behavior, and GUI errors.

## Contributing and support

Use [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow, branch and tag conventions, test requirements, and pull request rules. Use [SUPPORT.md](SUPPORT.md) for usage help. Participation is governed by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Report vulnerabilities privately through [SECURITY.md](SECURITY.md).

## Documentation maintenance requirement

Every project change must include a review and update of:

- [README.md](README.md) for installation, operation, behavior, limitations, or development guidance affected by the change.
- [assessment.md](assessment.md) for current status, open findings, release readiness, and verification results.
- [changelog.md](changelog.md) for a concise entry under `[Unreleased]`.
- [future-upgrades.md](future-upgrades.md) when priorities, dependencies, or candidate upgrades change.
- [completed-upgrades.md](completed-upgrades.md) when a tracked upgrade is implemented and verified.
- [SCHEDULING.md](SCHEDULING.md) when scheduler configuration, prompts, security boundaries, or execution behavior changes.

This requirement applies to code, tests, documentation, configuration, packaging, and workflow changes. Do not leave instructions or status statements that describe behavior the application no longer has.

When an upgrade is completed, remove it from `future-upgrades.md`, add it to `completed-upgrades.md` with its completion evidence, and add at least one new candidate to the future backlog. A completed upgrade must never appear in both files.
