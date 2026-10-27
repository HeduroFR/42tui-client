# Development changelog

Latest release: **0.3.0** (`v0.3.0` in the original repository).
Package version: **0.3.0**; no new release has been prepared.
Suggested next release: **0.4.0**, because first-run setup now requires a connected
42 account. This changes the previously optional connection flow while the project
is pre-1.0. This is a recommendation, not authorization to bump or publish.

This file tracks implemented changes since the latest release. Keep published
history in [CHANGELOG.md](CHANGELOG.md). Maintenance, version selection and reset
instructions are in [distribution operations](docs/distribution.md#development-changelog).

## Changes since 0.3.0

### Changed behavior

- **2026-10-27 · minor (pre-1.0 breaking change) · Onboarding:** remove Skip setup
  and the Escape bypass; require a connected 42 account before advancing or
  finishing. Reject completion if the connection is lost. Update French and
  Spanish copy. Existing completed installations retain their current status.
  Connection uses the existing OAuth flow; active enrollment is not separately
  checked. Reference: `e5e42a3`.

### Fixes

- **2026-10-27 · patch · Friend search:** refresh readiness/status when suggestion
  results change independently of the highlighted row. Reference: `682f4f4`.
- **2026-10-27 · patch · Installation website:** redirect `/github` to the new
  client repository. Reference: `636fe31`.
- **2026-10-26 · patch · Release tooling:** find existing draft GitHub releases,
  including paginated results, when resuming publication. Reference: `a0ca473`
  in the original repository, carried into the client split.

### Internal changes and documentation

- **2026-10-27 · no release required · Repository split:** separate the public
  client from the private backend, with independent contribution, CI and release
  ownership. Keep the current HTTP v1 contract and package version. Client
  publication remains disabled pending release ownership cutover. References:
  `f6a7250`, `a252c11`, `2bdd8a5`.
- **2026-10-27 · no release required · Client architecture:** move feature logic,
  storage/HTTP adapters and views into their owning modules; separate shared
  infrastructure and app composition; remove old internal import paths and update
  callers, resources and tests. CLI names and local data formats remain unchanged.
  References: `f6a7250`, `5e63aa5`.
- **2026-10-27 · no release required · Compatibility policy:** document independent
  client/backend versions, supported peer combinations, rollout order and required
  compatibility/deployment evidence for dependent client releases. Reference:
  `2bdd8a5` and `docs/api-compatibility.md`.
- **2026-10-27 · no release required · Regression checks:** stabilize team creation
  UI interactions in consolidated CI. Reference: `900b56c`.
- **2026-10-27 · no release required · User documentation:** rewrite the README,
  document project navigation and editor integrations, clarify platform support,
  and add contributor/agent workflow instructions. References: `7fc136c`,
  `69b8d40`, `d2d1423`, `766b167`, `16486fa`, `8b85760`, `5e0a39c`.
- **2026-10-27 · no release required · Development tracking:** add this rolling
  changelog, require updates and release advice after every task, and document
  version decisions and resetting released entries after successful publication.

## Validation and release readiness

- Last recorded local client suite at `e5e42a3`: **794 tests, passed, 4 skipped**;
  regression-scope ownership and diff checks also passed.
- The development tracking change is documentation-only; local links and diff
  formatting are checked separately.
- Live OAuth, cross-repository compatibility and production deployment have not
  been verified for a new release in this log.
- Before release, review the skipped checks, confirm publication ownership and
  run the required checks on the exact release candidate. Follow
  [distribution operations](docs/distribution.md).
