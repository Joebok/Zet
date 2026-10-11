# System contracts

These are code/test-backed rules or existing repository instructions, not proposed improvements. Tests listed below are verification targets; a listing does not mean every test currently passes. See [DEVELOPMENT](DEVELOPMENT.md) for observed results.

## 1. Reusable behavior belongs behind the web layer

- **Rule/why:** [AGENTS](../AGENTS.md) requires reusable workflow logic in services/repositories/models or pipeline scripts, with new dashboard actions exposed through `ZetApp`, `AssetRef`, or a focused service. UI technology must not own business transitions. Retired Streamlit and standalone Render Console receive no new features.
- **Implementation/impact:** [zet/app.py](../zet/app.py), [web routers](../zet/web/), [services](../zet/services/). Existing `RenderConsoleQueue` remains queue support used by the current web app; its presence does not revive the standalone UI.
- **Verify:** review the dependency direction and service-level tests for a new action; [test_web_workflow_services.py](../tests/test_web_workflow_services.py) covers extracted workflow behavior. This architectural requirement is not enforced by a complete static boundary test.

## 2. A universe owns its library, not the shared queue

- **Rule/why:** bound universe paths, request context, and manifest ownership must agree. Shared queue location does not grant access to another universe's results.
- **Implementation/impact:** [UniverseService.bind_config](../zet/services/universe_service.py), request `ContextVar` in [create_app](../zet/web/app.py), `_ask_belongs_to_run` in [local character service](../zet/services/local_character_asset_pipeline_service.py), ownership checks in [AIAnswerHarvester](../zet/services/ai_answer_harvester.py). Missing ownership is assigned Moonsea only for legacy config.
- **Verify:** [test_universe_management.py](../tests/test_universe_management.py), [test_universe_lifecycle.py](../tests/test_universe_lifecycle.py), owning workflow queue tests. Review lazy app creation and background consumers if adding a new route/job type.

## 3. Authoritative images and a derived index are different stores

- **Rule/why:** [EntityLibraryRepository](../zet/repositories/entity_library_repository.py) owns `catalog.sqlite3`; [LibraryIndexRepository](../zet/repositories/library_index_repository.py) owns a rebuildable machine-local cache outside Git/Dropbox. Losing the cache must not imply loss of authored state. Published index generations/freshness, not partial scans, drive indexed queries.
- **Implementation/impact:** [LibraryIndexService](../zet/services/library_index_service.py), entity library, dashboard paging, compilation dependencies, image references.
- **Verify:** [test_entity_library_service.py](../tests/test_entity_library_service.py), [test_wp09_library_index.py](../tests/test_wp09_library_index.py), [test_wp10_library_index_reconciliation.py](../tests/test_wp10_library_index_reconciliation.py), [test_wp11_indexed_dashboard.py](../tests/test_wp11_indexed_dashboard.py). Read rebuild/migration commands before use.

## 4. Traditional character generation stays retired

- **Rule/why:** the six traditional character pipelines in [pipeline_retirement.py](../zet/services/pipeline_retirement.py) cannot execute through guarded generation/worker paths. Active local workflows reuse compiler functions without restoring old stage-driven generation.
- **Implementation/impact:** `WorkerService.run_current_worker`/`run_named_worker`, guarded app/web actions, local Body/Head/Assembly/Dressing services. Retained assets may still be inspected/reviewed or used by supported consumers.
- **Verify:** inspect `require_active_pipeline` callers, [test_compound_asset_commands.py](../tests/test_compound_asset_commands.py), [test_web_app.py](../tests/test_web_app.py), [test_head_image_pipeline.py](../tests/test_head_image_pipeline.py). Do not equate file presence with an active workflow.

## 5. Approved local sources are verified snapshots

