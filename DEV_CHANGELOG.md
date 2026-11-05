# Development changelog

Latest published release: **0.7.1** ([`v0.7.1`](https://github.com/HeduroFR/42tui-client/releases/tag/v0.7.1)),
published and verified on GitHub and PyPI on 2026-11-05.
Package version: **0.7.1**.
Suggested next release: **none**. No additional release is warranted.

## Changes since 0.7.1

No unreleased changes.

## Release record

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
