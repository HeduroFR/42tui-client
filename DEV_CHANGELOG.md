# Development changelog

Latest release: **0.5.2** ([`v0.5.2`](https://github.com/HeduroFR/42tui-client/releases/tag/v0.5.2)).
Package version: **0.5.2**.
Suggested next release: **none**. No unreleased product changes.
The tester workspace rework remains planned for 0.6.0; unfinished Git design
work remains in [TODO.md](TODO.md). Plans alone do not justify publication.

This file tracks implemented changes since the latest successful release. Keep
published notes in [CHANGELOG.md](CHANGELOG.md). See
[distribution operations](docs/distribution.md#development-changelog).

## Changes since 0.5.2

No unreleased changes.

## Verified publication · 2026-10-29

- [PR #44](https://github.com/HeduroFR/42tui-client/pull/44) integrates the editor
  Git recovery review, colored diff, dev/vog sources and ancestry guidance,
  confirmed action/output modals, one-row buttons, masked SSH authentication,
  operation-scoped passphrase reuse and five-minute unchanged-state cache.
  User confirmed native workflow/cache testing works and authorized publication.
  Authoritative version and English release notes match v0.5.2. Tag points to
  reviewed main `e1207b162459a59f8cce45a59f8d42cdd2fe78f0`; the merged tree is
  identical to candidate `778fa9800478ff2ce286e397cb62a71135ed040c`.
- All 21 [PR checks](https://github.com/HeduroFR/42tui-client/actions/runs/40825742900)
  passed on their first attempt. Local projects scope: 177 passed; all 926 tests
  have exactly one regression-scope owner. Candidate wheel/sdist build, package
  validation and clean-wheel full-app Catppuccin/real encrypted-key checks passed.
- [Release run 40826211920](https://github.com/HeduroFR/42tui-client/actions/runs/40826211920)
  succeeded on attempt 4. All project/platform/package/container checks passed
  on attempt 1. Accounts passed on attempt 3 after two different unchanged UI
  timing failures: cursus refresh checked before asynchronous completion, then
  onboarding advance checked before its next step. Both failed tests passed in
  focused clean-wheel checks and other attempts. Retry only the failed accounts
  scope, without changing the tag, disabling tests or rebuilding artifacts.
- PyPI published on attempt 3. GitHub publication needed attempt 4 because the
  just-created draft was temporarily invisible to lookup. Reuse the original
  artifacts; do not rebuild or republish PyPI. GitHub published at
  `2026-10-29T06:10:15Z`. All seven release assets and SHA256SUMS verified;
  wheel and sdist downloads on GitHub/PyPI match original CI bytes. SHA-256:
  wheel `a558ac8f4ca92dce514c3f7a3cd9f5046565a715fb35139ca2cbb61512286761`;
  sdist `e6e53740685fe9e75ae0e5329c49aeb09e1772f4c0bb2a6068c25f3f1c430cf6`.
- Actual unpinned `42tui update` upgraded a disposable PyPI 0.5.1 installation
  to 0.5.2, installed all four commands and preserved a local-data marker. The
  first update retained 0.5.1 due to index/cache propagation; clear only the
  disposable package cache and retry successfully. Version-specific PyPI metadata
  independently confirms 0.5.2. Published installers match the source tree.
- No API, schema, backend dependency, hosted installer or shell configuration
  changes. Existing supported peer contracts remain unchanged; this unrelated
  client-only fix needs no new backend rollout. No new live API/campus Vogsphere
  or Windows askpass validation was performed. Keep the known accounts UI timing
  limitation visible; synthetic tests do not establish campus authentication.
- Reset shipped entries only after GitHub/PyPI, artifact and update verification.
  This documentation follow-up needs no package release. Checks: publication
  receipts, versions, links, artifact hashes and whitespace reviewed. Branch
  `docs/verified-0.5.2-publication`; commit/PR pending.
