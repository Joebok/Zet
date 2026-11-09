# Shared Candidate Board
Status: complete
Specification: [Candidate Board](../../Docs/COMPONENTS/CANDIDATE_BOARD.md)

1. Controls and grid. Extend the browser module with a keyed mount/update/dispose contract and shared CSS. Check exact render intents and stable slots in Chromium.
2. Review and comparisons. Depends on packet 1. Add the separate modal, focus management, comparison chooser and shared zoom lifecycle. Check compact layout and progress updates during review.
3. Integration guide and validation. Depends on packet 2. Document the subscriber contract and verify it using a disposable fixture and the approved fast suite.

The module adds no requests or preflight checks. Existing services and callers retain their action and polling responsibilities. Production workflow migrations are separate.


All three packets completed. The dashboard loads the scoped styles and shared
zoom helper. The reusable API is exported alongside the existing board helpers.
See the [subscriber guide](../../Docs/COMPONENTS/CANDIDATE_BOARD_INTEGRATION.md)
and [UI ownership decision](../../Docs/DECISIONS/0051-candidate-board-ui-ownership.md).

Validation passed on 2026-11-08. JavaScript syntax checks passed.
The disposable Chromium subscriber checked exact Draft 1 and Final 4 intents,
insufficient capacity, card and review updates, synchronized zoom, broken
comparison fallback, local error feedback, focus return, compact layout, and
late action completion after scope change. The approved fast suite passed
all four scenarios in 41.0 seconds. Production workflow migrations are separate.
