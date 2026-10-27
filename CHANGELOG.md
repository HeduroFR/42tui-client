# Changelog

## Unreleased

See [DEV_CHANGELOG.md](DEV_CHANGELOG.md) for development progress, release impact
and the suggested next version. Published release notes remain below.

## 0.3.0

- Add `42tui update`, `42tui uninstall` and its `remove` alias for uv/pipx installations.
- Add a standalone `uninstall.sh` for production uv installations while preserving local data and shared tooling.
- Install stable updates automatically after exit for supported uv/pipx installations,
  with an opt-out in Settings and protection for development and pinned installs.
- Show bundled release notes on the first startup after an upgrade.
- Reuse account-scoped cached reads for friend profiles and project activity, preserving
  warm views while discarding outdated results after account or membership changes.
- Improve correction availability selection, direct drag deletion and calendar rendering.
- Split regression checks into 14 feature scopes while preserving complete test coverage.
- Fix settings status callbacks during screen teardown and stabilize calendar and
  friend-cache regression tests across startup timing and local timezones.
- Isolate installer lifecycle checks from unrelated installed commands and include
  the standalone uninstaller in distribution and release assets.

## 0.2.2

- Configure Bash/Zsh PATH automatically without duplicate exports.
- Open OAuth login through the configured default browser, including Flatpak desktop entries when URL associations are broken.

- Correct the package version and release notes before production publication.
- Split regression checks by feature scope while retaining complete test coverage.
- Prevent tester inspection workers from updating controls after their removal.
- Remove an environment-dependent Nerd Font glyph assertion from CI.

The `v0.2.1` tag failed version validation before publication because its commit
still declared version 0.2.0. Release 0.2.2 supersedes that failed tag.

## 0.2.0

- Add versioned Python releases, package validation and automatic PyPI publication.
- Add uv installers that obtain a compatible Python without replacing system Python.
- Offer optional per-user JetBrainsMono Nerd Font installation.
- Add a static installer service for Dokploy and production setup instructions.
- Add a safe `42tui --version` command.
- Handle outdated system uv with a compatible user installation, without sudo.
- Support campus OAuth login with installed Chrome/Chromium and a copyable authorization link.

The next release is 0.2.0 because installation and distribution are new user-facing
features. The checkout previously declared 0.1.2; no published release tag was
available locally when this release was prepared. Confirm remote tags and PyPI
ownership before publishing.