- **Rule/why:** `locked_assets` requires locked, non-stale records, existing image bytes matching SHA-256, and a valid live batch `spec.json` when `batch_id` is present. Selecting a new candidate does not replace an existing immutable lock. Changing an upstream selection does not silently mutate a locked dependent.
- **Implementation/impact:** [LocalAssetStoreService](../zet/services/local_asset_store_service.py): `locked_assets`, `_batch_exists`, `lock`, `promote_chain`; [LocalAssetSourceService](../zet/services/local_asset_source_service.py); identity/turnaround/phase consumers and catalog publication.
- **Verify:** [test_local_asset_store_service.py](../tests/test_local_asset_store_service.py). [test_character_local_cutover.py](../tests/test_character_local_cutover.py) currently has two fixtures rejected by the live-batch rule; see Development. Check failure rollback as well as successful promotion.

## 6. Review verdicts and human decisions have explicit meaning

- **Rule/why:** narrow gate verdict `TRUE` means a rejection defect; only a single TRUE/FALSE is accepted. Rankings must contain every submitted survivor exactly once, with unique IDs/reasons. Human decisions are `keep`, `reject`, or `undecided`; automated approval cannot override human rejection. Manual rank adjustments preserve Luna's original order.
- **Implementation/impact:** [candidate_review_contract.py](../zet/services/candidate_review_contract.py), [local_candidate_review_contract.py](../zet/services/local_candidate_review_contract.py), [local_image_pipeline_policy.py](../zet/services/local_image_pipeline_policy.py); every local candidate gate/ranker.
- **Verify:** [test_local_candidate_review_contract.py](../tests/test_local_candidate_review_contract.py), [test_local_image_pipeline_policy.py](../tests/test_local_image_pipeline_policy.py), [test_local_image_ranking_service.py](../tests/test_local_image_ranking_service.py). Include stale result/reevaluation cases when changing eligibility.

## 7. Queue publication and consumption preserve ownership and readiness

- **Rule/why:** publish a complete hidden staging bundle by atomic rename; consume only ready answers with valid inventory and applicable producer/local routing. Drain shared answers into a verified local copy before removing shared payload. Superseded attempts and durable receipts prevent late/duplicate application.
- **Implementation/impact:** [FileProxyClient](../zet/services/file_proxy_client.py), [AIQueueLifecycleService](../zet/services/ai_queue_lifecycle_service.py), [workflow_storage.py](../zet/services/workflow_storage.py), [AIAnswerHarvester](../zet/services/ai_answer_harvester.py), manual publication/submission. Changes affect all AI producers and consumers.
- **Verify:** [test_file_proxy_client.py](../tests/test_file_proxy_client.py), [test_ai_queue_lifecycle_service.py](../tests/test_ai_queue_lifecycle_service.py), [test_workflow_reliability.py](../tests/test_workflow_reliability.py), [test_ai_answer_harvester_external.py](../tests/test_ai_answer_harvester_external.py). Include missing route, corrupt/incomplete answer, copy failure, foreign producer, and stale attempt.

## 8. Persistence updates preserve revisions and locking

- **Rule/why:** traditional asset batches belong to one character/phase with unique IDs and current revisions; saves increment revisions and preserve unrelated stored keys. Workflow lock files intentionally persist to avoid splitting owners across different inodes; same-thread nested locks are supported. Atomic writes protect individual files, not arbitrary multi-file sequences.
- **Implementation/impact:** [AssetRepository.save_assets](../zet/repositories/asset_repository.py), [json_storage.py](../zet/repositories/json_storage.py), [atomic_file_service.py](../zet/services/atomic_file_service.py), [file_lock](../zet/services/workflow_storage.py); all state/review writers. Do not remove lock files as routine cleanup.
- **Verify:** [test_repository_json_storage.py](../tests/test_repository_json_storage.py), revision/concurrent writer and rollback cases in [test_workflow_reliability.py](../tests/test_workflow_reliability.py). Review lock boundaries when moving a service call.

## 9. Reference order, view domains, and schema gates are contracts

