# Contributing

Browser Bookmark Tool is a Windows and macOS Python application. It supports Chrome and Edge synchronization, optional Firefox import/export, and read-only Safari workflows on macOS. Contributions should preserve its backup-first, add-only synchronization behavior and Safari's no-write boundary unless a change explicitly redesigns those contracts.

## Before opening an issue

- Use the bug or feature request form.
- Remove bookmark URLs, titles, browser profile data, usernames, local paths, tokens, and backup contents from all examples.
- Report vulnerabilities through the private process in [SECURITY.md](SECURITY.md), not through a public issue.
- Use [SUPPORT.md](SUPPORT.md) for usage questions and troubleshooting scope.

## Development setup

```powershell
py -m pip install -e ".[dev]"
py -m pytest -q
py -m ruff check .
py -m py_compile browser_bookmark_sync.py safari_adapter.py test_sync.py
py -m browser_bookmark_sync --help
```

On macOS, use `python3` in place of `py` and run `./run-browser-bookmark-tool.sh --help` as an additional launcher check.

Run the standalone build when a change affects packaging, startup, or command-line behavior:

```powershell
.\build.ps1
.\dist\BrowserBookmarkTool.exe --help
```

## Dependency updates

Dependabot groups Python and GitHub Actions updates into weekly pull requests. Review Ruff release notes and the resulting lint output before changing the allowed Ruff range or enabled rules. Keep every action pinned to a full commit SHA and update its version comment with the pin.

## Branches and tags

Use short branch names with one of these prefixes:

- `feature/` for new behavior
- `fix/` for defect corrections
- `docs/` for documentation-only changes
- `chore/` for maintenance and dependency work

Release tags use `vMAJOR.MINOR.PATCH`, such as `v0.3.0`.

## Pull requests

- Keep each pull request focused on one change.
- Add or update tests for behavior changes.
- Update `README.md`, `assessment.md`, and `changelog.md` when behavior, configuration, packaging, or project status changes.
- Update `future-upgrades.md` and `completed-upgrades.md` when a tracked upgrade is completed.
- Confirm the cross-platform CI workflow passes, including the Windows Python matrix and native macOS test/build job.
- Do not commit generated executables, build output, browser data, mappings, logs, results, health history, or scheduler files.

Pull requests are squash merged. Write the title so it can serve as the final commit message.

## Code signing roles

The project roles, approval requirements, and release controls are defined in [CODE_SIGNING_POLICY.md](CODE_SIGNING_POLICY.md).

- Mick Pletcher is the project author, committer, reviewer, and signing approver.
- External contributions require maintainer review before merge.
- Every release signing request requires a separate manual approval after the source, tag, checks, build metadata, and artifact provenance are verified.
- Pull requests from forks and other untrusted contexts must never receive signing credentials or permission to approve signing requests.

This is a solo-maintained project. There is no independent second human reviewer for maintainer-authored changes. Required Windows CI, release-package validation, current-branch enforcement, and resolved review conversations remain mandatory controls.
