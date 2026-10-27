# Development changelog

Latest release: **0.4.0** ([`v0.4.0`](https://github.com/HeduroFR/42tui-client/releases/tag/v0.4.0)).
Package version: **0.4.1**, prepared but not published.
Prepared patch candidate: **0.4.1**, client `4e48e9b`, validated with deployed
backend `e917aca`; awaiting separate tag/publication authorization.
Suggested release including tester setup: **0.5.0** (minor), because the tester flow
adds user-visible setup and execution behavior after published 0.4.0. Keep the
existing 0.4.1 preparation unchanged; tester changes may follow that patch release.
The later tester release still requires its relevant CI, native platform checks
and exact-pair verification. Version preparation does not authorize deployment or publication.

This file tracks implemented changes since the latest release. Keep published
history in [CHANGELOG.md](CHANGELOG.md). Maintenance, version selection and reset
instructions are in [distribution operations](docs/distribution.md#development-changelog).

## Changes since 0.4.0

### Changed behavior

- **2026-10-27 · minor · Tester setup:** replace separate install/start/docs/recheck
  controls with one Run action per tester. Preserve compact image removal, locking,
  pinned sources, platform-specific images, mount checks and captured project paths.
  Setup uses no sudo, package-manager installs, system service changes or socket/group
  permission changes. Linux uses an accessible existing engine and can start an
  existing rootless user service. macOS installs Desktop under `~/Applications`
  through an unprivileged DMG mount, staged copy, signature verification and rename;
  failed copies remain retryable. Keep Desktop's user-level defaults.
  Build pinned `.git` sources inside Docker BuildKit without host Git, preserving
  Git metadata. Other custom HTTPS clone URLs retain the existing-Git fallback and
  give explicit guidance if Git is absent. Update README, French/Spanish copy and
  focused regressions. Reference: `3ea93ab`, [PR #13](https://github.com/HeduroFR/42tui-client/pull/13).

### Fixes

- **2026-10-27 · patch · Correction slots:** use the current quarter-hour rounded
  down plus 30 minutes as the earliest start (10:18 → 10:45), consistently for
  calendar selection, Add availability, editor publication and pre-dispatch checks.
  Keep nearby existing availability deletable. Update French/Spanish messages.
  Reference: client `82f583b`, backend `880ce27`.
  Requires the matching backend change deployed before releasing the client.

### Internal changes and documentation

- **2026-10-27 · no release required · Friend-search test readiness:** wait for
  the Add button's ResultsChanged handler before asserting it is enabled; table
  rows can appear before that queued UI message is processed. The unchanged
  v0.4.1 release run hit this test race twice. Preserve the immutable tag and all
  release gates; no product behavior or release artifact is changed by this test.
  Carry forward the partial-publication recovery guidance from superseded PR #11;
  close that obsolete 0.4.0 documentation PR instead of restoring its old baseline.
  Reference: `fix/friend-suggestions-test-readiness`. Friends scope: 52 tests
  passed, 1 optional integration skipped; independent read-only review passed.
  The bounded wait still fails if the button never becomes enabled, and the
  subsequent click and exact request assertion remain unchanged.

- **2026-10-27 · no release required · Final readiness record:** client PR #12
  merged as `4e48e9b`, with the same Git tree as PR head `a3cfc09`; CI run
  `40590113023` passed all 21 jobs (14 regression scopes, four platforms,
  packaging/installers, distribution container and campus-Python installation).
  Its exact wheel passed installed-package smoke and the synthetic slot HTTP
  roundtrip through the real client provider and backend routes/service/transport.
  Final compatibility run `40590735918` passed all three pairs against deployed
  backend `e917aca`, including supported client 0.4.0. The readiness checker
  accepted the candidate receipt and observed Dokploy deployment evidence.
  Update TODO.md to freeze the tested release candidate and leave only explicit
  publication authorization, tag/publish, and post-release verification pending.
  These documentation changes follow the candidate; do not retag a later head.
  Live Intra write acceptance remains unverified. No tag/publication performed.
  Checks: documentation diff, links, recorded CI and deployment evidence reviewed.

- **2026-10-27 · no release required · Readiness reconciliation:** merge the
  later tester work from main into the documentation branch without changing it.
  Preserve its minor-release advice and validation separately from the frozen
  0.4.1 patch candidate. Only DEV_CHANGELOG.md required textual conflict resolution;
  the release candidate remains 4e48e9b. Documentation diff/conflict checks passed.

- **2026-10-27 · no release required · PR #13 reconciliation:** merge current
  main into `feat/tester-one-click`. Preserve the published 0.4.0 baseline,
  correction-slot work and 0.4.1 patch preparation; retain only unreleased tester
  work and its validation from this branch. Do not restore changes already shipped
  in 0.4.0. Package version remains 0.4.1; combined tester release advice is 0.5.0.
  The only textual merge conflict was DEV_CHANGELOG.md. Focused checks recorded below.

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
- Backend deployment and final exact-pair evidence for patch candidate 4e48e9b
  passed as recorded above. Slot HTTP checks remain synthetic; real Intra
  acceptance is unverified. Obtain separate tag/publication approval and reverify
  backend readiness immediately before publication.

### Tester setup validation (2026-10-27)

- Adapter tests: 54 passed, covering no privileged setup commands, managed-school
  Docker missing/denied/stopped, user-only rootless startup, per-user macOS discovery,
  pinned remote builds without host Git, safe custom clone fallback, Git metadata,
  interrupted Mac copy cleanup/retry, timeout and terminal operation boundaries.
- Read-only reviews found partial-copy retry and custom-build compatibility gaps;
  reproduced each with failing regressions, fixed and verified the adapter suite.
  Linux rootless-service approval copy now describes Linux startup correctly.
- Final tester scope: 70 passed in 54.868 seconds using the runner-only heartbeat.
  Locale checks: 2 passed; new setup/error strings have French/Spanish coverage.
  Scope ownership: all 820 discovered tests assigned exactly once. Diff whitespace
  check passed. The full suite was not run locally.
- Ordinary UI runs stalled during Python 3.14 asyncio executor shutdown in this
  sandbox after successful assertions. A temporary runner-only event-loop heartbeat
  resolves the wakeup stall; product and test files contain no workaround.
- A WSL2/Ubuntu 26.04 probe confirmed Docker is absent here. The earlier privileged
  installation attempt stopped at the sandbox's no-new-privileges guard before any
  package changes. The final WSL probe selected no installation plan, produced the
  school-Docker guidance, executed zero host setup commands and released the lock.
- Native school Docker access, real container builds and native macOS installation
  remain unverified. Full-suite/CI remain release gates. Flake8 is unavailable.
- The tester feature merits a minor release (0.5.0) after published 0.4.0. The
  existing 0.4.1 patch candidate is preserved; no package version is changed here.
  Native school Docker access, macOS installation and combined CI remain unverified.

### PR #13 merge validation (2026-10-27)

- Conflict markers removed; both unreleased tester work and main's release record
  retained. Standard tester scope: 70 passed in 51.827 seconds, without the earlier
  heartbeat workaround. Correction scope: 52 passed in 15.306 seconds. Locale
  checks: 2 passed. All 823 discovered tests have exactly one scope owner; staged
  whitespace checks passed. Full suite and native Docker/Mac integration not rerun.
- Unrelated companion work in the primary checkout is excluded from this worktree.
