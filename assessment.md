# Browser Bookmark Tool Assessment

Last reviewed: 2026-08-09
Project version: 0.3.0
Release readiness: Source ready; trusted signing credential required for binary release

## Summary

The project is a Windows application for previewing, reporting, backing up, exporting, cataloging, comparing, verifying, restoring, and organizing Chrome bookmarks and Microsoft Edge favorites, with disabled-by-default Firefox import and export. Version 0.3.0 combines transactional write and browser-process protections with privacy-safe machine-readable previews, cross-format preview comparison and count-only policy gates, read-only backup-set inventory, isolated backup verification, a vendor-neutral local execution contract, capped privacy-safe health history, optional rate-limited failure notifications, and fail-closed signed release automation. SignPath Foundation application readiness includes a public code-signing policy, privacy policy, explicit solo-maintainer roles, manual approval requirements, and enforced Windows release metadata. A trusted provider and verified signing integration are still required before the first binary release can be published.

## Current status

| Area | Status | Notes |
| --- | --- | --- |
| Packaging | Ready | Editable installation, module execution, and the batch launcher command path pass verification. |
| Automated tests | Passing | All 110 test cases pass on Python 3.13.3 across Firefox discovery, Places import and export, cross-browser matching, backup ordering, manifests, disabled-mode isolation, three-browser rollback, merge, machine-readable preview reports and policy gates, mapping, backup catalog and comparison, backup verification, restore, integrity, logging, scheduling, automation, transaction, process, CLI, and GUI paths. |
| Backup safety | Ready | Every run creates HTML and Chromium JSON backups plus a validated SHA-256 manifest. Enabled Firefox runs add a consistent SQLite backup before checkpoint or replacement. GUI and CLI cataloging groups and compares generated sets without changing them, while verification currently covers Chromium JSON snapshots. |
| Synchronization safety | Ready | Chrome and Edge replacements are prepared and validated before writes. Firefox export stages and validates SQLite from its backup. Edge failure restores Chrome, and Firefox replacement failure restores both Chromium files. |
| Bookmark organization | Ready | Duplicate removal and recursive folder-first alphabetization are independently optional in the GUI and CLI. |
| URL matching | Ready | Conservative matching changes only scheme and host case. Aggressive whole-URL matching and trailing-slash collapse require explicit opt-in. |
| Merge and preview | Ready | Five strategies are available. GUI and CLI dry runs make no browser or backup changes. CLI dry runs can atomically create a requested JSON or CSV report, with private bookmark details excluded by default and browser-profile destinations rejected. Version 1 JSON and CSV reports can be compared by mapping without reopening profiles, and optional count-only thresholds return a distinct policy failure code. |
| Restore | Ready | Chrome and Edge can be restored independently from validated JSON snapshots after preserving the current file. HTML remains a browser-import format. |
| Multi-profile support | Ready | Private named mapping files separate work and personal profiles; optional Firefox paths are ignored unless explicitly enabled. CLI runs one, several, or all mappings. |
| Integrity and logging | Ready | Manifests validate SHA-256 and size before pruning. Default logs contain operation metadata and counts but no bookmark URLs. |
| Scheduling | Ready | A common local PowerShell entrypoint provides private configuration, no-write readiness checks, atomic locks, privacy-safe JSON results, capped allowlisted health history, disabled-by-default failure notifications, and explicit backup, dry-run, or sync modes. |
| Windows distribution | Blocked on signing-provider onboarding | CI builds pass. The project is applying to SignPath Foundation, and release executables now enforce the product metadata required for signing. The existing Azure workflow remains fail-closed and unchanged until SignPath approval and integration details are available. No signing provider is configured. |
| Chromium GUID handling | Ready | Existing Chrome GUIDs are preserved, imported nodes receive new UUIDs, duplicate GUIDs are rejected, and repeated synchronization remains stable. |
| Browser process handling | Ready | Running Chrome or Edge blocks synchronization after backups and export. Firefox is checked only when it is an enabled write target. CLI users can explicitly force-close selected process trees with `--close-browsers` or bypass detection with `--force`. |
| Repository security | Ready | Secret scanning, push protection, Dependabot, private vulnerability reporting, CodeQL, restricted SHA-pinned Actions, and a solo-maintainer `main` ruleset are enabled. Optional non-provider patterns and validity checks are unavailable. |
| Documentation | Ready | The README includes the repository social preview and documents current behavior, safety requirements, GUI and CLI use, installation and removal, backup restoration, limitations, download status, privacy, code-signing roles, development checks, contribution rules, support scope, and security reporting. |
| Upgrade tracking | Good | Completed `FUT-020` is recorded with replacement candidate `FUT-021` for reusable private policy profiles. Three priority tiers still track SignPath integration, release provenance, recovery, reporting, macOS Chrome and Edge compatibility, and phased Safari support. |

## Strengths

