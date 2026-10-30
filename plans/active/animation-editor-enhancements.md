# Animation editor enhancements
Status: active
Related plan: [Story Animation](story-animation.md)

## Goal
Compact scene cards, target-based zoom motion, and independent timed text fades.
Preserve existing animation tracks, pinned images, revision fencing, and the
unrelated unfinished work in the parent plan.

## Work packets
- WP1: Extend version 1 camera validation and retain existing keyframe formats.
  Validate legacy and target specifications with disposable service checks.
- WP2: Add target framing to the standalone player. Validate zoom and seek in
  disposable Chromium against the legacy rendering behavior.
- WP3: Rebuild scene controls as compact cards, retaining unrepresentable tracks
  until explicitly replaced. Validate drafts and responsive layout in Chromium.
- WP4: Add an accessible target picker with revision-checked save and cancellation.
  Validate selection, keyboard, resize, reload, and conflict behavior.
- WP5: Update Narrative, data model, code map, testing evidence, and ADR; run the
  approved fast suite and diff checks, then archive this plan when complete.

## Constraints
Timed text starts at the specified millisecond, fades in over 300 ms, begins
fading out at start plus duration, and finishes fading 300 ms later. Do not add
permanent tests or dependencies, call live AI services, modify production data,
or deploy.

## Progress
Camera mode validation started. Remaining packets are pending.
