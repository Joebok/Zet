# Body BACK uses selected FRONT
Status: complete

## Goal and current behavior
Staged Body-Reference BACK currently uses a selected rear quarter, which the reviewed Tsaeytte batch copied instead of turning squarely backward. Use selected FRONT for future Body BACK renders, including existing staged batches. Preserve other pipelines, saved render inputs, retries, images and selections. Do not change prompt wording or submit live renders.

## Impact and constraints
Reference recipes own input selection; progression owns stage admission; previews and slots must agree with the effective recipe. Dashboard controls must describe that recipe. Affected knowledge owners are local characters and prompts. No schema change, new dependency, permanent test, production deployment or library mutation is needed.

## Luna sized work packets
### WP1 — Resolve and present Body BACK references
- Files: local_view_reference_service.py, local_character_progression_service.py, local_prompt_preview_service.py, local_prompt_improvement_service.py, render_slot_service.py, local_asset_pipeline.js.
- Dependencies: none.
- Work: normalize staged Body BACK recipes to FRONT; use the same rule in previews, slot freezing, prerequisites and Continue; show the fixed FRONT choice in the dashboard.
- Acceptance: existing rear-quarter recipes resolve to current selected FRONT for new renders; other pipelines and frozen inputs remain unchanged.
- Validation: disposable isolated reference/slot/preview checks, Python AST, JavaScript syntax, existing S2.
- Status: complete.

### WP2 — Document and verify
- Files: Docs/COMPONENTS/LOCAL_CHARACTERS.md, Docs/COMPONENTS/PROMPTS.md, this plan.
- Dependencies: WP1.
- Work: synchronize the Body-only exception and record validation.
- Acceptance: final diff contains only requested changes; validation results and limitations recorded.
- Validation: git diff --check and final diff inspection.
- Status: complete.

## Validation and results
Disposable isolated checks (`python3 -B test-results/check-body-back-front.py`) passed Body BACK preview/render prompt equality, selected FRONT image binding, effective recipe provenance, Continue from a saved rear-quarter choice, missing-FRONT rejection, rear-quarter save rejection, and unchanged historical frozen state. Head/Assembly/Dressing retained rear-left references in preview, render and Continue. No permanent tests or live AI calls were added.

`npm.cmd run test:e2e -- --grep "character-to-costume"` passed the existing S2 scenario (15.9 seconds including startup). Python AST checks, `node --check zet/web/static/local_asset_pipeline.js` and `git diff --check` passed. Final diff inspection excluded pre-existing DEVELOPMENT/INDEX and HTTPS work. S2 protects front Assembly/Dressing behavior; the disposable checks establish BACK bindings, not generated image quality.

The effective recipe is applied at read/preparation time to existing staged Body batches. Their saved state and historical requests are not migrated. New Continue writes FRONT normally. Prompt previews, render snapshots and dashboard controls consume the effective recipe. Other generation stages and prompt wording are unchanged. Knowledge updates are limited to the two affected component documents; no responsibilities or significant entry points moved. No production deployment or new artwork was performed.
