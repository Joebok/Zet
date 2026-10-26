# 0033 — Costume modes, persistent targets and private source trials
Status: accepted
Date: 2026-10-26

## Context
Costume-Dressing used predecessor-based batch stages while rotation and no-reference alternatives were separate staging/Pilot paths. Its Post Render Adjustments action edited Character.md. Prompt Generator Pilot optimized compiled prompts rather than durable costume instructions.

## Decision
Use `CostumeRenderModeService` as the common mode/input owner for generation, previews and staging. Preserve FRONT's dressing contract; allow other views independently after governing-prompt acceptance when their mode inputs exist. Explicit references never fall back. Frozen retries retain captured inputs and profiles; publication preserves actual lineage and locked-image protections.

Store visual acceptance criteria and human accomplishment status per costume/view outside batch directories, shared across modes. Use stable IDs and revision-checked writes. Accomplished items remain visible and are excluded from improvement analysis.

Specialize the shared private post-render lifecycle with costume-only source suggestions. Compose existing view tags with optional inline render-mode annotations. Partition replaced prose into disjoint scopes so unchecked contexts retain original text. Favor unselected symmetric mirrors and protect selected other views by default, while allowing explicit scope choices.

Approval binds a cumulative source diff and session revision before four target-view trials. Seeds and profiles remain fixed across rounds. AI assessment is advisory; accomplishment and master promotion are explicit human actions. Preserve source/active-revision conflict checks, private trial isolation, recoverable save and cancellation/attempt fencing. Partial improvements may be saved while unfinished criteria persist.

Retire Pilot execution, pages and authoring adapters from both pipelines. Retain historical records/images, retired role keys for configuration compatibility, and adopted-image provenance readers. Terminalize persisted Pilot and old costume Character.md continuations before dispatch. Other pipelines retain Character.md adjustments.

## Consequences and verification
Mode settings and version-2 costume sessions are additive file records; no catalog migration or dependency is required. Existing batches retain frozen submissions and accepted source overlays. Changed review inputs or master conflicts require a fresh review.

Prepared-response and isolated browser checks verify software behavior, not artistic success. Live inference and deployment are separate actions. See [Local Characters](../COMPONENTS/LOCAL_CHARACTERS.md#costume-dressing-modes-and-adjustments-2026-10-26) and [Testing](../Testing.md).
