# Luna-ranked local image cards
Status: active
Related issue/specification: [Issue #60](https://github.com/Joebok/Zet/issues/60)

## Goal
After a complete Luna ranking, show ranked local pipeline candidate cards in Luna order so rank #1 is leftmost and rank #2 follows it. Apply through the shared gallery to Body-Reference, Head-Image, Character-Assembly, and Costume-Dressing. Preserve the original report as acceptance authority.

## Current behavior
The shared local pipeline gallery in `zet/web/static/local_asset_pipeline.js` renders cards by `slots_by_view`; each card's `slot` is used by generate/regen/retry/clear actions. Luna stores `luna_ordered_candidate_ids`, while `ordered_candidate_ids` may contain manual adjustments. The gallery currently displays each candidate's effective-rank badge but leaves cards in slot order. Local character documentation and Invariant 14 state that rank never changes the grid order and render positions remain independent of candidates.

## Desired behavior
When a view has a `COMPLETE` ranking, display candidates represented in Luna's order first, then remaining occupied candidates in their existing slot order, then empty-slot placeholders. Candidate labels and slot actions continue to identify/operate on the candidate's original physical slot. Without a complete ranking, retain slot order. The shared UI means all four local character pipelines receive the behavior.

## Impact analysis
- Browser presentation: `zet/web/static/local_asset_pipeline.js` only; no service transition, serialized data, rank mutation, or slot-map mutation.
- Component contract: `Docs/COMPONENTS/LOCAL_CHARACTERS.md` documents ranking display behavior and the existing S2 coverage gap.
- Invariant 14: clarify that physical positions and candidate membership remain stable while presentation may order cards by completed Luna ranking.
- Tests: use helper revision-bound approved S1-S3 validation and an ignored, prepared-fixture acceptance check for multi-candidate rank ordering, all four pipeline selectors, card slot actions, and incomplete ranking fallback. No permanent test or scenario is added.

## Invariants and constraints
Preserve candidate IDs, `slots_by_view`, selection/lock protection and action ownership. Luna's original order is `luna_ordered_candidate_ids`; manual review rank adjustments remain separate. No normal library, queue, index, live model, render service, dependency, or permanent test is used.

## Implementation steps
### WP1 — Shared ranked gallery presentation
- Dependencies: none.
- Files/interfaces: `zet/web/static/local_asset_pipeline.js`, shared local pipeline gallery.
- Work: order the rendered card presentation by complete Luna ranking while keeping each occupied card attached to its physical slot and controls; retain original order for non-complete ranking and append empty slots after candidates.
- Acceptance: ranks #1 and #2 render first in that order; candidate actions still send the physical slot and expected candidate ID; all four page configurations share this behavior.
- Validation: focused code review plus prepared-fixture browser/API acceptance check; helper validation command for approved S1-S3 and `git diff --check`.
- Status: complete. The shared gallery sorts candidate cards by complete Luna order while retaining physical slot labels/actions, appends empty slots, and restores card focus/details by candidate identity when a live update changes gallery order. Rank labels now use Luna's original order when available.

### WP2 — Update owning contract documentation
- Dependencies: WP1.
- Files/interfaces: `Docs/COMPONENTS/LOCAL_CHARACTERS.md`, Invariant 14 in `Docs/INVARIANTS.md`.
- Work: document Luna-ordered presentation separately from fixed physical slot identity and state the test coverage limits.
- Acceptance: docs match the UI behavior and existing service/storage invariant.
- Validation: source-linked documentation review and `git diff --check`.
- Status: in progress. Updated the local character component contract and Invariant 14 to distinguish presentation order from physical slot bindings.

## Validation
Planned: helper `validate --token` runs the unchanged approved three-scenario baseline plus `git diff --check`; run a disposable, prepared-fixture check with known multiple candidates/rankings to verify all four pipeline UI configurations and slot-action mappings. `node --check zet/web/static/local_asset_pipeline.js` and an initial `git diff --check` passed. No live model/render check or maintained coverage expansion.

## Risks and alternatives
Changing persisted slot maps would violate slot identity and action fencing, so only presentation order changes. If the prepared fixture cannot represent all four pipeline configurations without introducing an unsupported fixture or permanent scenario, verify shared rendering logic and representative UI behavior, record the gap, and ask Joe only if acceptance cannot be demonstrated.

## Progress and decisions
- 2026-10-14: Verified one shared browser gallery for all local character pages and separate Luna versus manually adjusted ordering arrays. Kept backend and persisted render slots unchanged. Rank completion changes only browser card order; actions remain tied to the source slot.

## Final results
Pending implementation and validation.
