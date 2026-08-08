# Security Policy

## Supported versions

Security fixes are applied to the latest code on `main` and the latest published GitHub release when one exists. Older revisions are not supported.

## Report a vulnerability

Use [Report a vulnerability](https://github.com/mickpletcher/browser-bookmark-tool/security/advisories/new) on the repository's **Security** tab. This creates a private report for the maintainer. Do not open a public issue for an unpatched vulnerability.

Include the affected version, impact, reproduction steps, and any proposed mitigation. Remove real bookmark URLs, browser profile data, usernames, and backup contents before attaching evidence.

## Protect bookmark data

Chrome and Edge `Bookmarks` files, JSON and HTML backups, restore snapshots, generated task scripts, and profile mapping files can contain private browsing data, internal URLs, access tokens, usernames, or local paths. Keep them outside the repository. The project `.gitignore` blocks standard private filenames as a secondary safeguard.

Backup manifests contain file names, sizes, hashes, and count-only summaries. Default logs contain timestamps, actions, counts, selected strategy, and browser process names. They intentionally exclude bookmark names and URLs. Treat all generated operational files as private unless independently reviewed and sanitized.
