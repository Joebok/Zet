# Head container reference and phase-change controls
Status: complete
Related issue/specification: User request, 2026-11-07

## Goal
Move Head Construct/Edit FRONT source and phase-change controls into Container settings beside governing Character.md editing. Make the three FRONT prompt modes explicit and enforce that phase change requires a reference. Require a selected same-container FRONT reference for non-FRONT head renders, defaulting to FRONT while allowing another selected view.

## Current behavior
`character_asset_container.js` puts Apply phase change on the FRONT candidate board and source controls in Container settings. The settings have a file chooser and upload action, but no paste target. Saved phase/pipeline or upload references are consumed automatically for FRONT; the phase-change checkbox only changes compiler wording. Non-FRONT Head Construct allows no reference and has no default selected source, while Head Edit defaults to FRONT. `CharacterAssetContainerService.resolve_references` owns available reference resolution and `_preset` selects text vs edit profiles from actual inputs. The container router passes checkbox state into prompt preview/preparation.

## Desired behavior
- FRONT source controls sit below Edit governing Character.md: upload input, paste target and Upload; Phase Change checkbox; enabled source phase/pipeline when selected; left-aligned Save source and Clear source.
- Source save remains shared across Draft and Final and upload remains a managed, verified input.
- FRONT mode is determined by reference presence and Phase Change: no reference/no phase change, reference/no phase change, reference/phase change. Reject phase change without a reference at the API boundary.
- Show the effective FRONT render mode above FRONT render buttons. Remove Apply phase change from the candidate board.
- Non-FRONT Head Construct and Edit require a selected available reference, default FRONT, and permit another selected view as the guide.

## Impact analysis
- UI: `zet/web/templates/index.html`, `zet/web/static/character_asset_container.js`, `zet/web/static/zet.css`.
- Business rules: `zet/services/character_asset_container_service.py` and prompt/route boundary if necessary.
- Documentation owners: `Docs/COMPONENTS/LOCAL_CHARACTERS.md`, `Docs/INVARIANTS.md`, `Docs/CODE_MAP.md`; update this plan. No storage migration expected.
- Validation: existing approved e2e baseline, syntax checks and diff check; no permanent tests or live rendering.

## Invariants and constraints
Preserve universe ownership, upload validation and managed paths, locked published source checks, frozen render inputs, and revision checks. A currently saved source is a reference independently of Phase Change. Phase Change only changes FRONT prompt intent and must never compile with zero references. Do not change other pipeline source semantics.

## Implementation steps
### WP1 — Move controls and add usable upload/paste interaction
- Dependencies: none.
- Files/interfaces: `index.html`, `character_asset_container.js`, `zet.css`.
- Work: Arrange upload, checkbox, conditional phase/pipeline, and left-aligned save/clear controls under governing Character.md. Attach the shared image input helper and accept pasted images. Render mode caption above FRONT render actions; remove board checkbox.
- Acceptance: Both head pipelines show controls in settings; paste or file selection can upload; checkbox enables source selectors; save is green and clear uses red outline; mode caption follows state.
- Validation: `node --check` plus targeted source/DOM inspection.
- Status: complete.

### WP2 — Enforce prompt mode and non-FRONT reference requirements
- Dependencies: WP1.
- Files/interfaces: `character_asset_container_service.py`, `character_asset_container.js`.
- Work: Reject phase-change preparation/preview without resolved references. Default all non-FRONT head source views to selected FRONT; remove no-reference option and require selected/available references. Preserve alternate view choice.
- Acceptance: API rejects phase-change/no-reference; FRONT source controls describe all three valid modes; non-FRONT head prompt compilation fails clearly until chosen reference is selected.
- Validation: focused disposable API/service checks and syntax checks.
- Status: complete.

### WP3 — Update owned docs and verify
- Dependencies: WP1, WP2.
- Files/interfaces: `LOCAL_CHARACTERS.md`, `INVARIANTS.md`, `CODE_MAP.md`, this plan.
- Work: Document control ownership, valid modes and non-FRONT reference default; run approved validation and record actual outcome.
- Acceptance: docs agree with source; final diff is scoped.
- Validation: `npm run test:e2e`, `python3 -m compileall` on changed Python module(s), `node --check`, `git diff --check`.
- Status: complete.

## Validation
Validation completed: `npm run test:e2e` passed all four approved scenarios (41.3s); a disposable Playwright browser/API check passed both Head pipelines, source-control visibility/state across view navigation, and both API rejection boundaries; `node --check zet/web/static/character_asset_container.js`, `python3 -m compileall -q zet/services/character_asset_container_service.py`, and `git diff --check` passed. The disposable check files were removed. No permanent tests or live rendering/library writes.

## Risks and alternatives
Existing saved sources are references whether or not Phase Change is checked; this preserves current source storage while making the checkbox govern prompt intent. Legacy Head Construct view settings that explicitly saved no reference will now resolve to FRONT for future requests.

## Progress and decisions
Plan created after inspecting current UI, service and prompt compilation. Existing shared-source active plan remains the owner of source migration and cross-quality storage behavior; this plan only covers its dashboard interaction and render-mode semantics.

## Final results
Implemented settings controls, paste/file upload, three FRONT prompt modes, reference guards, and required non-FRONT head references. Documentation updated. Validation recorded above. No remaining blockers.
