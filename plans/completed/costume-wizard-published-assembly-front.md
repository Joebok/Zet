# Costume Wizard published FRONT rendering fix
Status: active
Related issue/specification: Costume Wizard test render failure documented in Zet Tester run 2026-11-13T17-38-25-538Z-daef488f

## Goal
Allow Costume Wizard FRONT test renders to use the current published Assembly FRONT, retain private isolation, and resume queued renders.

## Current behavior
`CostumeWizardService._render_job` resolves an Asset Container source, overwrites its lock flag, then hands the lower-case container pipeline name and universe path to a renderer that requires canonical naming and a private-workspace path. Its initial candidate has no image path, so input preparation also uses the process working directory. Existing approved S2 covers normal Dressing board publication, not the Costume Wizard handoff.

## Desired behavior
Capture and validate the currently published FRONT lock inside the private render workspace, prepare all render artifacts under the private run, resume from saved run/ask IDs, and keep the test candidate separate from normal Dressing boards. Draft and Final Assembly sources are eligible, while the Wizard render itself is Draft.

## Impact analysis
- Service: `zet/services/costume_wizard_service.py`; no interface or serialized schema changes.
- Documentation: Local Characters component and Testing results. The active plan records implementation and validation.

## Invariants and constraints
- Trust only a currently published source resolved for the app's selected universe. Verify path ownership, file existence, and bytes before staging.
- Preserve source candidate, Inventory, hash, and mode provenance. Never modify the real container or queue live image generation for validation.
- Keep private runs and references under the private workspace; continuation uses its captured source.

## Implementation steps
### WP1 - Capture and stage the published FRONT source
- Dependencies: none.
- Files/interfaces: `costume_wizard_service.py`; existing LocalAssetSourceService and atomic byte writer.
- Work: Validate approved Inventory ownership, canonicalize pipeline identity, verify source hash and universe path, atomically stage exact bytes under the Wizard render root, and pass source metadata and mode into the private run.
- Acceptance: Draft and Final locks are accepted; missing, unlocked, changed, and out-of-universe records fail before a render ask is queued.
- Validation: disposable focused workflow checks.
- Status: complete.

### WP2 - Keep render preparation inside the private run and resume
- Dependencies: WP1.
- Files/interfaces: `costume_wizard_service.py`.
- Work: Derive candidate input directory from private run root and F-001 identity. New attempts resolve a fresh source; pending attempts reuse saved run and ask IDs and captured bytes.
- Acceptance: No preparation artifacts escape the private run; repeat continuation does not enqueue a duplicate ask; a valid answer reaches TEST_READY with a retrievable image.
- Validation: disposable prepared-answer replay, with interrupted/resumed attempt check.
- Status: complete.

### WP3 - Verify downstream flow and update knowledge
- Dependencies: WP1, WP2.
- Files/interfaces: Local Characters component notes and Testing results.
- Work: Replay Costume Wizard draft, test render, acceptance, Draft 4 Dressing FRONT, review, and publication. Update docs and archive this plan with results.
- Acceptance: Private test stays off the regular Dressing board; published result references the Assembly lock; no permanent test or dependency is added.
- Validation: `npm.cmd run test:e2e`; `git diff --check`; disposable flow replay.
- Status: complete.

## Validation
Observed: disposable Draft and Final Wizard-to-Dressing replays passed with prepared render answers and mocked Wizard review/Luna ranking. The approved `npm.cmd run test:e2e` baseline passed all four scenarios in 40.8s. Python syntax and `git diff --check` passed. No live AI/render calls.

## Progress and decisions
Initial replay reproduced the reported source identity error, the workspace path error after identity normalization, and the empty candidate-path preparation defect. The production service now validates and privately stages the published source and uses a private candidate input directory. Recovery continues from saved run and ask IDs.

## Final results
Implemented in `zet/services/costume_wizard_service.py`. Updated Local Characters and Testing documentation. Draft and Final replay accepted Princess and published the ranked Dressing FRONT image with approved Inventory provenance. Browser-specific Wizard interaction and image visual quality were not validated by the prepared-response replay.

