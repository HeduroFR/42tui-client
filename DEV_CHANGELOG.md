# Development changelog

Latest release: **0.4.3** ([`v0.4.3`](https://github.com/HeduroFR/42tui-client/releases/tag/v0.4.3)).
Package version: **0.4.4**, prepared but not published.
Suggested next release: **0.4.4** (patch), for pre-launch automatic updates,
unsaved-note protection and timer safety. This isolated candidate starts at
published v0.4.3; main's unreleased minor tester work is excluded.

## Changes since 0.4.3

- **2026-10-28 · patch · Updates before launch:** include [PR #26](https://github.com/HeduroFR/42tui-client/pull/26)
  (`30869d8`). Install managed stable updates before loading OAuth/TUI code and
  restart into the installed entry point. Preserve offline/failure fallback,
  opt-out, pin/development guards, update locks and the one-launch restart guard.
  Background discoveries wait until the next launch. Include settings, README,
  French/Spanish copy and focused regressions.
- **2026-10-28 · patch · Note loss and timer safety:** include [PR #27](https://github.com/HeduroFR/42tui-client/pull/27).
  Protect dirty notes with Save/Discard/Cancel across selection, new-note actions,
  links and catalog refreshes, retaining project ownership and failed-save drafts. Translate operational
  storage failures at the adapter boundary; preserve the selected note and editor
  with localized retry guidance.
  Stop/guard dashboard activity callbacks during shutdown, including after awaits.
  Serialize SQLite manual start/stop/toggle transitions before their active-timer
  reads, including sessions with an existing SQLAlchemy read transaction. Preserve
  duration/switch accounting and history; existing duplicate active rows are not
  automatically repaired. Include French/Spanish modal copy and regressions.
- **2026-10-28 · release preparation · 0.4.4:** prepare the package version and
  matching release notes on `fix/release-0.4.4-candidate`. No API, backend,
  schema, dependency, installer-hosting or tester changes. No process documents.
  Baseline remains 0.4.3 until publication is verified. No tag/publication.

- **2026-10-28 · documentation · Project workflow roadmap:** integrate the
  planning content from `docs/project-workflow-roadmap` (`e5504f9`), preserving
  the verified 0.4.3 baseline and this isolated patch scope. Include urgent Git
  recovery/push workflows and proposed 42git, 0.6.0 dashboard/GitHub/Discord,
  0.7.0 notifications/presence, 0.8.0 profiles/clubs and later initiatives.
  Planning only; none of those features is implemented by 0.4.4. Review of links,
  documentation diff and whitespace passed. Candidate revision changes, so fresh
  exact-revision compatibility and archive/package checks are required.

## Validation and release readiness

The normal fix branch passed 43 focused UI/service/architecture/locale tests;
three targeted regressions failed before implementation. Scope ownership and
changed runtime undefined/unused-name checks passed. These results do not replace
validation of this isolated candidate. Initial version, wheel/sdist content,
installer-helper digest and POSIX shell syntax checks passed. All 824 candidate
tests have exactly one scope owner. Exact-candidate package, full regressions,
platform and main-ancestry validation remain required before publication.

This client-only patch needs no new backend capability or deployment. The oldest
supported client remains 0.4.0; existing synthetic friend-preview compatibility
coverage does not cover the whole API or live OAuth/Intra writes.

A 0.4.4 patch is worth preparing for these fixes. Main's unreleased tester work
still warrants 0.5.0 separately. The user will review the exact candidate before
any tag is pushed; no tag or publication is authorized by this preparation.
