# Independent Head-Image Edit pipeline
Status: complete
Specification: [Qwen trial recipes](../../Docs-Joe/Qwen-Head-Image-Prompts.md), approved chat plan 2026-10-22.

## Goal and contracts
Add `head-image-edit` / Head-Image Edit alongside legacy Head-Image. Independent Head-Image-Edit runs, owner identity, selections and publications. FRONT independently anchors all seven other views; optional BACK-guided rear-quarter hair finishing is a separate attempt with explicit adoption. Assembly freezes an explicit head pipeline (legacy by default). No migration, automatic selection, live inference, deployment, dependencies or maintained tests.

New optional character sections: HEAD_EDIT_FRONT_DESCRIPTION, HEAD_EDIT_PRESERVE, HEAD_EDIT_VIEW_OVERRIDES, HEAD_EDIT_REFERENCE_GUIDANCE, HEAD_EDIT_EXPRESSION_GUIDANCE, HEAD_EDIT_PHASE_CHANGES, HEAD_EDIT_REVIEW_CRITERIA. Populate a separate Adult Tsaeytte block, preserving prior text. Shared marker/view conditioning, source maps, schema-2 image roles and ordered frozen bytes remain authoritative. Same-batch/universe guards and published-lock protections remain required.

## Current behavior / impact
LocalHeadImageService hardcodes legacy identity across storage, compilation, queue and publication; common consumers enumerate four pipelines. Progression/preview/reference guards chain predecessor views. Refinement renders attach only the canvas. Assembly resolves Head-Image by role. Onboarding requires all shared sections, so the new family must be optional for legacy validation. Affect Local Characters, Prompts, Data Model, Code Map and architecture ownership documentation; write an ADR for durable parallel-source policy.

## Work packets
All packets executed sequentially by one agent. Validation uses disposable isolated Python/API/browser checks; no real inference.

### WP1 — Independent identities
- Dependencies: none. Files: local_head_image_service, local_image_pipeline_policy, new local_head_image_edit_service.
- Work: bounded identity hooks; focused adapter without duplicating lifecycle.
- Acceptance: separate runs/assets/owners, unchanged legacy defaults.
- Validation: temporary-library identity and foreign-run rejection checks.
- Status: complete.
### WP2 — Compatible authoring
- Dependencies: WP1. Files: shared character template/instructions, section metadata, onboarding.
- Work: optional family; scoped new-pipeline readiness and template revisions.
- Acceptance: old characters remain valid, new pipeline explains missing authoring.
- Validation: disposable template checks.
- Status: complete.
### WP3 — Compiler
- Dependencies: WP2. Files: new Run_Head_Image_Edit_Jobs, prompt templates, task bundles.
- Work: edit-first generation/analysis, scopes, source maps, ordered inputs.
- Acceptance: eight views, no legacy frontal/eye/hair-length conflicts.
- Validation: offline all-view generation/analysis and reference failures.
- Status: complete.
### WP4 — Source policy
- Dependencies: WP1/WP3. Files: progression, view references, preview, template revision.
- Work: FRONT/remaining stages, versioned policy, partial-view closure.
- Acceptance: direct same-batch FRONT source for every base edit; no BACK cycle.
- Validation: readiness/source/preview checks.
- Status: complete.
### WP5 — Reproducibility
- Dependencies: WP3/WP4. Files: render slots, adapter, staging, presets.
- Work: complete manifests through fresh/cached/staged/retry paths; dedicated 1024-square trial-compatible presets.
- Acceptance: ordered image bytes/citations and effective settings agree.
- Validation: prepared requests/retry checks, no inference.
- Status: complete.
### WP6 — Finishing
- Dependencies: WP5. Files: refinement service/UI.
- Work: optional scoped render guide and BACK-guided hair operation; explicit adoption.
- Acceptance: canvas then guide actually attached; original history retained; stale adoption rejected.
- Validation: disposable correction/guide/retry/adoption checks.
- Status: complete.
### WP7 — Dashboard and recovery
- Dependencies: WP4-WP6. Files: workflow/router/navigation, overview, run remaining, recovery.
- Work: fifth pipeline registration and independent controls.
- Acceptance: isolated review/selection/resume/recovery, board unchanged except explicit staging.
- Validation: isolated API/browser checks.
- Status: complete.
### WP8 — Assembly
- Dependencies: WP1/WP5/WP7. Files: assembly/source resolution/publication/UI.
- Work: frozen head_pipeline, filtered options, actual dependency keys.
- Acceptance: either family consumed, no cross-pipeline fallback, legacy default.
- Validation: disposable both-family preparation/publication and approved S2.
- Status: complete.
### WP9 — Pilot authoring, verification, documentation
- Dependencies: WP2-WP8. Files: Adult Tsaeytte appended block; affected knowledge and this plan.
- Work: isolated template first, append preserving original; legacy output comparison; record outcomes.
- Acceptance: both versions coexist, original sections unchanged.
- Validation: disposable offline/browser checks; npm.cmd run test:e2e; syntax; git diff --check; final diff review.
- Status: complete.

