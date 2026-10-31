# Render slot timeout and late-image recovery

## Goal and evidence
Final character cards show available images alongside stale timeout errors.
`CharacterRenderSlots.collect` expires asks 1860 seconds after queueing without
checking shared job pending state. The shared detail projection marks images
complete but retains render errors; explicit reconciliation can also retain errors.

## Constraints and impact
Preserve candidate identity, attempt fencing, mode separation and review errors.
No production writes, model calls, dependencies or permanent tests. Owners:
`render_slot_service.py`, `local_image_pipeline_policy.py`,
`image_harvest_service.py`, and `Docs/COMPONENTS/LOCAL_CHARACTERS.md`.

## Work packets
### WP1 — Correct waiting and recovered-image state
- Dependencies: none.
- Work: allow one hour before slot timeout and defer expiry for shared pending jobs;
  remove stale render errors from available-image detail and reconciliation.
- Acceptance: old queued/running jobs remain pending; unavailable failures stay
  visible; available images have no render error; review errors remain intact.
- Validation: disposable isolated checks and approved fast E2E baseline.
- Status: complete.

### WP2 — Record and verify
- Dependencies: WP1.
- Work: update owning component documentation, inspect diff, archive plan.
- Acceptance: exact observed validation and deployment limits recorded.
- Validation: Python syntax and `git diff --check`.
- Status: complete.

## Results
Implemented one-hour fallback with shared pending-job protection. Existing detail
responses clear obsolete render errors for nonempty images; explicit reconciliation
repairs persisted errors even if hash/status already match. No schema or ownership
change; no code-map or ADR update needed.

`python3 -B test-results/check_render_timeout.py` passed isolated collector and
recovery checks, including provider errors, missing/empty outputs and retained
review errors. `npm.cmd run test:e2e` passed all four scenarios (47.2s). Python AST
syntax and `git diff --check` passed. Final diff reviewed for scope.

Hosted URL could not be fetched through the web tool. No deployment, live render
or production state write was performed. Deploy/restart is required for the
hosted dashboard to use the fix.
