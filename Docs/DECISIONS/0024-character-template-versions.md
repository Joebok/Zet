# 0024 — Character template versions and explicit view references

The new process in [ADR 0025](0025-character-review-stages-and-refinement.md) supersedes representative-image proposals and ordinary sequencing for newly enrolled batches. Historical records remain readable; overlays and explicit master promotion remain applicable.
Status: accepted locally; artistic quality unverified
Date: 2026-10-17

## Context
Character prompt review exported every candidate and requested replacements outside Zet. It did not provide local versioning, trial compilation or source promotion. Stable render slots already support individual iterations; existing batch runners have fixed front-anchor behavior. Joe requested targeted template changes, representative evidence, view consistency and flexible selected-view conditioning.

## Decision
Keep revisions with their batch. Freeze one representative per included view, observations and complete governing sources; prefer selections over current Luna #1 and require explicit choices for unranked alternatives. Use the existing resumable AI_Proxy boundary. Constrain edits to chosen known source IDs and preserve marker/placeholder contracts.

Compile through context-local text overlays in existing readers, preserving canonical source provenance. Validate visibility/spatial syntax in every orientation and fully compile evidence views. Only READY revisions can activate or promote. Edits create children; source IDs rebind paths in the active universe/release.

Promotion requires explicit confirmation and all-source baseline checks. Retain before/after text and a journal; interrupted multi-file promotion permits explicit retry with already-applied replacements. Later conflicting edits require a new revision. Writes are atomic per file, not across files.

Reference recipes choose defaults, no batch anchor, or a selected image from a different view of this batch. Individual renders copy the current selected bytes and label the actual source angle. Matching prerequisites retain roles/order. Saved asks, Retry and published images remain frozen. Ordinary batch sequencing remains unchanged.

## Rationale and tradeoffs
Representatives limit context and discourage fixing discarded random failures; observations retain broader recurrence evidence. Real compilers validate syntax and attachment contracts. Context-local overlays reuse compilation without leaking trial edits into simultaneous work or masters. Known source IDs constrain replacement authority; view-configuration issues remain read-only recommendations.

Reusing slots avoids a separate render workflow. Custom recipes apply to individual renders; this does not redesign every front-selection/ranking gate. Batch-local evidence supports comparison/audit but retains disk usage; no pruning or destructive history migration is introduced. Prepared answers do not establish artistic quality.

## Related code and validation
- [Revisions](../../zet/services/local_template_revision_service.py), [overlays](../../zet/services/template_source_service.py), [references](../../zet/services/local_view_reference_service.py), [slots](../../zet/services/render_slot_service.py).
- [Local characters](../COMPONENTS/LOCAL_CHARACTERS.md), [prompts](../COMPONENTS/PROMPTS.md), [data](../DATA_MODEL.md).
- [Completed plan](../../plans/completed/character-template-improvement.md). Disposable service/API/browser checks plus existing S1–S4; no new maintained scenario or live artistic claim.
