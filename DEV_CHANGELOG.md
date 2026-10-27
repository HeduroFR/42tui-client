# Development changelog

Latest release: **0.4.1** ([`v0.4.1`](https://github.com/HeduroFR/42tui-client/releases/tag/v0.4.1)).
Package version: **0.4.2**, prepared but not published.
Suggested next release: **0.4.2** (patch), for update discovery, exam resumption
and corrected onboarding instructions. This isolated branch starts at v0.4.1;
later tester features on main remain outside this patch. Publication requires
separate authorization after exact-candidate validation and main integration.

## Changes since 0.4.1

- **2026-10-28 · patch · Automatic updates:** carry only the update policy/view,
  settings hook and tests from `ee60aa2` (PR #18). Check at every startup, every
  12 hours while running, and immediately on re-enable. Preserve opt-out and
  managed/development/pinned safeguards and installation after normal exit.
- **2026-10-28 · patch · Continue working:** exclude exams before active/recent/
  selected/fallback resumption selection. Reuse the catalog kind classifier so
  exam-rank slugs in older snapshots are recognized. Catalog and curriculum
  progress still include exams. The regression failed all eight scenarios before
  the fix. No user data, API contract or backend behavior changes.
- **2026-10-28 · patch · First-run documentation:** replace the README's obsolete
  connection bypass instructions with required initial connection and continued
  offline access to saved projects/notes after setup.
- **2026-10-28 · release preparation · 0.4.2:** prepare package version, matching
  release notes and a checklist for only these three fixes. Reference:
  `fix/release-0.4.2`. No tag, publication or deployment performed.

## Validation and release readiness

- Dashboard resumption regression failed eight scenarios before editing; all
  28 dashboard and 70 installation-updates scope tests now pass. Independent
  read-only review found no substantive issues. Version check v0.4.2 and diff
  whitespace checks passed. Clean package build validation remains pending.
- Live OAuth, native platform checks and real Intra writes are not exercised.
- Review, CI/main integration and exact-candidate compatibility remain pending.
  The patch is worth preparing, but is not yet ready to publish.
