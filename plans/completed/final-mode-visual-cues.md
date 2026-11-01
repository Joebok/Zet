# Final-mode visual cues
Status: complete

## Goal and current behavior
Make Final mode recognizable while scrolled in all five shared character pipelines,
Minor Characters, Image Generation and Narrative Scenes. Their controllers already
own independent mode state; the shared stylesheet owns the canvas and palette.
No backend, storage, queue, image binding or rendering behavior changes.

## Implementation packets
### WP1 — Shared presentation and character views
- Dependencies: none.
- Files: `zet/web/static/zet.css`, `local_asset_pipeline.js`, `minor_characters.js`.
- Add a shared darker green Final canvas and labeled pill before view headings;
  expose each page's current mode without changing mode selection behavior.
- Acceptance: every pipeline view and Minor Character heading identifies Final;
  Draft and other pages retain their existing background.
- Validation: JavaScript syntax, disposable Chromium presentation check.
- Status: complete.

### WP2 — Generation, Narrative and verification
- Dependencies: WP1 presentation.
- Files: `zet/web/static/zet.js`, `narrative.js`, `zet/web/templates/index.html`,
  `Docs/COMPONENTS/DASHBOARD_UI.md` (presentation owner).
- Reuse cues for result/slot headings and Narrative images. Refresh changed asset
  versions. Keep Narrative's cue scoped to its image workspace.
- Acceptance: mode switching and navigation apply/remove the cue; all slots,
  including empty slots, identify Final.
- Validation: approved `npm.cmd run test:e2e`, syntax, disposable Chromium,
  `git diff --check` and final diff review. No permanent tests or live services.
- Status: complete.

## Impact and constraints
Presentation-only; component/data/invariant/workflow ownership stays unchanged.
No architecture or code-map entry points move. Use existing dependencies and
isolated checks. Browser checks establish styling and scrolled visibility, not
physical-device acceptance.

## Final results
- Shared Final canvas and heading pills implemented in all five character pipelines,
  Minor Characters, Image Generation and Narrative Scenes; asset versions updated.
- Presentation ownership documented in Docs/COMPONENTS/DASHBOARD_UI.md.
- npm.cmd run test:e2e: all four approved scenarios passed (48.7s).
- Changed JavaScript syntax checks and git diff --check passed.
- Disposable Chromium checks passed all four workflow presentations: Final pills,
  scroll beyond 1000px, Draft reset and navigation reset. Scrolled screenshot
  inspected. Prepared markup checked CSS behavior; production/device appearance
  and live AI execution were not exercised. No permanent scenarios added.
- Final diff reviewed; no storage, backend or queue changes.
