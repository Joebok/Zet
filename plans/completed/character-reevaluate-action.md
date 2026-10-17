# Consolidate character evaluation controls
Status: complete
Related decision: [Ranking-only character review](../../Docs/DECISIONS/0018-ranking-only-character-review.md)

## Goal and current behavior
Expose Re-evaluate as the single evaluation action in all four character pipelines. The existing action passes through adapter preparation and the render runner; Head preparation clears human decisions/selections. Rank images stages Luna ranking separately; Re-analyze refreshes prompt-improvement observations. Completed evaluation IDs currently prevent a replacement staging record from being saved.

## Desired behavior and constraints
Re-evaluate stages fresh Luna ranking and refreshes AI prompt observations for existing rendered images in one view, or every rendered view at batch scope. Skip unrendered views and never submit renders or retired gate analysis. Preserve human decisions, selections, source bindings and immutable publication; retain existing harvest validation, universe binding, lock protections and stale-result fencing. Reuse active evaluation/observation work. Remove the separate dashboard ranking/analysis buttons; compatibility API routes remain.

## Impact analysis
Primary workflow owner: `local_image_workflow_service.py`; HTTP scheduling: `local_character_asset_pipeline_router.py`; dashboard: `local_asset_pipeline.js`; new evaluation admission: `local_image_evaluation_service.py` and the three adapters' staging callbacks; observation retry text/automatic deduplication: `local_prompt_improvement_service.py`. Existing record format stays unchanged. Update LOCAL_CHARACTERS and CODE_MAP. S2 covers initial Assembly/Dressing ranking and publication, but not explicit reevaluation; use disposable isolated checks for that contract.

## Implementation packets
### WP1 — Unified action and evaluation staging
- Dependencies: none.
- Files: shared workflow, evaluation service, three adapters, prompt improvement service and router.
- Work: validate rendered view targets before staging; refresh ranking/observations without the render runner; allow new evaluation staging while keeping completion updates fenced.
- Acceptance: completed or empty evaluations can be replaced, stale workers cannot overwrite replacements, no render/gate jobs or human-decision resets occur.
- Validation: disposable isolated workflow and persisted-evaluation checks; existing S1–S4 baseline.
- Status: complete.

### WP2 — Dashboard and knowledge
- Dependencies: WP1.
- Files: shared dashboard JS, LOCAL_CHARACTERS and CODE_MAP.
- Work: remove Rank images/Re-rank and Re-analyze buttons/client dispatch; describe Re-evaluate and update retry messages.
- Acceptance: all four pages expose only Re-evaluate for evaluation; observations/ranking remain visible.
- Validation: JS syntax, isolated browser inspection, Python syntax, final diff review.
- Status: complete.

## Validation and final results
- `npm.cmd run test:e2e`: all four approved scenarios passed in 32.1 seconds using the verified project Python 3 environment and pinned browser cache under ignored test-results. The first sandboxed attempt hit Windows atomic-file replacement errors and was stopped; the complete run outside that sandbox passed.
- Disposable `test-results/check-character-reevaluate.py`: actual HTTP action routing and adapter staging callbacks passed for all four pipelines with prepared observations/ranking operations and isolated persisted state. Covered batch vs. view targeting, replacement of completed/empty evaluation IDs, repeated reevaluation, harvest admission, preserved human decisions/notes/selections, skipped unrendered views, no render/legacy reevaluation calls and rejection of old evaluation updates/completion.
- Disposable `test-results/run-character-controls.py`: all four pages expose only Re-evaluate for evaluation; view/batch requests carry the correct scope, AI observations remain visible, and no browser page errors occurred. Used the isolated inspection fixture and intercepted pipeline writes; server stopped afterward.
- Modified Python AST parsing, `node --check zet/web/static/local_asset_pipeline.js`, and `git diff --check` passed; final diff reviewed.
- Updated LOCAL_CHARACTERS and CODE_MAP. No serialized format change, new maintained scenarios, dependencies, live model calls or production deployment. Existing compatibility rank/reanalyze API routes remain; dashboard reevaluation bypasses legacy adapter review preparation entirely.
