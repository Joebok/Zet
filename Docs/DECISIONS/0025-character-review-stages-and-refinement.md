# 0025 — Character prompt review, staged views and image refinement
Status: accepted
Date: 2026-10-18

## Context
Joe requested prompt/template correction before image generation and a separate selected-image refinement workspace. The existing governing-template proposal required representative images, while ordinary batch sequencing did not use the incremental same-side reference chain.

## Decision
New batches first analyze all eight compiled view prompts and their sources without images. Exact, independently selectable corrections create accepted batch versions; master promotion remains separate. Existing compilers expose a context-local non-renderable preview for future reference roles without weakening actual render validation.

Continue opens FRONT, front quarters, profiles, rear quarters and BACK in order. Selected same-side predecessors condition each next view; matching upstream pipeline resources remain. Existing batches retain legacy sequencing until explicitly enrolled. Reference changes are advisory and do not impose downstream conditions.

Selected images open a dedicated refinement page. Analysis may compare selected views chosen by the operator; targeted edits receive only their working image. Explicit adoption creates a new candidate in the original occupied slot and preserves private original/attempt history and published images. AI work uses existing AI_Proxy job/continuation and image-generation services.

## Rationale and tradeoffs
Text review can correct authored problems before rendering. Keeping image edits independent prevents accidental template changes while improving a selected result. Explicit stage boundaries leave time for optional refinement. Batch-local records and immutable inputs support resumption and replay, at the cost of retaining private snapshots. Preview reference roles describe planned inputs, so final rendering must compile again against actual references. Model findings remain optional advice; prepared checks do not prove artistic quality.

## Related code and documentation
- [Preview](../../zet/services/local_prompt_preview_service.py), [revisions](../../zet/services/local_template_revision_service.py), [progression](../../zet/services/local_character_progression_service.py), [refinement](../../zet/services/local_character_refinement_service.py).
- [Local characters](../COMPONENTS/LOCAL_CHARACTERS.md), [data](../DATA_MODEL.md), [invariants](../INVARIANTS.md), [testing](../Testing.md).
- Supersedes the representative-image proposal and ordinary-sequencing portions of [ADR 0024](0024-character-template-versions.md) for the new process; its overlays, explicit promotion and immutable submitted inputs remain applicable.

- [Completed implementation plan](../../plans/completed/character-prompt-review-and-refinement.md) records packet completion and observed validation.
