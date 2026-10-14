# Show references blocking costume deletion
Status: complete
Related issue/specification: https://github.com/Joebok/Zet/issues/58

## Goal
When deleting a costume is blocked by Narrative references, show every blocking Story and Scene and link to each scene where the app supports navigation. Preserve deletion protection and library integrity.

## Current behavior
`LibraryDeletionService.delete_costume` identifies related entity-library assets, then `_protect_narrative_assets` queries current Narrative usage rows with `LIMIT 1` and raises a generic string. `/api/costumes/{slug}` maps that exception to HTTP 400; `deleteSelectedCostume` displays only the error text. Current usage rows identify `NarrativeStories/<story-id>/<scene-id>/scene.json` or a nested target JSON, and store exact reference locations in `locator`.

## Desired behavior
A blocked costume deletion returns all current Narrative consumers with readable Story/Scene titles, reference context, and links opening the relevant Narrative scene. If no usage records match, deletion follows the existing archive flow unchanged.

## Impact analysis
- `zet/services/library_deletion_service.py`: resolve and report matching usage rows from the authoritative entity catalog plus Narrative JSON.
- `zet/web/app.py`: return structured conflict details for blocked costume deletion while preserving other error handling.
- `zet/web/static/zet.js`: render a safe, accessible linked list in the costume status area.
- `Docs/COMPONENTS/LIBRARY.md` and `Docs/CODE_MAP.md`: document deletion protection behavior and entry points.
- Existing S1–S3 baseline is the only approved maintained E2E suite; none specifically asserts costume deletion references. No new tests/scenarios without approval.

## Invariants and constraints
Use current authoritative `asset_usages` and logical-reference joins; do not bypass protection, touch production library data, or infer missing references. Read names from the current fixture/library records. Preserve universe isolation and deletion archive behavior. Use only the worktree fixture and prepared responses. No new dependencies, permanent tests, live models, merge, or deployment.

## Implementation steps
### WP1 — Resolve complete Narrative blockers
- Dependencies: none.
- Files/interfaces: `zet/services/library_deletion_service.py`.
- Work: query all matching current Narrative usages for the costume's entity assets; resolve story/scene/target names and reference locators from their Narrative JSON paths; return structured blocking data in the service error.
- Acceptance: multiple usages produce complete, stable references without changing successful deletion behavior.
- Validation: source inspection against usage-index path/locator generation; helper's approved revision-bound baseline later.
- Status: complete.

### WP2 — Present actionable references
- Dependencies: WP1.
- Files/interfaces: `zet/web/app.py`, `zet/web/static/zet.js`, `Docs/COMPONENTS/LIBRARY.md`, `Docs/CODE_MAP.md`.
- Work: expose structured conflict details and show every Story/Scene with a link into the Narrative scene editor; escape user content and retain readable fallback for non-structured errors; update owning docs.
- Acceptance: a blocked deletion displays all references with usable scene links; unrelated errors retain current display.
- Validation: inspect before/after code paths and run the approved `npm run test:e2e` plus `git diff --check` through helper validation.
- Status: complete.

## Validation
- Focused disposable check passed: two current Narrative usages resolved to titled Story/Scene references. The prepared inspection catalog had no entity assets, so the check used a temporary in-memory usage repository and temporary fixture scene records; no maintained test was added.
- Helper revision-bound validation passed at `6cc9e9d0320283a6dbb0b5c88b6565a8abfb3e0b`: `npm run test:e2e; git diff --check` (3 approved scenarios passed). Log: `C:/Users/Joe/.codex/worktrees/zet-pickup-20261014-1418/Zet/test-results/issue-worker-validation.log`.

## Risks and alternatives
The current usage index stores file path and JSON locator, not cached display titles. Resolve titles from authored Narrative files at error time; if a record is missing or malformed, report the ID/path and locator rather than omitting a protection reference. Scene links use the existing `page=narrative&story_slug=...&scene_slug=...` route.

## Progress and decisions
- Issue #58 is the original acceptance authority; it reports costume `Relaxed` for `Valindia / Adult` and requests all references, with a link if possible.
- Verified `refresh_usages` emits Narrative consumer paths and nested JSON locators. No comments or screenshot evidence were attached.
- WP1 now collects every matching current usage and resolves authored Story/Scene/target titles from files contained under `NarrativeStories/`; unresolved records retain ID/path and locator details.
- WP2 now returns a structured HTTP 409 conflict and renders a safe linked list in the costume editor. Updated the Library component and code map.

## Final results
Implementation, validation and final review are complete. The approved S1–S3 suite does not assert this exact deletion error contract; the focused disposable check verifies complete service-level reference collection.
