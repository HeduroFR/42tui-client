# Development changelog

Latest release: **0.6.0** ([`v0.6.0`](https://github.com/HeduroFR/42tui-client/releases/tag/v0.6.0)).
Package version: **0.6.0**.
Suggested next release: **none** until the session-storage feature is complete.

This file tracks implemented changes since the latest successful release. Keep
published notes in [CHANGELOG.md](CHANGELOG.md). See
[distribution operations](docs/distribution.md#development-changelog).

## Changes since 0.6.0

- 2026-10-30: Expand the 0.7.0 roadmap to cover a substantial projects, friends
  and dashboard loading and cache rework. Documentation only; no release required.
  Checked roadmap placement and diff; implementation and performance validation
  remain pending.

- 2026-10-30: Add an in-memory-only account connection choice, restoring the
  previous credential store when pairing is cancelled. Minor impact; 31 account
  UI tests and two focused session-only UI tests passed. The full accounts scope
  failed twice in an onboarding navigation assertion; that test passed in
  isolation. Encrypted-session integration and a clean accounts run remain pending.

- 2026-10-30: Prototype a passphrase-encrypted session store with scrypt,
  authenticated encryption and atomic writes. It is not connected to the app
  and requires security review, concurrent-session integration, UI, migration,
  recovery and campus calibration before use. Fourteen keychain/vault tests pass,
  including rejection of insecure and symlinked vault directories and reload of
  credentials changed by another unlocked store; failed atomic replacement also
  preserves the original vault;
  no release required for the unfinished prototype.

- 2026-10-30: Add an isolated in-memory credential-store implementation as
  groundwork for session-only account connections. It is not wired into the UI
  and changes no user behavior; no release required yet. Seven keychain tests
  passed with the project virtual environment. Storage selection, encrypted vault,
  security review and campus validation remain pending.

- 2026-10-30: Record the verified 0.6.0 publication and update the distribution
  baseline. GitHub and PyPI wheel and source archive hashes match. No release
  required; backend deployment and compatibility verification remain outstanding.
