# Speed up character pipeline review
Status: active
Related issue/specification: none

## Goal
Make review navigation responsive across Body-Reference, Head-Image, Character-Assembly, and Costume-Dressing. Avoid saving unchanged decisions, reusing mutation results, and building full run details for candidate image requests. Do not change saved decisions, selected images, schemas, or locks in existing libraries.

## Current behavior
The shared review UI saves a decision on each navigation; `perform` follows mutations with a full detail request. Candidate image routes call each adapter's full `detail`, repeating ranking, lock, file and candidate projection. The Elder Tsaeytte Head-Image batch has 64 candidates across eight views. Read-only local timings were ~0.44 seconds for detail and ~0.23 seconds for an image request.

## Desired behavior
Unchanged navigation performs no request; changed decisions save before navigation and remain visible if save fails. Review, select, and rank mutations update the UI from their response without a detail GET. Candidate image resolution validates run membership and containment without full detail projection. Image URLs remain stable until bound image content changes.

## Invariants and constraints
Preserve universe/costume ownership, portable path decoding, candidate membership, path containment, selection eligibility, request fencing, human decisions, and immutable locks. No dependencies, permanent test expansion, live generation, production deployment, or edits to production batch data.

## Implementation steps
### WP1 — Skip unchanged review saves
- Dependencies: none.
- Files/interfaces: `zet/web/static/local_asset_pipeline.js`.
- Normalize saved legacy Pass/Fail decisions and serialize review actions. Save only a changed decision before navigation.
- Acceptance: unchanged navigation updates locally without review/detail requests; failed saves keep the current candidate and edit.
- Validation: JavaScript syntax and disposable browser checks.
- Status: complete. Changed decisions save before moving; unchanged navigation makes no request. Review actions are serialized.

### WP2 — Reuse mutation results
- Dependencies: WP1.
- Files/interfaces: shared pipeline JavaScript, `local_prompt_improvement_service.py`, `local_image_workflow_service.py`, `local_character_asset_pipeline_router.py`.
- Project review/select/rank mutation results into the existing detail presentation shape without rereading state; merge them directly in the browser and fence stale poll/action responses. Version reference-image URLs by their existing content identity.
- Acceptance: unchanged selection takes one POST with no detail GET; review position and edits survive refreshes.
- Validation: disposable request-count, delayed-response, and failure checks.
- Status: complete. Review/select/rank responses are presented directly, stale polls are fenced, and source/reference URLs use stable saved identities.

### WP3 — Resolve candidate images directly
- Dependencies: none.
- Files/interfaces: focused resolver in `zet/services`, Body, Head, and shared Assembly/Dressing service adapters.
- Read owning spec/state, merge current candidate membership, decode portable paths, and verify the image stays inside the run. Keep costume qualification in the existing run resolver.
- Acceptance: image requests do not call full detail and reject absent, detached, missing, or outside-run files.
- Validation: disposable isolated checks across all pipelines.
- Status: complete. All four adapters use the resolver; current membership, missing/detached IDs, and run containment are checked.

### WP4 — Validate and document
- Dependencies: WP1–WP3.
- Update local-character docs and code map. Run the approved E2E baseline, syntax checks, `git diff --check`, and disposable 64-candidate browser checks. Record actual outcomes and archive this plan when complete.
- Status: complete. Documentation and approved validation completed; no permanent tests or live render calls were added.

## Progress and decisions
- Review navigation saves changed decisions before moving, per Joe's preference.
- 2026-10-17: Read-only inspection and timing completed; no production data was changed.
- 2026-10-17: Isolated resolver checks passed for all four adapters without calling detail; detached and outside-run files were rejected. 63/64 existing Elder Tsaeytte candidate entries resolved to current images.
- 2026-10-17: `node --check`, Python compile check, and `git diff --check` passed. The approved `npm.cmd run test:e2e` baseline passed all four scenarios in 36.5 seconds on the final code. An earlier S2 attempt timed out with ranking complete in its failure snapshot; a fresh isolated S2 run passed in 5.9 seconds, followed by the passing full baseline.

## Final results
Review navigation avoids redundant saves and detail fetches; selection and ranking merge their mutation response. Candidate image delivery checks the active candidate record directly. Local-character documentation and code map point to the resolver. No UI-specific 64-candidate browser timing run was performed; the existing 64-candidate Elder batch was used only for read-only image-resolution verification.
