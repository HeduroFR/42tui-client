# Development changelog

Latest release: **0.5.0** ([`v0.5.0`](https://github.com/HeduroFR/42tui-client/releases/tag/v0.5.0)).
Package version: **0.5.0**.
Suggested next release: **none**. No unreleased product changes.
The tester workspace rework remains planned for 0.6.0; remaining Git design tasks
are tracked in [TODO.md](TODO.md). Plans alone do not justify publication.

This file tracks implemented changes since the latest successful release. Keep
published notes in [CHANGELOG.md](CHANGELOG.md). See
[distribution operations](docs/distribution.md#development-changelog).

## Changes since 0.5.0

No unreleased changes.

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
  exercised. Hosted installer deployment remains pending access as previously
  recorded; package publication does not establish hosted installer rollout.
- Reset included development entries only after publication/artifact/update
  verification. Keep user-facing notes, pending Git design and tester rework in
  CHANGELOG.md/TODO.md. Documentation checks: release evidence, relative links,
  version consistency and whitespace reviewed; no runtime changes or additional
  package release required. Branch: `docs/verified-0.5.0-publication`; PR pending.
