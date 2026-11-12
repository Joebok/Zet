# Shared Candidate Board Draft upscale

Status: complete

The Image Generation adapter mounts the common board but has no upscale handler. Other boards each declare the same action. The [Candidate Board specification](../../Docs/COMPONENTS/CANDIDATE_BOARD.md) and [invariants](../../Docs/INVARIANTS.md) govern presentation and ownership.

## WP1 - Queue and settle Image Generation upscales

- Dependencies: existing Image Generation asset actions and Qwen Draft upscale recipe.
- Files: `image_render_request.py`, `ad_hoc_image_generation_service.py`, `image_generation_workspace_service.py`, `ad_hoc_image_generation_router.py`.
- Reuse the Draft's saved image and shared upscale recipe. Reserve the attempt under the asset lock, retain the Draft and selection until a validated result replaces the same slot, and keep the Draft on failure. Include the pending attempt in deletion fencing and visible progress.
- Acceptance: selected and unselected Drafts upscale in place, stale and Final actions are rejected, and failed or cancelled work cannot replace a Draft.
- Validation: isolated service and route checks with prepared images and proxy results.
- Status: complete.

## WP2 - Offer Upscale Draft in the shared board

- Dependencies: WP1 for Image Generation dispatch.
- Files: `candidate_board_component.js`, active board adapters and their asset URLs.
- Derive the action in one place for a Draft with a saved image. Apply active and lock guards, route to each workflow's existing action handler, and report pending or failed Image Generation attempts on the Draft.
- Acceptance: eligible Drafts offer the same action on cards and in review, and Final images omit it.
- Validation: disposable browser check, approved fast E2E baseline, and `git diff --check`.
- Status: complete.

## Results

- `npm run test:e2e` passed all four approved fast scenarios.
- A disposable Playwright check used the real dashboard and Image Generation
  routes with a private queue and prepared answers. It verified card and
  review actions, selected and unselected Drafts, stale and duplicate action
  rejection, exact captured Draft bytes and aspect ratio, same-slot Final
  replacement, wrong-size rejection with Draft retention, and deletion with a
  late answer. The original multi-image job remained available after cancellation.
- `git diff --check` passed. The Candidate Board contract, subscriber guide,
  code map, and Image Generation storage notes describe the changes.
