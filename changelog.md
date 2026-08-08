# Changelog

All notable project changes are recorded in this file.

This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
