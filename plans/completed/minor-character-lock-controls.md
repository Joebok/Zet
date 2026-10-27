# Minor Character lock controls
Status: complete

## Goal and current behavior
Expose lock/unlock on cards and review dialogs for Style, Front, Three-quarter and Profile. Current projection and publication restrict locking to view true-ups; no unlock endpoint exists.

## Constraints and impact
Keep style private, preserve immutable Inventory images on unlock, and retain board revision fences. Affected owners: minor service/workflow, publication service, router and minor JavaScript. Update Local Characters, Data Model, Invariants and Code Map. No new dependencies or permanent tests.

## Work packets
### WP1 — Backend transitions
- Dependencies: none.
- Files: minor_character_service.py, minor_character_workflow_service.py, quick_character_publication_service.py, minor_character_router.py.
- Work: allow current rendered stage candidates to lock; persist style privately; add revision-fenced unlock without deleting published assets.
- Acceptance: each stage locks/unlocks; stale revisions fail; style never publishes.
- Validation: disposable isolated service checks and Python syntax.
- Status: complete.

### WP2 — Shared presentation and documentation
- Dependencies: WP1.
- Files: minor_characters.js and affected Docs owners.
- Work: shared accessible icon toggle on cards/dialogs; document new eligibility and preservation behavior.
- Acceptance: both surfaces expose matching lock state and unlock action.
- Validation: disposable browser check, node syntax, approved E2E baseline, git diff --check and final diff review.
- Status: complete.

## Validation and final results
- Implemented shared accessible lock/unlock icon controls on stage cards and review dialogs.
- Added revision-fenced unlock and private STYLE lock records; official alignment/true-up views can publish, while publication still rejects STYLE. Unlock retains selection and Inventory bytes.
- Updated Local Characters, Data Model, Invariants and Code Map.
- `npm.cmd run test:e2e`: all four approved scenarios passed (44.8s).
- Disposable `python3 -B test-results/minor-locks/check.py`: passed real service/API transitions for all stages, failed-review alignment eligibility, stale revision/wrong candidate rejection, private style, mixed style/view publication, locked image reads and preserved Inventory bytes/selections. Changed Python AST passed.
- Disposable `node test-results/minor-locks/browser.cjs`: passed mounted real HTML/JavaScript with prepared responses, icon state/actions on cards/dialogs for all four stages, matching state updates and no browser errors.
- `node --check zet/web/static/minor_characters.js` and `git diff --check`: passed. Final diff reviewed.
- No permanent tests, dependencies, live AI calls or normal library changes. Running Zet process was not restarted; backend changes require its normal restart/reload.

