# Assembly runs all requested views
Status: complete

## Goal and current behavior
Assembly no longer depends on previous views, but shared progression still opens one stage at a time. Replace its Continue-to-FRONT action with Run all views. Preserve Body/Head/Dressing stages, human selection/publication, two-image preparation, optional selected-FRONT ranking, queue ownership and frozen retries.

## Luna-sized packets
- WP1 — Progression/execution: local_character_progression_service.py opens/executes all requested Assembly views in one action, including existing partial batches; no selection gates. local_image_workflow_service.py reruns target all requested views. Keep persisted progression shape; stage 4 denotes all Assembly stages opened. Acceptance: real runner visits all views without selections; explicit view targets and interrupted resume stay bounded. Validate with disposable prepared runner checks. Status: complete.
- WP2 — Dashboard: local_asset_pipeline.js labels the action Run all views, removes Assembly stage/prompt-review wording from status and batch picker; front-only batches remain supported. Depends WP1. Acceptance: UI queues all requested views and doesn't advertise prompt review. Validate JavaScript syntax and disposable browser checks. Status: complete.
- WP3 — Validation/docs: update local-character/code-map/data-model knowledge; run approved S2/full fast regression and git diff --check. No new permanent tests/dependencies/live inference. Depends WP1-WP2. Record results and archive plan. Status: complete.


## Results and validation
Implemented Assembly all-view progression/execution, legacy partial-batch continuation, all-requested-view reruns and dashboard action/status/picker wording. Existing API and persistence shapes remain compatible; opened legacy Assembly stages allow all requested views. No human selections or published images are changed by the action. Human selection/publication and optional selected-FRONT ranking remain separate from generation.

Focused S2 passed (13.3s); full S1-S4 passed (41.1s). Disposable actual-runner checks passed eight-view execution without selections, legacy seven-view continuation, interrupted resume skipping the completed FRONT, explicit view fencing, all-view rerun and stop/other-pipeline review preservation. Chromium passed single-click eight-view dispatch, new action text and no stage/review picker labels/browser errors. Python AST, JavaScript syntax, final diff review and git diff --check passed. The disposable browser fixture shut down cleanly. Updated local characters, prompts, data model, code map and Testing. No new tests/dependencies or live quality claims; no remaining blocker.
