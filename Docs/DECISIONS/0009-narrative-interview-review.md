# 0009 — Review Narrative interview proposals before applying
Status: accepted
Date: 2026-10-13

## Context
The former interview could edit only four moment fields. Shared appearance and visual context
could disagree with them, leaving prompt synthesis to reconcile conflicts and sometimes weaken
important height or equipment directions. Appearance notes are shared across several subscenes.

## Decision
Interview results propose whole-field replacements with conflicts/questions. The user reviews
Old/New and selects Accept/Reject, or Override/Shared/Reject for visual context, then Apply commits
the chosen changes. Defaults favor quick acceptance/target-local override; bulk buttons touch
only rows without an explicit choice. Shared visual application clears this target's override.
Authority stays limited to moment fields, assigned-element appearance and visual context.

## Rationale and alternatives
Direct automatic edits would hide the destination and shared impact. Restricting pose text in
the editor would constrain prose without resolving existing inputs. The selected approach gives
the interview more editing latitude while keeping destination choices visible and fast. It does
not add a separate analysis step, confirmation gate, backup system or live image-inspection model.

## Consequences
Generation stores pending reviews; focused services validate and apply selected server-owned
text under the existing workflow lock. Atomic file writes are retained, not extended into a
multi-file transaction. Retry reapplies the same replacements after a failed write; unrelated
current fields are preserved. Old replies normalize to proposals; old completed history remains.

Prompt generation retains first-mention reference bindings and full reference mappings, with
instructions favoring complete facts over fixed word limits. Candidate freshness is a subtle
comparison of recorded prompt text with the editor, not a persistent version or quality judgment.

## Related code and validation
[Narrative](../COMPONENTS/NARRATIVE.md) owns behavior and interfaces;
[interview contracts](../../zet/services/narrative_interview_service.py),
[scene service](../../zet/services/narrative_scene_service.py),
[generation](../../zet/services/narrative_generation_service.py) and
[presentation](../../zet/web/static/narrative.js) implement it.
S3's approved lifecycle is repaired to Apply proposals before synthesis. Disposable checks cover
review destinations, selection behavior, Group Photo text and image indicators. No live render
quality result is implied.
