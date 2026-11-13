# Ollama Head Image Edit template review
Status: complete
Related issue/specification: Head Image Edit template review investigation

## Goal
Use compact structured line selections for directed, text-only Ollama Head Image Edit template reviews. Keep existing finding, selection, preview, and revision-check behavior.

## Current behavior
`CharacterContainerTemplateService._review_job` sends all eight compiled prompts, the full source, and Qwen role guidance, then accepts only exact `before` excerpts and canonical source IDs. Investigation showed truncation for Zet-Image-1 and rejected repeated excerpts / generated source IDs. A short line-ID request succeeded for both tested models. Saved screening examples are under `C:/Users/Joe/Projects/Zet_Tester/runs/head-edit-template-eval-20261113`.

## Desired behavior
For fresh text-only Head Image Edit reviews with a direction and an Ollama model, submit at most one editable `HEAD_EDIT_*` bullet line ID and replacement with a 384 token cap. Resolve IDs against frozen source in Zet. Compile proposed text to derive affected views, then use the current finding and selected preview flow. Persist a format version so pending proposals retain their request contract.

## Impact analysis
- `zet/services/character_container_template_service.py`: request selection, line mapping, result reconstruction, affected view derivation.
- `zet/services/llm_role_service.py`: skill-free text role.
- `Docs/COMPONENTS/LOCAL_CHARACTERS.md`, `Docs/COMPONENTS/LLM_ROLES.md`, `Docs/PIPELINE_LLM_REQUIREMENTS.md`, and `Docs/CODE_MAP.md`: workflow, role, inventory, ownership notes.
- Public API and stored proposal schema remain compatible through an optional version field.

## Invariants and constraints
Only selected `Character.md` text inside `HEAD_EDIT_*` sections is offered. Lines that occur more than once anywhere in the frozen source, unknown IDs, empty and unchanged replacements are rejected. Marker and placeholder validation, source revision checks, universe isolation, and ordered preview compilation remain active. Existing proposals without the new format version resume through their saved prompt contract. Do not add permanent test scenarios without approval.

## Implementation steps
### WP1 — Build a bounded provider request
- Dependencies: none.
- Files/interfaces: template review service and LLM role registry.
- Work: select line mode for directed text reviews with Ollama; freeze version; send unique bullet candidates and compact schema; cap output at 384 tokens.
- Acceptance: Codex, candidate reviews, no-direction reviews, and other pipelines retain existing path.
- Validation: Python compilation and role guidance inspection.
- Status: complete.

### WP2 — Reconstruct and validate Zet findings
- Dependencies: WP1.
- Files/interfaces: template review service.
- Work: map returned line ID to frozen unique line; validate replacement; compile source overlay; derive views from changed compiled prompts; feed existing finding validator.
- Acceptance: accepted findings select and compile with the existing flow; no-op compiler changes are rejected.
- Validation: replay saved model responses through finding selection and eight preview compilers.
- Status: complete.

### WP3 — Verify integration and document
- Dependencies: WP2.
- Files/interfaces: approved E2E suite and owning documentation.
- Work: run fast E2E, inspect diff, record replay evidence and remaining unverified real queue cases.
- Acceptance: suite passes and docs distinguish replay verification from five-call model repeatability through the API.
- Validation: `npm run test:e2e`, `git diff --check`.
- Status: complete.

## Validation
Disposable replay of three saved line-ID responses per model passed Zet finding validation, selection, and all eight previews. All six reported `FRONT` as affected. The isolated Asset Container API and private AI_Proxy queue completed five fresh reviews per model. All ten yielded one selectable finding, all eight previews, and FRONT-only impact. The preliminary exact-text substring score was invalid because those responses used `L01` as a source ID. Saved-response replay also passed 3/3 per model through selection and eight previews. A disposable review-criteria edit was accepted by the converter and affected all eight views. A uniquely anchored `[f]` view-tagged line was accepted and affected only `FRONT`; duplicate anchors elsewhere in the frozen source are excluded. The production library `Character.md` hash remained unchanged.

## Final results
The bounded line-ID path is ready for deployment to the test dashboard. Five fresh API calls per model passed the acceptance checks for this fixture: one selectable finding and eight compiled previews, with FRONT-only impact. The targeted review-criteria and view-tagged conversion checks also passed. These results measure acceptance and preview behavior, not whether the edit satisfies the full direction. The latest `npm run test:e2e` run passed four of four approved scenarios. Python compilation and `git diff --check` passed. The production library `Character.md` hash remained `58FAE6A34B9170010637FB6F1D7548AF94CAE3771EE85A5E427693451323276A`.