- Creates raw backups before changing any supported browser data.
- Prepares and validates both Chromium replacements and an enabled Firefox SQLite replacement before changing live data.
- Uses `os.replace` for individual file replacement and restores Chrome automatically after an Edge replacement failure.
- Restores both Chrome and Edge automatically if the final Firefox replacement fails.
- Blocks synchronization when Chrome or Edge processes are running while preserving backup and export results.
- Can explicitly force-close selected browser process trees, verify closure, and then synchronize.
- Creates collision-resistant portable HTML backups and retains up to 50 backup sets.
- Orders retention by generated filename timestamps and leaves unrelated files and directories untouched.
- Ignores standard Chromium bookmark files and generated backup names to reduce accidental private-data commits.
- Generates unique UUIDs for imported bookmarks and folders and validates the merged collection for duplicate GUIDs.
- Exports portable Netscape bookmark HTML with escaped titles and URLs.
- Retains the union of bookmarks rather than propagating deletions.
- Optionally removes duplicate normalized URLs while retaining the first occurrence.
- Optionally alphabetizes folders and bookmarks recursively with folders first.
- Preserves case-sensitive paths and query values under default duplicate matching.
- Reports planned additions, duplicates, folder changes, and final counts to standard output without writing files unless a preview report path is explicitly requested.
- Atomically writes optional versioned JSON or CSV preview reports for one or several mappings without creating backups, pruning files, or changing browser data.
- Keeps report output count-only by default, requires an explicit option for bookmark names and URLs, and rejects destinations inside selected browser profiles.
- Compares version 1 JSON and CSV preview reports by mapping, reports only settings and counts, and never reopens browser profiles or changes either input.
- Rejects detailed report comparison by default and provides distinct exit codes for invalid input and exceeded aggregate policy thresholds.
- Supports independent restore and private named multi-profile workflows.
- Verifies recovery snapshots in isolated temporary profiles and reports only bookmark counts, folder counts, manifest name, and no-write status.
- Catalogs generated backup sets without opening live profiles, distinguishes completeness from validity, flags missing or extra members, and reports only browser types and counts.
- Compares only complete, valid sets and uses SQLite immutable mode so Firefox inventory cannot create recovery-directory sidecars.
- Validates backup integrity and logs count-only operational data.
- Generates backup-first Task Scheduler scripts and a standalone Windows executable.
- Embeds and validates Windows product name, version, description, and original-filename metadata in release executables.
- Publishes explicit code-signing roles, manual approval controls, local-data privacy boundaries, and pending-provider status without representing unsigned binaries as trusted releases.
- Gives local AI schedulers a deterministic entrypoint without granting `--force`, repository mutation, or access to bookmark contents in structured results.
- Blocks concurrent scheduled runs and atomically publishes count-only results without local profile or backup paths.
- Records capped scheduled-run health using only operation status, mapping names, counts, duration, browser process names, and allowlisted error categories.
- Sends optional sanitized failure records to a local notifier once per consecutive matching failure and resets suppression after recovery.
- Detects Chrome and Edge `Default` and `Profile *` profiles.
- Discovers Firefox profiles explicitly from `profiles.ini`, honors relative and absolute entries, and leaves Firefox disabled by default.
- Keeps runtime dependencies in the Python standard library.

## Open findings

### Critical

No open critical findings.

### High

No open high findings.

### Medium

No open medium findings.

### Low

- SignPath Foundation has not approved or configured the project. The repository must not add provider-specific signing integration or represent artifacts as SignPath-signed until onboarding details are supplied and reviewed.
- The existing Azure Artifact Signing account, verified public-trust certificate profile, OIDC federated identity, signer role, environment values, and expected publisher subject are not configured. The workflow intentionally stops before publishing without them.
- The repository has no version tags, GitHub Releases, downloads, stars, forks, or other project-specific adoption evidence. SignPath requires a project to be released in the form being signed and to have verifiable reputation, so application acceptance remains uncertain. Do not publish an unsigned executable solely to satisfy that condition.
- Firefox export staging is validated against a copied backup of the current local Places schema and synthetic failure cases. Unsupported schemas fail before replacement. Direct Firefox snapshot verification and restore remain planned under `FUT-018`.

## Verification snapshot

Verified on Windows 11 with Python 3.13.3 on 2026-08-08.

