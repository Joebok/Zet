# Restart Narrative interview
Status: complete

## Goal and current behavior
Add Restart interview beside Continue interview and Re-run last interview. Currently
every interview includes the saved conversation; replay uses frozen historical inputs.
Restart must use current saved inputs without earlier conversation.

## Impact and constraints
Owners: narrative_generation_service.py, narrative.js, COMPONENTS/NARRATIVE.md.
Keep authored inputs, prompt, candidates, references and immutable job snapshots.
Mark earlier interview jobs as cleared so late responses and replay cannot restore
discarded conversation. Supersede pending proposals; retain applied input changes.
No new dependencies, permanent tests, live AI calls or production data writes.

## Work packets
### WP1 — Restart service action
- Dependencies: none.
- Files: zet/services/narrative_generation_service.py.
- Add restart_interview, clear conversation, fence old reviews/responses/replays.
- Acceptance: new request has current inputs and empty history; other state survives.
- Validation: disposable isolated service checks and Python syntax.
- Status: complete.

### WP2 — Dashboard and documentation
- Dependencies: WP1.
- Files: zet/web/static/narrative.js, Docs/COMPONENTS/NARRATIVE.md.
- Add button, dispatch, busy handling and direction clearing using existing flow.
- Acceptance: current edits save before restart; existing actions retain semantics.
- Validation: JavaScript syntax, approved npm run test:e2e, diff review.
- Status: complete.

## Validation and results
- `npm.cmd run test:e2e`: all four approved scenarios passed (41.0s).
- Disposable in-memory service checks passed: current-input request with no old
  history, new direction included, authored state and images preserved, pending
  proposals superseded, late replies suppressed, cleared replay rejected, and
  subsequent Continue interview uses only the new conversation.
- `node --check zet/web/static/narrative.js`, Python AST parsing and
  `git diff --check` passed. Final diff reviewed for unrelated changes.
- No live AI execution or production library writes. The new button was wired
  through the existing save/submission/busy flow; no dedicated browser journey
  was added. Existing frozen job records remain for execution provenance.

## Final results
Added Restart interview alongside the existing controls and documented its
semantics. A cleared-job marker fences late results and replay without changing
authored data or deleting immutable execution snapshots. No new dependencies,
permanent tests or unresolved blockers.
