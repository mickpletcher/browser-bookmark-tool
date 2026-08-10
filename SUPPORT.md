# Support

## Usage help

Read [README.md](README.md) and [SCHEDULING.md](SCHEDULING.md) first. If the problem remains, open a GitHub issue using the bug report form.

Include:

- Operating system and version (Windows or macOS)
- Python version or standalone executable version
- Chrome, Edge, Firefox, and Safari versions when applicable
- The command or GUI action used
- Expected and actual behavior
- Sanitized error text

Do not attach browser `Bookmarks` files, backup files, profile mappings, scheduler configurations, logs containing private paths, or screenshots containing bookmark names or URLs.

## Scope

The current release supports Chrome and Microsoft Edge on Windows and macOS, plus disabled-by-default Firefox import and opt-in export on both platforms. Firefox recovery verification and restore are also supported on Windows and macOS.

On macOS, Safari support is deliberately read-only: the tool can discover, validate, back up, preview, organize, merge, and export bookmarks from Safari's version 1 bookmark plist. It excludes Reading List entries and can prepare a validated HTML file for a user-controlled Safari import. It never edits Safari's live data or automates the final import. Direct Safari writes and signed/notarized macOS distribution remain planned work in [future-upgrades.md](future-upgrades.md).

Source installations are supported on Windows 11 and current supported macOS releases. CI tests both platforms and creates native smoke builds. Public binaries are not available until the applicable platform signing requirements are complete.

Support is best effort. There is no guaranteed response time.

## Security reports

Do not open a public issue for a vulnerability. Follow [SECURITY.md](SECURITY.md).
