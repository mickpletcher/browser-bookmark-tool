# Changelog

All notable project changes are recorded in this file.

This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Added guided, user-controlled Safari HTML import preparation in the GUI and CLI without editing Safari or automating the final import.
- Recorded successful physical-Mac validation of 285 bookmarks and 61 folders, manifest integrity, and an unchanged live Safari plist hash.

- Added the read-only phase of `FUT-011`: macOS Safari bookmark discovery, validated plist backups in SHA-256 manifests, bookmark-only parsing with Reading List exclusion, merge planning, duplicate handling, organization, portable HTML export, and GUI/CLI controls.
- Added fail-closed Safari schema handling, iCloud synchronization warnings, privacy-safe count-only output, Safari backup catalog/verification support, and regression coverage without any Safari write path.

- Added isolated, count-only verification of Firefox SQLite recovery snapshots with manifest hashes, SQLite integrity, supported Places schema, and required-root validation.
- Added GUI and CLI Firefox restore with platform-native process blocking, consistent preservation of the current database, staged replacement, stale WAL and shared-memory cleanup, and rollback-safe failure handling.
- Added corrupt, mismatched, unsupported-schema, running-process, replacement-failure, sidecar, GUI, CLI, physical-macOS copied-profile, and physical Windows 11 coverage for completed `FUT-018`.
- Added `FUT-025` cross-platform recovery rehearsal as the replacement candidate for completed `FUT-018`.

- Added native macOS Chrome, Edge, and Firefox profile discovery, platform-specific process safeguards, exact-name explicit closure, and platform-aware restore guards.
- Added a portable `python3` shell launcher, backup-first `launchd` property-list generation, macOS package metadata, and a SHA-pinned macOS CI test and PyInstaller smoke-build job.
- Added macOS regression and physical-Mac validation coverage while preserving the complete Windows suite.
- Added `FUT-024` signed and notarized macOS distribution as the replacement candidate for completed `FUT-013`.

- Added optional atomic version 1 `preview-policy-result` JSON output with input and policy hashes, expected mappings, aggregate and per-mapping counts, configured limits, violations, status, and exit code.
- Added protected result destinations, default Git ignore coverage, detailed-report redaction, and regression coverage for pass, policy failure, schema stability, atomic replacement, and no browser or backup access.
- Added `FUT-023` preview result catalog and trend summaries as the replacement candidate for completed `FUT-022`.
- Added private version 1 preview policies with baseline SHA-256 binding, exact expected-mapping validation, aggregate count limits, and optional per-mapping overrides.
- Added fail-closed policy handling for malformed schemas, baseline mismatches, missing or unexpected mappings, and conflicts with direct threshold options.
- Added a sanitized path-free `preview-policy.example.json`, private policy ignore rules, privacy-safe output, and no-write regression coverage.
- Added read-only comparison of version 1 JSON and CSV preview reports with mapping-name matching and count-only settings, browser-count, planned-addition, duplicate, and folder-change differences.
- Added optional aggregate policy gates for planned additions, duplicate removals, and folder changes with exit code `2` for exceeded thresholds.
- Added default rejection of detailed preview reports, explicit private-data acknowledgment, count-only comparison output, cross-format schema validation, and no-write regression coverage.
- Added `FUT-021` reusable preview policy profiles as the replacement candidate for completed `FUT-020`.
- Added versioned JSON and row-oriented CSV output for direct and multi-mapping dry runs through `--preview-report`.
- Added explicit `--include-bookmark-details` opt-in for merged bookmark names, URLs, and folder paths while keeping default reports limited to settings, counts, and change categories.
- Added regression coverage for JSON and CSV schemas, default privacy, explicit details, multi-mapping aggregation, unsafe destinations, unsupported extensions, option dependencies, browser-file preservation, and backup-pruning isolation.
- Added `FUT-020` preview report comparison and policy gates as the replacement candidate for completed `FUT-004`.
- Added a read-only GUI and CLI backup catalog with generated-timestamp grouping, complete, incomplete, valid, and invalid filters, manifest status, browser-specific bookmark and folder counts, and deltas from the previous complete and valid set.
- Added explicit count-only comparison for two complete, valid backup sets through `--compare-backups`.
- Added regression coverage for complete sets, missing and extra members, manifest mismatches, unrelated files and directories, CLI and GUI reporting, and exact no-change backup-directory verification.
- Added `FUT-019` duplicate backup-set detection as the replacement candidate for completed `FUT-017`.
- Added disabled-by-default Firefox import through explicit `profiles.ini`, CLI, GUI, profile-mapping, and automation configuration paths.
- Added opt-in Firefox export that creates and manifests a consistent SQLite backup before any write, stages and validates the replacement, blocks on `firefox.exe`, and restores Chrome and Edge if the Firefox replacement fails.
- Added cross-browser conservative and aggressive duplicate matching plus Firefox discovery, Places schema, backup ordering, manifest, process, disabled-mode, export, and three-browser rollback tests.
- Added `FUT-018` Firefox recovery verification and restore as the replacement candidate for completed `FUT-006`.
- Updated support, security, issue-reporting, package, and repository About metadata for optional Firefox support.
- Added a 1280 by 640 repository social preview covering Chrome, Edge, optional Firefox, backup, export, synchronization, and transactional safety.
- Added non-destructive JSON recovery verification through the GUI and CLI using an isolated temporary Chromium profile, schema validation, GUID validation, matching manifest checks, and count-only reports.
- Added regression coverage for valid snapshots, corrupt JSON, invalid Chromium structure, duplicate GUIDs, manifest mismatches, live-file preservation, and GUI and CLI verification results.
- Added `FUT-017` backup-set catalog and comparison as the replacement candidate for completed `FUT-002`.
- Added a fail-closed versioned Windows release workflow that requires Azure Artifact Signing through OIDC, timestamp and publisher verification, SHA-256 checksums, a CycloneDX SBOM, and GitHub provenance before publishing a Release.
- Added an explicit unsigned local validation mode whose executable and archive names include `-unsigned` and which never publishes artifacts.
- Added isolated release dependencies and SBOM path-leak checks so global packages and local editable-install paths cannot enter a published SBOM.
- Added copy-ready Authenticode, checksum, and GitHub attestation verification instructions.
- Added `future-upgrades.md` with three priority tiers, acceptance criteria, and fourteen proposed upgrades.
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
- Added contribution, support, conduct, ownership, issue, and pull request guidance for public repository participation.
- Added weekly grouped Dependabot version updates for Python and GitHub Actions.
- Added package README, keywords, classifiers, and project links to `pyproject.toml`.
- Added `FUT-015` release artifact provenance and SBOM work to replace the completed deterministic lint upgrade.
- Added a SignPath-compatible code-signing policy with public source, explicit solo-maintainer roles, manual approval requirements, account-security controls, and a signing-incident response path.
- Added a privacy policy covering local bookmark processing, generated files, optional user-configured notification delivery, retention, and deletion.
- Added uninstall instructions for editable installs, portable executables, optional scheduled tasks, and separately retained user data.
- Added `FUT-016` to track SignPath Foundation onboarding and verified signing-provider integration separately from application readiness.

