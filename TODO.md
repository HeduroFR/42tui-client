# TODO

## 0.5.0 — Project Git workflow and `42git`

Status: **0.5.0 published and verified** (PR #38, tag `v0.5.0`).
The 0.5.1 patch adds remote default/sole-branch discovery and reviewed
fast-forward-only `42git pull dev|vog|all` (PR #42, tag `v0.5.1`).
Implemented: conservative checkout recovery, reviewed committed-history pushes,
`42git status` and `42git push dev|vog|all`, folder opening and project dialog
improvements. See [the Git guide](docs/project-git.md). Both destinations receive
the committed history. Native Vogsphere and Linux/macOS tester checks were
confirmed by the maintainer on 2026-10-29; automated candidate checks are separate.
The existing one-button tester implementation is included; its 0.6.0 rework is
still pending.

Release CI, exact-revision compatibility, package hashes and the actual
0.4.4 → 0.5.0 update path passed; see DEV_CHANGELOG.md.

The detailed design below remains a roadmap: source-choice UI, staging/commits,
separate Vogsphere file selection, extended CLI and project-list redesign are
not all implemented in this candidate. Preserve these tasks for follow-up work.

### Recovery and configuration

- [ ] Inspect the local folder and both remotes before first editor launch.
  When both remotes contain work, require a choice between development and
  Vogsphere, with no default selection. Show URL, branch, latest commit and date.
  Choosing a recovery source does not overwrite the other remote.
- [ ] Recover into an empty folder. For files without a Git repository, offer
  **Use local**, **Other folder**, **Cancel** with explanatory text. Use local
  leads to staging/commit review; it does not automatically commit everything.
- [ ] Preserve existing checkouts, local files, commits, branches and remote
  configuration. Show uncommitted changes and offer committing through the TUI
  or recovery elsewhere. Inspect a clean checkout's history/remotes before
  connecting it. An unfinished merge/rebase must be resolved before recovery.
  Never automatically delete files, stash changes, reset branches or force-push.
- [ ] Review configured remote URLs and destination branches during setup;
  never silently replace an existing URL. Show the actual destination branch
  instead of assuming the development remote uses main or Vogsphere uses master.

### Development commits and Vogsphere selection

- [ ] Keep normal Git staging/commit behavior for development work, including
  personal tests, notes and tools. Provide a TUI changes list, diff preview,
  Stage/Unstage actions and a commit-message field. Selecting rows/checkboxes
  chooses paths for those actions; committing uses the staged changes.
- [ ] Configure Vogsphere inclusion in a separate TUI file tree, saved per project.
  Include only selected files/folders; staging a development file does not select
  it for Vogsphere. Private development files must not enter Vogsphere history.
  File selection does not delete local files or alter development inclusion.
- [ ] A selected folder includes new children unless explicitly excluded; highlight
  new files during push review. New files outside selected paths stay excluded.
  Deleting or excluding a previously pushed file appears under Deleted and needs
  confirmation, including during the first selection of an existing repository.
  Removing a file from the next version does not erase it from older history.
- [ ] Push from a committed development revision and show uncommitted changes as
  excluded. Never silently stage/commit on push. Preserve the development checkout
  while preparing a separate Vogsphere version/history containing selected files.
  Different histories are expected; block for unexpected remote changes or
  unresolved conflicts, not merely because the histories differ. Resolve these
  cases explicitly, without overwrite or force-push.

### Push review and results

- [ ] Offer **Push dev**, **Push Vog**, **Push all**. Vogsphere push means Git
  publication only: it must not mark the project finished on Intra, close
  registration or request evaluation. Do not use the ambiguous submit command.
- [ ] Review source commit, complete destination URL/branch, included/excluded
  files and Added/Changed/Deleted counts. Provide **View diff**, **Files**,
  **Push**, **Cancel**; show the diff against the reviewed Vogsphere branch.
  Reuse the development commit message for Vogsphere with an editable field.
  If no changes exist, show **Up to date** without making a redundant commit.
- [ ] Push all reviews both destinations once, then pushes development first.
  Stop if development fails. If only Vogsphere fails, retain development success
  and offer **Retry Vog**; report each destination independently inside the TUI.
- [ ] Recheck the destination after uncertain/interrupted results before retrying:
  the remote may already contain the pushed commit. If it changed unexpectedly
  since review, refresh the comparison and require a new review. Do not silently
  retry against a changed destination or overwrite another writer's work.

### Initial `42git` command set

Share the TUI's project configuration and Git operations. Resolve the configured
project from any subdirectory and explain clearly when none is found. Use concise
help with examples and distinguish development staging from Vogsphere inclusion.

| Command | Agreed behavior |
| --- | --- |
| `42git`, `42git help`, `42git --help` | Display general help and the typical workflow. |
| `42git <command> --help` | Display command-specific help and examples. |
| `42git status` | Show branch, local/staged changes, remote status and Vogsphere readiness. |
| `42git add <paths...>` | Stage paths using ordinary Git semantics; `add .` is relative to the current directory and respects `.gitignore` for untracked files. |
| `42git commit -m "message"` | Commit staged changes. |
| `42git commit` | Open the configured Git commit editor. |
| `42git push dev` | Push committed development work to its configured destination. |
| `42git push vog` | Use the saved inclusion selection, review changes and confirm the Vogsphere push. |
| `42git push all` | Review both destinations, push development, then Vogsphere. |

- [ ] Implement these commands and help in the initial version. If no Vogsphere
  selection exists, direct users to configure it in the TUI instead of guessing.
  Show the destination and branch before pushing. Keep branching/merging as
  ordinary Git operations; the initial command set does not wrap all of Git.

### Project interface and list cleanup

- [ ] Use short action labels with explanations nearby. Provide Overview/Git
  navigation, preserve access to existing Testers, Activity and registration/team
  controls, and add **Folder** beside **Editor** for the platform file explorer.
  Keep Git progress/results inside the TUI. The dedicated tester workspace
  remains 0.6.0 work, not an implied addition to this release.
- [ ] Remove the separate **Details** button/modal after moving catalog/description
  information to Overview, branch/remotes/status to Git, and folder/configuration
  information beside **Editor**, **Folder**, **Config**. Provide **Intra** directly
  in Overview. Preserve all currently useful information and account controls.
- [ ] Simplify project rows to a name and concise status/score line. Remove
  PATH SET/SETUP/PATH MISSING from the list; put setup and **Folder missing**
  beside folder controls. Rename the name's active-project marker to **Current**
  to distinguish it from academic progress. Keep a compact **Exam** indicator.
- [ ] Use the current Intra attempt in the correct account/curriculum context,
  ahead of an older result. Show older scores in Overview or Activity. Use
  existing attempt/registration data where available; validate coverage before
  promising statuses. Identify outdated observations (for example, **Cached**);
  unknown data must not imply inactivity, eligibility or a confirmed result.

| Observed academic state | List label |
| --- | --- |
| Creating a group | Creating team |
| Searching for a group | Looking for team |
| Waiting to start | Not started |
| In progress | In progress |
| Waiting for correction | Awaiting evaluation |
| Finished, validated | Passed · score, when known |
| Finished, not validated | Failed · score, when known |
| Finished, validation unknown | Result pending |
| Confirmed available / locked / inactive | Available / Locked / Inactive |
| Unknown | Unknown |

Git push success never changes academic status by itself.

### Implementation details and validation still required

- [ ] Finalize separate Vogsphere commit ancestry/preparation, persistence of file
  selections and interrupted-operation recovery without changing the agreed
  safeguards. Define behavior for empty remotes and a single populated remote.
- [ ] Finalize keyboard navigation, file-tree selection, diff scrolling and
  small-terminal layouts; maintain French/Spanish coverage and shared widgets.
- [ ] Validate recovery from either remote, development-only/empty repositories,
  local/dirty checkouts, expected history differences, unexpected remote updates,
  unfinished merge/rebase, inclusion/deletion review, authentication/network
  failures, uncertain results, rejected pushes and partial success using disposable
  repositories. Verify current-attempt precedence, freshness and unavailable data.
- [ ] Run focused Git/UI/CLI regressions and required CI on the exact candidate;
  complete package, installer and compatibility checks before publication.
  Review already-merged tester code explicitly when selecting the 0.5.0 candidate;
  scheduling its rework for 0.6.0 does not validate or remove that code.

## 0.6.0 — Testers and update reliability

Status: **workspace and result infrastructure implemented; tester/runtime expansion and release validation ongoing**.
Latest published stable release is 0.5.2. This roadmap does not bump the package
version or authorize publication.

| Item | Integration status | 0.6.0 scope |
| --- | --- | --- |
| One-button Francinette setup/run on Linux and macOS | Published in 0.5.0 (PR #13, #38) | Main feature |
| Modular testers with lighter setup and an in-TUI workspace | Workspace/results implemented; native push_swap added, platform validation pending | Rework the existing tester feature |
| Stable update check on every startup, then every 12 hours while running | Published in 0.4.2 through PR #19 | Preserve and regression-test |
| Tester instructions and French/Spanish translations | Merged with the tester feature | Include |
| Backend storage, backup and connection encryption | Planned; implementation and deployment verification pending | Priority security work alongside 0.6.0 |
| GitHub/Discord Settings buttons and persistent one-time reminders | Planned for 0.7.0 | Deferred beyond 0.6.0 |

### Agreed tester rework

- [ ] Keep one Run action and extend the existing TOML catalog for multiple
  project/module-specific testers, including Python modules and push_swap.
  Define pinned sources, supported platforms, prerequisites, preparation/run
  commands and execution method. Add result readers only where structured
  summaries require them; ordinary tester additions should use definitions.
- [ ] Prefer validated native execution with private tester directories and
  Python virtual environments where appropriate. Retain a shared Linux container
  runtime for testers needing Linux-specific tools; Docker Desktop must not be
  mandatory for every tester. Evaluate a headless macOS runtime such as Colima,
  including installation prerequisites, lifecycle and resource use, before
  selecting it. Do not silently change environments or omit checks.
- [ ] Validate a lighter Francinette setup against the pinned source on Linux
  and macOS, including Intel/Apple Silicon support and memory-check tooling.
  Do not assume native execution preserves all checks. Preserve unprivileged
  setup, explicit prerequisite approval, retries and existing user configuration.
- [ ] Add a dedicated Testers workspace showing preparation/build/run stages,
  live scrollable output, cancellation, follow-output control and final results.
  Keep execution inside the TUI, including internal terminal emulation when
  required. Allow leaving and returning while a run continues; preserve the
  captured project and prevent concurrent conflicting operations.
- [ ] Show duration, available test counts/failures, Run again and Save log.
  Preserve full logs and distinguish test failures, setup failures, cancellation
  and unreadable results. Do not equate a successful process exit with all tests
  passing; show percentages only when progress is measurable.
- [x] Use a disposable project copy by default so tester builds/cleanup preserve
  the working folder. Native runs require explicit confirmation explaining that
  a private directory or virtual environment does not sandbox executed code.

Current implementation: pinned Francinette (Docker) and ft_ps_tester for push_swap
(native Python environment with definition-driven build/run commands). The native
adapter has synthetic PTY/result/cancellation tests. Full Linux/macOS platform
validation, a Francinette summary reader, dedicated stage indicators and the
headless-container/runtime evaluation remain pending.
- [ ] Prove the complete flow with Francinette and one contrasting tester
  (push_swap or a Python module tester), including setup/retry, cancellation,
  output capture, result handling and French/Spanish interface coverage.

Existing tester implementation checks and remaining native-validation gates are
recorded in the [tester validation tracker](docs/superpowers/plans/2026-10-28-release-0.5.0.md).
These checks do not validate the pending 0.6.0 rework.

### Priority backend data protection — target 0.6.0

Status: **planned; no production encryption or recovery validation claimed**.
The backend owns implementation and operations; client/backend versions remain
independent. Complete this work as soon as possible, before or alongside 0.6.0.

- [ ] Encrypt all PostgreSQL storage through encrypted volumes or the database
  provider's storage encryption, covering data files, indexes, WAL/transaction
  logs, temporary files, replicas and snapshots wherever they are stored. Record
  deployed coverage and key ownership; preserve existing data during migration
  and verify recovery before retiring the previous storage.
- [ ] Encrypt backups separately, including logical dumps and archived WAL.
  Keep keys in restricted secret/key management, separate from backup access,
  with recoverable key backups and documented retention and rotation. Replace
  any backup example that produces an unencrypted dump with a verified encrypted
  procedure. Restore an encrypted backup into an isolated environment and record
  integrity, credential decryption and session-revocation/reconciliation checks,
  achieved recovery time and recovery point before marking this complete.
- [ ] Require TLS with trusted certificate and hostname verification for every
  production PostgreSQL connection, including API, workers, migrations and
  backup/restore tools. Reject plaintext and invalid/untrusted certificates;
  test successful verified connections and those rejection cases. Keep local
  development exceptions explicit and unavailable in production configuration.
- [ ] Preserve credential encryption and device-token hashing. Assess private
  account, registration, preference and social payloads for protection against
  database-only compromise; selectively encrypt those requiring it before they
  reach PostgreSQL. Include duplicated/cache copies in that assessment, record
  remaining readable identifiers/search metadata, and preserve query behavior.
  Any field-encryption migration needs tested backfill, key rotation, recovery
  and compatible rollback without data loss.
- [ ] Keep existing API contracts and supported clients compatible. Deploy and
  verify backend/storage changes before announcing these protections with
  0.6.0; record exact backend revision/image, storage/TLS evidence and restore
  results. Storage encryption protects offline media, not an authorized database
  connection or a compromised running backend; do not describe it as end-to-end
  encryption. Block the security-complete claim until all required checks pass.

### Integration and release checklist

- [x] Merge the single Run action, unprivileged setup/retries, tester instructions
  and French/Spanish translations.
- [x] Deliver automatic update discovery in 0.4.2 through PR #19, carrying the
  update fix from superseded PR #18. Preserve opt-out, offline behavior,
  managed-install protections and post-exit installation.
- [x] Record shipped update behavior in CHANGELOG.md and retain the unreleased
  tester notes and validation in DEV_CHANGELOG.md.
- [ ] Complete the agreed tester rework above; PR #13 alone does not validate it.
- [ ] Validate real native/container tester setup and execution on school Linux
  and native macOS, including installation/retry, image builds where applicable,
  and the selected headless runtime's startup/cleanup behavior.
- [ ] Run the tester and installation-updates regression scopes and required CI
  on the exact integrated release candidate; verify locale coverage.
- [ ] Complete package/version/installer checks and the compatibility checks
  required by [API compatibility](docs/api-compatibility.md), recording exact
  revisions and healthy deployed-backend evidence where required. The tester
  rework requires no backend change; the separate priority data-protection scope
  above requires backend/infrastructure rollout and may require storage/schema
  migrations, while preserving the API contract.
- [ ] Complete and verify the priority backend data-protection checklist before
  presenting 0.6.0 as delivering those protections; planning and client CI alone
  are insufficient evidence.
- [ ] Prepare the 0.6.0 version and final release notes after review, then obtain
  separate publication authorization and verify published artifacts/update path.

Standalone binaries, a broader README redesign and the complete keyboard/keymap
redesign are separate future work; they do not expand this release's scope.

## 0.7.0 — Dashboard and interface cleanup

Status: **scope agreed; implementation and release validation pending**.

- [ ] Rework the dashboard student-profile card.
- [ ] Replace the dashboard Cluster Map card with a log-time heatmap showing
  time connected to campus workstations, not editor coding time. Confirm source
  coverage and reuse existing session data where available; define local-day
  boundaries, sessions crossing midnight and ongoing sessions. Show daily totals
  and distinguish missing/stale data from zero time. Preserve access to the
  dedicated Cluster Map view and keep coding-time statistics clearly labelled.
- [ ] Add hover information to the progress bar and details below weekly coding.
- [ ] Remove the dashboard's top-right connected-account/local-projects label;
  verify its exact location separately from the app header changed in 0.4.0.
- [ ] Polish project details beyond the 0.5.0 Git/interface work and move
  View project away from the list's top edge.
- [ ] Book a correction/evaluation slot for an eligible project from its details:
  show available times, review the selected slot and confirm the booking. Reuse
  existing project/evaluation context; handle unavailable slots and uncertain
  booking results by refreshing before retrying. Existing Correction Slots
  availability editing does not cover booking an evaluation for one's project.
- [ ] Show upcoming evaluations on the dashboard, both as evaluator and evaluated
  student, with project, counterpart, local date/time and a link to the details.
  Reflect rescheduling/cancellation and distinguish loading, empty and stale data.
- [ ] Display Intra events for the selected campus in an agenda list and weekly
  calendar, with a detail view and a link to the event on Intra. Validate source
  coverage and account visibility, use explicit local times and distinguish
  loading, empty, unavailable and stale data. Assess reuse of the correction
  calendar's navigation/layout without carrying over slot-editing behavior.
- [ ] Include upcoming evaluations in the personal agenda, both as evaluator and
  evaluated student, reusing the dashboard's evaluation data. Visually distinguish
  Intra events from evaluations and provide filters for each; reflect schedule
  changes/cancellations consistently across the agenda and dashboard.
- [ ] Standardize danger-button styling and hover, including the tester removal
  control. One-button tester setup is already implemented for 0.6.0; do not
  duplicate it here or assume its removal styling is complete.
- [ ] Rework the full Settings interface: review category grouping, navigation,
  labels and layout, including simplifying Curriculum and Appearance. Preserve
  existing preferences, account/curriculum scope and validation; make save state
  and feedback clear. Validate keyboard access, small-terminal layouts and
  French/Spanish coverage. Keep the later Discord RPC toggle within this structure.
- [ ] Stabilize time-tracking extensions and their installation for Vim, Neovim,
  VS Code and Zed. Review each existing integration, provide reproducible install,
  update and uninstall instructions, and make executable-path setup and a working
  heartbeat check clear from Settings. Preserve editor configuration and recorded
  time; handle idle/resume, editor restarts, multiple windows and missing `42tui`
  without duplicate time or disruptive errors. Preserve local tracking without
  reading file contents or retaining file paths. Validate fresh installation,
  upgrade/removal and time attribution on Linux/macOS for each supported editor.
- [ ] Add a GitHub button in Settings opening the project repository, plus a
  one-time reminder to star the project, remembered across app restarts.
- [ ] Add a Discord button in Settings opening the project's Discord invite, plus
  a one-time reminder to join the community, remembered across app restarts.
  Confirm the official invite URL before implementation.
- [ ] Improve friend-profile, project/evaluation detail loading; measure remaining
  delays rather than treating the caching shipped in 0.3.0 as completion.

## 0.8.0 — Notifications, presence and pokes

Status: **scope agreed; implementation and release validation pending**.

- [ ] Add a unified notification inbox with a bell left of the DND button,
  integrating activity notifications, friend requests and other existing sources.
- [ ] Include evaluation bookings, rescheduling, cancellations and upcoming
  evaluation reminders in the inbox, linking to the relevant project/evaluation.
  Define reminder timing, read/deduplication behavior and DND handling; keep the
  dashboard and notifications consistent after schedule changes.
- [ ] Add user-selected Intra event reminders, time-change and cancellation
  notifications to the unified inbox, respecting DND. Define reminder choices,
  subscriptions and deduplication; link back to the event and keep notifications
  consistent with the 0.7.0 agenda after refreshes and schedule changes.
- [ ] Show online, inactive, DND and offline using differently colored round
  Unicode indicators in friends lists, replacing rank numbers outside ranking mode.
  Define presence source, idle/offline timing and DND behavior before implementation.
- [ ] Add optional Discord Rich Presence (RPC), disabled by default, showing
  42TUI and the current section/activity while navigating. Provide a Settings
  toggle; exclude account identifiers, private project details and messages.
  Define idle/DND behavior, clear activity on disable/exit, and handle Discord
  being unavailable or reconnecting without blocking the TUI. Validate on Linux
  and macOS; this is separate from in-app friend presence and the Discord invite.
- [ ] Replace the poke inbox below search with a direct Send poke action, matching
  friend details; make each poke a message viewed once and define read semantics.
- [ ] Simplify the poke sender modal, remove excessive details below the message
  and separate Cancel and Send poke.
- [ ] Replace the large poke popup with a compact adaptive notification containing
  the sender's portrait, username and message below the portrait.

## 0.9.0 — Profiles and clubs

Status: **scope agreed; implementation and release validation pending**.

- [ ] Provide both a compact profile modal and a full detailed profile page with
  dashboard-style information.
- [ ] Allow profile customisation and show the viewed user's choices to visitors.
- [ ] Enlarge the user's portrait when clicked in profile details.
- [ ] Rework club lists and club UI/logic; add discovery for open and request-to-join
  clubs. Keep private clubs accessible through delegate/owner invitations only,
  with invitations delivered through the notification inbox introduced in 0.8.0.

## Further updates — Versions and dates undecided

Status: **captured for design; versions and dates undecided**.

- [ ] Simplify Git collaboration on group projects: guide teammates through
  connecting a shared development repository, pushing their committed work and
  pulling each other's changes. Reuse the existing Git review/actions and show
  incoming/outgoing commits, destination branches and synchronization status.
  Explain divergent histories and conflicts with guided resolution steps;
  preserve local edits and require review before changes, without automatic
  overwrite or force-push. Keep shared development synchronization separate from
  Vogsphere publication. Detailed design, version and date remain undecided.
- [ ] Later, support Intra event registration/unregistration from the TUI after
  validating available capabilities and account permissions. Review and confirm
  actions, reflect capacity/eligibility where known and refresh uncertain results
  before retrying. Include club events in the agenda after the club rework,
  preserving club visibility/permissions and distinguishing them from Intra events.
- [ ] Prepare a stable release for all 42 campuses: audit features currently
  tailored to Angouleme and remove campus-specific assumptions using the selected
  campus context and its available capabilities. Validate feature coverage across
  campuses, preserve Angouleme behavior and clearly indicate unavailable features
  rather than showing data from another campus. Confirm readiness per campus
  before claiming stable support across the network.
- [ ] Support specific curricula and short programmes, including Piscine Discovery
  and work-experience placements for seconde students (stages de seconde). Audit
  available curriculum data and adapt onboarding, project/progress displays and
  eligible actions to the selected programme instead of assuming the common core.
  Preserve account/campus/curriculum boundaries and validate each programme with
  representative fixtures before claiming support.
- [ ] Add a project readiness checklist before evaluation: review required files,
  Git state, compilation and tester results, with links to resolve issues. Reuse
  existing project/Git/tester data, distinguish missing or stale checks from
  passing results, and make clear that readiness does not guarantee validation.
- [ ] Add opt-in peer study matching for students working on the same project,
  including study sessions and mock evaluations. Let users control visibility
  and withdraw availability; respect campus/curriculum context and existing
  blocking/privacy rules.
- [ ] Add a workload planner combining personal project targets, booked evaluations
  and declared availability into a weekly plan. Reuse evaluation data and keep
  personal targets distinct from official deadlines; handle schedule changes and
  overlapping commitments without silently changing bookings.
- [ ] After 0.10.0 (exact version and detailed design undecided), extend the
  planner/personal agenda with a milestone view based on the student's selected
  pace and current progress. Suggest a project sequence and target submission
  dates to stay on schedule, accounting for prerequisites, availability and
  evaluation time. Distinguish official milestone deadlines from estimated
  project durations and suggested dates; show uncertainty or an infeasible plan
  rather than guaranteeing timely completion. Define pace/deadline sources and
  campus/curriculum rules during later design, with user review when replanning.
- [ ] Add exam practice mode with timed sessions in disposable folders, saved
  results and a review of recurring mistakes. Use permitted practice material,
  keep personal project files intact and support interruption/restart; distinguish
  practice results from official exam outcomes.
- [ ] Add integration diagnostics covering editor heartbeats, executable paths,
  backend connectivity and stale data. Reuse integration setup checks, show
  actionable fixes and provide a reviewable sanitized report excluding credentials,
  personal paths and private account/project data; do not send it automatically.
- [ ] Add data export and backup for notes, time records and preferences, with
  safe restore when changing machines. Exclude credentials, validate imports,
  preview conflicts and preserve existing data on cancellation or failure;
  document backup contents and format compatibility.
- [ ] Explore optional Obsidian integration complementing existing project dev
  logs/notes: associate a project with a chosen vault folder, export selected notes
  as Markdown and open the corresponding note in Obsidian. Support explicit import
  of external edits with conflict review; preserve note identity, timestamps and
  user content without duplicate imports or silent overwrites/deletions. Consider
  an opt-in daily dev-log summary linking project notes, recorded work sessions
  and next steps. Reuse Markdown export/backup work, keep built-in notes usable
  without Obsidian, and validate vault paths, missing/moved files and Linux/macOS
  app-opening behavior before delivery; avoid a required plugin or cloud service.
- [ ] Add an optional music player integrated into the TUI, with provider
  selection targeting Spotify, Deezer, SoundCloud and YouTube. Reuse maintained
  open-source players/libraries after verifying license compatibility, dependency
  redistribution and attribution requirements. Assess playback support, provider
  terms, authentication and subscription requirements per provider before promising
  support. Provide guided installation/setup and in-TUI playback controls while
  navigating, with safe credential storage and graceful handling of unavailable
  providers. Validate installation, playback and cleanup on Linux/macOS; choose
  the initial supported providers after feasibility review.
- [ ] Integrate the actual Intra goodies shop and wallets; establish available
  integration capabilities before committing to delivery.
- [ ] Explore optional game modules within clubs, depending on the club rework
  planned for 0.9.0. Start with a chess club: play chess inside the TUI, retain
  match history and provide club rankings with Elo ratings. Reuse a maintained,
  license-compatible chess library for legal moves and game outcomes; define
  time controls, draws, resignation and interrupted-game behavior before delivery.
- [ ] Add a babyfoot (table football) club module for recording players/teams,
  live scores and completed matches, with history and Elo-based rankings. Define
  singles/doubles rating rules, result confirmation and correction handling;
  keep chess and babyfoot ratings separate and avoid rating unfinished or
  duplicate matches.
- [ ] Provide a small mobile-friendly companion web app for the babyfoot club:
  select players/teams, start a match, count points, undo scoring mistakes and
  confirm the final result. Keep scores, history and rankings consistent with
  the TUI; handle concurrent scorers and interrupted connections without duplicate
  points/results. Reuse club membership/permissions, restrict score changes to
  authorized participants and assess backend/authentication/hosting needs before
  committing to delivery. Keep club rankings scoped to the relevant club.
- [ ] Later, extend club games with opt-in inter-campus rankings for babyfoot,
  chess and other supported games available locally. Record each participating
  campus's confirmed games/equipment (such as a babyfoot table); unavailable or
  unknown availability must not count as a loss or zero score. Build on validated
  club results and retain local rankings. Define whether rankings compare players,
  teams or campuses, common rules and comparable rating pools before combining
  results; independent local Elo ratings are not directly comparable. Depends on
  stable multi-campus support and the relevant club-game modules.
- [ ] Design a separate TUI currency, earning quests/activities and a shop for
  upgrading profile customisation. Depends on the profile work above.
- [ ] Explore WIP, an animated pixel-art royal otter companion with multiple
  states, movement in the TUI and emotes; scope its behavior in a dedicated design.

For future campus/curriculum/social/profile/club/shop features requiring API changes, assess contracts
and older-client compatibility, validate both repositories separately and deploy
required compatible backend changes before the consuming client release. See
[API compatibility](docs/api-compatibility.md). These scopes do not imply backend
implementation or deployment is complete.

## 0.4.4 — Notes, timers and updates before launch

Status: **published and verified** on PyPI and GitHub. Tag `v0.4.4` points to
`bbb619db0cfd6e64ad7c6e8e6661b945327f87fd`, based on v0.4.3; PR #28 integrated
candidate ancestry through `18eea9c` while retaining main's 0.5.0 tester work.

- [x] Include pre-launch updater, dirty-note Save/Discard/Cancel and save-failure
  protection, dashboard teardown guard and serialized manual timers.
- [x] Include project-workflow roadmap documentation as planning only.
- [x] Run 824 candidate tests (820 passed, four optional skips), archived package,
  rebuild/installed smoke, all21 PR checks and three compatibility pairs.
- [x] Obtain tag approval and publish v0.4.4 through workflow40762004464.
- [x] Verify all seven GitHub assets/checksums and exact byte equality of PyPI and
  GitHub distributions against original CI artifacts; actual update from0.4.3
  to0.4.4 preserved disposable local data and passed CLI/resource smoke.
- [x] Advance verified baseline to0.4.4; retain pending minor tester work.

Existing overlapping manual-timer history is not rewritten. Hosted installer
access/deployment remains pending under0.4.3 below. No new backend deployment.

## 0.4.3 — Automatic installer shell setup

Status: **package published and verified** on PyPI and GitHub.
Tag `v0.4.3` points to isolated candidate
`67be64839c2cd921898a5ac7b1ddde6441a42ddc`, based on v0.4.2.
PR #24 merged as `261e801`, preserving candidate ancestry and pending 0.5.0 work.
Release workflow `40744295147` succeeded on attempt 3.

- [x] Configure PATH and 42goto in managed blocks in Bash and Zsh startup files;
  support ZDOTDIR, repeat installation, existing user settings and macOS Bash 3.2.
- [x] Include the author's About this project note at the top of the README.
- [x] Prepare version 0.4.3 and matching notes without the minor tester feature.
- [x] Run 805 archived-candidate tests (801 passed, four optional skips), package
  and installed-resource checks, real installer/uninstaller smoke and three-pair
  compatibility against e917aca with 0.4.0 as oldest supported client.
- [x] Pass all 21 integration CI checks and release CI. Friends UI teardown and
  account UI navigation checks needed retries; see DEV_CHANGELOG for details.
- [x] Obtain tag/publication authorization; publish original CI artifacts.
- [x] Verify all seven GitHub assets/checksums and byte equality of PyPI/GitHub
  distributions against original CI artifacts; actual 42tui update from 0.4.2 to
  0.4.3 preserved disposable local data and passed installed CLI/resource smoke.
- [x] Advance the package baseline to verified 0.4.3, retaining 0.5.0 tester work.
- [ ] Deploy the hosted installer scripts together through Dokploy and verify
  exact bytes/helper hashes. Deployment is authorized; access is unavailable.
  Existing Docker-host SSH authentication failed; the current endpoint is healthy
  but still serves the older install.sh/install.ps1/install.py.

## 0.4.2 — Updates, resumption and first-run instructions

Status: **published and verified** on PyPI and GitHub.
Tag `v0.4.2` points to isolated candidate
`0f3f4c3642e11f39a958fbe89e09a0d4e868b1d9`, based on v0.4.1.
PR #19 merged as `b758138`, preserving candidate ancestry and later tester work
on main for 0.5.0. Release workflow `40603624612` succeeded.

- [x] Carry automatic update discovery from PR #18 without tester changes.
- [x] Exclude active/recent/selected/fallback exams from Continue working.
- [x] Preserve exams in the catalog and curriculum progress.
- [x] Correct the README's first-run connection requirement and offline behavior.
- [x] Prepare package version 0.4.2 and matching user-facing notes.
- [x] Focused regressions: 28 dashboard and 70 installation-updates tests passed;
  clean archived package/version/installed smoke checks passed.
- [x] Independent review, PR #19 and main integration; superseded PR #18 closed.
- [x] Final PR CI passed all 21 jobs (40602985868); exact-candidate compatibility
  passed all three pairs (40600874913), including supported client 0.4.0.
  The paired scenario covers synthetic friend-preview HTTP, not the entire API.
- [x] Obtain separate authorization and push v0.4.2 on the exact isolated candidate.
- [x] Tag workflow passed all release checks and published to PyPI/GitHub.
- [x] Verify all seven GitHub assets/checksums and exact byte equality of PyPI and
  GitHub distributions against original CI artifacts.
- [x] Run actual `42tui update` from 0.4.1 to 0.4.2 in disposable unpinned uv tools;
  preserve local test data and pass installed-package CLI/resource smoke.
- [x] Advance DEV_CHANGELOG baseline to 0.4.2, retaining unreleased 0.5.0 tester work.

## 0.4.1 — Correction-slot start window

Status: **published and verified** on PyPI and GitHub.
Tag `v0.4.1` points to `30e124509489c5017cacc5320ecc7f23ab395273`.
Release workflow `40597765312` succeeded after retrying only GitHub publication
with its original CI artifacts. Later tester features remain unreleased for 0.5.0.

### Main fixes

- [x] Use current quarter-hour rounded down + 30 minutes: 10:18 → 10:45.
- [x] Align calendar selection and Add availability with that limit.
- [x] Recheck the start when publishing and before dispatch; retain deletion of
  nearby existing availability.
- [x] Align backend validation without changing payloads or error codes.
- [x] Update French/Spanish messages and user-facing release notes.
- [x] Commit fixes: client `82f583b`; backend `880ce27`.

### Local validation completed

- [x] Client correction scope: 52 tests passed; locale tests: 2 passed.
- [x] Backend suite: 472 passed, 34 skipped, no failures.
- [x] Backend TypeScript check, Prisma generation and schema validation passed.
  Schema validation used a dummy database URL; it did not connect to PostgreSQL.
- [x] Postman HTTP simulation: 2 tests passed, including 10:30 rejected without
  upstream dispatch and 10:45 accepted at 10:18. This uses synthetic Intra data.

### Release verification completed

- [x] Independently review both fixes and open linked PRs:
  [client #12](https://github.com/HeduroFR/42tui-client/pull/12), backend #5.
- [x] Obtain green backend CI and merge backend #5 as `e917aca`.
- [x] Obtain green client CI and merge client #12 as `4e48e9b`.
  [CI run 40590113023](https://github.com/HeduroFR/42tui-client/actions/runs/40590113023)
  passed all 21 jobs, including 14 regression scopes and four platforms. The
  merged candidate has the same Git tree as the tested PR head `a3cfc09`.
- [x] Confirm the published 0.4.0 baseline in GitHub and align distribution
  documentation with the development changelog.
- [x] Select 0.4.0 as the oldest supported client for this release.
- [x] Run the initial three-pair compatibility workflow successfully:
  backend Actions run `40589486585` (client `0c22b9a`, backend `880ce27`,
  supported client 0.4.0, prior deployed backend `731b7cd`).
- [x] Refresh exact candidate/deployed backend evidence and run the three
  compatibility pairs described in
  [API compatibility](docs/api-compatibility.md). The existing friend-preview
  scenario alone does not verify correction-slot behavior.
  Original-candidate compatibility run `40590735918` passed all three pairs for
  candidate `4e48e9b` and deployed backend `e917aca`, with supported client 0.4.0.
  The readiness checker accepted the candidate receipt and manually observed
  Dokploy deployment evidence; neither is a signed attestation.
- [x] Verify correction-slot behavior: UI/model tests cover 10:18 → 10:45,
  rollover, stale-editor validation and nearby deletion. The exact CI wheel
  passed a real client-provider/Hono-route/service/transport roundtrip through
  local Postman: reject 10:30 without upstream write, save/decode 10:45, delete.
  Auth and Redis in that harness were synthetic; live Intra acceptance was not
  exercised. The CI wheel SHA-256 is
  `39d6fca61ddc1f7bad5108329f34d8e93cba7737e4b3483b6c371d3e3879e491`.
- [x] Deploy backend `e917aca` through Dokploy with separate authorization.
  Its API image ID is `sha256:d87af92f735c42324fd95a344e0be777cc3d84bdd19b93c4cdb8bfe9de08d7ef`.
  Deployment finished; deployed slot-source hash matches that revision; 22
  synthetic slot tests pass inside the API container. Read-only PostgreSQL
  SELECT 1, Redis PING and API health probes passed. No real Intra write was made.
- [x] Prepare version 0.4.1 and its CHANGELOG section with authorization; retain
  pending DEV_CHANGELOG entries until publication has been fully verified.
- [x] Validate `v0.4.1`, wheel/sdist contents, installed-package resources and
  entry points. CI covered package, installers, regressions and supported
  platforms; exact merged-candidate compatibility receipts passed. The tag
  workflow rebuilt and checked the exact authorized candidate before publishing.
- [x] Obtain original tag/publication authorization and push v0.4.1 at 4e48e9b.
  Workflow 40593923756 failed its friend UI assertion three times; no publication.
- [x] Validate corrected candidate 30e1245 and integrate its tests through PR #16.
  CI 40596753649 passed all 21 jobs; compatibility 40596520184 passed all three
  pairs. Clean archived package/version/smoke checks passed; runtime source is
  unchanged from the original tag.
- [x] Obtain authorization to replace the unpublished tag, reverify backend readiness,
  then publish the tested immutable client artifacts through the release workflow.
- [x] Verify both PyPI distributions and GitHub release assets/checksums, smoke
  test the published package and update path, then advance DEV_CHANGELOG to the
  verified 0.4.1 baseline while retaining any later changes.

Published release wheel SHA-256:
`8d3a5b36d4943184c1dcd57bf8adb69dc9eee25203ec004c174d11a3b0a7eabf`.

Verification evidence: all seven GitHub release assets match SHA256SUMS; wheel
and sdist are byte-identical to release CI artifacts and PyPI digests. Actual
`42tui update` upgraded a disposable uv installation from 0.4.0 to 0.4.1 and the
installed CLI/resources passed smoke checks. No live Intra write was performed.

## Future major milestone — Complete keyboard navigation and keymaps redesign

Status: **planned, version and date undecided**. This is a dedicated future
milestone, outside the numbered minor-release scopes above. Schedule it when the
main screens and user journeys have settled, before extending inconsistent keyboard conventions
to more features. Reassess the timing during each release planning cycle; do not
wait for an arbitrary version number.

- [ ] Audit navigation and bindings across every screen, pane and dialog,
  including actions currently requiring a mouse and terminal key conflicts.
- [ ] Redesign the keyboard interaction model and keymaps together: consistent
  movement, pane switching, search, primary actions, back/cancel and shortcuts.
- [ ] Make focus predictable on entry, after dialogs and after background refreshes;
  preserve text entry and accessible, visible focus throughout the app.
- [ ] Keep contextual help, shortcut hints and the command palette aligned with
  the actual available bindings, so users can discover actions without memorizing
  the entire keymap.
- [ ] Plan the transition for existing users: document changed shortcuts, retain
  compatible aliases where possible and explain unavoidable breaking changes.
- [ ] Validate the main journeys without a mouse, including small terminals,
  supported platforms and regression tests for focus, bindings and navigation.

Treat this as a major user-experience change. Choose the package version at
scoping time using the current pre-1.0/release policy; do not reserve 1.0.0,
5.0.0 or 7.0.0 solely for this work. No API major change is implied.

## Distribution and documentation backlog

- [ ] Add standalone Linux x64/ARM64 and macOS Intel/Apple Silicon builds to GitHub releases.
  - Set up dedicated packaging and tests for each supported platform and architecture.

- [ ] Rework `README.md` into an appealing, readable introduction for users.
  - Lead with what 42TUI is, who it helps and its key benefits.
  - Explain the main features with short, concrete examples of everyday use.
  - Add useful screenshots or a short demo with synthetic data.
  - Make installation easy to find, including requirements and platform support.
  - Walk through first launch, optional account connection and basic navigation.
  - Explain updates, uninstalling and common installation problems concisely.
  - Include a Thanks / Acknowledgements section crediting the repositories and
    projects used by 42TUI, with links and a short explanation of their role.
    Verify attribution and any license-required notices.
  - Keep development, architecture, test and release details in `CONTRIBUTING.md`
    and the relevant guides, with clear links from the README.
  - Use a clear visual hierarchy and concise language; verify all examples and
    avoid promising features or platform support that have not been validated.
