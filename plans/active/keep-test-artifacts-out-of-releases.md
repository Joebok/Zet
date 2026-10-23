# Keep test artifacts out of releases
Status: active — historical artifact cleanup blocked by automatic approval review
Related issue/specification: Joe's request to keep generated files out of release folders.

## Goal
Keep disposable E2E output and npm test packages outside finished production releases and the Zet source checkout. Preserve the approved scenarios and their isolated library/queue behavior.

## Current behavior
`playwright.config.mjs`, `playwright.live.config.mjs`, `tests/e2e/server.py`, and `tests/e2e/fast.spec.mjs` write under checkout-local `test-results`. `deploy_release.py` runs npm in each staged release; npm bootstraps `node_modules` there and leaves it after validation. Existing releases contain both directories.

## Desired behavior
Default E2E output lives in a disposable machine temp folder associated with the checkout. A caller can override its parent with `ZET_TEST_RESULTS_ROOT`. Successful test runs remove their unique output folder; failed runs retain it. Staging uses an operation-specific validation path outside `releases`, removes that path on success, and removes generated `node_modules` after the suite. Historical artifacts still need cleanup.

## Impact analysis
E2E configuration and fixture paths, deployment staging cleanup, and the Testing/Development/deployment documentation are affected. No production data, dependency declarations, or maintained scenarios change.

## Invariants and constraints
Keep fixture deletion confined to the selected test results root and scenario-specific subfolder. Do not touch the normal library or queue. Preserve failure traces. The release's `.venv` and runtime config remain in place.

## Implementation steps
### WP1 — Relocate E2E artifacts
- Dependencies: none.
- Files/interfaces: Playwright configs, `tests/e2e/server.py`, `tests/e2e/fast.spec.mjs`; `ZET_TEST_RESULTS_ROOT`.
- Work: Resolve one external default results root and apply it to Playwright, fixture, and prepared image paths.
- Acceptance: An E2E run creates no checkout-local `test-results`; successful output is removed and failure retention stays under the selected root.
- Validation: Approved fast E2E suite and path inspection.
- Status: complete. Four approved fast scenarios passed; no successful-run output remained under the temp results root.

### WP2 — Keep release staging disposable packages out of completed releases
- Dependencies: WP1.
- Files/interfaces: `zet/scripts/deploy_release.py` staging.
- Work: Route staging output to runtime state and remove the release's generated `node_modules` after the test command, including failed validation.
- Acceptance: New staged releases have no `test-results` or `node_modules` after validation.
- Validation: Focused disposable stage check; source review and `git diff --check`.
- Status: complete. A disposable mocked staging check passed for success and failure cleanup paths; production deployment was not run.

### WP3 — Document and review
- Dependencies: WP1–WP2.
- Files/interfaces: relevant Testing, Development, and deployment docs.
- Work: Record new paths, validation results, and review final diff; clean historical artifacts and complete this plan.
- Acceptance: Documentation matches the code and no unrelated files changed.
- Validation: `git diff --check`, `git status --short`.
- Status: blocked on historical cleanup. Documentation and diff review are complete.

## Validation
Run the approved fast E2E suite, a focused disposable staging check, and `git diff --check`. Do not run the live check.

## Risks and alternatives
Existing artifacts are disposable and Joe authorized cleanup after passing validation. Automatic approval review rejected recursive deletion, including a single fixed source path; this cleanup remains for Joe to perform manually. Temporary storage may be cleaned by the OS; failed runs are retained for diagnosis until removed manually.

## Progress and decisions
Existing five production releases contain checkout-local test artifacts and npm packages; they are not tracked Git files. Joe confirmed successful test output should be deleted to conserve disk space. The approved fast suite passed 4/4 in 41.5 seconds after the runner fix. The disposable staging check verified successful output cleanup, failed trace retention, and npm package cleanup. Existing targets were verified as direct folders without reparse points (about 1.208 GB total), but automatic approval review rejected deletion commands.

## Final results
Future test and staging cleanup is implemented and validated locally. Existing `C:\Users\Joe\Projects\Zet\test-results` and five release copies of `test-results` and `node_modules` remain because recursive deletion was rejected. No production deployment or live narrative check was run.
