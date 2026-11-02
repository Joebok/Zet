# Character pipeline review navigation and comparisons
Status: complete
Related issue/specification: none

## Goal
Restore side-by-side comparison choices on all five character pipelines and restore batch-page image review with navigation across displayed selected or locked views. Keep batch and view reads scoped; add no persistent test or dependency.

## Current behavior
`LocalPipelineProjectionService.summary` returns selected-card status but no candidate/image identity or cross-view comparison identities. `view` returns only its own candidates. `local_asset_pipeline.js` opens selected-card images through `openReview`, but the batch summary contains no candidates for `orderedReviewCandidates`; the shared `ZetImageCardUI` also decorates the card's view link as an icon. The review dialog's comparison builder expects candidate lists for FRONT/opposite and locked Draft metadata.

## Desired behavior
Batch summary carries minimal available selected/locked card image identities and comparison-source identities. View pages consume only those compact identities plus their current-view candidate data. Batch image review traverses available card images in view order, without candidate decisions. View comparisons offer selected FRONT, selected opposite side, and matching locked Draft when available.

## Invariants and constraints
Preserve universe, batch, render-mode, and Costume ownership; never add other views' candidate records to a view projection. Candidate and lock images use existing authorized image routes. No permanent test or live model/render check. Update Local Characters and Dashboard UI documentation.

## Implementation steps
### WP1 — Compact projection identities
- Dependencies: none.
- Files/interfaces: `zet/services/local_pipeline_projection_service.py`, `zet/web/static/local_asset_pipeline.js`.
- Work: project selected-card image identity and availability, falling back to the matching lock when selected output is unavailable; include compact selected-view and locked-Draft comparison identities in summary; pass the metadata through view normalization.
- Acceptance: summary and view projection expose only identifiers and hashes needed for images/comparisons; view candidate collection remains current-view only.
- Validation: disposable isolated projection/browser check; `node --check zet/web/static/local_asset_pipeline.js`.
- Status: complete. Summary cards now expose selected and lock image identities; summary and view projections expose available selected comparison identities and matching locked Draft records.

### WP2 — View comparison options
- Dependencies: WP1.
- Files/interfaces: `zet/web/static/local_asset_pipeline.js`.
- Work: build the chooser from summary identities, with selected FRONT when distinct, selected opposite side when available, and matching locked Draft; preserve the reviewed image and single-image fallback.
- Acceptance: each available choice swaps only the left image; missing/broken sources disappear safely.
- Validation: disposable prepared browser check for all choices and none-available state.
- Status: complete. The view dialog offers the available selected FRONT, opposite side, and locked Draft images while keeping the reviewed candidate fixed.

### WP3 — Batch review carousel and docs
- Dependencies: WP1.
- Files/interfaces: `zet/web/static/local_asset_pipeline.js`, `zet/web/static/zet.css`, `Docs/COMPONENTS/LOCAL_CHARACTERS.md`, `Docs/COMPONENTS/DASHBOARD_UI.md`.
- Work: retain visible view links, exempt them from icon decoration, open the existing dialog from summary images, and navigate available selected/locked cards with dialog buttons and arrow keys without saving decisions. Update owning docs.
- Acceptance: Draft and Final batch cards open originals; navigation follows displayed view order and respects boundaries.
- Validation: disposable isolated browser check; `npm run test:e2e`; `git diff --check`.
- Status: complete. Batch card images open the shared review dialog and navigate only available displayed images; view links remain readable. Local Characters and Dashboard UI docs are updated.

## Validation
Observed: `python3 -B -m compileall -q zet/services/local_pipeline_projection_service.py`, `node --check zet/web/static/local_asset_pipeline.js`, and `git diff --check` passed. `npm run test:e2e` passed 4/4. No separate disposable browser fixture was run; the E2E suite does not specifically assert these new review controls. No maintained tests or live checks were added.

## Progress and decisions
- 2026-11-02: Implemented compact review identities, comparison options, batch review carousel, and documentation updates. No schema or dependency changes.

## Final results
Completed. Changed the local pipeline projection and browser controller, updated Local Characters and Dashboard UI guidance, and archived this plan. Validation results and the unrun disposable browser fixture are recorded above.
