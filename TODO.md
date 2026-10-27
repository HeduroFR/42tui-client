# TODO

## 0.4.1 — Correction-slot start window

Status: original tag v0.4.1 at 4e48e9b failed a UI-test race in three workflow
attempts; neither PyPI nor GitHub received a release. Backend remains deployed.
Corrected isolated candidate: `30e124509489c5017cacc5320ecc7f23ab395273`.
Runtime is identical to the original candidate; only tests/docs changed. Its
CI/compatibility and main integration are in progress. Replacing the unpublished
tag requires explicit authorization after validation.
This progress-only documentation follows that candidate and must not silently
replace the tested revision when creating the release tag.
The latest published version remains 0.4.0. This patch contains only the correction-slot fix; the dashboard,
exam filtering and other 0.5.0 work are outside this release.

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

### Remaining before release

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
  Final private compatibility run `40590735918` passed all three pairs for
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
  workflow must rebuild and check the exact authorized candidate before publishing.
- [x] Obtain original tag/publication authorization and push v0.4.1 at 4e48e9b.
  Workflow 40593923756 failed its friend UI assertion three times; no publication.
- [ ] Validate corrected candidate 30e1245 and integrate its tests into main.
- [ ] Obtain authorization to replace the unpublished tag, reverify backend readiness,
  then publish the tested immutable client artifacts through the release workflow.
- [ ] Verify both PyPI distributions and GitHub release assets/checksums, smoke
  test the published package and update path, then advance DEV_CHANGELOG to the
  verified 0.4.1 baseline while retaining any later changes.

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
