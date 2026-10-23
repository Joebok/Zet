# Post-render Character.md improvement
Status: complete
Related specification: approved chat plan (2026-10-23)

## Goal
Offer optional observation-led Character.md improvement after local character renders. Trial two images per affected rendered view without changing batch inputs; explicitly keep or cancel.

## Current behavior
AI Observations start after ranking. Pre-render template review is text-only and activates a batch version at acceptance. Character image refinement has a dedicated page and resumable AI jobs. Assembly currently bypasses template versions.

## Desired behavior
All five character pipelines expose explicit observations and a dedicated, resumable post-render page. Proposals edit Character.md only. Selected edits compile and render in isolation. Keep updates Character.md and batch prompts; cancel leaves only saved observations.

## Impact analysis
Services: local prompt improvement, new post-render session, template revision/overlay, render input and AI continuation. Web: local workflow/router, pipeline and new page. Data: private batch session records; no catalog migration. Docs: Local Characters, Prompts, Data Model, Invariants, LLM Roles, Code Map.

## Invariants and constraints
One agent; preserve unrelated checkout edits. No permanent tests, dependencies or live check. Use AI_Proxy. Preserve universe ownership, ordered references, frozen queued inputs, selections and locked images. Keep trial images outside batch slots.

## Implementation steps
### WP1 — Explicit observations
- Dependencies: none.
- Files/interfaces: local prompt improvement, workflow, pipeline UI.
- Work: remove automatic triggers, decouple Re-evaluate, expose explicit per-view run action.
- Acceptance: ranking and opening Observations do not invoke AI; button does.
- Validation: isolated call check and browser action.
- Status: complete.

### WP2 — Private review sessions
- Dependencies: WP1.
- Files/interfaces: focused session service, AI role/continuation, workflow/router.
- Work: freeze evidence and source, propose selectable Character.md-only edits, persist sessions.
- Acceptance: all five pipelines can start/reload; no batch/template change.
- Validation: isolated fixture with prepared AI result.
- Status: complete.

### WP3 — Trial rendering
- Dependencies: WP2.
- Files/interfaces: session service, compilation/AI render adapters.
- Work: compile selected edits; freeze render inputs; queue two per affected rendered view; collect/retry privately.
- Acceptance: trial results visible and batch gallery/prompts unchanged.
- Validation: prepared render fixture and input hash checks.
- Status: complete.

### WP4 — Keep/cancel and Assembly
- Dependencies: WP3.
- Files/interfaces: session service, template overlay, Assembly compiler, prompt artifacts.
- Work: conflict-checked keep with recovery and recompilation; cancel fences late work.
- Acceptance: only keep changes Character.md and active batch prompts; Assembly honors accepted overlay.
- Validation: conflict/interruption/cancel checks.
- Status: complete.

### WP5 — Page, documentation and checks
- Dependencies: WP1–WP4.
- Files/interfaces: new template/JS/CSS, pipeline link, affected Docs.
- Work: card, observation, suggestion, trial, refinement and exit controls; document contracts.
- Acceptance: page works at desktop/mobile widths and across reload; exact batch return.
- Validation: disposable browser journey, `npm.cmd run test:e2e`, syntax checks, `git diff --check` and final diff review.
- Status: complete.

## Progress and decisions
- User chose all five pipelines, affected rendered views, Character.md plus batch on keep, private trial images, and observations-only persistence on cancel.
- Existing unrelated checkout edits will be preserved.
- Added explicit observation controls on both pages and removed ranking/Re-evaluate submission hooks.
- Session records retain frozen evidence, observation snapshots, source baselines and private trial attempts. A batch-state pointer is read directly for resume across all adapters.
- Disposable fixture checks compiled eight previews and two trial inputs for Body, Head, Head Edit, Assembly and Dressing. Prepared render outcomes completed an Assembly keep; a forced finalization interruption resumed. Costume cancellation preserved Character.md, the active revision and gallery.
- Cancel now removes private evidence, compilation and trial files after fencing the session; a Head Edit cancellation check confirmed removal without a Character.md write.
- Browser check clicked the pipeline entry and loaded the dedicated page at 1280px and 390px, with no page errors or narrow overflow. Live image quality and actual model adherence were not checked.
- Recorded the private trial and recoverable promotion boundary in `Docs/DECISIONS/0030-private-post-render-character-prompt-trials.md`.

## Validation
- `npm.cmd run test:e2e`: four approved scenarios passed (36.9s); a nonfatal fixture storage-maintenance lock warning appeared.
- Python AST checks for changed modules and `node --check` for both changed dashboard scripts passed.
- `git diff --check` passed after whitespace correction; Git emitted line-ending warnings for two existing files.

## Final results
Implemented optional observations, scoped Character.md suggestions, isolated two-render trials, resumption/retry, cancellation and conflict-checked keep for all five character pipelines. Updated affected knowledge; no permanent test, dependency, live model call or normal-library mutation was added.
