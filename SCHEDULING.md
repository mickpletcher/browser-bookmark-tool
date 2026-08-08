# Scheduled AI Execution

Browser Bookmark Tool can be invoked by Codex, Claude, Copilot, Windows Task Scheduler, or another local scheduler through one deterministic PowerShell entrypoint. The AI model is the scheduler and monitor. The bookmark tool performs the actual backup or synchronization.

## Required execution boundary

Chrome and Edge bookmark files exist on the Windows computer that owns the browser profiles. A cloud-hosted coding agent or GitHub-hosted runner cannot access those files.

Use one of these execution environments:

- A local Codex automation running on the browser computer.
- A local GitHub Copilot CLI session or externally scheduled Copilot CLI process running on the browser computer.
- A local Claude Desktop scheduled task or Claude Code session running on the browser computer.
- A dedicated self-hosted Windows runner operating under the same Windows account as the browser profiles.

Do not copy real bookmark files, profile mappings, automation configuration, logs, or result files into Git, an AI prompt, an issue, a pull request, or a cloud artifact.

## Files

- `Invoke-BrowserBookmarkAutomation.ps1` is the common local entrypoint.
- `automation-config.example.json` is the sanitized scheduler configuration template.
- `profile-mappings.example.json` is the sanitized browser profile mapping template.
- The private automation configuration, profile mapping, lock, result, backups, and logs must remain outside the repository.

The repository ignores common private automation file names, but Git exclusion is only a secondary safeguard.

## Set up the private files

1. Copy `profile-mappings.example.json` to a private directory outside the repository.
2. Replace its placeholder Chrome, Edge, and backup paths with the correct local paths.
3. Copy `automation-config.example.json` to the same private directory.
4. Set `profile_map` to the private profile mapping file.
5. Select the mapping names to run. An empty `mappings` list runs every mapping in the profile map.
6. Keep `operation` set to `backup` for the first scheduled runs.
7. Keep `browser_behavior` set to `block` unless forced browser closure has been explicitly approved and tested.
8. Restrict the private directory so only the intended Windows account can read it.

Relative paths in the automation configuration are resolved from the directory containing that configuration. Chrome, Edge, and backup paths inside the private profile mapping must be absolute so scheduler working-directory changes cannot redirect browser access.

## Configuration fields

| Field | Required | Behavior |
| --- | --- | --- |
| `schema_version` | Yes | Must be `1`. |
| `operation` | Yes | `backup`, `sync`, or `dry-run`. |
| `profile_map` | Yes | Path to the private named profile mapping file. |
| `mappings` | No | Unique mapping names. Empty means all mappings. |
| `keep` | No | Backup sets to retain from 1 through 50. Default is 50. |
| `deduplicate` | No | Removes duplicate normalized URLs when `true`. Default is `false`. |
| `alphabetize` | No | Recursively sorts folders and bookmarks when `true`. Default is `false`. |
| `duplicate_mode` | No | `conservative` or explicit `aggressive`. |
| `merge_strategy` | No | One of the five documented merge strategies. |
| `browser_behavior` | No | `block` or `close`. `close` is valid only for `sync`. |
| `result_file` | No | Privacy-safe JSON result path. Defaults beside the configuration. |
| `lock_file` | No | Atomic concurrency lock path. Defaults beside the configuration. |
| `lock_timeout_minutes` | No | Stale-lock timeout from 5 through 1440 minutes. Default is 180. |

There is no automation setting equivalent to `--force`. Scheduled runs cannot bypass browser-process detection.

## Validate before scheduling

Run a no-write readiness check:

```powershell
.\Invoke-BrowserBookmarkAutomation.ps1 `
  -ConfigPath "D:\Private\browser-bookmark-automation.json" `
  -Mode Check
```

The check validates the private configuration, mappings, bookmark JSON, merge behavior, output destinations, active lock, and browser-process detection. It does not create backups or change browser files.

A running browser produces a warning for `sync`. It does not make the configuration invalid. A subsequent run will still create JSON and HTML backups before blocking synchronization. If `browser_behavior` is `close`, the warning states that the run will force-close the detected browser processes.

## Run manually before scheduling

```powershell
.\Invoke-BrowserBookmarkAutomation.ps1 `
  -ConfigPath "D:\Private\browser-bookmark-automation.json" `
  -Mode Run
```

The wrapper uses a current standalone executable when available. Otherwise it runs the checked-out Python source through the Windows `py` launcher. Use `-ExecutablePath` to require a specific reviewed executable.

