# 0010 — Composite harmonization and explicit subscene transparency
Status: accepted
Date: 2026-10-14

## Context
Finishing restored every original subject pixel after Qwen generation, preventing
subject relighting and retaining extraction remnants. Reference assembly allowed
integration but relied on numeric text for placement. Subscene prompts could ask
for transparency while the deterministic suffix demanded a plain neutral background.

## Decision
Add `harmonize_composite` as a third explicit mode. Freeze the prepared composite
as the only render reference and retain the full dimension-validated result. Keep
finishing as the default and retain its protection behavior. Prompt instructions
preserve layout and identities while allowing visual integration; supporting pair
references and new renderer machinery are outside this change.

Subscenes have a persisted, default-checked transparency checkbox. Interview and
Write Prompt treat it as overriding visible scenery without deleting authored
context. Unchecked uses saved context. Deterministic prompt packaging asks for real
zero-alpha background rather than a painted checkerboard/neutral matte. Manual
Render remains an exact submission of editable text. New text jobs freeze the
preference; mismatched and legacy-absent preferences do not auto-apply results.

## Consequences and alternatives
Full-output harmonization permits relighting but cannot guarantee exact geometry.
Keeping pixel restoration would preserve the original integration failure. Numeric
placement alone already failed to preserve complete groups in observed outputs.
Transparency wording removes contradictory instructions but does not certify image
alpha quality. No creative records, old prompts, images or nested job snapshots are
bulk-migrated. Existing targets read the new default; imported targets copy it.

## Ownership and validation
[Narrative](../COMPONENTS/NARRATIVE.md) owns workflow and result behavior;
[Prompts](../COMPONENTS/PROMPTS.md) owns context and prompt construction;
[Data Model](../DATA_MODEL.md) owns persistence. Disposable isolated checks cover
new contracts, with the existing approved E2E baseline for regressions. Actual
Qwen artistic quality and alpha fidelity require separately requested live work.
