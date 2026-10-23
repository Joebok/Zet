# 0030 — Private post-render Character.md trials
Status: accepted locally
Date: 2026-10-23

## Context
Rendered local character batches need a way to refine Character.md using image evidence without changing accepted prompts or gallery images during review. Body, Head, Head Edit, Assembly and Dressing share the character template but have separate render inputs and batch state.

## Decision
Use a persistent, batch-scoped review session. Freeze the current batch version, Character.md baseline, submitted prompts, representative images and ordered render references. AI Observations run only on an explicit action. Review suggestions may edit only Character.md and are independently selectable. Compile selected edits and render two private trial images for each affected rendered view with valid reference bindings. Trial attempts never enter batch slots or galleries.

Keep checks the frozen baseline and batch version, writes the reviewed Character.md with a recoverable session status, activates the child batch version and recompiles renderable prompts. Cancel fences pending trial work and removes private files; saved human observations remain. Assembly compilation honors the accepted batch version without introducing a pre-render gate.

## Rationale
The private session lets the operator compare images before changing production prompt state. Frozen inputs make trials reproducible across reload and keep already queued renders independent. A recoverable keep status allows retry after an interruption between the template write and prompt recompilation.

## Alternatives and tradeoffs
Rendering trials into normal batch slots would alter candidate and selection state before acceptance. The private session adds persistent state and cleanup responsibility. Keep can fail on concurrent template or batch edits and requires the operator to restart from current evidence.

## Consequences
The web page presents observations, selectable diffs and private trial results; the focused service owns source validation, compilation, render submission and promotion. No trial image is published by keeping template edits. Actual model adherence and artistic quality require operator review; automated checks cover workflow state and compilation.

## Related code and documentation
[Post-render service](../../zet/services/local_post_render_prompt_service.py), [workflow](../../zet/services/local_image_workflow_service.py), [pipeline router](../../zet/web/local_character_asset_pipeline_router.py), [Local Characters](../COMPONENTS/LOCAL_CHARACTERS.md), [Prompts](../COMPONENTS/PROMPTS.md), [plan](../../plans/completed/post-render-character-prompt-improvement.md).
