# Minor Character restart and prompt display
Status: active
Related issue/specification: none

## Goal
Add a restart action for the active Minor Character stage. Restarting a view returns to the selected style image and creates a fresh alignment. Restarting Style clears downstream working boards and stale analysis inputs, then re-analyzes the existing references. Show the final prompt for the current board round below “Try these changes.”

## Current behavior
`MinorCharacterWorkflow.board_action` handles Continue and Undo. Boards expose the template candidate's prompt, but the dashboard does not display it. `MinorCharacterService._analyze` starts asynchronous analysis; `_new_candidate` creates the first image for a view from the selected STYLE image. Board membership fences late results. Published Inventory locks are stored separately from working selections.

## Desired behavior
- A dynamic `Restart <stage>` button appears immediately before Undo.
- Restarting a view clears that view's working round and selection, returns its board to alignment, and starts a new image from the selected style image.
- Restarting Style clears changes, notes, analysis results, selections, and every stage's working board, then starts fresh analysis over the retained original references.
- If a view board has been started, Style restart requires confirmation that all view working images and revisions will be discarded.
- Published Inventory locks and immutable source files remain intact.
- The current board template prompt is visible below “Try these changes.”

## Impact analysis
- `zet/services/minor_character_workflow_service.py`: reset/restart transitions and board revision handling.
- `zet/web/minor_character_router.py`: existing board action endpoint carries restart operations.
- `zet/web/static/minor_characters.js`, `zet/web/templates/index.html`, `zet/web/static/zet.css`: dynamic action, confirmation, prompt display.
- Update Local Characters, Data Model, Invariants and Code Map documentation.
- No serialized schema version change or new endpoint is required.

## Invariants and constraints
Keep universe isolation, monotonic board revisions, working-slot access fencing, late-result fencing, and immutable Inventory locks. Do not expose discarded candidates as current images. No permanent tests or scenario expansion without approval.

## Implementation steps
### WP1 — Restart workflow transitions
- Dependencies: none.
- Files/interfaces: `minor_character_workflow_service.py`; existing `POST /api/minor-characters/{sid}/boards/{view}/{action}`.
- Work: implement view restart from selected STYLE and Style reset plus re-analysis; reject pending render work and require a server-checked confirmation when view work exists.
- Acceptance: view restart creates a fresh alignment candidate and clears only that view; Style restart clears working board membership and analysis inputs while retaining references and locks.
- Validation: Python 3 AST parse and inspect revision/late-result paths.
- Status: complete.

### WP2 — Dashboard controls and prompt
- Dependencies: WP1.
- Files/interfaces: `index.html`, `minor_characters.js`, `zet.css`.
- Work: dynamic restart label/action, conditional confirmation, state reset in the editor, current template prompt display below the refinement button.
- Acceptance: button says “Restart Style alignment” or the active view label; prompt follows the current template candidate.
- Validation: JavaScript syntax check and inspect generated DOM bindings.
- Status: complete.

### WP3 — Knowledge updates and final review
- Dependencies: WP1, WP2.
- Files: `Docs/COMPONENTS/LOCAL_CHARACTERS.md`, `Docs/DATA_MODEL.md`, `Docs/INVARIANTS.md`, `Docs/CODE_MAP.md`, this plan.
- Work: document restart scope, lock preservation, confirmation, and prompt ownership; record validation and archive plan.
- Acceptance: affected workflow/data contracts describe current behavior; final diff contains no unrelated changes.
- Validation: `git diff --check`; final diff review.
- Status: complete.

## Validation
Commands to run: `python3 -c "import sys, ast, pathlib; assert sys.version_info.major == 3; ast.parse(pathlib.Path('zet/services/minor_character_workflow_service.py').read_text(encoding='utf-8'))"`; `node --check zet/web/static/minor_characters.js`; `git diff --check`.
No maintained test additions or E2E scenarios are planned.

## Risks and alternatives
Restarting Style can invalidate working views, so the browser and service both enforce confirmation. Existing locked Inventory assets must remain independent of workspace board resets.

## Progress and decisions
- Initial inspection confirmed current board prompts already come from the latest template candidate and are public as `board.prompt`.
- Current board-action revisions and slot membership provide the existing late-result fence.
- WP1 and WP2 are implemented. View restart starts a fresh alignment render; STYLE restart resets all boards/analysis inputs and re-analyzes. The confirmation is checked both in the browser and service. Inventory locks are left untouched.
- Documentation updates cover restart and prompt display ownership; final diff review and static checks passed.

## Final results
Changed behavior: stage restart actions, conditional STYLE restart confirmation, and current-round prompt display. Inventory locks and original references are preserved. No permanent tests or scenarios were added.

Validation observed: Python 3 AST parse passed; `node --check zet/web/static/minor_characters.js` passed; `git diff --check` passed. The approved E2E suite and visual/browser behavior were not run for this change.

Remaining issues: none known. The changed browser flow was not exercised interactively.
