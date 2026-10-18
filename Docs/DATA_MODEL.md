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
| `PipelineCandidates/Character-Pipeline/` | [LocalBodyReferenceService](../zet/services/local_body_reference_service.py), [LocalHeadImageService](../zet/services/local_head_image_service.py), [LocalCharacterAssetPipelineService](../zet/services/local_character_asset_pipeline_service.py) | Durable batch `spec.json`, run state, source snapshots, candidate images, human decisions, rankings, and selections. Review records use `review_version: 3`; `library_path_format_version` remains an independent path contract. Read serializers/mutation helpers in [local_image_pipeline_policy.py](../zet/services/local_image_pipeline_policy.py) before changing state. |
| `_state/LocalAssets/<character>/<phase>/local_assets.json` | [LocalAssetStoreService](../zet/services/local_asset_store_service.py) | Schema version 1 workspace with keyed assets. Separates selected candidate, published lock, upstream dependencies, entity asset ID, and logical reference. A usable lock requires its permanent file; batch history and byte verification are not required. |
| `Stories/<story>/` | Preserved legacy source files; [retirement archive](../Archive/scene-builder/README.md) | Original V4 JSON, Markdown, images and optional 3D layouts remain unchanged; no active authoring or normalization. |
| Legacy story pipeline artifacts | Preserved files and [offline source archive](../Archive/scene-builder/README.md) | Historical compiler/review/queue records; retired execution paths do not stage or publish new work. |
| `NarrativeStories/<story-id>/<scene-id>/<target-id>/` | [NarrativeRepository](../zet/repositories/narrative_repository.py), [Narrative models](../zet/models/narrative.py) | `story.json`, `scene.json`, `target.json` plus images/snapshots. Independent of Scene Builder. Target reads fill absent model defaults; no global schema version is declared in these models. |
| Zine documents/outputs | [ZineDocument/ZineRecord](../zet/models/zine.py), [ZineService](../zet/services/zine_service.py), `PathService.zines_path` | Source selections and page/spread layout. Use service validation and slot constants rather than inventing another ordering. |
| Machine-local index `<library-hash>.sqlite3` | [LibraryIndexRepository](../zet/repositories/library_index_repository.py) | **Derived**, schema version 1, under `[Storage].Root/Indexes`; Windows config selects `E:/Zet/AppData`. Root rejected inside Git/Dropbox or the authored library. One published snapshot is kept; parsed-source payloads match current sources; completed history is limited to seven days. |
| Producer-local queue state | [AIQueueLifecycleService](../zet/services/ai_queue_lifecycle_service.py), [StoragePathService](../zet/services/storage_path_service.py) | `[Storage].Root/AI_Queue/<queue-hash>/<producer>/`; shared queue transport remains at `BaseAIQueuePath`. Routes, receipts, requests, continuations and model cache are local state, not authored data. See [QUEUES](COMPONENTS/QUEUES.md) and [AI jobs](COMPONENTS/AI_JOBS.md). |
| Machine-local task workflow and migration reports | [runtime_state_service.py](../zet/services/runtime_state_service.py), [LibraryReferenceMigrationService](../zet/services/library_reference_migration_service.py) | Configured relative children `TaskWorkflow` and `LibraryReferenceUpdates`; explicit Runtime/GitHub state overrides retain precedence. Loading configuration creates no directories. |

## Character template revisions

Character batches retain `template_improvement/revisions/<id>.json`, compiled artifacts and `active.json`. [LocalTemplateRevisionService](../zet/services/local_template_revision_service.py) reads historical version-1 image-evidence revisions and creates version-2 text reviews with frozen sources/prompts, independently selectable findings, saved decisions and accepted READY child versions. Sources retain stable `library/` and `project/` identities and master baselines. Acceptance selects a batch overlay; promotion remains an explicit separate master write.

New batches have additive version-1 `character_progression` in `state.json`, owned by [LocalCharacterProgressionService](../zet/services/local_character_progression_service.py). It records accepted template identity, requested/required views, opened stage and BACK reference choice. Batch detail projects stage readiness and advisory reference warnings. Per-view recipes and frozen `render_input` preserve actual selected candidate identities, ordered reference bytes and template identity. Legacy batches have no progression record until explicitly enrolled; `review_version` is unchanged.