### Security

- Rejected preview report destinations inside selected browser profiles and excluded standard private JSON and CSV preview report names from Git.
- Used SQLite immutable mode for Firefox catalog inspection so read-only inventory cannot create WAL or shared-memory sidecars beside recovery snapshots.
- Enforced Windows ProductName, ProductVersion, FileDescription, and OriginalFilename metadata in release builds and included the code-signing and privacy policies in release archives.
- Documented that SignPath approval is pending, unsigned artifacts are not public releases, and provider-specific integration must not be added before configuration is reviewed.
- Restricted release publication to the `release` environment and `v*` tags, kept private signing keys out of GitHub, and used short-lived OIDC authentication for managed hardware-backed signing.
- Kept full-SHA Actions enforcement and expanded the allowlist only for the exact reviewed Azure Login 3.0.1 and Azure Artifact Signing 2.0.0 commits.
- Replaced classic `main` protection with a solo-maintainer ruleset that permits administrator emergency bypass, blocks deletion and non-fast-forward pushes, requires current pull requests with resolved conversations and all five Windows CI checks, and allows squash merge only.
- Rejected manifest entries containing traversal paths, invalid sizes, or malformed SHA-256 values.
- Rejected profile mapping files whose root document does not contain a mapping list.
- Disabled persisted checkout credentials and added a 20-minute timeout to the SHA-pinned Windows CI job.
- Restricted Actions to GitHub-owned actions while retaining required full commit SHA pinning and read-only workflow permissions.
- Strengthened `main` protection with linear-history and review-conversation-resolution requirements while retaining administrator enforcement and force-push and deletion blocks.
- Prevented scheduled runs from using the process-detection `--force` bypass.
- Excluded private automation configurations, results, and lock files from Git.
- Excluded private scheduler health histories from Git and kept notification commands and credentials out of health and notification payloads.
- Restricted scheduled structured output to counts, mapping names, operation status, process names, and privacy-safe errors without bookmark URLs or local paths.
- Updated the Windows workflow to current verified official action SHAs while retaining repository-enforced SHA pinning and read-only permissions.
- Added privacy warnings and private vulnerability routing to the public issue workflow.

### Changed

- Documented the local-only backup catalog data boundary in the README and privacy policy.
- Corrected the README's stale branch-protection summary to match the active solo-maintainer ruleset and required Windows CI checks.
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
- Replaced duplicate branch and pull request CI runs with `main` push and pull request triggers, cancellation of superseded runs, a Python 3.10 through 3.13 test matrix, dependency checks, and a gated Windows build artifact.
- Updated stale release-readiness documentation after two successful Windows CI runs and moved `FUT-010` to completed upgrades.
- Added workflow and license badges plus contribution and support links to the README.

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
