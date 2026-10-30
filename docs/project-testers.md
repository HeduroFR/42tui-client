# Project testers

Francinette is no longer bundled. The Tripouille tester covers the mandatory
`get_next_line` suite with a structured summary.
Existing user catalog definitions remain user-controlled; remove a custom
Francinette entry there if you added one. Previously downloaded images are not
automatically deleted.

Configure an existing local project folder, find **Testers** below Registration
(or press `t` in Projects), then choose **Run Supra libft tester** or
**Run Supra printf tester**, or **Run Tripouille get_next_line tester**.
The same button handles setup and retries.

Tester builds and cleanup run against a temporary copy of the project, excluding
Git metadata. Your original files stay in place; generated files in the copy are
discarded after the run, including after failure or cancellation. Keep the tester
log when you need its diagnostics. Allow enough temporary disk space for the copy.

Runs open an in-app tester workspace with live, scrollable output, optional line input,
cancellation, elapsed time and **Run again**. Close it to keep using the app,
then choose **View full output** from a project's tester section to return.
**Pause output** stops automatic scrolling. Full logs are saved automatically;
**Open log folder** opens its directory in your file explorer. The output view
retains recent output only.
The console interprets cursor redraws and colors on a 100-column terminal with
scrollback; narrow windows can scroll horizontally. Process completion alone does
not mean all tests passed. The workspace and saved log distinguish reported test
failures, process failures, unreadable reports and unverified results, with the
process exit code and available test counts. The printf and get_next_line forks
provide structured summaries; libft and push_swap results remain unverified.
Full-screen terminal applications are not supported.

Custom definitions in `~/.config/42tui/testers.toml` (or
`$XDG_CONFIG_HOME/42tui/testers.toml`) can opt into structured results by adding
`result_file = "reports/result.json"` to their `[[testers]]` entry. The tester must
write a UTF-8 JSON report at that path under `/project` during each run:

```json
{"version": 1, "total": 4, "passed": 2, "failed": 1, "errors": 0, "skipped": 1}
```

All counts are required nonnegative integers, must add up to `total`, and must
include at least one executed test. Only a valid report with no failures/errors
and process exit code zero yields **Tests passed**. An absent, invalid, empty or
all-skipped report cannot confirm passing tests. An explicit `"incomplete": true`
allows an all-skipped report to be displayed as unverified; a report with skipped
checks also remains unverified. Reports are limited to 64 KiB;
symbolic links and nonregular files are rejected. Use a dedicated report path,
not a source file: an inherited report is removed from the disposable copy before execution
to prevent stale results. The original project is unchanged. Reported success
describes that tester's checks, not official project validation.

For **push_swap**, choose **Run Push_swap tester**. This uses the pinned
[ft_ps_tester](https://github.com/italoalmeida0/ft_ps_tester) (MIT) natively,
without Docker. Git, Python, `make` and your project's compiler/libraries must be
available already. Review and approve native execution before each run: it can
access your computer; the private environment and disposable copy are not a
sandbox. External/absolute symlinks in the project copy are rejected. Setup
fetches the pinned source and creates a temporary Python virtual environment
without pip; `make` builds the disposable project, then the tester runs its full
default suite. Setup needs network access on every run, and all temporary files
are removed afterward. No system packages are installed. This tester currently
has no validated structured report, so inspect its log rather than interpreting
an unverified result as a pass.

Custom native definitions use `runtime = "native"`, optional
`prepare = [["make"]]`, and the normal `command` list. Arguments can reference
`{source}` (the pinned source/context), `{project}` (the project copy) and
`{python}` (the private environment's interpreter). Commands run without a shell,
from the project copy. Docker remains the default for existing definitions.

For **ft_printf** and **libft**, **Supra printf tester** and
**Supra libft tester** actions build the pinned testers in Linux
containers on Linux and macOS. The printf fork supports native arm64; libft
requires amd64 emulation on ARM. The engine and mount checks report diagnostics
when it is unavailable. No Vala, Meson,
NASM or tester dependencies are installed on the host. Both use the same pinned
Debian base and GCC/glibc environment, with separate source-specific images and
shared Docker layers. Their runtime has networking disabled, a read-only root
filesystem and a writable disposable project copy plus temporary storage.

The libft tester reports **unverified** completion. For every tester, read the full transcript,
including failures, missing functions and forbidden-function checks. They do not establish official project correctness or superior memory coverage. To include printf bonus tests, override `supra-printf` in your user catalog
with the same fields and append `"--bonus"` to its `command`. Runtime Makefiles
must work with GCC/cc; compiler-specific dependencies are not installed automatically.
See [runtime details and validation](tester-runtimes.md).

For Docker testers on Linux, an accessible Docker engine with BuildKit support must already be
available. Check with `docker info` from your normal account. 42TUI can start an
existing rootless user service; it does not install system packages, start system
services, change socket permissions or use `sudo`. If Docker is missing or access
is denied at school, ask school staff to make an engine available.

On macOS, the setup button can install Docker Desktop in `~/Applications` without
using Homebrew or a privileged installer. Keep Docker's user-level defaults:
user CLI tools, no default system socket and no privileged port mapping. Accept
Docker's terms if prompted, then testing continues automatically. Existing local
or remote Docker contexts remain supported. See Docker's
[Mac permission requirements](https://docs.docker.com/desktop/setup/install/mac-permission-requirements/).

The bundled tester builds its pinned source inside Docker, so host Git and C
compiler installation are unnecessary. Custom tester clone URLs without a `.git`
suffix retain support through an existing Git installation; use an HTTPS `.git`
clone URL to build those without host Git.


## Python modules and A-Maze-ing

Germinette is available for Python modules 00–10, modules 05 bis and 06 bis,
and A-Maze-ing. Choose the tester in the selected project's Testers section.
The first run builds a shared pinned Linux image; removing it from any of these
projects removes it for all of them. Docker must be available. Runs use a
disposable project copy and disable networking.

The bis checkers provide reported counts for the checks they execute; a skipped
check leaves the run incomplete. The other Germinette checkers report recorded
failures but do not reliably account for every outcome, so their reports remain
incomplete even if no failure is recorded: read their logs. These checks cannot
replace peer evaluation. Germinette targets particular subject versions and may
not match a newer subject or every valid solution. Bis checkers do not run mypy.
