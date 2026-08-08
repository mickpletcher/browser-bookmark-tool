# Changelog

All notable project changes are recorded in this file.

This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Added `future-upgrades.md` with three priority tiers, acceptance criteria, and thirteen proposed upgrades.
- Added `completed-upgrades.md` with promotion rules and the version 0.2.0 capability baseline.
- Added deterministic Ruff configuration and version control to the Priority 1 upgrade backlog after live Windows CI exposed dependency drift.
- Added phased Safari backup and synchronization on macOS to the Priority 2 backlog with bookmark-only scope, iCloud warnings, and transactional write requirements.
- Added native macOS Chrome and Edge compatibility to the Priority 2 backlog as the platform foundation that must precede Safari support.
- Added a private versioned automation configuration and sanitized example for local AI and deterministic schedulers.
- Added `--check-automation` for no-write configuration, mapping, bookmark, destination, lock, and process readiness checks.
- Added `--run-automation` with atomic concurrency locking and privacy-safe structured JSON results.
- Added `Invoke-BrowserBookmarkAutomation.ps1` as the common local Codex, Claude, Copilot, and Task Scheduler entrypoint.
- Added `SCHEDULING.md` with setup instructions, execution boundaries, result schema, failure handling, and copy-ready model prompts.
- Documented the supported local scheduling paths for Codex desktop tasks, Claude Desktop local tasks, Claude Code session loops, and GitHub Copilot CLI, including each cloud or session boundary.
- Added active-run, stale-lock, backup, dry-run, blocked synchronization, browser-closing sync, privacy, CLI, and PowerShell wrapper regression coverage.
- Added capped scheduled-run health history containing only operation status, mapping names, numeric counts, duration, browser process names, and allowlisted error categories.
- Added optional local failure notification commands with sanitized JSON standard input, disabled-by-default configuration, consecutive-failure suppression, and recovery reset.
- Added successful-run, blocked synchronization, stale-lock recovery, repeated-failure, recovery, and notification-redaction regression coverage.
- Added `FUT-014` notification delivery verification and provider templates to the Priority 2 backlog as the replacement candidate for completed `FUT-012`.

### Security

- Rejected manifest entries containing traversal paths, invalid sizes, or malformed SHA-256 values.
- Rejected profile mapping files whose root document does not contain a mapping list.
- Disabled persisted checkout credentials and added a 20-minute timeout to the SHA-pinned Windows CI job.
- Restricted Actions to GitHub-owned actions while retaining required full commit SHA pinning and read-only workflow permissions.
- Strengthened `main` protection with linear-history and review-conversation-resolution requirements while retaining administrator enforcement and force-push and deletion blocks.
- Prevented scheduled runs from using the process-detection `--force` bypass.
- Excluded private automation configurations, results, and lock files from Git.
- Excluded private scheduler health histories from Git and kept notification commands and credentials out of health and notification payloads.
- Restricted scheduled structured output to counts, mapping names, operation status, process names, and privacy-safe errors without bookmark URLs or local paths.

### Changed

- Added manifest retention and path-validation regression coverage.
- Documented that standalone executable artifacts are not Authenticode-signed.
- Required completed upgrades to leave the future backlog, enter the completed ledger with verification evidence, and be replaced by at least one new candidate.
- Linked both upgrade tracking files from the README and synchronized the assessment maintenance rules.
- Updated the GitHub About description and topics for the current Windows GUI and CLI feature set.
- Disabled unused GitHub Projects and Wiki features while retaining Issues and the existing disabled Discussions and Pages state.
- Standardized pull requests on squash merge, enabled branch update suggestions, and enabled automatic deletion of merged branches.
- Recorded the live Windows CI Ruff 0.16.2 lint failure as a release-readiness finding; tests pass before the failing lint step.
- Defined explicit Ruff rules and a supported `ruff>=0.16.2,<0.17` range so local and Windows CI lint behavior does not drift silently.
- Updated the maintained test suite to 80 passing cases.

## [0.2.0] - 2026-08-07

### Added

