# WIP Companion Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Ship a tiny crawling WIP companion with sleep and centered poke delivery.

**Architecture:** Reuse the social inbox and modal as the only message owners.
A shared presentation widget renders bundled pixel frames, with a small header
perch and a modal-owned travel/hanging sprite. Preferences use existing storage.

**Tech Stack:** Python 3.12+, Textual 8, Pillow, textual-image, unittest.

**Spec:** `docs/superpowers/specs/2026-10-27-wip-companion-design.md`

## Global Constraints

- No backend/API changes, version bumps, commits or publication.
- Preserve explicit acknowledgement, DND, expiry, context fences and bell preferences.
- Reuse terminal image modes and shared AppButton/AppSelect.
- Keep artwork small; preserve the 42 badge on a lanyard and top-left grip anchor.
- Use disposable test storage and synthetic social data.

## Review Focus

- DND enabled under a covered poke modal must not pop its covering screen.
- Context changes during travel must not show or acknowledge an old account's poke.
- Reduced motion, hidden sprites and image failures must preserve message access.
- Resize and multiple pokes must keep the sprite off message text and controls.
- Failed dismissal and arrivals during dismissal must retain exact acknowledgement IDs.

### Task 1: Sprite and perch presentation

**Files:** Create `src/ft_tui/ui/companion.py`,
`src/ft_tui/ui/companion_art.py`, `src/ft_tui/assets/wip.png`,
`tools/build_wip_sprite.py`, `tests/test_ui_companion.py`.
Modify `src/ft_tui/ui/layout.py`, `pyproject.toml`, `MANIFEST.in`,
`release/check_package.py`, `release/smoke_package.py`.

**Interfaces:** `WipSprite(pose='idle')` exposes `set_pose(pose, frame=0)`;
`WipPerch` owns only local animation timers. `companion_enabled(app)` respects
visibility/image preferences. `companion_art.frame(pose, index)` loads cached RGBA
frames; `POSES` defines the strip order.

- [x] Add tests for distinct transparent crawl/sleep/hang frames, tiny perch bounds,
  images-off and missing-image behavior. Run them and observe missing-feature failures.
- [x] Build bundled nearest-neighbor pixel frames from the approved canvas concept;
  implement rendering using existing image protocols with a half-cell fallback.
- [x] Reserve a compact top-right perch beside the existing header. Animate only
  visible sprites and stop timers on unmount.
- [x] Run focused companion tests and verify asset packaging declarations.

### Task 2: Poke travel, hanging and DND lifecycle

**Files:** Modify `src/ft_tui/features/social/views/pokes.py`,
`src/ft_tui/features/social/views/inbox.py`, `tests/test_ui_social.py`,
`tests/test_ui_companion.py`.

**Interfaces:** `PokeNotification` retains `reconcile`, `acknowledge`, `dismiss`.
Its local sprite travels from the header anchor to a reserved top-left slot;
`WipPerch` reads accepted social/DND state without network operations.

- [x] Add failing tests for DND hiding an open modal without acknowledging,
  including a covering modal, and restoring an eligible poke when DND ends.
- [x] Add failing tests for travel/hang, multiple arrivals, resize, expiration,
  account switches, reduced motion, image-off and failed-dismiss return behavior.
- [x] Integrate local travel/hang/return presentation without delaying modal
  controls or acknowledging on animation completion. Preserve message semantics.
- [x] Run companion and social tests, including existing acknowledgement races.

### Task 3: Preferences, release notes and final validation

**Files:** Modify `src/ft_tui/features/settings/state.py`,
`src/ft_tui/features/settings/views/workspace.py`, `src/ft_tui/app/startup.py`,
`src/ft_tui/ui/app.py`, `src/ft_tui/locales/fr.json`,
`src/ft_tui/locales/es.json`, `tests/test_ui_terminal_settings.py`,
`tests/test_shell_startup_service.py`, `release/regression_scopes.py`,
`tests/test_canonical_imports.py`, `CHANGELOG.md`, `DEV_CHANGELOG.md`.

**Interfaces:** Saved booleans `companion_visible` (default true) and
`companion_motion` (default true) live in SettingsState and startup preferences.
Saving changes refreshes companion widgets across the screen stack.

- [x] Add failing persistence/default tests; implement Appearance selects for
  visibility and motion using the existing settings service. Translate new copy.
- [x] Register companion tests in `clubs-social` and run focused social,
  settings, startup and architecture checks.
- [x] Review the full diff and run a fresh independent review. Fix material
  findings, record real checks and unavailable native-terminal validation.
- [x] Update both changelogs and this checklist. Leave changes uncommitted on
  `feat/wip-companion`; offer exact staging/commit/push commands at delivery.

## Execution notes

- User approved the design and said to proceed. Execute inline without another
  confirmation; use a fresh reviewer at completion.
- Continue in the dedicated feature checkout, preserving the uncommitted design
  and changelog. Do not add another worktree or commit without authorization.
- Keep this plan as the execution record; update checkboxes as tasks complete.
- Updated the branch to origin/main `4e48e9b` during execution, preserving its
  0.4.1 package version and 0.4.0 published baseline. WIP itself did not bump a
  version; its recommended minor release is 0.5.0.
- Fresh review found return-position jumps and unreadable half-cell badge text.
  Dedicated regressions cover the corrected home/grip anchors and text lettering.
  Follow-up review also caught native pixels being recreated on covered screens;
  the active-screen guard and resume restoration pass the added regression.
  Follow-up independent review found no remaining material issues.
- Validation: 76 clubs/social tests (one opt-in simulation skipped), 21 settings
  tests, 91 release/architecture/startup tests, two locale tests, ownership for
  817 discovered tests, diff/undefined-name checks, wheel/sdist resource checks
  and installed-wheel smoke checks. Native terminal graphics checks remain manual.
