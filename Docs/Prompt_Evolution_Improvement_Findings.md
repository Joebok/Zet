# Prompt Evolution Improvement Findings

## Corpus

Reviewed runs `20260809_102411_990248`, `20260809_201219_439863`, and
`20260809_203410_106727`, including their audit records, exact LLM prompts,
responses, batch manifests, scores, mutations, and 56 candidate renders.

## Findings

- All three runs retained their initial prompt. Every automatic refinement batch
  was rejected.
- Category evidence identified useful corrections (black hair, dark leggings,
  the open overskirt, tall boots, and garment colors), but refinement received
  only scores and checklist failure statements.
- The refiner repeatedly changed `black` hair to `dark brown`, even when the
  checklist reported that the render was not black.
- Raw curated metadata expanded refinement requests to about 13 KB and repeated
  unrelated project rules, variant instructions, and an unresolved auxiliary
  token.
- Exact comma-term matching treated a multi-clause costume edit as unmatched,
  converted it to an addition, and duplicated the costume description.
- Other refinements contained no-op edits, vague negatives, or repeated changes
  already identified as ineffective.
- One evaluator response nested `costume_evidence` under
  `character_evidence`; the legacy parser accepted the scores and silently lost
  the costume evidence.
- The original hair checklist marked 12 of 25 visibly non-black renders true
  and 13 false. The false results were false negatives, not evidence that the
  renders had black hair. The newer dedicated checklist marked all 31 visibly
  brown or purple renders as violations.
- The open-toed-boots checklist marked all 31 visibly closed-toe renders false.
  This was correct throughout the reviewed corpus.
- The `0.1` automatic acceptance margin is not an evidence-based noise bound.
  The workflow also exposes only aggregate scoring, not a paired prompt-versus-
  incumbent judgment.

## Replay

The latest incumbent was evaluated three times with a concise structured
feedback prompt. All three responses were identical. The evaluator correctly
identified purple hair, incorrect eye color, garment material, palette, and
footwear differences and returned direct corrections.

Three refinement inputs were compared:

1. The existing score-only input changed black hair to brown and produced
   duplicate/no-op operations.
2. Corrective text preserved black hair but removed the overskirt.
3. Corrective text plus reference and candidate images preserved black hair and
   the overskirt.

The third result was rendered against the incumbent with five identical seeds.
A blinded review preferred the corrective/image-grounded result on three pairs,
preferred the incumbent on one, and found one effectively tied. The revised
palette improved the costume but sometimes bled green into the hair. Production
v2 therefore needs both a strengthened positive hair term and concrete excluded
hair colors when this defect is selected.

A persisted replay experiment repeated the same evaluation three times with a
zero-point score range in every category. It retained both refinement responses:
the corrective-text response passed term validation, while the image-grounded
response was marked invalid because it omitted required operation categories.
An invalid variant no longer invalidates the entire replay experiment.

## Live v2 validation

The updated dashboard and harvester were restarted to remove duplicate stale
processes. Three same-checkpoint references were exercised: Adult canonical
adventure gear, Adult formal gown, and Elder everyday clothing.

- All three produced image-only reusable cores and separate render wrappers.
- Structured category scores and corrections were parsed correctly.
- Refinement prompts were about 1.8 KB rather than about 13 KB.
- Invalid term operations were rejected and retried without changing the core.
- The complete adventure-gear run rendered and evaluated a second batch.
- The two more complex references exhausted refinement validation. Exploration
  stopped safely, preserved the incumbent, and entered blinded finalist review
  rather than adopting an invalid mutation or failing the run.
- The adventure-gear validation finalist was selected and persisted as separate
  core/wrapper artifacts. The formal-gown and Elder runs await human review of
  their preserved incumbents.

## Decision

The replay cleared the prompt-only gate for an image-grounded corrective v2.
Production changes must keep the prompt core separate from the render wrapper,
remove raw metadata from LLM tasks, use structured category corrections, use
stable term IDs, validate mutations, and require a human finalist decision.
