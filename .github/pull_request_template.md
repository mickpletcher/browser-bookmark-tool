## Summary

Describe the change and why it is needed.

## Validation

- [ ] `py -m pytest -q`
- [ ] `py -m ruff check .`
- [ ] `py -m py_compile browser_bookmark_sync.py test_sync.py`
- [ ] `py -m browser_bookmark_sync --help`
- [ ] Standalone build checked when packaging, startup, or CLI behavior changed

## Safety and documentation

- [ ] No bookmark data, local paths, credentials, private configuration, logs, or generated artifacts are included
- [ ] Backup-first and no-deletion synchronization behavior is preserved or explicitly documented
- [ ] README, assessment, changelog, and upgrade tracking were updated where required
