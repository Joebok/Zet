# Guided Prompt Generator Pilot
Status: complete (historical); executable workflow retired by [costume adjustments](costume-post-render-adjustments.md) on 2026-10-26
Related specification: user-approved guided cycle; supersedes the workflow and spending policy in [original pilot plan](../active/prompt-generator-pilot.md).

## Goal and desired behavior
Current compiled prompt → four baseline images → AI evaluations → human corrections and optional criteria reassessment → approved next round → proposed directions → direction approval → automated draft → draft approval → four images and evaluations. The operator authorizes each round, with no pilot spending/case/round caps. Prompts are read-only in separate tabs. Desktop review prioritizes a large left-hand image with right-hand review controls. Scrapping archives evidence and fences late work; restarting freezes fresh inputs without dispatch.

## Current behavior and impact
Verified owners: `zet/models/prompt_generator.py`, `LocalPromptGeneratorService`, `LocalImagePipelineWorkflowService`, the local pipeline router, pilot HTML/JS/CSS, LLM roles and durable AI continuations. Existing pilot duplicates identical criterion sets, drops saved values from displayed inputs, excludes baselines from feedback, lacks evaluation/direction stages and does not start polling after actions. Legacy sessions contain valuable images/reviews and must remain readable. Shared queues, immutable packet/reference bindings, universe isolation, exact approvals, and separate adoption/publication remain authoritative.

## Luna-sized implementation packets
1. **WP1 Session lifecycle** — model and session storage; dependencies none. Versioned stages/revisions, registry, legacy conversion, archive/restart; remove budgets. Acceptance: copied legacy data survives and discarded work stays fenced. Validate disposable storage checks. Status: complete; disposable checks passed.
2. **WP2 Round orchestration** — cycle service, existing render continuation and `AIWorkflowService`; depends WP1. Four fixed seeds, durable identity, partial retry, automatic evaluation handoff. Validate prepared renders/replay. Status: complete; disposable checks passed.
3. **WP3 Evaluations/review** — focused review service, contracts and LLM roles; depends WP2. Criterion identities/history, evaluations, separate human corrections, reassessment/confirmation gates. Validate disposable prepared answers. Status: complete; disposable checks passed.
4. **WP4 Directions/drafts** — cycle/draft service; depends WP3. All four results and corrected reviews inform directions; exact approvals gate drafting/rendering; preserve failed responses. Validate prepared full-cycle checks. Status: complete; disposable checks passed.
5. **WP5 API/viewer** — workflow/router and read-only prompt view; depends WP4. Stage actions, optimistic revisions, historical prompt identities, universe checks. Validate disposable route checks. Status: complete; validation recorded below.
6. **WP6 Workspace** — pilot HTML/JS and scoped CSS; depends WP5. Ordered stages, next-action status, autosave, immediate feedback, polling, large images, restart/history. Validate disposable browser at 1440×900, 1920×1080 and narrow width. Status: complete; validation recorded below.
7. **WP7 Integration/knowledge** — batch entry and affected docs; depends WP6. Existing runs resume; archive accessible; update component/roles/jobs/data/invariants/code-map/testing and superseding ADR. Validate syntax, approved `npm.cmd run test:e2e`, final diff and `git diff --check`. Status: complete; validation recorded below.

## Validation boundaries
One implementer, existing dependencies, no permanent tests. Prepared responses and disposable library/queue only; no normal-library writes, live inference, render submissions or production deployment. Verify both pipelines, reload/repeated actions, edited criteria/history, partial failures, stale tabs, late results after scrap, legacy preservation, prompt links and adoption separation. Documentation validation claims must reflect observed checks.

## Progress and decisions
- 2026-10-24: implementation authorized; checkout initially clean. Verified Python 3 via `py -3`. No delegation, dependencies, permanent tests, live inference or production deployment.
- Implemented version-2 sessions with non-writing legacy reads, optimistic revisions, a batch registry, uncapped round authorization and archive/restart. Frozen packet/publication formats remain compatible.
- Added dedicated evaluation/direction contracts and registered durable continuations. Confirmed human conclusions inform all four-output directions and automatic drafts. Draft responses survive failed validation; normalized citations allow protected Image N clauses without weakening genuine omission checks.
- Replaced the workbench with ordered URL-addressable stages, visible next actions, busy/confirmation feedback, saved review restoration, autosave, independent desktop review scrolling and read-only prompt tabs. Isolated visual inspection caught and corrected menu, textarea and footer issues.
- Preserved existing adoption/provenance boundaries, verified source bytes and rechecked empty-slot membership within the existing batch-state transaction.
- Updated component, jobs, roles, prompt, data, invariant, code-map and testing owners. ADR 0032 supersedes the original pilot workflow/budget policy; original plan remains explicitly labeled historical/superseded.

## Validation and final results
- `py -3 -B test-results/guided-pilot/check_cycle.py` passed both supported pipelines through five rounds, criterion reassessment without new images, saved human overrides, direction/draft/image/evaluation failures and selective retry, exact historical prompts, stale revisions, adoption without selection/locking, fresh restart and a deliberately delayed evaluator after archive.
- Read-only legacy verification retained the real Tsaeytte session's four images, scores, notes and failed-draft diagnostic. Its source bytes were unchanged.
- `node test-results/guided-pilot/browser.mjs` passed the full guided baseline/next-round cycle through the actual router and local workflow action boundary, with prepared services and temporary storage. Checked autosave/reload, busy feedback, prompt popup, reassessment/history, draft rejection/regeneration, archive/restart, URL resume and no uncaught browser errors. Inspected 1440×900, 1920×1080 and 390×844 screenshots and asserted width containment and desktop image/review proportions.
- `npm.cmd run test:e2e` passed all four approved fast scenarios in 39.6s using a verified Python 3 interpreter via `ZET_TEST_PYTHON`.
- Changed Python compilation and JavaScript syntax checks passed. Final diff review excludes unrelated changes; `git diff --check` passes with only repository line-ending notices.
- Disposable evidence/scripts are ignored under `test-results/guided-pilot/`; no permanent scenario was added. Actual image quality, live model adherence and production deployment remain unperformed and outside implementation validation. No blocker remains for local implementation.
