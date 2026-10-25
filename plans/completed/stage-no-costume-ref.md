# Stage Costume Dressing without a prior costume reference
Status: complete
Related issue/specification: user request in Codex

## Goal
Add a per-view Costume Dressing action that freshly compiles and stages a prompt
and required references without any earlier dressed view. Preserve normal staging,
rotation, and batch state.

## Current behavior
`ImageGeneratorStagingService` stages normal views using `CharacterRenderSlots` and
Stage Rotation using `CostumeRotationService`. Dressing's compiler requires the
matching Assembly image and automatically adds front-costume or selected-view
references according to the normal recipe. The per-view controls and staging POST
are in `local_asset_pipeline.js` and `local_character_asset_pipeline_router.py`.

## Desired behavior
Every Dressing view offers **Stage no Costume Ref**. It freshly compiles with the
view's matching Assembly snapshot, costume template, and view-filtered supplemental
resources; it never adds a prior costume view. Staging bypasses Dressing progression
and costume anchors while retaining source and Image Generator input validation.

## Implementation steps
### WP1 — Prepare independent Dressing inputs
- Dependencies: none.
- Files/interfaces: new `zet/services/costume_no_reference_service.py`.
- Work: verify the matching Assembly snapshot, compile into temporary storage via
  the existing adapter/compiler and template revision, then freeze ordered inputs.
- Acceptance: no Dressing anchor or selected-view reference enters the prompt or
  staged image list; no batch records are modified.
- Validation: disposable checks across all eight views and an active template
  revision. The fixture did not contain view-filtered supplemental images.
- Status: complete.

### WP2 — Integrate staging and availability
- Dependencies: WP1.
- Files/interfaces: `image_generator_staging_service.py`, `render_slot_service.py`,
  and `local_character_asset_pipeline_router.py`.
- Work: add optional `no_costume_ref` request flag; reject rotation combinations and
  non-Dressing use; dispatch to WP1; expose per-view availability reason.
- Acceptance: staging skips progression/anchor gates but validates view, Assembly,
  prompt, profile, image bytes, and limits before replacing generator workspace.
- Validation: a disposable staging-service handoff check verified the packaged
  Assembly reference; invalid combined modes failed before workspace replacement.
- Status: complete.

### WP3 — Add the button and document the handoff
- Dependencies: WP2.
- Files/interfaces: `local_asset_pipeline.js`, `zet.js`,
  `Docs/COMPONENTS/LOCAL_CHARACTERS.md`.
- Work: add per-view control, send request flag, show status, and document behavior.
- Acceptance: button opens Image Generator with prompt/references ready; normal
  staging and rotation remain unchanged.
- Validation: the approved S2 regression, changed JavaScript syntax, and
  `git diff --check`. The new browser click path was not exercised in Chromium.
- Status: complete.

## Constraints
Use existing dependencies and compiler contracts. Add no maintained tests or live
AI calls. Do not refresh source snapshots or mutate run selections, prompts, locks,
or reference recipes.

## Validation
`npm.cmd run test:e2e -- --grep "character-to-costume"` passed all four approved
fast scenarios (38.7 seconds). Disposable compiler checks passed all eight views
with an active template revision and confirmed only matching Assembly references;
a BACK Image Generator handoff check confirmed reference packaging and conflicting
mode rejection before workspace replacement. Python AST checks for changed Python
modules, JavaScript syntax checks for both changed scripts, and `git diff --check`
passed. The new browser click path and missing-snapshot failure path were not
exercised in Chromium. No permanent tests, live AI calls, or normal-library writes
were used.

## Progress and decisions
The independent compiler uses `active_revision` and `template_sources` directly
because provenance recording requires outputs below `PipelineCandidates`, while
staging artifacts belong in temporary storage. The disposable check confirmed the
accepted revision was applied without writing batch prompt artifacts.

## Final results
Added **Stage no Costume Ref** to each Costume Dressing view. The action compiles
with the matching Assembly snapshot and active template revision, preserves compiled
supplemental references, and stages through existing Image Generator validation.
S2 and disposable validation passed as recorded above. No unresolved issues.
