# Character rename feedback
Status: complete
Related issue/specification: user report of silent character renames and stale scope selectors.

## Goal and current behavior
Character Overview currently awaits the synchronous rename API without visible
feedback, then reloads the page. The service completes filesystem/catalog updates
before returning; derived index refresh remains asynchronous. The shell owns scope
selectors and stored selection. Preserve the existing storage and recovery contract.

## Desired behavior and constraints
Show pending feedback immediately, prevent duplicate/conflicting scope actions,
refresh both selectors and preserve the returned character/phase, then show a
persistent positive completion message. Distinguish rename success from refresh
failure. Preserve universe ownership and user changes. No new dependencies,
permanent tests, live inference, or normal-library writes.

## Impact and documentation
`character_hub.js` owns operation feedback and management controls; `zet.js` owns
scope state, URL, storage and refreshed selectors. Dashboard UI and Local Characters
own the affected behavior documentation; the code map will note shell ownership.
No serialized data or backend API changes are needed.

## Implementation packets
### WP1 - Rename lifecycle and scope refresh
- Dependencies: none.
- Files: `zet/web/static/character_hub.js`, `zet/web/static/zet.js`.
- Work: expose awaited shell refresh for a returned rename scope; display pending,
  refreshing, success and error feedback; retain feedback across overview refresh;
  prevent conflicting management/scope actions while awaiting completion.
- Acceptance: character and phase rename preserve the other selected value, remove
  obsolete options, update URL/storage and confirm completion without page reload.
- Validation: JavaScript syntax, existing rename E2E, disposable delayed/failure
  browser checks in the isolated fast fixture.
- Status: complete.

### WP2 - Validation and affected knowledge
- Dependencies: WP1.
- Files: affected component/code-map documentation and this plan.
- Work: document final behavior, record observed results, inspect final diff,
  archive the completed plan.
- Acceptance: validation accurately reports gaps; existing user changes preserved.
- Validation: focused E2E and `git diff --check`.
- Status: complete.

## Risks and decisions
Navigation must not cancel an accepted rename request. A rename that succeeded
must not be described as failed merely because a subsequent dashboard refresh
failed. UI feedback must not be replaced by a late ordinary overview response.

## Progress and observed validation
- Implemented in-place shell scope refresh and scope-bound hub feedback, with
  conflicting controls disabled and page-independent rename transport.
- JavaScript syntax checks passed for both controllers; `git diff --check` passed.
- Existing rename E2E passed (1/1, 4.9s).
- Disposable browser check passed (1/1, 8.4s): delayed pending response, disabled
  controls, actual character and phase renames, obsolete options removed,
  unchanged opposite selection, URL/storage persistence after reload, no reload
  during rename, retained success on overview refresh, API rejection, and
  successful mutation followed by context-refresh failure. No browser exceptions.
- One initial disposable run could not start because another test server occupied
  port 8765. It passed after that server exited; no other process was stopped.
- Disposable test removed after execution. No permanent scenario was changed.
- The default-port full-suite attempts collided with a concurrent test run; the
  overlapping attempt was interrupted. The complete existing suite then passed
  on private port 8875 with a unique temporary fixture root (11/11, 53.6s), using
  `node node_modules/playwright/cli.js test --config
  playwright.rename-feedback-disposable.config.mjs`. The disposable configuration
  imported the existing configuration and only changed its server launch/port;
  the wrapper reused `tests/e2e/server.py` in fast mode. Both temporary files were
  removed. The run logged one non-failing usage-maintenance file-in-use warning
  in its isolated temporary storage.
- Updated Dashboard UI, Local Characters and Code Map ownership notes. Final
  JavaScript syntax and diff checks passed; final diff reviewed for scope.

## Final results
Character and phase rename now show pending, refreshing and persistent completion
feedback. The shell refreshes both selectors in place, preserves the returned
selection and updates URL/storage. Conflicting scope/management controls remain
disabled until settlement; an accepted rename is not canceled by page navigation.
Refresh errors after a successful rename explicitly preserve that successful
outcome. No backend/storage contract, dependency, or permanent test was changed.
Existing user changes were preserved. Live-library renames and live AI services
were not exercised.
