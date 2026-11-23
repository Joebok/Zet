# Broaden Zet E2E task coverage
Status: active
Related issue/specification: approved test coverage expansion in Codex conversation

## Goal
Maintain 20 isolated Playwright task scenarios covering active workflows using the existing prepared-response queue and private test server. Retain the existing four journeys and add 16 representative journeys.

## Current behavior
The four scenarios are in `tests/e2e/fast.spec.mjs`; live Narrative is separately invoked. The runner currently drops forwarded CLI arguments, the server reset retains some queue catalog state, and all fast tests navigate through Narrative readiness. Python 3.14.6 and `npm.cmd run test:e2e` were verified before implementation (4/4, 43.6 seconds).

## Invariants and constraints
Keep AI answers prepared and route them through real services. Keep all paths under per-run temporary roots. Do not invoke live AI or render services. Keep retired workflows out of coverage. No production API or serialized format changes.

## Implementation steps
### WP0 - Harness foundation
- Dependencies: none.
- Files/interfaces: `Scripts/run-e2e.mjs`, Playwright config, `tests/e2e/server.py`, E2E helpers/specs.
- Work: forward CLI args, broaden fast spec discovery, isolate scenario setup, remove universal Narrative startup, retain failures and capture page exceptions.
- Acceptance: `--list` and grep select scenarios reliably; existing four pass.
- Validation: filtered list/run and full fast suite.
- Status: complete.

### WP1 - Strengthen existing journeys
- Dependencies: WP0.
- Files/interfaces: existing E2E spec and helpers.
- Work: assert S1 appearance persistence, S2 frozen source identities/order, S3 retry frozen-input continuity, and S4 universe ownership.
- Acceptance: persisted assertions pass without altering scenario purpose.
- Validation: each updated scenario, then full suite.
- Status: complete for S1, S3 and S4 assertions; S2 retained its prior assertions because its frozen source bindings are exposed through the Candidate Board review, not the generic Narrative job detail.

### WP2-WP17 - Representative user workflows
- Dependencies: WP0; WP8 may share WP7 helpers.
- Files/interfaces: one workflow-owned E2E spec and private fixture changes only as required.
- Work and acceptance: implement the approved Character generation, template editing, Character Wizard, Costume Wizard, Minor Character, Image Generation, reconstruction, Inventory, universe/species, character rename/archive, source consumption, Narrative finishing, animation, zine, board protection, and restart recovery scenarios as specified in the approved plan.
- Validation: run each scenario independently with prepared answers and private storage.
- Status: complete. Twenty maintained scenarios cover the four original journeys plus all sixteen planned task scopes: upstream Body/Head generation and captured sources; template editing and conflict; Character and Costume Wizards; Minor Characters; Image Generation and reconstruction; Inventory and universe settings; Character rename/archive; published source consumption; Narrative finishing, animation, and zines; candidate-board safety; and interrupted-production recovery.

### WP18 - Documentation and live-check repair
- Dependencies: scenarios that change coverage claims.
- Files/interfaces: `Docs/Testing.md`, `Docs/CODE_MAP.md`, `Docs/INVARIANTS.md`, `plans/README.md`, `tests/e2e/live.spec.mjs`.
- Work: reconcile scenario count and coverage statements; repair live selectors and size expectations while leaving execution separately opt-in.
- Acceptance: documentation matches executable scenarios; live spec is statically compatible with current UI.
- Validation: full fast suite, `git diff --check`; do not run live workflow.
- Status: complete. Testing, code-map, invariant, and plan summaries match the 20 listed scenarios. Live selectors and sizing expectations are repaired; live execution remains separately invoked and was not run.

