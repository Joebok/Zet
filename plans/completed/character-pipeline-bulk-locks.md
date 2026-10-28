# Character pipeline bulk locks
Status: complete
Related specification: Joe's request for Lock all / Unlock all with one confirmation.

## Goal and current behavior
The five character pipeline pages share `local_asset_pipeline.js`. Individual
actions use `LocalImagePipelineWorkflowService` and existing adapter publication
guards. Assembly/Dressing preview and publish required lineage. Locks belong to
character/phase/pipeline/costume, independently of the displayed batch.

## Desired behavior and constraints
Lock all selected images in the open batch; unlock every lock in the current
pipeline scope, including other batches and views absent from the open batch.
One confirmation per bulk action, with lineage changes included for publication.
Retain existing guards, immutable Inventory images, universe/costume isolation,
and report any partial failures. No dependencies or permanent tests.

## Impact analysis
Workflow service owns orchestration; existing local router exposes actions;
shared controller/CSS owns controls, confirmation and outcome. No schema changes.
Knowledge owners: Local Characters, Code Map, Testing. Existing S2 covers single
Assembly/Dressing publication, not bulk actions or the other three pipelines.

## Implementation steps
### WP1 — Bulk service actions and routes
- Dependencies: none.
- Files: `zet/services/local_image_workflow_service.py`,
  `zet/web/local_character_asset_pipeline_router.py`.
- Work: scope targets, aggregate publication previews, reuse adapter locks/unlocks,
  fence changed selections and expose completed/failed outcomes.
- Acceptance: selected-only lock; all scoped locks unlock; no cross-scope changes.
- Validation: disposable isolated service/API checks; Python syntax.
- Status: complete.

### WP2 — Shared pipeline controls
- Dependencies: WP1.
- Files: `zet/web/static/local_asset_pipeline.js`, `zet/web/static/zet.css`.
- Asset cache versions: `zet/web/templates/index.html`.
- Work: add Lock all / Unlock all beside selected views, one confirmation,
  duplicate-action protection, refresh and explicit outcomes.
- Acceptance: all five pages share actions; cancellation makes no writes.
- Validation: disposable browser checks and `node --check`.
- Status: complete.

### WP3 — Regression and knowledge
- Dependencies: WP1/WP2.
- Files: affected component/code-map/testing documents and this plan.
- Acceptance: document scope and partial-failure behavior, inspect final diff.
- Validation: approved `npm.cmd run test:e2e`; `git diff --check`.
- Status: complete.

## Risks and alternatives
Individual publications are recoverable, but the whole bulk action is not one
transaction. Report per-view failures while retaining completed operations.
Live rendering is unnecessary and outside this change.

## Progress and final results
All work packets complete. All four approved E2E scenarios passed (40.1s). Disposable
service checks passed publication, no-op, other-batch/out-of-view unlock, phase/
pipeline/costume isolation, retained Inventory bytes, stale selections and
per-view partial failures across all five adapters. Two disposable Chromium
journeys passed (23.7s), verifying all five pages, one dialog per action,
cancellation without writes, lock/unlock/relock, disabled completed actions and
retained publication files. Reference pipelines exercised two selected views;
Assembly/Dressing used prepared responses. Initial disposable runs needed fixture,
import and assertion corrections; the final run passed without page errors.
Python AST, JavaScript syntax and final diff checks passed. Component/code-map/
testing knowledge is updated. No new schemas, dependencies, permanent tests,
live inference, production-library writes or deployment. Disposable scripts live
under ignored `test-results/bulk-locks/`; no known blocker remains.
