# Development changelog

Latest published release: **0.7.2** ([`v0.7.2`](https://github.com/HeduroFR/42tui-client/releases/tag/v0.7.2)),
published on GitHub and PyPI on 2026-11-05. Package version: **0.7.3**
(prepared; not published). Suggested next release: **0.7.3 (patch)** for the
user-requested urgent offline-mode improvement. Review, PR CI and verification
of the deployed backend remain release blockers.

## Changes since 0.7.2

- 2026-11-08: Prepare version 0.7.3 and its release notes for the offline-mode
  changes. User-requested patch impact; no backend update. Reference:
  `feat/backend-offline-mode` (uncommitted). Version/notes, focused offline
  tests, wheel/sdist contents, installer hashes and shell syntax checks pass.
  PR CI, review and real-server verification remain pending.

- 2026-11-08: Start the backend availability probe during initial view loading
  and reduce its network timeout to two seconds so the warning appears sooner.
  User-requested 0.7.3 patch target; no backend change. Reference:
  `654b711`. Five offline and five dashboard
  cache tests, focused lint and diff whitespace checks pass. Real-server timing
  and PR CI remain unverified.

- 2026-11-08: Shorten and compact the localized backend-unavailable dialog.
  User-requested 0.7.3 patch target; no backend change. Reference:
  `654b711`. Four focused offline checks, lint
  and diff whitespace checks pass. Visual review and PR CI remain pending.

- 2026-11-08: Detect backend liveness loss, warn on startup, preserve local
  data, gate remote actions and resume them after recovery. Allow first-run
  setup offline and keep map loading out of the tab event handler. User-requested
  0.7.3 patch target;
  no backend change. Reference: `0c88af1`.
  Focused offline, account, onboarding, agenda, club, social, correction,
  registration and team tests pass; the reported real-world map freeze and
  integration with the deployed backend remain unverified. Review and PR CI
  remain release blockers.

- 2026-11-06: Document English-only project content and Jotty Kanban and
  checklist tracking for client work. No release required; no API or runtime
  change. Documentation review and diff whitespace checks pass.

## Release record

- 2026-11-05: Publish 0.7.2 from main commit `0db5264` with successful release
  workflow checks. GitHub release and PyPI distributions are published; their
  wheel and source distribution SHA-256 digests match, neither is yanked, all
  seven GitHub assets are present, and release notes match CHANGELOG.md.

- 2026-11-05: Publish stable patch 0.7.1 from reviewed main `2e870c6`, following
  [PR #61](https://github.com/HeduroFR/42tui-client/pull/61) with all 33 checks
  successful. Tag `v0.7.1` points to that exact commit. All 36 jobs in the
  [publication workflow](https://github.com/HeduroFR/42tui-client/actions/runs/42069882207)
  pass, including PyPI and GitHub release publication. No API change or backend
  rollout was required.
- 2026-11-05: Verify both PyPI distribution SHA-256 hashes against the original
  release CI artifacts, all seven GitHub assets and SHA256SUMS, installer bytes,
  stable/non-draft release flags and the exact CHANGELOG.md release notes. Install
  `ft-tui==0.7.1` from PyPI into an isolated Python 3.12 environment and pass the
  installed entry-point, version and package-resource smoke checks. Published
  distributions are not yanked. The version JSON endpoint initially returned a
  cached 404; an uncached request confirmed both published distributions.
- 2026-11-05: Reset development entries included in the verified release and
  update the distribution guide's stable baseline to 0.7.1. Published user-facing
  notes remain in CHANGELOG.md; no later development entries existed to retain.
  Documentation only; no release required. Reference: `docs/release-0.7.1-record`.
  Version and diff checks pass; no package, dependency, API or tag change.

Interactive oldest-supported Neovim and full LazyVim/SupraVIM setups were not
retested during publication. Isolated standard/Lazy.nvim startup checks passed
in release preparation; these do not replace interactive configuration coverage.
