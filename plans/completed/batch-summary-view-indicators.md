# Batch summary view indicators
Status: complete
Related issue/specification: user request, 2026-11-03

## Goal

Show an inexpensive per-view attention cue on Draft and Final batch summaries
when a view has no selected or locked candidate. Reuse existing summary data and
active-work refresh; add no reads, queue scans, image checks, or polling.

## Current behavior

`LocalPipelineProjectionService.summary` loads candidate metadata and slot maps
and returns one `selected_cards` item per requested view. Batch cards in
`local_asset_pipeline.js` display selected/locked identities and otherwise say
that no image is selected. Batch reads already refresh during active work.

## Desired behavior

For an unselected/unlocked view, show the count of saved candidate image paths
within its physical slots and whether saved metadata reports queued/running work.
Use these cues: zero images with no active renders; zero images with active
renders; images with active renders; images ready to review with no active
renders. Counts are advisory; view/action checks remain authoritative.

## Luna sized work packets

### WP1 — Project summary indicators
- Dependencies: none.
- Files/interfaces: `zet/services/local_pipeline_projection_service.py`, summary card projection.
- Work: derive image/slot counts and active render state from the loaded mode-specific slot map, candidate metadata, and pending render IDs. Do not inspect image files or external queues.
- Acceptance: Draft and Final values are independent; a normal eight-slot view with one saved image path reports 1/8. Existing selected/locked fields and response scope remain intact.
- Validation: isolated disposable projection fixture across all four indicator states and both modes; Python compilation.
- Status: complete.

### WP2 — Render the attention cue
- Dependencies: WP1.
- Files/interfaces: `zet/web/static/local_asset_pipeline.js`, scoped `zet/web/static/zet.css` only if needed.
- Work: render one concise status line for cards without selected or locked candidates. Preserve current messages for all other cards. Reuse summary load and refresh behavior.
- Acceptance: four states render correctly; batch network traffic remains summary-only and no polling is added.
- Validation: JavaScript syntax check; inspect request path to confirm the cue adds no reads. A dedicated browser network trace is not run.
- Status: complete.

### WP3 — Verify and sync knowledge
- Dependencies: WP1–WP2.
- Files/interfaces: `Docs/COMPONENTS/LOCAL_CHARACTERS.md`, this plan.
- Work: run validation, record observed results/limits, review the diff, and move this plan to `plans/completed/`. Add no permanent test scenario.
- Acceptance: isolated fixture covers four states and Draft/Final separation; approved E2E baseline passes; documentation describes advisory metadata and refresh behavior.
- Validation: `npm.cmd run test:e2e`, Python compilation, JavaScript syntax check, and `git diff --check`.
- Status: complete.

## Invariants and constraints

- Preserve universe and mode scoping, selected/locked card behavior, and action-time image availability checks.
- Image counts use saved paths as metadata only. No per-candidate filesystem check or queue scan is added.
- No new maintained test scenario or dependency.

## Progress and decisions

- 2026-11-03: Confirmed with Joe that indicators use the existing active-work refresh; no additional polling is needed.
- 2026-11-03: Implemented summary metadata and the card cue. An isolated projection fixture passed all four status states and checked Draft/Final separation. `py -3 -m compileall -q zet/services zet/web`, `node --check zet/web/static/local_asset_pipeline.js`, and `git diff --check` passed. `npm.cmd run test:e2e` passed 4/4 (48.6s). Network behavior was verified by code-path inspection: the cue consumes existing summary fields and adds no request; a dedicated browser network trace was not run.

## Final results

Implemented the indicators for unselected/unlocked batch cards across the five
character pipelines and both render modes. Counts use saved image-path metadata;
view/action availability checks remain authoritative. No permanent tests or
runtime polling were added.
