# Character view overrides
Status: complete

## Goal and behavior
Each Body, Head, Assembly and Dressing batch view accepts a browsed or pasted
image as its working selection, with the existing explicit Lock action available.
No inference, production library mutation, new dependency or permanent test is needed.

## Impact and constraints
Use the shared workflow boundary, focused service, local router and pipeline UI.
Keep universe/costume ownership, portable paths, distinct candidate identities,
state locking, immutable published bytes and downstream choices. Preserve existing
unrelated Head changes and local-character documentation edits.
Documentation owners: LOCAL_CHARACTERS, DATA_MODEL and CODE_MAP. S2 covers existing
Assembly/Dressing publication; disposable checks cover imports and all four pages.

## Luna sized work packets
### WP1 — Import service and HTTP endpoint
- Files: local_character_override_service.py, local_image_workflow_service.py,
  local_character_asset_pipeline_router.py.
- Dependencies: existing slot maps and shared manual selection.
- Accept PNG/JPEG/WebP under 32 MB; validate contents, fence stale selection,
  reject active work, create an owned candidate and select it. Replace the selected
  working slot (retaining history), or use an empty/unrendered unprotected slot
  when unselected. Full rendered boards require an explicit selection or clearing.
- Acceptance: invalid/stale imports leave state unchanged; original locks survive.
- Validation: disposable isolated service/API checks and Python syntax.
- Status: complete.

### WP2 — Per-view browse/paste presentation
- Files: local_asset_pipeline.js; reuse ZetImageInput.
- Dependencies: WP1.
- Preview staged image and explicitly apply with Use as selected. Existing Lock
  remains separate. Guard late callbacks after navigation; preserve input on polls.
- Acceptance: each pipeline/view has labeled browse/paste controls and useful errors.
- Validation: JS syntax, disposable browser checks, approved S2.
- Status: complete.

### WP3 — Documentation and final review
- Files: affected documents above and this plan.
- Dependencies: WP1/WP2.
- Record actual validation, review diff, archive completed plan.
- Validation: git diff --check.
- Status: complete.

## Progress and decisions
- Reused shared manual selection for current and legacy batches, matching refinement
  adoption while retaining immutable published images and downstream choices.
- Overrides have independent candidates and additive provenance; saved recipe fields
  remain available for future regeneration. No schema migration or ADR was needed.
- Added explicit Unlock published image on selected override cards so the old lock
  remains actionable after replacing its working candidate.
- Initial disposable checks exposed fixture/check limitations: only FRONT prerequisite
  locks were seeded; already-selected views were collapsed; an unlock of an absent
  lock correctly failed; eager response-body inspection hit Chromium cache eviction.
  The fixture setup and checks were corrected without changing maintained scenarios.

## Final results
- `npm.cmd run test:e2e -- --grep character-to-costume`: passed (latest 1 test,
  18.1s including startup; earlier run 19.9s).
- Disposable API checks passed import/replacement/image delivery, invalid input and
  stale selection refusal for all 32 pipeline/view combinations. All four pipelines
  locked imports and preserved the prior published image after another override.
- Disposable Chromium checks passed all four pages' eight inputs, file browse,
  clipboard paste events, preview/explicit apply, polling draft preservation and
  390px viewport bounds. Desktop/narrow screenshots were inspected. Dressing's
  explicit unlock/lock/reload passed.
- Latest fresh-fixture HTTP/browser check passed an eight-reserved-slot Head board,
  mocked clipboard-read button, gallery Override label and Review dialog.
- Disposable service checks passed full reserved-board replacement, active/slot
  fences, concurrent selection conflict, portable persistence and invalid/oversized
  input rejection with unchanged state.
- Python import/AST, JS syntax and `git diff --check` passed. Final diff reviewed;
  existing Head implementation/documentation/plan changes were preserved.
- Updated LOCAL_CHARACTERS, DATA_MODEL and CODE_MAP. No permanent tests, dependencies,
  live inference, production-library writes or deployment were added. Native device
  clipboard permission behavior remains unverified.
