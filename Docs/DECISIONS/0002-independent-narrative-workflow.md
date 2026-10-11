# 0002 — Narrative authoring is independent of Scene Builder

Status: current implemented boundary; retrospective.
Record date: 2026-10-11. Historical decision date is unknown.

## Context

Scene Builder constructs scenes from structured JSON, settings, placements and deterministic compilers. Narrative introduces prose-oriented target interviews/synthesis, candidates, source snapshots and assembly. Both serve illustrated scenes and share infrastructure, so a feature name alone cannot select the correct implementation.

## Decision

Narrative uses its own models, repository, services, HTTP router, jobs and image ownership. It does not delegate creation/loading/staging to legacy story/Scene Builder methods. Shared universe/image-library/queue infrastructure remains reusable.

## Rationale

[Narrative approach](../../Docs-Joe/Narrative_Scene_Approach.md) proposes coherent narrative prose with deterministic reference packaging rather than using a constraint compiler to construct the scene description. Current module contracts and [generation test fixtures](../../tests/test_narrative_generation.py) explicitly enforce independent orchestration. That supports the current boundary; it does not establish every original migration rationale.

## Alternatives and tradeoffs

Adapting the existing Scene Builder compiler is an obvious retrospective alternative, but evidence here does not establish a historical alternatives evaluation. Independence keeps authoring semantics and job state separate; it also means new scene features may need separate implementation/tests and no automatic storage interchange should be assumed.

## Consequences

Classify the requested workflow before changing scene code. Add Narrative behavior to its author/generation/reference/assembly services and preserve frozen input and protected-image contracts. Sharing transport helpers does not justify calling `StoryService.stage_scene_render` from Narrative.

## Related code and documentation

[Narrative models](../../zet/models/narrative.py), [repository](../../zet/repositories/narrative_repository.py), [author](../../zet/services/narrative_scene_service.py), [generation](../../zet/services/narrative_generation_service.py), [prompt service](../../zet/services/narrative_prompt_service.py), [Narrative component](../COMPONENTS/NARRATIVE.md), [Scene Builder component](../COMPONENTS/SCENE_BUILDER.md). Tests: [generation](../../tests/test_narrative_generation.py), [phase 2](../../tests/test_narrative_phase2.py), [references](../../tests/test_narrative_references.py).
