# Collaboration

Read [CONTRIBUTING.md](CONTRIBUTING.md) before implementing changes.
For API, version or rollout changes, also read [API compatibility](docs/api-compatibility.md).
Do not release a dependent client until its exact revision is tested with the backend and the required backend is verified deployed. Auto-update does not eliminate older supported clients.

Preserve unrelated local work. Use dedicated feat/, fix/ or docs/ branches and pull requests to main.
Do not commit, push, tag, publish, deploy or change repository visibility without authorization.
Use a one-line English Conventional Commit matching the branch prefix and repository scope: `type(client): description` (for example, `docs(client): clarify contributor workflow`).
Keep credentials, .env files, user databases, browser profiles, sessions and .local/ out of Git.
Use relative paths in shared instructions. Review the diff and run relevant checks before delivery.

# Development changelog

Read [DEV_CHANGELOG.md](DEV_CHANGELOG.md) before making changes. Every task that
changes tracked files must add or update an entry there before delivery, including
code, tests, configuration, CI and documentation changes. Record the date, concrete
result, release impact (patch, minor, major or no release required), and a commit/PR
reference when available. Record checks actually run and remaining release blockers;
do not describe planned work or unverified deployments as complete.

Keep CHANGELOG.md user-facing: update its Unreleased section alongside each
implemented feature, behavior change or fix that affects users. Include user-facing
documentation improvements. Describe the visible result and any required user
action. Keep CI/CD upgrades, test-only changes, release tooling, repository
restructuring and internal refactors exclusively in DEV_CHANGELOG.md unless they
also change shipped behavior; in that case describe only the user-visible effect
in CHANGELOG.md. Apply the same filter when preparing published release notes.

Keep the baseline at the latest successfully published stable release, not the
working package version. Reassess the suggested next version from the highest
accumulated impact using [distribution operations](docs/distribution.md#development-changelog).
At the end of every task, review the accumulated entries and advise the developer
whether a new release is warranted now. State the recommended bump and version,
the concrete reason (for example a useful completed feature, an important fix or
changed compatibility), and any checks or rollout blockers before publication.
Distinguish “a release is worth preparing” from “the release is ready to publish.”
Do not recommend releases based only on commit count or elapsed time. If accumulated
changes do not justify a release, say so briefly. Include the recommendation in the
delivery and keep DEV_CHANGELOG.md consistent with it.
Do not bump versions or publish without authorization. Preserve pending entries
through release preparation, drafts, failures and partial publication. Only after a
clean release is verified, preserve its notes in CHANGELOG.md, clear entries included
in that release, advance the baseline and retain any later development changes.

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
