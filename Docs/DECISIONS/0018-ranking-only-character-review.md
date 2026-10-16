# 0018 — Ranking-only review for local character pipelines
Status: accepted locally; existing library conversion pending approval
Date: 2026-10-16

## Context

Body-Reference, Head-Image, Character-Assembly and Costume-Dressing used separate
defect verdict jobs before candidates could proceed through ranking and human
review. The gate prompts, saved results, policy controls and test rig added a
second eligibility system alongside Luna ranking and human decisions.

## Decision

Rendered candidates with valid current image bytes are available for human review
and ranking after render harvest. Body-Reference ranking excludes human-rejected
candidates; the other pipelines retain their existing human-review behavior.
Automatic FRONT selection requires a current ranking, the original Luna #1,
current valid image bytes, and no human rejection. Review records use
`review_version: 3`; `library_path_format_version` remains independent.

## Rationale

Joe retired the defect-gate feature and confirmed that Autogenerate should keep
selecting Luna's current #1 FRONT candidate while respecting manual rejection
and image/ranking validity. Ranking supersession and queue attempt fencing still
protect against stale work.

## Alternatives and tradeoffs

No automatic defect verdict remains in these four pipelines. Luna ranking,
human review, observations, prompt improvement, selection and immutable
publication remain available. Existing ranking records are retained as history;
records whose old comparison contract is no longer current are marked stale.

## Consequences

Gate pages, endpoints, prompts, policy settings, evaluation fields and owned
queue handlers are removed. A focused converter inventories and backs up legacy
candidate and rig data before applying its conversion. Existing library and
queue data is not converted until Joe reviews the dry-run inventory and approves
the cutover.

## Related code and documentation

[Local character services](../COMPONENTS/LOCAL_CHARACTERS.md),
[review invariants](../INVARIANTS.md),
[retirement plan](../../plans/active/remove-character-gates.md),
[retirement CLI](../../zet/scripts/retire_local_gates.py).
