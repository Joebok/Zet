# Scene text sizing and live style preview
Status: active
Related issue/specification: user request, 2026-11-02

## Goal
Calibrate scene lettering on a repository-owned 896x1184 draft backdrop, scale all pixel dimensions by square root of actual image pixel count relative to that backdrop, provide a live shared style dialog, and add a shrink-to-fit placement action that preserves current wrapping.

## Current behavior
`scene_text_render_service.py` scales font, padding, outline, and tail by width/1216 and owns inline text wrapping. `/scene-text-style/preview` renders a fixed sample over transparency. Story settings use a modal; Universe Settings embeds controls in the page. Candidate placement uses `NarrativeSceneTextService` and `/scene-text/{operation}`.

## Desired behavior
An editable sample appears over a shared internal test backdrop with minimum fitting bubble geometry. Universe and story style editing share the dialog and controls. Candidate box shrinking preserves its current rendered line breaks and center.

## Impact analysis
Renderer/style preview, `scene_text.js`/CSS, Universe Settings page controls, narrative router/service, and packaged preview image. Update Narrative, Data Model, Code Map and add ADR. No persistent record format change; no permanent test scenario.

## Invariants and constraints
Use the same Pillow metrics for preview, confirmation, and shrink. Keep candidate revision/lock fences and original artwork. Preview backdrop must not depend on a selected universe or library availability. Existing finished images remain immutable.

## Implementation steps
### WP1 — Pixel-area rendering and preview backdrop
- Dependencies: none.
- Files/interfaces: `zet/services/scene_text_render_service.py`, `zet/services/scene_text_style_service.py`, `zet/web/narrative_router.py`, `zet/assets/scene_text_test.png`.
- Work: share layout metrics; scale dimensions by sqrt(actual pixels / preview pixels); validate and render editable preview text snugly on the fixed test backdrop; provide backdrop endpoint.
- Acceptance: equal-area images at different aspect ratios use equal pixel sizing; preview box bounds fit text and padding.
- Validation: disposable Python renderer/API checks.
- Status: complete.

### WP2 — Shared live style dialog
- Dependencies: WP1.
- Files/interfaces: `zet/web/static/scene_text.js`, `scene_text.css`, `zet/web/static/zet.js`, `zet/web/templates/index.html`.
- Work: modal with controls and +/- affordances on left and image plus live overlay on right; preserve story inheritance/reset; universe style saves immediately in modal and is removed from page Save Settings payload.
- Acceptance: all appearance fields update preview; both entry points share layout and save semantics.
- Validation: disposable browser journey.
- Status: complete.

### WP3 — Shrink candidate box
- Dependencies: WP1.
- Files/interfaces: renderer layout helper, `NarrativeSceneTextService`, `narrative_router.py`, `scene_text.js`.
- Work: add read-only shrink operation using same wrap/layout, minimal fitting raster dimensions, normalized result centered and clamped, unchanged tail geometry; report absent/overflow cases.
- Acceptance: shrink preserves current line breaks and preview/save/confirmation behavior.
- Validation: disposable service/browser checks.
- Status: complete.

### WP4 — Knowledge and verification
- Dependencies: WP1-WP3.
- Files/interfaces: Narrative/Data Model/Code Map docs, ADR, this plan.
- Work: document area sizing and shrink; run E2E, syntax checks, diff check; inspect final diff; record results and archive plan.
- Acceptance: docs match implementation and validation limitations are explicit.
- Validation: `npm run test:e2e`, Python compile/syntax, JS syntax, `git diff --check`.
- Status: complete.

## Validation
`npm run test:e2e` passed all 4 scenarios (46.5s). Python compileall, JavaScript syntax checks, `git diff --check`, and disposable equal-area/tight-box renderer checks passed. No live narrative check or permanent tests were run.

## Risks and alternatives
Changing scaling semantics affects future confirmations for existing stored styles; the user accepts regenerating legacy scenes. Actual image pixel count governs scale even when it differs from configured mode target.

## Progress and decisions
- Confirmed backdrop reference resolves to approved 896x1184 (1,060,864 pixel) image. Configured draft/final targets are approximately 1/4 megapixels; scaling is square-root area ratio.
- User chose shared assembly editor scope, actual image sizing, and immediate universe-style save in the dialog.

## Final results
Implemented. The style dialog preview and candidate shrink interaction were source- and syntax-checked, but not exercised in a separate browser journey.

