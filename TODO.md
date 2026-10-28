# TODO

## Urgent priority — Project Git workflow and proposed `42git` command

Status: **requested; implementation not started**. Prioritize this work before
0.6.0 dashboard polish. Target the next suitable minor release; assess inclusion
in 0.5.0 without treating its existing tester scope as validation of Git changes.
No package version bump or publication is authorized by this plan.

- [ ] Recover existing Vogsphere work before opening the editor for the first
  time: clone Vogsphere into a new/empty project folder when it holds the work,
  and fetch/inspect its history when a checkout already exists. The current
  setup clones the development remote but only configures the Vogsphere remote.
- [ ] Preserve existing local files, commits, branches and remote configuration.
  Resolve divergent development/Vogsphere histories explicitly; never silently
  overwrite work, reset branches or force-push to recover a project.
- [ ] Offer Push dev, Push Vogsphere and Push all in the project Git controls.
  Show the destination and branch before dispatch and the result per remote;
  Push all must report partial success and allow retrying the failed destination.
- [ ] Define the branch/commit rules before implementation: which committed work
  is published to each destination, how work reaches Vogsphere's master branch,
  and what happens with uncommitted changes or divergent remote history.
- [ ] Evaluate a `42git` companion command alongside `42goto`, sharing the TUI's
  project Git operations. Proposed initial interface: `42git status`,
  `42git push dev`, `42git push vog`, `42git push all`. Resolve the current project
  clearly and fail clearly outside a configured project; CLI details remain a
  proposal pending design. Push actions must not silently stage or commit files.
- [ ] Add Open in file explorer beside the existing project folder/editor actions
  on supported platforms, with clear errors for missing folders or unavailable tools.
- [ ] Validate recovery from Vogsphere, development-only and empty repositories,
  existing/dirty checkouts, divergent history, authentication/network failures,
  rejected pushes and partial success using disposable repositories.

## 0.6.0 — Dashboard and interface cleanup

Status: **scope agreed; implementation and release validation pending**.

- [ ] Rework the dashboard student-profile and cluster-map cards.
- [ ] Add hover information to the progress bar and details below weekly coding.
- [ ] Remove the dashboard's top-right connected-account/local-projects label;
  verify its exact location separately from the app header changed in 0.4.0.
- [ ] Rework project details and move View project away from the list's top edge.
- [ ] Book a correction/evaluation slot for an eligible project from its details:
  show available times, review the selected slot and confirm the booking. Reuse
  existing project/evaluation context; handle unavailable slots and uncertain
  booking results by refreshing before retrying. Existing Correction Slots
  availability editing does not cover booking an evaluation for one's project.
- [ ] Show upcoming evaluations on the dashboard, both as evaluator and evaluated
  student, with project, counterpart, local date/time and a link to the details.
  Reflect rescheduling/cancellation and distinguish loading, empty and stale data.
- [ ] Standardize danger-button styling and hover, including the tester removal
  control. One-button tester setup is already implemented for 0.5.0; do not
  duplicate it here or assume its removal styling is complete.
- [ ] Simplify Curriculum and Appearance settings.
- [ ] Add a GitHub button in Settings opening the project repository, plus a
  one-time reminder to star the project, remembered across app restarts.
- [ ] Add a Discord button in Settings opening the project's Discord invite, plus
  a one-time reminder to join the community, remembered across app restarts.
  Confirm the official invite URL before implementation.
- [ ] Improve friend-profile, project/evaluation detail loading; measure remaining
  delays rather than treating the caching shipped in 0.3.0 as completion.

## 0.7.0 — Notifications, presence and pokes

Status: **scope agreed; implementation and release validation pending**.

- [ ] Add a unified notification inbox with a bell left of the DND button,
  integrating activity notifications, friend requests and other existing sources.
- [ ] Include evaluation bookings, rescheduling, cancellations and upcoming
  evaluation reminders in the inbox, linking to the relevant project/evaluation.
  Define reminder timing, read/deduplication behavior and DND handling; keep the
  dashboard and notifications consistent after schedule changes.
