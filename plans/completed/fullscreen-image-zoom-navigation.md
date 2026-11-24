# Full-screen image zoom and character navigation
Status: complete

## Goal and verified behavior
Reuse review wheel zoom in the shared full-screen viewer. Character Overview
currently opens individual locked images; scene navigation already exists.
No storage, pipeline, API, or dependency changes are needed.

## Luna sized work packets
### WP1 - Shared viewer interaction
- Files: `zet/web/static/zet.js`, `zet/web/static/zet.css`.
- Dependencies: existing `ZetReviewImageZoom.attach` and scene navigation.
- Work: attach zoom with an artwork-sized viewport; add optional image-list
  navigation, button labels and keyboard handling; reset on image changes/close.
- Acceptance: wheel zoom fits through 4x, controls stay visible, scene navigation
  and right-button cropping retain their existing behavior.
- Validation: JavaScript syntax and disposable isolated browser checks.
- Status: complete.

### WP2 - Character views and documentation
- Files: `character_hub.js`, `index.html`, `Docs/COMPONENTS/DASHBOARD_UI.md`.
- Dependencies: WP1 image-list option.
- Work: pass locked images in each group's existing view order, update asset
  versions and document interaction.
- Acceptance: click opens the chosen view; arrows/buttons move through available
  images in that group, stop at boundaries and reset zoom.
- Validation: existing focused character E2E, disposable browser check,
  `git diff --check`, final diff inspection. No permanent tests added.
- Status: complete.

## Constraints and risks
Preserve existing user edits and publication/image ownership. Full-screen crop
coordinates depend on the image rectangle, so keep the wrapper artwork-sized.
The maintained suite does not directly assert wheel zoom or gallery arrows;
use disposable browser assertions for those interactions.

## Results
Implemented the shared zoom helper and optional per-group image navigation. Updated
the dashboard component documentation and browser asset versions.
Validation: focused character-to-costume and Candidate Board E2E passed 2/2
(23.4s). Disposable Chromium checks passed zoom fit/4x limits, buttons and keys,
boundaries, resets, single-image behavior, crop base dimensions and Character
Overview image order/missing-view filtering. An initial boundary focus failure
was corrected and the disposable check passed. JavaScript syntax and
git diff --check passed. Reviewed the final diff. No permanent tests or live
library changes. The full E2E suite and live AI checks were not run.
