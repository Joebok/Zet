# Character Activity live work and errors
Status: complete
Related issue/specification: User request in current thread

## Goal
Show only in-progress character preparation and undismissed errors. Hide successful, partial and expected blocked actions. Dismissed errors do not block later action admission. Close Activity on successful navigation and refresh on navigation, open, tab return, submission or explicit request; remove recurring Activity polling.

## Implementation steps
### WP1 — Activity projection and non-blocking terminal errors
- Status: complete. Activity lists active and undismissed errors only; terminal operation states no longer block admission. Existing execution guards remain.
### WP2 — Dismiss endpoint
- Status: complete. `POST /api/local/operations/{id}/dismiss` is idempotent, and operation GET remains available for request identity recovery.
### WP3 — Browser Activity and navigation
- Status: complete. Removed Activity interval, added event-driven refresh and navigation close, Dismiss controls, and stale inline message cleanup.
### WP4 — Legacy state and knowledge
- Status: complete. Verified old recovery reservation had no committed candidates or handoff; canceled the reservation and marked its operation terminal under the ownership lock. Updated component, architecture, data model, code map, ADR index and ADR.

## Validation results
- Disposable repository check passed: active and error projection, hidden success/partial/blocked, repeated dismissal, retry admission and active dismissal refusal.
- Disposable FastAPI check passed: list, idempotent dismissal and operation ID recovery.
- Legacy runtime inspection: Activity projection now returns 0 visible records; 28 records remain retained for identity recovery.
- `npm.cmd run test:e2e -- --grep "character-to-costume"` passed all four approved scenarios (the runner executed the complete baseline; 4 passed in 42.3s).
- Python AST, `node --check` for all three changed JavaScript files, and `git diff --check` passed.
- No live model/render check or permanent test was added.

## Final results
Character Activity now shows active preparation and undismissed errors. Expected blocked and partial outcomes leave Activity, errors can be dismissed, retries are admitted, navigation closes the panel and refreshes the list, and Activity no longer polls on a timer.
