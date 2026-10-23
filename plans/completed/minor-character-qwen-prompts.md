# Minor Character Qwen Image 2.1 prompts
Status: complete
Related issue/specification: [Minor Character alignment](../../Docs/DECISIONS/0015-minor-character-alignment.md)

## Goal
Make Minor Character style, view-alignment and true-up prompts explicit for Qwen Image 2.1 while preserving existing stage gates, frozen inputs, reference order, image dimensions and publication behavior.

## Current behavior
`MinorCharacterWorkflow._render_job` assembles the three render paths. Multi-reference style prompts rely on generic appended labels; view prompts use screen-left/right phrasing; true-ups name the edit but do not explicitly identify the sole source image as the canvas. `AdHocImageGenerationService` appends numbered labels by default. S1-S4 do not exercise Minor Character prompting.

## Desired behavior
Ordered style references have explicit Qwen image tags when there are several; view instructions identify the anatomical side visible and keep head/body rotation aligned; true-ups explicitly preserve the source canvas and unaffected design. Prompts remain short for edits and stored with each candidate.

## Impact analysis
`zet/services/minor_character_workflow_service.py` only; rendered request text changes for new candidates. No schema, route, storage version or external service change. Update `Docs/COMPONENTS/LOCAL_CHARACTERS.md` and `Docs/COMPONENTS/PROMPTS.md`; code-map responsibility stays put.

## Invariants and constraints
Reference order/bytes, frozen candidate replay, view gates, original-pixel analysis-only reconstruction, and Inventory locks remain authoritative. No permanent tests or live check without approval.

## Implementation steps
### WP1 — Render prompt assembly
- Dependencies: none.
- Files/interfaces: `minor_character_workflow_service.py` prompt helpers and `_render_job`.
- Work: distinguish source roles, anatomical orientation and scoped true-up edits; preserve reference payload shape and render dimensions.
- Acceptance: sample payloads bind the same references in order, new wording is unambiguous, existing candidate replay still uses saved payloads.
- Validation: disposable isolated prompt assembly check and Python AST parse.
- Status: complete.

### WP2 — Documentation and regression
- Dependencies: WP1.
- Files/interfaces: relevant component docs and this plan.
- Work: document new prompt behavior and observed validation.
- Acceptance: docs match source and final diff has no unrelated changes.
- Validation: `npm.cmd run test:e2e`; `git diff --check`.
- Status: complete.

## Validation
Run isolated prompt checks without live inference or normal-library writes, approved fast E2E regression, syntax and diff checks. Review final diff.

## Risks and alternatives
Prompt changes may affect actual image quality; offline checks establish text/binding correctness only. Keep render settings and user input precedence unchanged.

## Progress and decisions
Official Qwen edit guidance calls for explicit `<imageN>` roles with multiple images and scoped edits with blanket preservation. Existing one-image paths already use Qwen's local edit workflow; no new inference or dependency is needed.
The scoped `render_config` suppresses generic appended reference labels and leaves the existing Qwen default preset selection in place. A disposable assembly harness passed ordered-reference, four side-view and true-up assertions; Python AST parsing passed. The approved four-scenario fast suite passed. Final diff review found only the prompt owner, two affected component docs and this plan.

## Final results
New style prompts state ordered Qwen reference roles and reference framing; alignment uses anatomical-side viewpoint language; true-ups use a scoped edit-canvas instruction. Candidate payloads retain their existing frozen input and replay behavior. `python3 -B test-results/minor-qwen-prompt-check.py`, Python AST parse, `npm.cmd run test:e2e` (4 passed, 43.1s) and `git diff --check` passed. No live inference was run, so image quality and model adherence remain unverified.
