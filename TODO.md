# TODO

## 0.5.0 — Testers and update reliability

Status: **scope agreed; release preparation pending**. Latest published stable
release remains 0.4.1. This roadmap does not bump the package version or authorize
publication.

| Item | Integration status | 0.5.0 scope |
| --- | --- | --- |
| One-button Francinette setup/run on Linux and macOS | Merged, unreleased (PR #13) | Main feature |
| Stable update check on every startup, then every 12 hours while running | Implemented in `ee60aa2` on `fix/automatic-update-checks`; 70 update tests and 2 settings UI tests recorded as passed | Include; main integration and final candidate validation pending |
| Tester instructions and French/Spanish translations | Merged with the tester feature | Include |
| GitHub button in Settings and persistent one-time star reminder | Planning only on `docs/github-roadmap` | Deferred beyond 0.5.0 |

### Integration and release checklist

- [x] Merge the single Run action, unprivileged setup/retries, tester instructions
  and French/Spanish translations.
- [x] Implement and locally validate update reliability in `ee60aa2`: check on
  every stable startup despite a recent check, repeat every 12 hours and check
  immediately when automatic updates are re-enabled. Preserve opt-out, offline
  behavior, managed-install protections and post-exit installation. The development
  log records 70 installation-updates tests, 2 settings UI tests and read-only review.
- [ ] Integrate `fix/automatic-update-checks` into main after required PR checks.
- [x] Record both features' user-facing notes in CHANGELOG.md and validation
  records in DEV_CHANGELOG.md on this branch; preserve them through integration.
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
