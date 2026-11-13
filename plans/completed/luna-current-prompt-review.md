# Rank finished images against the current prompt
Status: active
Related issue/specification: none

## Goal
Rank completed images against the current board prompt while retaining each image's original prompt and inputs as its production record.

## Current behavior
`review_images_with_luna` in `zet/services/local_image_ranking_service.py` sends each candidate's saved prompt as its intended result. Character Containers, Narrative, and Minor Characters use this shared service. Legacy automatic rankers use a separate request path.

## Desired behavior
Each review has one current prompt and ordered references. If no current prompt is available, use visual criteria and available evidence. Existing image records and selection/publication behavior stay intact.

## Implementation steps
### WP1 — Shared review request
- Dependencies: none.
- Files/interfaces: `zet/services/local_image_ranking_service.py`.
- Work: accept current prompt and references, omit candidate prompt text, number finished outputs first, and mark historical inputs as evidence.
- Acceptance: captured request has the current prompt once and no candidate's old prompt.
- Validation: disposable request capture.
- Status: complete.

### WP2 — Character Container reviews
- Dependencies: WP1.
- Files/interfaces: `character_asset_container_service.py`, `character_asset_container_router.py`, `character_asset_container.js`.
- Work: compile the current prompt and references once per review using Preview Prompt options. Fall back to visual criteria on missing or uncompileable prompt.
- Acceptance: prompt/master changes affect a rerun over existing images; detail reads do not compile prompts.
- Validation: disposable review request capture.
- Status: complete.

### WP3 — Narrative and Minor Character reviews
- Dependencies: WP1.
- Files/interfaces: `narrative_generation_service.py`, `narrative_scene_service.py`, `minor_character_service.py`.
- Work: use saved current prompts, resolve ordered current evidence, freeze Minor Character review inputs for continuation, and detect prompt edits during review.
- Acceptance: next review follows the latest saved prompt; resumed review uses its captured request.
- Validation: disposable continuation and request captures.
- Status: complete.

### WP4 — Status and knowledge
- Dependencies: WP2, WP3.
- Files/interfaces: review board adapters, `Docs/COMPONENTS/CANDIDATE_BOARD.md`, `Docs/COMPONENTS/NARRATIVE.md`, `Docs/COMPONENTS/LOCAL_CHARACTERS.md`, `Docs/CODE_MAP.md`.
- Work: show submitted criteria and visual-only state, identify previous/outdated rankings, preserve candidate and image fencing, and document behavior.
- Acceptance: rerun replaces advice without changing images, slots, selection, locks, or render records.
- Validation: approved E2E baseline, JavaScript syntax checks, and `git diff --check`.
- Status: complete.

## Invariants and constraints
Keep the AI Proxy boundary, universe isolation, finished-image records, locks, and candidate/image checks. No live model calls or permanent tests are planned.

## Progress and decisions
- 2026-11-13: User selected visual-criteria fallback when the current prompt is blank or cannot be compiled.
- 2026-11-13: Shared request no longer includes candidate prompts. Character Container compiles a current prompt per review with visual-only fallback. Narrative and Minor Character reviews now pass their current saved prompt; Minor Character freezes prompt/reference paths in its persisted review job. Narrative and Minor Character prompt edits obsolete active/completed reviews.
- 2026-11-13: Narrative assembly reviews resolve current source-layer references when using reference assembly mode. Character Container review endpoint accepts Preview Prompt options. Boards show visual-only status, and obsolete reviews are identified as previous reviews. Component and code-map docs updated.
- 2026-11-13: Disposable shared-request capture passed. Python compilation, JavaScript syntax checks, `git diff --check`, and all four approved fast E2E scenarios passed.

## Final results
Current prompts govern new reviews across the shared review workflows. Images retain their original production records. The approved E2E baseline and disposable request capture passed. No live model call was made. Move this plan to `plans/completed/` after final diff review.
