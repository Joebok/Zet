# Character prompt review, staged generation, and image refinement
Status: complete
Related specification: Joe's approved plan in the implementation chat, 2026-10-18.

## Goal and desired behavior
All new Body, Head, Assembly and Dressing batches first review all eight compiled prompts without images. Independently selectable corrections create batch versions; master promotion stays explicit. Continue advances FRONT → front quarters → profiles → rear quarters → BACK, using selected same-side predecessors. A selected image opens a dedicated resumable refinement page with optional selected-view comparisons, targeted edits, and explicit same-slot adoption. Changed references produce advisory warnings only. Existing published bytes and submitted inputs remain immutable.

## Current behavior and impact
LocalTemplateRevisionService currently requires representative images and proposes whole-source edits. CharacterRenderSlots supports individual reference recipes, while batch runners/automation still use FRONT-centric ordering. Minor Characters and ImageTrueUpService provide the correction interaction and AI_Proxy integration patterns. Affected knowledge: LOCAL_CHARACTERS, PROMPTS, DATA_MODEL, INVARIANTS, CODE_MAP, Testing and a new ADR. Preserve universe ownership, portable paths, queue attempts, ordered references and immutable publication.

## Work packets
Each packet is sequential work by the current agent; no delegation.

### WP1 — Text-only compilation
- Dependencies: none. Files: four Run_*_Jobs character compilers, shared compiler support, new local prompt-preview service.
- Work: share real composition with an explicitly non-renderable text preview using declared references; retain production file validation.
- Acceptance/validation: disposable eight-view/all-pipeline compilation and missing-render-reference rejection.
- Status: complete.

### WP2 — Selectable text corrections
- Dependencies: WP1. Files: local_template_revision_service.py, AI continuation registration.
- Work: frozen text evidence, structured findings, deterministic selected edits, validation, no-change acceptance, child iterations and stale-source checks.
- Acceptance/validation: prepared analysis has zero image attachments; selective/overlap/stale/no-change checks.
- Status: complete.

### WP3 — Prompt review UI
- Dependencies: WP2. Files: local_template_improvement.js and dashboard markup/styles.
- Work: compiled prompts, unchecked findings, persisted decisions, custom feedback, acceptance and retained promotion/history.
- Acceptance/validation: disposable browser reload/retry/feedback/decision checks; node --check.
- Status: complete.

### WP4 — Persist progression
- Dependencies: WP2. Files: new progression service, four adapter initialization/preview paths.
- Work: versioned accepted revision/stage/reference state; new batches default to prompt review; ancestor preview and legacy compatibility.
- Acceptance/validation: disposable paired/front-only/ancestor/reload/idempotence checks.
- Status: complete.

### WP5 — Generation entry points
- Dependencies: WP4. Files: shared workflow, adapters, render slots, overview and Run All Remaining.
- Work: common gate and reference chain for fresh generation; explicit Continue, frozen retries, paused automation.
- Acceptance/validation: prepared dispatch role/order checks, recovery and bypass checks.
- Status: complete.

### WP6 — Refinement service
- Dependencies: WP4. Files: new local character refinement service, shared true-up support, AI workflow registration.
- Work: persisted base/comparisons/reports/attempts, correction-only edits via AI_Proxy, fencing and replay.
- Acceptance/validation: disposable prepared analysis/edit/retry/recovery checks.
- Status: complete.

### WP7 — Adoption and warnings
- Dependencies: WP5/WP6. Files: slot transitions, adapter selections and reference provenance.
- Work: explicit same-slot adoption with retained originals, expected-selection checks, future reference resolution and nonblocking reference warnings.
- Acceptance/validation: disposable full-slot/adoption/concurrency/publication/downstream checks.
- Status: complete.

### WP8 — Dedicated refinement page
- Dependencies: WP6/WP7. Files: new page/script, local router, selected-image controls.
- Work: comparisons, findings, targeted attempts, adoption and return navigation through service interfaces.
- Acceptance/validation: disposable desktop/narrow browser journey, navigation/reload and node --check.
- Status: complete.

### WP9 — Presentation, documentation and final validation
- Dependencies: WP3/WP5/WP8. Files: local_asset_pipeline.js, summaries, affected knowledge and ADR.
- Work: stage/Continue/reference/warning presentation; synchronize docs and record exact validation.
- Acceptance/validation: npm.cmd run test:e2e; Python AST and changed JS syntax checks; git diff --check and final diff review. Repair S2 only to preserve its approved task; no permanent additional scenarios.
- Status: complete.

## Defaults and constraints
Analyze all eight views; generate requested views plus previewed required ancestors. Preserve counts. BACK defaults to selected back-left quarter. Comparisons initially include every other available selection; correction renders receive only their edit base. One refinement attempt per edit. AI work uses shared AI_Proxy and existing profiles; no dependency additions, live inference or production deployment. Existing batches keep legacy behavior until explicitly enrolled. Visual improvement requires operator judgment.

## Progress and final results
Implementation started with clean working tree. WP1-WP9 are complete. All requested changes are local and documentation is synchronized.

Observed validation: all 32 view/pipeline text previews passed. Disposable prepared service checks passed all five stages, exact same-side reference bindings, default seven comparison choices, image-only analysis, one-base edits, frozen replay, idempotent edits, occupied-slot adoption and nonblocking downstream warnings for all four pipelines. Existing S1-S4 passed in 52.1s after S2 was adapted to the prompt-review gate and its front-only seed count. No live inference or production library writes.


## Final results
+- Implemented all four pipeline prompt previews, text correction decisions/acceptance and batch-local overlays; separate master promotion remains.
+- Added explicit staged progression, same-side references, partial-view ancestors, supplemental/automation gates, advisory drift and actionable paused-work links.
+- Added dedicated persisted image refinement, chosen comparisons, targeted one-base edits, replay/retry and explicit same-slot adoption with retained originals and published-image integrity. Namespaced AI ownership links work back to the refinement page.
+- Existing S1-S4: 4 passed in 48.9s. All-pipeline disposable service checks and desktop/800px browser journeys passed. Selective/overlap/stale-source/failure/retry/adoption edge checks passed. Syntax/AST and final diff checks passed.
+- Fixed issues discovered during validation: front-only seed counts, correction-label UTF-8, action/poll races, independent adopted gallery copies, adoption record recovery, late-result/deletion fencing, and real image-service ERROR handling. These stayed within the approved workflow.
+- Early checks failed on the old front-only seed expectation and disposable harness timing/assertion assumptions; corrected checks subsequently passed. A disposable rerun initially encountered its still-open browser fixture directory; its owned server was stopped before rerunning successfully. An earlier baseline logged one transient existing Windows queue-file read error; the final baseline completed without it.
+- No permanent coverage expansion, new dependencies, live AI/render execution, normal-library writes or production deployment. Actual image improvement remains unverified until an operator trial.
