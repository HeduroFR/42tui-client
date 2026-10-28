# Development changelog

Latest release: **0.4.4** ([`v0.4.4`](https://github.com/HeduroFR/42tui-client/releases/tag/v0.4.4)).
Package version: **0.4.4**. The working tree also contains unreleased tester
changes; the published patch uses isolated candidate `bbb619d`.
Suggested next release: **0.5.0** (minor), for the unreleased tester setup below.
A release is worth preparing; native Docker/macOS validation and fresh candidate
checks remain required before publication. No version bump is authorized here.

This file tracks implemented changes since the latest release. Keep published
history in [CHANGELOG.md](CHANGELOG.md). Maintenance, version selection and reset
instructions are in [distribution operations](docs/distribution.md#development-changelog).

## Changes since 0.4.4

- **2026-10-28 · minor (accumulated tester feature) · 0.5.0 validation:**
  track each release-roadmap item in docs/superpowers/plans/2026-10-28-release-0.5.0.md.
  Add ten missing French/Spanish tester diagnostic translations per language,
  preserving technical error details. Isolate the desktop-start regression from
  the host's installed Docker application path; the first native macOS run exposed
  this test-only dependency (69/70 passed). Branch: `feat/0.5.0-validation`;
  commit/PR pending. Base: `c5dee552f8e494827e6eaa8d0419aa3f82c9cd5c`.
  Installation-updates scope: 83 passed. Scope ownership: all 848 tests assigned
  exactly once. Existing locale tests: two passed; 20 diagnostic translations
  and dynamic detail preservation passed an assert-based check. Baseline wheel/
  sdist build, package contents, installed CLI/resources, installer hashes,
  POSIX installer/uninstaller syntax and current `v0.4.4` consistency passed.
  Final tester rerun: 70 passed in 49.446 seconds. Rebuilt wheel/sdist contents,
  installed CLI/resources/locales and sdist-rebuilt installed smoke passed after
  translations; every French/Spanish format field matches its source.
  Native arm64 macOS probe correctly detects the installed per-user Docker
  Desktop and stopped engine (missing socket); no host setup was run. Native
  school Linux, real image build/run, clean macOS installation/retry and final
  committed-candidate CI remain release blockers. No API/backend/schema change;
  no backend rollout required. This is local validation, not fresh exact-pair or
  deployed-backend evidence. Minor 0.5.0 remains worth preparing after review,
  but is not ready to publish. No version bump, commit, push or publication.

- **2026-10-28 · no release required · Evaluation roadmap:** explicitly record
  project evaluation-slot booking and upcoming evaluations on the dashboard for
  0.6.0, with evaluation events/reminders in the 0.7.0 notification inbox. Separate
  booking from existing correction availability management. Planning only; no
  runtime/API changes or new release blocker. Checks: documentation diff and
  existing relative links reviewed; behavioral tests not run for this docs-only
  task. Branch: `docs/evaluation-roadmap`; commit/PR pending. Accumulated tester
  work still warrants 0.5.0 after native validation and exact-candidate checks.

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


### Internal changes and documentation

- **2026-10-28 · no release required · Verified 0.4.4 publication:** after user
  review and explicit tag approval, publish isolated candidate
  `bbb619db0cfd6e64ad7c6e8e6661b945327f87fd` from v0.4.3. Includes pre-launch
  updates (PR #26), note-loss/dashboard/manual-timer safety (PR #27, `b291006`)
  and project-workflow roadmap documentation from `e5504f9`. Integration PR #28
  merged as `18eea9c`, preserving candidate ancestry and pending 0.5.0 tester work.
  Release run [40762004464](https://github.com/HeduroFR/42tui-client/actions/runs/40762004464)
  succeeded on attempt 3. GitHub publication completed at 2026-10-28T20:27:17Z;
  PyPI and GitHub publication verified. All seven GitHub assets/checksums match;
  both PyPI/GitHub distributions are byte-identical to original attempt-1 CI
  artifacts. Wheel SHA-256:
  `77cfd60f55a9c8af1d98d69645ef3f96f3d283f48f1c2b3fd4ef3921e1a47529`;
  sdist: `fa8d6a39166b1ab472e639b26781afd3b1149dc0e62b66da19c1e328ebc051cb`.
  Candidate scopes ran 824 tests: 820 passed, four optional integrations skipped.
  Fresh archived build/version/package/installed smoke and source-rebuild checks
  passed. Documentation-only roadmap integration changed no runtime/test/wheel
  members. All 21 PR #28 checks passed, as did three exact-revision synthetic
  friend-preview compatibility pairs in run40760015793 against backend e917aca
  with supported client0.4.0. This client-only release requires no backend change.
  Release CI retried the existing onboarding step timing failure once; unchanged
  code passed. GitHub draft-visibility delay required retrying only its publisher
  using original artifacts, without replacing the tag or rebuilding PyPI files.
  Actual unpinned `42tui update` upgraded disposable PyPI0.4.3 to0.4.4, preserved
  local data and passed installed CLI/resource smoke. Initial PyPI index lag
  selected0.4.3; retry succeeded. No personal data or credentials used.
  Existing duplicate active timer rows remain unrepaired; native pipx/Windows,
  live OAuth/Intra writes and full API coverage weren't exercised locally.
  Hosted installer deployment remains pending access as previously recorded;
  no hosting/backend deployment performed by this release. Advance the verified
  package baseline, remove shipped pending entries and preserve all future scopes
  and pending tester/native-validation gates. Checks for this documentation:
  release evidence, links and whitespace reviewed. No additional release needed.

- **2026-10-28 · no release required · Verified 0.4.3 publication:** after explicit
  user authorization, publish isolated candidate
  `67be64839c2cd921898a5ac7b1ddde6441a42ddc` from v0.4.2. Installer/navigation
  fix and README note came through [PR #23](https://github.com/HeduroFR/42tui-client/pull/23);
  [PR #24](https://github.com/HeduroFR/42tui-client/pull/24) integrated release
  metadata as `261e801` while preserving candidate ancestry and pending tester work.
  [Release run 40744295147](https://github.com/HeduroFR/42tui-client/actions/runs/40744295147)
  completed successfully on attempt 3; PyPI and GitHub publication are verified.
  GitHub publication completed at 2026-10-28T18:30:14Z. All seven GitHub assets
  and checksums match; both PyPI distributions and GitHub package files are
  byte-identical to the original attempt-1 CI artifacts. Wheel SHA-256:
  `6e0f10fe7528abd0a7ef4e064621a5374ed765f15b3b1ca19b9c7d46bd5ba7e4`;
  sdist: `41f5fd19b1d88e3ee0ea2602cf173cff8a2634daa15f347032a1671d162fd227`.
  Clean archived-candidate scopes ran 805 tests: 801 passed, four optional
  integrations skipped. Version/package/installed-resource checks passed, as did
  disposable fresh/repeat/exact-version installer and uninstall tests. Actual
  `42tui update` upgraded an unpinned PyPI 0.4.2 installation to 0.4.3, preserved
  disposable local data and passed installed CLI/resource smoke checks. Initial
  PyPI index propagation still selected 0.4.2; retry upgraded successfully.
  PR CI passed all 21 checks after retrying a friends UI teardown timer error.
  Release CI passed after retrying account onboarding/navigation UI failures;
  these failures were in unchanged 0.4.2 code/tests. The failed scopes passed
  on retry without source changes; intermittent UI regression instability remains.
  GitHub's draft-visibility delay required retrying only its publication job with
  original artifacts, without replacing the tag, rebuilding or republishing PyPI.
  Compatibility run 40743077664 passed all three synthetic friend-preview pairs
  against backend e917aca with supported client 0.4.0. The initial dispatch used
  the 0.4.0 tag object rather than its resolved commit and failed the revision
  guard; the corrected run passed. This client-only patch needs no backend change.
  Live OAuth/Intra writes, full API coverage and fresh backend deployment checks
  were not exercised. All smoke data/tool/cache paths stayed under /tmp.
  Hosted installer health is OK, but install.sh/install.ps1/install.py still
  differ from the release. Deployment is authorized but blocked on Dokploy/SSH
  access; existing Docker-host SSH authentication failed. No installer deployment
  has been performed. Update this item after access and deployment verification.
  Advance only the verified package baseline and clear shipped preparation entries;
  retain pending 0.5.0 tester work and its native validation gates. Checks for this
  documentation: release evidence, diff and links reviewed; no product release
  is needed for this reset.

- **2026-10-28 · no release required · Combined roadmaps:** integrate the GitHub
  Settings button/star-reminder plan and future keyboard/keymap redesign plan on
  current main. Retain the 0.5.0 tester scope and validation gates; correct the
  update-discovery status to shipped in 0.4.2 through PR #19. Preserve the verified
  0.4.2 baseline, publication evidence and existing pending tester work.
  Sources: `a26aa9e` (`docs/github-roadmap`, PR #21), `3ebcf07` and `80ea4b9`
  (`docs/keyboard-navigation-roadmap`). No runtime or package-version changes.
  Checks: reviewed both source roadmaps, combined diff, relative links and
  whitespace. Runtime tests were not run for this documentation-only change.
  Existing 0.5.0 native tester and exact-candidate release gates still apply;
  this integration requires no release.

- **2026-10-28 · no release required · Verified 0.4.2 publication:** after explicit
  tag/publication authorization, publish isolated candidate
  `0f3f4c3642e11f39a958fbe89e09a0d4e868b1d9`, integrated through
  [PR #19](https://github.com/HeduroFR/42tui-client/pull/19) as `b758138`.
  Close superseded PR #18. The patch contains update discovery, exam resumption
  filtering and first-run instructions; later tester features are excluded.
  [Release run 40603624612](https://github.com/HeduroFR/42tui-client/actions/runs/40603624612)
  passed all checks and both publishers. GitHub publication completed at
  2026-10-27T23:44:03Z. Verify all seven release assets/checksums and byte equality
  of both PyPI downloads and GitHub distributions against original CI artifacts.
  Wheel SHA-256: `86c9c66805ffe0358b36aade07e971bfb0be8b05f05e681b4fdb924f073ee6a0`;
  sdist: `f3383f18264f61d5a4e1a56bff7d25fec6dddce49b8c7dd314e9bcc03fdf3352`.
  A disposable unpinned uv installation ran the real `42tui update` from 0.4.1
  to 0.4.2, preserved a local-data sentinel and passed installed CLI/resource smoke.
  Initial PyPI metadata/index propagation briefly returned 404/0.4.1; retry succeeded
  without changing the tag, rebuilding or republishing. Tool/data/cache paths stayed
  under /tmp; no real user data or credentials were used.
  Exact-candidate compatibility run 40600874913 passed three synthetic friend-preview
  pairs against backend e917aca with 0.4.0 as oldest supported client. This patch
  changes no API or backend behavior; no new backend deployment was required.
  Live Intra writes and full API coverage remain outside that scenario.
  Advance only the verified baseline, clear shipped preparation records and complete
  TODO/plan checklists, retaining unreleased tester behavior and validation below.
  Checks for this documentation: diff, release evidence and relative links reviewed.
  No additional product release is needed for this documentation reset.

- **2026-10-28 · documentation · Project workflow roadmap:** integrate the
  planning content from `docs/project-workflow-roadmap` (`e5504f9`), preserving
  the verified 0.4.3 baseline and this isolated patch scope. Include urgent Git
  recovery/push workflows and proposed 42git, 0.6.0 dashboard/GitHub/Discord,
  0.7.0 notifications/presence, 0.8.0 profiles/clubs and later initiatives.
  Planning only; none of those features is implemented by 0.4.4. Review of links,
  documentation diff and whitespace passed. Candidate revision changes, so fresh
  exact-revision compatibility and archive/package checks are required.

## Validation and release readiness

The 0.4.4 package publication is verified. Hosted installer deployment remains
pending access as recorded above. Pending release work belongs to 0.5.0 tester
setup; the successful patch release does not validate native tester installation.

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
- The tester feature merits a minor release (0.5.0) after published 0.4.2.
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
