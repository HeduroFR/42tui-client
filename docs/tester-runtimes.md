# Tester runtimes and validation

Native push_swap uses a private Python environment and disposable C build. Git,
Python, make and a C compiler must already be installed. It executes host code
after per-run consent and requires no Docker runtime. Its upstream default suite
has no validated structured reader, so a successful exit remains unverified.

Francinette stays in Linux containers to retain Valgrind and the upstream Linux
toolchain. The image definition is pinned, but its Dockerfile clones Francinette
upstream; the summary hook therefore checks the exact BaseTester.py SHA-256 before
reading its results and disables automatic updates for the verified source. The
validated source revision is b828ca56497afd1f183da483ba64caf6fe6326e3. Unrecognized
source yields an unreadable report. The report counts suite outcomes and the
norm/function-list checks, not individual test assertions. Failed norm or suite
checks remain failures even when upstream exits zero. Logs preserve details.

## Headless macOS runtime assessment — 2026-10-30

[Colima's documentation](https://github.com/abiosoft/colima) describes a headless
Docker-compatible VM, with configurable CPU, memory and disk allocation. It still
requires installation, a Linux VM and a Docker CLI. Native execution avoids those
costs for suitable testers; Colima does not eliminate Francinette's Linux image or
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

Native Francinette is not selected: macOS cannot provide the Linux Valgrind checks
merely through a Python venv. A smaller replacement image must pin all upstream
sources and demonstrate the same suites and memory checks on Linux amd64/arm64
before adoption. The existing runtime remains available during that work.

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
check; a hosted Linux runner does not establish that policy. For container/UI
coverage, use `python tests/manual/tester_smoke.py NEW_DISPOSABLE_DIRECTORY` with
an accessible engine. No personal projects/accounts are used by these checks.

## Supra printf/libft containers

The bundled definitions use `recipe = "supra"`, the pinned Debian bookworm-slim
base digest, and exact source SHAs from nda-cunh/printf_tester and libft_tester.
They share one multi-stage recipe and cached toolchain layers; each final image
contains one tester and the GCC C-project build/runtime dependencies. Vala,
Meson, Ninja, NASM and Git are build-only. Debian package updates are resolved
when building an image; this is a common Linux ABI/toolchain, not a bit-reproducible
package archive. Image identity includes the recipe bytes and source revision.

Both definitions select Linux amd64 on every supported host. On Apple Silicon or
Linux ARM, Docker must provide amd64 emulation. Existing host/engine detection,
architecture inspection and writable-mount/execution probes remain mandatory.
Windows is outside the current client support matrix. No emulator, system package,
Docker context or daemon permission is silently changed by these definitions.

Install directly through Meson, avoiding upstream install.sh's user-level pip
fallback. Install binaries without a `.git` sibling so background `git pull` and
self-rebuild cannot run. Execution disables networking, drops capabilities, denies
privilege elevation and makes the root filesystem read-only; only the disposable
project mount and bounded `/tmp` are writable. Temporary storage permits execution
because the testers compile and load shared libraries there. This limits host exposure, but is
not evidence that one tester finds more bugs or has stronger memory checks.

The sources lack a validated machine-readable summary integration here. Keep
results unverified even if the process exits zero. Missing functions and forbidden
function checks must remain visible in the full log. Francinette stays available;
Supra is an additional choice. No upstream code is vendored in the Python package.

`python tests/manual/supra_tester_smoke.py ft_printf` (or `libft`) builds and runs
the actual pinned tester against an incomplete synthetic C fixture, checks the
expected diagnostics and unchanged original files, and reports image size. PR CI
runs both cases on amd64 and ARM Linux runners (amd64 emulation) and retains logs. These checks do not establish all
passing/failing cases, memory-check equivalence, or Mac/ARM emulation support.
Local Docker Desktop could not start in this session; live container validation
must be established through CI and later Mac/ARM runs before release claims.
