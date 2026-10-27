# TODO

## 0.4.1 — Correction-slot start window

Status: fixes committed and locally tested; not ready to publish. Package version
remains 0.4.0. This patch contains only the correction-slot fix; the dashboard,
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

- [ ] Review both fixes, push/open linked PRs when authorized, obtain required
  client/backend CI results and merge reviewed changes to each main branch.
- [ ] Confirm documentation agrees on the published 0.4.0 baseline; distribution
  documentation still describes it as unpublished.
- [ ] Define the oldest supported client and record exact candidate/current
  backend revisions; run the three compatibility pairs described in
  [API compatibility](docs/api-compatibility.md). The existing friend-preview
  scenario alone does not verify correction-slot behavior.
- [ ] Verify the correction-slot behavior with the candidate pair, including
  10:18 → 10:45, quarter-hour rollover, stale editor validation and deletion.
  Record any remaining real-Intra acceptance limitation explicitly.
- [ ] Deploy the compatible backend first, with separate authorization. Verify
  its actual deployed SHA/image digest and functional readiness, not only health.
- [ ] Prepare version 0.4.1 and its CHANGELOG section when authorized; retain
  pending DEV_CHANGELOG entries until publication has been fully verified.
- [ ] On the final reviewed release revision, validate `v0.4.1` with
  `release/check_version.py`; obtain package, installer, regression and supported
  platform checks from CI. Record compatibility evidence for the exact candidate.
- [ ] Obtain separate tag/publication authorization, reverify backend readiness,
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