## Risks and defaults
Live image quality remains unverified until Joe authorizes a render budget. Accepted ad hoc images are evidence, not automatically adopted. Tsaeytte's new block uses chin/upper-neck bob, right-eye occlusion and elf-ears-back only for rear-right/BACK. Left rear follows initial edit then optional text correction. New template sections must not break old characters or leak into legacy compilers. Locked downstream chains must retain true pipeline identity.

## Progress and results
- Planning inspection complete; working tree clean at implementation start. All nine packets completed sequentially by one agent.
- Dedicated operation wording lives in an additional source-mapped `head_image_edit_operations.md`; governing reviews freeze and edit both task templates, and only HEAD_EDIT character content.
- Reused the existing optional render_config boundary with validated frozen sampler/encoder overrides for staged/refinement replay. Added actual ordered render_references separately from refinement source ancestry; later text-only corrections retain effects without stale Image 2 instructions.
- Legacy automatic overview progression retains its original four-stage chain. New head batches participate independently in navigation, batch status, Run All Remaining and recovery; no unconfigured character is automatically enrolled.
- No existing runs/selections/locks were migrated. Concurrent Config-process changes appeared in app.py/zet.js during implementation; preserved them and excluded them from this feature's claims. DECISIONS/README.md already contained mixed encoding; inserted its new link without changing prior bytes.

## Observed validation
- `npm.cmd run test:e2e`: all four approved scenarios passed. Final run 39.3s (earlier successful runs 40.4s and 38.8s). Existing Node NO_COLOR/FORCE_COLOR warning only. No new maintained scenario or dependency.
- `python3 -B test-results/head-edit/pilot.py`: 16 new generation/analysis compiles across all eight views; correct reference counts/order; all eight legacy generation prompts byte-identical before/after isolated authoring. Missing/unprepared authoring remains blocked for the new pipeline, while legacy readiness remains valid.
- `python3 -B test-results/head-edit/services.py`: disposable isolated app checks passed for separate run namespaces and foreign-run rejection, governing prompt acceptance and operation source maps, FRONT/remaining and partial-view policy, ordered all-view slots, both lock families, locked and selected-batch Assembly source choices, saved-family refresh, guided hair correction/adoption and BACK dependency, follow-up text-only edits without ghost guide citations, stale-guide refusal, and template ownership.
- Same disposable service check passed all-view explicit staging parity (1024 square, prompt globals/label appending off), and actual isolated AI_Proxy provider preparation for text FRONT and two-image BACK with correct owner/checkpoint/settings. No worker or inference process was started.
- `node test-results/head-edit/browser.cjs`: actual isolated Chromium navigation, partial-view API, foreign-run refusal, both Assembly source selectors, hair finishing click/reload, 1280px/390px containment and zero browser errors passed. Screenshots inspected under ignored test-results/head-edit. The disposable server stubs inference continuations and was stopped afterward.
- Changed Python AST, JSON parsing, four JavaScript `node --check` commands, and `git diff --check` passed. Git emitted CRLF conversion notices for two existing files, not diff errors.
- An early disposable browser check raced collapsed New batch settings; waiting for the loaded batch and opening that section fixed the check. A disposable fixture recreation initially hit a lingering owned server's working-directory handle; the owned server was stopped before the successful rerun. These were test-harness failures, not ignored passes.

## Final results
- Implemented independent Head-Image Edit with FRONT-anchored views, optional scoped/selected-BACK finishing and explicit adoption, separate authoring/presets/storage/publication, shared lifecycle/UI/recovery, and a frozen per-Assembly head-family choice.
- Updated shared template/instructions and metadata. Appended the tested block only to E:/Zet/Zet_Library_v5/Moonsea/Characters/Tsaeytte/Adult/Character.md, preserving the entire original byte prefix and all 26 legacy sections. Receipt and original-byte backup remain in ignored test-results/head-edit. Youth and Elder were not edited.
- Updated architecture ownership, component documents, data model, code map and ADR 0028.
- No live model calls, production deployment/restart, external publication, trial-image adoption, ordinary generator-board changes, production dependencies or permanent tests. New compiled image quality and non-Tsaeytte generalization still require a separately authorized live render budget.
