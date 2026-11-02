# Development changelog

Latest release: **0.6.2** ([`v0.6.2`](https://github.com/HeduroFR/42tui-client/releases/tag/v0.6.2)).
Package version: **0.6.2**.
Suggested next release: **0.7.0** (minor), for the Agenda redesign, campus exams,
Correction Slots loading and the accumulated interface and loading work. Final
candidate checks, compatibility, backend deployment and publication validation
remain outstanding.

This file tracks implemented changes since the latest successful release. Keep
published notes in [CHANGELOG.md](CHANGELOG.md). See
[distribution operations](docs/distribution.md#development-changelog).

## Changes since 0.6.2

- 2026-11-02: Reset the development changelog to the verified 0.6.2 publication
  baseline after confirming the GitHub release, tag and PyPI version, and removed
  the 17 entries included in 0.6.1/0.6.2. Documentation only; no release impact.
  Remaining 0.7.0 candidate validation is unchanged.


- 2026-11-01: Defer Correction Slots prefetch until the view is mounted and
  recover invalidated reads without waiting for a timeout. The live trace showed
  the initial read being invalidated before provider dispatch; Correction
  Slots UI tests passed; the user confirmed prompt loading in a live session.
  Patch impact within 0.7.0; release validation remains pending.

- 2026-11-01: Add pulsing Correction Slots calendar placeholders without hiding
  saved slots, and stagger Agenda and slot placeholders by day and hour. Patch
  impact within 0.7.0. All 89 corrections-scope tests passed; focused workspace
  and Agenda skeleton checks passed afterward. Live terminal and release
  validation remain outstanding.


- 2026-11-01: Extend Agenda loading cards across their columns and pulse them
  while loading, stopping the timer when data arrives. Show loading guidance
  instead of an empty-week message during the initial load. Patch impact within
  0.7.0; focused skeleton tests passed, including narrow/wide layouts and timer
  behavior. Live terminal and final release validation remain outstanding.


- 2026-11-01: Refine Agenda loading cards with inset, varied widths and short
  placeholder strokes that fit narrow and wide calendars. Patch impact within
  0.7.0. Focused skeleton tests passed; live terminal review and release
  validation remain outstanding.


- 2026-11-01: Replace the Agenda loading overlay with calendar placeholders and
  keep partial or cached results visible while sources load. Patch impact within
  0.7.0. All 33 staged Agenda tests and 87 working-tree corrections tests passed;
  live terminal and final release validation remain outstanding.


- 2026-11-01: Restore cached agenda rows during week changes and retry pending
  event/exam worker reads at the backend's requested interval, with a bounded
  retry count. Patch impact within 0.7.0. All 31 agenda tests passed; a local
  Postman HTTP simulation confirmed a pending exam followed by a successful
  retry. Live backend timing and final release validation remain outstanding.


- 2026-11-01: Shade past agenda calendar cells using the active theme while
  retaining event colors and the current-time marker. Patch impact within 0.7.0.
  Focused past/current/future rendering check passed; live terminal appearance
  and final release validation remain unverified.


- 2026-11-01: Dim past agenda days and half-hours and mark the current half-hour
  in empty cells, refreshing the display as time advances. Patch impact within
  0.7.0. All 28 agenda tests passed, including past, current and future rendering;
  live terminal and final release validation remain outstanding.


- 2026-11-01: Retry temporary agenda read failures once after the cache retry
  deadline and use the direct exam page for Intra links. Patch impact within
  0.7.0. Focused agenda checks cover initial transient failures and both links;
  live first-load behavior, links and release validation remain unverified.


- 2026-11-01: Keep agenda week navigation responsive during source reads, batch
  completed reads, avoid redraws for unchanged background refreshes and open events
  using their direct Intra URL. Patch impact within 0.7.0. The 26 agenda tests
  passed, including slow exam and direct-link checks; all 80 corrections-scope
  tests passed. Live source timing, event links, deployment and final candidate
  validation remain outstanding.


- 2026-11-01: Update the 0.7.0 roadmap with remaining integration, performance,
  editor and release work, and record the direct Intra event URL for the agenda
  action. Documentation only; no release required. Reviewed the roadmap against
  local branch and worktree records; live links, final CI and deployment remain
  unverified.

- 2026-10-31: Diagnose deployed campus-exams 403 responses and expose an explicit translated access-denied reason instead of only a generic stale source. Requires backend c1c43ab for same-token campus-filtered exam collection fallback and correct 403 propagation. Patch impact within 0.7.0; 22 agenda tests passed in the working checkout, and 17 passed against an isolated export of this staged patch, preserving concurrent unrelated work. Backend suite passed 536 tests with 38 environment-dependent skips and type-checking passed. Full client suite, deployment and live fallback success remain unverified; no separate release warranted.

- 2026-10-31: Redesign Agenda with event blocks, overlap lanes, theme colors, compact responsive navigation and readable Markdown details. Correct SelectCurrent clipping by limiting toolbar layout rules to their owning containers; test English/French/Spanish at narrow/wide sizes. Add campus exams and optional location/occupancy/project metadata, retaining zero counts and explicit unknown values. Manage on Intra opens the observed profile-v3 calendar; event writes require an ungranted profile scope and exam writes require Advanced tutor, so no subscription writes or scope expansion were added. Minor impact toward 0.7.0; 70 corrections/agenda tests and 14 architecture/navigation/layout tests passed, with 16 agenda tests and three exam-detail checks rerun after final UI adjustments. Synthetic 40/80/150-column previews inspected. Requires backend 9cdd26a or reviewed successor; deploy it first and verify the exact pair/live campus payloads before release. Full client suite, live subscription/link flow and release CI remain unverified. 0.7.0 remains worth preparing, not ready to publish.

- 2026-10-31: Remove My evaluations from tab composition and localization routing. Rework Agenda into a half-hour week timeline with a shared event/evaluation detail panel, role filters, overlap selection and narrow-terminal stacking. Clear visible rows immediately on account changes and retain dashboard/project-slot views. Minor impact toward 0.7.0; 10 agenda tests, nine architecture checks, four navigation tests and the focused full-app layout test passed in separate runs after correcting the navigation fixture for Agenda and scrollable tabs. Covers overlaps, midnight spans, DST folds, filtering and account clearing. Full suite and live Intra validation not rerun; no backend change or separate release needed for this UI iteration.

- 2026-10-31: Add a bottom margin to the project activity footer and use the primary variant for Set as finished. Patch impact within 0.7.0; nine project-activity UI tests and the focused project-layout test passed, covering footer space at wide/narrow sizes and the primary variant. Full suite not rerun; no separate release warranted.

- 2026-10-31: Gate project evaluation actions on fresh account/campus/project registration state, rename slot browsing to Subscribe to defense, and hide the fallback calendar toolbar/date range for unfinished projects. Patch impact within 0.7.0; 36 focused registration, agenda and project-layout tests passed, including state visibility, expiry/isolation and hidden calendar controls. Full suite and live Intra checks not rerun; no separate release warranted.

- 2026-10-31: Shorten the project evaluation action labels and place them in an equal-width two-column row with a gap, nowrap/ellipsis overflow and full-label tooltips. Patch impact within 0.7.0; 22 project-layout tests passed and the wide/narrow action-layout test passed again after adding narrow assertions. Full suite not rerun; no separate release warranted.

- 2026-10-31: Shorten the project modal action to Open Intra with single-line sizing in English/French/Spanish, and move evaluation/history/finish actions into Registration to reuse its full-width buttons and vertical spacing. Patch impact within 0.7.0; seven agenda tests and 22 project-layout tests passed, including narrow translated button labels and action alignment. Full client suite not rerun; no separate release warranted.

- 2026-10-31: Center the project evaluation modal’s Intra and Close actions in a shared footer with a two-column gap and consistent widths. Patch impact within the planned 0.7.0 release; seven agenda tests passed, including footer alignment, bounds and dismissal at 40/120 columns. Full client suite and live campus checks were not rerun; no separate release is warranted for this layout fix.

- 2026-10-31: Gate project slot reads on the connected user’s current project state and selected campus; unfinished projects show an Intra handoff instead of unrelated availability. Reuse the read-only correction timeline, hide redundant filters, show time ranges, and bound the project modal at narrow/wide sizes. Patch impact within 0.7.0; 61 client correction/agenda tests, 9 architecture checks, 530 backend tests and backend type-checking passed; 38 environment-dependent backend checks skipped. Backend deployment, exact-pair compatibility and live Intra comparison remain pending; textual-calendar was evaluated but not added because its documented widgets select dates/times rather than lay out events.

- 2026-10-30: Add a phased loading and caching performance investigation plan covering measurements, isolation, release validation and a client-wide waiting-path audit. Documentation only; no release required. Plan review pending; no performance or deployment claims.

- 2026-10-30: Implement read-only agenda list/week views, role filters, evaluation
  history by week, project availability, dashboard upcoming evaluations, and the
  Intra project-finish handoff. Reuse bounded account-scoped reads for agenda
  sources and correction weeks, invalidating availability after writes. Add
  French/Spanish labels and align the shared-UI ownership fixture with the
  previously implemented theme preview. Minor impact toward 0.7.0. Backend deployment, exact-pair
  compatibility, live Intra permission/payload verification and release CI remain
  required; native booking/finishing remain deferred. Focused agenda, account
  boundary and narrow-terminal tests passed. Final checks: corrections scope
  58/58, project layout 22/22, architecture boundaries 9/9 and canonical imports
  3/3; regression scope ownership is complete. Optional full client run interrupted
  and not verified. Requires backend `b22a830` or its reviewed successor. The
  accumulated features warrant preparing minor 0.7.0 after the preceding release
  baseline is resolved; they are not ready for publication.

- 2026-10-30: Record the Intra redirect as the interim project finish flow for
  0.7.0. Documentation only; no release required. Roadmap diff checked;
  implementation and validation remain pending.

- 2026-10-30: Add Flatpak editor launch support to the 0.7.0 roadmap, including
  VS Code on campus workstations. Documentation only; no release required.
  Roadmap diff reviewed; implementation and validation remain pending.

- 2026-10-30: Update the 0.7.0 roadmap with completed local dashboard, project
  preview, Settings and community work and remaining integration and validation.
  Documentation only; no release required. Roadmap and diff reviewed; full CI
  and release validation remain pending.

- 2026-10-30: Align terminal image and icon selectors with a responsive
  narrow-terminal layout. Patch impact; focused terminal Settings checks run.
  Full CI and release validation remain pending.

- 2026-10-30: Remove Workspace and notification helper lines and display the TDF requirement
  only when its viewer is selected. Patch impact; focused Settings UI checks
  run. Full CI and release validation remain pending.

- 2026-10-30: Remove Account settings helper paragraphs; show the session-only
  deletion warning when that option is selected. Patch impact; focused Settings
  and account locale checks run. Full CI and release validation remain pending.

- 2026-10-30: Align catalog refresh with the fallback selector, stacking them
  in narrow terminals, and remove catalog, cursus, automatic-update and subject
  auto-check help text.
  Patch impact;
  focused Settings layout checks run.
  Full CI and release validation remain pending.

- 2026-10-30: Center Community browser feedback and clear it after five seconds, resetting the
  timer for subsequent actions. Patch impact; focused Settings check run.
  Full CI and release validation remain pending.

- 2026-10-30: Redesign the Settings Community section with descriptive,
  responsive GitHub and Discord cards. Patch impact within 0.7.0; focused
  Settings checks run. Full CI and release validation remain pending.

- 2026-10-30: Show the GitHub and Discord reminders once as bottom-right
  cards after setup, with link and dismiss buttons and project-hosted redirect
  links for GitHub and Discord. Minor impact toward 0.7.0;
  focused reminder persistence and UI checks run. Full release checks pending.

- 2026-10-30: Add Community links and independently persistent reminders, and
  use native desktop clipboard tools for OAuth links with terminal fallback.
  Minor impact toward 0.7.0; focused Settings and account tests run. Full CI,
  real desktop clipboard checks and release validation remain pending.

- 2026-10-30: Preview highlighted themes in the open selector and restore the
  selected theme when dismissed; place the session move action beside its
  selector. Patch impact within 0.7.0; focused Settings checks run.

- 2026-10-30: Preview selected themes immediately in Settings and onboarding;
  Settings still persists the choice on save. Patch impact within 0.7.0.
  Focused theme UI checks run; full CI and release validation remain pending.

- 2026-10-30: Add active session storage selection in Account settings, verifying
  the destination before removing the previous copy and rejecting existing
  destinations. Minor impact toward 0.7.0. Focused credential-store and Settings
  checks run; security review, cross-process filesystem and release checks pending.

- 2026-10-30: Remove the terminal icon preview and capability notes from Settings
  while preserving image and icon mode selection, and align the username preview.
  Patch impact; focused terminal
  and Settings navigation tests passed. Full CI and release validation pending.

- 2026-10-30: Redesign Settings navigation, category context and sections, and
  group catalog, terminal display and notification controls. Retain existing
  preferences, validation and keyboard navigation. Minor impact toward 0.7.0;
  Settings, curriculum and terminal UI checks passed. Full CI, manual terminal
  review and release validation remain pending.

- 2026-10-30: Add hover previews and keyboard-accessible, scrollable project
  lists to dashboard progress statuses, respecting the selected curriculum. Make
  segments resize proportionally, color tooltip headers by status and focus the
  list when opened. Patch impact;
  focused dashboard checks and small-terminal interaction checks passed.
  Full release CI and candidate validation remain pending.

- 2026-10-30: Replace the duplicated profile-card workstation with the selected
  cursus grade, level and primary campus, and arrange profile statistics in two
  columns. Coalition values require the pending backend integration. Patch impact; dashboard UI
  checks cover cursus selection, unavailable values and French/Spanish labels.
  Full release CI and candidate validation remain pending.

- 2026-10-30: Combine dashboard label cleanup and friend project preview
  layout and details changes. Patch impact; 23 focused UI and locale checks
  passed on the combined branch. Release CI and candidate validation remain pending.

- 2026-10-30: Remove the danger-button item from the 0.7.0 roadmap and clarify
  agreed priorities, dashboard details and the observed log-time response format.
  Documentation only; no release required. Roadmap diff checked; endpoint
  feasibility and 0.6.2 release validation remain pending.
