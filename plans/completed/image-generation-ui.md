# Image Generation UI improvements
Status: complete
Related issue/specification: none

## Goal
Make Image Generation compact and clear, surface aspect ratio across Candidate Board subscribers, and give reconstruction an asset-scoped subpage.

## Current behavior
Image Generation places generation mode, aspect ratio, style, and reference management in board settings. Reconstruction fields are disclosures below the board. The Candidate Board renders all settings in a disclosure.

## Desired behavior
Aspect ratio is visible beside board render actions in all subscribers. Image Generation owns its generation mode, universe style, and references. Reconstruction has a dedicated route view that retains the same asset and board.

## Impact analysis
Shared board component/CSS, four board adapters, Image Generation controller/template, dashboard route preservation, and Candidate Board/Dashboard UI docs.

## Invariants and constraints
Preserve asset revision saves, ordered references, frozen retries, selected candidates, reconstruction provenance, Narrative inherited scene sizing, and shared component neutrality.

## Implementation steps
### WP1 — Shared aspect ratio
- Dependencies: none.
- Files/interfaces: candidate_board_component.js, candidate_board.css, all four subscriber adapters.
- Work: add an always-visible ratio control, optionally read-only with explanatory text; migrate subscribers to it.
- Acceptance: editable ratios remain workflow-owned; Narrative inherited sizing is clear.
- Validation: JavaScript syntax and subscriber source review.
- Status: complete.
### WP2 — Image Generation setup
- Dependencies: WP1.
- Files/interfaces: image_generation.js, index.html, zet.css.
- Work: move mode, style, and references outside shared board controls; compact prompt fields and reference list.
- Acceptance: controls are clear, compact, and locally acknowledge saves and style insertion.
- Validation: JavaScript syntax and DOM/CSS inspection.
- Status: complete.
### WP3 — Reconstruction subpage
- Dependencies: WP2.
- Files/interfaces: image_generation.js, index.html, zet.js.
- Work: add asset-scoped route state and a reconstruction view with source, analysis, prompt application, board render, and compare/correct actions.
- Acceptance: navigation/reload retains asset and inputs; applying a prompt never implies a render started.
- Validation: route/controller inspection and JavaScript syntax.
- Status: complete.
### WP4 — Documentation and review
- Dependencies: WP1-WP3.
- Files/interfaces: Candidate Board specification/integration guide, Dashboard UI documentation, this plan.
- Work: record shared contract, subscriber behavior, completion and validation.
- Acceptance: docs match implementation and diff is scoped.
- Validation: git diff --check.
- Status: complete.

## Validation
`node --check` passed for all six changed JavaScript modules. `git diff --check` passed. The approved `npm.cmd run test:e2e` baseline passed all 4 scenarios (42.4s). An isolated browser fixture verified generation setup, prompt sizing, collapsed negative prompt, visible aspect ratio, eight-slot board, and the asset-scoped reconstruction view. No live model calls or normal-library edits.

## Risks and alternatives
Read-only Narrative target ratios direct operators to the scene settings editor.

## Progress and decisions
Joe selected an asset subpage for reconstruction.

## Final results
Moved aspect ratio into shared board presentation, migrated Character/Minor/Narrative/Image Generation subscribers, added Image Generation page setup and an asset-scoped reconstruction route/view, compacted the prompt editor, and updated owning UI docs. All approved fast scenarios, JavaScript syntax checks, diff checks, and isolated browser inspection passed.
