# Browser Bookmark Tool Assessment

Last reviewed: 2026-08-07
Project version: 0.2.0
Release readiness: Needs CI verification

## Summary

The project is a Windows application for previewing, backing up, exporting, restoring, and organizing Chrome bookmarks and Microsoft Edge favorites. Version 0.2.0 provides transactional write and browser-process protections. The unreleased scheduler update adds a vendor-neutral local execution contract for Codex, Claude, Copilot, Windows Task Scheduler, and other trusted schedulers without exposing bookmark data to cloud agents.

## Current status

| Area | Status | Notes |
| --- | --- | --- |
| Packaging | Ready | Editable installation, module execution, and the batch launcher command path pass verification. |
| Automated tests | Passing | All 77 test cases pass on Python 3.13.3 across merge, preview, mapping, restore, integrity, logging, scheduling, automation configuration, path enforcement, locking, structured results, failure artifact reporting, PowerShell execution, transaction, process, CLI, and GUI paths. |
| Backup safety | Ready | Every run creates HTML and JSON backups plus a validated SHA-256 manifest. Microsecond timestamps prevent collisions, and filename-based retention ignores unrelated files. |
| Synchronization safety | Ready | Both replacements are prepared and validated before writes. Chrome is restored automatically if the Edge replacement fails. |
| Bookmark organization | Ready | Duplicate removal and recursive folder-first alphabetization are independently optional in the GUI and CLI. |
| URL matching | Ready | Conservative matching changes only scheme and host case. Aggressive whole-URL matching and trailing-slash collapse require explicit opt-in. |
| Merge and preview | Ready | Five strategies are available, and GUI or CLI dry-run reports make no filesystem or browser changes. |
| Restore | Ready | Chrome and Edge can be restored independently from JSON snapshots after preserving the current file. HTML remains a browser-import format. |
| Multi-profile support | Ready | Private named mapping files separate work and personal profile pairs; CLI runs one, several, or all mappings. |
| Integrity and logging | Ready | Manifests validate SHA-256 and size before pruning. Default logs contain operation metadata and counts but no bookmark URLs. |
| Scheduling | Ready | A common local PowerShell entrypoint provides private configuration, no-write readiness checks, atomic locks, privacy-safe JSON results, and explicit backup, dry-run, or sync modes for Codex, Claude, Copilot, and deterministic schedulers. |
| Windows distribution | Needs verification | Local tests and explicit Ruff 0.16.2 rules pass. A new Windows CI run is required after commit before the remote artifact is release-ready. |
| Chromium GUID handling | Ready | Existing Chrome GUIDs are preserved, imported nodes receive new UUIDs, duplicate GUIDs are rejected, and repeated synchronization remains stable. |
| Browser process handling | Ready | Running browsers block synchronization after backups and export. CLI users can explicitly force-close both process trees with `--close-browsers` or bypass detection with `--force`. |
| Repository security | Ready | Secret scanning, push protection, Dependabot, private vulnerability reporting, CodeQL, restricted SHA-pinned Actions, and protected `main` rules are enabled. Optional non-provider patterns and validity checks are unavailable. |
| Documentation | Good | The README documents current behavior, safety requirements, GUI and CLI use, backup restoration, limitations, development checks, and links to project tracking files. |
| Upgrade tracking | Good | Three priority tiers track proposed work, including separate macOS Chrome and Edge compatibility and phased Safari support, while a permanent ledger records completed upgrades and their verification evidence. |

## Strengths

- Creates raw backups before changing either browser file.
- Prepares and validates both replacement files before changing either browser.
- Uses `os.replace` for individual file replacement and restores Chrome automatically after an Edge replacement failure.
- Blocks synchronization when Chrome or Edge processes are running while preserving backup and export results.
- Can explicitly force-close Chrome and Edge process trees, verify closure, and then synchronize.
- Creates collision-resistant portable HTML backups and retains up to 50 backup sets.
- Orders retention by generated filename timestamps and leaves unrelated files and directories untouched.
- Ignores standard Chromium bookmark files and generated backup names to reduce accidental private-data commits.
- Generates unique UUIDs for imported bookmarks and folders and validates the merged collection for duplicate GUIDs.
- Exports portable Netscape bookmark HTML with escaped titles and URLs.
- Retains the union of bookmarks rather than propagating deletions.
- Optionally removes duplicate normalized URLs while retaining the first occurrence.
- Optionally alphabetizes folders and bookmarks recursively with folders first.
- Preserves case-sensitive paths and query values under default duplicate matching.
- Reports planned additions, duplicates, folder changes, and final counts without writing files.
- Supports independent restore and private named multi-profile workflows.
- Validates backup integrity and logs count-only operational data.
- Generates backup-first Task Scheduler scripts and a standalone Windows executable.
- Gives local AI schedulers a deterministic entrypoint without granting `--force`, repository mutation, or access to bookmark contents in structured results.
- Blocks concurrent scheduled runs and atomically publishes count-only results without local profile or backup paths.
- Detects Chrome and Edge `Default` and `Profile *` profiles.
- Keeps runtime dependencies in the Python standard library.

