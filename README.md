# 42TUI client

Offline-first terminal workspace for École 42 students: projects, time tracking,
notes and optional account-connected features. Source: [HeduroFR/42tui-client](https://github.com/HeduroFR/42tui-client).

Python >=3.12 is required. The distribution remains `ft-tui`, version **0.3.0**;
commands remain `42tui`, `42goto`, and `42tui-zed-lsp`.

## Development

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
42tui --version
python release/regression_scopes.py --check
python -m unittest discover -s tests
```

The interface stores personal data locally. Use a disposable environment for UI
smoke checks. Online features use `https://oauth.42wip.in`; override it with
`FT_TUI_API_URL`. See [API compatibility](docs/api-compatibility.md).

## Install and maintain

```sh
curl -fsSL https://tui.42wip.in/install.sh | sh
42tui update
42tui uninstall
```

Review scripts before executing them. Windows installation through
`https://tui.42wip.in/install.ps1` is experimental. Uninstall preserves application
data and credentials. Editable installs are maintained through their original manager.
See [distribution operations](docs/distribution.md) and [editor integrations](integrations/README.md).

## Local checks

```sh
uv build
python release/check_package.py dist
python release/installer_hashes.py
sh -n distribution/install.sh
sh -n distribution/uninstall.sh
```

The backend is separately maintained. This checkout needs no backend source to
build, install or run its unit/UI tests. Optional HTTP simulations are described
in [simulation checks](postman/README.md). No new release is created by this split.

## Architecture

Feature ownership, dependency rules and the remaining migration stages are
described in [the architecture guide](docs/architecture.md).
