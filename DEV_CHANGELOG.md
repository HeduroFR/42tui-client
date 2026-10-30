# Development changelog

Latest release: **0.6.0** ([`v0.6.0`](https://github.com/HeduroFR/42tui-client/releases/tag/v0.6.0)).
Package version: **0.6.0**.
Suggested next release: **0.7.0** (minor) for optional encrypted and session-only
account storage, after security review, campus validation and release checks.

This file tracks implemented changes since the latest successful release. Keep
published notes in [CHANGELOG.md](CHANGELOG.md). See
[distribution operations](docs/distribution.md#development-changelog).

## Changes since 0.6.0

- 2026-10-30: Expand the 0.7.0 roadmap to cover a substantial projects, friends
  and dashboard loading and cache rework. Documentation only; no release required.
  Checked roadmap placement and diff; implementation and performance validation
  remain pending.

- 2026-10-30: Add session-only and passphrase-encrypted account storage, startup
  unlock, explicit keyring migration and local vault reset. Preserve the keyring
  option and serialize store switches with token refresh. Minor impact. The
  accounts scope passed 109 tests with one skip; 23 focused storage, UI and
  translation checks passed after subsequent changes, including startup unlock
  cancellation. Earlier accounts runs
  twice failed an onboarding navigation assertion which passed in isolation and
  on the later complete run. Security review, campus KDF calibration, platform
  validation and release checks remain outstanding.

- 2026-10-30: Add the in-memory credential-store foundation in commit `1d75eb3`.
  Seven keychain tests passed at that stage; integrated and validated above.

- 2026-10-30: Record the verified 0.6.0 publication and update the distribution
  baseline. GitHub and PyPI wheel and source archive hashes match. No release
  required; backend deployment and compatibility verification remain outstanding.
