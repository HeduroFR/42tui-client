# Collaboration

Read [CONTRIBUTING.md](CONTRIBUTING.md) before implementing changes.
For API, version or rollout changes, also read [API compatibility](docs/api-compatibility.md).
Do not release a dependent client until its exact revision is tested with the backend and the required backend is verified deployed. Auto-update does not eliminate older supported clients.

Preserve unrelated local work. Use dedicated feat/, fix/ or docs/ branches and pull requests to main.
Do not commit, push, tag, publish, deploy or change repository visibility without authorization.
Use a one-line English Conventional Commit matching the branch prefix and repository scope: `type(client): description` (for example, `docs(client): clarify contributor workflow`).
Keep credentials, .env files, user databases, browser profiles, sessions and .local/ out of Git.
Use relative paths in shared instructions. Review the diff and run relevant checks before delivery.

# Git command location

Always run Git commands from the shared `42TUI/` workspace folder containing
`42tui-client/` and `42tui-backend/`, never from inside either repository.
Prefix every Git command for this repository with `git -C 42tui-client`.
This applies to commands executed by agents and commands given to the user,
including status, fetch, branch, diff, add, commit and push. Do not provide bare
Git commands or use `cd 42tui-client` to run Git. The workspace folder is
not a third Git repository; do not initialize one there. Non-Git setup/test commands
still follow their documented working directories.

# Delivery format

For each completed feature, fix or documentation task:

- Separate the final delivery by affected repository, labelled **Client** and/or
  **Backend**. Include only repositories changed by the task; do not imply an
  untouched repository was validated.
- In each repository's block, summarize the change, checks actually run and any
  skipped, failed or unavailable checks. State whether files remain uncommitted.
- If a commit remains to be created, provide commands executable from the workspace
  folder: `git -C 42tui-client add <exact task files>` and
  `git -C 42tui-client commit -m "type(scope): description"`. Use the real
  paths and branch name; stage only task files, never the whole working tree.
- Propose `git -C 42tui-client push -u origin <actual-task-branch>` for each affected repository,
  clearly separate from commands already executed. If changes were committed
  with authorization, report the commit and omit duplicate add/commit commands.
- For cross-repository work, provide separate commits and push commands, identify
  linked PRs when available, and explain API compatibility, version implications,
  rollout order and any remaining integration or deployment verification.
- Providing commands does not authorize executing them. Commit authorization alone
  does not authorize push, merge, tag, publication or deployment. Preserve those
  separate authorization boundaries; do not invent a release for an internal change.
- If the user asks only for a commit message, return only the scoped Conventional
  Commit line without explanation or a code block.

# Client

Python >=3.12. Package name ft-tui; commands 42tui, 42goto, 42tui-zed-lsp.
Use AppButton from src/ft_tui/ui/button.py and AppSelect from src/ft_tui/ui/select.py
(or their localized wrappers); never import these widgets directly elsewhere.
project.version in pyproject.toml is authoritative. Repository separation does not authorize a version bump.
Install: pipx install --python python3.12 --editable .
Reinstall: pipx install --force --python python3.12 --editable .
Release only from reviewed main, with matching changelog and tag, after python release/check_version.py vX.Y.Z.
Release publication needs separate explicit authorization. Do not reuse a published version.
