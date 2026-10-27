# Distribution operations

The Python package remains `ft-tui` at 0.3.0. Keep published version/tag ownership
with the original repository until an explicit release cutover is authorized.
The copied workflow is `.github/workflows/release.yml.disabled`, deliberately
inactive. Do not rename it until the Trusted Publisher and release ownership have
been reviewed. Ordinary branch pushes must not publish packages.

Client CI builds wheel/sdist, checks package contents, rebuilds from sdist, runs
all 14 regression scopes and validates installers on supported platforms.

The installation website and shell/PowerShell/Python installers stay here.
Build using `docker build -f distribution/Dockerfile distribution`.
For Dokploy select this repository, branch main, Build Path `/distribution`,
Dockerfile Path `Dockerfile`, Docker Context Path `distribution`, port 8080,
health path `/healthz`, and hostname `tui.42wip.in`. No secrets or volumes are needed.
The `/github` path permanently redirects (HTTP 301) to `https://github.com/HeduroFR/42tui-client`.
Change the repository binding only after the reviewed client tree is published;
do not enable deployment as part of repository creation.

A future release cutover must configure PyPI Trusted Publishing for GitHub owner
`HeduroFR`, repository `42tui-client`, workflow `release.yml`, environment `pypi`.
Preserve PyPI package ownership, protect main and stable tags, and retain original
release artifacts. Published versions are immutable: never republish 0.3.0 merely
to populate the new repository. New backend deployments are independent.

Before a separately authorized release, calculate the version from the last
confirmed stable release and all subsequent product changes. Update
`project.version` and the matching CHANGELOG heading, integrate the reviewed
change to main, and run `python release/check_version.py vX.Y.Z` from the exact
commit intended for the tag. Creating/pushing a tag requires explicit permission;
pushing that tag triggers package publication once the workflow is enabled.

Installer helper bytes and embedded SHA-256 checks are unchanged by the split.
After any future helper edit, run `python release/installer_hashes.py --write`
and review all entry points together. Package and installer rollback are distinct.
