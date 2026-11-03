# Costume Wizard render and batch creation repair
Status: complete
Related issue/specification: Joe's RockStar Costume Wizard and Create New Batch report (2026-11-03).

## Goal
Restore private Costume Wizard test rendering and enable Create batch when the selected costume's requirements are ready. Preserve the accepted RockStar costume and production library state.

## Current behavior
The saved RockStar wizard session failed with `Expected a path beneath PipelineCandidates`. `CostumeWizardService._render_job` gives its isolated Dressing adapter a `runs` root beneath `_state/CostumeWizard`; progression and state serialization require a `PipelineCandidates` ancestor. The batch dialog starts with a disabled Create button; `readiness()` reports ready but never updates that button. The wizard's nested render-preparation adapter also needs the same real locked-source store used by the private batch's preview.

## Desired behavior
An eligible Costume Wizard FRONT test can create and prepare its private run without the path or source-store failure. Create batch becomes enabled after successful readiness, stays disabled for blocking requirements, and the server still checks on submission.

## Impact analysis
`costume_wizard_service.py`, `local_character_asset_pipeline_service.py`, `local_asset_pipeline.js`, and affected local-character/code-map documentation. No data format or route change. Existing S2 exercises Dressing batch creation but not Costume Wizard test rendering or the disabled-state transition.

## Invariants and constraints
Test runs remain private and universe bound; production locked source images are read only. No new permanent tests or live render calls without Joe's approval. Do not mutate the accepted RockStar session or normal library as validation.

## Implementation steps
### WP1 — Private render batch path and inputs
- Dependencies: none.
- Files/interfaces: `zet/services/costume_wizard_service.py`, `zet/services/local_character_asset_pipeline_service.py`.
- Work: place private runs below the private universe's `PipelineCandidates` tree and pass the preview's locked-source store into nested render preparation.
- Acceptance: a private Dressing test reaches queue preparation without a path or missing-lock error.
- Validation: disposable isolated check with prepared sources; Python syntax check.
- Status: complete.

### WP2 — Batch dialog readiness state
- Dependencies: none.
- Files/interfaces: `zet/web/static/local_asset_pipeline.js`.
- Work: tie the Create button's enabled state to current preview readiness; retain server validation.
- Acceptance: ready enables Create; blockers and failed checks disable it.
- Validation: JS syntax and disposable browser interaction if feasible.
- Status: complete.

### WP3 — Documentation and final checks
- Dependencies: WP1, WP2.
- Files/interfaces: `Docs/COMPONENTS/LOCAL_CHARACTERS.md`, `Docs/CODE_MAP.md`, this plan.
- Work: record the private test boundary and observed validation, review final diff.
- Acceptance: targeted checks and `git diff --check` pass; plan is archived.
- Validation: approved focused S2 or full baseline as relevant, plus diff review.
- Status: complete.

## Validation
The isolated prepared wizard check staged the private FRONT ask with frozen inputs and reached its expected pending result without a live AI call. A disposable Chromium check observed Create enabled for ready Body-Reference requirements and disabled after invalid input. `npm.cmd run test:e2e -- --grep character-to-costume` ran the four approved fast scenarios; all passed (44.3 seconds). Python AST, JavaScript syntax, and `git diff --check` passed.

## Risks and alternatives
Private test rendering cannot prove live ComfyUI output. Saved accepted wizard sessions are not resumable; the corrected path applies to future tests and RockStar can be rendered through its new batch.

## Progress and decisions
Inspected the saved RockStar session read only. The recorded failure identifies the missing `PipelineCandidates` ancestor. A nested workflow adapter also used the private library's empty asset store for current locked sources; it now receives the owning adapter's store. No production state was changed.

## Final results
Private wizard FRONT tests can stage a render with the current locked source, and the batch dialog's Create button tracks current readiness. The accepted RockStar session remains accepted and is not resumable. A new RockStar Dressing batch can use its accepted template. Actual ComfyUI image output and artistic quality were not exercised.
