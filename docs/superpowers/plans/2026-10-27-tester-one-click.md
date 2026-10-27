# Single-button tester implementation plan

**Goal:** Run Francinette from one primary action on school Linux and personal macOS without sudo.

**Architecture:** Use Docker on both platforms. Keep setup/build/run in the adapter and presentation/consent in the sidebar. Preserve the compact image-removal control, pinned source revisions, architecture-specific images, mount probes, operation locking and terminal logs. No backend/API changes.

## Constraints and platform limits

- Never run privileged host commands, install host system packages, change Docker socket/group permissions or start system services.
- School Linux requires an existing accessible Docker engine with BuildKit. Detect missing, stopped and denied states rather than assuming Docker is installed. An existing rootless service may be started with `systemctl --user` after approval; other managed services require school staff.
- On macOS, use existing Docker or install Docker Desktop under `~/Applications` with unprivileged `hdiutil`, `ditto`, `codesign` and `mv`. Stage the copy before publishing it; remove failed staging and detach the installer. Keep Docker Desktop user-level defaults. OS policy may still prevent launching apps; native validation is required.
- Bundled `.git` source URLs build directly inside Docker BuildKit with the full pinned revision and retained Git metadata. Custom clone URLs without `.git` use already-installed Git, preserving prior support. Missing Git gives explicit clone-URL guidance and never triggers host installation.
- Require an existing local project folder before any setup. Capture that folder before showing approval. Bound startup waiting to 180 seconds and preserve interruption/retry behavior.

## Task: Unified unprivileged setup and run

- [x] Write and observe failing adapter regressions for privileged plans, school Docker failures, host-Git-free builds and per-user Mac setup.
- [x] Replace privileged installation and system service startup with user-owned paths and existing user-service startup.
- [x] Build bundled sources inside Docker and preserve custom repository behavior and Git metadata.
- [x] Keep one Run/Retry action per configured tester and show actionable status/errors below it.
- [x] Verify approval cancellation, captured project paths, double clicks, terminal restoration and small-screen navigation.
- [x] Reproduce and fix review findings: failed copy prevents retry, HTTPS URLs without `.git` lose Git semantics, missing Git metadata, Linux approval uses Mac-only wording.
- [x] Update README, French/Spanish copy and user/development changelogs.
- [x] Record final tester scope, locale checks, ownership coverage and diff review. Do not commit or push without authorization.

## Execution record

The user approved the original single-button proposal for both platforms and requested execution. They later clarified that school Linux has no sudo and Docker availability is uncertain. That requirement supersedes the earlier privileged installer design. The user performed the required fetch after this environment's DNS failures; branch `feat/tester-one-click` and `origin/main` start at `bb5caff`.

A read-only review checked the original and revised flows. Each functional finding was reproduced with a failing regression and fixed. Adapter suite: 54 passed before final scope validation.

Validation uses a temporary runner heartbeat for this sandbox's asyncio executor shutdown wakeup stall. No workaround is shipped in the product or tests. Native school Docker access, real image builds and macOS installation remain unverified. No commit, push or release is performed.

Final verification: 70 tester tests passed in 54.868 seconds; 2 locale tests passed;
all 820 discovered tests have exactly one scope owner; whitespace diff checks passed.
A real WSL2/Ubuntu 26.04 missing-Docker probe returned no installation plan and
executed zero host setup commands. It displayed the school-access requirement and
released the operation lock. Flake8 is unavailable. No native Mac or school Docker
engine was available for end-to-end installation/build/run checks. Full CI remains.
