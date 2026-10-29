# Development changelog

Latest release: **0.5.1** ([`v0.5.1`](https://github.com/HeduroFR/42tui-client/releases/tag/v0.5.1)).
Package version: **0.5.1**.
Suggested next release: **0.5.2** (patch), worth preparing for the editor recovery
fix below. Not ready to publish: PR review/CI and a native reproduction check
remain; package version stays 0.5.1.
The tester workspace rework remains planned for 0.6.0; unfinished Git design
work remains in [TODO.md](TODO.md). Plans alone do not justify publication.

This file tracks implemented changes since the latest successful release. Keep
published notes in [CHANGELOG.md](CHANGELOG.md). See
[distribution operations](docs/distribution.md#development-changelog).

## Changes since 0.5.1

- 2026-10-29: Route OpenSSH askpass requests during editor recovery to a masked
  modal, preserving SSH configuration/agent behavior and keeping answers in
  memory. Use a temporary helper plus an authenticated loopback bridge scoped to
  one checkout operation; no passphrase in files, command arguments or environment.
  Show loading before starting remote access, support cancellation and suppress
  late editor launches, including Vogsphere warning fallback. Clear input on
  submission/cancel and remove the helper on completion. Patch impact for 0.5.2;
  branch `fix/editor-git-review`; local follow-up to `c23fb85`, not pushed/tagged.
  Checks: real disposable encrypted OpenSSH key unlock and bridge cancellation/
  authentication (also passed under a real pseudo-terminal), masked UI submit/
  cancel and delayed-recovery cancellation. Final Git suite 45 passed; dialog/
  layout/locales suite 14 passed; architecture 9 passed; all 914 tests have one
  regression-scope owner; locale and whitespace checks passed. User/campus and
  Windows askpass integration remain unverified. No release or API/backend change.

- 2026-10-29: Replace the editor-blocking history mismatch notification with an
  English/French/Spanish Git review modal: fetched snapshot, local branch/HEAD,
  working status and read-only tracked-file diff. Explicit Open local files or
  Cancel leaves local history/index/files untouched. Preserve strict setup,
  pull/push and unrelated configuration failures; unresolved recovery is not
  cached. Tests cover unrelated/unborn histories, staged/unstaged/untracked
  preservation, 80×24 modal actions and explicit editor approval. Patch impact;
  branch `fix/editor-git-review`; commit/PR pending. Checks: projects scope
  159 passed; final Git suite 43 passed; final dialog/layout/locales suite 12
  passed; architecture boundaries 9 passed; scope ownership and whitespace
  passed. Live campus/native editor reproduction and PR CI remain unverified.
  User requests hands-on testing before any new tag; no backend/API change,
  version bump or release performed.

## Verified publication · 2026-10-29

- [PR #42](https://github.com/HeduroFR/42tui-client/pull/42) integrates branch-aware
  Vogsphere recovery/push, reviewed fast-forward-only `42git pull dev|vog|all`,
  the website root redirect and English contributor/release guidance. Tag merged
  main `3343a29b69c7cccd0d462bb0c597688eaf04b97a` as v0.5.1 after the user resumed
  the release previously stopped before tagging. Authoritative version and notes
  match. All 21 PR checks passed in run 40812785438; unchanged onboarding UI tests
  required one accounts-scope retry. Release tests passed on their first attempt.
- [Release run 40814022012](https://github.com/HeduroFR/42tui-client/actions/runs/40814022012)
  succeeded on attempt 2. PyPI publication succeeded on attempt 1; retry only the
  GitHub publisher after its new draft was briefly invisible to lookup. Reuse the
  original artifacts without rebuilding, replacing the tag or republishing PyPI.
  GitHub published at 2026-10-29T03:53:16Z. All seven GitHub assets/checksums and
  both PyPI downloads are verified; distributions match original CI artifacts
  byte for byte. Wheel SHA-256:
  `0691d26549080d9f807fa2c64801832346c3eb78568df8f17438a57acbcc1b2d`;
  sdist: `514160a5706ad80330364080608943b92f72450fdbd917d394f96d11a1e72b7d`.
- Local Git suite: 41 passed; CLI: six passed; locales: two passed; release
  validation: two passed. Broader local project scope: 153 passed, followed by
  two added regressions in the final Git rerun. All 904 tests have exactly one
  scope owner; full regression/platform/package/container checks passed in release
  CI, with optional integrations skipped. Clean archive wheel/sdist, installed
  CLI/resources and pull help passed. Unrelated untracked duplicate files were
  preserved and excluded from the archive.
- Actual unpinned `42tui update` upgraded a disposable PyPI 0.5.0 installation to
  0.5.1, installed all four commands and preserved local data. Initial index/cache
  propagation still selected 0.5.0; clear only the disposable cache and retry
  successfully. Version-specific PyPI metadata confirms 0.5.1; the project metadata
  endpoint briefly retained the old version. Published-package smoke also uses
  disposable SQLite and real Git remotes to verify subfolder project resolution,
  cancellation, pull-all fast-forward from main and preservation of untracked work.
- Exact merged-revision [compatibility run 40813755591](https://github.com/HeduroFR/42tui-backend/actions/runs/40813755591)
  passed candidate, oldest supported client (0.4.0, `bb5caff`) and fallback pairs
  against backend `f6d31cd482defe22f6c7c3421ee10cb0791c131c`. This synthetic
  friend-preview scenario is partial API coverage; no API/backend/schema change
  or new backend rollout was required by this client-only patch.
- Website rollout from reviewed main 3343a29 was verified before tagging: `/`
  and `/github` return the GitHub HTTP 301, `/discord` returns the expected invite,
  and all four hosted installer/uninstaller files match main byte for byte.
  No new hosting change was needed for package publication.
- Live Vogsphere/campus credentials, native pipx/Windows and full live API coverage
  were not exercised. Use the documented remote branch review and manual conflict
  resolution; never assume synthetic tests establish live campus authentication.
  Retain the known onboarding test timing limitation noted above.
- Reset shipped entries only after GitHub/PyPI, artifact and update verification.
  Keep release notes and future roadmap tasks. This documentation follow-up needs
  no new package release. Checks: release evidence, version consistency, links
  and whitespace reviewed. Branch: `docs/verified-0.5.1-publication`; PR pending.
