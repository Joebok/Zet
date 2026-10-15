# Minor Character iteration slots and comparison review
Status: complete

## Goal
Group refinement attempts into prompt iterations with four manageable render slots. Inspect the designated original and a candidate together, select in review, and navigate only the current iteration's images.

## Current behavior and impact
MinorCharacterService stores frozen candidate inputs and render payloads; minor_characters.js displays individual candidates. Extend these records additively without changing selections, locks, stored files, or shared reconstruction behavior. Affected owners: LOCAL_CHARACTERS, DATA_MODEL, CODE_MAP and ADR 0014. Existing three E2E scenarios do not cover this editor; use disposable fixture checks.

## Invariants
No dependencies, permanent tests, live generation or normal library writes. Clearing/replacing a slot retains candidate files and selected/locked associations. Repeated renders use saved payloads with fresh seeds, independent of later workspace edits. Legacy candidates remain accessible as individual iterations.

## Luna-sized packets
### WP1 — Persistent iterations and slot actions
- Files: minor_character_service.py, minor_character_router.py.
- Dependencies: none.
- Add four-slot iteration records, legacy adoption, same-prompt add/regenerate and clear operations.
- Acceptance: frozen payload reuse, four-slot bound, independent iterations and preserved locks/selections.
- Validation: disposable prepared-response service checks, Python syntax.
- Status: complete.
### WP2 — Iteration board and full-size review
- Files: minor_characters.js, index.html, zet.css.
- Dependencies: WP1.
- Top iteration strip; four slots with clear/regenerate/select; shared count control; paired review dialog with selection and arrows/keyboard within current iteration.
- Acceptance: iteration switching restores its slots; reference changes affect display only; no separate image tabs; narrow layout usable.
- Validation: disposable Playwright journey and node syntax check.
- Status: complete.
### WP3 — Verification and knowledge
- Files: relevant component/data/code-map documentation, this plan.
- Dependencies: WP1–2.
- Record behavior and observed results; review diff.
- Validation: npm.cmd run test:e2e; git diff --check; disposable service/browser checks.
- Status: complete.

## Decisions
Generate and Try these changes start a new iteration with one occupied slot. Add renders fills up to the remaining four slots; regenerate replaces that slot only. Saved candidates remain internally available for selections and published image integrity.

## Observed validation and final results
- Disposable service journey passed: frozen prompt/pixel replay after workspace edits; four-slot bound; clear/regenerate preserves selections and locks; active iteration persistence; legacy board adoption. Existing disposable Minor Character service journey also passed.
- Disposable Playwright journey passed, including a final rerun after preview persistence changes: four slots, additions, switching iterations, clear/regenerate, preserved selection, review selection and arrows, refresh, and widths 1440/850/640. Paired review screenshot inspected. Prepared solid-color fixture images only; no live image-quality claim.
- npm.cmd run test:e2e: 3 passed in 26.8s on rerun. Initial run: two passed; costume scenario hit transient Windows permission denied reading its state.json and failure retention hit runner.lock. Inspected trace; no unrelated pipeline code or tests changed.
- Python AST, node --check, git diff --check passed. Final diff reviewed.
- Updated LOCAL_CHARACTERS, DATA_MODEL, CODE_MAP and ADR 0014. No dependencies or permanent tests added. Fixture servers stopped. Local implementation only; no commit, push or deployment performed.

## Refinements discovered during validation
Review navigation listens while the dialog is open even after candidate selection rebuilds its controls, preserving arrow-key operation. Preview and active iteration persist; empty boards remain available. Clear/replacement retains archived candidates internally for working selections, references and locks.
