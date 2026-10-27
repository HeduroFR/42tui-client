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

## 0.5.0 integration status

Implemented in `ee60aa2` on `fix/automatic-update-checks`. DEV_CHANGELOG.md records
70 installation-updates tests and 2 settings UI tests passed, scope ownership,
whitespace checks and read-only review. These are focused checks, not a final
release-candidate validation.

This fix belongs to the agreed 0.5.0 testers/update-reliability scope in
[the roadmap](../../../TODO.md#050--testers-and-update-reliability). Main integration
and required PR/release checks remain pending. Keep its user-facing Unreleased
notes alongside the tester notes. Native tester validation remains a separate
release blocker; no new backend/API change is required.
