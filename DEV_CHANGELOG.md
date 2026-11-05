# Development changelog

Latest published release: **0.7.1** ([`v0.7.1`](https://github.com/HeduroFR/42tui-client/releases/tag/v0.7.1)),
published and verified on GitHub and PyPI on 2026-11-05.
Package version: **0.7.2** (prepared; not published).
Suggested next release: **0.7.2 (patch)** for automatic printf/GNL bonus testing,
project-specific results, compatible tester updates and clearer tester diagnostics.
Worth preparing; not ready to publish before review and PR CI.

## Changes since 0.7.1

- 2026-11-05: Update all 14 Germinette catalog approvals to tester branch
  `feat/legacy-json-report` commit `f42c6b769ac064ed35d67571ac203858cc9a048e`.
  Preserve compatibility fingerprints and bundled offline fallback. Patch impact;
  no backend or API change. All 95 testers-core tests pass. Real Linux arm64
  Docker smoke checks pass for modules 00, 05 bis, 06 bis and A-Maze-ing, with
  synthetic fixtures preserved. The original PR's accounts-ui job failed during
  modal mounting; its failing test passes locally. Fresh PR CI and amd64 tester
  validation remain required before merge. Future branch commits still require
  catalog approval; the client does not automatically trust arbitrary branch heads.

- 2026-11-05: Add independent compatible updates for bundled testers before runs.
  A fixed HTTPS catalog on reviewed client `main` can approve exact commit SHAs
  for fingerprints covering each bundled definition and its recipe/patch bytes.
  It cannot change repositories, commands, execution modes or result readers.
  Custom overrides remain pinned. Bound metadata size/time, cache valid checks
  atomically for one hour and retain cached/bundled revisions on update-check
  failures. Record the selected revision and retain the updated catalog for image
  inspection/removal and later runs. Initial approvals match existing pins; no
  new upstream revision is claimed validated. Wire the four manual smoke scripts
  to the local candidate catalog, so existing amd64/ARM Docker PR CI validates
  approved refs. Native validation remains an explicit platform workflow.
  User-requested 0.7.2 patch preparation; no backend/API or dependency change.
  Reference: `fix/printf-bonus-detection` (uncommitted). All 95 `testers-core`
  checks pass, including 11 update tests for strict schema, compatibility, custom
  pins, bounded HTTP, offline fallback, cache failures and approval coverage.
  All 27 `testers-ui` checks and 11 focused release/scope/fixture checks pass.
  Version/notes check, installer digests, installer shell syntax, regression scope
  ownership and new French/Spanish messages pass. Built the 0.7.2 wheel/sdist
  offline using cached build dependencies and a temporary uv cache. Package
  contents, installed entry points/resources, exact updater source bytes and
  installed compatibility fingerprints pass. New updater/test-module lint and
  diff whitespace checks pass; Graphify code graph refreshed. Real Docker/native platform smoke
  checks and hosted PR CI were not rerun here. Live GitHub/PyPI checks are
  unavailable in this network-restricted environment; version availability,
  reviewed-main catalog availability, PR CI and publication remain unverified.
  Preserve all pending entries until a separately authorized release succeeds.

- 2026-11-05: Finish project-specific tester results, retry state and log/output
  actions keyed by project, local folder and tester. Capture that identity through
  setup approval and reruns so changing selection cannot assign another project's
  result. Preserve older results' log links after replacing the live workspace.
  Patch impact; no persistence, backend/API or version change. Reference:
  `fix/printf-bonus-detection` (uncommitted). Initial isolation verification passes
  all 26 tester UI tests, including shared tester IDs, folder changes, cancellation,
  setup approval and reruns after selection changes.

- 2026-11-05: Record mandatory-only or mandatory-plus-bonus scope from the disposable
  printf/GNL project copy and show it in result cards, workspace summaries and logs,
  with French/Spanish translations. Unknown/custom tester scopes stay unlabelled;
  missing reports retain their selected scope without implying passing tests.
  Patch impact; no tester-image, report-format, backend/API or version change.
  Reference: `fix/printf-bonus-detection` (uncommitted). Separate runner and UI
  checks pass for bonus layouts, explicit printf flags, source changes during a run,
  result cards and workspace/log translations in all three supported languages.

- 2026-11-05: Distinguish preparation errors from execution failures and show the
  stage plus original diagnostic in the workspace header and transcript. Docker
  and native project-copy failures add read-permission/disk-space guidance while
  preserving the original exception. Add French/Spanish copy and update the tester
  guide. Patch impact; no backend/API or version change. Reference:
  `fix/printf-bonus-detection` (uncommitted). Separate error checks pass for copy and
  build failures, launch errors, retry/busy cleanup and localized workspace/log
  diagnostics. All 84 `testers-core` and 26 `testers-ui` regressions pass; localized
  copy-error template checks and diff whitespace checks pass. Graphify code graph
  refreshed. Review, PR CI and release-candidate checks block publication.
  Real Docker and real student implementations were not rerun for these changes.

- 2026-11-05: Detect standard GNL bonus sources at the root or inside `bonus/` and
  run the mandatory and bonus suites together, preserving original project files.
  Apply a bundled patch to the exact pinned tester during image build, include it
  in the image identity/package checks, and use the existing child crash/timeout
  reporting for bonus tests. Incomplete bonus sources cannot produce a passing
  mandatory-only report. Extend the real-container smoke checks for both layouts,
  failures, early exits, hangs, crashes and missing bonus sources. Patch impact;
  no backend/API, upstream pin or package-version change. Reference:
  `fix/printf-bonus-detection` (uncommitted). All 82 `testers-core` regressions and
  ten real Linux arm64 Docker smoke cases pass: 222 mandatory and 501 combined
  checks for passing fixtures; wrong-output, early-exit, timeout, crash and missing
  bonus sources cannot pass. Original fixture files remain unchanged. Wheel/sdist
  resource checks (including exact patch bytes), installer digests, shell syntax
  and diff whitespace checks pass; Graphify updated. Validation used temporary
  Buildx/uv state because this sandbox cannot write their default cache folders.
  Intel Docker and the real student implementation were not tested. Review and
  PR CI remain publication blockers.

- 2026-11-05: Detect a root-level `bonus/` directory in the disposable Supra printf
  project copy and append `--bonus`, so the existing tester builds and tests both
  mandatory and bonus behavior. Preserve explicit `--bonus` without duplication;
  missing directories, regular files and other testers keep their existing command.
  Document detection and combined report counts. Patch impact; no backend/API,
  tester image or package-version change. Reference: `952a12d`
  (`fix/printf-bonus-detection`). All 75 focused `test_testers.py` tests pass. Real Linux arm64
  Docker checks pass with 503 mandatory and 1,629 mandatory-plus-bonus comparisons;
  the synthetic wrapper's forbidden `vprintf` adds one expected failure per run.
  Verified the bonus build marker, detection log and unchanged source fixture.
  Diff whitespace checks pass; Graphify updated. Intel Docker and the real student
  implementation were not run. Review and PR CI remain publication blockers.

## Release record

- 2026-11-05: Publish stable patch 0.7.1 from reviewed main `2e870c6`, following
  [PR #61](https://github.com/HeduroFR/42tui-client/pull/61) with all 33 checks
  successful. Tag `v0.7.1` points to that exact commit. All 36 jobs in the
  [publication workflow](https://github.com/HeduroFR/42tui-client/actions/runs/42069882207)
  pass, including PyPI and GitHub release publication. No API change or backend
  rollout was required.
- 2026-11-05: Verify both PyPI distribution SHA-256 hashes against the original
  release CI artifacts, all seven GitHub assets and SHA256SUMS, installer bytes,
  stable/non-draft release flags and the exact CHANGELOG.md release notes. Install
  `ft-tui==0.7.1` from PyPI into an isolated Python 3.12 environment and pass the
  installed entry-point, version and package-resource smoke checks. Published
  distributions are not yanked. The version JSON endpoint initially returned a
  cached 404; an uncached request confirmed both published distributions.
- 2026-11-05: Reset development entries included in the verified release and
  update the distribution guide's stable baseline to 0.7.1. Published user-facing
  notes remain in CHANGELOG.md; no later development entries existed to retain.
  Documentation only; no release required. Reference: `docs/release-0.7.1-record`.
  Version and diff checks pass; no package, dependency, API or tag change.

Interactive oldest-supported Neovim and full LazyVim/SupraVIM setups were not
retested during publication. Isolated standard/Lazy.nvim startup checks passed
in release preparation; these do not replace interactive configuration coverage.
