# Development changelog

Latest release: **0.6.0** ([`v0.6.0`](https://github.com/HeduroFR/42tui-client/releases/tag/v0.6.0)).
Package version: **0.6.0**.
Suggested next release: **none** until the session-storage feature is complete.

This file tracks implemented changes since the latest successful release. Keep
published notes in [CHANGELOG.md](CHANGELOG.md). See
[distribution operations](docs/distribution.md#development-changelog).

## Changes since 0.6.0

- 2026-10-30: Add an isolated in-memory credential-store implementation as
  groundwork for session-only account connections. It is not wired into the UI
  and changes no user behavior; no release required yet. Seven keychain tests
  passed with the project virtual environment. Storage selection, encrypted vault,
  security review and campus validation remain pending.

- 2026-10-30: Record the verified 0.6.0 publication and update the distribution
  baseline. GitHub and PyPI wheel and source archive hashes match. No release
  required; backend deployment and compatibility verification remain outstanding.