## Open findings

### Critical

No open critical findings.

### High

No open high findings.

### Medium

- The Ruff drift fix is implemented locally with an explicit rule set and the supported `ruff>=0.16.2,<0.17` range. The latest remote Windows CI runs predate this fix and remain failed. Commit and push the change, then confirm a complete Windows CI run before treating the workflow artifact as release-ready or moving `FUT-010` to completed upgrades.

### Low

- The standalone executable is not Authenticode-signed. Source builds and trusted workflow artifacts remain usable, but broad distribution should add signing and timestamping.

## Verification snapshot

Verified on Windows 11 with Python 3.13.3 on 2026-08-07.

- `py -m pip install -e .`: passed.
- `py -m browser_bookmark_sync --help`: passed.
- `Run Browser Bookmark Tool.bat --help`: passed and reached the application through the Python module.
- `py -m pytest -q`: passed with 77 cases, including private automation configuration, absolute-path enforcement, readiness, active and stale locks, backup, dry-run, blocked and browser-closing sync, process-override rejection, failure artifact reporting, privacy-safe results, CLI routing, and PowerShell wrapper execution.
- `py -m ruff check .`: passed with Ruff 0.16.2 and an explicit project rule set.
- `py -m py_compile browser_bookmark_sync.py test_sync.py`: passed.
- Standalone PyInstaller build: passed. The generated `BrowserBookmarkTool.exe --help` smoke test passed.
- Hidden Tkinter construction: passed with duplicate removal and alphabetization disabled by default.
- Live Windows `tasklist` detection: passed and identified the currently running `chrome.exe` and `msedge.exe` processes.
- `build.ps1`: produced `dist\BrowserBookmarkTool.exe` with PyInstaller 6.21.0.
- `dist\BrowserBookmarkTool.exe --help`: passed as a standalone CLI smoke test.
- `Invoke-BrowserBookmarkAutomation.ps1`: PowerShell syntax, readiness, and backup execution passed.
- `automation-config.example.json`: JSON parsing and schema loading passed.

GitHub repository settings were reviewed and updated on 2026-08-07. The About description and topics match the current Windows GUI and CLI. Issues remain enabled, while unused Projects, Wiki, Discussions, and Pages features are disabled. Pull requests use squash merge only, merged branches are deleted automatically, and branch update suggestions are enabled. The default branch blocks force pushes and deletion, enforces linear history and resolved review conversations, and applies protection to administrators without requiring pull requests or status checks.

Actions have read-only default workflow permissions, require full commit SHA pinning, and permit only GitHub-owned actions. Secret scanning, push protection, Dependabot security updates, private vulnerability reporting, and Python and Actions CodeQL default setup are enabled.

- The first Python CodeQL default-setup run passed with zero code-scanning alerts.
- Dependabot and secret-scanning alert counts are both zero.
- Non-provider secret patterns and secret validity checks remain unavailable for this account and are disabled.
- The Windows CI workflow uses verified official action SHAs, read-only contents permission, non-persisted checkout credentials, and a 20-minute job timeout. Its two current runs failed at lint before the explicit Ruff configuration was added; the replacement configuration passes locally and awaits a new remote run.

The documentation was reviewed against the current implementation and live GitHub configuration, including local AI scheduling, private configuration, structured results, concurrency, repository security, Windows CI status, and upgrade tracking on 2026-08-07.

## Maintenance requirement

Review and update this file with every project change. Update the review date, status table, findings, and verification results affected by the change. Remove resolved findings instead of leaving stale issues. Update `README.md` and record the same change in `changelog.md`.

When a tracked upgrade is implemented, remove it from `future-upgrades.md`, record it with verification evidence in `completed-upgrades.md`, and add at least one new candidate to the future backlog.
