# Narrative dashboard scenes

Narrative provides prose-oriented authoring and generation independent of Scene Builder's templates, schemas, and pipeline records. It shares universe configuration, the image library, and infrastructure, not the structured-scene authoring lifecycle. [ADR 0002](../DECISIONS/0002-independent-narrative-workflow.md) records this boundary.

## Implementation and interfaces

| Module | Responsibility |
| --- | --- |
| [models/narrative.py](../../zet/models/narrative.py), [NarrativeRepository](../../zet/repositories/narrative_repository.py) | Story, scene, element, target and candidate defaults; atomic JSON persistence, constrained IDs and repository workflow lock |
| [NarrativeSceneService](../../zet/services/narrative_scene_service.py) | Authoring CRUD, scene elements, targets, references, image selection/locking and protected deletion; `ZetApp.narrative_scene_service` |
| [NarrativeGenerationService](../../zet/services/narrative_generation_service.py) | `start`/detail polling, persisted interview/synthesis/render jobs, candidate slots, retry/replay and background poller |
| [narrative_prompt_service.py](../../zet/services/narrative_prompt_service.py) | `llm_request`, `assemble_prompt`, structured request schemas and deterministic prompt/reference packaging |
| [NarrativeProxyService](../../zet/services/narrative_proxy_service.py), [NarrativeCodexService](../../zet/services/narrative_codex_service.py) | Proxy text/image dispatch and durable Codex CLI text attempts; [narrative_qwen_workflow.py](../../zet/services/narrative_qwen_workflow.py) supplies image workflows |
| [NarrativeReferenceService](../../zet/services/narrative_reference_service.py) | Pinned backdrop inputs, local reuse/crop actions and independent imported subscenes |
| [NarrativeAssemblyService](../../zet/services/narrative_assembly_service.py) | Source/layer binding, editable extraction/cutouts, deterministic composition and frozen assembly snapshots |
| [narrative_router.py](../../zet/web/narrative_router.py), [narrative.html](../../zet/web/templates/narrative.html), [narrative.js](../../zet/web/static/narrative.js) | HTTP/browser presentation and calls into Narrative services; context capture integrates with shared [task_capture.js](../../zet/web/static/task_capture.js) |

## Data and job lifecycle

Inputs include scene intent/visual settings, named elements/library asset IDs, target narrative/staging/physical context/framing, model selection, candidate slot controls, and assembly layers. Targets include backdrop/subscene/assembly behavior. Outputs are authored prose, generated prompts with provenance, durable job/candidate records, image files, selections and locked images. Storage is under universe `NarrativeStories/`; [DATA_MODEL](../DATA_MODEL.md) owns identifiers/formats.

1. Author creates a story, scenes, elements, and targets with stable IDs. Target visual settings combine scene defaults and target overrides.
2. `start` chooses interview/synthesis/generate/render or a supported replay action. Text models with `codex:` dispatch to Codex; otherwise text work uses the proxy/Ollama path. Jobs persist model/provider provenance and a baseline for result application.
3. Submission snapshots ordered reference bytes. Assembly submission binds server-owned source layers and freezes an assembly snapshot; replay uses saved job inputs. Backdrop crop/unchanged operations use local actions instead of requesting generation.
   Qwen Image 2.1 render references are prepared in the local render-job workspace under the configured per-image and aggregate pixel budgets. Prepared source hashes/order and effective machine settings accompany the saved graph; pending ComfyUI submissions resume that graph and its snapshots after configuration changes.
4. Proxy/Codex results advance jobs and candidate slots. Background polling starts/stops with app lifespan; Codex attempts receive fresh attempt ownership after restart so old attempt outputs cannot apply.
5. The user selects/locks outputs. Protected deletion and pinned sources prevent accidental removal/mutation of images used by the workflow.

## Assembly and reference boundaries

Layer controls/identifiers come from the client, but filenames, metadata, and source-byte binding are server owned. Assembly modes influence prompt provenance; a prompt generated for one mode cannot silently render another. `finish_composite` is the model's default assembly mode; inspect the service for supported alternatives. Extraction uses OpenCV/NumPy/Pillow and its own lock. Imported subscenes/backdrops retain independent snapshots; they are not live links to another target's changing candidate.

The scene overview and scene-page target selector keep final assembly targets after backdrops and subscenes, even when a new target is added later. This is presentation ordering; stored target order remains unchanged.

