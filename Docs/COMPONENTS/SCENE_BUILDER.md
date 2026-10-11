# Structured stories and Scene Builder

Scene Builder is the existing structured story-scene workflow. It owns Markdown/settings, V4 scene JSON, target membership, measured layout, deterministic prompt compilation, queue staging, and image review. It is distinct from the independent [Narrative](NARRATIVE.md) workflow.

## Interfaces and inputs/outputs

- [StoryService](../../zet/services/story_service.py): `create_story`, `create_scene`, `load_scene_builder_data`, `save_scene_builder_data`, `save_scene_layout_data`, `compile_scene_prompt`, `stage_scene_render`; [ZetApp](../../zet/app.py) and dashboard call it.
- [SceneDocumentService.normalize](../../zet/services/scene_document_service.py): V4 defaults/field cleanup, scene elements, target normalization, placements and derived depth lanes. Exact fields live in code, not a second hand-maintained schema.
- [SceneRenderTargetService](../../zet/services/scene_render_target_service.py): `main`/background/subscene definitions, projections, target paths, enabled state, dependency freshness; membership/grouping has a maximum element-subscene depth of 3.
- [StoryReferenceService](../../zet/services/story_reference_service.py), [StoryCastService](../../zet/services/story_cast_service.py): resolve available image/character/cast bindings using catalog/entity/local sources.
- [SceneLayoutService](../../zet/services/scene_layout_service.py), [scene_layout_planner.py](../../zet/services/scene_layout_planner.py), [SceneBackgroundService](../../zet/services/scene_background_service.py): measured geometry, target/group coordinate conversion, camera projection, background framing and guide images.
- [StoryRenderService](../../zet/services/story_render_service.py): compilation, artifacts and staging. [SceneImageReviewService](../../zet/services/scene_image_review_service.py) owns candidate/locked-target review; [LocalSceneBatchService](../../zet/services/local_scene_batch_service.py) orchestrates candidate batches; [ScenePromptAnalysisService](../../zet/services/scene_prompt_analysis_service.py) queues/harvests prompt analysis.

Input is a scene document plus story settings, references, optional measured layout, and requested render target. Output is a target-specific prompt/IR/artifact bundle, queue task, and eventually candidate/locked images and metadata. [DATA_MODEL](../DATA_MODEL.md) owns file locations and schema versions.

## Render lifecycle

1. Normalize V4 scene data and resolve references. Validate elements, placements and target membership; disabled subscenes cannot be staged.
2. Derive a target projection and current input/dependency fingerprints. Subscene images can act as references for parent targets; dependency freshness participates in staging and review.
3. Compile IR/general prompt and local variants through [scene_render_compiler.py](../../zet/services/scene_render_compiler.py), [qwen_scene_prompt.py](../../zet/services/qwen_scene_prompt.py), and [shared prompt contracts](PROMPTS.md).
4. `compile_scene_prompt` supports an inspection preview with stale dependencies/incomplete descriptions allowed. `stage_scene_render` is the stricter submission path (unless its explicit stale-dependency option is used), protected by `Scene_Review.lock`. A successful preview does not guarantee staging will succeed.
5. Write IR, prompt variants, validation/diagnostics, source map and dependency manifest. Queue dispatch freezes task inputs; harvesting/review handles candidate promotion and superseded work.

## Geometry and freshness contracts

Typed [SceneLayout3D/ScenePawn/SceneCamera](../../zet/models/scene_layout.py) records use meters internally; character source measurements are parsed/formatted with [imperial_units.py](../../zet/services/imperial_units.py). Layout version 3 uses immediate-parent coordinate frames for grouped elements. Changing membership must preserve composed world placement before normalizing targets.

Measured camera projection controls screen position/scale/facing/ground contact. Group references carry identity/costume/action; their original camera/framing does not override parent projection. [scene_spatial_contract.py](../../zet/services/scene_spatial_contract.py) owns shared wording/suppression, background crop extensions and join rules. Details and verification targets are in [INVARIANTS](../INVARIANTS.md).

## Failure modes and extension points

Unsupported scene versions, bad slugs/membership, missing references, incomplete descriptions, disabled targets, stale accepted inputs, invalid geometry, and changed prompt dependencies can block staging. Saved layout migrations may request human review; do not silently clear those flags. Imported candidates pass through [SceneCandidateImportService](../../zet/services/scene_candidate_import_service.py), not ad hoc file copies.

For new scene fields update defaults/normalization/validation, projection/IR, prompt consumers and relevant UI together. Add workflow actions behind `StoryService`, a focused scene service, or `ZetApp`. A new scene feature does not automatically apply to Narrative. Zine source selection is another consumer of finished story-scene images.

## Tests and design evidence

[test_story_service.py](../../tests/test_story_service.py), [test_scene_v4_migration.py](../../tests/test_scene_v4_migration.py), [test_scene_layout_service.py](../../tests/test_scene_layout_service.py), [test_scene_ground_layout.py](../../tests/test_scene_ground_layout.py), [test_scene_spatial_contract.py](../../tests/test_scene_spatial_contract.py), [test_scene_render_compiler.py](../../tests/test_scene_render_compiler.py), [test_scene_image_review_service.py](../../tests/test_scene_image_review_service.py), [test_scene_reference_picker.py](../../tests/test_scene_reference_picker.py), [test_local_scene_batches.py](../../tests/test_local_scene_batches.py).

[Scene Compiler](../../Docs-Joe/Scene%20Compiler.md) is preserved design material; verify specific claims against current functions. [ADR 0002](../DECISIONS/0002-independent-narrative-workflow.md) records why agents must distinguish the two systems.
