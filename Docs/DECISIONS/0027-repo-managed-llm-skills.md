# 0027 — Repository-managed LLM roles and skill composition
Status: accepted locally
Date: 2026-10-22

## Context
Creative LLM callers use shared AI_Proxy execution but had incomplete Config role cards and helpers combining factual analysis, prompt writing and image review. Joe approved incorporating the Qwen Image 2.1 skill into appropriate existing calls while retaining deterministic compilation and correction composition.

## Decision
Own unchanged imported skill sources and separate Zet adapters in the repository. One backend role registry drives Config and request classification. Compose selected guidance at new text-request publication for both Codex and Ollama, using explicit downstream render intent rather than analysis attachments. Freeze effective instructions and hashes with requests. Preserve task schemas, ordered bindings and operator intent while the skill controls prompt prose and length.

Keep original model settings as inherited defaults and add optional per-role overrides below explicit task/session choices. Separate observations and assessment from prompt-writing responsibilities. Existing published envelopes and continuation identities remain readable and are not migrated.

## Alternatives and tradeoffs
Personal Codex skill files would introduce machine/provider coupling. Installing skills in AI_Proxy would move Zet-specific composition across the service boundary. A universal final rewrite would add latency and change deterministic workflows. The selected approach avoids those changes but adds instruction tokens to applicable existing calls. Prepared-response verification cannot establish live artistic quality.

## Consequences and evidence
Skill updates are reviewed repo changes, affecting new requests only; missing required files block preparation. No provider API changes, dependencies, additional model passes, maintained scenarios or live inference are introduced. [LLM roles](../COMPONENTS/LLM_ROLES.md) owns implementation and validation boundaries; [the completed plan](../../plans/completed/qwen-llm-roles.md) records observed results.
