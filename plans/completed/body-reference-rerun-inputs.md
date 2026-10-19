# Body-Reference recompile and reset inputs
Status: complete
Related request: respect Recompile and clear obsolete references on candidate reset.

## Goal and current behavior
Body-Reference already forwards batch/view Recompile to its adapter. Refresh updates
original candidate definitions but can leave older mutable prompt overrides intact.
Batch, view and failed-candidate resets retain reference previews; legacy downstream
invalidation also retains frozen render inputs.

## Impact and constraints
Owner: `zet/services/local_body_reference_service.py`; caller:
`LocalImagePipelineWorkflowService`; documentation owner:
`Docs/COMPONENTS/LOCAL_CHARACTERS.md`. Preserve ordered references, batch-local
template revisions, immutable locks, unrelated candidate state and Retry replay.
No schema change, live data repair, inference, deployment or permanent tests.

## Implementation steps
### WP1 — Refresh effective candidate prompts
- Dependencies: none.
- Files: `zet/services/local_body_reference_service.py`.
- Work: synchronize refreshed prompts into original and supplemental candidate
  overrides; check protected views before refreshing batch artifacts.
- Acceptance: Recompile replaces stale overrides only for affected active candidates;
  unchecked reruns retain saved prompt text and protected actions do not compile.
- Validation: disposable temporary-directory service checks with prepared compilation.
- Status: complete.

### WP2 — Clear obsolete render reference bookkeeping
- Dependencies: WP1.
- Files: same service and `Docs/COMPONENTS/LOCAL_CHARACTERS.md`.
- Work: clear frozen inputs, reference previews and input hashes in every reset path;
  document the reset and recompile contract.
- Acceptance: reset candidates expose no prior reference images; untouched views and
  render Retry keep their existing inputs.
- Validation: disposable reset checks, approved S2, Python AST, `git diff --check`.
- Status: complete.

## Validation and results
Completed 2026-10-19:
- `python3 -B test-results/body-reference-rerun-check.py`: ten disposable checks and
  Python AST passed. Checks cover batch/view resets with Recompile on/off, original
  and supplemental overrides, untouched views and detached candidates, protected
  actions before compilation, failed-candidate and legacy downstream resets,
  submitted reference bytes and frozen failed-render replay after Inventory changes.
- `npm.cmd run test:e2e -- --grep "character-to-costume"`: approved S2 passed,
  1 test in 16.9 seconds. S2 covers shared Assembly/Dressing regression only;
  disposable checks cover Body-Reference reset/recompile directly.
- `git diff --check`: passed; final diff reviewed for unrelated changes.

The disposable harness initially needed the production PipelineCandidates directory
shape and raw compiler-manifest path format; these fixture issues were corrected.
No live library, queue, render service or Inventory data was changed. No production
deployment or existing-batch repair was performed. The component document records
the corrected contract; no entry point or data schema moved, so no code-map or ADR
change is needed.
