# Privacy Policy

Last updated: 2026-08-08

Browser Bookmark Tool is a local Windows application. It does not include telemetry, analytics, advertising, automatic update checks, cloud synchronization, or a built-in service that uploads bookmark data.

## Local data access

The application reads the Chrome and Microsoft Edge bookmark files selected by the user. Depending on the requested operation, it can create local JSON recovery copies, a portable HTML export, SHA-256 manifests, count-only logs, private automation results, and capped health history. Synchronization and restore operations modify only the browser profile files explicitly selected by the user.

Bookmark titles, URLs, browser profile paths, backup paths, configuration files, and recovery files remain on the user's device unless the user independently copies or transmits them. The default logs and automation results exclude bookmark titles and URLs.

## Network transfers

This program will not transfer any information to other networked systems unless specifically requested by the user or the person installing or operating it.

The optional failure-notification feature runs only when the user configures a local notification command. That command receives a sanitized record containing allowlisted status fields. The user controls the command, its destination, and any third-party privacy terms that apply. The application does not supply a notification provider or credentials.

Links in the documentation can open external websites when selected by the user. GitHub Actions, SignPath, and other release infrastructure process project source and build artifacts for maintainers; they are not contacted by the installed application during normal use.

## Retention and deletion

The user selects the backup location and retention limit. The application can prune its own older generated backup sets according to that limit. Users can delete generated backups, exports, manifests, logs, configuration files, results, and health history through normal Windows file operations.

## Security reports

Do not include real bookmarks, URLs, local paths, tokens, profile data, or backup contents in public reports. Use the private reporting process in [SECURITY.md](SECURITY.md) for suspected vulnerabilities.
