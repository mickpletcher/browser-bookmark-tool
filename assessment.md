# Browser Bookmark Tool Assessment

Last reviewed: 2026-08-07
Project version: 0.1.0
Release readiness: Ready

## Summary

The project is a clear, small application for backing up, exporting, and organizing Chrome bookmarks and Microsoft Edge favorites on Windows. Its conservative union model reduces accidental bookmark loss. Optional duplicate removal and recursive alphabetization are available in the GUI and CLI. Packaging, automated tests, transactional writes, running-browser protection, automatic browser closure, collision-resistant HTML backups, and unique imported GUID handling are working.

## Current status

| Area | Status | Notes |
| --- | --- | --- |
| Packaging | Ready | Editable installation, module execution, and the batch launcher command path pass verification. |
| Automated tests | Passing | All 27 test cases pass on Python 3.13.3, including GUID, repeat-sync, organization, backup retention, transaction, process, closure, CLI, and GUI paths. |
| Backup safety | Ready | Every run creates a portable HTML backup and raw JSON recovery snapshots. Microsecond timestamps prevent rapid-run collisions, and retention accepts 1 through 50 sets with a default of 50. |
| Synchronization safety | Ready | Both replacements are prepared and validated before writes. Chrome is restored automatically if the Edge replacement fails. |
| Bookmark organization | Ready | Duplicate removal and recursive folder-first alphabetization are independently optional in the GUI and CLI. |
| Chromium GUID handling | Ready | Existing Chrome GUIDs are preserved, imported nodes receive new UUIDs, duplicate GUIDs are rejected, and repeated synchronization remains stable. |
| Browser process handling | Ready | Running browsers block synchronization after backups and export. CLI users can explicitly force-close both process trees with `--close-browsers` or bypass detection with `--force`. |
| Documentation | Good | The README documents current behavior, safety requirements, GUI and CLI use, backup restoration, limitations, development checks, and links to project tracking files. |

## Strengths

- Creates raw backups before changing either browser file.
- Prepares and validates both replacement files before changing either browser.
- Uses `os.replace` for individual file replacement and restores Chrome automatically after an Edge replacement failure.
- Blocks synchronization when Chrome or Edge processes are running while preserving backup and export results.
- Can explicitly force-close Chrome and Edge process trees, verify closure, and then synchronize.
- Creates collision-resistant portable HTML backups and retains up to 50 backup sets.
- Generates unique UUIDs for imported bookmarks and folders and validates the merged collection for duplicate GUIDs.
- Exports portable Netscape bookmark HTML with escaped titles and URLs.
- Retains the union of bookmarks rather than propagating deletions.
- Optionally removes duplicate normalized URLs while retaining the first occurrence.
- Optionally alphabetizes folders and bookmarks recursively with folders first.
- Detects Chrome and Edge `Default` and `Profile *` profiles.
- Keeps the implementation small and readable.

## Open findings

### Critical

No open critical findings.

### High

No open high findings.

### Medium

No open medium findings.

### Low

No open low findings.

## Verification snapshot

Verified on Windows 11 with Python 3.13.3 on 2026-08-07.

- `py -m pip install -e .`: passed.
- `py -m browser_bookmark_sync --help`: passed.
- `Run Browser Bookmark Tool.bat --help`: passed and reached the application through the Python module.
- `py -m pytest -q`: passed with 27 cases, including GUID regeneration, duplicate rejection, repeat-sync stability, HTML backup collisions, 50-backup pruning, automatic browser closure, process handling, CLI and GUI paths, organization options, and simulated write failures.
- `py -m py_compile browser_bookmark_sync.py test_sync.py`: passed.
- Hidden Tkinter construction: passed with duplicate removal and alphabetization disabled by default.
- Live Windows `tasklist` detection: passed and identified the currently running `chrome.exe` and `msedge.exe` processes.

The documentation was reviewed against the current 0.1.0 implementation, GUID handling, optional bookmark organization, transactional writes, running-browser protection, browser closure, and HTML backup retention on 2026-08-07.

## Maintenance requirement

Review and update this file with every project change. Update the review date, status table, findings, and verification results affected by the change. Remove resolved findings instead of leaving stale issues. Update `README.md` and record the same change in `changelog.md`.
