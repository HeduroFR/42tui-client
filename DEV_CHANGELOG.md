# Development changelog

Latest release: **0.5.1** ([`v0.5.1`](https://github.com/HeduroFR/42tui-client/releases/tag/v0.5.1)).
Package version: **0.5.1**.
Suggested next release: **none**. No unreleased product changes.
The tester workspace rework remains planned for 0.6.0; unfinished Git design
work remains in [TODO.md](TODO.md). Plans alone do not justify publication.

This file tracks implemented changes since the latest successful release. Keep
published notes in [CHANGELOG.md](CHANGELOG.md). See
[distribution operations](docs/distribution.md#development-changelog).

## Changes since 0.5.1

- 2026-10-29: Add unversioned club-game proposals to Further updates: in-TUI
  chess with Elo/history, babyfoot match scoring and rankings, and a mobile
  companion web app for live scoring. Record club-rework dependency, separate
  ratings, result confirmation/correction, permissions and reconnect/concurrency
  requirements. Extend the later scope with opt-in inter-campus rankings based
  on confirmed local games/equipment, preserving local rankings and requiring
  comparable rules/rating pools. Planning only; no release required. Checks: roadmap consistency
  and diff/whitespace review; gameplay, rating rules and web/backend feasibility
  not validated. Branch: `docs/roadmap-additions`; commit/PR pending.

- 2026-10-29: Add an optional integrated music player to Further updates,
  targeting provider selection for Spotify, Deezer, SoundCloud and YouTube through
  reusable open-source projects. Require license/provider feasibility review,
  guided installation and platform validation before committing to support.
  Planning only; no release required. Checks: roadmap placement and diff/whitespace
  review; project licenses, provider capabilities and playback not verified.
  Branch: `docs/roadmap-additions`; commit/PR pending.

- 2026-10-29: Add six selected unversioned further updates: project readiness,
  opt-in peer study matching, workload planning, exam practice, integration
  diagnostics and data export/backup. Record reuse, privacy and data-preservation
  requirements; rename the future-work heading to cover the expanded scope.
  Planning only; no release required. Checks: roadmap consistency and
  diff/whitespace review; runtime tests skipped. Branch: `docs/roadmap-additions`;
  commit/PR pending.

- 2026-10-29: Add unversioned future roadmap goals for a stable all-campus
  release beyond Angouleme-specific behavior and support for specific curricula,
  including Piscine Discovery and seconde work-experience placements. Record
  capability/data coverage, context isolation and representative validation as
  requirements, not delivered support. Planning only; no release required.
  Checks: roadmap placement, consistency and diff/whitespace review; runtime and
  cross-campus/programme checks skipped. Branch: `docs/discord-rich-presence-roadmap`;
  commit/PR pending.

- 2026-10-29: Extend the 0.7.0 roadmap with stable time-tracking integrations
  and installation/update/removal for Vim, Neovim, VS Code and Zed. Replace the
  planned dashboard Cluster Map card rework with a campus log-time heatmap,
  distinct from coding time, retaining the dedicated map view. Planning only;
  no release required. Checks: current integration documentation/source references,
  roadmap consistency and diff/whitespace review. Runtime/editor and session-data
  validation remain pending. Branch: `docs/discord-rich-presence-roadmap`;
  commit/PR pending.

- 2026-10-29: Add opt-in Discord Rich Presence to the 0.8.0 roadmap, alongside
  notifications and presence, with navigation activity, privacy, lifecycle and
  platform-validation requirements. Planning only; no feature implemented and
  no release required. Checks: roadmap placement and diff/whitespace review;
  runtime tests skipped for this documentation-only change. Branch:
  `docs/discord-rich-presence-roadmap`; commit/PR pending.
- 2026-10-29: Expand the 0.7.0 Settings roadmap from Curriculum/Appearance
  simplification to a full interface rework, preserving preferences and validation
  with clear save feedback and accessibility/locale checks. Planning only; no
  release required. Checks: existing Settings structure, roadmap and diff/whitespace
  review; runtime tests skipped. Branch: `docs/discord-rich-presence-roadmap`;
  commit/PR pending.

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
