# Development changelog

Latest release: **0.4.2** ([`v0.4.2`](https://github.com/HeduroFR/42tui-client/releases/tag/v0.4.2)).
Package version: **0.4.2**. The working tree also contains unreleased tester changes;
the published patch uses isolated commit `0f3f4c3642e11f39a958fbe89e09a0d4e868b1d9`.
Suggested next release: **0.5.0** (minor), for the unreleased tester setup below.
A release is worth preparing; native Docker/macOS validation and fresh candidate
checks remain required before publication. No version bump is authorized here.

This file tracks implemented changes since the latest release. Keep published
history in [CHANGELOG.md](CHANGELOG.md). Maintenance, version selection and reset
instructions are in [distribution operations](docs/distribution.md#development-changelog).

## Changes since 0.4.2

### Installer patch targeting 0.4.3

- **2026-10-28 · patch · Installer shell setup and project note:** configure both
  Bash and Zsh after verified installation with PATH and guarded 42goto setup in
  managed blocks at the end of their rc files. Respect ZDOTDIR, preserve manual
  functions, surrounding content, symlinks and modes; replace atomically and leave
  malformed blocks untouched. Attempt the other shell after a configuration error.
  Initialize Zsh completion when needed, stay quiet after uninstall and print
  activation commands. Replace Bash's mapfile usage for macOS Bash 3.2 completion.
  Add the user's About this project README note verbatim and document automatic
  setup. Refresh both bootstrap helper hashes. Branch: `fix/installer-shell-setup`;
  no commit/PR yet. Validation: 23 installer tests passed on native macOS with
  real Bash 3.2/Zsh loading; the installation-updates scope passed 72 tests.
  Wheel/sdist build and package-content checks passed (version remains 0.4.2).
  Helper hashes, POSIX syntax and 829-test scope ownership checks passed.
  Full suite, Linux/Windows platform execution, CI, exact 0.4.3 candidate and
  hosted installer deployment remain unverified. Independent review could not
  complete because its network permission was revoked; author reviewed the
  connected callers, shell output, documentation and final diff instead.
- **Release scope:** a selective 0.4.3 patch is worth preparing for the installer
  fix and README note. Do not publish current main as 0.4.3: it includes the minor
  tester feature below, which still warrants 0.5.0. No version bump or publication
  performed. Installer hosting needs a separately authorized deployment; package
  publication alone does not update the hosted scripts.

### Changed behavior

- **2026-10-27 · minor · Tester setup:** replace separate install/start/docs/recheck
  controls with one Run action per tester. Preserve compact image removal, locking,
  pinned sources, platform-specific images, mount checks and captured project paths.
  Setup uses no sudo, package-manager installs, system service changes or socket/group
  permission changes. Linux uses an accessible existing engine and can start an
  existing rootless user service. macOS installs Desktop under `~/Applications`
  through an unprivileged DMG mount, staged copy, signature verification and rename;
  failed copies remain retryable. Keep Desktop's user-level defaults.
  Build pinned `.git` sources inside Docker BuildKit without host Git, preserving
  Git metadata. Other custom HTTPS clone URLs retain the existing-Git fallback and
  give explicit guidance if Git is absent. Update README, French/Spanish copy and
  focused regressions. Reference: `3ea93ab`, [PR #13](https://github.com/HeduroFR/42tui-client/pull/13).


### Internal changes and documentation

- **2026-10-28 · no release required · Combined roadmaps:** integrate the GitHub
  Settings button/star-reminder plan and future keyboard/keymap redesign plan on
  current main. Retain the 0.5.0 tester scope and validation gates; correct the
  update-discovery status to shipped in 0.4.2 through PR #19. Preserve the verified
  0.4.2 baseline, publication evidence and existing pending tester work.
  Sources: `a26aa9e` (`docs/github-roadmap`, PR #21), `3ebcf07` and `80ea4b9`
  (`docs/keyboard-navigation-roadmap`). No runtime or package-version changes.
  Checks: reviewed both source roadmaps, combined diff, relative links and
  whitespace. Runtime tests were not run for this documentation-only change.
  Existing 0.5.0 native tester and exact-candidate release gates still apply;
  this integration requires no release.

- **2026-10-28 · no release required · Verified 0.4.2 publication:** after explicit
  tag/publication authorization, publish isolated candidate
  `0f3f4c3642e11f39a958fbe89e09a0d4e868b1d9`, integrated through
  [PR #19](https://github.com/HeduroFR/42tui-client/pull/19) as `b758138`.
  Close superseded PR #18. The patch contains update discovery, exam resumption
  filtering and first-run instructions; later tester features are excluded.
  [Release run 40603624612](https://github.com/HeduroFR/42tui-client/actions/runs/40603624612)
  passed all checks and both publishers. GitHub publication completed at
  2026-10-27T23:44:03Z. Verify all seven release assets/checksums and byte equality
  of both PyPI downloads and GitHub distributions against original CI artifacts.
  Wheel SHA-256: `86c9c66805ffe0358b36aade07e971bfb0be8b05f05e681b4fdb924f073ee6a0`;
  sdist: `f3383f18264f61d5a4e1a56bff7d25fec6dddce49b8c7dd314e9bcc03fdf3352`.
  A disposable unpinned uv installation ran the real `42tui update` from 0.4.1
  to 0.4.2, preserved a local-data sentinel and passed installed CLI/resource smoke.
  Initial PyPI metadata/index propagation briefly returned 404/0.4.1; retry succeeded
  without changing the tag, rebuilding or republishing. Tool/data/cache paths stayed
  under /tmp; no real user data or credentials were used.
  Exact-candidate compatibility run 40600874913 passed three synthetic friend-preview
  pairs against backend e917aca with 0.4.0 as oldest supported client. This patch
  changes no API or backend behavior; no new backend deployment was required.
  Live Intra writes and full API coverage remain outside that scenario.
  Advance only the verified baseline, clear shipped preparation records and complete
  TODO/plan checklists, retaining unreleased tester behavior and validation below.
  Checks for this documentation: diff, release evidence and relative links reviewed.
  No additional product release is needed for this documentation reset.

## Validation and release readiness

The 0.4.2 publication is verified. Pending release work belongs to 0.5.0 tester
setup; the successful patch release does not validate native tester installation.

### Tester setup validation (2026-10-27)

- Adapter tests: 54 passed, covering no privileged setup commands, managed-school
  Docker missing/denied/stopped, user-only rootless startup, per-user macOS discovery,
  pinned remote builds without host Git, safe custom clone fallback, Git metadata,
  interrupted Mac copy cleanup/retry, timeout and terminal operation boundaries.
- Read-only reviews found partial-copy retry and custom-build compatibility gaps;
  reproduced each with failing regressions, fixed and verified the adapter suite.
  Linux rootless-service approval copy now describes Linux startup correctly.
- Final tester scope: 70 passed in 54.868 seconds using the runner-only heartbeat.
  Locale checks: 2 passed; new setup/error strings have French/Spanish coverage.
  Scope ownership: all 820 discovered tests assigned exactly once. Diff whitespace
  check passed. The full suite was not run locally.
- Ordinary UI runs stalled during Python 3.14 asyncio executor shutdown in this
  sandbox after successful assertions. A temporary runner-only event-loop heartbeat
  resolves the wakeup stall; product and test files contain no workaround.
- A WSL2/Ubuntu 26.04 probe confirmed Docker is absent here. The earlier privileged
  installation attempt stopped at the sandbox's no-new-privileges guard before any
  package changes. The final WSL probe selected no installation plan, produced the
  school-Docker guidance, executed zero host setup commands and released the lock.
- Native school Docker access, real container builds and native macOS installation
  remain unverified. Full-suite/CI remain release gates. Flake8 is unavailable.
- The tester feature merits a minor release (0.5.0) after published 0.4.2.
  Native school Docker access and macOS installation remain unverified. CI for
  PR #16 passed all 21 jobs, including the tester scope; future candidates still
  require their own exact revision checks.

### PR #13 merge validation (2026-10-27)

- Conflict markers removed; both unreleased tester work and main's release record
  retained. Standard tester scope: 70 passed in 51.827 seconds, without the earlier
  heartbeat workaround. Correction scope: 52 passed in 15.306 seconds. Locale
  checks: 2 passed. All 823 discovered tests have exactly one scope owner; staged
  whitespace checks passed. Full suite and native Docker/Mac integration not rerun.
- Unrelated companion work in the primary checkout is excluded from this worktree.
