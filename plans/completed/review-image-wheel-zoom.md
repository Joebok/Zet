# Cursor-centered zoom for candidate reviews
Status: complete
Related issue/specification: user request, 2026-11-07

## Goal
Add wheel zoom from 1× to 4× to Character Asset Container, Minor Character, Narrative Scene, and Image Generation candidate review dialogs. Keep pointer anchoring and synchronize comparison images. No saved state, endpoints, dependencies, touch gestures, galleries, or standalone comparison tools.

## Current behavior
Four review implementations live in `character_asset_container.js`, `minor_characters.js`, `narrative.js`, and `zet.js`. Character and Narrative use the shared review dialog layout; Minor Characters builds comparison figures; Image Generation has a single result image. Images use `object-fit: contain`.

## Desired behavior
Wheel up zooms toward the pointer; wheel down restores the original fitted size. Visible comparison images share scale and normalized focal position. Wheel input outside artwork and ordinary modified/horizontal scrolling pass through. Navigation to another main image and closing the dialog reset zoom.

## Impact analysis
Add `review_image_zoom.js`, styles in `zet.css`, helper script loading in `index.html`, helper import in Narrative module, integrations in the four review controllers, and brief ownership/behavior updates to Dashboard UI and CODE_MAP documentation. No data or API changes.

## Invariants and constraints
Do not change review decisions, navigation, comparison selection, polling, or image requests. Bound image transforms to clipped viewports so they do not move other controls. Preserve the working tree's preexisting edits.

## Implementation steps
### WP1 — Shared zoom behavior
- Dependencies: none.
- Files/interfaces: `review_image_zoom.js`, `zet.css`, `index.html`.
- Work: add one delegated, dialog-scoped helper with 1×–4× bounds, fitted-artwork pointer mapping, synchronized images, resize handling, and close/reset behavior; load it before classic consumers.
- Acceptance: zoom retains pointer focus, does not change layout, excludes letterbox hit regions, and leaves ordinary wheel scrolling available.
- Validation: `node --check`; disposable Chromium geometry/event check.
- Status: complete.

### WP2 — Character and Minor Character reviews
- Dependencies: WP1.
- Files/interfaces: `character_asset_container.js`, `minor_characters.js`.
- Work: register current review images and reset only when main image changes or dialog closes.
- Acceptance: candidate/comparison wheel input updates every shown comparison, including multiple Character Asset Container comparisons; navigation/reopen resets.
- Validation: disposable Chromium review journeys.
- Status: complete.

### WP3 — Narrative and Image Generation reviews
- Dependencies: WP1.
- Files/interfaces: `narrative.js`, `zet.js`.
- Work: register each current review image and reset when candidate/image changes or dialog closes; ignore unavailable images.
- Acceptance: zoom persists across same-image refresh and Narrative clean-view toggles; review detail scrolling remains usable.
- Validation: disposable Chromium review journeys at desktop and narrow width.
- Status: complete.

### WP4 — Regression and documentation
- Dependencies: WP2, WP3.
- Files/interfaces: `Docs/COMPONENTS/DASHBOARD_UI.md`, `Docs/CODE_MAP.md`.
- Work: document behavior and ownership; execute approved baseline and syntax/diff checks; record exact outcomes and archive this plan.
- Acceptance: all checks pass or failures are recorded, with no unrelated diff.
- Validation: `npm.cmd run test:e2e`, changed-file `node --check`, `git diff --check`.
- Status: complete.

## Validation
Use disposable browser fixtures for wheel anchoring, synchronization, reset, and scroll pass-through; run the four approved fast scenarios. No permanent test added.

## Risks and alternatives
Different aspect ratios have different letterbox areas; shared focal position is measured in normalized artwork coordinates and clamped to the fitted image bounds. Zoom ceiling is 4×.

## Progress and decisions
The shared helper wraps current review images in clipped viewports and uses fitted artwork bounds (excluding letterbox space) for cursor anchoring. Dialog state is transient; main image identity changes and dialog close reset it. Existing unrelated edits in `Docs/GitHub_Task_Workflow.md` and `zet/scripts/deploy_release.py` were preserved.

## Final results
All four approved E2E scenarios passed (`npm.cmd run test:e2e`, 43.3s). Disposable Chromium verified synchronized zoom across different aspect ratios, the 4× ceiling, and reset after dialog close. Changed JavaScript passed `node --check`; `git diff --check` passed. No permanent tests or dependencies were added, and no live AI/render check ran.

Follow-up: at a zoom boundary, wheel input no longer changes the stored focal point. Disposable Chromium confirmed additional upward wheel input at 4× leaves both scale and transform origin unchanged.
