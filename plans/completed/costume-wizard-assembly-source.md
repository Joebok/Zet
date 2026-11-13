# Restore Costume Wizard FRONT Test Render
Status: active
Related issue/specification: ZetTester run 2026-11-13T05-18-10-705Z-33e60726

## Goal
Let Costume Wizard test a costume against the current published Character Assembly FRONT at Draft or Final quality, using private captured inputs.

## Current behavior
The wizard creates a private Dressing run. Its adapter reads Assembly from legacy `LocalAssets`, but current container publications are resolved through `LocalAssetSourceService`. Dressing preparation also insists that a live Draft source match its Draft render mode.

## Desired behavior
Resolve the current same-universe FRONT publication, snapshot its bytes and provenance into the private run, and prepare the Draft test from that snapshot. Pending attempts reuse captured inputs; new test actions resolve the current source again.

## Impact analysis
`costume_wizard_service.py`, `local_character_asset_pipeline_service.py`, `Docs/COMPONENTS/LOCAL_CHARACTERS.md`, `Docs/CODE_MAP.md`. No public API or migration. Existing S2 covers regular Assembly/Dressing, not the Wizard's private source path.

## Invariants and constraints
Only an available, approved, locked publication for this character, phase, pipeline and FRONT is eligible. Preserve the actual source quality and checksum. Capture bytes before queueing; do not publish the private Dressing output. No live inference or permanent test additions.

## Implementation steps
### WP1 — Resolve and snapshot current publication
- Dependencies: none.
- Files/interfaces: `costume_wizard_service.py`, `local_character_asset_pipeline_service.py`.
- Work: allow an internal source record only for one-view private FRONT Dressing creation; validate and copy it into the run snapshot.
- Acceptance: Draft and Final published sources create one private candidate; missing/unpublished sources fail before an ask.
- Validation: isolated real-container publication fixture.
- Status: complete.

### WP2 — Prepare from captured bytes
- Dependencies: WP1.
- Files/interfaces: `costume_wizard_service.py`, `local_character_asset_pipeline_service.py`.
- Work: prepare the Dressing candidate with the normal compiler/frozen-input path, persist it, then queue; reuse existing run/input on pending resume and remove the legacy store override.
- Acceptance: both qualities queue Draft renders from private snapshots and upstream changes after capture do not alter inputs.
- Validation: prepared AI Proxy response fixture; assert captured reference bytes and TEST_READY.
- Status: complete.

### WP3 — Document and validate
- Dependencies: WP1, WP2.
- Files/interfaces: local-character component docs, code map, this plan.
- Work: document source selection and private snapshot semantics; record checks.
- Acceptance: disposable cases and approved E2E baseline pass; diff is clean.
- Validation: `npm.cmd run test:e2e`; `git diff --check`.
- Status: complete.

## Progress and decisions
Run inspection confirmed the selected Draft publication and file are valid, approved, and checksum-matching. The wizard now resolves the current source projection and passes it via an internal argument restricted to single-view FRONT Dressing. The private run stores captured source identity and bytes; source quality is retained, while the wizard's mode check accepts the captured snapshot for its Draft output. Pending runs reuse their saved candidate and render input.

## Validation
`python3 -B` AST parsing passed for the changed Python services. A disposable source-record check passed for Draft and Final metadata preservation and rejected an unlocked source. `npm.cmd run test:e2e` passed all four approved scenarios (41.0s), including S2 Assembly-to-Dressing. `git diff --check` passed.

The approved E2E scenario covers ordinary Assembly-to-Dressing publication; this run did not stage a wizard render against both qualities or simulate a prepared response/resume. No live inference or permanent test scenario was run or added.

## Final results
The Costume Wizard uses the current published Assembly FRONT, captures it in its private test run, and stages its Dressing output as Draft. Missing or unpublished sources produce an actionable lock-and-publish error before run creation. No migration or public API change.
