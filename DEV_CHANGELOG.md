# Development changelog

Latest release: **0.5.0** ([`v0.5.0`](https://github.com/HeduroFR/42tui-client/releases/tag/v0.5.0)).
Package version: **0.5.1** (candidate; not published).
Suggested next release: **0.5.1**, as requested for the Vogsphere branch fix,
reviewed fast-forward pull commands and website root redirect. Preparation, PR
and merge are authorized; stop before creating or pushing any release tag.
Candidate CI and review are tracked in PR #42. Latest verified baseline stays 0.5.0;
no release tag or publication is authorized for this task.
The tester workspace rework remains planned for 0.6.0; remaining Git design tasks
are tracked in [TODO.md](TODO.md). Plans alone do not justify publication.

This file tracks implemented changes since the latest successful release. Keep
published notes in [CHANGELOG.md](CHANGELOG.md). See
[distribution operations](docs/distribution.md#development-changelog).

## Changes since 0.5.0

- **2026-10-29 · patch (requested 0.5.1) · Remote branches and pull:** share
  advertised-default/sole-branch selection across checkout recovery and Vogsphere
  push; reject ambiguity and recheck destination branch after review. An empty
  Vogsphere remote uses the reviewed local branch. Add CLI pull dev/vog/all with
  fetched commit review, clean-worktree/operation checks, one fast-forward after
  all selected sources are validated, ignored-file protection and review drift
  checks. Never automatically stash, reset, switch branches or merge divergent
  histories. Update TUI copy, translations, commands, guide and regressions.
  Also redirect the website root to GitHub, extend the existing Nginx CI assertion,
  and make the contributor/release template headings English. Set package/version
  notes to 0.5.1 while retaining the verified 0.5.0 publication baseline. Branch:
  `fix/git-remote-branches`; PR #42. Checks: branch regressions reproduced
  the hard-coded-master failure before the fix. Final disposable Git suite: 41
  passed; CLI: six passed; locale: two passed; release validation: two passed.
  Version/tag consistency, non-overlapping regression ownership and wheel/sdist
  contents passed. Broader project scope: 153 passed; final focused Git rerun
  includes two additional branch/recovery regressions (41 passed). Final ownership
  check covers all 904 tests. Clean committed archive wheel/sdist contents and
  installed CLI/resources/42git pull help passed; unrelated duplicate files are
  excluded. Full CI is tracked in PR #42, including the live Nginx container
  root-redirect assertion. No live Vogsphere credentials or user repositories
  were used.
  No API/backend/schema changes.
  Stop before release tag/publication per user instruction. Website rollout is
  separate from package publication; no rollout claimed here.

- **2026-10-29 · no package release required · Discord website redirect:** add
  exact Nginx `/discord` HTTP 301 to the maintainer-provided invite
  `https://discord.gg/QrRBcK5MeP`, matching `/github`. Extend the existing
  distribution-container CI assertion and document the destination. Website
  deployment required; no Python runtime/version change. Branch:
  `fix/discord-redirect`; PR #40. Initial container CI passed the exact redirect
  assertion; diff/whitespace and destination agreement reviewed. Local Docker
  test unavailable because the daemon socket is absent. Retain verified 0.5.0
  publication baseline from PR #39. PR #40 merged as `fb22488` after all
  21 CI checks passed in run 40791484292. Deploy the existing Installer service
  through Safari/Dokploy from main. Public checks confirm `/discord` returns
  `301 https://discord.gg/QrRBcK5MeP` and `/github` retains its 301 destination.
  All four hosted installer/uninstaller files match main byte for byte, completing
  the previously pending coordinated installer rollout. Maintainer also confirmed
  the Discord link works. Record deployment in this documentation-only follow-up;
  no new Python release is needed.


## Verified publication · 2026-10-29

- Integrate the pushed Git workflow and release metadata through
  [PR #38](https://github.com/HeduroFR/42tui-client/pull/38). Tag exact reviewed
  main `32ec455b041845890015d07d5c9dc068839c13a3` as v0.5.0 after all 21 PR
  checks passed. All 888 regression tests ran: 882 passed, six optional
  integrations skipped. Local project scope (139), account UI (30), locales
  (two), installer unit tests (23), clean archive builds/package contents,
  installed entry points/resources, installer hashes/syntax and disposable
  fresh/repeat/exact-version install/uninstall passed. Preserve untracked
  duplicate files outside the release archive.
- [Release run 40790223898](https://github.com/HeduroFR/42tui-client/actions/runs/40790223898)
  succeeded on attempt 1, including all regression/platform checks and both
  publishers. GitHub published at 2026-10-28T23:56:44Z. All seven GitHub assets
  and checksums are verified; both PyPI/GitHub distributions match original CI
  artifacts byte for byte. Wheel SHA-256:
  `05c665022af5fa91a08e40670870859777d8f9091d37f9e3f2c67bc2d42ec112`;
  sdist: `ab13421ee322c3197741c9c3be9269a6c139510556d5021480f533b2eabbdd4a`.
- The real unpinned `42tui update` upgraded a disposable PyPI 0.4.4 installation
  to 0.5.0, installed all four executables including 42git, preserved a local-data
  sentinel and passed installed CLI/resource smoke. Initial index propagation
  selected 0.4.4; retry succeeded. The version-specific PyPI JSON endpoint briefly
  returned 404; current project metadata and both downloaded package hashes
  verified 0.5.0. No tag/artifact was replaced or republished.
- Exact merged-candidate [compatibility run 40790011375](https://github.com/HeduroFR/42tui-backend/actions/runs/40790011375)
  passed candidate, oldest supported client (0.4.0, `bb5caff`) and fallback pairs
  against backend `f6d31cd482defe22f6c7c3421ee10cb0791c131c`. This synthetic
  friend-preview scenario is partial API coverage, not live OAuth verification.
- Backend [PR #8](https://github.com/HeduroFR/42tui-backend/pull/8) adds the
  requested 10-second close attempt with hashed CSP and manual-close fallback.
  Backend CI/typecheck passed; local suite: 486 passed, 34 optional integrations
  skipped. Deploy through existing Safari/Dokploy session before client tagging.
  Successful build image ID:
  `sha256:3f75bac77fe71c960600dbcb5876a95095eef9a145a2efbdaa0d381fd27790ae`.
  API-container source hash matches the merged page; 19 synthetic OAuth route
  tests (117 assertions), PostgreSQL SELECT 1, Redis PING and configured-port
  API health passed. Public API health passed. Compatibility/deployment evidence
  checker accepted the exact pair. No migration or credential changes.
- Native Vogsphere and Linux/macOS tester validation were confirmed by the
  maintainer, not independently rerun. Local Chromium launch was blocked by
  macOS sandbox permissions; browser tab-closing restrictions still apply.
  Native pipx/Windows, live OAuth/provider writes and full API coverage were not
  exercised. Hosted installer deployment was still pending at package publication;
  the subsequent verified rollout is recorded in the Discord redirect entry above.
- Reset included development entries only after publication/artifact/update
  verification. Keep user-facing notes, pending Git design and tester rework in
  CHANGELOG.md/TODO.md. Documentation checks: release evidence, relative links,
  version consistency and whitespace reviewed; no runtime changes or additional
  package release required. Branch: `docs/verified-0.5.0-publication`; PR pending.
