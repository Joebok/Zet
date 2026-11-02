# Narrative subscene aspect ratio
Status: complete
Related issue/specification: User request in this chat.

## Goal
Replace subscene width and height editing with a saved aspect ratio, initialized from the scene canvas. Keep render quality and calculated output size in Images.

## Current behavior
`narrative.js` edits target dimensions in The moment and holds a separate temporary render ratio in Images. `NarrativeSceneService` seeds target dimensions from the scene canvas; `NarrativeGenerationService` accepts render sizing by ratio. S1/S3 are existing Narrative regressions.

## Desired behavior
The subscene direction card has one aspect ratio control. Its value persists across reloads and drives render sizing. Images shows quality and calculated size.

## Impact analysis
`NarrativeTarget`, `NarrativeSceneService`, and `narrative.js` change. Existing target JSON needs a compatible ratio fallback. Narrative component and data documentation own the saved behavior.

## Invariants and constraints
Preserve existing target dimensions for legacy records and independent backdrop/assembly controls. No permanent tests or live render check without approval.

## Implementation steps
### WP1 — Persist subscene ratio
- Dependencies: none.
- Files/interfaces: Narrative model, repository read, scene service create/update/target.
- Work: seed ratio from scene canvas, validate and resolve edited ratio into target dimensions, derive a legacy display ratio.
- Acceptance: subscene ratio survives reload; legacy dimensions remain unchanged until edited.
- Validation: disposable service check.
- Status: complete.

### WP2 — Move editor control
- Dependencies: WP1.
- Files/interfaces: `zet/web/static/narrative.js`.
- Work: place ratio beside framing for subscenes, remove it from Images, preserve size preview and render quality, bind save and render.
- Acceptance: one ratio control, saved on edit, displayed size updates with quality.
- Validation: syntax check and approved fast E2E.
- Status: complete.

### WP3 — Documentation and diff review
- Dependencies: WP1, WP2.
- Files/interfaces: Narrative and data documentation, plan.
- Acceptance: docs match current behavior and final diff is scoped.
- Validation: `git diff --check`.
- Status: complete.

## Validation
Run focused disposable service validation, JavaScript syntax check, approved fast E2E, and `git diff --check`.

## Risks and alternatives
Legacy target ratios may be inferred from dimensions; the stored dimensions remain authoritative until the user edits the ratio.

## Progress and decisions
Inspected model, service, UI, image sizing and existing testing boundary. Stored
the exact edited ratio on subscenes while retaining their existing width/height
fields for snapshots and consumers. Older targets infer a display ratio without
rewriting their records.

## Final results
Changed model, scene service, subscene editor, Narrative and data documentation.
`node --check zet/web/static/narrative.js` passed. A disposable Python service
check covered scene canvas default, update, reload, and invalid ratio rejection.
`npm run test:e2e` passed all four approved fast scenarios. `git diff --check`
passed. Live rendering was not requested.