- [ ] Show online, inactive, DND and offline using differently colored round
  Unicode indicators in friends lists, replacing rank numbers outside ranking mode.
  Define presence source, idle/offline timing and DND behavior before implementation.
- [ ] Replace the poke inbox below search with a direct Send poke action, matching
  friend details; make each poke a message viewed once and define read semantics.
- [ ] Simplify the poke sender modal, remove excessive details below the message
  and separate Cancel and Send poke.
- [ ] Replace the large poke popup with a compact adaptive notification containing
  the sender's portrait, username and message below the portrait.

## 0.8.0 — Profiles and clubs

Status: **scope agreed; implementation and release validation pending**.

- [ ] Provide both a compact profile modal and a full detailed profile page with
  dashboard-style information.
- [ ] Allow profile customisation and show the viewed user's choices to visitors.
- [ ] Enlarge the user's portrait when clicked in profile details.
- [ ] Rework club lists and club UI/logic; add discovery for open and request-to-join
  clubs. Keep private clubs accessible through delegate/owner invitations only,
  with invitations delivered through the notification inbox introduced in 0.7.0.

## Later initiatives — Shops, currency and WIP

Status: **captured for design; versions and dates undecided**.

- [ ] Integrate the actual Intra goodies shop and wallets; establish available
  integration capabilities before committing to delivery.
- [ ] Design a separate TUI currency, earning quests/activities and a shop for
  upgrading profile customisation. Depends on the profile work above.
- [ ] Explore WIP, an animated pixel-art royal otter companion with multiple
  states, movement in the TUI and emotes; scope its behavior in a dedicated design.

For future social/profile/club/shop features requiring API changes, assess contracts
and older-client compatibility, validate both repositories separately and deploy
required compatible backend changes before the consuming client release. See
[API compatibility](docs/api-compatibility.md). These scopes do not imply backend
implementation or deployment is complete.

## 0.5.0 — Testers and update reliability

Status: **validation in progress; native checks and candidate CI pending**. Latest published stable
release is 0.4.4. This roadmap does not bump the package version or authorize
publication.

Track each checklist item and validation evidence in the
[0.5.0 task tracker](docs/superpowers/plans/2026-10-28-release-0.5.0.md).

| Item | Integration status | 0.5.0 scope |
| --- | --- | --- |
| One-button Francinette setup/run on Linux and macOS | Merged, unreleased (PR #13) | Main feature |
| Stable update check on every startup, then every 12 hours while running | Published in 0.4.2 through PR #19 | Preserve and regression-test |
| Tester instructions and French/Spanish translations | Merged with the tester feature | Include |
| GitHub/Discord Settings buttons and persistent one-time reminders | Planned for 0.6.0 | Deferred beyond 0.5.0 |

### Integration and release checklist

- [x] Merge the single Run action, unprivileged setup/retries, tester instructions
  and French/Spanish translations.
- [x] Deliver automatic update discovery in 0.4.2 through PR #19, carrying the
  update fix from superseded PR #18. Preserve opt-out, offline behavior,
  managed-install protections and post-exit installation.
- [x] Record shipped update behavior in CHANGELOG.md and retain the unreleased
  tester notes and validation in DEV_CHANGELOG.md.
- [ ] Validate real tester setup, image build and execution on school Linux with
  accessible Docker/BuildKit and on native macOS, including installation/retry.
- [ ] Run the tester and installation-updates regression scopes and required CI
  on the exact integrated release candidate; verify locale coverage.
- [ ] Complete package/version/installer checks and the compatibility checks
  required by [API compatibility](docs/api-compatibility.md), recording exact
  revisions and healthy deployed-backend evidence where required. No new backend
  feature, schema migration or API change is required by this scope.
- [ ] Prepare the 0.5.0 version and final release notes after review, then obtain
  separate publication authorization and verify published artifacts/update path.

Standalone binaries, a broader README redesign and the complete keyboard/keymap
redesign are separate future work; they do not expand this release's scope.

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
milestone, outside the current 0.5.0 scope. Schedule it when the main screens and
user journeys have settled, before extending inconsistent keyboard conventions
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
