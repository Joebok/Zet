# System contracts

These are supported by implementation and repository instructions, with earlier test evidence retained in Git history. [Testing](Testing.md) owns the current S1–S3 baseline and coverage approval. A scenario verifies only its named assertions; many contracts below require source inspection because dedicated tests were retired. Do not add coverage without explicit approval. See [DEVELOPMENT](DEVELOPMENT.md) for observed results.

## 1. Reusable behavior belongs behind the web layer

- **Rule/why:** [AGENTS](../AGENTS.md) requires reusable workflow logic in services/repositories/models or pipeline scripts, with new dashboard actions exposed through `ZetApp`, `AssetRef`, or a focused service. UI technology must not own business transitions. Retired Streamlit and standalone Render Console receive no new features.
- **Implementation/impact:** [zet/app.py](../zet/app.py), [web routers](../zet/web/), [services](../zet/services/). Existing `RenderConsoleQueue` remains queue support used by the current web app; its presence does not revive the standalone UI.
- **Verify:** Review dependency direction and the service interface. S1/S3 exercise dashboard authoring/job actions; no complete static web/backend boundary check remains.

## 2. A universe owns its library, not the shared queue

- **Rule/why:** bound universe paths, request context, and manifest ownership must agree. Shared queue location does not grant access to another universe's results.
- **Implementation/impact:** [UniverseService.bind_config](../zet/services/universe_service.py), request `ContextVar` in [create_app](../zet/web/app.py), `_ask_belongs_to_run` in [local character service](../zet/services/local_character_asset_pipeline_service.py), ownership checks in [AIAnswerHarvester](../zet/services/ai_answer_harvester.py). Missing ownership is assigned Moonsea only for legacy config.
- **Verify:** All fast scenarios run in the seeded Test universe. They do not test cross-universe switching/foreign-result rejection; inspect request context and owner checks. New coverage needs approval.

## 3. Authoritative images and a derived index are different stores

- **Rule/why:** [EntityLibraryRepository](../zet/repositories/entity_library_repository.py) owns `catalog.sqlite3`; [LibraryIndexRepository](../zet/repositories/library_index_repository.py) owns a rebuildable machine-local cache outside Git/Dropbox. Losing the cache must not imply loss of authored state. Published index generations/freshness, not partial scans, drive indexed queries.
- **Implementation/impact:** [LibraryIndexService](../zet/services/library_index_service.py), entity library, dashboard paging, compilation dependencies, image references.
- **Verify:** Inspect repository schema/root validation and generation publication. S1/S2 use library state incidentally; no dedicated migration, corruption, freshness or paging scenario remains. Read any rebuild/migration command before use.

## 4. Traditional character generation stays retired

- **Rule/why:** the six traditional character pipelines in [pipeline_retirement.py](../zet/services/pipeline_retirement.py) cannot execute through guarded generation/worker paths. Active local workflows reuse compiler functions without restoring old stage-driven generation.
- **Implementation/impact:** `WorkerService.run_current_worker`/`run_named_worker`, guarded app/web actions, local Body/Head/Assembly/Dressing services. Retained assets may still be inspected/reviewed or used by supported consumers.
- **Verify:** Inspect `require_active_pipeline` callers. S2 verifies active local Assembly/Dressing with seeded prerequisites; it does not exhaustively exercise retirement guards.

## 5. Approved local sources are verified snapshots

- **Rule/why:** `locked_assets` requires locked, non-stale records, existing image bytes matching SHA-256, and a valid live batch `spec.json` when `batch_id` is present. Selecting a new candidate does not replace an existing immutable lock. Changing an upstream selection does not silently mutate a locked dependent.
- **Implementation/impact:** [LocalAssetStoreService](../zet/services/local_asset_store_service.py): `locked_assets`, `_batch_exists`, `lock`, `promote_chain`; [LocalAssetSourceService](../zet/services/local_asset_source_service.py); identity/turnaround/phase consumers and catalog publication.
- **Verify:** S2 verifies seeded prerequisites, selection/lock and Assembly-to-Dressing use. Inspect `_batch_exists`, checksum checks and promotion rollback for uncovered cases. Old cutover fixture failures belong to the retired suite, not the maintained baseline.

## 6. Review verdicts and human decisions have explicit meaning

- **Rule/why:** narrow gate verdict `TRUE` means a rejection defect. The shared `parse_rejection_verdict` accepts a single TRUE/FALSE; Assembly/Dressing `_wait_gate` also accepts an optional `: reason`. Preserve the parser contract for the specific pipeline. Rankings must contain every submitted survivor exactly once, with unique IDs/reasons. Human decisions are `keep`, `reject`, or `undecided`; automated approval cannot override human rejection. Manual rank adjustments preserve Luna's original order.
- **Implementation/impact:** [candidate_review_contract.py](../zet/services/candidate_review_contract.py), [local_candidate_review_contract.py](../zet/services/local_candidate_review_contract.py), [local_image_pipeline_policy.py](../zet/services/local_image_pipeline_policy.py); every local candidate gate/ranker.
- **Verify:** S2 applies prepared defect responses and waits for a one-candidate rank before selection/lock. It does not cover multi-candidate ordering, stale evaluation or human-rejection overrides; inspect shared policy/parser code.

## 7. Queue publication and consumption preserve ownership and readiness

