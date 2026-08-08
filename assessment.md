# Browser Bookmark Tool Assessment

Last reviewed: 2026-08-08
Project version: 0.2.0
Release readiness: Ready for the next source release

## Summary

The project is a Windows application for previewing, backing up, exporting, restoring, and organizing Chrome bookmarks and Microsoft Edge favorites. Version 0.2.0 provides transactional write and browser-process protections. The unreleased scheduler update adds a vendor-neutral local execution contract, capped privacy-safe health history, and optional rate-limited failure notifications for Codex, Claude, Copilot, Windows Task Scheduler, and other trusted local schedulers.

## Current status

| Area | Status | Notes |
| --- | --- | --- |
| Packaging | Ready | Editable installation, module execution, and the batch launcher command path pass verification. |
| Automated tests | Passing | All 80 test cases pass on Python 3.13.3 across merge, preview, mapping, restore, integrity, logging, scheduling, automation configuration, path enforcement, locking, structured results, health history, notification suppression and redaction, failure artifact reporting, PowerShell execution, transaction, process, CLI, and GUI paths. |
| Backup safety | Ready | Every run creates HTML and JSON backups plus a validated SHA-256 manifest. Microsecond timestamps prevent collisions, and filename-based retention ignores unrelated files. |
| Synchronization safety | Ready | Both replacements are prepared and validated before writes. Chrome is restored automatically if the Edge replacement fails. |
| Bookmark organization | Ready | Duplicate removal and recursive folder-first alphabetization are independently optional in the GUI and CLI. |
| URL matching | Ready | Conservative matching changes only scheme and host case. Aggressive whole-URL matching and trailing-slash collapse require explicit opt-in. |
| Merge and preview | Ready | Five strategies are available, and GUI or CLI dry-run reports make no filesystem or browser changes. |
| Restore | Ready | Chrome and Edge can be restored independently from JSON snapshots after preserving the current file. HTML remains a browser-import format. |
| Multi-profile support | Ready | Private named mapping files separate work and personal profile pairs; CLI runs one, several, or all mappings. |
| Integrity and logging | Ready | Manifests validate SHA-256 and size before pruning. Default logs contain operation metadata and counts but no bookmark URLs. |
| Scheduling | Ready | A common local PowerShell entrypoint provides private configuration, no-write readiness checks, atomic locks, privacy-safe JSON results, capped allowlisted health history, disabled-by-default failure notifications, and explicit backup, dry-run, or sync modes. |
| Windows distribution | Ready with limitation | The latest two `main` Windows CI runs pass and produce a workflow artifact. The executable is not Authenticode-signed. |
| Chromium GUID handling | Ready | Existing Chrome GUIDs are preserved, imported nodes receive new UUIDs, duplicate GUIDs are rejected, and repeated synchronization remains stable. |
| Browser process handling | Ready | Running browsers block synchronization after backups and export. CLI users can explicitly force-close both process trees with `--close-browsers` or bypass detection with `--force`. |
| Repository security | Ready | Secret scanning, push protection, Dependabot, private vulnerability reporting, CodeQL, restricted SHA-pinned Actions, and protected `main` rules are enabled. Optional non-provider patterns and validity checks are unavailable. |
| Documentation | Ready | The README documents current behavior, safety requirements, GUI and CLI use, backup restoration, limitations, development checks, contribution rules, support scope, and security reporting. |
| Upgrade tracking | Good | Three priority tiers track proposed work, including release provenance, separate macOS Chrome and Edge compatibility, and phased Safari support. The completed ledger records the verified Ruff policy upgrade. |

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
- Records capped scheduled-run health using only operation status, mapping names, counts, duration, browser process names, and allowlisted error categories.
- Sends optional sanitized failure records to a local notifier once per consecutive matching failure and resets suppression after recovery.
- Detects Chrome and Edge `Default` and `Profile *` profiles.
- Keeps runtime dependencies in the Python standard library.

## Open findings

### Critical

No open critical findings.

### High

No open high findings.

### Medium

No open medium findings.

### Low

- The standalone executable is not Authenticode-signed. Source builds and trusted workflow artifacts remain usable, but broad distribution should add signing and timestamping.
- The repository has no version tags or GitHub Releases. Create the first release only after choosing the next version and completing the signed-package and checksum requirements.

## Verification snapshot

Verified on Windows 11 with Python 3.13.3 on 2026-08-08.