[LocalCharacterRefinementService](../zet/services/local_character_refinement_service.py) owns `refinements/<session_id>/session.json`, private original/comparison snapshots and iterative outputs. Records bind universe, batch, view, original/adopted selection, comparison report and attempt identities, accepted direction, frozen single-image payload/seeds and resumable work IDs. `refinement_sessions` in batch state remembers each view's current session. Adoption adds a new gallery candidate in the original slot, detaches the prior working candidate and copies the adopted image to its own render directory; original/attempt history and published locks remain intact. No catalog schema migration is required. Operational paths use the existing portable library serializer.


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

Library-owned typed JSON paths use portable format version 1: forward-slash paths relative to the owning universe, such as `PipelineCandidates/Character-Pipeline/...` or `images/<asset-id>`. [LibraryReferenceService](../zet/services/library_reference_service.py) owns the explicit path-field selectors and storage-boundary codec; [PathService](../zet/services/path_service.py) resolves these against the configured, universe-bound root with containment checks. Runtime reads return resolved filesystem paths while stored records retain portable paths. Document-relative and job-relative names, logical keys, IDs, repository templates, and explicitly external paths keep their existing owners. Legacy absolute paths remain readable; relocation is performed only by the offline updater with explicitly supplied old roots. Unsupported path-format versions fail closed. See [the portable-path ADR](DECISIONS/0011-portable-library-references.md) and [development command](DEVELOPMENT.md#existing-library-path-update).

## Configuration and templates

[config.toml](../config.toml) is loaded into frozen [Config](../zet/services/config_service.py). Platform-specific `BaseFoldersByPlatform` overlays base folders; environment/user expansion and relative subfolder resolution belong to `ConfigService`. `Storage.Root` resolves relative to the config file; child settings must remain relative and contained beneath it. Windows production selects `E:/Zet/AppData`. Other platforms and older configs keep their prior machine-local default. [StoragePathService](../zet/services/storage_path_service.py) rejects overlap with the creative library/shared queue and reports an unavailable configured drive instead of falling back. `UniverseService.bind_config` changes library/character/asset/pipeline roots while retaining the shared queue and repository templates.

Key sections to locate are `BaseFolders`, `BaseFoldersByPlatform`, `AIModels`, `LocalRender`, `ComfyUI`, `Render`, `AIHarvest`, `AIPromptAnalysis`, `PromptCondense`, `Zine`, and `Turnaround`, plus `SceneCandidateSources` tables. Consult the loader for defaults/coercion. `render_backend` selects final dispatch; `local_render_backend`/preset/checkpoint selects local generation. They are not interchangeable. Old saved local profile choices normalize to supported defaults; already-staged job validation still enforces current renderer policy.

`[Storage]` owns machine-local `Indexes`, `QueueState`, `MigrationState`, `WorkflowState`, seven-day `CompletedRetentionDays`, and daily `MaintenanceIntervalHours`. `python3 -B -m zet.scripts.manage_storage --config config.toml` is read-only; `--cutover-preview` emits a bounded path/checksum manifest, `--migrate-from <manifest> --confirm-offline` copies verified operational state and leaves sources intact, and `--apply` cleans only verified completed local queue state. Explicit `--rebuild-index --all-universes`, `--verify-indexes`, and offline `--compact-indexes` manage the disposable index. Regenerate the cutover preview after all writers stop. Old-source removal remains a separate approved step; authoritative catalog/library data is outside this operation.

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

Narrative targets also store `use_transparent_background` (boolean, default true;
only subscenes use it). Repository defaults cover missing fields on current targets
without changing historical nested job snapshots. New job detail and copied source
inputs retain explicit true/false. Background policy participates in text-result
application fencing; a historical snapshot without the field is distinguishable.
`assembly_mode` additionally accepts `harmonize_composite`, without changing the
default `finish_composite`. Harmonization snapshots set `has_composite=true`, freeze
one composition reference and source bytes, and omit edit-mask/protected artifacts.
Candidates retain their mode/snapshot and complete dimension-validated output.

## Render slot ownership (2026-10-12)
Character `spec.json` retains initial candidate definitions and initial `slots_by_view`. `state.json` can override slot maps and owns `slot_version=1`, `added_candidates` definitions, mutable `candidates` updates, `detached_candidates`, and persisted supplemental target IDs. New independent slot submissions use `slot_render_ids`, `slot_review_views`, and per-candidate `slot_managed`; older `target_candidate_ids` remain supported for interrupted batch-runner work. Shared merging excludes detached identities from execution/review and active counts. Slots refer to stable candidate IDs, independently of ranking. Existing >8-candidate views remain legacy galleries; compatibility never truncates them. Per-candidate `render_input` freezes prompt text, ordered copied reference paths/hashes and preset for new render attempts.

Image Generation jobs remain under universe `_state/ImageGeneration/<request_id>/job.json`. New jobs use `image_slots_version=1`, child-index image arrays, per-child status/error/seed, and persisted `render_payload` for replay. Historical completion-order jobs retain their original result indices. `_state/ImageGeneration/workspace.json` (version 1) owns eight nullable `{requestId,index}` assignments, `selected_slot` (zero-based or null), and one-time browser import state. A persistent workspace lock serializes allocation; reservations are saved before dispatch. Missing jobs display interruption rather than binding another result. Clear removes board bindings, not historical job files. See [ADR 0007](DECISIONS/0007-stable-render-slots.md).

## Style and reconstruction records (2026-10-14)

Universe style remains the multiline `canonical_art_style` in `universe.json`. Narrative scenes add boolean `use_universe_style`; new=true, absent legacy=false. Effective style/source and the universe snapshot travel in target context and frozen job provenance. Existing saved prompts and historical jobs are not migrated.

`_state/ImageReconstruction/<32-hex-id>/job.json` version 1 owns analysis status, model, source asset identity/hash, task-relative source filename, destination style snapshot, optional notes, extracted content/uncertainties and final prompt. Its immutable source bytes live beside the record. Style source location is informational provenance, not a path used to rediscover creative data. Interrupted analysis fails explicitly; successful handoff uses the same ID for the persisted Image Generation render job.

Existing eight-slot workspace reservations are saved before analysis. Submission verifies reservation ownership; clearing/replacing reserved slots prevents a late analysis result from dispatching. Render payload/job records optionally retain `reconstruction` metadata. Retries retain frozen inputs; edited regeneration retains lineage plus its actual new prompt. Library imports retain model, source hash, style/content, effective render prompt and per-result seed; reconstruction does not populate source-replacement bindings.

### Shared reconstruction targets and reports (2026-10-15)

New ImageReconstruction records use version 2. Ordered source snapshots live at task-relative `sources/<index>.<ext>` names. `target` separates source observations, preserve/change instructions with stable decision IDs, effective description/identity, proposed completions/questions, task context and frozen style; `target_hash` fingerprints it. Editing an approved description/identity/proposal creates a distinct task with `parent_task_id`; changing preserve/change intent causes fresh analysis. Existing v1 records remain readable without migration or replay.

`reports/<id>/report.json` binds target/source/candidate hashes, candidate identity, context, model and instruction version; its candidate/front snapshots are report-relative. Findings carry category, evidence, expected/observed appearance, visibility, severity and optional correction. Successful intentional changes and hidden details cannot be selected for correction. Separate `corrections.json` maps repeated correction requests to durable attempts; correction tasks reserve fresh Image Generation slots. Interrupted analysis/comparison explicitly fails; persisted render jobs reconcile handoff.

New wizard sessions use version 2 with `style_mode`, preserve/change inputs, analysis model and reconstruction task/hash links. The public target brief is derived from the shared task. Missing fields preserve legacy source-style behavior. Candidates retain frozen payload/request IDs, target/view/front bindings, byte hash, seed, comparison and correction/retry ancestry. Payload image data is omitted from public session responses. Publication retains the actual candidate's reconstruction metadata. No catalog table change is required.

Custom Image Generation feedback is appended to the next target's ordered changes and change text, with a new target hash; its submitted metadata identifies that effective target. Wizard comparison context includes the applicable refinement chain. A rendered `REVIEW_FAILED` wizard candidate can still be selected, refined with custom feedback, or published as an operator-selected view. Review state is not an artistic approval requirement.

### Minor Character current boards (2026-10-15)

New records retain `_state/QuickCharacterWizard/<id>/session.json` and base session version 2, adding `workflow_version: 1`. Retired records without this marker are excluded/rejected, not migrated. Names remain trimmed, case-insensitive and universe-local. Stable reference IDs preserve entry order; primary identity and comparison designation are independent.

`boards` maps STYLE and supported view IDs to one current four-slot board each. A board holds alignment/true_up mode, monotonic revision, template candidate, selected/prior-selection IDs, edit state and one private undo snapshot. `selected[STYLE]` enables independent view alignment. Working selections require slot membership; `locked[view]` references immutable Inventory assets. Clear/Regen clears a replaced working selection, never its lock. List thumbnails use locked front.

Restart view resets only that board and starts a fresh alignment candidate from the selected STYLE image. Restart STYLE resets all boards, increments each board revision, clears working selections and analysis-derived inputs, and re-analyzes retained references. Old candidate bytes may remain privately for reproducibility, but board membership revokes access and late results cannot restore it. Published `locked[view]` records are not changed by restart. The public board prompt continues to come from its current template candidate.

Candidates freeze inputs, accepted direction, selected correction text, kind, stage, anchor, source and submitted payload. Carrying changes neither prompt nor kind. Only generated view true_ups publish. Additional renders replay the template with fresh seeds. Public candidates and image reads expose current slots only; private source/request files may remain for reproducibility and dependent work, without recoverable image history.

Undo restores one previous recipe/edit state and frozen findings, empties all slots, clears working selection and consumes its snapshot. A private restored-source binding permits different corrections without exposing that source as a working image. Public boards expose prompt, findings, edit state and action availability, omitting undo internals and payloads. Expected revisions reject stale mutations; late results cannot restore discarded membership. Review is advisory.

Publication retains immutable candidate IDs/origin keys and per-view reference-set replacement. Catalog tables are unchanged. Workspace deletion uses deleted_at/ABANDONED and preserves published assets. See [ADR 0015](DECISIONS/0015-minor-character-alignment.md).

## Shared AI lifecycle records (2026-10-16)
The existing machine-local queue/producer root now contains compact `Jobs/` request
records, registered `Workflows/` continuations, and `StructuredResults/`, alongside
Inbox/Receipts/Routes. They are producer-local lifecycle state, not library assets or
the derived library index. Native request payload version 1 extends the unchanged
File Proxy protocol-v1 envelope. [Shared AI jobs](COMPONENTS/AI_JOBS.md) owns interfaces.

`DeletedJobs/<sha256(job_id)>.json` version 1 is a producer-local deletion fence:
job/producer/universe identity, deletion timestamp, cleanup-complete flag and an
optional cleanup error. It precedes payload deletion; incomplete cleanup is visible
and retryable. Completed deletions are excluded from activity/history and cannot be
republished or collected under the same identity. This marker and shared locks
survive cleanup; authored workflow/library records are not deletion targets.

Collection diagnostics add `failure_stage`, `exception_type`, `affected_path` and
`failed_at` to local job records. Receipts retain `execution_status` separately
from `answer_status`; image application can include `applied_artifact` with its
checksum, image flag and diagnostic destination path. Destination authorization
still comes from the owning workflow, never that diagnostic path. Older receipts
remain readable. Local character batch review uses current-file availability;
missing/outdated candidate hashes are refreshed on explicit Re-evaluate rather
than rejecting an existing image. Existing-image review does not require historical receipts or matching bytes;
current candidate/attempt ownership still fences new work. See [ADR 0021](DECISIONS/0021-file-based-local-image-availability.md).

New I/O collection failures also retain `collection_failures` and
`collection_retry_at` for delayed collection-only retry. Historical failures
without a scheduled retry stay unchanged until explicitly handled.

`Followups/` stores immutable publication timestamp reservations keyed by parent
render, analysis kind, frozen inputs and evaluation. Reconstruction's
`preparation.json` fingerprints its owner and inputs. Wizard sessions may retain
`draft_workflow_id` and `analysis_continuation` checkpoints, and candidates retain
`render_harvest` evidence. Wire versions and catalog schemas are unchanged.

## Recovery metadata (2026-10-17)
Version-1 fixed-local recovery records add root identities, compact request activity, registered continuation arguments and logical-to-current attempt reservations. Existing library and protocol-v1 envelope formats remain readable. New request records optionally retain the original envelope for interrupted staging publication. Recovery status fields are additive; fresh execution uses a new transport ID, with verified producer-local logical results. Details and storage ownership: [storage recovery](COMPONENTS/STORAGE_RECOVERY.md).

## Streamlined image integrity metadata (2026-10-17)

Catalog schema 3 and existing checksum/receipt fields remain compatible. Checksums
record Zet-managed writes, not file-system anti-tampering proof. New reconstruction
sources and wizard references may carry `managed_checksum` separately from the digest
of captured bytes; legacy snapshots fall back to their saved checksum metadata.
Preparation markers use `identity_version: 2` with request/source metadata identity.

Local Inbox `.zet-admitted.json` records one-time successful transfer verification;
it is local collection state, never trusted from a shared answer. Per-consumer
ImageUsages pending markers live under the existing machine-local recovery journal,
scoped by library configuration, with a bounded lock pool. `asset_usages` retains its
schema and direct-ID/key-only semantics; no bulk catalog migration is required.
Archive confirmations carry `confirm_ids` and per-image `expected_versions` derived
from catalog metadata, checked under the catalog transaction.
