# On-demand Luna review
Status: complete

## Goal
Restore on-demand mixed-quality Luna reviews and ranking on Character Asset Collections and Narrative Scenes. Keep physical slots fixed, show ranks and full review text, expose review criteria, and stale results only when a new image is successfully generated.

## Luna-sized implementation packets
### WP1 — Shared structured review contract
- Dependencies: none.
- Files/interfaces: `zet/services/local_image_ranking_service.py`, `zet/services/candidate_review_contract.py`, new shared board review service.
- Work: submit the exact displayed prompt through the `image_ranking` role, validate all candidate IDs and full reviews, retain successful result and prior result on failed rerun, serialize active attempt/status and prompt.
- Acceptance: exact prompt is retained with successful result and full per-image review and stable rank order.
- Validation: disposable prepared responses for one/multiple candidates, malformed response, duplicate submission, and restart recovery.
- Status: implemented. The shared invocation uses the existing AI_Proxy role and validates full review entries.

### WP2 — Character Asset Collection integration
- Dependencies: WP1.
- Files/interfaces: `character_asset_container_service.py`, `character_asset_container_router.py`.
- Work: on-demand view review using captured ordered render inputs and prior pipeline-specific criteria; exclude same-view selected Draft baseline and retain eligible Assembly FRONT comparison.
- Acceptance: mixed Draft/Final view ranking does not alter slots, selection, or locks.
- Validation: prepared disposable service/API checks for evidence order and board invariants.
- Status: implemented. Synchronous action persists active/result state, review prompt and candidate hashes.

### WP3 — Narrative Scenes integration
- Dependencies: WP1.
- Files/interfaces: `narrative_generation_service.py`, `narrative_router.py`.
- Work: on-demand target review for backdrop, subscene, and final assembly artwork using saved prompt and captured references.
- Acceptance: result persists with target and image identities across reload.
- Validation: prepared disposable responses across all target kinds.
- Status: implemented. Narrative target stores reviews and prompt with target candidates.

### WP4 — Freshness and fencing
- Dependencies: WP2, WP3.
- Files/interfaces: both board services and image completion paths.
- Work: mark saved results obsolete only when a newly generated image lands; fence late results by board, attempt, and submitted image identities. Retain obsolete review and prompt for existing images.
- Acceptance: failed/queued renders and non-generation board actions do not stale results; late responses cannot attach to changed images.
- Validation: disposable state-transition checks.
- Status: implemented for successful image placement, candidate/image identity fencing, duplicate submission, and re-request after a process restart. The prior successful result stays visible if a rerun fails.

### WP5 — Shared UI and owning documentation
- Dependencies: WP2–WP4.
- Files/interfaces: `candidate_board.js`, both workspace controllers/templates, component docs and code map.
- Work: add toolbar action and adjacent criteria disclosure, rank badges, review-pane text, status feedback and active-work polling. Preserve slot order and review context.
- Acceptance: works in both boards; criteria disclosure is inert and displays the exact submitted prompt and timestamp for saved/obsolete results.
- Validation: `npm run test:e2e`, prepared-response browser checks, `git diff --check`.
- Status: implemented. Criteria, rank badges and review text are shown in both workspaces. The approved fast E2E suite passed 4/4. Disposable prepared-response browser checks passed for Character and Narrative, including saved assessments/prompts, unchanged board order, and Narrative reload persistence.

## Constraints
Preserve existing user changes. Use AI_Proxy and existing image ranking role. Do not add maintained test scenarios or dependencies. Legacy separate Draft/Final ranking records remain historical.

## Final results
Both workspaces run on-demand mixed-quality ranking using background workers. Reviews and exact submitted prompts persist, stale after successful image generation, and late results are fenced by active review identity and candidate image hashes. Python compilation, JavaScript syntax checks, `git diff --check`, the approved four-scenario E2E suite, and disposable prepared-response checks for both workspaces passed. Temporary disposable specs/configuration were removed. Restart recovery is supported by allowing a new request to replace an orphaned RUNNING attempt while retaining the previous saved result.
