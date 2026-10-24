# 0031 — Prompt Generator Pilot packets and budget boundaries
Status: accepted locally; live artistic evaluation pending fresh authorization
Date: 2026-10-24

## Context

Costume-Dressing and Head-Image Edit had deterministic compilers, frozen render inputs, and separate human review/promotion paths, but no private workflow for an LLM-authored render prompt. The pilot requires distinct baseline/trial comparisons with four seeds, explicit image roles, and measured bounded usage. Existing mutable batch selection and lock state cannot serve as historical provenance for a trial.

## Decision

Create a versioned packet-bound session under each owning batch. Snapshot compiler facts, hashes, prompt-authoring modules, render settings, and mutable image bytes before submission. Resolve versioned template image declarations through explicit selectors and retain separate analysis/render ordering. New facts, criteria, or edit-base strategy create a new packet revision and revoke the old prompt approval.

Keep trial outputs private until Joe accepts an image and separately adopts it into an empty batch slot. Store compact prompt/reference provenance in existing catalog `provenance` during the current receipt-backed lock transaction. Add a universe-scoped pilot ledger for three cases, 36 LLM calls and 48 render submissions, plus a per-case ceiling of 12/16. Require explicit live authorization before either LLM or render submission. Existing AI_Proxy, continuation and catalog publication services remain the execution owners.

## Rationale

Four fixed seeds make within-case variance visible and align baseline/trial comparisons. Packet snapshots preserve what actually informed the prompt and image after mutable selections change. Separate acceptance, adoption, selection, lock and source review prevent one judgment from silently authoring durable source changes. Existing JSON/session and catalog schemas can carry additive records without a catalog migration.

## Alternatives and tradeoffs

Re-resolving references at replay would bind old trials to later selection state, so frozen bytes are retained below each session. Copying references into a global cache would add cross-session lifetime and invalidation rules, so the packet owns its snapshots. Locking or selecting an adopted candidate automatically would bypass existing human review, so adoption stops at an undecided managed candidate. Provider quotas are not exact job prices; the configured Codex reserve remains a preflight gate.

## Consequences

The workflow is opt-in and private until adoption. Packet, request, retry and publication provenance can survive selection/unlock changes and session cleanup of working state through catalog storage. Four seeds improve comparison but do not prove broad reliability. Image quality, prompt-editing savings and success across the three cases remain unverified until the live pilot is separately authorized and reviewed by Joe. Reusable source/template proposals remain separate from accepted images.

## Related code and documentation

[PromptPacket](../../zet/models/prompt_generator.py), [LocalPromptGeneratorService](../../zet/services/local_prompt_generator_service.py), compiler source-map declarations in [Build_Static_Final_Prompt.py](../../Scripts/Build_Static_Final_Prompt.py), [catalog publication](../../zet/services/entity_library_service.py), [Prompt compilation](../COMPONENTS/PROMPTS.md), [Local Characters](../COMPONENTS/LOCAL_CHARACTERS.md), [LLM roles](../COMPONENTS/LLM_ROLES.md), and [active implementation plan](../../plans/active/prompt-generator-pilot.md).
