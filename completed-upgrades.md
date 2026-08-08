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
