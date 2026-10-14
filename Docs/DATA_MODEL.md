# Data, configuration, and ownership

Paths below are relative to the **bound universe root** unless stated otherwise. Definitions in code own exact fields; this document describes relationships and compatibility, not a copy of every schema. [LIBRARY](COMPONENTS/LIBRARY.md) explains service workflows; [INVARIANTS](INVARIANTS.md) explains contracts.

## Persistence map

| Store | Owner and authoritative definition | Lifecycle / compatibility |
| --- | --- | --- |
| `universe.json` | [UniverseService](../zet/services/universe_service.py): descriptor with universe ID, name, canonical art style, layout version | New universes use layout version 1. Legacy Moonsea can resolve to the container root without a descriptor. Selection is project-local `Config/universe-selection.json`, not image data. |
| `catalog.sqlite3` and `images/` | [EntityLibraryRepository](../zet/repositories/entity_library_repository.py), [EntityLibraryService](../zet/services/entity_library_service.py) | Authoritative entity image catalog and ID-addressed blobs. Schema version 3 via `PRAGMA user_version`; initialization rejects newer versions and backs up an older existing database before migration. `assets.preferred_reference_key` selects the displayed active logical reference; empty means use the direct asset tag, and older active keys remain aliases. |
| `ImageCatalog/ImageCatalog.json`, `Records/`, `ReferenceSets/`, `Organization.json` | [ImageCatalogRepository](../zet/repositories/image_catalog_repository.py) | Distinct record-oriented catalog: manifest schema 3, record version 1, organization version 1. A v3 manifest must be complete and its declared layout present. Old/incomplete catalogs require explicit migration; `load` does not silently convert them. |
| `Characters/<character>/<phase>/Character.md`, costume Markdown, expression/appearance definitions | [PathService](../zet/services/path_service.py), [CharacterSourceService](../zet/services/character_source_service.py), [CostumeService](../zet/services/costume_service.py), models under [zet/models](../zet/models/) | Authoring sources. Shared templates/instructions are in repository `Shared_Library/`; generated prompt artifacts are not canonical source replacements. |
| Character-phase `Assets.json`, `Pipelines.json` and identity/turnaround records | [Asset](../zet/models/asset.py), [PipelineDefinition](../zet/models/pipeline.py), [repositories](../zet/repositories/) | Retained traditional pipeline data; numeric asset IDs are scoped by character and phase. Optimistic `revision` guards saves. Local character generation does not use these as its run state. |
| `PipelineCandidates/Character-Pipeline/` | [LocalBodyReferenceService](../zet/services/local_body_reference_service.py), [LocalHeadImageService](../zet/services/local_head_image_service.py), [LocalCharacterAssetPipelineService](../zet/services/local_character_asset_pipeline_service.py) | Durable batch `spec.json`, run state, source snapshots, candidate images, gates, and ranks. Read serializers/mutation helpers in [local_image_pipeline_policy.py](../zet/services/local_image_pipeline_policy.py) before changing state. |
| `_state/LocalAssets/<character>/<phase>/local_assets.json` | [LocalAssetStoreService](../zet/services/local_asset_store_service.py) | Schema version 1 workspace with keyed assets. Separates selected candidate, verified lock, upstream dependencies, entity asset ID, and logical reference. A lock is not merely a boolean flag. |
| `Stories/<story>/` | Preserved legacy source files; [retirement archive](../Archive/scene-builder/README.md) | Original V4 JSON, Markdown, images and optional 3D layouts remain unchanged; no active authoring or normalization. |
| Legacy story pipeline artifacts | Preserved files and [offline source archive](../Archive/scene-builder/README.md) | Historical compiler/review/queue records; retired execution paths do not stage or publish new work. |
| `NarrativeStories/<story-id>/<scene-id>/<target-id>/` | [NarrativeRepository](../zet/repositories/narrative_repository.py), [Narrative models](../zet/models/narrative.py) | `story.json`, `scene.json`, `target.json` plus images/snapshots. Independent of Scene Builder. Target reads fill absent model defaults; no global schema version is declared in these models. |
| Zine documents/outputs | [ZineDocument/ZineRecord](../zet/models/zine.py), [ZineService](../zet/services/zine_service.py), `PathService.zines_path` | Source selections and page/spread layout. Use service validation and slot constants rather than inventing another ordering. |
| Machine-local index `<library-hash>.sqlite3` | [LibraryIndexRepository](../zet/repositories/library_index_repository.py) | **Derived**, schema version 1, default `%LOCALAPPDATA%/Zet/Indexes` (fallback under the user's home). Root rejected inside Git or Dropbox. Published generations, cached parsed sources, dependency fingerprints, work/history summaries; rebuild does not recreate authoritative catalogs. |
| Shared queue + producer-local route/inbox/receipts | [FileProxyClient](../zet/services/file_proxy_client.py), [AIQueueLifecycleService](../zet/services/ai_queue_lifecycle_service.py), [queue_local_state_root](../zet/services/ai_queue_paths.py) | See [QUEUES](COMPONENTS/QUEUES.md). Queue location is shared across universes; routing state is keyed by canonical queue path and producer hostname. |

## Entity image relationships

`Entity` is the depicted subject (including costume as an entity type); `Variant` is an entity-specific life stage, form, state, or version. `Asset` here means an actual catalog image with immutable identifier and file metadata. This is distinct from the numeric traditional `zet.models.asset.Asset` workflow record.

[EntityLibraryRepository.initialize](../zet/repositories/entity_library_repository.py) owns the SQL tables: entities/variants and their aliases/relations; assets and entity assignments; reference sets/members; descriptors; facets/tags; logical and legacy references; usages; provenance. Foreign keys are enabled. Descriptors are purpose-specific text, facets are structured attributes, and tags are flexible labels. Some polymorphic ownership (such as descriptor owner IDs) is enforced at the service layer rather than by an SQL foreign key.

Logical references can bind an image or reference set and survive image replacement. Usage records connect consumers and locations to assets/references; services use them to protect archive/delete and merge operations. A usage with a direct asset ID remains bound to that image even if it also carries a historical logical key; a key-only usage follows the key's current binding. Refresh validates both fields independently, reports missing endpoints, and retains the valid endpoint. Read [EntityLibraryService](../zet/services/entity_library_service.py) for ID construction, allowed values, deduplication, and operation-specific validation instead of treating filenames as identity.

Active image-bound logical references cannot target archived images. Pipeline
reconciliation deactivates references in the same transaction that archives their
assets. To repair an existing mismatch, use the preview-first
[`repair_archived_reference`](../zet/scripts/repair_archived_reference.py) command
with an explicit universe root, key, and expected asset ID; `--apply` makes a
verified catalog backup before changing only the reference status and timestamp.

The asset editor saves image metadata, organization links, its two asset descriptors,
and preferred reference in one PATCH transaction. The asset detail endpoint queries
the selected image directly; pipeline discovery belongs to inventory search and
reconciliation, not a detail read.

## Identifier and reference conventions

| Identifier | Authority / meaning |
| --- | --- |
| Universe ID | Safe folder identifier validated by `UniverseService._safe_id`, including Windows reserved-name restrictions; exact descriptor lookup |
| Traditional asset | `(character, phase, integer asset_id)`; not a global entity image ID |
| Local source key | `LocalAssetStoreService.key(pipeline, view, qualifier)`; view and costume qualification matter |
| Record image catalog | `img_` plus truncated SHA-256 of `source_key`; reference-set filenames use a hashed ID |
| Scene Builder scene/target | Safe story/scene slugs and scoped target IDs; `main` is the full-scene target, subscenes have their own definitions |
| Narrative record ID | `uuid4().hex`; repository accepts exactly 32 lowercase hexadecimal characters for story/scene/target paths |
| Queue job/attempt | Producer-generated IDs in manifests, not directory position; consumers compare ownership and current attempts |
| Prompt image input | Ordered attachment binding with roles and render mode from [chatgpt_prompt_contract.py](../zet/services/chatgpt_prompt_contract.py); order is semantically significant |

Path serialization is mixed: [PathService.resolve_path](../zet/services/path_service.py) accepts absolute paths, legacy `_Lib`, known library-relative roots, and repository-relative paths, with Windows-path remapping. Do not replace resolution with an unconditional `Path.cwd()` join. File Proxy externalizes local absolute routes while snapshotting portable references.

## Configuration and templates

[config.toml](../config.toml) is loaded into frozen [Config](../zet/services/config_service.py). Platform-specific `BaseFoldersByPlatform` overlays base folders; environment/user expansion and relative subfolder resolution belong to `ConfigService`. `UniverseService.bind_config` changes library/character/asset/pipeline roots while retaining the shared queue and repository templates.

Key sections to locate are `BaseFolders`, `BaseFoldersByPlatform`, `AIModels`, `LocalRender`, `ComfyUI`, `Render`, `AIHarvest`, `AIPromptAnalysis`, `PromptCondense`, `Zine`, and `Turnaround`, plus `SceneCandidateSources` tables. Consult the loader for defaults/coercion. `render_backend` selects final dispatch; `local_render_backend`/preset/checkpoint selects local generation. They are not interchangeable. Old saved local profile choices normalize to supported defaults; already-staged job validation still enforces current renderer policy.

`[ComfyUI.QwenImage21]` in `config.toml` is machine-local renderer tuning read by
the ComfyUI adapter: `reference_resize_enabled`, `reference_max_pixels`,
`reference_total_max_pixels`, `cache_device`, and `cache_dtype`. Valid machine
settings override corresponding Qwen preset defaults. Render-job-local
`Qwen_Reference_Inputs/v1/` and `Qwen_Reference_Preparation.json` store prepared
reference PNGs and reproducibility metadata beside the compiled workflow; they are
artifacts rather than Narrative/library source data. Saved pending workflows and
their submission journal remain authoritative across settings changes. See
[PROMPTS](COMPONENTS/PROMPTS.md).

`[GitHub]` configures the shared repository, CLI timeout, machine-local StatePath, usage reserve and trusted reply authors. `[Runtime]` configures role, deployment Root and persistent StatePath. Frozen reports bind request IDs to repository/content hashes in SQLite outside Git/library; screenshot links pin an evidence commit. Runtime releases keep their own config.runtime.toml beside code; mutable universe selection, renderer presets and model caches use explicit persistent state paths. [GitHub task workflow](GitHub_Task_Workflow.md) owns these interfaces. Kanban files are not migrated or deleted implicitly.

Prompt task bundles, templates, section metadata, view text, and aliases are repository `Config/` assets. Shared character/costume Markdown uses compiler section markers and view directives; [PROMPTS](COMPONENTS/PROMPTS.md) owns their processing. Machine-local state and generated artifacts are not templates.

## Change checklist

Locate both writers and readers. Preserve required/default fields and unknown stored fields where repository saves merge them. Check schema gates, ID/reference usages, normalization, snapshots, and generated source maps. Use [Testing](Testing.md) for the approved scenarios; dedicated migration tests were retired, so inspect uncovered format transitions in source rather than claiming baseline coverage. Prefer approved migration tooling for persistent format changes; do not hand-edit or rebuild `catalog.sqlite3` as if it were the discovery index.

Narrative scene metadata may include `legacy_image` (independent catalog binding),
`source_provenance` and `migration` review/source records. Elements bind either a direct
asset or logical `reference_key`; repository reads fill absent scene/element defaults.
`_state/NarrativeMigration/journal.json` owns migration reservations/completion and
backup location; `_state/NarrativeCandidates/state.json` owns passed choices and import
reservations. These stores are universe-scoped. Historical source snapshots are not
editable generation state. `NARRATIVE` tags bind story/scene/target/candidate IDs;
legacy `SCENE`/`SCENE_RENDER` tags are read-only image compatibility.

Narrative interview jobs may include a `review` record built by
[interview_review](../zet/services/narrative_interview_service.py): validated whole-field proposals
with server-bound IDs/old values, conflicts/questions and pending/applied/superseded status.
Applied reviews retain chosen actions. Authored fields change only through the explicit
`NarrativeSceneService.apply_interview` operation. No global Narrative schema version or migration
is introduced; old completed drafts remain readable, and incoming legacy replies normalize to
proposals. UI-only field-purpose metadata is not a new authored scene field. Candidate `prompt`
already records submitted render text; freshness indicators derive from it without stored flags.

## Render slot ownership (2026-10-12)
Character `spec.json` retains initial candidate definitions and initial `slots_by_view`. `state.json` can override slot maps and owns `slot_version=1`, `added_candidates` definitions, mutable `candidates` updates, `detached_candidates`, and persisted supplemental target IDs. New independent slot submissions use `slot_render_ids`, `slot_review_views`, and per-candidate `slot_managed`; older `target_candidate_ids` remain supported for interrupted batch-runner work. Shared merging excludes detached identities from execution/review and active counts. Slots refer to stable candidate IDs, independently of ranking. Existing >8-candidate views remain legacy galleries; compatibility never truncates them. Per-candidate `render_input` freezes prompt text, ordered copied reference paths/hashes and preset for new render attempts.

Image Generation jobs remain under universe `_state/ImageGeneration/<request_id>/job.json`. New jobs use `image_slots_version=1`, child-index image arrays, per-child status/error/seed, and persisted `render_payload` for replay. Historical completion-order jobs retain their original result indices. `_state/ImageGeneration/workspace.json` (version 1) owns eight nullable `{requestId,index}` assignments, `selected_slot` (zero-based or null), and one-time browser import state. A persistent workspace lock serializes allocation; reservations are saved before dispatch. Missing jobs display interruption rather than binding another result. Clear removes board bindings, not historical job files. See [ADR 0007](DECISIONS/0007-stable-render-slots.md).
