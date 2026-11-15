# Recover failed Body Reference template reviews
Status: active
Related issue/specification: User report for AI_ab18814bfe37e14339e7623e17800240

## Goal
Settle structured template review requests from their durable terminal failure receipts, preserve valid sibling section edits, and show saved failure details on the review page.

## Current behavior
The Body Reference line review sends each section in a separate structured Ollama request with a 384-token output cap. A failed request whose answer payload has been cleaned up is not returned by AIJobService.result, so its continuation yields again even though its receipt is terminal. Proposal progress reports only the latest request. The observed failed request exhausted its token cap while producing JSON, while a sibling request completed successfully.

## Desired behavior
Direct and background structured consumers observe verified terminal failures from receipts. Body Reference sections use a 1,536-token cap for new asks. Saved proposals expose failures from each section, retain independently validated successful edits, and settle as failed when all sections fail. The page stops polling when settled and presents partial or complete failure details.

## Invariants and constraints
Keep receipt identity and universe checks, existing job locks, request identity reuse, answer ownership, storage pause behavior, response schema validation, independent section validation, source guards, explicit acceptance, and old cached structured results. Do not add dependencies or maintained tests.

## Implementation steps
### WP1 - Read durable structured failures
- Dependencies: none.
- Files/interfaces: zet/services/ai_job_service.py, zet/services/ai_job_coordinator.py.
- Work: Make result surface a verified terminal failed receipt when its payload is gone. Reuse this in direct continuation and background structured collection. Turn malformed output-limit failures into a clear truncation message using receipt runtime metadata.
- Acceptance: A cleaned terminal failure settles both callers without provider resubmission; temporary collection errors still retry and unavailable storage still pauses.
- Validation: Disposable incident-shaped receipts and successful prepared answers; inspect existing approved scenarios.
- Status: complete. Matching terminal failure receipts now surface through the shared result path. Output-cap JSON failures include the observed token count.

### WP2 - Settle section reviews
- Dependencies: WP1.
- Files/interfaces: zet/services/character_container_template_service.py.
- Work: Raise the new Body Reference section cap to 1,536 tokens. Preserve completed sibling edits and attach failed section details. Mark an all-failed review terminal with its causes.
- Acceptance: Existing request IDs are reused after restart; partial findings remain reviewable; all failures save a terminal proposal.
- Validation: Disposable fixture replay with failed receipt, missing answer/cache, and successful sibling cache, plus clean success and all-failed cases.
- Status: complete. Body sections allow 1,536 tokens; individually valid sibling findings survive section failures, and all-failed proposals persist FAILED.

### WP3 - Project settled proposal state
- Dependencies: WP1 and WP2.
- Files/interfaces: zet/services/character_container_template_service.py, zet/web/static/character_asset_container.js.
- Work: Share proposal progress projection between detail and latest APIs, summarize all section request statuses and errors, display saved partial failures, and stop polling at terminal state.
- Acceptance: The review page shows pending sibling work with prior failures, then shows the settled partial result after polling or reload.
- Validation: Disposable API and browser checks, JavaScript syntax, approved E2E baseline, and git diff --check.
- Status: complete. Latest and detail endpoints share progress projection, including every request's status and failure reason. The dashboard displays failures and stops polling when the proposal settles.

## Validation
npm.cmd run test:e2e passed all four approved scenarios (42.1 seconds). node --check zet/web/static/character_asset_container.js, Python AST parsing of the changed services, and git diff --check passed. No live model call or deployment was performed. The incident proposal was inspected in the Test data store but not reconciled because the Test release still runs the previous code.

## Progress and decisions
- Initial inspection found that request AI_ab18814bfe37e14339e7623e17800240 exhausted 384 tokens and a sibling request returned one edit. The Test page API still reported PROPOSING.
- Receipt-backed failures now settle structured callers after answer cleanup, with output truncation described from saved runtime metadata. New Body section asks receive the larger cap. API progress lists request failures alongside pending siblings.

## Final results
Implemented the three work packets and updated AI job and Local Characters documentation. The four-scenario E2E suite, JavaScript syntax check, Python AST check, and whitespace diff check passed. The Test deployment and its existing proposal remain pending a release update; no deployment or live retry was performed.
