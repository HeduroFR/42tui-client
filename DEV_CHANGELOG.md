# Development changelog

Latest release: **0.4.4** ([`v0.4.4`](https://github.com/HeduroFR/42tui-client/releases/tag/v0.4.4)).
Package version: **0.5.0** (release candidate).
Suggested next release: **0.5.0** (minor), for conservative project recovery,
reviewed committed-history pushes and `42git`, including the existing one-button
tester implementation. The tester workspace rework remains planned for **0.6.0**.
The maintainer authorized preparation, PR, merge after green checks, tagging and
publication on 2026-10-29 and confirmed the native Vogsphere/Linux/macOS tester
checks. This is maintainer evidence, not an agent-observed native run.
The maintainer confirmed production deployment/functional checks of backend
`f357da3`. The requested 10-second OAuth close follow-up requires a new backend
rollout. Exact-candidate CI and compatibility remain pending; do not mark publication complete until artifacts and update are verified.

This file tracks implemented changes since the latest release. Keep published
history in [CHANGELOG.md](CHANGELOG.md). Maintenance, version selection and reset
instructions are in [distribution operations](docs/distribution.md#development-changelog).

## Changes since 0.4.4

- **2026-10-29 · minor · 0.5.0 release preparation:** integrate pushed Git
  workflow `40d5f19` with main `cf86cb2`; retain OAuth theme handoff, tester
  diagnostics, roadmap tasks and publication history. Set authoritative package
  version and release notes to 0.5.0. Clarify that pushes publish committed history
  and that separate Vogsphere selection/staging UI remains future work. `42git`
  needs PATH only, without additional shell initialization. Preserve unrelated
  untracked duplicate files. Maintainer confirmed native validation; agent CI,
  packaging, compatibility and publication checks are recorded as they complete.
  Branch: `feat/release-0.5.0`; PR #38. Initial candidate `977daf8` passed
  local project scope (139), account UI (30), locales (two), installer unit tests
  (23), clean archived wheel/sdist checks, installed CLI/resources and disposable
  fresh/repeat/exact-version installation/uninstall. All three synthetic
  compatibility pairs passed in backend run 40789078183 against `f357da3` with
  oldest client `bb5caff` (0.4.0). Native checks/deployment confirmed by maintainer.
  User then requested a 10-second close attempt on the OAuth connected page;
  update notes/compatibility guidance and require the backend follow-up rollout
  before the final tag. Existing browser restrictions require manual-close copy.
  No client runtime change for this follow-up; fresh revision checks remain due.

- **2026-10-29 · patch (accumulated minor 0.5.0) · Project details dialog:**
  replace the viewport-wide metadata dump with a width-capped, scrollable dialog,
  selected-project heading and separate catalog, workspace and repository sections.
  Keep all catalog rules/snapshot evidence, Intra link, Git status and remote/path
  values. Use distinct field labels and a centered neutral Close button; preserve
  Escape dismissal. Pass structured sections from the existing single caller,
  without parsing translated text or changing shared catalog formatting.
  Add French/Spanish Catalog headings. Branch: `feat/project-git-workflow`;
  committed in `1a76c27`–`40d5f19`. Checks: eight project-layout, nine architecture and three
  catalog-formatting tests passed, including 80×24 footer visibility/scrolling,
  section grouping, project identity and centered Close alignment. French/Spanish
  headings, fatal-error lint and whitespace passed. Full CI and native UI were
  not run. Included in the pushed feature branch. Minor 0.5.0 remains worth preparing after review with existing
  native/on-campus, tester and exact-candidate release gates; no API change.

- **2026-10-29 · patch (accumulated minor 0.5.0) · Reconnect and Docker messages:**
  center session-expiry actions, replace Later with Quit TUI (including Escape),
  exit through the normal app shutdown path and remove the prompt's question mark.
  Keep reconnect's single-click pairing behavior. Translate the new copy to French/
  Spanish. Simplify tester Docker status to actionable summary/folder guidance,
  retaining the raw diagnostic in a tooltip instead of the visible status body.
  No expandable detail UI added. Branch: `feat/project-git-workflow`; commit/PR
  pending. Checks: 29 account UI, two locale and 15 tester UI tests passed,
  including centered buttons, Quit dispatch and hidden long Docker diagnostics.
  Fatal-error lint and whitespace checks passed. Live OAuth/Docker and full CI
  were not run. Included in the pushed feature branch; minor 0.5.0 remains worth preparing after review with existing
  native/on-campus, tester and exact-candidate release gates. No API/backend change.

- **2026-10-29 · patch (accumulated minor 0.5.0) · Tester section layout:**
  move Testers below Registration/activity in the overview column and remove
  the top-right shortcut button, its event route and enable/disable references.
  Preserve the t shortcut and update UI/manual smoke callers and README.
  Bound status diagnostics to five scrollable lines; keep the actionable summary
  and missing-folder guidance before the full Docker detail. No diagnostic text
  is discarded. Branch: `feat/project-git-workflow`; committed in `1a76c27`–`40d5f19`.
  Checks: 15 tester UI tests, eight project-layout tests and nine architecture
  tests passed. Regressions cover the removed header action, section placement,
  small-terminal shortcut/focus and full long diagnostics in a five-line viewport.
  All 885 tests have exactly one regression-scope owner; fatal-error lint and
  whitespace passed. Real Docker/manual smoke and full CI not run.
  Included in the pushed feature branch; minor 0.5.0 remains
  worth preparing after review with the existing native/on-campus, tester and
  exact-candidate release gates. No real tester/container execution in this task.

- **2026-10-29 · patch (accumulated minor 0.5.0) · Git button layout:**
  align editor, configuration and Git action rows to two equal-width columns
  across the workspace. Push dev/Push vog sit side by side; Push all and Open
  folder span both columns, with consistent spacing. Keep the explorer wording
  in the folder tooltip. Use the short vog label and Vogsphere/master tooltip so translated
  labels fit narrow sidebars. Keep shared button styling, action IDs and
  disabled behavior. Put timer control on the right of wrapping time/status text.
  Branch: `feat/project-git-workflow`; committed in `1a76c27`–`40d5f19`.
  Eight UI tests and nine size/locale checks (80/140/160 columns × English/
  French/Spanish) passed for matching row widths, full-row spans, spacing and
  readable labels. Final timer-row checks: eight UI tests and nine size/locale
  assertions passed for right alignment and contained time/status text.
  Whitespace check passed. Preserve all action IDs and
  disabled behavior.
  Included in the pushed feature branch; preserve the unrelated local
  uv.lock. Minor 0.5.0 remains worth preparing after review, subject to the
  existing native/on-campus, tester and exact-candidate release gates.

- **2026-10-28 · patch (accumulated minor 0.5.0) · Campus-only Vogsphere:**
  reflect the maintainer-confirmed campus network requirement in CLI/TUI push
  previews, French/Spanish copy and the concise README/detailed Git guide.
  Vogsphere pushes are unavailable outside campus; real authentication checks
  must run on campus using the student's existing Git/SSH setup. No network
  bypass or campus detection added. CLI scope: four passed, including preview
  guidance. The maintainer approved opening existing committed checkouts with
  a warning when Vogsphere is unreachable; fresh/empty/unborn recovery and actual
  history conflicts still block. Surface the warning in setup and editor flows;
  retry verification next editor launch instead of caching an unverified result.
  Document campus Push all, home Push dev, then development fast-forward on return.
  Distinguish strictly-ahead development history and recommend an explicit
  fetch/pull with --ff-only before retrying. Focused checks passed: 27 Git,
  13 service, four CLI and eight UI tests; fatal-error lint and whitespace clean.
  No live campus/Vogsphere verification. Changes committed on
  `feat/project-git-workflow`; committed in `1a76c27`–`40d5f19`. Recommended release remains
  minor 0.5.0, with the native/on-campus and exact-candidate gates above.

- **2026-10-28 · minor · Project Git workflow:** recover nonempty Vogsphere
  master before development work in a fresh folder; fetch/inspect existing
  checkout history and stop for manual reconciliation instead of overwriting
  local work. Preserve files, index, branches, remotes and pre-push hooks.
  Review pinned committed HEAD, destination URL and branch before Push dev,
  Push Vogsphere or Push all; report each outcome and retry failed destinations
  separately. Development receives the current branch and Vogsphere receives
  master; no automatic commit, reset or forced push. Add `42git status/push`
  for the configured project containing the current directory, an explorer
  action and French/Spanish UI strings. Wire recovery before first editor launch,
  capture project identity across asynchronous operations and block overlap.
  Include the 42git entry point in installer ownership checks and package smoke;
  refresh installer helper digests. Keep README commands compact and link the
  detailed guide. Bring in the agreed milestone order from
  `origin/docs/tester-workspace-roadmap` (`96c2991`); no package-version change.
  Branch: `feat/project-git-workflow`; committed in `1a76c27`–`40d5f19`. Focused checks:
  22 disposable Git tests, 13 existing services tests, four CLI tests, eight
  project-controls UI tests, nine architecture tests, two locale tests and
  41 installer tests passed. Scope ownership covers 879 tests exactly once;
  canonical import tests (three), fatal-error lint, installer hashes and shell
  syntax passed. Wheel/sdist contents and installed entry points/resources,
  including 42git help, passed. Integrated project scope: 132 passed in 87.759s.
  Actual uv fresh/repeat/exact-version installation and uninstall passed with
  a disposable HOME and this candidate wheel. Final integration review found
  two edges, now fixed: hidden URL changes invalidate a reviewed push using
  a non-secret fingerprint, and late worker completion cannot update an inactive
  push screen or open an editor after app unmount. Final focused Git (22), CLI
  (four) and UI (eight) checks passed after these changes. No real user repository,
  credentials or remote writes used.
  Minor 0.5.0 is worth preparing for this feature after review; not ready to
  publish. Exact-candidate CI, supported-peer compatibility, native platform
  checks and explicit validation/inclusion of the unreleased tester code still
  gate release. No API/backend/schema changes or deployment required.

- **2026-10-29 · no release required · OAuth branch sync:** merge current
  `main` (`1e9054f`) into `feat/oauth-terminal-page` for PR #37 without
  conflicts. Preserve the OAuth theme handoff and main's roadmap, documentation,
  translations and tester checks. Validation: 29 OAuth transport tests passed;
  regression ownership check passed (851 tests assigned exactly once);
  staged whitespace check passed. Full suite and production OAuth were not run.
  This synchronization adds no release justification; the planned 0.5.0 Git
  workflow and exact-candidate validation remain pending. No version bump,
  deployment or release was performed.

- **2026-10-28 · minor (accumulated tester feature) · Tester validation:**
  track each release-roadmap item in docs/superpowers/plans/2026-10-28-release-0.5.0.md.
  Add ten missing French/Spanish tester diagnostic translations per language,
  preserving technical error details. Isolate the desktop-start regression from
  the host's installed Docker application path; the first native macOS run exposed
  this test-only dependency (69/70 passed). Branch: `feat/0.5.0-validation`;
  reference: PR #36. Base: `c5dee552f8e494827e6eaa8d0419aa3f82c9cd5c`.
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
  deployed-backend evidence. The tester rework now targets 0.6.0 and is not implemented by these checks.
  Reconcile with current main while retaining its 0.5.0 Git scope, roadmap and
  publication history. No version bump or publication. Documentation reconciliation
  checks: relative links, tracker references, conflict markers and whitespace;
  runtime suites were not repeated for this documentation-only merge resolution.

- **2026-10-28 · no release required · Discord release documentation:** link
  CONTRIBUTING.md to the emoji release-note template and native GitHub-to-Discord
  webhook setup in docs/distribution.md. Explain automatic extraction, heading
  levels, credential handling and delivery verification. Documentation only;
  no webhook configured or release published. Reference: PR #35.
  Reconcile with current main, retain one entry per roadmap change and align
  evaluation milestones with TODO.md. Checks: documentation diff, relative links,
  template heading extraction, conflict markers and whitespace reviewed;
  no runtime tests or live delivery test. This documentation needs no release;
  0.5.0 remains the Git target after implementation, candidate inclusion review
  and release validation.

- **2026-10-28 · no release required · Agreed 0.5.0 Git design:** consolidate
  recovery/source choice, existing-folder protection, separate Vogsphere file
  selection, staging/commits, push review/retries and the initial 42git commands
  and help. Record project-panel simplification and precise Intra list statuses,
  with current-attempt precedence and cached-data handling. Planning only;
  implementation and validation remain pending. Based on fetched main `c5dee55`,
  carrying roadmap commit `38360ea` without creating a new commit; retain main's
  evaluation booking/dashboard and reminder scopes under 0.7.0 and 0.8.0.
  Checks: documentation diff, milestone order, command consistency, relative links,
  conflict-marker and whitespace checks; no behavioral tests for this docs-only
  task. Branch: `docs/git-workflow-design`; commit/PR pending. No release required
  for these documents; minor 0.5.0 remains the Git target after implementation,
  candidate inclusion review and release validation.

- **2026-10-28 · no release required · Evaluation roadmap:** explicitly record
  project evaluation-slot booking and upcoming evaluations on the dashboard for
  0.7.0, with evaluation events/reminders in the 0.8.0 notification inbox. Separate
  booking from existing correction availability management. Planning only; no
  runtime/API changes or new release blocker. Checks: documentation diff and
  existing relative links reviewed; behavioral tests not run for this docs-only
  task. Branch: `docs/evaluation-roadmap`; commit/PR pending. Accumulated tester
  rework targets 0.6.0 after implementation, native validation and exact-candidate checks.

- **2026-10-28 · no release required · Milestone order:** assign the urgent
  project Git workflow and proposed 42git to 0.5.0. Move testers to 0.6.0,
  dashboard/interface work to 0.7.0, notifications/presence to 0.8.0 and
  profiles/clubs to 0.9.0. Reorder TODO sections and update active references;
  keep published release history and unversioned initiatives intact. Planning
  only; no implementation, API or package-version changes. The Git scope and
  candidate checks remain pending; already-merged tester code needs an explicit
  inclusion/validation decision for 0.5.0. Checks: documentation diff, milestone
  order, existing relative links and whitespace reviewed; no runtime tests for
  this docs-only change. Source: `38360ea` on `docs/tester-workspace-roadmap`.

- **2026-10-28 · no release required · Tester workspace roadmap:** record the
  agreed tester rework (now scheduled for 0.6.0): extend the existing tester
  catalog, prefer validated native execution, evaluate headless macOS containers,
  and show progress/results inside
  a dedicated TUI workspace. Include disposable project copies, cancellation,
  logs and a second tester to validate extensibility. Planning only; no runtime,
  API or package-version changes. Source: `38360ea` on
  `docs/tester-workspace-roadmap`. Checks: documentation diff, relative links and whitespace
  reviewed; no behavioral tests for this documentation-only task. Accumulated
  tester rework targets minor 0.6.0 after implementation and release validation.

### Changed behavior

- **2026-10-28 · patch · OAuth completion theme:** pass the active resolved
  background, surface, foreground, primary and success colors to the validated
  browser/manual pairing URL. A supporting backend shows a responsive terminal
  completion page with GitHub/Discord links and no auto-close. Older backends
  ignore the optional palette and older clients receive the default page.
  Reference: `feat/oauth-terminal-page`. Checks: 29 OAuth transport
  tests and 30 account-connection UI tests passed; accounts regression scope ran
  97 tests (96 passed, one optional simulation skipped); regression ownership check
  passed. Backend tests: 486 passed, 34 optional integrations skipped; typecheck and
  dark/light responsive Chromium checks passed. Production OAuth and pinned-pair
  deployment checks remain unverified; deploy and verify the backend before a
  dependent client release. Follow main's current roadmap: **0.5.0** (minor)
  targets the pending Git workflow, with tester rework planned for **0.6.0**;
  publication remains blocked on candidate checks and verified rollout. No version bump or deployment was performed.

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
pending access as recorded above. The next planned release is the 0.5.0 Git
workflow, followed by the 0.6.0 tester rework. The successful patch release does
not validate either scope or native tester installation. Historical version
targets in the records below reflect the roadmap at the time.

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
