# Character pipeline batch and view pages
Status: active
Related issue/specification: none; requested 2026-11-02

## Goal

Make the five batch-based local character pipelines easier and faster to review by giving each batch one summary page and each of its views a focused page. Apply the same structure to Body-Reference, Head-Image (Construct), Head-Image (Edit), Character-Assembly, and Costume-Dressing, in Draft and Final modes. The batch page retains batch controls, governing prompt improvement, and one selected/locked image card per view. A view page owns that view's candidates, ranking, review, observations, references, selection, and render tools.

Do not wait for completed Final batches or run a preliminary timing study. The implementation is accepted by scoped loading and correct behavior, not a claimed latency target. Minor Characters and Narrative Scenes have separate workflows and are outside this change. No new production dependency, persistent test scenario, migration, or live AI/render check is planned.

## Current behavior

- `zet/web/templates/index.html` has one `#local-pipeline-page` for all five pipeline identities. `zet/web/static/zet.js` mounts it; `zet/web/static/local_asset_pipeline.js` loads a full run, shows selected cards, creates all view galleries (including collapsed views), and polls full detail every 30 seconds while active.
- `LocalImagePipelineWorkflowService.action("detail")` calls `LocalPromptImprovementService.detail` and `_present_run`. The latter adds slot boards, two-mode progress, source previews, per-candidate file/queue checks, reevaluation reasons, and operation contexts. `GET /api/local/{pipeline}/runs/{run_id}` exposes the full result. The browser filters it to one mode after transfer.
- Candidate and selected cards use full image `FileResponse` endpoints, with browser lazy loading. Reference cards also use image endpoints. The existing batch picker calls `list_run_summaries`, so the main expense under review is full run detail and image presentation, not list retrieval.
- The approved S2 E2E scenario checks front Assembly/Dressing API flow and publication. It does not cover populated view navigation or Final page rendering. `Docs/Testing.md` records disposable Draft/Final checks for all five compilers and other focused behavior.

## Desired behavior

1. A pipeline's batch URL retains universe, character, phase, costume when applicable, batch ID, and render mode. It shows prompt improvement, batch actions, clear Draft/Final progress, and selected/locked image cards for every view. Each view card links to its view URL and states selection versus lock independently.
2. A view URL adds one canonical view key. It shows only that view's candidates, eight physical slots, ranking/review, observations, source/reference images, mode/reference settings, and view actions. It provides a clear return to the batch and next/previous view navigation without losing batch or mode context. Existing deep links without a view still open the batch page.
3. The batch page requests a summary projection. The view page requests a view projection for its displayed mode and view. Neither page fetches or serializes full detail for routine load, polling, or action acknowledgement. A view projection may include narrow cross-view prerequisites needed to explain readiness, but no other view's candidate records or image gallery. The backend does not run per-candidate file/queue checks for unopened views during these reads. Existing full detail remains available to existing callers until their dependencies are checked; the new pages do not call it.
4. Cards and reference previews load bounded thumbnail bytes from identity- and content-versioned URLs. Full resolution is requested only when a user opens the review viewer or an explicit full-image action. Missing/changed images fail safely without making a cached thumbnail appear current.
5. Polling is page scoped: batch summary on the batch page; current view detail plus a lightweight batch-status indicator on a view page. Requests stop on navigation or hidden tabs, reject late responses from another batch/mode/view/universe, and preserve unsaved observations, settings, review decisions, focus, and scroll. A mutation refreshes only the affected projections. Current backend fences and validations remain authoritative even when a view page shows only part of the batch.

## Impact analysis

- Backend read models: `zet/services/local_image_workflow_service.py`, `local_prompt_improvement_service.py`, `render_slot_service.py`, the Body/Head/Assembly/Dressing adapters, and a focused projection service. Read from existing spec/state and source/asset services; avoid calling full `_present_run` then discarding fields. Keep mode and costume qualification explicit.
- HTTP: `zet/web/local_character_asset_pipeline_router.py` adds summary, view-detail, and thumbnail reads. Existing mutation routes and full-detail compatibility are retained. Routes remain thin; services own discovery, projection, image selection, and cache behavior.
- Browser: `zet/web/templates/index.html`, `zet/web/static/local_asset_pipeline.js`, `local_template_improvement.js`, `zet.js`, `local_batch_status.js`, and scoped CSS. Update task-context/deep-link capture and any overview or batch-status links that enter a pipeline.
- Image delivery: add a focused service for derived thumbnails using the existing Pillow dependency and a machine-local cache selected through project path/config services. Candidate and reference source resolution must use existing ownership and identity checks; thumbnail cache is derived, never authoritative.
- Documentation owners after implementation: `Docs/COMPONENTS/DASHBOARD_UI.md`, `Docs/COMPONENTS/LOCAL_CHARACTERS.md`, `Docs/CODE_MAP.md`, and `Docs/Testing.md`; `Docs/DATA_MODEL.md` only if an interface or persistent path contract changes. A short ADR is warranted if the summary/view read contract becomes a durable service boundary.

