# Development changelog

Latest release: **0.5.2** ([`v0.5.2`](https://github.com/HeduroFR/42tui-client/releases/tag/v0.5.2)).
Package version: **0.5.2**.
Suggested next release: **0.6.0** (minor), for the implemented tester workspace,
project copy protection and structured result reporting; not publication-ready.
Remaining tester runtime validation targets 0.6.0; unfinished Git design
work remains in [TODO.md](TODO.md). Plans alone do not justify publication.
The implemented tester workspace and copy protection warrant preparing 0.6.0
(minor) beyond the published 0.5.2 artifact.
Remaining runtime/platform and release gates prevent publication readiness.

This file tracks implemented changes since the latest successful release. Keep
published notes in [CHANGELOG.md](CHANGELOG.md). See
[distribution operations](docs/distribution.md#development-changelog).

## Changes since 0.5.2

- 2026-10-30: Center the tester removal icon by using an odd number of terminal
  cells for its square-style button. The width may differ from a physical square
  by up to one cell. Patch UI improvement within the planned 0.6.0 minor;
  focused removal UI test and whitespace check passed. No live terminal font
  check, release or deployment. PR #47.

- 2026-10-30: Hide input for the non-interactive printf tester and after any run;
  add a validated `interactive_input` catalog option defaulting to true for
  compatibility with custom testers. Hide input for setup/removal operations.
  Patch UI improvement within the planned 0.6.0 minor. Checks: 70 catalog
  tests, focused catalog and workspace visibility tests passed; whitespace passed.
  No live terminal check, release or deployment. PR #47.

- 2026-10-30: Use the shared localized trash icon for tester removal, retaining
  square danger styling in icon modes and a readable Remove label in text mode.
  Replace the shared trash Unicode fallback cross with a text-presentation bin.
  Extend existing icon and tester removal regressions. Checks: 4 capability tests
  and focused removal UI regression passed in nerd/Unicode/text modes; whitespace
  passed. No live terminal font check claimed.
  Uncommitted on feat/tester-workspace-0.6.0, PR #47. Patch UI polish within
  recommended 0.6.0 minor; publication gates remain open.

- 2026-10-30: Replace the project tester log-folder action with Open log using
  the configured VS Code/Zed/Vim/Neovim editor. Reuse project editor launch and
  terminal suspension behavior for files, preserving directory launches. Put
  View full output to its right in a shared action row, targeting the current
  workspace log. Add missing-file feedback, localized labels and regression
  checks for editor argv, terminal handoff and responsive button placement.
  Checks: 23 tester UI tests passed (102.672 seconds), 2 locale checks passed,
  and file/directory argv regression passed for all four editors. Inspected a
  headless rendered preview; editors were mocked rather than launched.
  Uncommitted on feat/tester-workspace-0.6.0, PR #47.
  Patch improvement within planned 0.6.0 minor; publication gates remain open.

- 2026-10-30: Redesign the project tester panel with a themed result card,
  status heading, total, responsive four/two-column counters, and a per-run
  log-folder action instead of displaying the absolute path. Retain diagnostics
  in the transcript and nonzero exit codes in the card. Shorten the ready state
  with explanatory tooltip and use a compact full-output action. Add French and
  Spanish labels without changing shared result-status translations. Add layout,
  result-tone and correct-log-folder regression coverage. Checks: 21 existing UI
  tests passed; new responsive/result/log-action regression passed at 80/200
  columns, locale checks 2 passed, whitespace passed. Inspected a rendered
  headless screenshot; no live WezTerm interaction claimed.
  Uncommitted on feat/tester-workspace-0.6.0, PR #47. Patch UI improvement within
  the accumulated 0.6.0 minor recommendation; release/license/runtime gates remain
  open. No version bump, publication, deployment or backend change.

- 2026-10-30: Connect bundled Supra printf to the maintained HeduroFR fork at
  f5c6484ab94efdfad0a65bbe8b88be93459c0d05. Prefer native arm64 Docker on
  Apple Silicon/ARM engines, retain amd64 on Intel, and pass a fresh JSON report
  to the existing validated result reader. Keep libft on amd64. Configure the
  fork watchdog, update architecture validation and catalog/manual regressions,
  and document the local development launcher. Checks: tester scope 98 passed (88.665 seconds),
  70 adapter and 9 architecture tests passed;
  real macOS Apple Silicon Docker run through the production adapter completed
  all 503 comparisons with one expected forbidden-vprintf failure, parsed the
  report and preserved the poisoned original fixture. No interactive WezTerm
  visual validation or new CI run claimed. Changes remain uncommitted on
  feat/tester-workspace-0.6.0 (PR #47). Patch fix within the accumulated 0.6.0
  minor; release/runtime and redistribution-license gates remain open. No bump,
  publication, backend change or deployment.

- 2026-10-30: Remove the bundled Francinette definition/launcher and its retired
  manual smoke harness; retain Supra printf/libft and native push_swap. Update
  catalog/UI regressions and active documentation/roadmap, preserving custom user
  definitions and old images. Add a one-cell RichLog left inset without changing
  PTY columns, emulator text or saved transcripts. get_next_line now has no bundled
  tester. Checks: tester scope 98 passed (74.751 seconds), adapter 70,
  architecture 9 and locale 2 passed; scope assignments cover 957 tests. Clean
  wheel/sdist validation confirms only the three remaining tester definitions;
  whitespace passed. Minor release remains 0.6.0 preparation, with runtime/release
  gates open. PR #47; no version bump, publication or deployment.

- 2026-10-30: Fix Supra container runs reusing up-to-date host objects/archives
  (macOS Mach-O cannot link into Linux ELF shared libraries). Add an entrypoint
  that runs fclean and a forced all build only inside the disposable mount, fails
  before launching the tester when preparation fails, and preserves tester argv.
  Include its packaged bytes in image identity to invalidate cached images.
  Add real make/ar regressions and seed both live container fixtures with
  future-dated foreign artifacts. Checks: adapter 72, architecture 9 and locale 2
  passed; clean wheel/sdist including entrypoint and shell syntax passed. Real
  Docker/macOS arm64 libft run rebuilt poisoned artifacts, completed and preserved
  originals. printf rebuilt and linked successfully, then stalled during tests
  under amd64 emulation; stopped the disposable container. No completed Mac printf
  run or memory equivalence is claimed. Full tester scope: 100 passed (81.097 seconds). Patch impact
  within the planned 0.6.0 minor; PR #47, no version bump or publication.

- 2026-10-30: Add definition-driven bundled Docker recipes and pinned Supra
  printf/libft definitions for Linux/macOS. Include recipe bytes in image identity,
  package the multi-stage Debian recipe and verify it in release archives. Keep
  legacy/custom Docker contexts unchanged. Select Linux amd64 consistently and
  retain existing OS/engine/emulation/mount checks. Install through Meson without
  upstream user pip installation or runtime auto-update. Restrict Supra runs with
  disabled networking, read-only root, temporary storage, dropped capabilities,
  no privilege escalation and a process limit. Keep results unverified; no claim
  of superior accuracy/memory coverage. Add real fixture/container PR checks and
  resource/parser/build/UI regressions. Local Docker daemon was unavailable and
  Desktop could not start; no successful local live build is claimed. Validation
  results: tester scope 98 passed (101.587 seconds), release-tooling 96,
  adapter 70, architecture 9 and locale 2 passed; clean tracked-file wheel/sdist,
  recipe-resource presence and installer hashes/syntax passed. Real container CI
  and Mac/ARM emulation remain pending. Initial CI built both images but exposed
  noexec temporary mounts preventing dlopen of generated libraries; explicitly
  permit execution only in the bounded temporary mount, retaining the other
  restrictions. Extend real checks to an ARM runner with a pinned QEMU helper.
  Minor impact within planned 0.6.0;
  PR #47 on `feat/tester-workspace-0.6.0`. No version bump/publication/deployment.

- 2026-10-30: Add preparation/build/run stages and a source-hash-guarded
  Francinette summary reader, counting suites and norm/function checks. Disable
  upstream auto-update for the verified source; unknown source/missing summaries
  remain unreadable. Live Docker/macOS arm64 fixture reported exit 0 with 6 checks,
  3 passed, 2 failed and 1 skipped, preserving the original project. Add summary
  parser regressions, stage translations and realistic UI session mocks. Add an
  opt-in full native C-fixture/default-suite smoke check and Ubuntu/Intel/Apple
  Silicon workflow, plus a sourced Colima/runtime assessment. Upstream push_swap
  default exits 0 despite printed failures; retain unverified status and do not
  claim memory coverage when leaks times out. Checks: installation-updates 83,
  architecture 9 and locale 2 passed; clean tracked-file wheel/sdist and installer
  hashes/syntax passed. Tester scope 96 passed (110.214 seconds); scope ownership covers all
  955 discovered tests without overlap. Full default native C build/suite smoke passed its failure/unverified-result
  assertions on macOS arm64, preserving the source. Upstream memory checks timed
  out and cannot establish memory safety. Backend protections are being prepared separately;
  production storage encryption, deployment evidence, hosted platform/Colima
  measurements and integrated release gates remain open. Minor impact: prepare
  0.6.0, not publication-ready; version unchanged. Branch
  `feat/tester-workspace-0.6.0`; PR #47. No publication/deployment.

- 2026-10-30: Add definition-driven native testers, preparation commands and
  source/project/Python placeholders. Bundle ft_ps_tester at commit 49cf9c7 for
  push_swap, using Git, a temporary venv without pip and disposable project
  copies. Require consent for initial/repeated native execution, reject external
  project symlinks, skip Docker inspection/setup, and reuse global locking,
  PTY cancellation, logs and structured report validation. Stop background
  children holding the PTY after the tester exits; add a real-process regression.
  Retain unverified status for upstream testers without a validated report reader. Refresh roadmap
  status and document prerequisites/network/permissions. Minor impact for 0.6.0;
  branch `feat/tester-workspace-0.6.0`, uncommitted. Checks: native adapter tests
  exercise setup/results/cancellation/error paths with real Git/venv/PTY commands;
  architecture 9 and locale 2 passed, plus 16 native-message translation assertions.
  Wheel/sdist, installer hashes/syntax and whitespace passed. Initial tester scope
  94 passed; a subsequent run exposed a 300-ms test-start assumption, replaced
  with an event wait. Final tester scope: 95 passed (84.331 seconds). Live macOS arm64 pinned
  upstream basic suite correctly rejected an intentionally incorrect Python
  executable fixture (exit 1, 61 failures), preserving the original project.
  Upstream leaks checks timed out and nevertheless printed a memory PASS; do not
  count that as memory validation. Initial live run was cancelled after a PTY held
  by descendants; the completed rerun used the cleanup fix. Full default push_swap
  suite, real C-project build, Linux/Intel platform matrix, Francinette summaries
  and final release gates remain open. No backend/API change, version bump or publication.

- 2026-10-29: Add portable tester outcomes and opt-in TOML `result_file` JSON
  summaries, read before disposable-copy cleanup. Distinguish test failures,
  process failures, unreadable reports and unverified results; require consistent
  counts and a successful process before confirming passing tests. Reject stale,
  linked, nonregular, oversized, invalid and all-skipped reports. Display exit
  codes/counts in the workspace and transcript with French/Spanish coverage;
  document the contract and keep Francinette explicitly unverified without a
  validated reader. Fix a teardown-timer crash exposed by repeated result runs.
  Checks: tester scope 90 passed (synthetic real-PTY subprocesses and headless UI),
  architecture 9 and locale 2 passed; scope ownership covers all 949 discovered
  tests without overlap; whitespace/diff reviewed and added-line/new-file security
  scan found no matches. Full-suite and packaging checks not run. Minor impact for
  planned 0.6.0, worth preparing against the published 0.5.2 baseline but not ready to publish. Branch
  `feat/tester-workspace-0.6.0`; PR #47. Independent review found no blocking
  security or logic issues; focused tester, architecture and locale checks were
  repeated successfully after synchronizing with the updated PR branch. Real
  Docker/Francinette Linux/macOS result validation, contrasting/native testers,
  exact-candidate CI/package/compatibility gates and separate backend security
  work remain pending. No version bump, backend change or external write.

Implemented tester changes and later roadmap documentation are retained below;
planning-only entries do not imply completed features.

- 2026-10-29: Consolidate the pending tester line-ending/button fixes, checkout
  SSH modal, development-remote fallback and unnumbered group-Git roadmap for
  the authorized branch commit/push. Checks previously run: Git suite 52 plus
  partial-clone preservation regression, terminal 6, rendering 2, project-details
  UI 22, architecture 9 and focused removal layout test passed. Final tracked
  diff and whitespace reviewed; unrelated untracked duplicate files excluded.
  No API/backend or version change; planned 0.6.0 remains subject to native and
  release validation, with no separate release justified by this consolidation.

- 2026-10-29: Add unnumbered future roadmap work for simpler group-project Git
  collaboration: shared development setup, guided push/pull, synchronization
  visibility and conflict guidance, reusing existing Git actions and preserving
  local work and separate Vogsphere publication. Planning only; no release
  required. Checks: unversioned placement, existing Git scope and whitespace
  reviewed; runtime tests skipped. Same branch; uncommitted.

- 2026-10-29: Allow checkout recovery to use a populated development remote
  when Vogsphere inspection or cloning fails for remote-access reasons. Retain
  Vogsphere configuration and explicit warnings; never remove a partial clone
  or overwrite existing/unborn checkout files. Keep development failures and
  unavailable sources blocking. Add disposable-repository regressions for new,
  empty and unborn folders plus clone-time refusal. Patch impact within planned
  0.6.0; no separate release warranted. Same branch, uncommitted. Checks: Git
  suite 52 passed, additional partial-clone preservation regression passed;
  whitespace reviewed. Live campus/Vogsphere access unverified.

- 2026-10-29: Pass the existing ProjectSshPromptHandler into Save + Set Up
  Checkout's background Git operation, covering its remote inspection/recovery
  authentication. Close prompts and release the busy state on success, failure
  and cancellation; suppress success reporting after cancelled authentication.
  Reuse existing masked entry and operation-scoped secret handling. Patch impact
  within planned 0.6.0; no separate release warranted. Same branch, uncommitted.
  Checks: project-details UI and architecture regressions; no real SSH key used.

- 2026-10-29: Use the shared AppButton square/danger behavior for tester removal;
  remove its fixed width and give Run a two-column right margin. Preserve tooltip,
  removal handling and equal row heights. Patch impact within planned 0.6.0;
  no separate release warranted. Same branch, uncommitted. Checks: focused
  removal UI regression and whitespace review; native tester runs not repeated.

- 2026-10-29: Fix diagonal tester output introduced by feeding app-generated
  bare line feeds into the terminal emulator. Convert synthetic status/command
  and final-result lines to CRLF while leaving raw PTY output unchanged. Add a
  real PTY-to-emulator regression with multiline commands and mixed newline forms.
  Checks: terminal tests 6 passed, redraw/rendering tests 2 passed, whitespace
  reviewed. Patch impact within planned 0.6.0; no separate release warranted.
  Same `feat/tester-workspace-0.6.0` branch; uncommitted. Native Francinette run
  and WezTerm visual inspection remain unverified.

- 2026-10-29: Fix tester console redraws using pyte 0.8.x terminal emulation
  matching the private 100×24 PTY, preserving ANSI colors, partial reads and
  bounded scrollback. Request plain Docker build progress; replace Log location
  with Open log folder using the existing explorer adapter and error feedback.
  Align Run and removal controls on one fixed-height row. Add redraw/scrollback
  regressions and alignment assertions. Patch impact within planned 0.6.0;
  same `feat/tester-workspace-0.6.0` branch, uncommitted. Checks: tester scope
  77 passed, log-folder action/error test passed, architecture 9 and locale 2
  passed; wheel/sdist checks, installer hashes/syntax and whitespace passed.
  WezTerm direct inspection was denied by the computer-use tool; native Docker
  reproduction is unverified. No version bump or publication.

- 2026-10-29: Add horizontal gaps between tester workspace action buttons and
  a blank row between the input field and action row. Patch impact, included in
  the planned 0.6.0 minor release; no separate release warranted. Branch:
  `feat/tester-workspace-0.6.0`; uncommitted. Checks: headless layout at 80×24
  and 140×65, plus diff/whitespace review. Native tester execution not repeated.

- 2026-10-29: Continue tester work on `feat/tester-workspace-0.6.0`: replace
  terminal suspension with a persistent in-app workspace and private PTY runner.
  Capture live output and line input, cancellation with process-group cleanup,
  elapsed time, follow-output control, rerun against the captured project and
  automatic full transcripts. Keep recent display output bounded; preserve setup
  approval, operation locking and disposable copies. Cancellation is consumed
  before installer cleanup so finally commands can still run. Add French/Spanish
  labels and terminal/UI regressions. Minor impact, intended release 0.6.0;
  no version bump or publication. Checks: tester scope 75 passed; extended UI
  rerun test passed, final PTY tests 5 passed; architecture checks 9 and locale
  checks 2 passed. Final diff and scope ownership reviewed. Native Docker validation, full-screen terminal emulation, structured
  result readers and lighter/multiple tester runtime definitions remain pending.
  Work is uncommitted; 0.6.0 remains unready for publication.

- 2026-10-29: Begin the 0.6.0 tester rework after roadmap PR #45 merged as
  `13f966b` with all 21 CI checks passing. Run Docker testers and their mount
  probes against a disposable project copy, excluding Git metadata and preserving
  symlinks. Clean up the copy on success, process failure and interruption;
  retain existing logs, Docker context/CPU/user mapping and container cleanup.
  Patch impact, targeted for the planned 0.6.0 minor release. Branch:
  `feat/tester-workspace-0.6.0`; uncommitted. Checks: tester scope 72 passed,
  including destructive-write and interrupted-run preservation checks; architecture
  checks 9 passed, locale checks 2 passed, French/Spanish copy-message assertions
  and diff/whitespace review passed. Native Docker runs and disk-space behavior
  remain unverified. Modular/native execution, in-TUI workspace, backend data
  protection and final 0.6.0 release gates remain pending; no release ready.

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
