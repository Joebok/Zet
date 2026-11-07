# Restore Character Board Render Options
Status: completed
Related issue/specification: User request, 2026-11-07

## Goal
Restore per-view Costume Dressing modes and independent Head FRONT reference/phase-change controls in Character Asset Container boards.

## Current behavior
The legacy local costume workflow persists Doll-dressing with reference, Doll-dressing without reference, and Rotate settings. The current asset container compiler prepares only the matching Character Assembly image for Costume Dressing. Head container sources already support managed uploads and locked FRONT images from another phase. Head Image Construct supports source-preserving and phase-change prompt behavior. Head Image Edit FRONT currently selects a prompt-only profile.

## Desired behavior
Non-FRONT Dressing boards save their mode and reference view. FRONT stays Assembly-based. Head FRONT references are independent from the optional phase-change toggle. Prepared candidates retain ordered frozen inputs and mode provenance.

## Implementation steps
### WP1 — Service settings and frozen inputs
- Dependencies: none.
- Files/interfaces: `zet/services/character_asset_container_service.py`, `zet/services/character_container_prompt_service.py`, `zet/web/character_asset_container_router.py`.
- Work: Persist and validate view-scoped dressing settings; resolve ordered Assembly/dressed-view inputs; use the saved settings in preview, generation and regeneration; preserve captured settings and resources through candidate template previews; choose Head Edit FRONT profile from the presence of references.
- Acceptance: Each mode compiles with the required ordered inputs; missing references block preparation; Head source and toggle semantics are consistent; retries retain captured references.
- Validation: Disposable API/compiler checks and approved E2E suite.
- Status: complete. Python syntax parsing, JavaScript syntax validation and the approved E2E suite passed. The suite exercised default Dressing behavior. Alternate-mode bindings and Head toggle combinations were not exercised end to end.

### WP2 — Candidate Board controls
- Dependencies: WP1.
- Files/interfaces: `zet/web/templates/index.html`, `zet/web/static/character_asset_container.js`.
- Work: Add saveable mode/reference controls to non-FRONT Dressing boards; expose the existing Head source choice in settings and on FRONT; keep one phase-source status element; send saved settings and toggle to preview and generation.
- Acceptance: Settings persist by costume/view across reloads; stale saves are reported; UI labels and readiness reflect saved sources and pending edits.
- Validation: Disposable browser checks for all modes and Head source/toggle combinations.
- Status: complete. Existing character-to-costume browser journey passed. Alternate-mode browser interactions were not separately exercised.

### WP3 — Documentation and closeout
- Dependencies: WP1, WP2.
- Files/interfaces: `Docs/COMPONENTS/LOCAL_CHARACTERS.md`, `Docs/DATA_MODEL.md`, `Docs/CODE_MAP.md`, `Docs/Testing.md`.
- Work: Document the board settings, compatibility defaults, and observed validation.
- Acceptance: Documentation describes implemented behavior and validation accurately.
- Validation: `npm.cmd run test:e2e`, `git diff --check`.
- Status: complete.

## Validation results
- `npm.cmd run test:e2e`: passed, 4/4 scenarios (42.8s).
- Python AST parsing, `node --check zet/web/static/character_asset_container.js`, and `git diff --check`: passed.
- Alternate Costume modes and Head source/toggle combinations have not received a dedicated isolated browser/API check or live render. No live model inference or permanent test was added.

## Compatibility and constraints
Existing Costume Dressing containers default to Doll-dressing without reference. No migration is needed. Head source selection remains shared across qualities. Use isolated fixtures and the approved fast E2E scenarios. Do not add permanent tests or run live model inference.