## Invariants and constraints

- Preserve universe isolation, costume qualification, stable slot-to-candidate bindings, ordered image references, Draft/Final separation, queue/operation ownership, selection and lock fencing, and immutable published images (`Docs/INVARIANTS.md`). Changing pages does not weaken cross-view prerequisite checks or server-side mutation validation.
- Do not change candidate storage, renderer inputs, batch transitions, selection/lock semantics, or AI_Proxy behavior. A selected image from one view may still be a prerequisite for another; the view page must show the current dependency state from the service.
- Do not add permanent tests or scenarios without Joe's explicit approval. Use the approved S2 scenario and disposable isolated service/browser checks. No normal library, queue, live model, or live renderer in fast checks.
- Keep unrelated in-progress workspace edits intact. At planning time the worktree has existing modifications, including `local_asset_pipeline.js` and several docs; implementation must inspect the then-current diff before editing.

## Implementation steps

### WP1 — Scoped read contracts
- Dependencies: none.
- Files/interfaces: focused projection service in `zet/services/`; `local_image_workflow_service.py`; `local_character_asset_pipeline_router.py`; consult the four adapters and `render_slot_service.py` for source data.
- Work: define `GET /api/local/{pipeline}/runs/{run_id}/summary?render_mode=...` and `GET /api/local/{pipeline}/runs/{run_id}/views/{view}?render_mode=...`, with costume where required. Load existing authoritative records once per request. Summary returns batch/prompt-improvement state, all-view progress and selected/locked identities; view detail returns one mode/view's candidates, slots, ranking, observations, references, controls, and narrow prerequisites. Exclude other-mode candidate records and unopened-view queue/file checks. Preserve the old full-detail endpoint for dependent callers.
- Acceptance: isolated fixtures for each of five pipelines and both modes return the correct projection; another view's candidate IDs, paths, references, and review text are absent from view detail. Invalid view/mode/costume/universe requests fail through existing ownership rules. A Final view can be represented by a prepared fixture without a completed live batch.
- Validation: disposable isolated HTTP/service checks; `python3 -m compileall -q zet/services zet/web` with the verified Python 3 interpreter.
- Status: pending.

### WP2 — Bounded image delivery
- Dependencies: WP1 identity contract.
- Files/interfaces: focused thumbnail service in `zet/services/`; read endpoints in `local_character_asset_pipeline_router.py`; browser URL helpers in `local_asset_pipeline.js`.
- Work: serve bounded candidate, selected-card, and reference thumbnails from existing verified image paths. Use content identity plus size/format in a machine-local derived cache key; never mutate originals or persist thumbnail paths in batch records. Keep original image endpoints for review/full-size inspection. Cache replacement or missing-source behavior must not display stale bytes.
- Acceptance: batch/view cards request thumbnail routes only; opening review requests the original. Draft and Final with the same slot number cannot collide; another universe/costume/batch/candidate cannot access or reuse the wrong thumbnail. A replaced source gets a new image URL/result.
- Validation: disposable isolated image/HTTP checks with temporary images and a browser network inspection; `git diff --check`.
- Status: pending.

### WP3 — Batch summary page
- Dependencies: WP1–WP2.
- Files/interfaces: `index.html`, `local_asset_pipeline.js`, `local_template_improvement.js`, scoped `zet.css`.
- Work: retain the existing pipeline and batch selectors, batch creation/actions, prompt improvement, progress, and selected/locked cards. Remove view galleries and view-only controls from this page. Use summary projection and thumbnails only. Add per-view links with progress, action-needed, selection, and lock state; preserve Draft/Final switch and costume context.
- Acceptance: the batch page shows all requested views and accurate selection versus lock state with no candidate gallery. Its initial and poll requests do not call full detail or fetch candidate/reference images for unopened views. Prompt-improvement actions still show their existing progress and result.
- Validation: disposable browser checks over prepared Draft/Final summaries for all five pipeline identities; focused S2 `npm.cmd run test:e2e -- --grep "character-to-costume"`.
- Status: pending.

