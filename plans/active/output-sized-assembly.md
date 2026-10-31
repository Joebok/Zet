# Output-sized assembly editor
Status: active

## Goal
Keep the placement editor and raw composite aligned to the configured output size, with movable backdrop and black uncovered areas.

## Work packets
- WP1: Add manual backdrop placement to composition and reference prompts; preserve existing presets and snapshots. Validate with disposable composition checks.
- WP2: Update the browser canvas, active layer interaction, dimension refresh and text button order. Validate with an isolated browser.
- WP3: Run the approved fast baseline, syntax and diff checks; update Narrative documentation and archive this plan.

## Constraints
Preserve existing user data, pinned sources, snapshots and generated candidates. No permanent tests, live AI calls or production-library writes.

## Progress and validation

Implemented manual backdrop composition, reference geometry, active-layer editing, dimension updates and text button order. `npm.cmd run test:e2e` passed all four scenarios (42.3s). Disposable temporary-library checks passed output dimensions, black background, manual placement and reference coordinates. JavaScript and Python syntax and `git diff --check` passed. Dedicated browser placement comparison, narrow layout, snapshot/reopen and screenshot inspection remain outstanding.