- `py -m pip install -e .`: passed.
- `py -m browser_bookmark_sync --help`: passed.
- `Run Browser Bookmark Tool.bat --help`: passed and reached the application through the Python module.
- `py -m pytest -q`: passed with 110 cases, including explicit Firefox discovery, Places import and export, conservative and aggressive cross-browser matching, backup-before-write ordering, Firefox manifest validation, process blocking, disabled-mode isolation, three-browser rollback, JSON and CSV preview reports, cross-format comparison and policy gates, read-only backup catalog and comparison, Chromium snapshot verification, automation, CLI, and GUI paths.
- Python 3.11.9 isolated environment: the prior 80-case baseline, Ruff, compilation, and `pip check` passed. The 110-case suite is verified on Python 3.13.3 and awaits CI matrix verification.
- `py -m ruff check .`: passed with Ruff 0.16.2 and an explicit project rule set.
- `py -m py_compile browser_bookmark_sync.py test_sync.py`: passed.
- Package wheel build: passed. The wheel contains only the application module, project metadata, console entry point, and MIT license.
- Standalone PyInstaller build: passed. The generated `BrowserBookmarkTool.exe --help` smoke test passed.
- Hidden Tkinter construction: passed with duplicate removal and alphabetization disabled and the backup catalog filter set to `all` by default.
- Live Windows `tasklist` detection: passed and identified the currently running `chrome.exe` and `msedge.exe` processes.
- Live Firefox discovery, count-only schema read, consistent backup, and temporary-profile export staging: passed against one discovered profile without printing bookmark titles, URLs, or profile paths and without checkpointing or replacing live data.
- `build.ps1`: produced `dist\BrowserBookmarkTool.exe` with PyInstaller 6.21.0.
- `dist\BrowserBookmarkTool.exe --help`: passed as a standalone CLI smoke test.
- `Invoke-BrowserBookmarkAutomation.ps1`: PowerShell syntax, readiness, and backup execution passed.
- `automation-config.example.json`: JSON parsing and schema loading passed.
- Workflow, Dependabot, and issue-form YAML files parse successfully.
- Release packaging validation: the unsigned local validation mode passed for version 0.3.0, including enforced Windows product metadata, executable smoke test, CycloneDX validation, policy and privacy documents in the archive, archive contents, and independent checksum verification. Trusted signing validation cannot run until a code-signing certificate is supplied.
- `pip-audit`: no known vulnerabilities in the runtime or resolved release-tool dependency sets, including CycloneDX 7.3.1 and PyInstaller 6.21.0.
- Bandit: no medium or high findings. Six low findings cover the intentional `subprocess` import and argument-list calls to Windows tools or the explicitly configured local notifier; none use `shell=True`.
- Root Markdown relative-link validation: passed.

GitHub repository settings were reviewed on 2026-08-08. The repository name, About description, topics including `firefox`, and MIT license detection match the current Windows GUI and CLI. A new 1280 by 640 JPEG social preview source is tracked at `.github/social-preview.jpg`, remains below GitHub's 1 MB upload limit, and is ready for upload through the repository settings. The blank homepage is appropriate because the project has no separate site. Issues remain enabled, while unused Projects, Wiki, Discussions, and Pages features are disabled. Pull requests use squash merge only, merged branches are deleted automatically, and branch update suggestions are enabled. The active solo-maintainer ruleset targets the default branch, allows repository administrators to bypass in emergencies, blocks deletion and non-fast-forward pushes, requires a pull request with zero approvals, requires resolved review conversations, requires the Python 3.10 through 3.13 tests and Windows executable build, requires the branch to be current, and permits squash merge only. The prior classic branch protection was removed after the ruleset was verified active.

Actions have read-only default workflow permissions, cannot approve pull requests, and require full commit SHA pinning. The allowlist permits GitHub-owned actions plus only the exact reviewed Azure Login 3.0.1 and Azure Artifact Signing 2.0.0 commit SHAs used by the release workflow. Secret scanning, push protection, Dependabot alerts and security updates, private vulnerability reporting, and Python and Actions CodeQL default setup are enabled. Weekly Dependabot version updates for Python and GitHub Actions are configured.

- Python and Actions CodeQL default setup is configured and current runs pass with zero code-scanning alerts.
- Dependabot and secret-scanning alert counts are both zero.
- Non-provider secret patterns and secret validity checks remain unavailable for this account and are disabled.
- Windows CI runs `31238970704` and `31239476514` passed on `main`. Audit pull request run `31240802924` also passed Python 3.10 through 3.13, dependency checks, and the gated Windows executable build with current full-SHA official action pins. CodeQL run `31240802041` passed both Python and Actions analysis on the same commit. Audit PR #1 was marked ready and squash-merged as commit `27a8c8a5d1a23b7478342e540588eeccf2656fe9`.
- The repository has one active ruleset and a `release` environment restricted to `v*` tags. It has no tags, releases, packages, deployments, webhooks, deploy keys, Azure signing secrets or variables, or collaborators other than the owner.
- Repository and full-history scans found no provider credential patterns. GitHub secret scanning also reports zero open alerts.

The documentation was reviewed against the current implementation and the 2026-08-08 live GitHub configuration snapshot, including optional Firefox import and export, machine-readable preview reports, cross-format preview comparison and policy gates, read-only backup catalog and comparison, isolated backup verification, local AI scheduling, private configuration, structured results, health history, optional notification delivery, concurrency, repository security, Windows CI status, release metadata, SignPath application readiness, privacy, community health files, and upgrade tracking on 2026-08-09.

## Maintenance requirement

Review and update this file with every project change. Update the review date, status table, findings, and verification results affected by the change. Remove resolved findings instead of leaving stale issues. Update `README.md` and record the same change in `changelog.md`.

When a tracked upgrade is implemented, remove it from `future-upgrades.md`, record it with verification evidence in `completed-upgrades.md`, and add at least one new candidate to the future backlog.
