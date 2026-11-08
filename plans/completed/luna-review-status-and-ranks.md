# Luna Review status and card ranks
Status: complete
Related issue/specification: User request, 2026-11-08

## Goal
Show accurate async Luna Review status in Character Asset Containers and update candidate cards with saved ranks after render duration.

## Implementation steps
### WP1 - Review status lifecycle
- Dependencies: none.
- Files/interfaces: zet/web/static/character_asset_container.js.
- Work: show running after admission, surface saved terminal outcomes from progress/detail, update open review, keep current-view fencing and polling lifecycle.
- Acceptance: no RUNNING response is announced as complete; terminal states reflect saved review.
- Validation: JS syntax and diff checks passed. E2E attempt could not start because port 8765 was already occupied by another server.
- Status: complete.

### WP2 - Candidate rank display
- Dependencies: none.
- Files/interfaces: zet/web/static/candidate_board.js and Character card signature in zet/web/static/character_asset_container.js.
- Work: render saved rank after duration and include rank changes in card signature.
- Acceptance: ranked cards update without reload; failed/running reviews do not expose stale ranks as current; obsolete ranks are labeled previous.
- Validation: JS syntax and diff checks passed. Prepared browser check not completed because the E2E server port was occupied.
- Status: complete.

## Validation
- node --check zet/web/static/candidate_board.js: passed.
- node --check zet/web/static/character_asset_container.js: passed.
- git diff --check: passed.
- npm.cmd run test:e2e: initial run began and reported the first two scenarios passing before the command call returned without its final result. A subsequent run exited before tests because http://127.0.0.1:8765/api/context was already in use. No existing server was stopped.
- Disposable browser scenarios for delayed completion, failure, obsolete results and navigation were not performed.

## Final results
Updated async status feedback and rank presentation. Full E2E outcome and delayed-review browser cases remain unverified because the test server port was occupied.
