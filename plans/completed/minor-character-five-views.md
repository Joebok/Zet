# Five views for Minor Characters
Status: complete
Related specification: Joe's approved five-view implementation plan (2026-10-27).

## Goal and current behavior
Expose Front, Front left 3/4, Front right 3/4, Left profile and Right profile after Style alignment in new and existing current-workflow workspaces. Currently `MinorCharacterWorkflow._views` limits boards to the saved side. Alignment prompts and per-view publication already support both sides; `MinorCharacterService._read` supplies missing boards without replacing saved ones.

## Impact and constraints
The public views list and boards map expand using existing identifiers. Preserve session/workflow versions, legacy side fields, saved boards, selections, revisions, locks, anatomical-side prompts and immutable Inventory assets. No bulk migration, dependencies, permanent tests, live AI calls or normal-library writes. Keep retired workflows unchanged. Knowledge owners: Local Characters, Data Model and Code Map.

## Luna-sized work packets
### WP1 — Expose five boards
- Dependencies: none.
- Files/interfaces: `zet/services/minor_character_workflow_service.py`; verify `minor_character_service.py` read compatibility.
- Work: return STYLE, FRONT, FRONT_LEFT_3_4, FRONT_RIGHT_3_4, LEFT_PROFILE, RIGHT_PROFILE independently of side.
- Acceptance: new and existing left/right workspaces expose all boards without resetting existing state.
- Validation: disposable isolated Python service checks, including persistence and anatomical-side prompts.
- Status: complete.

### WP2 — Dashboard labels and controls
- Dependencies: WP1.
- Files/interfaces: `zet/web/static/minor_characters.js`, `zet/web/templates/index.html`.
- Work: remove side selector/binding; share explicit view labels for tabs, captions, comparisons, locks and restart controls.
- Acceptance: five individually usable views after Style, correct right-three-quarter labels, desktop/narrow containment.
- Validation: `node --check zet/web/static/minor_characters.js`; disposable prepared-response Chromium checks.
- Status: complete.

### WP3 — Compatibility, regression and knowledge
- Dependencies: WP1–WP2.
- Files/interfaces: publication contract (inspect/check), affected Docs and this plan.
- Work: verify isolated per-view publication/replacement preserves opposite-side associations and bytes; update knowledge; review final diff; archive plan after completion.
- Acceptance: focused checks and approved baseline pass with no unrelated changes.
- Validation: disposable isolated service/browser checks; `npm.cmd run test:e2e`; `git diff --check`.
- Status: complete.

## Progress and results
Implemented the ordered six-stage list (Style plus five official views), removed the side selector/binding, and shared explicit labels across stage controls and image captions. Existing read-time initialization and per-view publication needed no changes. Existing responsive tab wrapping passed without CSS changes. Updated the three affected knowledge owners.

Validation observed on 2026-10-27:
- `npm.cmd run test:e2e`: all four existing fast scenarios passed (42.5s).
- `python3 -B test-results/five-views/check.py`: disposable private-fixture checks passed new and existing left/right workspaces, preservation of boards/revisions/undo/selections/locks/candidates, save/reload, anatomical-side prompts, five independent publications, and right-three-quarter replacement preserving other roles/locks and all previously published bytes. Changed workflow and owning service AST checks passed. The script then served only the private fixture on port 8767 for browser checks.
- `node test-results/five-views/browser.mjs`: actual dashboard/private API plus prepared generation responses passed all six tab labels, absence of the side selector, generation requests for each of five views, lock/restart labels, saved active view after reload, desktop (1440px) and narrow (390px) tab containment, and no uncaught page errors. Screenshots inspected at both sizes.
- `node --check zet/web/static/minor_characters.js`: passed.
- `git diff --check`: passed; final diff reviewed for scope.

No permanent tests, dependencies, live AI/render calls, production deployment or normal-library writes. Live artistic quality is unverified. Disposable scripts/images remain ignored under `test-results/five-views/`; the private fixture server was stopped after validation.
