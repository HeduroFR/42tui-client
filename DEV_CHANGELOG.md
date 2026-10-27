# Development changelog

Latest release: **0.3.0** (`v0.3.0` in the original repository).
Package version: **0.4.0**, prepared but not published.
Prepared next release: **0.4.0**, because first-run setup now requires a connected
42 account. This changes the previously optional connection flow while the project
is pre-1.0. Preparation is authorized; tagging and publication are not.

This file tracks implemented changes since the latest release. Keep published
history in [CHANGELOG.md](CHANGELOG.md). Maintenance, version selection and reset
instructions are in [distribution operations](docs/distribution.md#development-changelog).

## Changes since 0.3.0

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
  focused regressions. Reference: uncommitted `feat/tester-one-click`.

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

- **2026-10-27 · patch · Cached UI lifecycle:** reject activity renders as soon as
  Textual starts removing the screen, and skip status updates after removal.
  Make Friends cache tests wait for tab readiness and the actual sync worker
  instead of an initial idle flag. Reproduced the activity crash in repeated
  local runs; the deterministic removal regression failed before the fix.
  Reference: PR #7 (`feat/version-title`). Final checks recorded below.
- **2026-10-27 · patch · Friend search:** refresh readiness/status when suggestion
  results change independently of the highlighted row. Reference: `682f4f4`.
- **2026-10-27 · patch · Installation website:** redirect `/github` to the new
  client repository. Reference: `636fe31`.
- **2026-10-26 · patch · Release tooling:** find existing draft GitHub releases,
  including paginated results, when resuming publication. Reference: `a0ca473`
  in the original repository, carried into the client split.

### Internal changes and documentation

- **2026-10-27 · no release required · Publication cutover:** activate the existing
  stable tag workflow as `.github/workflows/release.yml`, preserving validation,
  CI, OIDC permissions and immutable artifact checks. The maintainer confirmed
  PyPI setup; the GitHub `pypi` environment is restricted to `v*` tags. Update
  contributor and distribution guidance. Reference: `feat/enable-release-publishing`.
  No tag or publication is performed by this task; final checks are recorded below.
- **2026-10-27 · no additional release impact · Release preparation:** prepare
  stable package 0.4.0 and its user-facing notes; preserve the 0.3.0 published
  baseline and all pending development entries until publication is verified.
  Require fetching origin before new branches in both repositories' AGENTS.md.
  Reference: `feat/release-0.4.0`; backend documentation is on
  `docs/fetch-before-branch`. Validation and publication blockers are below.
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

- Publication cutover: **6 focused release tests passed**. Workflow YAML, tag-only
  trigger, CI dependency, `pypi` environment and job-scoped OIDC permissions were
  checked; the renamed workflow is byte-for-byte identical to its disabled
  predecessor. GitHub environment reads confirmed only `v*` tag deployments.
  The maintainer confirmed PyPI setup; an actual OIDC upload is not yet verified.
- 0.4.0 preparation: **6 focused release tests passed** after refreshing editable
  package metadata. Tag/version validation, wheel/sdist contents, a wheel rebuilt
  from the sdist, fresh installed-package entry points/resources, app-header
  version and bundled upgrade notes passed. Installer helper hashes, shell syntax
  and documentation diff checks passed. PyPI version 0.4.0 and remote tag v0.4.0
  were absent during preparation. Artifacts are in ignored
  `.local/release-0.4.0/dist/`; unrelated local files are excluded.
- The merged release preparation `54acfcc` passed all PR #9 CI checks. The workflow
  cutover still needs its own PR CI/review and merge, then validation on the exact
  release revision. No tag, upload or deployment has been performed.
- Cached UI lifecycle fix: **90 release-tooling scope tests, 9 project activity
  tests and 4 friend-project preview tests passed**. All 8 cache UI tests passed
  in **10 consecutive runs** after the original activity crash reproduced on
  the third pre-fix run. The deterministic pruning regression failed before
  the fix. Diff checks passed; the full suite is left to PR CI.
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
- Release 0.4.0 remains worth preparing: accumulated onboarding and tester behavior
  justify the existing minor bump from published 0.3.0. No version bump or publication
  is performed; CI and native platform checks still block publication readiness.
