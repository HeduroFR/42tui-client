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

- **2026-10-27 · patch · App header:** show the installed package version instead
  of account connection status; preserve alpha, beta and release-candidate
  suffixes through language and connection changes. No version bump or changes
  to stable-only publication/update rules. Reference: uncommitted
  `feat/version-title`. Validation recorded below.
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

- **2026-10-27 · no release required · Contributor checks:** require focused local
  checks for affected features and leave the full suite to PR CI; a full local
  run is optional. Keep relevant packaging and compatibility checks. Reference:
  uncommitted `feat/version-title`. Reviewed the documentation diff, command/link
  targets and matching backend policy; no test suites rerun for this docs change.
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
- **2026-10-27 · no release required · User release notes:** populate CHANGELOG.md
  Unreleased with onboarding, friend-search, website-link and user-documentation
  changes. Remove CI/CD and internal release-process details from existing notes.
  Require future user-facing changes in both logs, with internal work recorded
  only in this development log.

## Validation and release readiness

- Header change: **4 focused locale/header tests passed**, including installed,
  alpha, beta, RC and final version strings across all supported languages and
  connection states. Regression-scope ownership and diff checks passed; a
  headless 100×30 render shows `42 TUI — 0.3.0` from installed metadata.
- Full client suite for the header change on merged-main base `58a67fc`:
  **795 tests, passed, 4 skipped** (opt-in Friends, social, OAuth and catalog-cache
  simulations). The target remains 0.4.0 for the accumulated
  onboarding change; prerelease publishing is not implemented, and publication
  ownership, live OAuth and compatibility/deployment checks remain blockers.
- Last recorded local client suite at `e5e42a3`: **794 tests, passed, 4 skipped**;
  regression-scope ownership and diff checks also passed.
- The development tracking change is documentation-only; local links and diff
  formatting are checked separately.
- Live OAuth, cross-repository compatibility and production deployment have not
  been verified for a new release in this log.
- Before release, review the skipped checks, confirm publication ownership and
  run the required checks on the exact release candidate. Follow
  [distribution operations](docs/distribution.md).
