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

The following roadmap documentation landed after the release candidate; it
requires no package release and remains pending implementation.

- 2026-10-29: Reconcile roadmap additions with current main for PR #45,
  preserving all pending 0.5.2 release work and future plans. Planning only;
  no additional release required. Checks: three-file roadmap diff, relative
  links and whitespace reviewed; runtime tests skipped for documentation only.

- 2026-10-29: Target priority backend data protection before or alongside 0.6.0:
  encrypted PostgreSQL storage/WAL, separately encrypted backups with protected
  keys and an isolated recovery drill, certificate/hostname-verified database
  TLS across production callers, and selective private-payload encryption after
  assessment. Add deployment, migration/recovery and compatibility acceptance
  criteria; distinguish tester-only validation from backend security rollout.
  Planning only; no release required and no protection implemented or deployed.
  Checks: roadmap/tracker consistency, relative links and diff/whitespace review;
  runtime, production encryption/TLS and recovery checks skipped. Branch:
  `docs/roadmap-additions`; commit/PR pending.

- 2026-10-29: Extend the future workload-planner roadmap with a pace-based
  milestone calendar and suggested project submission dates, targeted after
  0.10.0 with detailed design deferred. Distinguish official deadlines from
  estimates and flag infeasible plans. Planning only; no release required.
  Checks: existing planner/agenda scope and diff/whitespace review; scheduling
  logic and pace/deadline sources not validated. Branch: `docs/roadmap-additions`;
  commit/PR pending.

- 2026-10-29: Schedule Intra event browsing and a personal agenda with upcoming
  evaluations for 0.7.0, user-selected reminders/change/cancellation notifications
  respecting DND for 0.8.0, and event participation plus club-event integration
  as later work. Record source/permission validation and reuse of existing
  calendar/evaluation behavior. Planning only; no release required. Checks:
  roadmap consistency and diff/whitespace review; live Intra capabilities and
  client/backend integration not validated. Branch: `docs/roadmap-additions`;
  commit/PR pending.

- 2026-10-29: Add optional Obsidian integration to Further updates, complementing
  existing dev logs/notes with project-vault links, Markdown export, explicit
  conflict-reviewed import and a possible daily summary. Preserve built-in notes
  and reuse planned export/backup work. Planning only; no release required.
  Checks: existing note storage/editor references, roadmap consistency and
  diff/whitespace review; Obsidian integration/runtime behavior not verified.
  Branch: `docs/roadmap-additions`; commit/PR pending.

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
  Retain the later planning-only entries from PR #45. This documentation
  follow-up needs no package release. Checks: publication
  receipts, versions, links, artifact hashes and whitespace reviewed. Branch
  `docs/verified-0.5.2-publication`; commit/PR pending.
