# Development changelog

Latest published release: **0.7.0** ([`v0.7.0`](https://github.com/HeduroFR/42tui-client/releases/tag/v0.7.0)),
verified as a published stable GitHub release on 2026-11-05.
Package version: **0.7.0**.
Suggested next release: **0.7.1** (patch), for direct editor launch, explicit Git
recovery and automatic Neovim integration loading under Lazy.nvim. A release is
worth preparing; release CI and live editor/version validation remain outstanding.
These fixes do not change the API or require a backend rollout.

The historical entries below are retained until distribution verification and
release bookkeeping are complete; they do not all represent unreleased changes.
Keep published notes in [CHANGELOG.md](CHANGELOG.md). See
[distribution operations](docs/distribution.md#development-changelog).

## Changes since 0.7.0

- 2026-11-05: Add a manifest-owned Neovim `after/plugin/42tui` loader that makes
  the existing data-directory module available under standard and Lazy.nvim
  startup. Native installations upgrade in place; both entry points share the
  existing setup guard. Respect XDG config/data and `NVIM_APPNAME`, preserve
  overrides, remove startup entry points before module removal, and report
  unknown runtime activity separately from CLI dry-run verification. Other
  editors and heartbeat implementation are unchanged; no dependency added.
  Patch impact toward 0.7.1; no package version bump.
  Reference: branch `fix/neovim-config-loader`.
  Checks: focused lifecycle and isolated standard/Lazy.nvim startup tests pass
  on Neovim 0.12.6 with heartbeat execution stubbed, including repeat install,
  native migration, failure recovery, uninstall, custom XDG/appname, spaces,
  Unicode paths, setup overrides and one autocommand group/pending timer.
  After integrating PR #59 (`7d0aeed`), all 50 editor-integration scope tests
  and focused flake8 checks pass in the isolated task worktree;
  wheel/sdist build and resource checks, focused flake8, locale JSON, installer
  digests, shell syntax and diff checks pass. Graphify code graph refreshed.
  Oldest supported Neovim and complete LazyVim/SupraVIM configurations are not
  retested; full-suite PR CI and release/publication checks remain outstanding.
  Preparing patch 0.7.1 is worthwhile, but it is not ready to publish.

- 2026-11-05: Separate direct editor launch from explicit project checkout
  recovery. Group Recover Git and the three existing push actions in a collapsed
  two-column Git section, retain SSH/review/cancellation safeguards, refresh
  workspace availability after recovery without automatically launching an editor,
  and fix the undefined command in terminal-editor exit reporting. Update French,
  Spanish and project Git documentation. Patch impact toward 0.7.1;
  no version bump. Reference: branch
  `fix/project-editor-actions`.
  Follow-up: render the Git disclosure header on one fully clickable line and pad its expanded
  contents so buttons do not touch the background edges. Focused layout check
  passes at 80/160 columns in English/French/Spanish, including header height,
  spacing on all four sides and unclipped button labels; diff whitespace check passes.
  Far-right clicks open and close the section at both widths in all three
  languages; the focused regression check passes.
  Checks: 7 editor launch and 53 Git behavior tests pass; 22 project details/Git
  UI tests pass, followed by 5 updated layout/completion tests covering direct
  launch, keyboard access and 80/160-column layouts in English/French/Spanish.
  Focused selection clearing and tester-log editor checks, recovery translation
  assertions and diff whitespace checks pass. Full CI and live checks were not run.
  Preparing patch 0.7.1 is worthwhile for this fix; release CI and live
  editor/campus validation remain before publication. No backend API change.

## Earlier development record since 0.6.2

- 2026-11-02: Make the cancelled-connection release check wait for the
  account modal before asserting it. Test-only; no runtime impact.

- 2026-11-02: Prepare version 0.7.0 and its release notes. Minor impact; package
  version and changelog headings updated, regression scope ownership and
  wheel/sdist checks run locally. Release CI, manual editor validation, backend
  deployment and exact-candidate publication checks remain pending.

- 2026-11-02: Document that local verification uses only the focused tests or
  `release/regression_scopes.py --scope <affected-scope>` for the changed
  feature; the full suite stays in PR CI and is reserved for release-candidate
  validation or cross-cutting failures. No runtime impact.

- 2026-11-02: Add managed editor integrations for Vim, Neovim, VS Code and Zed.
  Assets ship inside the wheel and install offline into native `pack/start`
  directories (Vim/Neovim), a generated VSIX or extension folder (VS Code), and
  Zed's installed-extension directory. The feature service resolves the absolute
  `42tui` path, injects it into files 42TUI owns, refuses unmarked targets, writes
  an install manifest, and removes only manifest-owned files. `42tui heartbeat
  --dry-run` resolves a configured project without inserting a heartbeat or
  crediting time, so Settings can verify the executable without polluting
  activity. Onboarding offers install/skip/retry; Settings → Workspace → Editor
  shows install state, path, last editor event, heartbeat verification,
  update/repair and confirmed uninstall. French and Spanish strings are included.
  Minor impact toward 0.7.0.
  Checks: full suite (1147 tests, 5 skipped) passes; asset/packaging, VSIX contents, warm-path filesystem safety, editor
  targets, fake `code`/`flatpak` commands, heartbeat dry-run, service lifecycle,
  Settings and onboarding UI tests pass. `uv build` and
  `python release/check_package.py dist` pass with all editor assets.
  Review fixes: repair restores missing owned files, uninstall removes only
  manifest-owned files and moves unrelated leftovers to a sibling
  `-unrelated` directory, heartbeat verification uses the CLI
  path recorded at install, Settings requires `--version` before saving a path,
  foreign installs cannot be uninstalled, result messages translate their base
  text before appending technical detail, and Neovim's user `setup()` falls back
  to the injected absolute command.
  Blockers: live VS Code (VSIX activation) and Zed (hand-placed wasm) validation
  is pending on machines where those editors are installed; the owner reviews the
  real extensions. A LazyVim/SupraVIM install/startup check with the full plugin
  manager is still pending, but a Neovim startup that calls
  `require("ft_tui").setup()` before the auto plugin verified that the user's
  command and interval are not overridden. Manual macOS
  checks passed for fresh Vim/Neovim installs, plugin auto-load with a generated
  absolute path, and a Neovim `BufEnter` heartbeat recorded through the installed
  plugin; Vim's headless ex-mode does not exercise its asynchronous job, so the
  Vim edit/save attribution walkthrough remains for interactive review.

- 2026-11-02: Assign the `test_activity_heatmap` and `test_editor_launch`
  modules to their dashboard and projects regression scopes, and wait for the
  asynchronous agenda subscription tooltip before asserting it. Test-only; no
  runtime impact.

- 2026-11-02: Add the dashboard activity-card toggle between local coding time and
  the connected account's reported campus workstation time. Workstation mode sums
  reported daily seconds into four weeks, keeps missing days distinct from reported
  zero, labels stale retained data, shows pending/loading/unavailable states with
  bounded retries, and preserves cached data on refresh failures. It reads the
  account-scoped `GET /v1/me/attendance`, which takes no user or login parameter
  and queues the authenticated Intra worker read of
  `translate.intra.42.fr/users/<login>/locations_stats.json`. Patch impact toward
  0.7.0.
  Hovering a day now shows its exact time and the cumulative week-to-date total in
  the compact `10h32 (34h00)` form; activity cells use a smooth hour-based color
  gradient instead of fixed bands, the grid stays centered, and the heatmap uses a
  pointer cursor. The toggle is a centered 3-row AppButton and the section is
  labelled `LOG TIME`.
  Checks: 130 agenda/dashboard/profile/HTTP client tests passed, including the new
  projection, provider, pending-retry, gradient and per-day tooltip tests. The
  dependent backend and worker change is not deployed yet; live campus permissions,
  timezone coverage and ongoing-session behavior remain unverified.

- 2026-11-02: Exclude exam projects from the dashboard's Needs Attention setup
  candidates and its setup button, matching the existing resume filter, while
  keeping exams in the curriculum journey. Patch impact toward 0.7.0. Nine
  dashboard service tests passed, including the exam exclusion.

- 2026-11-02: Rework the dashboard's action row: My evaluations now groups the
  sessions the user evaluates, the sessions where they are evaluated, and the
  events/exams they subscribed to, with dashboard-style section headings; recent
  notes move beside the progress bar.
  Requires the backend subscribed-event-ids endpoint. Minor impact toward 0.7.0.
  Seventy-nine agenda/dashboard tests passed, including role grouping,
  subscription filtering, past-item exclusion and the new card heights. Live
  layout review and backend deployment of the new endpoint remain outstanding.

- 2026-11-02: Read the dashboard coalition name, score and rank from the deployed
  `/v1/me/coalition` snapshot, scoped to the connected account and cursus, with
  a profile fallback while pending or unavailable and a 60-second refresh. The
  coalition name and rank (`Name - #N`) use the coalition color above the score.
  Patch impact toward 0.7.0.
  Thirty-three dashboard tests passed, including snapshot precedence,
  foreign-account/cursus rejection and malformed values. Live snapshot timing
  remains unverified.

- 2026-11-02: Launch a Flatpak-installed editor when its executable is not on
  PATH (VS Code `com.visualstudio.code`, Zed `dev.zed.Zed`, Neovim
  `io.neovim.nvim`, Vim `org.vim.Vim`), while native installs keep priority.
  Patch impact toward 0.7.0. Five focused resolver tests, one navigation launch
  test and the project-tester editor scope passed (31 tests). Live Flatpak
  launch on Linux remains unverified.

- 2026-11-02: Align the two dashboard layout checks with the scrollable dashboard
  page; its five blocks cannot fit 46 rows and the page uses `overflow-y: auto`.
  Test-only; no release impact. Dashboard profile scope passed 8 tests.

- 2026-11-02: Keep the user-facing Unreleased notes aligned with committed code;
  notes for the still-uncommitted performance work remain in the worktree with
  that code. Documentation only; no release impact.

- 2026-11-02: Paint the friends list from the cached summary batch during refresh,
  enrich details two at a time instead of one by one, and shorten rank cells while
  keeping the full explanation in details. Patch impact toward 0.7.0. Friends scope
  passed 61 tests with two optional skips; synthetic 10-friend probes cut detail
  completion from 1.01 s to 0.51 s and added one batch call on refresh. Live
  backend timing and final candidate validation remain outstanding.

- 2026-11-02: Add Intra event subscription management to Agenda with the `profile`
  scope requested on every login, and translate its copy. Minor impact toward
  0.7.0. Focused subscription and locale tests passed; backend deployment, live
  42 behavior and final candidate validation remain outstanding.

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

- 2026-10-31: Ignore a failed Clubs read after its campus or revision changes, preventing an obsolete error from replacing the current campus status. Patch impact. The delayed campus-switch failure regression and clubs/social scope passed (67 tests, one skipped); live verification remains outstanding.

- 2026-10-31: Repeat full unittest discovery in the temporary editable environment: 1,060 tests in 983.6 s, with five skips and the same two dashboard viewport-height failures reproduced at baseline c45713c. This run began before the final safety follow-ups, so it does not certify the final candidate. Five synthetic inbox-open runs with a 250 ms refresh delay gave 252.70 ms median before and 0.75 ms after; these measurements exclude live network timing. Verification only; no release impact.

- 2026-10-31: Mark a failed agenda source unavailable or stale immediately while other sources are still loading. Patch impact. Focused delayed-source and failure-status tests passed, as did all 77 correction/agenda scope tests. Live verification remains outstanding.

- 2026-10-31: Mark disk-restored friend snapshots consistently stale so validated offline profiles can display saved projects. Patch impact. Repository and disposable-database profile regression tests passed, as did all 40 profile scope tests; the friends scope passed 60 tests with two optional simulations skipped. No live timing or release verification.

- 2026-10-31: Fence social-inbox error handling by revision so an obsolete denied refresh cannot clear newer data. Patch impact. Focused obsolete-response, access-denial and offline-retention tests passed; the clubs/social scope passed 65 tests with one optional simulation skipped.

- 2026-10-31: Run local cross-language friend-preview simulation against the current client and backend performance worktrees: two tests passed and 42 mock requests were recorded. Verification only; no release impact. Worktrees were uncommitted; this is not a pinned compatibility receipt or deployment evidence.

- 2026-10-31: Queue a Clubs refresh requested while an earlier read is in flight, preventing campus switches from being dropped until another refresh trigger. Patch impact. Delayed-campus regression passed; the clubs/social scope passed 64 tests with one optional simulation skipped. The new request still waits for the earlier read to finish; live timing and release validation remain outstanding.

- 2026-10-31: Run manual friends-inbox refresh in the background so controls remain responsive; keep saved content on network failure and clear it on authorization denial. Minor impact toward 0.7.0. Focused blocked-provider, offline and authorization tests passed; the clubs/social scope passed 63 tests with one optional simulation skipped. Live timing and release validation remain outstanding.

- 2026-10-31: Open the friends inbox immediately from its existing snapshot while refreshing in a background worker; avoid a refresh when closing it. Minor impact toward 0.7.0. All 17 social UI tests passed, including a deliberately blocked provider, visible refresh status, denial clearing and offline retention; the clubs/social scope passed 60 tests with one optional simulation skipped before the final UI follow-up. Live timing remains outstanding.

- 2026-10-31: Full unittest discovery in a temporary editable environment ran 1,055 tests in 926.6 s: two dashboard viewport-height failures and four skips. Both failures also reproduce at archived baseline c45713c; the run began before later agenda/profile test additions and is not a final-candidate check. Verification only; no release impact.

- 2026-10-31: Diagnose deployed campus-exams 403 responses and expose an explicit translated access-denied reason instead of only a generic stale source. Requires backend c1c43ab for same-token campus-filtered exam collection fallback and correct 403 propagation. Patch impact within 0.7.0; 22 agenda tests passed in the working checkout, and 17 passed against an isolated export of this staged patch, preserving concurrent unrelated work. Backend suite passed 536 tests with 38 environment-dependent skips and type-checking passed. Full client suite, deployment and live fallback success remain unverified; no separate release warranted.

- 2026-10-31: Extend the synthetic Postman friends mock and HTTP test to verify 101 summaries over three authenticated batches with at most two concurrent requests. Both friends HTTP simulation tests passed. Test-only; no release impact. Deployed backend and real 42 behavior remain unverified.

- 2026-10-31: Load up to two catalog categories concurrently, retaining complete-page and cross-category snapshot validation before atomic publication. Minor impact toward 0.7.0. Focused tests cover concurrency bounds, incomplete pages, account changes, conflicting snapshots and failed scans without starting the next pair. Five synthetic runs with 50 ms per category had 169.20 ms median before and 117.43 ms after; The full catalog scope passed 45 tests with one optional skip, and its local Postman HTTP simulation passed separately. Real backend timing and release validation remain outstanding.

- 2026-10-31: Pass local Postman friends-refresh and catalog-cache HTTP simulations with synthetic data (one test each). Verification only; no release impact. Catalog mock returned 501 for unimplemented incidental routes; these simulations do not verify live backend compatibility, 42 access or deployment.

- 2026-10-31: Display agenda sources progressively, clear already shown data on authorization failure, and fence rendering during teardown or context changes. Minor impact toward 0.7.0. All 21 agenda tests and all 74 correction-slot scope tests passed, including slow sources, late 401, pending requests, week changes and shutdown. Five synthetic runs with a 250 ms event-source delay gave 273.82 ms median at 3408627 and 43.56 ms after; real backend timing and release validation remain outstanding.

- 2026-10-31: Aggregate dashboard heartbeat totals by local stored day in SQLite instead of materializing every heartbeat. Minor impact toward 0.7.0. Exact-cutoff and daily total tests passed; five synthetic reads of 50,000 records had a 48.38 ms median before and 15.83 ms after, returning 50,000 versus 18 rows. This excludes UI and real-device timing. Nineteen dashboard service, repository, wiring and cache tests passed; the dashboard scope has two pre-existing viewport-height failures. Live timing and release validation remain outstanding.

- 2026-10-31: Display validated selected-friend project snapshots immediately in profiles as stale while core and project data load; ignore incomplete or mismatched seeds, identify saved data while offline, and discard cached profile data on profile authorization denial. Minor impact toward 0.7.0. All 40 profile scope tests passed. In five synthetic runs with a 250 ms core delay, median first-project display was 263.53 ms before and 82.44 ms after; this excludes real HTTP. Live timing and release validation remain outstanding.

- 2026-10-31: Run the clubs/social regression scope: 59 passed and one optional simulation was skipped. Verification only; no release impact. Real backend and network behavior remain unverified.

- 2026-10-31: Run the dashboard regression scope: 29 passed and two viewport-height assertions failed (52 rows versus 42). Both failures reproduce in the archived c45713c baseline. Verification only; no release impact. Dashboard layout failures remain unresolved.

- 2026-10-31: Run the full project regression scope: all 182 tests passed. Verification only; no release impact. This does not verify live backend or upstream evaluation timing.

- 2026-10-31: Deduplicate concurrent portrait loads within each existing cache while preserving cancellation independence, image validation and account-specific cache lifetimes. Minor impact toward 0.7.0. Cluster portrait, feature service and dashboard portrait tests passed (21 tests); all 88 cluster scope tests passed. Live timing and remaining performance checks are outstanding.

- 2026-10-31: Redesign Agenda with event blocks, overlap lanes, theme colors, compact responsive navigation and readable Markdown details. Correct SelectCurrent clipping by limiting toolbar layout rules to their owning containers; test English/French/Spanish at narrow/wide sizes. Add campus exams and optional location/occupancy/project metadata, retaining zero counts and explicit unknown values. Manage on Intra opens the observed profile-v3 calendar; event writes require an ungranted profile scope and exam writes require Advanced tutor, so no subscription writes or scope expansion were added. Minor impact toward 0.7.0; 70 corrections/agenda tests and 14 architecture/navigation/layout tests passed, with 16 agenda tests and three exam-detail checks rerun after final UI adjustments. Synthetic 40/80/150-column previews inspected. Requires backend 9cdd26a or reviewed successor; deploy it first and verify the exact pair/live campus payloads before release. Full client suite, live subscription/link flow and release CI remain unverified. 0.7.0 remains worth preparing, not ready to publish.

- 2026-10-31: Add opt-in synthetic evaluation rendering measurement. Five cold runs with 50 peer and 50 automated entries had a 276.5 ms median and 277.3 ms slowest completion, with two fake provider calls each; this does not measure real API latency or establish a performance guarantee. Measurement only; no additional release impact. Evaluation backend and live timings remain unverified.

- 2026-10-31: Coalesce routine friends-list redraws for up to 100 ms while keeping the selected friend and authorization failures immediate; flush pending redraws on completion. Minor impact toward 0.7.0. Five isolated synthetic runs with 100 friends and an immediate provider reduced median completion from 3,930.3 ms at c45713c to 423.7 ms, with 101 provider calls in both; 20-friend medians were 261.7 ms and 93.6 ms. These measurements use disposable SQLite and do not include real network or backend latency. Focused scheduling tests passed; the friends scope passed 59 tests with one optional simulation skipped. Live timing and release checks remain outstanding.


- 2026-10-31: Show completed friend-summary batches while later batches are still loading; clear already displayed results if a later batch loses authorization. Minor impact toward 0.7.0. Focused delayed-batch and later-401 tests passed; the friends scope passed 59 tests with one optional simulation skipped. Live performance and release checks remain outstanding.

- 2026-10-31: Load independent account profile and cursus sources concurrently while preserving per-source failure handling. Minor impact toward 0.7.0. Five synthetic runs with 50 ms per source gave 109.53 ms median before and 53.81 ms after; this excludes real HTTP and UI timing. Account service and context tests passed. The first accounts scope run had one connection-screen mount error; that test passed alone, and a full rerun passed 131 tests with one optional skip. Live backend timing and release validation remain outstanding.

- 2026-10-31: Overlap curriculum and the first personal-project page while retaining account and pagination validation before saving. Minor impact toward 0.7.0. Five synthetic runs with 50 ms per read gave 108.77 ms median before and 52.49 ms after; this excludes actual backend and UI rendering. Focused catalog tests passed; the catalog scope passed 42 tests with one optional simulation skipped. Live timing and release validation remain outstanding.

- 2026-10-31: Overlap up to two friends summary batches, cancel sibling waits on failure, and retain existing per-profile fallback. Minor impact toward 0.7.0. Five synthetic runs with two 50 ms cache-only reads gave 102.14 ms median before and 51.18 ms after; this excludes network and rendering. Focused scheduling and authorization-failure tests passed; the full friends scope passed 55 tests with one optional simulation skipped. Live backend timing and release validation remain outstanding.

- 2026-10-31: Remove My evaluations from tab composition and localization routing. Rework Agenda into a half-hour week timeline with a shared event/evaluation detail panel, role filters, overlap selection and narrow-terminal stacking. Clear visible rows immediately on account changes and retain dashboard/project-slot views. Minor impact toward 0.7.0; 10 agenda tests, nine architecture checks, four navigation tests and the focused full-app layout test passed in separate runs after correcting the navigation fixture for Agenda and scrollable tabs. Covers overlaps, midnight spans, DST folds, filtering and account clearing. Full suite and live Intra validation not rerun; no backend change or separate release needed for this UI iteration.

- 2026-10-31: Add a bottom margin to the project activity footer and use the primary variant for Set as finished. Patch impact within 0.7.0; nine project-activity UI tests and the focused project-layout test passed, covering footer space at wide/narrow sizes and the primary variant. Full suite not rerun; no separate release warranted.

- 2026-10-31: Run all 35 profile regression tests successfully, including independent loading with a delayed projects source. Test-only; no additional release impact. No real-network performance claim; remaining performance work remains outstanding.

- 2026-10-31: Preserve validated complete friend snapshots at the storage boundary when later summaries arrive, without bypassing membership identity checks. Focused repository tests passed; the full friends regression scope passed 53 tests with one optional simulation skipped, and regression-scope ownership passed. Minor impact toward 0.7.0; live measurements and remaining performance work remain outstanding.

- 2026-10-31: Add an opt-in synthetic selected-friend detail dispatch benchmark. Across five runs with a 250 ms gated summary, median dispatch was 251.30 ms at c45713c and 0.15 ms with the scheduling change; this excludes HTTP, backend and UI rendering. Project activity and cache checks passed 21 tests. Test/measurement only; no additional release impact. Live timings, backend integration and remaining performance work are outstanding.

- 2026-10-31: Gate project evaluation actions on fresh account/campus/project registration state, rename slot browsing to Subscribe to defense, and hide the fallback calendar toolbar/date range for unfinished projects. Patch impact within 0.7.0; 36 focused registration, agenda and project-layout tests passed, including state visibility, expiry/isolation and hidden calendar controls. Full suite and live Intra checks not rerun; no separate release warranted.

- 2026-10-31: Preserve complete saved friend details when a concurrent summary finishes later, and verify the ordering with a focused regression. Minor impact toward 0.7.0. Focused friends, profile and cache tests passed; 32 friends, profile and read-cache UI tests also passed. Live timing and release validation remain outstanding.

- 2026-10-31: Shorten the project evaluation action labels and place them in an equal-width two-column row with a gap, nowrap/ellipsis overflow and full-label tooltips. Patch impact within 0.7.0; 22 project-layout tests passed and the wide/narrow action-layout test passed again after adding narrow assertions. Full suite not rerun; no separate release warranted.

- 2026-10-31: Verify that a selected friend detail arriving after an account change is discarded, and that slow project reads do not hold the independently loaded attendance and goals sections. Test-only; no additional release impact. Focused tests passed; full performance plan and live measurements remain outstanding.

- 2026-10-31: Shorten the project modal action to Open Intra with single-line sizing in English/French/Spanish, and move evaluation/history/finish actions into Registration to reuse its full-width buttons and vertical spacing. Patch impact within 0.7.0; seven agenda tests and 22 project-layout tests passed, including narrow translated button labels and action alignment. Full client suite not rerun; no separate release warranted.

- 2026-10-31: Center the project evaluation modal’s Intra and Close actions in a shared footer with a two-column gap and consistent widths. Patch impact within the planned 0.7.0 release; seven agenda tests passed, including footer alignment, bounds and dismissal at 40/120 columns. Full client suite and live campus checks were not rerun; no separate release is warranted for this layout fix.

- 2026-10-31: Compared the existing isolated synthetic cache benchmark at client commit c45713c and the working tree (five warm revisits each). Normal warm friends median was 17.8 ms and 18.3 ms respectively, with zero provider calls; the one-friend fixture does not exercise selected-detail scheduling, so this is not evidence of its speedup. The focused friends/read-cache/context suite passed 23 tests with one optional simulation skipped. Documentation and verification only; no additional release impact. Live timing and the remaining performance work are outstanding.

- 2026-10-31: Gate project slot reads on the connected user’s current project state and selected campus; unfinished projects show an Intra handoff instead of unrelated availability. Reuse the read-only correction timeline, hide redundant filters, show time ranges, and bound the project modal at narrow/wide sizes. Patch impact within 0.7.0; 61 client correction/agenda tests, 9 architecture checks, 530 backend tests and backend type-checking passed; 38 environment-dependent backend checks skipped. Backend deployment, exact-pair compatibility and live Intra comparison remain pending; textual-calendar was evaluated but not added because its documented widgets select dates/times rather than lay out events.

- 2026-10-30: Allow selected friend detail reads during summary synchronization, limiting concurrent enrichment to the selected friend. Minor impact toward 0.7.0. Synthetic scheduling and friends UI regressions passed; read-cache UI regressions passed with the tests path configured. The opt-in synthetic cache benchmark ran with five warm revisits; live before/after timings, integration and release checks remain outstanding.

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
