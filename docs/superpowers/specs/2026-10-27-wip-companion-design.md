# WIP companion design

Status: approved by the user on 2026-10-27; implementation follows the linked plan
at `../plans/2026-10-27-wip-companion.md`.

## Intent

Add WIP, the cute 42 otter mascot, as a small companion in the terminal app.
His presence communicates quiet company and DND; his delivery of a poke should
remain deliberately interruptive. The browser studies establish a working
direction, not final artwork or proof of terminal rendering.

## Agreed direction

- WIP is a tiny crawling otter with a low body, four small paws, a tail and a
  smaller, rounded head. Preserve brown fur, a cream muzzle and a dark nose.
- The accessory is a **42 badge on a lanyard**, not a scarf. Colored blocks are
  not a substitute for a recognizable badge.
- His permanent perch is at the top right of the TUI.
- When DND is enabled, he becomes sleepy and sleeps.
- A poke still appears in the middle of the screen and interrupts the user.
  WIP travels from his permanent perch to deliver it.
- At the destination, WIP grips the **top-left edge** of the poke box. His body,
  tail and badge hang below his paws. Keep the message readable beside him.
- The current crawling and hanging mockup is acceptable as a starting point.
  Further artwork polish is deferred.

## Approaches explored

1. **Upright otter and a message near the header.** Easy to keep in one area,
   but the large upright character and peripheral delivery did not match the
   requested size, crawling personality or interruptive poke behavior.
2. **Tiny crawling sprite and a centered poke box.** Requires separate crawl,
   sleep and hanging poses and coordination between shell and modal. This is
   the direction selected through the mockup iterations: WIP has a permanent
   top-right perch and a temporary perch on the poke box's top-left edge.

The renderer remains an implementation decision. Reuse existing terminal image
support rather than introducing a separate graphics protocol.

## Proposed interaction details

These details are recommendations for approval, rather than additional user
requirements.

### Idle and DND

Reserve a small header area so WIP does not hide controls or account/version
information. Start with the visual footprint of the 48 × 32 pixel browser study;
translate it to terminal cells using the actual cell dimensions. Do not assume
browser pixels are terminal pixels. Keep the companion small on narrow screens.

Use occasional blinks while idle. Enter sleep with a short settling motion and
return to idle with a brief wake-up. Avoid random speech, chores or pet-care needs.
Use the existing effective DND state, including the social and clubs settings.
Until the relevant state is known, avoid speculative poke delivery.

### Poke delivery

1. Accept only eligible pokes from the existing inbox state.
2. Start a short crawl from the top-right perch toward the centered poke box.
3. Transition to a hanging pose with both paws anchored to the top-left border.
4. Keep sender identity, message and explicit dismissal controls visible. A
   subtle body or tail wiggle provides persistence without moving the text.
5. After confirmed dismissal of all displayed pokes, climb back onto the border
   and return to the permanent perch.

Proposed travel time is approximately one second. Animation must not delay access
to the message or dismissal controls. The modal retains keyboard focus and the
existing Escape dismissal semantics. Movement completion never acknowledges a
poke. If dismissal fails, retain the message and allow retry.

For multiple pokes, reconcile the existing modal rather than spawning competing
companions or replaying travel for every poll. Preserve scrolling and per-poke
dismissal. A poke arriving during dismissal must not be acknowledged accidentally.

### DND during delivery

While DND is active, do not start a new delivery or ring for incoming pokes. On
leaving DND, reconcile the current inbox and deliver only still-eligible pokes.
Do not rely on a separate local pending-message queue.

Proposed behavior if DND is enabled during travel or while the modal is visible:
hide the delivery without acknowledging it, return WIP to sleep, and let the
existing inbox retain the pending poke. This intentionally extends current
behavior: an already-open poke modal currently continues to reconcile during DND.
Test this transition explicitly; do not route it through the acknowledgement
action used by Escape.

### Motion, visibility and failures

Provide a reduced-motion option: show the centered message immediately with a
static hanging pose. Offer a companion visibility option; hiding WIP must preserve
ordinary centered poke delivery and DND rules. Exact settings placement is left
to implementation, using existing preferences conventions.

Respect existing image modes (`auto`, `sixel`, `tgp`, `halfcell`, `off`). Use the
existing capability policy; do not probe terminal stdin from a widget. For
half-cell rendering, verify the sprite remains recognizable at its small size.
With images off or an asset/render failure, preserve all message content and
controls, using a compact text DND indicator if needed.

Recompute the hanging anchor on resize, scrolling and poke-list changes. Never
cover sender text, the close button or the message body. If space is insufficient,
prioritize readable poke content over showing the companion. Pause hidden
animation work and cancel timers on teardown. Modal changes, expiry, disconnects
and account/provider context changes must clear stale delivery state.

## Integration and ownership

Current integration points:

- `src/ft_tui/ui/app.py`: app composition and companion lifecycle.
- `src/ft_tui/features/social/views/inbox.py`: `dnd()`, `_show_pokes()`, eligibility,
  context fences and modal reconciliation.
- `src/ft_tui/features/social/views/pokes.py`: centered `PokeNotification`,
  sender portraits, dismissal and acknowledgement lifecycle.
- `src/ft_tui/ui/terminal_capabilities.py`: image mode and cell geometry policy.

Keep social data, expiry, deduplication and acknowledgements in their existing
owners. The companion consumes presentation state; it is not another social
poller or a second source of DND truth. Keep graphics and animation in presentation
code, and use shared button widgets. Choose precise new module/resource locations
after examining shell/header composition during implementation planning.

Use bundled transparent sprite frames for idle, crawl, settling/sleep, wake,
hang and return transitions. Separate poses must preserve consistent proportions
and grip anchors. Final asset production and supported-protocol animation checks
remain implementation work. The browser canvas study is a reference, not a
production sprite sheet. Do not add a generative service or runtime network
dependency for artwork.

## Scope and compatibility

This is a client-only presentation feature using existing poke and DND contracts.
No backend, API, database migration or rollout ordering change is expected. If
implementation reveals a contract gap, revisit the design before extending scope.

Out of scope: a general pet framework, new social actions, pet progression,
custom characters, new sound effects, replacing sender portraits and final sprite
polish. Existing bell preferences remain authoritative.

The design document needs no release. A completed companion feature would normally
have minor release impact; assess it against accumulated changes when implemented.
Do not bump or publish a version as part of this design task.

## Acceptance and verification

- Tiny crawling WIP appears at the top right without hiding existing controls.
- Poke delivery reaches a centered modal and ends in a stable top-left hanging
  pose. Paws stay anchored as the tail/body moves.
- The badge reads as a 42 badge on a lanyard; head proportions remain small.
- DND changes appearance and suppresses new delivery; leaving DND reconciles
  current unexpired pokes without duplicate acknowledgements.
- Mid-delivery DND, expiry, account changes, modal interruption and resize cannot
  leave an orphan sprite, steal focus or acknowledge an unseen message.
- Multiple arrivals and failed dismissals preserve existing message semantics.
- Reduced motion, hidden companion, images off and renderer failures preserve
  centered poke functionality.
- Focused UI/state regressions cover lifecycle and acknowledgement transitions.
  Register any new test modules with the repository's regression scopes.
- Manually verify real terminal rendering, erasure and placement for available
  image protocols and small layouts. Report unavailable protocol checks honestly.

## Review status

The design was checked against existing inbox DND, poke eligibility, modal
reconciliation, Escape acknowledgement and terminal image policy. Proposed
mid-delivery DND handling is explicitly distinguished from current behavior.
The visual direction is accepted provisionally. The user approved this written
design and authorized implementation; further sprite polish remains deferred.
