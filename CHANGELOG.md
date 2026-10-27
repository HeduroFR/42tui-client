# Changelog

## Unreleased

- Show the installed version in the app header instead of account connection
  status, including alpha, beta or release-candidate suffixes when present.
- Require a connected 42 account to complete first-run setup. Remove Skip setup
  and the Escape bypass, and prevent completion if the connection is lost.
  Existing completed installations keep their current setup status.
- Refresh friend-search readiness messages when suggestion results change.
- Direct the installation website's `/github` link to the new client repository.
- Clarify installation, project navigation, editor integrations and platform
  support in the user documentation.

See [DEV_CHANGELOG.md](DEV_CHANGELOG.md) for the full development record and
release recommendation, including internal work.

## 0.3.0

- Add `42tui update`, `42tui uninstall` and its `remove` alias for uv/pipx installations.
- Add a standalone `uninstall.sh` for production uv installations while preserving local data and shared tooling.
- Install stable updates automatically after exit for supported uv/pipx installations,
  with an opt-out in Settings and protection for development and pinned installs.
- Show bundled release notes on the first startup after an upgrade.
- Reuse account-scoped cached reads for friend profiles and project activity, preserving
  warm views while discarding outdated results after account or membership changes.
- Improve correction availability selection, direct drag deletion and calendar rendering.
- Prevent settings status updates from targeting controls after their screen closes.
- Include the standalone uninstaller in release downloads.

## 0.2.2

- Configure Bash/Zsh PATH automatically without duplicate exports.
- Open OAuth login through the configured default browser, including Flatpak desktop entries when URL associations are broken.
- Prevent tester inspection workers from updating controls after their removal.

Release 0.2.2 supersedes the unpublished 0.2.1 release.

## 0.2.0

- Add versioned Python packages and release downloads.
- Add uv installers that obtain a compatible Python without replacing system Python.
- Offer optional per-user JetBrainsMono Nerd Font installation.
- Add an installation website with downloadable installers.
- Add a safe `42tui --version` command.
- Handle outdated system uv with a compatible user installation, without sudo.
- Support campus OAuth login with installed Chrome/Chromium and a copyable authorization link.
