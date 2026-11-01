# Regen view confirmation
Status: complete

## Goal
Explain prompt and reference handling for Regen view in all five character pipelines and use the primary confirmation color.

## Work packets
- WP1: Update the shared confirmation dialog tone in `zet/web/static/zet.js`; preserve danger as the default. Validate styling and syntax.
- WP2: Describe saved pipeline inputs and prompt handling in `zet/web/static/local_asset_pipeline.js`. Validate representative modes and cancellation using isolated browser checks.
- WP3: Update `Docs/COMPONENTS/LOCAL_CHARACTERS.md`, run the approved fast E2E suite and `git diff --check`, and review the diff.

## Constraints
Preserve generation and source selection behavior, existing user changes, and locked assets. No permanent tests or live renders.

## Results
- Shared confirmation tone and pipeline-specific descriptions implemented; documentation updated.
- `npm.cmd run test:e2e`: four passed. JavaScript syntax and `git diff --check` passed.
- Disposable Chromium check exercised description generation for five pipelines and both prompt choices, and narrow-screen containment. It did not exercise real dialog actions, cancellation, color reset, or submitted requests; no live rendering was performed.
