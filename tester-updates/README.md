# Compatible tester updates

Clients starting with 0.7.2 read `v1.json` from this directory on reviewed `main`
before tester runs. A successful check is cached for one hour. Offline, failed or
invalid checks retain the previous valid catalog, or the bundled revisions if
there is no cache. This does not require a new TUI release or a backend deployment.
The endpoint becomes available when these files are merged to `main`.

Each entry approves one exact Git commit (`ref`) for a bundled tester (`id`) with
an exact compatibility fingerprint (`base`). The fingerprint covers the bundled
definition and build recipe bytes, including patches. Updates can change only
the source commit, never the repository, runtime, commands, permissions or result
reader. User overrides, including an identical explicit pin, do not opt in.
The client logs the selected revision. Docker builds a separate image when it
changes; old images are retained until the user removes that tester's images.

## Approve a revision

1. Edit the relevant entries' `ref` to the candidate's full, lowercase 40-character
   commit SHA. Update all compatible Germinette entries when updating that shared
   source. Keep the existing `base` values and entries for supported older clients.
   The initial catalog deliberately starts with the already pinned revisions.
2. Run `python release/regression_scopes.py --scope testers-core`. The published
   catalog test checks schema, duplicate approvals and coverage of current bundled
   testers. Run `--scope testers-ui` for changes to update selection or presentation.
3. Run the affected real smoke check from the repository root:
   `python tests/manual/supra_tester_smoke.py ft_printf` (or `libft`),
   `python tests/manual/gnl_tester_smoke.py`,
   `python tests/manual/germinette_tester_smoke.py`, or
   `python tests/manual/native_tester_smoke.py`.
   These scripts apply the local candidate catalog without fetching the published
   one. Existing PR CI runs the Docker checks on amd64 and ARM; the opt-in native
   workflow checks Linux, Intel macOS and Apple Silicon. Validate each supported
   fingerprint being promoted, including failure/incomplete results and unchanged
   original project files. A source commit merely existing is not approval.
4. Review and merge the catalog change to `main`. Installed clients pick it up
   before their next run after the one-hour cache expires. A branch push alone
   does not publish updates. Do not approve a revision that needs a new recipe or
   result protocol for an older fingerprint: that requires a client update.

To obtain baseline entries for a changed bundled definition or recipe, run:

```sh
python -m ft_tui.features.projects.adapters.tester_updates > /tmp/42tui-tester-baselines.json
```

Merge new entries from that file into `v1.json`; do not overwrite older supported
entries or their approved refs. For a rollback, set the affected entries' `ref`
back to the last validated commit. Clients never mutate an existing image tag or
remove a working image automatically. Network failure while building a newly
selected image can still fail that run; an update-catalog cache is not a source
or image cache. No arbitrary upstream branch is executed automatically.