### WP4 — Single-view page
- Dependencies: WP1–WP2.
- Files/interfaces: `index.html`, `local_asset_pipeline.js`, scoped `zet.css`; existing view mutation routes.
- Work: move gallery, candidate review, selection/lock, observations, references, render controls, mode/reference settings, and per-view operations to a view page. Request only the selected view projection. Keep stable physical slots and current ranking display order. Preserve review navigation within the view; any cross-view review navigation becomes explicit page navigation.
- Acceptance: each pipeline opens a valid view directly in Draft or Final; the page cannot show another view's gallery. Select, lock/unlock, review, retry, regenerate, failed-only rerun, Re-evaluate, and source controls retain current server behavior and user feedback. Blocked prerequisites and in-flight operations remain visible without loading other views' candidates.
- Validation: disposable browser checks with isolated fixtures for one populated view per pipeline and both modes, plus empty/failed/queued cases; focused S2.
- Status: pending.

### WP5 — Navigation, polling, and response fencing
- Dependencies: WP3–WP4.
- Files/interfaces: `local_asset_pipeline.js`, `zet.js`, `local_batch_status.js`, task-context integration and any direct pipeline links in `zet/web/static/`.
- Work: encode page kind and view in URLs, preserving batch/mode/costume/universe context across back/forward, deep links, Batch Status, Overview and task capture. Batch polling refreshes only summary; view polling refreshes current view plus a small summary/status projection. Fence overlapping requests by context and cancel/ignore responses after navigation. Audit each page action that currently returns full detail; provide an opt-in compact acknowledgement on those routes while preserving the old response for other callers, then refresh the relevant scoped projection without an all-view rerender.
- Acceptance: navigating between views or modes does not flash stale candidates, apply late responses, overwrite unsaved input, or keep hidden-page polling alive. The network trace for a view never includes other view details/images or a full-detail response, including after actions; the batch trace never includes view detail. Existing links without a view land on the batch page.
- Validation: disposable Chromium navigation/network checks using prepared records; focused S2 and `git diff --check`.
- Status: pending.

### WP6 — Integration and knowledge sync
- Dependencies: WP1–WP5.
- Files/interfaces: affected documentation owners above; this plan.
- Work: exercise all five pipelines with isolated prepared Draft and Final states, including selected/locked and missing prerequisite cases. Inspect request scopes and responsive layout. Run the approved fast E2E baseline, review final diff for unrelated changes, document observed behavior and remaining limits, and archive this plan only after completion.
- Acceptance: no pipeline needs a completed real Final batch for verification; all five routes and both modes use scoped reads and thumbnails. Existing S2 publication still works. Unverified live-scale responsiveness is recorded honestly.
- Validation: `npm.cmd run test:e2e`; `git diff --check`; disposable browser/API checks from prior packets.
- Status: pending.

## Validation

Commands above are planned, not observed. Use `python3` if available, otherwise verify a Python 3 fallback before reuse. The existing S2 E2E scenario is the closest maintained workflow check; it is front-only and primarily API-driven. Disposable fixtures/browser checks cover new page behavior without expanding the permanent suite. Verify network request scope and payload fields rather than imposing an unmeasured latency target. Do not run the optional live Narrative check or a live character renderer for this work.

## Risks and alternatives

- A visual page split alone leaves the existing full-detail computation and response cost. WP1 makes scoped server reads a prerequisite for the new pages.
- Summary accuracy may require checking selected image availability and dependencies across views. Restrict these checks to selected identities and compact progress; candidate-level queue and file checks belong to the opened view. Keep server-side action validation global where invariants require it.
- Some existing mutation routes return full detail. An opt-in compact acknowledgement avoids transferring that payload during a page action without changing responses used by other callers.
- Thumbnail generation adds cache/storage work. Keep it derived and content-versioned so cleanup or a missing source cannot change authoritative images. Use an existing configured machine-local location; do not introduce a new production dependency.
- No completed Final batch is required or available for every pipeline. Prepared isolated Final fixtures verify data isolation and page behavior; real final-resolution responsiveness and artistic review remain unverified until normal use.

## Progress and decisions

- 2026-11-02: Plan created after source/document inspection. Joe chose to skip preliminary measurement and proceed on the expectation that scoped pages, data, images, polling, and checks improve responsiveness. No implementation or runtime validation was performed while planning.

## Final results

Pending implementation and observed validation.
