# Accessibility

Browser Bookmark Tool provides a Python/Tkinter desktop interface and a command-line interface on Windows and macOS. We welcome reports of barriers in the application, documentation, and contribution process.

## Current status

Accessibility has not been independently audited. The project does not claim WCAG conformance or verified compatibility with any screen reader. Functional tests and successful CI builds do not establish accessibility conformance. Tkinter behavior can vary with the operating system, Python/Tcl/Tk version, theme, and assistive technology.

The CLI is an alternative for supported operations, not a guarantee of accessibility or complete interface parity. Use `python -m browser_bookmark_sync --help` to review commands. Both interfaces currently require a Tcl/Tk-enabled Python installation; see [README.md](README.md).

## Report a barrier

Use the [accessibility issue form](https://github.com/mickpletcher/browser-bookmark-tool/issues/new?template=accessibility.yml). Include the task, reproduction steps, expected and actual behavior, application/OS versions, and Python/Tcl/Tk version if known. Assistive technology and version are optional.

Issues are public. Do not include medical information. Remove bookmark names and URLs, profile data, usernames, local paths, credentials, and private content from screenshots and logs. For vulnerabilities, use the private route in [SECURITY.md](SECURITY.md). Support is best effort, with no guaranteed response time.

## Contributor review checklist

For changes to the GUI, CLI, documentation, or error handling:

- Check keyboard-only navigation, focus order and visibility, activation, cancellation, and focus after dialogs.
- Use descriptive control labels and error messages. Do not convey essential information through color alone.
- Check operating-system scaling and large text for clipped controls or instructions.
- Where practical, test affected flows with Windows Narrator or NVDA and macOS VoiceOver. Record actual platforms, versions, scope, results, and untested combinations.
- Keep CLI help and errors understandable as plain text; document alternatives when GUI tasks cannot be completed accessibly.
- Use descriptive links, meaningful headings, and useful image alternative text.
- Use synthetic bookmark data only. Preserve confirmations, backup-first behavior, and Safari's read-only boundary.

Record checks and limitations in the pull request. A checklist documents checks performed, not certification.
