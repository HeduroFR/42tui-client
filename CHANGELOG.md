# Changelog

## Unreleased

- Use a trash icon for tester removal, with a readable Remove label in text mode.

- Present tester results in a status card with readable counts that adapt to narrow
  panels. Open the log in your preferred code editor, with “View full output”
  alongside it on the right; successful
  runs no longer show a raw log path or redundant exit code.

- Use the maintained Supra printf fork with native arm64 Docker execution on Apple
  Silicon, per-test timeouts and validated JSON result counts. The new pinned image
  builds on first run. libft still uses amd64 emulation on ARM.

- Remove bundled Francinette in favor of Supra printf/libft and native push_swap.
  There is currently no bundled get_next_line tester. Keep custom catalog entries
  and previously downloaded Docker images untouched.
- Add a one-character left inset to tester console output.

- Clean and force-rebuild Supra project copies inside Linux before testing, so
  existing macOS/other-architecture objects and archives cannot be reused as an
  up-to-date build. Original source folders and compiled outputs remain intact.

- Add Supra testers for ft_printf and libft using pinned Linux containers
  on Linux/macOS, with a Debian GCC/glibc environment and no host tester-tool
  installation. Runs preserve project files, disable network access and keep full
  diagnostics. libft completion remains unverified.

- Show the current tester preparation/build/run stage. Keep detailed test cases
  in the log; custom testers can provide verified summaries.

- Run a pinned push_swap tester without Docker, using a private Python environment
  and a disposable project copy. Native execution requires confirmation; Git and
  project build tools must already be installed. Custom tester definitions can
  select native execution and preparation commands.

- Distinguish reported test failures from tester process failures, unreadable
  reports and unverified results. Show exit codes and available test counts in
  the workspace and saved log, with French/Spanish translations. Custom testers
  can provide a fresh JSON summary through `result_file`; results are never inferred
  from a successful exit alone.
- Avoid a workspace refresh error when replacing a finished tester run.

- Recover new or empty project folders from the development remote when Vogsphere
  is unreachable, with a warning that Vogsphere history remains unverified.
  Existing local work still requires review before synchronization.

- Ask for SSH passphrases in the masked modal during Save + Set Up Checkout,
  keeping authentication prompts inside the TUI. Cancel stops completion feedback.

- Separate tester Run and removal controls with a visible gap and use the shared
  square danger button for removal.

- Keep tester status messages and multiline commands aligned at the left edge
  of the console instead of drifting diagonally across the output.

- Keep tester setup and execution inside 42TUI, with live output, line input,
  cancellation, elapsed time, rerunning and saved logs. Close and reopen the
  tester workspace while a run continues on its original project.
  Render terminal redraws without repeated progress blocks, open the log folder
  directly, and align the tester removal button with Run.
  Separate the action buttons with gaps and leave space below the input field.

- Run Docker testers against a disposable project copy, excluding Git metadata,
  so tester builds and cleanup preserve your working folder. Generated files in
  the copy are discarded after the run; diagnostics remain in the tester log.

## 0.5.2

### 🐛 Fixes

- Open existing project files even when remote Git history differs: review a
  colored diff first, then choose **Open local files** or **Cancel**. Local files,
  staged changes and branches remain intact.
- Identify the remote as **dev (origin)** or **vog (vogsphere)**, with its URL,
  branch and commit counts. Suggest actions based on whether histories can
  fast-forward, diverge or have no common ancestor.
- Run status, commit inspection, pull and push through spaced review buttons
  on one row, with output shown in a modal. Pull/push require confirmation and
  fresh validation; pull stays fast-forward-only and push never uses force.
- Enter SSH key passphrases in a masked dialog instead of a terminal prompt
  overwriting the TUI. Reuse the value in memory during one operation, allow
  correction after rejection and discard it when the operation ends.
- Reuse editor remote checks for five minutes while local Git state is unchanged,
  reducing repeated passphrase prompts. Pull/push still revalidate before writing.
  Remote-only changes can remain unseen until the editor-check cache expires.

### 📦 Update

- Run `42tui update` for a managed installation. Pinned and development installs
  keep their selected version or checkout and must be updated explicitly.
- No shell configuration, database migration or backend update is required.

## 0.5.1

### 🐛 Fixes

- Open the community Discord invite through `https://tui.42wip.in/discord`.
  This website improvement is live and does not require a package update.
- Recover and push Vogsphere work using its actual default or only branch,
  including `main` and `master`. Ambiguous branches require manual resolution.
- Redirect `https://tui.42wip.in/` to the GitHub repository while preserving
  installer downloads and the GitHub/Discord shortcuts (requires website rollout).

### ✨ New features

- Review and fast-forward committed project work with `42git pull dev`,
  `42git pull vog`, and `42git pull all`. Pull preserves local work, requires a
  clean checkout and stops when histories diverge. Pull all fetches both remotes
  before applying one compatible fast-forward.

### 📦 Update

- Run `42tui update` after 0.5.1 is published. No additional shell setup is needed.

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
