# 0054 - Narrative prompt freshness follows effective preparation

Status: accepted
Date: 2026-11-24

## Context

Narrative saves editable prompt text separately from target preparation. A prompt
can outlive changes to scene direction, local visual overrides, reference
bindings, backdrop adaptation, style or assembly placement. Render requests
previously accepted any non-empty prompt, with only an assembly-mode check.
Older targets have no prompt-input basis. Narrative prompt freshness is owned by
the saved target and does not require scanning finished image lineage.

## Decision

`narrative_prompt_service.prompt_input_basis` hashes the effective prompt inputs
for a target. Prompt provenance records that digest when an AI result is applied
or when the user explicitly saves/adopts prompt text. Target detail derives
`ready`, `stale`, `unknown` or `missing`; it does not migrate old records as a
read side effect. Render admission requires `ready`. A user can explicitly save
edited or legacy text against current preparation, or use Update Prompt to ask
for fresh AI-authored text.

Prompt jobs capture the basis at submission. A late result whose basis no longer
matches is retained in job history and cannot overwrite the saved prompt or
stage generated images. Candidate retries retain their frozen request. Existing
selection, lock, source, ownership and attempt fences remain authoritative.

## Rationale

The digest covers saved effective inputs rather than editing activity or current
image lineage. Reverting preparation to the same values restores readiness. The
explicit Save Prompt action makes manual prompt adoption clear; Update Prompt
remains separate from rendering. Unknown legacy state requires deliberate review
before a new render, while existing completed candidates remain readable and
protected by their captured production records.

## Alternatives and tradeoffs

- Automatically rewrite or clear prompts when any authoring field changes. This
  would discard editable text and require coordinated invalidation across shared
  scene and element records.
- Treat every prompt without a digest as current. That preserves legacy render
  admission but cannot distinguish changed preparation from unchanged inputs.
- Compare each candidate's full historical source lineage on board reads. This
  adds repeated scans and conflicts with the finished-image source policy.

## Consequences

`prompt_provenance.input_basis` is optional and backward readable. Existing
prompts without it report unknown until saved or updated. Render requests reject
stale and unknown prompts with actionable messages. Prompt basis changes do not
alter already submitted requests, finished images, selection or locks.

## Related code and documentation

- [Narrative prompt basis](../../zet/services/narrative_prompt_service.py)
- [Narrative generation](../../zet/services/narrative_generation_service.py)
- [Narrative target service](../../zet/services/narrative_scene_service.py)
- [Narrative component](../COMPONENTS/NARRATIVE.md)
- [Data model](../DATA_MODEL.md)
- [Implementation packets](../../plans/completed/ui-consolidation/implementation.md)
