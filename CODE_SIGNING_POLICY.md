# Code Signing Policy

## Status

Browser Bookmark Tool is applying to the SignPath Foundation open-source program. No binary release is currently represented as SignPath-signed. The existing release workflow remains fail-closed until a trusted signing provider is configured and the resulting executable passes signature and timestamp verification.

Free code signing provided by [SignPath.io](https://about.signpath.io/), certificate by [SignPath Foundation](https://signpath.org/).

## Project and source

- Project: [Browser Bookmark Tool](https://github.com/mickpletcher/browser-bookmark-tool)
- License: [MIT](LICENSE)
- Source repository: [mickpletcher/browser-bookmark-tool](https://github.com/mickpletcher/browser-bookmark-tool)
- Release downloads: [GitHub Releases](https://github.com/mickpletcher/browser-bookmark-tool/releases)

Only binaries produced from the public source code and build configuration in this repository may be submitted for project signing. Proprietary code and separately maintained third-party binaries must not be submitted under this project.

## Team roles

- Authors and committers: [Mick Pletcher](https://github.com/mickpletcher)
- Reviewers: [Mick Pletcher](https://github.com/mickpletcher)
- Signing approvers: [Mick Pletcher](https://github.com/mickpletcher)

This is a solo-maintained project. External contributions require maintainer review before merge. Maintainer-authored changes use pull requests, required automated checks, current-branch enforcement, and resolved review conversations. A second independent human reviewer is not currently available.

## Signing requirements

Every release signing request requires manual approval by the signing approver. Approval is granted only after confirming that:

1. The version tag matches `pyproject.toml` and points to a commit on `main`.
2. Required Windows CI and release-package validation checks pass.
3. The executable was built by the repository's reviewed automation from public source.
4. Windows version metadata identifies the product as `Browser Bookmark Tool` and matches the release version.
5. The Authenticode signature, code-signing usage, expected publisher, and trusted timestamp pass verification.
6. SHA-256 checksums, a CycloneDX SBOM, and GitHub build provenance are generated and verified before publication.

Signing is suspended if source provenance, build integrity, account security, or artifact contents cannot be verified. Suspected signing misuse must be reported through the private process in [SECURITY.md](SECURITY.md).

## Account security

Project maintainers and signing approvers must use multi-factor authentication for GitHub and SignPath. Signing credentials and private keys must not be committed to the repository, stored in release artifacts, or exposed to untrusted pull-request workflows.

## Privacy

See [PRIVACY.md](PRIVACY.md) for the complete project privacy policy.

This program will not transfer any information to other networked systems unless specifically requested by the user or the person installing or operating it.