- **Rule/why:** publish a complete hidden staging bundle by atomic rename; consume only ready answers with valid inventory and applicable producer/local routing. Drain shared answers into a verified local copy before removing shared payload. Superseded attempts and durable receipts prevent late/duplicate application.
- **Implementation/impact:** [FileProxyClient](../zet/services/file_proxy_client.py), [AIQueueLifecycleService](../zet/services/ai_queue_lifecycle_service.py), [workflow_storage.py](../zet/services/workflow_storage.py), [AIAnswerHarvester](../zet/services/ai_answer_harvester.py), manual publication/submission. Changes affect all AI producers and consumers.
- **Verify:** S2/S3 exercise private prepared answers and result application; S3 includes one render failure/retry. Generic harvester, foreign/missing-route, stale-attempt, copy-failure and duplicate branches are not independently covered. A separately requested live check exercises actual Narrative dispatch, not all these cases.

## 8. Persistence updates preserve revisions and locking

- **Rule/why:** traditional asset batches belong to one character/phase with unique IDs and current revisions; saves increment revisions and preserve unrelated stored keys. Workflow lock files intentionally persist to avoid splitting owners across different inodes; same-thread nested locks are supported. Atomic writes protect individual files, not arbitrary multi-file sequences.
- **Implementation/impact:** [AssetRepository.save_assets](../zet/repositories/asset_repository.py), [json_storage.py](../zet/repositories/json_storage.py), [atomic_file_service.py](../zet/services/atomic_file_service.py), [file_lock](../zet/services/workflow_storage.py); all state/review writers. Do not remove lock files as routine cleanup.
- **Verify:** Inspect revision comparison, atomic replacement and lock boundaries when changing writers. S1/S3 verify save/reload/persistence; concurrency, rollback and traditional-asset revision conflicts have no dedicated maintained scenario.

## 9. Reference order, view domains, and schema gates are contracts

- **Rule/why:** prompts, numbered image citations, `image_inputs`, and bundled bytes must share ordering. Render modes/roles and prompt schema are validated centrally. Body/head view conditioning is independent; anatomical left/right differs from screen left/right. Unsupported document/catalog versions fail rather than being guessed.
- **Implementation/impact:** [chatgpt_prompt_contract.py](../zet/services/chatgpt_prompt_contract.py), [PromptTemplateService](../zet/services/prompt_template_service.py), [view_conditioning_service.py](../zet/services/view_conditioning_service.py), [SceneDocumentService](../zet/services/scene_document_service.py), [ImageCatalogRepository](../zet/repositories/image_catalog_repository.py); compilers, queue snapshots, render adapters.
- **Verify:** S2/S3 exercise limited compilation/attachment packaging. View-tag permutations, unsupported schemas and exhaustive ordering validation have no dedicated scenario. Inspect compilers and both producer/consumer; do not sort references after compilation.

## 10. Measured scene geometry controls staging

- **Rule/why:** when measured layout is present, projection facts control screen placement, size, facing, overlap, and ground contact. Contradictory authored spatial clauses are suppressed without stripping anatomical-side descriptions. Group images supply identity/costume/action while parent projection controls final placement. Layout v3 grouping converts coordinates across immediate parent frames while preserving world placement.
- **Implementation/impact:** [scene_spatial_contract.py](../zet/services/scene_spatial_contract.py), [SceneLayoutService](../zet/services/scene_layout_service.py), general/Qwen scene compilers, background framing and browser layout controls.
- **Verify:** No maintained scenario exercises retiring Scene Builder geometry or its compiler. Inspect projection/group conversion and spatial suppression in code; Narrative E2E results are not evidence of these geometry contracts.

## 11. Narrative owns its records and frozen job inputs

- **Rule/why:** Narrative authoring/generation must not call Scene Builder creation/loading/staging. Jobs pin reference bytes and assembly inputs; source changes must not silently alter a submitted job. Selected/locked images require protection checks before deletion. Server-owned layer filenames/metadata cannot be accepted as arbitrary client paths.
- **Implementation/impact:** [NarrativeRepository](../zet/repositories/narrative_repository.py), [NarrativeGenerationService](../zet/services/narrative_generation_service.py), [NarrativeAssemblyService](../zet/services/narrative_assembly_service.py), [NarrativeSceneService](../zet/services/narrative_scene_service.py), router.
- **Verify:** S1/S3 operate exclusively through Narrative UI/API/storage and verify persisted assembly publication/display. Inspect source freezing, layer binding, protected deletion and attempt checks directly; the fast suite does not assert every protection/provenance case.

## 12. Production local renders use supported profiles

- **Rule/why:** [require_qwen_profile](../zet/services/local_render_policy.py) accepts ComfyUI profiles with `model_family=qwen-image-2.1` and registered diffusion models. Historical Stable Matrix files are not production-policy exceptions. AGENTS says ComfyUI normally runs through AI Proxy; direct operation requires asking for ComfyUI Desktop.
- **Implementation/impact:** [LocalRenderBackendService](../zet/services/local_render_backend_service.py), queue producers, ConfigService normalization, [Local_Render_Presets.json](../Config/Local_Render_Presets.json).
- **Verify:** Inspect profile validation and producer/backend consumers. Fast tests use prepared images. The separately requested live check verifies configured Narrative final-assembly rendering; skipped or unrequested live checks establish no service/model availability.
