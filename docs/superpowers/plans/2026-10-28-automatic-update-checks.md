# Automatic update checks

Approved behavior: check on every stable-version startup, then every 12 hours
while running, and immediately when the setting is re-enabled. Automatic-updates opt-out prevents network calls and installation.
Keep current managed-install protections and post-exit installation unchanged.

## Implementation plan

- [x] Reproduce suppression on the second startup and missing periodic checks in
  tests/test_ui_updates.py; add a policy regression for an explicit startup check.
- [x] Allow the startup check to bypass persisted cooldown in installation/service.py.
  Schedule recurring checks in installation/views/updates.py, retaining cooldown
  for non-startup calls and checking opt-out before work. On a successful
  false-to-true settings save, launch a forced check.
- [x] Verify startup, periodic checks, opt-out and installation regressions with
  the installation-updates scope. Update CHANGELOG.md and DEV_CHANGELOG.md.

No API, dependencies, installer, package version or release changes are required.
