# Tester runtimes and validation

Native push_swap uses a private Python environment and disposable C build. Git,
Python, make and a C compiler must already be installed. It executes host code
after per-run consent and requires no Docker runtime. Its upstream default suite
has no validated structured reader, so a successful exit remains unverified.

Francinette is no longer bundled. Supra covers printf/libft and the native tester
covers push_swap; the Tripouille fork covers get_next_line. Custom catalog entries stay
user-controlled, and old Docker images are not automatically deleted.

## Headless macOS runtime assessment — 2026-10-30

[Colima's documentation](https://github.com/abiosoft/colima) describes a headless
Docker-compatible VM, with configurable CPU, memory and disk allocation. It still
requires installation, a Linux VM and a Docker CLI. Native execution avoids those
costs for suitable testers; Colima does not eliminate the Supra Linux images or
prove memory-check equivalence on either architecture.

The [Colima FAQ](https://github.com/abiosoft/colima/blob/main/docs/FAQ.md) states that
starting it can change the default Docker context. The app must preserve the
existing user configuration. Therefore retain the existing chosen Docker runtime
and do not silently install or select Colima. A disposable evaluation must use
isolated Colima/Docker configuration and an explicit socket/context, exercise
startup, folder mounts with spaces/quotes, builds, run/cancel/retry and shutdown,
and measure startup time, idle/peak RAM and image/disk use before selecting it.
This machine has Docker Desktop available but no Colima installation; no Colima
resource measurements or successful lifecycle validation are claimed.

## Reproducible platform checks

Run `python tests/manual/native_tester_smoke.py` from the repository root with the
package installed. It builds an intentionally incorrect C fixture, runs the full
pinned push_swap default suite, checks the printed failures and confirms the original remains unchanged.
The pinned default suite exits zero even with failures: the app must retain an
unverified result rather than a confirmed pass. Inspect `native-tester-smoke.log`: upstream memory tools can time out or
be unavailable, and a printed memory PASS alone is not validation.

The opt-in `tester-platforms.yml` workflow runs that same check on Ubuntu,
macOS Intel and Apple Silicon and retains transcripts. A workflow definition is
not a successful run. School-managed Linux still needs its own permission/runtime
check; a hosted Linux runner does not establish that policy. For actual container coverage, use the Supra smoke commands below with an
accessible engine. No personal projects/accounts are used by these checks.

## Supra printf/libft containers

The bundled definitions use `recipe = "supra"`, the pinned Debian bookworm-slim
base digest, and exact source SHAs from HeduroFR/printf_tester (the maintained
portability fork) and nda-cunh/libft_tester.
They share one multi-stage recipe and cached toolchain layers; each final image
contains one tester and the GCC C-project build/runtime dependencies. Vala,
Meson, Ninja, NASM and Git are build-only. Debian package updates are resolved
when building an image; this is a common Linux ABI/toolchain, not a bit-reproducible
package archive. Image identity includes the recipe bytes and source revision.

The printf fork selects native Linux arm64 on Apple Silicon/Linux ARM and amd64
on Intel hosts. The libft definition still requires Linux amd64 emulation on ARM.
Existing host/engine detection,
architecture inspection and writable-mount/execution probes remain mandatory.
Windows is outside the current client support matrix. No emulator, system package,
Docker context or daemon permission is silently changed by these definitions.

Before testing, the container entrypoint runs `make fclean` and `make -B all`
in the disposable project mount. This prevents up-to-date host artifacts (including
macOS Mach-O objects) from entering Linux shared libraries. A failed cleanup or
build stops before the tester runs. Original objects/archives are never cleaned.

Install directly through Meson, avoiding upstream install.sh's user-level pip
fallback. Install binaries without a `.git` sibling so background `git pull` and
self-rebuild cannot run. Execution disables networking, drops capabilities, denies
privilege elevation and makes the root filesystem read-only; only the disposable
project mount and bounded `/tmp` are writable. Temporary storage permits execution
because the testers compile and load shared libraries there. This limits host exposure, but is
not evidence that one tester finds more bugs or has stronger memory checks.

The printf fork writes a version-1 JSON report inside the disposable copy through
`--report`; the existing `result_file` reader validates it and displays counts.
The fork compares binary stdout and return values in isolated sequential children,
with a two-second case timeout and a ten-minute runner watchdog. Failed builds do
not produce a report. libft still has no structured reader and stays unverified
even if its process exits zero. Missing and forbidden functions remain visible in the log. Supra is the bundled choice for printf/libft. No upstream code is vendored in the Python package.

`python tests/manual/supra_tester_smoke.py ft_printf` (or `libft`) builds and runs
the actual pinned tester against an incomplete synthetic C fixture, checks the
expected diagnostics and unchanged original files, and reports image size. PR CI
runs both cases on amd64 and ARM Linux runners and retains logs. printf uses
native ARM; libft uses emulation. These checks do not establish memory-check
equivalence or every passing/failing student implementation.

For local testing from the shared workspace, launch
`42tui-client/.venv/bin/42tui`, open an ft_printf project, then use **Run Supra printf tester**.
The new pinned image builds automatically; old images are not reused. A custom
`~/.config/42tui/testers.toml` entry with the same ID overrides the bundled definition.

Custom tester definitions can set `interactive_input = false` to hide the input field.
It defaults to true for existing custom testers; the field is hidden after a run finishes.

## get_next_line

The bundled Tripouille tester uses the pinned 42TUI fork's mandatory suite in
native Linux amd64 or arm64 Docker containers, with GCC, Clang and Valgrind.
It runs in a disposable project copy and never invokes upstream's `git pull`.
The fork writes a version-1 JSON report: functional checks count as passed or
failed, leaks count as failures, and test crashes/timeouts count as errors.
Upstream allocation-size checks remain visible in the log but are not counted.
The suite expects `get_next_line.c`, `get_next_line_utils.c` and
`get_next_line.h` at the project root. Bonus tests are not run by this integration.
The report reflects this suite's
checks; it does not prove complete correctness or memory safety.

Run `python tests/manual/gnl_tester_smoke.py` from the client repository with a
working Docker engine to exercise passing, failing and prematurely exiting synthetic
projects through the real adapter; the originals are checked for changes. CI is
configured for native amd64 and arm64 runners, but a workflow definition is not a
successful run.
