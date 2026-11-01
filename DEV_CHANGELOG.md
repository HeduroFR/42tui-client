# Development changelog

Latest release: **0.6.0** ([`v0.6.0`](https://github.com/HeduroFR/42tui-client/releases/tag/v0.6.0)).
Package version: **0.6.2** (release candidate).
Suggested next release: **0.6.2**, for structured push_swap results and interface
fixes. Exact-candidate release checks, compatibility and remaining platform
validation are outstanding. GitHub and PyPI list 0.6.1, with matching package
hashes; complete publication verification before advancing the baseline.

This file tracks implemented changes since the latest successful release. Keep
published notes in [CHANGELOG.md](CHANGELOG.md). See
[distribution operations](docs/distribution.md#development-changelog).

## Changes since 0.6.0

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

- 2026-10-30: Prepare version 0.6.2 and its release notes. Patch impact; version,
  regression scope ownership, wheel and sdist checks passed locally. Release CI,
  compatibility and exact-candidate checks remain pending. Preserve pending
  entries until publication is fully verified.

- 2026-10-30: Add the agreed 0.6.2 tester results and interface fixes to the
  roadmap. Documentation only; no release required. Reviewed the roadmap diff;
  implementation and release validation remain pending.

- 2026-10-30: Pin the merged push_swap tester fork and display its structured
  results, marking unavailable memory checks incomplete. Patch impact. Fork PR:
  https://github.com/HeduroFR/42tui-tester-push-swap/pull/1. The 74 focused
  client tester checks and scope ownership check passed; five fork unit tests and
  a macOS ARM full-suite failing fixture passed. Intel/AMD, release CI and a
  passing student implementation remain unverified.

- 2026-10-30: Restore primary-style bevels and focus styling to red danger
  buttons. Patch impact toward 0.6.2; all 16 shared button tests passed. Release
  CI and final candidate validation remain pending.

- 2026-10-30: Hide expired correction slots in the calendar without changing
  stored availability or bookings. Patch impact toward 0.6.2; 13 calendar and
  22 correction-slot UI tests passed, including expiry and midnight boundaries.
  Release CI and final candidate validation remain pending.

- 2026-10-30: Serialize pairing with credential refresh and reject an approved
  pairing if its installation key changed; restore the selected keyring after
  a failed session-only attempt. Put the shared session lock beside the vault
  and sync vault directories before deleting migrated keyring credentials.
  Patch impact within 0.6.1. The accounts scope passed 123 tests with one skip;
  three social-provider tests and scope ownership checks passed. Added stale-token,
  key-change, storage-selection, cross-process lock and migration sync-failure
  checks. Cross-host network filesystem locking and campus hardware remain
  unverified; independent security review and candidate CI remain release blockers.

- 2026-10-30: Update the prelaunch update-process fixture for the credential-store
  constructor argument after 0.6.1 PR CI exposed its outdated mock. Test-only;
  no release impact. Full candidate CI must pass on the updated commit.

- 2026-10-30: Prepare package version 0.6.1 and release notes at the maintainer’s
  direction. Release checks, security review and campus validation remain pending.

- 2026-10-30: Add space between passphrase fields and center Continue and Cancel
  side by side. Patch impact within the planned minor release; focused layout
  and passphrase validation checks passed at 80×24 and 45×24.

- 2026-10-30: Hide overlapping connection actions while the session-storage
  dropdown is open, keeping Quit or Cancel available and restoring the other
  actions after selection or Escape. Patch impact within the planned minor
  release; focused account and shared-selector tests passed, including quitting
  while the dropdown is open.

- 2026-10-30: Replace separate disconnected-state storage buttons with a
  selector and one Connect action, hide the unavailable Disconnect action,
  and align the controls in a narrower dialog with option-specific guidance.
  Patch impact within the planned minor release; six focused session, layout
  and translation tests passed. Campus validation remains pending.

- 2026-10-30: Require account connection after completed onboarding and after
  disconnect, with Quit TUI available and successful pairing returning to the
  app. Existing unlocked sessions continue normally. Minor impact in pre-1.0;
  startup, pairing and disconnect UI checks passed. The accounts scope passed
  114 tests with one skip after stabilizing an onboarding timing assertion.
  Campus validation pending.

- 2026-10-30: Center and stack account connection and expired-session actions
  with clear spacing, move Cancel last, and constrain dialogs for narrow
  terminals. Patch impact within the planned minor release; focused layout
  checks passed at 80×24 and 120×45. The cancellation flow passed after scrolling
  to its button when the manual pairing link fills a small terminal.

- 2026-10-30: Expand the 0.7.0 roadmap to cover a substantial projects, friends
  and dashboard loading and cache rework. Documentation only; no release required.
  Checked roadmap placement and diff; implementation and performance validation
  remain pending.

- 2026-10-30: Add session-only and passphrase-encrypted account storage, startup
  unlock, explicit keyring migration and local vault reset. Preserve the keyring
  option and serialize store switches with token refresh. Minor impact. The
  accounts scope passed 109 tests with one skip; 23 focused storage, UI and
  translation checks passed after subsequent changes, including startup unlock
  cancellation. Earlier accounts runs
  twice failed an onboarding navigation assertion which passed in isolation and
  on the later complete run. Security review, campus KDF calibration, platform
  validation and release checks remain outstanding.

- 2026-10-30: Add the in-memory credential-store foundation in commit `1d75eb3`.
  Seven keychain tests passed at that stage; integrated and validated above.

- 2026-10-30: Record the verified 0.6.0 publication and update the distribution
  baseline. GitHub and PyPI wheel and source archive hashes match. No release
  required; backend deployment and compatibility verification remain outstanding.
