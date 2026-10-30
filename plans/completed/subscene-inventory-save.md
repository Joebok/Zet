# Save subscene images to inventory
Status: complete
Related specification: Joe's request in this chat (2026-10-30).

## Goal and desired behavior
Save a selected or locked Narrative subscene image as an independent Inventory item from image review. Default its editable name to the saved subscene title; retain the candidate's rendered prompt and story/scene/subscene titles in notes. Repeated saves, identical bytes and duplicate names are allowed. Never mutate the subscene or create enforced source relationships.

## Current behavior and impact
`NarrativeSceneService` owns authored records; `NarrativeGenerationService` owns candidate review. `narrative.js` renders image review through `narrative.html` and `narrative_router.py`. `EntityLibraryService.import_asset`, exposed through `ZetApp.entity_library_import`, already creates independent assets when `origin_key` is omitted. Asset labels are not unique; Image Generator's separate checksum deduplication remains unchanged. No schema changes or dependencies are required.

Affected knowledge owners: Docs/COMPONENTS/NARRATIVE.md (workflow), Docs/COMPONENTS/LIBRARY.md (imports), Docs/CODE_MAP.md (entry point). Architecture, DATA_MODEL and INVARIANTS were inspected; existing boundaries and formats suffice. Narrative locking and universe binding must be preserved. No usage scan, duplicate query or source backlink is needed.

## Implementation steps
### WP1 — Backend copy operation
- Dependencies: none.
- Files/interfaces: `NarrativeSceneService.save_subscene_image_to_inventory`; Narrative candidate `/inventory` POST route.
- Work: validate subscene/candidate eligibility under the Narrative lock; snapshot image bytes, prompt and source notes; call the existing indexed import facade without a deduplication key.
- Acceptance: selected-only and locked-only saves succeed; unprotected/missing images are refused; repeated saves create separate IDs and source files remain unchanged.
- Validation: disposable isolated service/API checks; Python syntax.
- Status: complete.

### WP2 — Review action and name dialog
- Dependencies: WP1.
- Files: `zet/web/static/narrative.js`, `zet/web/templates/narrative.html`.
- Work: show Save to inventory for subscenes, enabled only for selected/locked images; open a small naming dialog with prompt display and duplicate-name guidance; retain context and show local progress/errors/success.
- Acceptance: default name, edited name, cancellation, repeated save and ineligible button behavior work without changing selection, locks or prompt.
- Validation: disposable Chromium check against private fixture; JavaScript syntax.
- Status: complete.

### WP3 — Regression checks and documentation
- Dependencies: WP1–WP2.
- Files: affected component docs, code map and this plan.
- Work: run existing approved fast E2E suite, review final diff, record observed results, archive completed plan.
- Acceptance: no permanent tests, new scenarios, dependencies or normal-library writes; isolated validation passes.
- Validation: `npm.cmd run test:e2e`; `git diff --check`.
- Status: complete.

## Risks and alternatives
Use the candidate's frozen prompt rather than today's editable target prompt. Copy bytes while holding the existing workflow lock, then release it before catalog work. The optional duplicate-name warning is omitted to avoid adding lookups; the dialog explains that duplicate names are allowed. The existing Inventory editor can organize the new item later.

## Progress and decisions
- Implemented the bounded copy operation on the existing Narrative authoring service and indexed Inventory import facade. Existing asset constraints and generation import behavior are unchanged.
- The review dialog retains its candidate and endpoint while polling preserves the editable name. Save progress, retryable errors and completion appear locally.
- Updated Narrative and Library component docs and the code map. CODE_MAP.md contained an existing non-UTF-8 byte; its new ASCII section was appended as bytes to preserve the original contents without encoding cleanup.
- No schema, invariant, architecture or durable design change required an ADR. No permanent tests or dependencies were added.

## Validation and final results
- `npm.cmd run test:e2e`: all four approved fast scenarios passed (40.1s).
- `node node_modules/playwright/cli.js test --config test-results/subscene-inventory/playwright.config.mjs` with an isolated `ZET_TEST_RESULTS_ROOT`: final disposable browser/API check passed (9.2s). It covered selected-only and locked-only eligibility, refusal of unprotected/missing/non-subscene inputs and blank names, default/edited/duplicate names, repeated identical-byte imports with separate IDs, frozen prompt and source notes, cancel, name preservation during polling, local error/retry, unchanged story/scene/target/image bytes, and copied image survival after source deletion. No page errors occurred.
- The added error-injection check initially failed because its disposable interception expected a query parameter while the UI uses the universe header. Corrected the interception; the final check passed without product changes. The initial core-contract check had also passed (9.3s).
- Python AST parsing, `node --check zet/web/static/narrative.js`, final diff review and `git diff --check` passed. Inspected the captured naming/error dialog screenshot.
- Approved S1/S3 remain library/Narrative regressions; new save contracts use disposable checks only. No live AI calls or normal-library writes were performed. Physical touch and narrow-device presentation were not separately exercised.
