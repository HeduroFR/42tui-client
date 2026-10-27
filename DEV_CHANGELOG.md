# Development changelog

Latest release: **0.4.0** ([`v0.4.0`](https://github.com/HeduroFR/42tui-client/releases/tag/v0.4.0)).
Package version: **0.4.0**, published to PyPI and GitHub.
Suggested next release: **0.4.1** (patch), for correction-slot start selection.
Worth preparing; publication remains blocked on backend deployment and exact-pair
verification. The package version remains 0.4.0 until release preparation.

This file tracks implemented changes since the latest release. Keep published
history in [CHANGELOG.md](CHANGELOG.md). Maintenance, version selection and reset
instructions are in [distribution operations](docs/distribution.md#development-changelog).

## Changes since 0.4.0

### Fixes

- **2026-10-27 · patch · Correction slots:** use the current quarter-hour rounded
  down plus 30 minutes as the earliest start (10:18 → 10:45), consistently for
  calendar selection, Add availability, editor publication and pre-dispatch checks.
  Keep nearby existing availability deletable. Update French/Spanish messages.
  Reference: client `82f583b`, backend `880ce27`.
  Requires the matching backend change deployed before releasing the client.

### Internal changes and documentation

- **2026-10-27 · no release required · Release checklist:** track completed
  correction-slot fixes and local checks in TODO.md, with separate remaining
  review/CI, exact-pair compatibility, backend deployment, version preparation,
  publication authorization and post-release verification tasks. Preserve the
  existing distribution/documentation backlog. Reference:
  `fix/correction-slot-start` (checklist update uncommitted).
  Checks: documentation diff and relative links reviewed; no runtime tests rerun.

- **2026-10-27 · no release required · Release record:** verify the published
  wheel/sdist against GitHub checksums and PyPI digests, install the published
  wheel and verify its CLI/resources, then advance the published baseline to
  0.4.0 and clear only entries included in that tag. Preserve the user-facing
  release history and document safe recovery from a partial publication.
  Reference: `docs/post-release-0.4.0`.
  Publication used commit `bb5caff0988cbedd54d00c8dcb455a187da153bf` and
  [release run 40570776094](https://github.com/HeduroFR/42tui-client/actions/runs/40570776094),
  which succeeded after retrying the GitHub draft-visibility failure with the
  original CI artifacts. Live OAuth and pinned-pair compatibility were not
  exercised during publication; this limitation was disclosed before authorization.

## Validation and release readiness

- Post-release documentation diff/link checks passed. Runtime suites were not
  repeated for this documentation-only update.
- Correction-slot scope: 52 tests passed; regression-scope ownership checked.
- Backend HTTP simulation uses synthetic records; real Intra acceptance, deployed
  backend revision and exact-pair release checks remain unverified.
- Prepare 0.4.1 after review; do not publish before the required backend is verified.
