# E2E process review
Status: complete
Related specification: review of completed broaden-e2e-coverage plan and commit b1f1166.

## Goal
Verify the approved 20-scenario suite and recent testing changes, fix observed defects, and retain isolated failure evidence. No new maintained scenarios, dependencies, live AI calls, or deployment.

## Impact and constraints
Testing ownership: `tests/e2e`, `Scripts/run-e2e.mjs`, Playwright configuration, and `Docs/Testing.md`. Navigation ownership: `Docs/INDEX.md`. Preserve private library/queue/runtime isolation, frozen inputs, and attempt fencing. Inspect recent production changes without broadening their scope.

## Implementation steps
### WP1 - Review and baseline
- Dependencies: none.
- Files: completed plan, recent commit, testing guidance and harness.
- Acceptance: identify unresolved issues and run the approved suite.
- Validation: `npm.cmd run test:e2e`.
- Status: complete. Baseline passed 20/20 in 2.0 minutes.

### WP2 - Repair observed harness defects
- Dependencies: WP1.
- Files: affected E2E hooks, `tests/e2e/server.py`, and `zet/services/image_usage_service.py`.
- Acceptance: browser-exception failures preserve fixture evidence; no scenario expansion.
- Validation: disposable failure probe and approved suite rerun.
- Status: complete. Existing hooks repaired; disposable browser-error probe retained fixture and trace, then failed as intended. Rename UI and marker concurrency probes passed.

### WP3 - Reconcile documentation and finish
- Dependencies: WP2.
- Files: `Docs/Testing.md`, `Docs/INDEX.md`, completed coverage plan, this plan.
- Acceptance: current baseline and results match executable behavior.
- Validation: discovery, relevant syntax checks, `git diff --check`, final diff review.
- Status: complete. Documentation reconciled; discovery, syntax and diff checks passed.

## Findings
- Coverage plan is stored as completed but still says active.
- Index still calls the current baseline four scenarios.
- Existing afterEach hooks retain ordinary failures but skip fixture retention when the browser-error assertion itself fails.
- Plan records a fixed cross-phase source NameError and intermittent Windows image-usage file-sharing warnings. Inspect current execution before deciding whether another fix is needed.
- Baseline reproduced a Windows sharing warning on an image-usage pending marker. Inspection found `drain` opening a marker before acquiring the consumer lock, racing writer deletion. Replay now derives the same lock from the filename before reading; validates consumer/hash correspondence inside the lock. Storage formats and polling remain unchanged. `Docs/COMPONENTS/LIBRARY.md` owns this maintenance detail.
- Disposable lock-order and already-completed-marker probes passed. The first browser probe setup was rejected because Playwright forbids importing another spec; corrected to copy the actual existing hooks into the disposable spec.
- Corrected disposable browser run: one intentional browser-error failure, one successful Character/phase rename UI check including reload. Retained failure snapshot verified under ignored `test-results/e2e-review-probe`. Temporary spec removed.
- Real-file-lock concurrency probe confirmed replay waits while the writer owns the lock and tolerates the marker being deleted before replay acquires it.
- Release output buffering, streamed command success and nonzero exit propagation probes passed without deploying. Syntax checks passed for all six Python and 22 JavaScript files changed by the recent commit or this review.
- Discovery lists exactly 20 tests in 17 files. Final approved-suite rerun is in progress. No optional live check was invoked.
- Second full run passed 20/20 in 2.0 minutes with no usage warning, but reproduced the plan's separate Windows Proactor socket-shutdown traceback. The Windows fast fixture now runs Uvicorn on a selector loop; it uses no asyncio subprocesses. Live and inspection modes keep their existing loop choice. A final full rerun checks this harness repair.

## Final results
Final `npm.cmd run test:e2e`: 20 passed in 2.0 minutes, with no application usage-maintenance warning or socket-reset traceback. Node emitted only its harmless conflicting color-environment warning. Discovery: 20 tests in 17 files. Python/JavaScript syntax and `git diff --check` passed. Final diff inspected; no unrelated product changes, dependencies or maintained scenarios added. Completed coverage plan status and current testing navigation corrected. Optional live execution and production deployment remain unverified by design.
