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

Implementation status: The fail-closed Azure Artifact Signing and verification workflow is implemented, and SignPath application-readiness controls are documented. Completion is blocked until a trusted provider is configured and a release executable verifies as `Valid`.

Acceptance criteria:

- The release executable has a valid Authenticode signature.
- Signature verification runs during the release workflow.
- Signing secrets and certificates are not stored in the repository or build artifacts.
- The README documents how users verify the signature.

### FUT-003: Signed release packages and checksums

Create versioned release packages containing the executable, documentation, license, and published SHA-256 checksums.

Implementation status: Versioned package construction and checksum verification are implemented. Completion is blocked until the first trusted signed release is published and independently verified.

Acceptance criteria:

- CI creates deterministic package names tied to the project version.
- A checksum file is generated and verified before artifact upload.
- Package contents exclude browser data, local mappings, logs, and generated task scripts.
- Release instructions document checksum verification in PowerShell.

### FUT-015: Release artifact provenance and SBOM

Publish verifiable provenance and a software bill of materials with each versioned release package.

Implementation status: CycloneDX generation and SHA-pinned GitHub attestation steps are implemented. Completion is blocked until the first trusted signed release publishes and verifies both attestations.

Acceptance criteria:

- The release workflow generates an SPDX or CycloneDX SBOM from the packaged application and its build dependencies.
- GitHub artifact attestations cover the executable, archive, checksum file, and SBOM.
- Verification instructions include copy-ready PowerShell commands.
- Provenance generation uses least-privilege workflow permissions and no long-lived repository credentials.

### FUT-016: SignPath Foundation onboarding and integration

Complete SignPath Foundation review and, if approved, replace the unconfigured Azure signing step with the exact provider-supported GitHub Actions integration.

Implementation status: Application prerequisites are documented. The repository publishes the required code-signing acknowledgment, maintainer roles, manual approval policy, privacy statement, honest download status, and enforced Windows product metadata. Provider approval and configuration are pending.

Acceptance criteria:

- SignPath Foundation approves the project and confirms the repository, artifact configuration, and signing workflow.
- Every signing request requires manual approval in SignPath by the documented approver.
- The integration signs only artifacts built from this public repository and never exposes signing authority to untrusted pull requests.
- All third-party actions are reviewed, pinned to full commit SHAs, and added to the repository allowlist only when required.
- The final workflow verifies the SignPath Foundation publisher, trusted timestamp, Windows product metadata, checksums, SBOM, and provenance before publication.
- The first signed release is independently verified and the download page identifies the signing provider and links to the code-signing policy.

## Priority 2: Planned

These upgrades improve reporting, multi-profile administration, and browser coverage.

### FUT-005: Multi-profile batch dashboard

Add a GUI view for selecting, previewing, and running multiple named profile mappings with independent results.

Acceptance criteria:

- Each mapping shows its profiles, status, and preview counts.
- A failure in one mapping does not hide results for other mappings.
- Synchronization still enforces browser-process safety per run.
- Private mapping paths remain excluded from Git.

### FUT-018: Firefox recovery verification and restore

Add isolated verification and explicit restore for the raw Firefox SQLite recovery snapshots created by completed `FUT-006`.

Acceptance criteria:

- Verification runs against a temporary database copy, validates SQLite integrity and required Places roots, and never opens a live Firefox profile.
- Restore requires `firefox.exe` to be closed, validates the selected snapshot and its manifest, and preserves the current `places.sqlite` before replacement.
- WAL and shared-memory sidecars are handled without replaying stale data into the restored database.
- GUI, CLI, and failure-path tests cover valid, corrupt, mismatched, and unsupported-schema snapshots.

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

### FUT-019: Duplicate backup-set detection

Identify exact duplicate recovery content across complete, valid backup sets and report potential redundant storage without deleting files.

Acceptance criteria:

- Duplicate detection uses verified manifest hashes instead of bookmark names, URLs, or timestamps.
- The report shows duplicate set counts, affected browser types, and potential recoverable bytes without exposing private content.
- No automatic or interactive deletion option is added.
- Incomplete, invalid, and unrecognized files are excluded from duplicate conclusions and reported separately.
- Tests cover identical, partially identical, distinct, incomplete, and invalid sets without changing backup files.

### FUT-021: Reusable preview policy profiles

Add private versioned policy files for repeatable preview-report gates with aggregate and per-mapping limits.

Acceptance criteria:

- A versioned JSON policy schema defines aggregate defaults and optional per-mapping limits for planned additions, duplicate removals, and folder changes.
- Policies identify the expected baseline report by SHA-256 without embedding bookmark details or local profile paths.
- Missing mappings, unexpected mappings, unsupported policy versions, and baseline hash mismatches fail closed with documented exit codes.
- A sanitized example is tracked while real policy files and reports remain ignored and local.
- Tests cover aggregate and per-mapping overrides, baseline validation, privacy-safe output, malformed policies, and no-write behavior.