- Added `assessment.md` with the current release-readiness assessment, prioritized findings, and verification results.
- Added a project maintenance rule requiring `assessment.md` and `changelog.md` to be reviewed and updated with every change.
- Added optional duplicate removal across the merged Chrome bookmark and Edge favorites collection.
- Added optional recursive alphabetization with folders first and bookmarks second.
- Added GUI checkboxes and the `--deduplicate` and `--alphabetize` CLI flags.
- Added unit and synchronization tests for organization behavior and disabled defaults.
- Added Windows process detection for `chrome.exe` and `msedge.exe`.
- Added synchronization blocking that preserves raw backups and HTML exports while browsers are running.
- Added the advanced CLI-only `--force` override.
- Added tests for Chrome-only, Edge-only, combined process blocking, export-only behavior, forced synchronization, process parsing, and CLI error exit handling.
- Added the explicit `--close-browsers` CLI option to force-terminate Chrome and Edge process trees, verify closure, and then synchronize.
- Added tests for automatic browser closure, failed closure, forceful `taskkill` commands, retention limits, and rapid HTML backup creation.
- Added unique UUID generation for every imported bookmark, imported folder, and generated import wrapper.
- Added merged-data validation that rejects duplicate GUID values.
- Added tests for nested imported GUID regeneration, duplicate GUID rejection, and repeated synchronization stability.
- Added a private vulnerability reporting policy and repository ignore rules for Chromium bookmark data and generated backups.
- Enabled Dependabot alerts and security updates, private vulnerability reporting, Python CodeQL default setup, SHA-pinned Actions enforcement, and `main` force-push and deletion protection. Confirmed that secret scanning push protection remains enabled.
- Added conservative and aggressive duplicate-matching modes with conservative behavior as the default.
- Added `chrome-wins`, `edge-wins`, `preserve-both`, `merge-folders`, and `dated-folder` strategies.
- Added GUI and CLI dry-run reports that do not create files or write browser data.
- Added independent Chrome and Edge restore from JSON recovery snapshots.
- Added private named profile mappings with multi-mapping CLI execution and a sanitized example.
- Added validated SHA-256 manifests and privacy-safe count-only logs.
- Added PowerShell Task Scheduler script generation with backup-only defaults and explicit synchronization opt-in.
- Added PyInstaller standalone Windows build support and a SHA-pinned Windows CI build artifact.

### Changed

- Replaced the brief README with a detailed operating guide covering current status, synchronization behavior, safety requirements, GUI and CLI use, profile locations, backup restoration, known limitations, and development checks.
- Added prominent README links to `assessment.md` and `changelog.md`.
- Expanded the maintenance rule to require `README.md`, `assessment.md`, and `changelog.md` updates with every project change.
- Corrected the setuptools configuration so the root-level `browser_bookmark_sync` module installs successfully in editable mode.
- Updated the merge test to count parsed bookmark URL nodes instead of matching URL text in serialized JSON.
- Updated the Windows batch launcher to run the Python module without requiring Python's `Scripts` directory on `PATH` and to forward command-line arguments.
- Updated the operating guide and assessment with the repaired installation, launcher, and test status.
- Changed synchronization to prepare and validate both browser replacement files before changing either original.
- Added automatic Chrome restoration when the Edge replacement fails.
- Added cleanup for prepared and rollback files after successful writes and handled failures.
- Added tests simulating first-write failure and second-write failure with automatic rollback.
- Updated the operating guide and assessment with the transactional write behavior.
- Updated GUI result messages and CLI output with duplicate-removal and alphabetization results.
- Increased the minimum GUI height to accommodate the organization options.
- Updated the operating guide and assessment with optional organization instructions.
- Changed CLI runtime failures to print a concise error and return exit code `1` without a traceback.
- Updated the GUI and CLI error path to identify detected browser executable names.
- Updated the operating guide and assessment with process-safety instructions.
- Increased default backup retention from 30 to 50 and enforced a maximum of 50 backup sets.
- Added microseconds to backup filenames to prevent same-second overwrites.
- Clarified that the merged HTML file is the portable backup and the raw JSON files are recovery snapshots.
- Updated the GUI retention label and range for 1 through 50 backup sets.
- Updated CLI output to report browsers closed by the synchronization run.
- Updated the operating guide and assessment with automatic closure and HTML backup retention.
- Removed the redundant second merge operation from synchronization.
- Replaced the deprecated license table with the SPDX `MIT` string and raised the setuptools build requirement to version 77.
- Updated the operating guide and assessment with resolved GUID handling and 27-test verification status.
- Changed backup pruning to order recognized tool-generated files by their filename timestamps instead of inherited modification times.
- Limited backup pruning to regular JSON and HTML files that match the tool's generated naming format.
- Added regression coverage for raw-backup timestamp ordering and unrelated-file protection, bringing the suite to 29 tests.
- Updated the operating guide and assessment with privacy guidance, repository security settings, and corrected retention behavior.
- Changed default URL comparison to preserve path, query, fragment, and trailing-slash distinctions.
- Extended GUI controls with duplicate mode, merge strategy, preview, restore, and mapping management.
- Extended CLI operation handling for preview, mappings, restore, logging, scheduling, and verbose reports.
- Added manifest retention, private-data ignore rules, and sanitized template handling.
- Bumped the project version to 0.2.0 and expanded the maintained test suite to 55 passing cases.
- Updated generated tasks to use the packaged executable when running from the standalone build.
- Changed the local build script to use a unique system temporary workspace and explicit native exit-code checks, avoiding OneDrive build-directory locks.

## [0.1.0] - 2026-08-07

### Added

- Added Chrome and Microsoft Edge bookmark profile discovery.
- Added raw JSON backups with configurable retention.
- Added portable Netscape bookmark HTML exports.
- Added conservative URL-based bookmark synchronization without deletion propagation.
- Added a Tkinter desktop interface and command-line interface.
- Added atomic writes for individual bookmark files.
- Added initial merge, export, and synchronization tests.

## Maintenance requirement

Update the `[Unreleased]` section with every project change. Include code, tests, documentation, configuration, packaging, and workflow changes. Move entries into a versioned section when a release is created. Review and update `README.md` and `assessment.md` during the same change.