- `py -m pip install -e .`: passed.
- `py -m browser_bookmark_sync --help`: passed.
- `Run Browser Bookmark Tool.bat --help`: passed and reached the application through the Python module.
- `py -m pytest -q`: passed with 80 cases, including private automation configuration, absolute-path enforcement, readiness, active and stale locks, stale-lock health recovery, backup, dry-run, blocked and browser-closing sync, health allowlisting, repeated-failure suppression, recovery reset, notification redaction, process-override rejection, failure artifact reporting, privacy-safe results, CLI routing, and PowerShell wrapper execution.
- Python 3.11.9 isolated environment: all 80 tests, Ruff, compilation, and `pip check` passed.
- `py -m ruff check .`: passed with Ruff 0.16.2 and an explicit project rule set.
- `py -m py_compile browser_bookmark_sync.py test_sync.py`: passed.
- Package wheel build: passed. The wheel contains only the application module, project metadata, console entry point, and MIT license.
- Standalone PyInstaller build: passed. The generated `BrowserBookmarkTool.exe --help` smoke test passed.
- Hidden Tkinter construction: passed with duplicate removal and alphabetization disabled by default.
- Live Windows `tasklist` detection: passed and identified the currently running `chrome.exe` and `msedge.exe` processes.
- `build.ps1`: produced `dist\BrowserBookmarkTool.exe` with PyInstaller 6.21.0.
- `dist\BrowserBookmarkTool.exe --help`: passed as a standalone CLI smoke test.
- `Invoke-BrowserBookmarkAutomation.ps1`: PowerShell syntax, readiness, and backup execution passed.
- `automation-config.example.json`: JSON parsing and schema loading passed.
- Workflow, Dependabot, and issue-form YAML files parse successfully.
- `pip-audit`: no known vulnerable project dependencies.
- Bandit: no medium or high findings. Six low findings cover the intentional `subprocess` import and argument-list calls to Windows tools or the explicitly configured local notifier; none use `shell=True`.
- Root Markdown relative-link validation: passed.

GitHub repository settings were reviewed on 2026-08-08. The repository name, About description, topics, MIT license detection, and custom 1280 by 640 social preview match the current Windows GUI and CLI. The blank homepage is appropriate because the project has no separate site. Issues remain enabled, while unused Projects, Wiki, Discussions, and Pages features are disabled. Pull requests use squash merge only, merged branches are deleted automatically, and branch update suggestions are enabled. The default branch blocks force pushes and deletion, enforces linear history and resolved review conversations, and applies protection to administrators without requiring pull requests or status checks.

Actions have read-only default workflow permissions, cannot approve pull requests, require full commit SHA pinning, and permit only GitHub-owned actions. Secret scanning, push protection, Dependabot alerts and security updates, private vulnerability reporting, and Python and Actions CodeQL default setup are enabled. Weekly Dependabot version updates for Python and GitHub Actions are configured in this change.

- Python and Actions CodeQL default setup is configured and current runs pass with zero code-scanning alerts.
- Dependabot and secret-scanning alert counts are both zero.
- Non-provider secret patterns and secret validity checks remain unavailable for this account and are disabled.
- Windows CI runs `31238970704` and `31239476514` passed on `main`. Audit pull request run `31240802924` also passed Python 3.10 through 3.13, dependency checks, and the gated Windows executable build with current full-SHA official action pins. CodeQL run `31240802041` passed both Python and Actions analysis on the same commit.
- The repository has one protected branch, no rulesets, tags, releases, packages, deployments, environments, webhooks, deploy keys, repository secrets, or repository variables, and no collaborators other than the owner.
- Repository and full-history scans found no provider credential patterns. GitHub secret scanning also reports zero open alerts.

The documentation was reviewed against the current implementation and live GitHub configuration, including local AI scheduling, private configuration, structured results, health history, optional notification delivery, concurrency, repository security, Windows CI status, package metadata, community health files, and upgrade tracking on 2026-08-08.

## Maintenance requirement

Review and update this file with every project change. Update the review date, status table, findings, and verification results affected by the change. Remove resolved findings instead of leaving stale issues. Update `README.md` and record the same change in `changelog.md`.

When a tracked upgrade is implemented, remove it from `future-upgrades.md`, record it with verification evidence in `completed-upgrades.md`, and add at least one new candidate to the future backlog.
