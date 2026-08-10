# Completed Upgrades

This file records implemented and verified project upgrades. Completed entries are permanent history and must not remain in [future-upgrades.md](future-upgrades.md).

## Completion rules

When an upgrade is completed:

1. Remove its entry from `future-upgrades.md`.
2. Add it here with the original ID and title, completion date, release version, implementation summary, and verification evidence.
3. Add at least one new upgrade option to `future-upgrades.md` and assign a priority tier.
4. Update `README.md`, `assessment.md`, and `changelog.md` in the same change set.
5. Confirm no completed ID or title remains in the future backlog.

## Baseline completed before backlog tracking

The following capabilities were already complete when the upgrade tracking files were introduced on 2026-08-07. They establish the project baseline and were not promoted from the future backlog.

### BASE-001: Transactional Chrome and Edge synchronization

- Completed: 2026-08-07
- Release: 0.2.0
- Summary: Prepares and validates both replacement files, blocks unsafe live-browser writes, and restores Chrome automatically if the Edge replacement fails.
- Verification: Transaction, first-write failure, second-write failure, process detection, forced synchronization, and browser-closing tests pass.

### BASE-002: Backup, export, integrity, and recovery

- Completed: 2026-08-07
- Release: 0.2.0
- Summary: Retains up to 50 raw JSON recovery backups and portable HTML backups, creates SHA-256 manifests, and supports independent Chrome or Edge JSON restore.
- Verification: Backup retention, rapid backup creation, manifest validation, restore safety, and HTML export tests pass.

### BASE-003: Optional organization and merge controls

- Completed: 2026-08-07
- Release: 0.2.0
- Summary: Adds optional duplicate removal, alphabetization, conservative or aggressive URL matching, five merge strategies, and no-write previews.
- Verification: Matching, organization, strategy, and dry-run tests pass with safe options disabled by default.

### BASE-004: Profiles, automation, packaging, and CI

- Completed: 2026-08-07
- Release: 0.2.0
- Summary: Adds named multi-profile mappings, privacy-safe logs, Task Scheduler script generation, a standalone Windows build, and SHA-pinned Windows CI.
- Verification: Mapping, logging, task generation, GUI, CLI, batch launcher, PyInstaller, and workflow checks pass.

## Completed after backlog tracking

### FUT-010: Deterministic lint configuration

- Completed: 2026-08-08
- Release: Unreleased
- Summary: Defines an explicit Ruff rule set and supported Ruff range, verifies the same policy locally and in Windows CI, and adds weekly grouped dependency updates for Python and GitHub Actions.
- Verification: Ruff 0.16.2 passes locally. Windows CI runs `31238970704` and `31239476514` passed after the policy fix. The audit workflow adds Python 3.10 through 3.13 coverage and current SHA-pinned official actions.

### COMP-001: Scheduler-safe local AI execution contract

- Completed: 2026-08-07
- Release: Unreleased
- Summary: Adds a vendor-neutral local PowerShell entrypoint, private versioned configuration, no-write readiness checks, active and stale run locking, atomic privacy-safe JSON results, and copy-ready boundaries for Codex, Claude, and Copilot scheduling.
- Verification: Configuration validation, readiness, concurrency, stale-lock recovery, backup, dry-run, blocked synchronization, explicit browser closure, structured-result privacy, CLI routing, and PowerShell wrapper execution tests pass. Scheduled execution has no `--force` option.

### FUT-012: Scheduled-run health and failure notifications

- Completed: 2026-08-07
- Release: Unreleased
- Summary: Adds capped allowlisted health history for every scheduler run and optional local failure delivery through a configured command. Notifications are disabled by default, contain only the sanitized health record, suppress consecutive matching failures, and reset after a successful run or different failure.
- Verification: The 80-case suite covers successful health records, blocked synchronization, stale-lock recovery counts, repeated-failure suppression, recovery reset, disabled defaults, and redaction of bookmark titles, URLs, browser and backup paths, configuration values, and credentials. Ruff, Python compilation, and diff checks pass.

### FUT-006: Firefox bookmark support

- Completed: 2026-08-08
- Release: Unreleased
- Summary: Adds explicit Windows Firefox profile discovery, optional Places import, opt-in export to a tool-owned Firefox folder, consistent SQLite backups, manifest coverage, Firefox process controls, and rollback of both Chromium files when Firefox replacement fails. Firefox remains disabled by default across the GUI, CLI, mappings, and scheduler configuration.
- Verification: The 94-case suite covers explicit relative and absolute profile discovery, live Places schema reading, conservative and aggressive cross-browser matching, disabled-mode isolation, backup-before-write ordering, manifest integrity, Firefox export, process blocking, and three-browser rollback. Ruff, Python compilation, and temporary-profile export staging from a copied live Firefox backup pass.

### COMP-002: SignPath Foundation application readiness

- Completed: 2026-08-08
- Release: Unreleased
- Summary: Adds a public code-signing policy, privacy policy, explicit solo-maintainer signing roles, manual approval requirements, honest download and provider status, and enforced Windows product metadata. Provider onboarding and workflow integration remain tracked separately under `FUT-016`.
- Verification: The unsigned release-package validation confirms ProductName, ProductVersion, FileDescription, and OriginalFilename metadata; includes both policy documents in the release archive; and retains executable smoke testing, CycloneDX validation, checksum verification, and fail-closed signing publication.

### FUT-002: Automated restore verification

- Completed: 2026-08-08
- Release: Unreleased
- Summary: Adds GUI and CLI verification that copies a selected JSON recovery snapshot into an isolated temporary Chromium profile, validates required roots and bookmark-node structure, rejects malformed or duplicate GUIDs, verifies the matching SHA-256 manifest, and returns a count-only no-write report.
- Verification: The 88-case suite covers valid snapshots, corrupt JSON, invalid Chromium structure, duplicate GUIDs, automatic and explicit manifest mismatches, live-profile preservation, and concise GUI and CLI reports. Ruff and Python compilation pass.

### FUT-017: Backup-set catalog and comparison

- Completed: 2026-08-09
- Release: Unreleased
- Summary: Adds read-only GUI and CLI inventory that groups generated backups by timestamp, separates completeness from validity, filters complete, incomplete, valid, and invalid sets, reports count-only Chrome, Edge, and Firefox content, calculates changes from the previous complete and valid set, and directly compares two verified sets.
- Verification: The 100-case suite covers complete sets, missing and extra members, manifest mismatches, unrelated files and directories, CLI filters and comparison, GUI output, count privacy, and exact before-and-after backup-directory equality. Firefox catalog reads use SQLite immutable mode and create no WAL or shared-memory sidecars. Ruff and Python compilation pass.
