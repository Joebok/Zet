# Costume-Dressing refresh and regeneration
Status: complete
Related issue/specification: User-approved implementation plan in Codex conversation.

## Goal
Make current-master acceptance refresh the visible batch before another render can be submitted, verify prompt provenance before reusing Costume-Dressing prompts, and allow a view regeneration request to cancel the view's outstanding work and wait for confirmed termination. Preserve selected/locked images and work in other views. Correct stale phase qualifiers in batch links.

## Current behavior
- `local_template_improvement.js` accepts current masters, renders its success state, then awaits detail reload. A user can submit Run front while the batch view still carries the previous revision fingerprint.
- `CostumeRenderModeService.prepare` can reuse `prompts/<view>/Final_Image_Prompt.md` without checking its recorded template revision or render mode. It stamps the current revision onto the frozen input even when using an older prompt file.
- `local_asset_pipeline.js` disables Regen view while the run or slot collector is busy. Existing cancel/supersede behavior fences answers but does not stop the active ComfyUI prompt.
- AI_Proxy schedules expensive local work non-preemptively and holds admission until ComfyUI settles. Safe per-job cancellation needs a targeted ownership contract and terminal acknowledgement; never send a global interrupt without proving the prompt belongs to the requested ask.
- The supplied batch ID resolves to Tsaeytte Youth, not Adult. The operation record was BLOCKED with the previous revision fingerprint and submitted no candidate.

## Implementation steps

### WP1 — Atomic current-master acceptance UI
- Dependencies: none.
- Files/interfaces: `zet/web/static/local_template_improvement.js`, `zet/services/local_template_revision_service.py`.
- Work: Detect active-source drift against current masters; confirm once before accepting current masters. Keep batch render controls disabled during acceptance/reload. Refresh detail and operation contexts before reporting success. Retain backend revision fencing for genuine concurrent changes.
- Acceptance: One proceed choice updates the displayed active revision and operation fingerprint before Run front is enabled; cancel performs no write.
- Validation: Disposable browser/service check with an active revision that differs from current masters; no permanent scenario.
- Status: complete.

### WP2 — Costume prompt provenance
- Dependencies: WP1.
- Files/interfaces: `zet/services/costume_render_mode_service.py`, `zet/services/render_slot_service.py`.
- Work: Record the active template revision and render mode with each reusable costume prompt. Reuse only when both match; otherwise compile from the accepted frozen source before freezing a new candidate. Preserve retry's immutable captured input.
- Acceptance: Final FRONT's frozen prompt digest and revision identify the accepted version even when an older prompt artifact exists.
- Validation: Disposable preparation check for matching/mismatching revision and mode; run approved S2.
- Status: complete; S2 passed, provenance guard inspected and syntax-checked.

### WP3 — View-scoped cancel and replace
- Dependencies: WP2.
- Files/interfaces: Zet operation admission/reservation, slot collector, ComfyUI worker/service; AI_Proxy targeted cancellation interface.
- Work: Keep Regen available while active when an unprotected occupied slot exists. Confirm selected mode and protected slots. Under per-batch/view fencing, detach/supersede queued asks and fence late results. For a running ask, send an owner-scoped cancellation request through AI_Proxy, interrupt only its verified ComfyUI prompt, and wait for terminal settlement before preparing replacements. Keep the operation waiting with an actionable reason if cancellation is uncertain; do not overlap renders. Preserve other views and selected/locked assets.
- Acceptance: Repeated Regen clicks deduplicate; selected/locked candidates remain; replacements use fresh candidate IDs/seeds; old results cannot attach; a new render starts only after cancellation acknowledgement.
- Validation: Disposable queued, running, duplicate, protected-slot, unrelated-view, timeout, and ambiguous-settlement checks with isolated fixtures/fake backend. Do not run a live render.
- Status: complete; targeted cancellation smoke check passed with a fake ComfyUI HTTP server.

### WP4 — UI, docs, and completion
- Dependencies: WP1–WP3.
- Files/interfaces: `zet/web/static/local_asset_pipeline.js`; affected Local Characters, Queues, Invariants, Testing and Code Map docs; AI_Proxy file transport/scheduling docs and invariant; ADR if the targeted cancel contract changes the durable execution contract.
- Work: Correct generated links to use the selected run's phase. Present confirmation, cancellation progress, and terminal/uncertain outcomes. Synchronize both repositories' contracts and this plan.
- Acceptance: The Youth batch link remains Youth; final UI states explain whether old work stopped and whether replacements started.
- Validation: Approved `npm run test:e2e`, relevant existing AI_Proxy checks, Python/JavaScript syntax checks, and `git diff --check` in both repositories. No new permanent test scenario.
- Status: complete; docs synchronized, full approved Zet E2E baseline passed.

## Invariants and constraints
- No new dependencies. No live Final render.
- Cancellation is scoped to exact ask IDs and verified prompt ownership. Preserve AI_Proxy's single-attempt handling, backend ownership, and no-overlap guarantee.
- Selected and locked images remain protected; frozen retries stay unchanged.
- Existing S1–S4 remain the approved Zet baseline. AI_Proxy tests remain within its approved baseline; use disposable checks for new cases.

## Progress and decisions
- User confirmed Youth is the intended phase, selected preservation of selected/locked images, and requested waiting for the active render to stop before replacement.
- Investigation found `supersede_task` removes queued asks but leaves running work available. AI_Proxy's general scheduler remains non-preemptive; Zet now uses the existing ComfyUI proxy with a prompt-ID-scoped interrupt for an explicit, owner-verified regeneration request. A generic `/interrupt` call remains unsafe.
- Current-master acceptance waits for refreshed batch detail, costume prompt reuse checks revision/mode provenance, and batch URLs take character and phase from the selected run.
- Implemented ask-local `.zet_cancel.json` signalling. The ComfyUI worker reads it during prompt settlement, selects queued removal or a prompt-ID-scoped interrupt, and waits for history/queue settlement. The operation remains WAITING until the render collector settles the old candidate.
- Verified with a disposable fake ComfyUI HTTP server that only the owned prompt ID is interrupted and history settlement is awaited. The approved four-scenario Zet E2E baseline, Python compilation, JavaScript syntax checks, and `git diff --check` passed. Live ComfyUI cancellation and the browser drift confirmation remain unverified.

## Validation
- `npm run test:e2e`: passed all four approved scenarios, including S2.
- `node --check` on the two changed dashboard scripts: passed.
- `py -3 -m py_compile` on changed Python modules: passed.
- Disposable fake ComfyUI server verified prompt-ID-specific interruption and terminal-history wait.
- `git diff --check`: passed.
- Not run: live ComfyUI cancellation, browser confirmation against a drifted active revision, and cross-process shared-storage cancellation. No live image render was started.

## Final results
Current-master acceptance refreshes detail and operation context before success; Costume-Dressing prompt reuse checks revision and mode; view regeneration now requests view-scoped cancellation and waits for candidate settlement; batch links use the selected run's phase. No permanent tests or dependencies were added.
