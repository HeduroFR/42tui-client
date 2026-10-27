# Development changelog

Latest release: **0.4.0** ([`v0.4.0`](https://github.com/HeduroFR/42tui-client/releases/tag/v0.4.0)).
Package version: **0.4.1**, prepared but not published.
Suggested next release: **0.4.1** (patch), for correction-slot start selection.
Worth preparing; publication remains blocked on backend deployment and exact-pair
verification. Version preparation is authorized; deployment and publication remain separate.

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

- **2026-10-27 · no release required · Candidate checks:** fix two UI-cache
  tests that assumed a non-refresh reload always starts a worker; explicitly
  force synchronization before awaiting it. The release-tooling scope now passes
  all 90 tests locally, after refreshing editable package metadata to 0.4.1.
  Clean archived-commit wheel/sdist checks, installed-package smoke, 6 release
  tests, version validation and installer digests passed. Preserve unrelated
  untracked files and exclude them from clean release builds.
  Client PR #12 and backend PR #5 are linked; backend CI passed and #5 merged as
  `e917aca`. Authorized Dokploy deployment completed, the deployed slot-source
  hash matches that revision, 22 synthetic slot tests passed in the API container,
  and read-only PostgreSQL/Redis/API probes passed. Initial three-pair workflow
  `40589486585` passed; final candidate/deployed pair evidence must be refreshed.
  No live Intra mutation or client publication was performed.

- **2026-10-27 · patch preparation · 0.4.1:** prepare the authorized package
  version and matching release notes, reconcile distribution documentation with
  the verified GitHub 0.4.0 publication, and record 0.4.0 as the supported client
  baseline. Independent read-only review found no substantive slot-fix defects.
  Reference: `fix/correction-slot-start`. Deployment, final exact-pair evidence
  and publication remain pending; pending release entries are retained.

- **2026-10-27 · no release required · Release checklist:** track completed
  correction-slot fixes and local checks in TODO.md, with separate remaining
  review/CI, exact-pair compatibility, backend deployment, version preparation,
  publication authorization and post-release verification tasks. Preserve the
  existing distribution/documentation backlog. Reference:
  `258116b` (checklist); progress updates on `fix/correction-slot-start`.
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
- Backend deployment was verified as described above. HTTP simulations remain
  synthetic; real Intra acceptance and final exact-pair evidence are pending.
- Prepare 0.4.1 after review; do not publish before the required backend is verified.
