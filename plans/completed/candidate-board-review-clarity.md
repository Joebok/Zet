# Candidate Board review clarity

Status: completed

Show captured references, saved render settings, and Luna status across Character Candidate Boards. Preserve the frozen request and the current ranking rules.

1. Serve the scoped frozen reference with its detected raster type in the Character router. Verify with disposable files, including extensionless PNGs and unavailable inputs.
2. Add optional input markers and render settings to the shared board. Map saved Character bindings and settings in its adapter. Verify labels, order, and settings in Chromium.
3. Give Luna a dedicated shared status line fed by Character actions and polling. Verify each transition and keep action feedback separate.
4. Update the component spec and subscriber guide. Run the approved fast suite, syntax checks, and diff checks. Record results and archive the plan.

## Validation results

- The disposable HTTP fixture served both extensionless and named PNG files inline with their exact captured bytes. It rejected wrong-view, wrong-universe, missing, invalid-index, corrupt, and outside-directory inputs.
- The disposable Chromium fixture verified all four saved reference labels in binding order, separate-tab targets, candidate settings independent of current controls, and Luna status transitions from initial state through start, completion, outdated, failure, and rerun.
- The first approved fast run found S2 still expected the old link labels. Updated that existing assertion and reran the suite. All four scenarios passed in 41.4 seconds.
- Changed JavaScript syntax, Python AST parsing, and `git diff --check` passed. The browser and HTTP checks ran in disposable fixtures without live AI.
