# Development changelog

Latest release: **0.4.2** ([`v0.4.2`](https://github.com/HeduroFR/42tui-client/releases/tag/v0.4.2)).
Package version: **0.4.3**, prepared but not published.
Suggested next release: **0.4.3** (patch), for automatic installer shell setup
and compatible macOS Bash completion. This isolated candidate starts at v0.4.2;
main's pending minor tester work remains outside this release.

## Changes since 0.4.2

- **2026-10-28 · patch · Installer shell setup:** carry the installer, navigation,
  tests and user documentation from [PR #23](https://github.com/HeduroFR/42tui-client/pull/23)
  (`9b3a271`). Configure managed blocks at the end of both Bash and Zsh rc files,
  respecting ZDOTDIR. Preserve user content, manual functions, symlinks and modes;
  quote paths, handle reinstall without duplicates, initialize Zsh completion and
  stay quiet after uninstall. Attempt both shells independently and print source
  commands. Refresh the helper digest in both bootstraps. Avoid Bash mapfile so
  completion works on macOS Bash 3.2.
- **2026-10-28 · documentation · Project direction:** include the author's exact
  About this project README note about AI-assisted Python development, 420 monthly
  active users for two consecutive months and a handwritten Rust rewrite.
- **2026-10-28 · release preparation · 0.4.3:** prepare the package version and
  matching user-facing notes on `fix/release-0.4.3-candidate` from published
  v0.4.2. No API, backend, data schema, dependency or tester changes. No new plan
  documents. Baseline remains 0.4.2 until verified publication.

## Validation and release readiness

PR #23 passed all 21 CI checks. That validates the feature on main, not this
new release candidate. This candidate passed 23 focused installer tests and all
72 installation-updates tests, version v0.4.3, wheel/sdist build and package
contents, helper hashes, POSIX syntax and 805-test scope ownership checks.
Clean archived-package, installed smoke, full regression and paired compatibility
checks remain pending. Retain 0.4.0 as
the oldest supported client. The existing paired scenario covers synthetic friend
preview only, not the entire API or live OAuth/Intra writes. This independent
installer fix requires no new backend capability or deployment.

A 0.4.3 patch is worth preparing. Review/main-ancestry integration and exact
candidate validation remain required. Tags, publication and installer-hosting
deployment require separate approval; none has been performed.
