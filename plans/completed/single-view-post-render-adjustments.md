# Single-view Post Render Adjustments
Status: complete
Related specification: [post-render implementation](../completed/post-render-character-prompt-improvement.md)

## Goal
Enter post-render Character.md improvement from an individual rendered view and show only that view's cards and observations. Suggestions may change any valid Character.md text; two private trial renders evaluate the chosen view. Display source changes in the established side-by-side template diff.

## Current behavior
`local_asset_pipeline.js` has one batch-level entry. `LocalPostRenderPromptService.open` freezes all rendered views, analysis binds findings to evidence views, and trial renders all cited views. The dedicated page renders a single-column text diff. `local_template_improvement.js` owns the established side-by-side diff markup.

## Impact analysis
The dashboard entry, dedicated page, batch-scoped session record and `state.json` resume pointer change. The service continues to own source validation, AI calls, render inputs and promotion. Local Characters and Data Model documentation own user flow and persisted session details.

## Invariants and constraints
Keep Character.md-only validation, frozen inputs, private trials, two fresh seeds, conflict-checked keep, and cancel fencing. Preserve existing sessions and unrelated workspace edits. No permanent scenario or live model run is authorized.

## Implementation steps
### WP1 — View entry and session scope
- Dependencies: none.
- Files/interfaces: `local_asset_pipeline.js`, `index.html`, `local_post_render_prompt_service.py`.
- Work: put a Post Render Adjustments button on each rendered view; create/resume one session per view; bind evidence, observations and private trial renders to that view without narrowing legal Character.md edits.
- Acceptance: entering one view shows and trials only that view; another view has a separate session; findings can edit any valid template location.
- Validation: disposable isolated service check and browser inspection.
- Status: complete.

### WP2 — Side-by-side diff and documentation
- Dependencies: WP1.
- Files/interfaces: dedicated page JS/HTML/CSS and affected Docs.
- Work: reuse prompt improvement diff table structure, update labels and documentation.
- Acceptance: aligned Master/Proposed columns with change highlighting, responsive page, current batch return.
- Validation: JavaScript/Python syntax, focused browser check, approved E2E baseline, `git diff --check` and diff review.
- Status: complete.

## Risks and alternatives
Older multi-view sessions retain their frozen inputs and remain readable; new per-view entry creates separate sessions. Trials of global Character.md edits cover the chosen view only, so other views require their own visual review if desired.

## Progress and decisions
- The requested single-view scope applies to cards, observations and trial renders, while suggestion text may target any valid Character.md location.
- Fixed a selected-view shadowing error found in a disposable two-view fixture. Per-view batch pointers retain separate resumable sessions. Existing multi-view session records remain readable.
- A selected finding now updates aligned master/proposed diff rows before the trial starts.
- Finding view citations accept all eight supported orientations, including views not rendered in the current batch; the chosen view still owns the trial.

## Final results
Added a Post Render Adjustments button to each rendered pipeline view and removed the batch-level entry. New sessions collect one view's evidence and observations; selected Character.md changes can cite another view, while two private trial attempts target the chosen view. The page shows the existing side-by-side source diff pattern.

Validation: a disposable service check covered fresh per-view sessions, resume, cross-view cited edits, diff data and two selected-view attempts (compilation and render submission stubbed); actual browser navigation showed one view card, both diff columns, no page errors or horizontal overflow at 1280px and 390px. `npm.cmd run test:e2e` passed all four scenarios (38.1s). Python AST, both JavaScript syntax checks and `git diff --check` passed. A separate mocked analysis call did not complete and was interrupted; no model response or render quality was verified.
