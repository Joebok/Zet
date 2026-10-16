# Minor Character and iteration deletion
Status: complete

## Goal and scope
Add Delete controls to the Minor Characters list/editor and prompt iterations. Use logical deletion to remove records from the workspace without removing published Inventory assets or source/candidate files used by retained renders. Existing review-layout edits are user work and must remain intact.

## Luna-sized packets
### WP1 - Service and API deletion
- Files: minor_character_service.py, minor_character_router.py.
- Dependencies: none. Persist workspace/iteration deletion markers; hide deleted records and reject stale mutations; handle legacy aliases/name collisions and in-flight results. Clear working selections belonging to deleted iterations while retaining published locks and dependent renders.
- Acceptance: deleting an iteration or workspace stays deleted after reload; other iterations/characters and Inventory bytes remain intact; names can be reused; late jobs cannot resurrect deleted entries.
- Validation: disposable isolated service/API checks and Python syntax.
- Status: complete.
### WP2 - Management controls
- Files: minor_characters.js, index.html, zet.css.
- Dependencies: WP1. Add list/editor Delete character and per-iteration Delete actions with concise confirmation. After deletion show remaining iteration or list; avoid nested buttons. Preserve existing review layout and custom feedback.
- Acceptance: cancel is harmless; confirmed actions target only the named item; empty state remains usable.
- Validation: disposable browser journey, JS syntax and diff review.
- Status: complete.
### WP3 - Documentation and regression checks
- Files: LOCAL_CHARACTERS, DATA_MODEL, CODE_MAP, this plan.
- Dependencies: WP1-2. Document deletion semantics and actual validation.
- Validation: three approved E2E scenarios, git diff --check; no permanent tests/dependencies, normal-library writes, live generation or release actions.
- Status: complete.

## Impact and constraints
Reuse version 2 optional fields, no catalog schema change. Retain deleted records internally so queue results, selected-front references and published provenance keep valid files. Delete controls are user-triggered; no actual user data is deleted during implementation validation. Existing E2E scenarios provide regression coverage; feature checks stay disposable.

## Decisions and implementation
- Workspace Delete is available from list rows and the editor; iteration Delete is beneath each iteration thumbnail. Both use a concise confirmation naming the target and stating that Inventory images remain. Cancel leaves the workspace unchanged.
- Optional deleted_at markers hide records without deleting files. Iteration deletion clears working selections belonging to its candidates; existing locked Inventory outputs and dependent iterations remain valid. Deleted candidates are rejected by selection, refinement, lock and legacy render-retry paths. Late jobs cannot restore deleted entries. Pending slot responses from before deletion cannot overwrite the current editor.
- Workspace deletion uses the existing universe name lock, includes adopted legacy same-name records and renamed aliases, rejects reopening and permits name reuse. Analysis completion checks deletion before creating candidates. No catalog change or new dependency.
- Updated LOCAL_CHARACTERS, DATA_MODEL, CODE_MAP and the existing ADR 0014 deletion decision. Preserved all pre-existing review-layout edits.

## Observed validation and final results
- Disposable minor-delete-check.py passed, including final rerun after stale-refinement/retry guards: iteration deletion/reload, cleared working front versus retained side selections/locks, published bytes, dependent iteration replay, late queued completion, hidden render busy state, rejected stale mutations, workspace/alias deletion, name reuse and deletion during blocked analysis.
- Disposable minor-delete-browser.mjs passed: character and iteration confirm/cancel, inactive/final iteration removal, reload, stale API 404, preserved locks, empty state, name reuse, editor/list delete controls. Existing independent slots, card/review locking and responsive checks also passed in that journey.
- Existing disposable minor-character-check.py passed before the feature checks.
- npm.cmd run test:e2e: all three approved scenarios passed (28.1s).
- Python AST, node --check, git diff --check passed; final diff reviewed for unrelated changes. No permanent tests or dependencies added.
- Owned fixture server stopped. Normal library untouched; no live generation, commit, push or deployment performed.
