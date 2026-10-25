# 0032 — Guided prompt refinement with round authorization
Status: accepted locally; supersedes the workflow and spending policy of [0031](0031-prompt-generator-pilot.md)
Date: 2026-10-24

## Context

The initial pilot supplied frozen inputs and manual prompt trials but omitted AI evaluation and separate approval of suggested directions. Duplicate criteria, blank restored controls and absent action polling made it confusing. Joe requested a guided cycle, machine-written prompts, large desktop image review, uncapped four-image rounds and recoverable run restart.

## Decision

Retain packet preparation, render collection and adoption in `LocalPromptGeneratorService`. `PromptGeneratorCycle` owns the version-2 session, stage/revision checks, round authorization and durable continuations; `PilotAIReview` owns structured evaluation, direction and draft requests. AI execution uses the existing shared AI_Proxy boundary.

Starting the baseline or approving another round authorizes its associated AI work. Four confirmed human reviews gate another round, approved directions gate drafting, and exact draft approval gates rendering. Criteria edits reassess existing images, preserve earlier findings/corrections and require renewed confirmation. Prompts have a read-only viewer; human oversight edits findings and directions rather than prompt text.

Remove pilot budgets, case/round limits, model-tier escalation gates and reserve admission. Keep fixed matched seeds within a run. A batch-local session registry replaces ledger-based discovery; old ledgers are neither consulted nor deleted. Version-1 sessions convert in memory on read and persist version 2 on the first user mutation. Existing images require explicit catch-up evaluation.

Scrapping retains read-only evidence and fences late tasks. Starting over freezes fresh inputs/seeds with copied editable criteria, without dispatch. Adoption, selection and catalog locking remain separate; immutable published provenance is unchanged.

## Rationale and consequences

The pilot now measures automated review and prompt writing while Joe controls each round and corrects findings. Removing caps reflects a manually supervised experiment, not a future autonomous workflow. History supports learning from failed runs. Archived requests may already be executing externally; fencing prevents their results from advancing discarded state but cannot undo execution.

Prepared-response and isolated browser checks establish transitions, persistence and presentation, not live image quality. No new dependency or permanent scenario is introduced. Live evaluation and production deployment remain separate actions.

## Sources

[Local Characters](../COMPONENTS/LOCAL_CHARACTERS.md#prompt-generator-pilot-2026-10-24), [data model](../DATA_MODEL.md#prompt-generator-pilot-records-2026-10-24), [cycle service](../../zet/services/prompt_generator_cycle_service.py), [review contracts](../../zet/services/prompt_generator_review_service.py), and [implementation plan](../../plans/completed/guided-prompt-generator.md).
