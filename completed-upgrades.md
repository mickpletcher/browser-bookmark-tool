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

### FUT-004: Machine-readable preview reports

- Completed: 2026-08-09
- Release: Unreleased
- Summary: Adds optional atomic JSON and CSV output for direct and multi-mapping dry runs. Versioned default reports contain only settings, counts, and change categories. The explicit `--include-bookmark-details` option adds merged bookmark names, URLs, and folder paths, while report destinations inside selected browser profiles are rejected.
- Verification: The 104-case suite covers default JSON privacy, explicit JSON details, default and detailed CSV schemas, multi-mapping aggregation, unsupported extensions, unsafe browser-profile destinations, option dependencies, exact browser-file preservation, absent backup directories, and a fail-on-call backup-pruning guard. Ruff and Python compilation pass.

### FUT-020: Preview report comparison and policy gates

- Completed: 2026-08-09
- Release: Unreleased
- Summary: Adds read-only comparison of version 1 JSON and CSV preview reports matched by mapping name. Count-only output covers settings, browser counts, planned additions, duplicates, and folder changes. Optional aggregate thresholds return exit code `2`, while detailed reports require an explicit private-data acknowledgment and still never print bookmark details.
- Verification: The 110-case suite covers cross-format schema validation, missing and duplicate mappings, settings and count changes, passing and failing policy thresholds, detailed-report rejection and acknowledgment, count-only output, and exact before-and-after input-directory equality. Ruff and Python compilation pass.

### FUT-021: Reusable preview policy profiles

- Completed: 2026-08-09
- Release: Unreleased
- Summary: Adds private version 1 JSON policies with an exact baseline report SHA-256, expected mapping contract, aggregate count limits, and optional per-mapping overrides. Policies fail closed on malformed schemas, baseline mismatches, missing or unexpected mappings, and conflicting direct thresholds. A sanitized path-free example is tracked while real policies remain ignored.
- Verification: The 122-case suite covers aggregate and per-mapping limits, inherited defaults, baseline hash validation, missing and unexpected mappings, malformed versions, hashes, names, and limits, detailed-report acknowledgment, privacy-safe output, CLI conflicts, the sanitized example, and exact no-write behavior. Ruff and Python compilation pass.

### FUT-022: Machine-readable preview policy results

- Completed: 2026-08-09
- Release: Unreleased
- Summary: Adds optional atomic version 1 JSON results for preview comparisons and policy decisions. Results contain the input report hashes, policy hash when used, expected mapping names, aggregate and per-mapping counts, configured limits, violations, status, and exit code while excluding private bookmark fields and every local path.
- Verification: The 129-case suite covers passing and failed gates, exact schema shape, input and policy hashes, aggregate and per-mapping values, protected report and policy destinations, detailed-report acknowledgment and redaction, atomic replacement, invalid options, and fail-on-call guards against browser or backup access. Ruff and Python compilation pass.

### FUT-013: macOS Chrome, Edge, and Firefox compatibility

- Completed: 2026-08-09
- Release: Unreleased
- Summary: Adds native macOS Chrome, Edge, and Firefox profile discovery, platform-specific process blocking and explicit closure, portable shell execution, backup-only `launchd` generation, macOS package metadata, and a SHA-pinned native CI build while preserving Windows behavior. Safari remains separate under `FUT-011`.
- Verification: The 135-case suite covers macOS standard profile discovery, executable-name process detection, exact-name closure, platform-aware restore blocking, launchd generation, existing transactional and rollback paths, and all Windows regressions. Ruff, compilation, shell and CLI smoke tests, physical-Mac discovery and process checks, and a native PyInstaller executable smoke test pass.

### FUT-018: Firefox recovery verification and restore

- Completed: 2026-08-09
- Release: Unreleased
- Summary: Adds isolated Firefox SQLite snapshot verification and GUI and CLI restore with manifest, integrity, Places schema, and required-root validation; platform-native process blocking; consistent preservation of the current database; staged replacement; stale WAL and shared-memory cleanup; and rollback-safe failure handling.
- Verification: The 142-case suite covers valid, corrupt, mismatched, unsupported-schema, running-process, stale-sidecar, replacement-failure, GUI, and CLI paths. Ruff, compilation, dependency, and shell smoke checks pass. Physical macOS copied-profile and Windows 11 validation both pass without changing the live macOS profile.

### FUT-011 phase 1: Read-only Safari bookmarks

- Completed: 2026-08-09
- Release: Unreleased
- Summary: Delivers the completed read-only portion of still-open `FUT-011`: macOS discovery, validated plist copies, manifest integrity, bookmark-only parsing, preview and merge planning, duplicate handling, organization, portable HTML export, and GUI/CLI support. It contains no Safari write path.
- Verification: The 154-case suite covers discovery, binary plist parsing, nested folders, Reading List exclusion, malformed and unsupported data, duplicates, backup integrity, HTML export, guided import preparation, privacy, unsupported platforms, GUI/CLI behavior, and existing-browser regressions. A physical Mac read and validated an isolated backup containing 285 bookmarks and 61 folders, verified its manifest, and confirmed the live plist hash was unchanged.

### FUT-025: Cross-platform recovery rehearsal

- Completed: 2026-08-10
- Release: Unreleased
- Summary: Adds `--rehearse-recovery` for complete backup sets. The command validates manifest integrity and represented-browser membership, restores Chrome, Edge, optional Firefox, and Safari artifacts only under an automatically removed temporary directory, verifies restored schemas and counts, rejects live profile and process-control options, and emits count-only status or the failing stage.
- Verification: The 160-case suite passes on Python 3.11 and 3.13 and covers Windows and macOS behavior, mixed-browser restoration, complete and incomplete membership, corrupt manifests, unsupported Firefox schemas, isolated restore failures, privacy-safe CLI output, exact backup-directory preservation, no live discovery or process access, Firefox sidecar isolation, Ruff, and Python compilation. Physical Windows source and packaged-executable rehearsals passed against a disposable Chrome, Edge, and Firefox set with 291, 321, and 294 bookmarks; backup and live-profile hashes were unchanged and temporary data was removed.
