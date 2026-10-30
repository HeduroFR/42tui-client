# Development changelog

Latest release: **0.6.0** ([`v0.6.0`](https://github.com/HeduroFR/42tui-client/releases/tag/v0.6.0)).
Package version: **0.6.1** (release candidate).
Suggested next release: **0.6.1** at the maintainer’s direction, for optional
encrypted and session-only account storage and connection requirements. Security
review, campus validation and release checks remain outstanding.

This file tracks implemented changes since the latest successful release. Keep
published notes in [CHANGELOG.md](CHANGELOG.md). See
[distribution operations](docs/distribution.md#development-changelog).

## Changes since 0.6.0

- 2026-10-30: Remove repeated catalog facts from friend project descriptions,
  retaining them in the preview header. Patch impact; four friend project UI
  tests passed against this worktree. Release CI and candidate checks remain pending.

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
