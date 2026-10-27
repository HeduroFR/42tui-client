# Contributing to 42TUI client

Read [AGENTS.md](AGENTS.md) and [the architecture guide](docs/architecture.md)
before changing code. This public repository owns the Python TUI, installers,
installation website, editor integrations and client release tooling. The backend
is a separate private repository. Each repository has its own branches, commits,
pull requests and release/deployment decisions.

## Workspace and branches

A convenient workspace is a parent folder containing both clones:

```text
42TUI/                  # Workspace folder, not a third Git repository
├── 42tui-client/
└── 42tui-backend/
```

Always run Git commands from the shared `42TUI/` workspace folder, using
`git -C 42tui-client ...` for this repository and `git -C 42tui-backend ...`
for the backend. Do not run bare Git commands or initialize the parent as a repository.
Return to the workspace folder before Git operations if you have entered a
repository to run setup or tests. A client-only feature
needs no backend clone. Never add sibling source imports or require the private
backend checkout for client builds or ordinary tests.

Before starting, inspect `git -C 42tui-client status --short` and preserve unrelated work. Once
the initial migration is reviewed and `main` exists, start each task from updated
`main` in a clean checkout:

```sh
git -C 42tui-client fetch origin
git -C 42tui-client switch main
git -C 42tui-client pull --ff-only
git -C 42tui-client switch -c feat/club-invitations
```

Use `feat/`, `fix/` or `docs/` according to the task. Reuse an existing task branch
when continuing the same work. Do not edit `main` directly or force-push shared
history. If the initial clone has only `feat/client-architecture`, finish reviewing
and establishing the initial `main` before using this routine; do not create a
competing history or assume that fetching created `main`.

## Local development

Use Python 3.12 or newer. From the client repository root:

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
42tui --version
```

The requirements install this checkout in editable mode. An optional pipx setup
is `pipx install --python python3.12 --editable .`; use `--force` when replacing an
existing installation. Editable installs follow this checkout and its active
branch. Reinstall explicitly if moving to another clone.

Use disposable local data for manual UI checks:

```sh
client_sandbox="$(mktemp -d)"
XDG_DATA_HOME="$client_sandbox" 42tui
```

This redirects app files, not the OS credential store. Do not connect a real
account for ordinary UI tests; use synthetic fixtures/mocks. Tests must not open a
contributor's personal database or modify their real projects.

## Architecture and checks

Put feature operations/state/ports in `src/ft_tui/features/`. Keep Textual
presentation in views and database, HTTP, subprocess and filesystem work in
adapters. The app shell owns lifecycle, routing and composition. Import canonical
feature modules internally; keep public compatibility aliases when required.
Use the shared `AppButton`/`AppSelect` or their localized wrappers. Preserve locale
coverage, resource paths and account/provider/cursus context fences.

Run focused tests for the affected features locally before requesting review.
The full suite runs in PR CI; running it locally is optional, not a prerequisite
for review. Broaden local checks when useful for cross-cutting changes or failures:

```sh
python release/regression_scopes.py --check
python release/regression_scopes.py --scope projects
# Optional full local run:
python -m unittest discover -s tests
```

Choose the scope matching your change; new test modules need explicit ownership in
`release/regression_scopes.py`. Do not export source-tree `PYTHONPATH` for the full
suite: it can interfere with temporary installed-package lifecycle checks.
For packaging/installer changes also run:

```sh
uv build
python release/check_package.py dist
python release/installer_hashes.py
sh -n distribution/install.sh
sh -n distribution/uninstall.sh
```

Install `uv` separately if needed. HTTP simulations and their opt-in variables are
documented in [postman/README.md](postman/README.md). Report skipped integrations
and unavailable platform checks explicitly. Documentation-only changes need a diff,
link and documented-command review rather than a full behavioral test run.

## Features involving client and backend

1. Agree on the contract first: route, request/response examples, permissions,
   errors, stale/pending behavior, idempotency and compatibility with older peers.
   The backend owns canonical OpenAPI; the client keeps reviewed synthetic
   examples/mocks. Do not copy private implementation or unsanitized artifacts here.
2. Create a dedicated branch in each affected repository. Matching names such as
   `feat/club-invitations` help coordination; the branches remain independent.
   Give each task an owner and agree on any shared interface before parallel work.
3. Implement each side against the agreed contract. For a local combined check,
   start the backend using its contributing guide, then in the client terminal:

   ```sh
   client_sandbox="$(mktemp -d)"
   XDG_DATA_HOME="$client_sandbox" FT_TUI_API_URL=http://localhost:3000 42tui
   ```

   Backend `PUBLIC_BASE_URL` must match the reachable development origin; pairing
   additionally needs a development OAuth application/callback. Use only a test
   account and disposable services. Otherwise use the documented HTTP simulations.
4. Test the pair and record both exact Git revisions and client version. Check
   the supported older client/backend combinations as well as the new pair. See
   [API compatibility](docs/api-compatibility.md); the support window is not yet
   enforced by a version handshake. A liveness response or skipped test is not a
   full end-to-end check.
5. Open two linked PRs with contract changes, checks, compatibility and rollout
   order. Keep each CI independent. Cross-repository compatibility jobs needing
   backend access belong in trusted private CI; never expose credentials to public
   pull requests.
6. Normally deploy additive backend changes/migrations before releasing the
   consuming client. Preserve old routes for rollback. Breaking API behavior needs
   a new API major and an overlap period, not a simultaneous mandatory upgrade.

The private backend coordinator performs manually selected pinned-pair checks; see
[API compatibility](docs/api-compatibility.md#cross-repository-verification-and-failed-deployments).
Keep public CI independent of private backend access.

## Review, releases and private data

Read [DEV_CHANGELOG.md](DEV_CHANGELOG.md) before starting a task and update it with
every change, including documentation, tests and CI. Record the implemented result,
date, release impact, available commit/PR reference and validation. Keep one entry
per meaningful change and update it as the work evolves. The log covers everything
since the latest successful release; its maintenance and reset procedure is in
[distribution operations](docs/distribution.md#development-changelog).
At task completion, review the accumulated log and advise whether a release is now
worth preparing, its recommended version and why, and what still blocks publication.
Documentation-only or internal work does not by itself require a release.

Also update CHANGELOG.md under Unreleased for user-facing features, behavior
changes, fixes and user documentation improvements. Explain the visible effect;
keep CI/CD, tests, release tooling and internal restructuring in DEV_CHANGELOG.md.
Use the same user-facing scope for published release notes.

Use one-line English Conventional Commits matching the branch prefix, for example
`feat: add club invitations` or `docs: document contributor workflows`. Stage only
task files. PRs target `main` and explain the problem, resulting behavior, tests,
limits and related backend PR. Wait for review and required CI before merging.

`project.version` in `pyproject.toml` is authoritative. Client package and backend
versions do not need to match. Documentation/internal refactors do not require a
release. For an authorized client release, prepare the version and changelog on
`main`, validate the exact commit with `python release/check_version.py vX.Y.Z`,
then separately authorize the tag/publication. Never reuse a published version.
The release workflow is currently disabled; enabling/configuring it is a separate
reviewed operation. See [distribution operations](docs/distribution.md).

Never commit credentials, populated `.env` files, user databases, browser profiles,
sessions, `.local/`, generated analysis graphs or backend internals. Keep shared
instructions relative to the repository. Assistants prepare changes and checks;
commits, pushes, tags, publications and deployments require explicit authorization.
