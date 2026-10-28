# TODO

## 0.5.0 — Testers and update reliability

Status: **scope agreed; release preparation pending**. Latest published stable
release is 0.4.3. This roadmap does not bump the package version or authorize
publication.

| Item | Integration status | 0.5.0 scope |
| --- | --- | --- |
| One-button Francinette setup/run on Linux and macOS | Merged, unreleased (PR #13) | Main feature |
| Stable update check on every startup, then every 12 hours while running | Published in 0.4.2 through PR #19 | Preserve and regression-test |
| Tester instructions and French/Spanish translations | Merged with the tester feature | Include |
| GitHub button in Settings and persistent one-time star reminder | Planning only; see the undated roadmap below | Deferred beyond 0.5.0 |

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

## Undated roadmap

- [ ] Add a GitHub button in Settings that opens the project's repository.
  - Show a one-time reminder to star the project on GitHub, remembering that it
    has been shown across app restarts.

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
