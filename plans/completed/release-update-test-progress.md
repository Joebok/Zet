# Release updater test progress
Status: complete
Related plan: [command-line release update](../command-line-release-update.md)

## Goal
Show the active E2E scenario and result in the command line during a release update, give the expanded 20-scenario suite an appropriate timeout, and retain the explicit `-SkipTests` behavior.

## Constraints
Keep production APIs and deployment request formats stable. Preserve current deployment lifecycle, failure handling, output logs, and test lock. `-SkipTests` must not invoke npm, Playwright, or any other test command; release validation and compatibility checks remain active. Do not run a real production update.

## Work packets
### WP1 - Stream test output to the updater CLI
- Files: `zet/services/deployment_service.py`, `zet/scripts/deploy_release.py`, `zet/scripts/update_release.py`.
- Work: retain controller output in a per-operation log, stream E2E subprocess output into that log, and tail new lines from the CLI while waiting for the deployment state. Force Playwright's line reporter for release validation so scenario starts and results are visible without terminal redraws.
- Acceptance: scenario start/result output is visible during the command; failure and timeout output remains available in the operation log; dashboard deployment still retains a log.
- Status: complete.

### WP2 - Reconcile E2E timeouts and skip behavior
- Files: `zet/scripts/deploy_release.py`, `zet/scripts/update_release.py`, `Docs/DEVELOPMENT.md`, `Docs/Testing.md`, `Docs/CODE_MAP.md`, `Docs/GitHub_Task_Workflow.md`.
- Work: set the E2E command timeout to 15 minutes, document the updater wait window and current 20-scenario suite, and verify the skip branch omits every test command.
- Acceptance: ordinary updates stream and finish within the longer suite window; `-SkipTests` still performs port cleanup and non-test release validation without invoking npm/Playwright.
- Status: complete.

## Results
- `npm.cmd run test:e2e` passed all 20 scenarios in 2.1 minutes. Windows emitted intermittent, non-fatal image-usage maintenance file-sharing warnings.
- With the release line reporter, a focused scenario printed its `[1/1]` title at start and passed (8.7s). The full suite also emitted `[n/20]` titles and results.
- Disposable Python checks passed for skip-branch command isolation, inherited subprocess output, incremental controller-log tailing, and final partial-line handling.
- `python3 -m py_compile zet/scripts/update_release.py zet/scripts/deploy_release.py zet/services/deployment_service.py` passed.
- `git diff --check` passed. Its only output was existing working-tree line-ending warnings.
- No live update, production restart, or optional live rendering check was performed.

## Final results
Complete. E2E timeout is 900 seconds and outer update wait is 2700 seconds. `-SkipTests` remains on the mutually exclusive branch before validation command construction, so the npm lifecycle and Playwright/browser setup are skipped while the other release checks continue.
