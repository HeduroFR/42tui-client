# Changelog

## Unreleased

- Open the community Discord invite through `https://tui.42wip.in/discord`.
  This website improvement is live and does not require a package update.

## 0.5.0

### ✨ Nouveautés

- Match the OAuth completion page to your active terminal theme when supported by
  the backend. The redesigned page links to GitHub and Discord, then attempts
  to close after 10 seconds; close it manually if the browser prevents this.
- Read project details in a compact dialog with separate catalog, workspace and
  repository sections, a project-name heading and centered Close button.
- Center the expired-session dialog actions and offer Reconnect or Quit TUI.
- Keep Docker status messages short; hover over the status for the raw diagnostic.
- Find Testers below Registration in project details, with concise status
  messages. Use `t` to jump to its actions; the top-right Testers button is removed.
- Align workspace actions in two columns, with Open folder and Push all spanning
  the full row and consistent spacing between controls. Place the timer button
  to the right of its time/status information.
- Recover existing Vogsphere work before opening a project and stop for manual
  reconciliation when remote history is missing locally, preserving local files
  and existing branches/remotes.
- Review and push committed work to development, Vogsphere or both from the
  project controls or `42git`; see each destination's result and retry failures.
  Both destinations receive the committed history; there is no separate Vogsphere
  file selection yet. Stage and commit with ordinary Git before pushing.
  Open project folders in the system file explorer from the project controls.
- Explain in push previews that Vogsphere requires the 42 campus network.
- Keep existing committed projects editable with a warning when Vogsphere cannot
  be reached off campus; new or empty projects still require recovery first.

- Run Francinette from one button on Linux and macOS, with installation and retries.
  Tester setup never uses sudo or changes host packages or permissions. School
  Linux machines need an accessible Docker engine with BuildKit support. macOS
  setup installs Docker Desktop in the user's Applications folder; keep its
  user-level settings and accept Docker's terms when prompted.
- Show tester build, Docker context and local-folder diagnostics in French and
  Spanish, preserving technical error details.

### 📦 Mise à jour

- Run `42tui update`. `42git` is installed automatically alongside `42tui`; no
  additional Bash/Zsh configuration is needed when the tools directory is on PATH.
  Existing `42goto` shell initialization remains sufficient.

## 0.4.4

- Install automatic updates before opening the TUI, then start the updated
  version in the same launch. Offline checks and failed updates fall back to the
  installed version. Updates found while the app is open wait for the next launch
  instead of installing when it closes. Automatic-update opt-out and protections
  for pinned/development installations remain respected.
- Ask whether to save, discard or cancel before replacing an edited Dev Log note
  when switching projects/notes, creating a note or refreshing the project catalog.
- Prevent dashboard activity refreshes from crashing during shutdown.
- Serialize manual timer changes across concurrent app instances so only one
  new manual timer can run at a time. Existing timer history is preserved.

## 0.4.3

- Configure PATH and `42goto` navigation automatically in both Bash and Zsh
  when using the Linux/macOS installer. Reinstalling updates a managed block;
  open a new terminal or use the printed activation command after installation.
- Fix project completion on macOS's bundled Bash.
- Explain the project's AI-assisted Python development and the conditions for
  a future handwritten Rust rewrite at the top of the README.

## 0.4.2

- Check for stable updates on every launch and every 12 hours while the app
  remains open. Re-enabling automatic updates immediately starts a check.
- Keep exams out of Continue working suggestions, including active, recent and
  selected exams. Exams remain available in the project catalog and progress.
- Clarify that first-run setup requires a connected 42 account; saved projects
  and local notes remain available offline after setup.

## 0.4.1

- Fix correction-slot selection and suggested start times: at 10:18, the first
  available start is 10:45. Prevent publishing a start that became too early while
  editing.

See [DEV_CHANGELOG.md](DEV_CHANGELOG.md) for the development record and release
readiness.

## 0.4.0

- Prevent activity-screen background updates from crashing while the screen is
  being removed during navigation.
- Show the installed version in the app header instead of account connection
  status, including alpha, beta or release-candidate suffixes when present.
- Require a connected 42 account to complete first-run setup. Remove Skip setup
  and the Escape bypass, and prevent completion if the connection is lost.
  Existing completed installations keep their current setup status.
- Refresh friend-search readiness messages when suggestion results change.
- Direct the installation website's `/github` link to the new client repository.
- Clarify installation, project navigation, editor integrations and platform
  support in the user documentation.

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
