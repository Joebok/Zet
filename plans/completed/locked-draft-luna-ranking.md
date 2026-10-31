# Locked Draft fidelity in Luna ranking
Status: complete

## Goal and constraints
Rank Draft and Final separately across the five character pipelines, using the matching locked Draft as important comparison evidence when available. Preserve human decisions, locks, universe isolation and existing Draft state. No new permanent tests or live model calls are authorized.

## Work packets
1. Shared ranking and evaluation contracts (`local_image_ranking_service.py`, `local_image_evaluation_service.py`): matching Draft locks, labeled evidence, mode-scoped state and fences. Validation: disposable attachment and isolation checks. Status: complete.
2. Body Reference (`local_body_reference_service.py`): mode-aware ranking, recovery and stale checks, retaining rejection behavior. Validation: disposable candidate isolation and rejection check. Status: complete.
3. Head Image and Head Image Edit (`local_head_image_service.py`): mode-aware ranking and locked-Draft evidence. Validation: disposable Final prepared request and stale-result fence. Status: complete.
4. Assembly and Dressing (`local_character_asset_pipeline_service.py`): mode-aware ranking, comparison fencing and costume isolation; retain Assembly FRONT evidence. Validation: disposable prepared Assembly request with both comparisons. Status: complete.
5. Dashboard and collector (`local_image_workflow_service.py`, `render_slot_service.py`, router and `local_asset_pipeline.js`): queue, recover, display and re-evaluate the active mode. Validation: isolated Final API/Chromium journey and recovery dispatch checks. Status: complete.
6. Documentation and validation: update Local Characters, data model, invariants, testing and code map; run baseline and diff check, review diff and archive plan. Status: complete.

## Progress and remaining work
Draft and Final ranking now flow independently through all five character pages. Comparison changes stale advice and fence late results. Existing records default to Draft; missing Final fields are empty. Prepared checks cannot establish live model quality or full restart recovery.

Final validation: `npm.cmd run test:e2e` passed all four approved scenarios (43.8 seconds); Python AST, JavaScript syntax and `git diff --check` passed. Disposable checks covered candidate isolation, reference mapping, rejection, recovery dispatch and a changed-lock late-result fence. An isolated API/Chromium journey verified Final evaluation, display, mode-specific Re-evaluate and switching to Draft. No live model calls were made; full restart recovery and artistic ranking quality remain unverified.