Exit code `0` means the configured operation completed. Any nonzero code means the scheduler must report the failure and stop. It must not retry with `--force`.

## Structured result

Each run atomically replaces the private `result_file` with count-only JSON containing:

- operation and status;
- start time, completion time, duration, and exit code;
- mapping names and bookmark counts;
- duplicate and folder counts;
- whether backups, HTML, and a validated manifest were created;
- whether synchronization completed;
- browser process names closed by an approved `close` run;
- a privacy-safe failure message.

The result excludes bookmark titles, URLs, browser profile paths, backup paths, and configuration paths. Detailed private paths remain only in local application output files.

## Concurrency

Only one automation run may use a configuration lock at a time. A concurrent run exits nonzero without replacing the active run's result. A lock older than `lock_timeout_minutes` is treated as stale and replaced when a new run starts.

Use a separate lock file for schedules that must run independently. Schedules that touch any of the same browser profiles should share one lock file.

## Codex scheduled prompt

Create the task from Codex in the ChatGPT desktop app and select this local project. Keep the Windows computer powered on, keep the desktop app running, and confirm the project is available when the task runs. Do not use a web-only scheduled task because it cannot access a folder on this computer.

The private configuration and browser profiles are outside the repository. Use the narrowest Codex permission configuration that allows the reviewed PowerShell entrypoint to read those files and write the configured backup, result, and lock paths. Test the permission rule manually before enabling recurrence. Avoid broad unattended access when a command-specific rule is sufficient.

Use a prompt based on:

```text
Run the Browser Bookmark Tool automation against the local browser profiles.
First run Invoke-BrowserBookmarkAutomation.ps1 with Mode Check and the private configuration path.
If the readiness status is not-ready, report the privacy-safe errors and stop.
If it is ready, run the same script with Mode Run.
Do not edit repository files. Do not use --force. Do not read or print bookmark files, URLs, private profile paths, configuration contents, logs, or backup contents.
Report only the structured JSON status, counts, browser process names, and exit code.
Never commit, push, open a pull request, upload artifacts, or change the schedule.
```

The Codex automation must run locally on the Windows computer containing the browser profiles. Review its first few runs in **Scheduled** before relying on unattended synchronization.

## Claude scheduled prompt

Create a **Local** scheduled task in Claude Desktop and use the same prompt. Local desktop tasks can access local files and tools, but the computer must remain on. A remote Claude Routine runs in Anthropic's cloud against a fresh repository clone and cannot access local Chrome or Edge profiles.

Claude Code `/loop` scheduling is suitable only while its current session remains running. Recurring `/loop` tasks expire after seven days. Use a Claude Desktop local scheduled task for durable local execution.

The official Claude GitHub Action is currently outside this repository's GitHub-owned-actions-only policy. Do not broaden that policy or add an Anthropic credential merely to run local bookmark synchronization. If a self-hosted runner is approved later, allow only the reviewed action at a pinned commit SHA and use short-lived authentication.

## Copilot scheduled prompt

Use the same prompt with GitHub Copilot CLI on the browser computer and require the PowerShell entrypoint. Copilot CLI `/every` scheduling is experimental and runs only while its interactive session remains open. For unattended execution with no active session, use Windows Task Scheduler to start the reviewed Copilot CLI command, or schedule the deterministic PowerShell entrypoint directly.

GitHub Copilot cloud automations are not available for this public repository, and a GitHub-hosted runner cannot access local browser profiles. Do not change repository visibility merely to schedule bookmark synchronization.

## Recommended operating sequence

1. Schedule daily backup-only runs with `browser_behavior` set to `block`.
2. Review several result files, manifests, HTML exports, and retention outcomes.
3. Run `dry-run` with the intended merge and organization settings.
4. Test an attended `sync` while both browsers are closed.
5. Enable scheduled `sync` only after the attended test passes.
6. Use `close` only if force-closing browsers and losing unsaved browser work is acceptable.
7. Keep human review for configuration, schedule, repository policy, and executable changes.

## Vendor references

- [Codex scheduled tasks](https://learn.chatgpt.com/docs/automations)
- [Claude Code scheduling options](https://code.claude.com/docs/en/scheduled-tasks)
- [GitHub Copilot cloud automations](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/cloud-agent/create-automations)
- [GitHub Copilot CLI scheduled prompts](https://docs.github.com/en/copilot/how-tos/copilot-cli/automate-copilot-cli/schedule-prompts)