Qwen reference sizing and prefix-cache placement are configured under
`[ComfyUI.QwenImage21]` in `config.toml`; see
[PROMPTS](PROMPTS.md) for limits and image handling. Pixel budgets are tunable
workload settings, not a prediction of VRAM fit or render duration. The metadata
records configured cache device/precision separately from ComfyUI's runtime status.

## Failure modes and extensions

Unknown record IDs, missing selected source files, stale jobs/results, occupied slots, protected images, unavailable Codex executable, external proxy errors, invalid structured text results, and assembly-mode/provenance mismatch are relevant failure cases. Inspect persisted target job errors and text-attempt artifacts before retrying. An HTTP read can reconcile job state, so it is not necessarily a pure file read.

Add Narrative fields to model defaults, author patch/validation lists, prompt/job snapshots, result application and UI together. Keep queue protocol changes in shared infrastructure and Narrative-specific job semantics here. The retired Scene Builder staging facade has been removed; do not recreate it as a shortcut.

## Tests and design notes

[fast.spec.mjs](../../tests/e2e/fast.spec.mjs) S1 saves/reloads story, scene and element authoring; S3 runs interview/synthesis, prepared backdrop/subscene renders, a failure/retry, source selection/locking and final assembly through persisted publication/display. The [live check](../../tests/e2e/live.spec.mjs) uses prepared prerequisites then real final-assembly synthesis/rendering. These scenarios do not exhaustively verify frozen-input rejection, protected deletion, source import or Codex restart branches. See [Testing](../Testing.md) for live opt-in and coverage approval and [DEVELOPMENT](../DEVELOPMENT.md) for results.

[Narrative approach](../../Docs-Joe/Narrative_Scene_Approach.md), [phase 1](../../Docs-Joe/Narrative_Scenes_Phase_1.md), [phase 2](../../Docs-Joe/Narrative_Scenes_Phase_2.md), and [references](../../Docs-Joe/Narrative_Scene_References.md) preserve intent and specifications; check code before treating recommendations as implemented behavior.

## Dashboard, migration and Candidates (2026-10-12)

The dashboard Stories workspace mounts the existing editor through
`mountNarrative` in [narrative.js](../../zet/web/static/narrative.js), with explicit
unmount/save, listener cancellation, polling cleanup and task-provider restoration.
Canonical URLs use `/?page=narrative&workspace=story` plus universe/story/scene/target
IDs. `/narrative` redirects for existing links and approved scenarios. Story navigation
contains Stories, Candidates and Zines; migration provenance maps old story/scene links.

Scene defaults include service-owned `legacy_image`, `source_provenance`, and
`migration`; elements optionally use `reference_key` instead of `asset_id`. Scene
and target serializers resolve current logical references; stale/archived/missing
bindings show issues and cannot supply render references. Submitted jobs still freeze
resolved IDs, ordered files and bytes. [NarrativeSceneService](../../zet/services/narrative_scene_service.py)
refreshes entity usages on authoring changes. Legacy image assets survive scene deletion.

[NarrativeMigrationService](../../zet/services/narrative_migration_service.py) and its
[CLI](../../zet/scripts/migrate_narrative_scenes.py) consume the reviewed
[manifest](../../Config/Legacy_Narrative_Migration.json). Preparation/dry-run do not
write creative data. Apply/resume are offline, back up the destination, journal stable
IDs and preserve existing/edited destinations. Verification checks counts, order,
required targets, membership and image checksums. The image reviews seed prose staging,
not measured geometry or a functioning pipeline. Targets start without jobs, prompts,
selections, candidates or assembly layers. Full legacy scene documents/Markdown and
story settings remain in provenance. See the [archive guide](../../Archive/scene-builder/README.md)
for backup and rollback boundaries.

[SceneCandidateSourceService](../../zet/services/scene_candidate_source_service.py)
parses existing read-only Adventure Log Markdown. [NarrativeCandidateImportService](../../zet/services/narrative_candidate_import_service.py)
creates resumable stubs with provenance, exact visible participants, backdrop/subject/
assembly inputs and unresolved-reference notes. `/api/narrative/candidate-sources`
and `/api/narrative/candidates` own listing/import/passed/review actions. Default story
slugs resolve through migrated provenance. Passed/import reservations are universe-local.
Repeated imports open existing destinations; all three celestial-rift associations
remain distinct. Source review compares recorded/incoming briefs; acknowledgement
changes only provenance, preserving authored fields and target images.

Selected final assemblies feed discovery, story summaries and zines through
`finished_sources`; `NARRATIVE` image tags bind an explicit candidate. Legacy images
are separately labeled and never count as newly completed assemblies.
