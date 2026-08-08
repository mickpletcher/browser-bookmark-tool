# Future Upgrades

This file contains proposed upgrades that are not implemented. Priority reflects current value, safety, and implementation readiness.

## Tracking rules

- Keep each proposed upgrade in exactly one priority tier.
- Remove an upgrade from this file after it is implemented and verified.
- Add the completed upgrade to [completed-upgrades.md](completed-upgrades.md) with its completion date, release version, summary, and verification evidence.
- Add at least one new upgrade option to this file whenever an upgrade is completed. Assign the new option to the appropriate tier.
- Update [README.md](README.md), [assessment.md](assessment.md), and [changelog.md](changelog.md) in the same change set.
- Reprioritize existing entries when risk, dependencies, or project goals change.

## Priority 1: Near term

These upgrades address distribution trust, recovery confidence, and release integrity.

### FUT-001: Authenticode signing and timestamping

Sign the standalone Windows executable through CI using protected credentials and a trusted timestamp service.

Acceptance criteria:

- The release executable has a valid Authenticode signature.
- Signature verification runs during the release workflow.
- Signing secrets and certificates are not stored in the repository or build artifacts.
- The README documents how users verify the signature.

### FUT-002: Automated restore verification

Add a non-destructive verification workflow that restores a selected JSON backup into a temporary profile structure and validates its Chromium schema, GUID uniqueness, and manifest integrity.

Acceptance criteria:

- Verification never replaces a live browser file.
- Invalid JSON, duplicate GUIDs, and manifest mismatches produce clear failures.
- GUI and CLI users receive a concise verification report.
- Tests cover valid, corrupted, and mismatched backups.

### FUT-003: Signed release packages and checksums

Create versioned release packages containing the executable, documentation, license, and published SHA-256 checksums.

Acceptance criteria:

- CI creates deterministic package names tied to the project version.
- A checksum file is generated and verified before artifact upload.
- Package contents exclude browser data, local mappings, logs, and generated task scripts.
- Release instructions document checksum verification in PowerShell.

### FUT-010: Deterministic lint configuration

Define stable Ruff rules and a tested version range so local development and Windows CI evaluate the same code with the same policy.

Acceptance criteria:

- `pyproject.toml` explicitly defines the enabled Ruff rule set.
- Development dependencies prevent unreviewed Ruff behavior changes from breaking CI.
- The current source and tests pass locally and on Windows CI with the selected configuration.
- Dependency update guidance includes a lint-policy review before the allowed Ruff range changes.

## Priority 2: Planned

These upgrades improve reporting, multi-profile administration, and browser coverage.

### FUT-004: Machine-readable preview reports

Allow dry-run results to be saved as privacy-safe JSON or CSV reports for review and automation.

Acceptance criteria:

- Reports contain counts and change categories without bookmark URLs by default.
- An explicit option controls whether bookmark details are included.
- Report generation performs no browser writes or backup pruning.
- JSON and CSV output are covered by tests.

### FUT-005: Multi-profile batch dashboard

Add a GUI view for selecting, previewing, and running multiple named profile mappings with independent results.

Acceptance criteria:

- Each mapping shows its profiles, status, and preview counts.
- A failure in one mapping does not hide results for other mappings.
- Synchronization still enforces browser-process safety per run.
- Private mapping paths remain excluded from Git.

### FUT-006: Firefox bookmark support

Add optional Firefox import and export support without weakening the current Chrome and Edge transaction guarantees.

Acceptance criteria:

- Firefox profile discovery is explicit and testable.
- Firefox data is backed up before any supported write.
- Cross-browser duplicate matching follows the selected matching mode.
- Firefox support can be disabled without changing Chrome and Edge behavior.

### FUT-013: macOS Chrome and Edge compatibility

Make the existing Chrome and Edge backup, preview, organization, restore, and synchronization workflow run natively on macOS before adding Safari support.

Acceptance criteria:

- Platform adapters isolate browser profile discovery, process detection, browser closure, scheduling, launchers, and packaging without changing verified Windows behavior.
- Chrome and Microsoft Edge profiles are discovered from supported macOS locations, with explicit paths still available for nonstandard profiles.
- Backup, dry-run, HTML export, restore, deduplication, alphabetization, and transactional synchronization pass on a physical Mac.
- Browser-process safeguards detect Chrome and Edge on macOS, block writes by default, and test any explicit closure option without weakening rollback guarantees.
- A portable `python3` or shell entrypoint and documented `launchd`, Codex, Claude, and Copilot scheduling paths replace Windows-only launcher assumptions on macOS.
- macOS CI runs the automated suite and performs a native packaging smoke test, while physical Mac validation covers local browser files and permissions that CI cannot reproduce.
- Safari remains outside this upgrade and is implemented separately under `FUT-011` after the shared macOS platform layer is stable.

### FUT-011: Safari backup and synchronization on macOS

Add a separate macOS implementation for backing up, previewing, organizing, and synchronizing Safari bookmarks with supported Chromium browsers.

Acceptance criteria:

- The first delivery supports Safari bookmark backup, preview, merge, and portable HTML export without direct Safari writes.
- Safari import and export use documented macOS and Safari mechanisms wherever possible.
- The feature handles bookmarks only and never exports passwords, history, credit cards, extensions, Reading List data, or open tabs.
- The tool detects or clearly warns about iCloud Safari synchronization before any write because changes may propagate to other Apple devices.
- Automated writes require Safari to be closed, prepare and validate all replacements first, preserve recovery data, and provide rollback after a partial failure.
- Safari support is implemented as a separate macOS adapter and does not weaken Windows Chrome and Edge behavior.
- Tests cover supported macOS and Safari versions, malformed exports, duplicate handling, iCloud warnings, backup integrity, and failed writes.

### FUT-014: Notification delivery verification and provider templates

Add a safe delivery test and reviewed local notifier examples for scheduled-run failure records.

Acceptance criteria:

- A no-bookmark test command sends a synthetic allowlisted failure record through the configured notification command.
- Provider templates accept the JSON record through standard input and do not require credentials in command arguments or repository files.
- Delivery timeouts, missing executables, and nonzero notifier exits produce a privacy-safe diagnostic without exposing command contents or credentials.
- Testing notification delivery does not access browser profiles, create backups, change bookmarks, or alter failure suppression history.
- Tests cover successful delivery, timeout, missing command, nonzero exit, and payload redaction.

## Priority 3: Later

These upgrades add optional portability and stronger protection for stored data.

### FUT-007: Encrypted backup archives

Support optional encrypted archives for JSON, HTML, manifests, and logs using user-supplied credentials or Windows-protected keys.

Acceptance criteria:

- Encryption is optional and disabled by default.
- Credentials are never written to logs, manifests, command history examples, or repository files.
- Archive integrity is verified before old backup sets are pruned.
- Recovery instructions cover encrypted and unencrypted backups.

### FUT-008: Portable configuration bundle

Export and import sanitized application settings without including browser data or private local profile paths.

Acceptance criteria:

- The bundle includes organization, matching, merge, retention, and logging preferences.
- Profile paths and bookmark contents are excluded by default.
- Imported settings are validated before application.
- The schema is versioned and documented.

### FUT-009: Synchronization history dashboard

Provide a local count-only history view using privacy-safe logs and manifests.

Acceptance criteria:

- The dashboard shows run time, mapping name, strategy, counts, result, and backup manifest.
- Bookmark titles and URLs are not displayed or stored.
- Missing or pruned backup sets are represented clearly.
- History can be filtered and exported without changing browser data.