- **Rule/why:** prompts, numbered image citations, `image_inputs`, and bundled bytes must share ordering. Render modes/roles and prompt schema are validated centrally. Body/head view conditioning is independent; anatomical left/right differs from screen left/right. Unsupported document/catalog versions fail rather than being guessed.
- **Implementation/impact:** [chatgpt_prompt_contract.py](../zet/services/chatgpt_prompt_contract.py), [PromptTemplateService](../zet/services/prompt_template_service.py), [view_conditioning_service.py](../zet/services/view_conditioning_service.py), [SceneDocumentService](../zet/services/scene_document_service.py), [ImageCatalogRepository](../zet/repositories/image_catalog_repository.py); compilers, queue snapshots, render adapters.
- **Verify:** [test_chatgpt_prompt_contract.py](../tests/test_chatgpt_prompt_contract.py), [test_view_conditioning_service.py](../tests/test_view_conditioning_service.py), [test_scene_render_compiler.py](../tests/test_scene_render_compiler.py), [test_wp08_catalog_migration.py](../tests/test_wp08_catalog_migration.py). Do not sort reference inputs after prompt compilation.

## 10. Measured scene geometry controls staging

- **Rule/why:** when measured layout is present, projection facts control screen placement, size, facing, overlap, and ground contact. Contradictory authored spatial clauses are suppressed without stripping anatomical-side descriptions. Group images supply identity/costume/action while parent projection controls final placement. Layout v3 grouping converts coordinates across immediate parent frames while preserving world placement.
- **Implementation/impact:** [scene_spatial_contract.py](../zet/services/scene_spatial_contract.py), [SceneLayoutService](../zet/services/scene_layout_service.py), general/Qwen scene compilers, background framing and browser layout controls.
- **Verify:** [test_scene_spatial_contract.py](../tests/test_scene_spatial_contract.py), [test_scene_layout_service.py](../tests/test_scene_layout_service.py), [test_scene_ground_layout.py](../tests/test_scene_ground_layout.py), [test_scene_render_compiler.py](../tests/test_scene_render_compiler.py), [test_qwen_scene_prompt.py](../tests/test_qwen_scene_prompt.py).

## 11. Narrative owns its records and frozen job inputs

- **Rule/why:** Narrative authoring/generation must not call Scene Builder creation/loading/staging. Jobs pin reference bytes and assembly inputs; source changes must not silently alter a submitted job. Selected/locked images require protection checks before deletion. Server-owned layer filenames/metadata cannot be accepted as arbitrary client paths.
- **Implementation/impact:** [NarrativeRepository](../zet/repositories/narrative_repository.py), [NarrativeGenerationService](../zet/services/narrative_generation_service.py), [NarrativeAssemblyService](../zet/services/narrative_assembly_service.py), [NarrativeSceneService](../zet/services/narrative_scene_service.py), router.
- **Verify:** [test_narrative_generation.py](../tests/test_narrative_generation.py) forbids legacy scene entry points in fixtures; [test_narrative_phase2.py](../tests/test_narrative_phase2.py), [test_narrative_references.py](../tests/test_narrative_references.py), [test_narrative_repository.py](../tests/test_narrative_repository.py) cover storage, freezing, provenance and protection.

## 12. Production local renders use supported profiles

- **Rule/why:** [require_qwen_profile](../zet/services/local_render_policy.py) accepts ComfyUI profiles with `model_family=qwen-image-2.1` and registered diffusion models. Historical Stable Matrix files are not production-policy exceptions. AGENTS says ComfyUI normally runs through AI Proxy; direct operation requires asking for ComfyUI Desktop.
- **Implementation/impact:** [LocalRenderBackendService](../zet/services/local_render_backend_service.py), queue producers, ConfigService normalization, [Local_Render_Presets.json](../Config/Local_Render_Presets.json).
- **Verify:** inspect policy consumers and renderer tests, including [test_comfyui_render_service.py](../tests/test_comfyui_render_service.py). Live workflow/node/model availability requires a separately authorized service check.