## Progress and decisions
- Plan approved for implementation on 2026-11-23. Use 20 total maintained scenarios, no new dependencies, prepared responses, and separate live execution.
- `npm.cmd run test:e2e -- --list` listed four fast scenarios after matcher correction.
- Focused S1, S3 and S4 runs passed. The initial S3 enhancement exposed a missing helper; it was added before validation.
- Full `npm.cmd run test:e2e` passed all four scenarios in 39.6 seconds.
- The new Minor Character journey passed independently with prepared isolated storage (1/1, 5.1 seconds).
- Image Generation asset setup passed independently (1/1, 4.8 seconds); the complete six-scenario suite passed in 41.4 seconds.
- Universe and species persistence/stale-revision journey passed independently (1/1, 4.9 seconds).
- Character template save/conflict journey passed independently; fixture master bytes are restored in a `finally` block.
- Inventory image edit/alias-preservation journey passed independently with fixture image bytes.
- Image Generation now routes a prepared output through its queue, harvests, selects, and publishes to Inventory. The nine-scenario suite passed in 49.6 seconds; Windows emitted a non-fatal file-sharing warning during usage maintenance.
- Image Generation additionally verifies queued render cancellation and withdrawal. Focused scenario passed; full nine-scenario suite passed in 46.1 seconds with a non-fatal Windows usage-maintenance warning.
- Character and phase rename journey passed independently, restoring fixture names in `finally`; full ten-scenario suite passed in 49.1 seconds.
- Character archive safety journey passed independently and in the full suite. It restores the temporary active-work marker, verifies preview/version fencing, then archives the fixture; the archive test is ordered last because it removes that fixture. Full eleven-scenario suite passed in 53.6 seconds.
- The latest full `npm.cmd run test:e2e` passed all eleven maintained scenarios in 52.7 seconds. A transient run that overlapped a self-removing disposable test was discarded; the clean maintained-suite rerun passed. Windows logged non-fatal usage-maintenance file-sharing warnings.
- Character Wizard prepared interview, reload/resume, preview-before-publication, and explicit acceptance journey passed independently (1/1). Its fixture session and created character are removed in `finally`.
- Full `npm.cmd run test:e2e` passed all eleven maintained scenarios in 56.7 seconds. Windows logged two non-fatal usage-maintenance file-sharing warnings. `git diff --check` passed.
- Costume Wizard private test and acceptance journey passed independently (1/1). The prepared image answer is harvested by the normal auxiliary-job path; the helper leaves harvest receipts to the application. Cleanup unlocks the Assembly candidate through its owning workflow; the fixture catalog is isolated per run.
- Image Generation reconstruction and correction journey passed independently (1/1). It retains original evidence bytes for analysis, edits/applies the proposed prompt through the Reconstruction UI, verifies the prepared render carries the target, and checks comparison/correction ancestry after a fresh context reload.
- Narrative scene finishing journey passed independently (1/1). It crops a pinned backdrop, renders a 16:9 Final assembly at frozen 2720x1536 dimensions, adds and confirms lettering, rejects a stale confirmation, and verifies lock/reload preserves lettering while original artwork bytes stay intact. The isolated server now prepares this exact-size image response.
- Published source consumption journey passed independently (1/1). Test-only setup supplies all Body-Reference orientations, then the scenario creates and publishes an Identity Key, creates a partial Turnaround, unlocks FRONT, and confirms new source choices exclude it while the saved Inventory key still resolves.
- Narrative animation journey passed independently (1/1). It seeds a prepared lettered assembly, binds its locked source, persists camera/text timing, rejects a stale revision, reloads the animation, and confirms the export embeds the pinned artwork and lettering layer.
- Narrative zine journey passed independently (1/1). It assigns a locked finished scene to print pages, reloads saved page bindings, regenerates the printable image, checks output dimensions, and verifies the source bytes remain unchanged.
- Candidate-board safety journey passed independently (1/1). It reviews multiple Drafts, cancels a queued upscale, rejects stale and incomplete cleanup confirmation, and applies a fresh exact protected-effect approval.
- Recovery journey passed independently (1/1). A separately owned server restarts against the same fixture root/config/queue/context, resumes and harvests queued work, then fences an old failed-attempt answer after retry.
- Upstream Body/Head journey passed independently (1/1). It publishes a non-FRONT Body Reference bound to FRONT and a Head FRONT from a different phase, checking frozen source identities, hashes and phase-change provenance.
- Rename and archive checks are combined into one destructive Character management scenario, matching WP11's single-scenario acceptance and preserving the 20-scenario target. The combined scenario passed independently.
- The WP2 probe exposed a `source_pipeline` NameError in cross-phase Head source saving. It blocked WP2's required workflow and was fixed with a localized guard correction; the new prepared-response scenario passes.
- `npm.cmd run test:e2e -- --list` listed exactly 20 tests in 17 files.
- Final `npm.cmd run test:e2e` passed all 20 scenarios in 2.1 minutes. Windows printed two non-fatal image-usage maintenance file-sharing warnings.
- Final `git diff --check` passed after documentation reconciliation. The optional live check was not invoked.
- The nine-scenario fast suite passed in 44.5 seconds.
- The eight-scenario fast suite passed in 43.5 seconds.
- The seven-scenario fast suite passed in 42.5 seconds. Windows logged a transient socket-reset callback after S2; all seven scenarios still passed.
- `git diff --check` passed before the final documentation/live updates; rerun before delivery.

## Final results
Harness, all 20 planned scenarios, documentation reconciliation, and final validation are complete. The optional live check remains unrun by design.
