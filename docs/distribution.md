# Distribution operations

The Python package is `ft-tui`. The latest confirmed stable release is
[0.4.0](https://github.com/HeduroFR/42tui-client/releases/tag/v0.4.0), published
on GitHub and PyPI. Version 0.4.1 is prepared but not yet published. This client repository owns publication
through `.github/workflows/release.yml`. Only explicitly authorized stable release
tags publish packages; ordinary branch pushes do not publish.

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

PyPI Trusted Publishing must match GitHub owner
`HeduroFR`, repository `42tui-client`, workflow `release.yml`, environment `pypi`.
The maintainer confirmed the PyPI configuration during the release cutover.
The GitHub `pypi` environment permits only tags matching `v*`; the workflow also
checks the exact stable version, release notes and main ancestry before publishing.
The successful 0.4.0 publication verified end-to-end OIDC authorization.
Preserve PyPI package ownership, protect main and stable tags, and retain original
release artifacts. Published versions are immutable: never republish 0.3.0 merely
to populate the new repository. New backend deployments are independent.

Before a separately authorized release, calculate the version from the last
confirmed stable release and all subsequent product changes. Update
`project.version` and the matching CHANGELOG heading, integrate the reviewed
change to main, and run `python release/check_version.py vX.Y.Z` from the exact
commit intended for the tag. Creating/pushing a tag requires explicit permission;
pushing that tag triggers package publication through the release workflow.

Installer helper bytes and embedded SHA-256 checks are unchanged by the split.
After any future helper edit, run `python release/installer_hashes.py --write`
and review all entry points together. Package and installer rollback are distinct.

If publication stops after uploading to PyPI, retain the tag and original CI
artifacts and rerun only the failed job in the same workflow run. A newly created
GitHub draft can briefly be invisible to a follow-up lookup; retrying resumes it.
Do not rebuild or overwrite distributions for an already published version.

## Development changelog

[DEV_CHANGELOG.md](../DEV_CHANGELOG.md) is the rolling record from the latest
successfully published stable release to current development. Update it with every
change, including fixes, features, refactoring, tests, CI, configuration and docs.
Record actual behavior and compatibility effects rather than copying commit titles.
Keep unreleased work visible even when it does not justify publishing a new version.
Do not include private backend implementation details or credentials.

CHANGELOG.md contains user-facing features, behavior changes, fixes and user
documentation improvements. Update Unreleased as those changes are implemented,
then move the included notes under the release version during preparation. Keep
CI/CD, test-only, release tooling and internal architecture work in DEV_CHANGELOG.md;
only describe a resulting user-visible change in the main changelog. This filter
also applies to the release notes shown in the application.

Use the highest accumulated release impact to suggest the next version:

| Impact | When to use it | Example from 0.3.0 |
| --- | --- | --- |
| No release required | Documentation, tests, CI or internal refactoring with no shipped behavior change | Keep 0.3.0 until a release is needed |
| Patch | Compatible bug fix or correction to existing behavior | 0.3.1 |
| Minor | New compatible functionality; also intentional breaking behavior during 0.x development, clearly identified in the notes | 0.4.0 |
| Major | Breaking a stable public contract after 1.0 | 1.2.3 → 2.0.0 |

Treat 1.0.0 as an explicit stable-contract milestone, not an automatic consequence
of a pre-1.0 change. Assess user workflows, CLI behavior, saved data and public
integration/API contracts; commit prefixes alone do not decide the version. API
major changes and backend deployment identifiers remain separate from the client
package version. A recommendation in the log never authorizes a release.

After every task, review the accumulated log and tell the developer whether a
release is worth preparing now, the suggested version and reason, and the remaining
publication blockers. Base this on useful shipped behavior, important fixes and
compatibility effects, not a number of commits or days. Say when no release is
needed. Keep that advice distinct from verified readiness to publish.

For a separately authorized clean release:

1. Review all entries against the exact release candidate. Summarize the user-facing
   changes included in that candidate under its version in CHANGELOG.md and prepare
   the matching package version. Leave DEV_CHANGELOG.md intact during preparation.
2. Complete the existing release checks, required compatibility/deployment checks
   and approved publication. Verify the intended immutable version, artifacts and
   published GitHub release. A passing CI run, pushed tag, draft release or only
   partially completed publication is not a clean release.
3. After verified success, reset the released entries in DEV_CHANGELOG.md in a
   follow-up change. Set its latest-release baseline to the published version,
   retain changes made after the release candidate, and recalculate the suggestion
   from those remaining entries. If none remain, use “Suggested next release: none”
   and “No unreleased changes.” Remove validation/blockers belonging to the old
   release; require fresh evidence for the next candidate. Preserve CHANGELOG.md.

This reset is part of the release procedure; the publication workflow
does not automatically edit branches or erase the development log. Failed,
cancelled or partial releases must leave pending entries available for retry.
