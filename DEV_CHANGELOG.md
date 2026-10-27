# Development changelog

Latest release: **0.4.0** ([`v0.4.0`](https://github.com/HeduroFR/42tui-client/releases/tag/v0.4.0)).
Package version: **0.4.0**, published to PyPI and GitHub.
Suggested next release: **none**. There are no unreleased user-facing changes;
the post-release documentation below does not require a new release.

This file tracks implemented changes since the latest release. Keep published
history in [CHANGELOG.md](CHANGELOG.md). Maintenance, version selection and reset
instructions are in [distribution operations](docs/distribution.md#development-changelog).

## Changes since 0.4.0

### Internal changes and documentation

- **2026-10-27 · no release required · Release record:** verify the published
  wheel/sdist against GitHub checksums and PyPI digests, install the published
  wheel and verify its CLI/resources, then advance the published baseline to
  0.4.0 and clear only entries included in that tag. Preserve the user-facing
  release history and document safe recovery from a partial publication.
  Reference: `docs/post-release-0.4.0`.
  Publication used commit `bb5caff0988cbedd54d00c8dcb455a187da153bf` and
  [release run 40570776094](https://github.com/HeduroFR/42tui-client/actions/runs/40570776094),
  which succeeded after retrying the GitHub draft-visibility failure with the
  original CI artifacts. Live OAuth and pinned-pair compatibility were not
  exercised during publication; this limitation was disclosed before authorization.

## Validation and release readiness

- Post-release documentation diff/link checks passed. Runtime suites were not
  repeated for this documentation-only update.
- No additional package release is warranted. New runtime changes require fresh
  candidate checks and release evidence.
