# Collaboration

Preserve unrelated local work. Use dedicated feat/, fix/ or docs/ branches and pull requests to main.
Do not commit, push, tag, publish, deploy or change repository visibility without authorization.
Use a one-line English Conventional Commit matching the branch prefix.
Keep credentials, .env files, user databases, browser profiles, sessions and .local/ out of Git.
Use relative paths in shared instructions. Review the diff and run relevant checks before delivery.

# Client

Python >=3.12. Package name ft-tui; commands 42tui, 42goto, 42tui-zed-lsp.
Use AppButton from src/ft_tui/ui/button.py and AppSelect from src/ft_tui/ui/select.py
(or their localized wrappers); never import these widgets directly elsewhere.
project.version in pyproject.toml is authoritative. Repository separation does not authorize a version bump.
Install: pipx install --python python3.12 --editable .
Reinstall: pipx install --force --python python3.12 --editable .
Release only from reviewed main, with matching changelog and tag, after python release/check_version.py vX.Y.Z.
Release publication needs separate explicit authorization. Do not reuse a published version.
