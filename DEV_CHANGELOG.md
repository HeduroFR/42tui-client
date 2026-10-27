# Development changelog

Latest release: **0.4.1** ([`v0.4.1`](https://github.com/HeduroFR/42tui-client/releases/tag/v0.4.1)).
Package version: **0.4.1**, published to PyPI and GitHub.
Suggested next release: **0.5.0** (minor), focused on testers and update
reliability. Tester setup is merged; automatic-update checks are implemented in
`ee60aa2` on `fix/automatic-update-checks`, with focused validation recorded below.
Main integration and final candidate validation remain. See [TODO.md](TODO.md).
A release is worth preparing; native Docker/macOS validation and fresh candidate
checks remain required before publication. No version bump is authorized here.

This file tracks implemented changes since the latest release. Keep published
history in [CHANGELOG.md](CHANGELOG.md). Maintenance, version selection and reset
instructions are in [distribution operations](docs/distribution.md#development-changelog).

## Changes since 0.4.1

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

- **2026-10-28 · patch · Automatic update checks:** check on every stable-version
  startup, bypassing a recent persisted check, then schedule checks every 12 hours
  during the session; re-enabling the setting immediately starts a check.
  Enforce opt-out before scheduling network work and again
  before accepting results. Keep post-exit installation, managed-tool detection,
  development/pinned protections and offline failure behavior unchanged.
  Regression tests first reproduced both suppressed relaunch and missing periodic
  detection. Reference: `ee60aa2` (`fix/automatic-update-checks`).
  Validation: all 70 installation-updates scope tests passed; scope ownership
  and diff whitespace checks passed; 2 campus-settings UI tests passed.
  Independent read-only review passed. Live PyPI lookup returned 0.4.1. No release
  performed; full regression coverage is delegated to PR CI.
  The accumulated tester feature still warrants a 0.5.0 minor release; this fix
  alone is patch-sized (0.4.2 if released separately without tester changes).

### Internal changes and documentation

- **2026-10-28 · no release required · Roadmap alignment:** bring the agreed
  0.5.0 scope and future keyboard-navigation milestone onto
  `fix/automatic-update-checks` from roadmap commits `3ebcf07` and `80ea4b9`.
  Replace the stale uncommitted-update status with implemented commit `ee60aa2`
  and its recorded focused validation; separate completed implementation/notes
  from pending main integration, native tester checks and final candidate CI.
  Keep GitHub/star reminder, standalone binaries and broader README work deferred.
  Reference: uncommitted documentation on `fix/automatic-update-checks`.
  Checks: documentation diff, relative links and whitespace reviewed; existing
  behavioral test results retained as recorded evidence, not rerun for this task.
  Release impact: no release required for this planning change. The accumulated
  tester feature and update fix merit 0.5.0 preparation; main integration, native
  tester validation and final release-candidate checks still block publication.

- **2026-10-27 · no release required · Verified 0.4.1 publication:** publish the
  isolated correction-slot candidate `30e124509489c5017cacc5320ecc7f23ab395273`
  after explicit authorization to replace the unpublished initial tag. The first
  tag's three attempts stopped in CI before package publication. The corrected
  candidate changes only tests/docs; later tester features are excluded.
  [Release run 40597765312](https://github.com/HeduroFR/42tui-client/actions/runs/40597765312)
  passed all release checks and PyPI publication; retry only the GitHub job with
  the original CI artifacts after the newly created draft was briefly invisible.
  GitHub release publication completed at 2026-10-27T22:55:56Z.
  Verify all seven GitHub assets/checksums, and byte equality of both distributions
  against release CI artifacts and PyPI SHA-256 digests. The published wheel is
  `8d3a5b36d4943184c1dcd57bf8adb69dc9eee25203ec004c174d11a3b0a7eabf`;
  sdist is `0f020726d027e870ead359874c9747be6d3afa826fab6949411d598f40c5bfeb`.
  A disposable unpinned uv installation successfully ran the actual `42tui update`
  from 0.4.0 to 0.4.1, then passed CLI/resource smoke and package integrity checks.
  Tool, XDG and cache paths stayed under /tmp; no real user data or credentials.
  Compatibility run 40596520184 passed three pairs against deployed backend
  `e917aca`, with 0.4.0 as oldest supported client. Production PostgreSQL SELECT 1,
  Redis PING, deployed-code hash and API health were verified. Live Intra writes
  remain unverified; synthetic slot HTTP checks do not establish live acceptance.
  Reset only shipped patch/preparation records, retain unreleased tester work and
  validation, complete TODO.md and update distribution guidance. Reference: PR #17.
  Checks for this documentation: diff/relative links and publication evidence
  reviewed; runtime suites were not repeated for the documentation reset.

## Validation and release readiness

The 0.4.1 publication is verified. The 0.5.0 scope covers tester setup and update
reliability. The update fix is implemented and locally validated in `ee60aa2`,
but still requires main integration and final candidate checks. The successful
patch release does not validate native tester installation. See
[the 0.5.0 checklist](TODO.md#050--testers-and-update-reliability).

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
- The tester feature merits a minor release (0.5.0) after published 0.4.1.
  Native school Docker access and macOS installation remain unverified. CI for
  PR #16 passed all 21 jobs, including the tester scope; future candidates still
  require their own exact revision checks.

### PR #13 merge validation (2026-10-27)

- Conflict markers removed; both unreleased tester work and main's release record
  retained. Standard tester scope: 70 passed in 51.827 seconds, without the earlier
  heartbeat workaround. Correction scope: 52 passed in 15.306 seconds. Locale
  checks: 2 passed. All 823 discovered tests have exactly one scope owner; staged
  whitespace checks passed. Full suite and native Docker/Mac integration not rerun.
- Unrelated companion work in the primary checkout is excluded from this worktree.
