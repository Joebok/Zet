# Independent Narrative scenes

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
| [narrative_router.py](../../zet/web/narrative_router.py), [narrative.html](../../zet/web/templates/narrative.html) | HTTP/browser presentation and calls into Narrative services |

## Data and job lifecycle

Inputs include scene intent/visual settings, named elements/library asset IDs, target narrative/staging/physical context/framing, model selection, candidate slot controls, and assembly layers. Targets include backdrop/subscene/assembly behavior. Outputs are authored prose, generated prompts with provenance, durable job/candidate records, image files, selections and locked images. Storage is under universe `NarrativeStories/`; [DATA_MODEL](../DATA_MODEL.md) owns identifiers/formats.

1. Author creates a story, scenes, elements, and targets with stable IDs. Target visual settings combine scene defaults and target overrides.
2. `start` chooses interview/synthesis/generate/render or a supported replay action. Text models with `codex:` dispatch to Codex; otherwise text work uses the proxy/Ollama path. Jobs persist model/provider provenance and a baseline for result application.
3. Submission snapshots ordered reference bytes. Assembly submission binds server-owned source layers and freezes an assembly snapshot; replay uses saved job inputs. Backdrop crop/unchanged operations use local actions instead of requesting generation.
4. Proxy/Codex results advance jobs and candidate slots. Background polling starts/stops with app lifespan; Codex attempts receive fresh attempt ownership after restart so old attempt outputs cannot apply.
5. The user selects/locks outputs. Protected deletion and pinned sources prevent accidental removal/mutation of images used by the workflow.

## Assembly and reference boundaries

Layer controls/identifiers come from the client, but filenames, metadata, and source-byte binding are server owned. Assembly modes influence prompt provenance; a prompt generated for one mode cannot silently render another. `finish_composite` is the model's default assembly mode; inspect the service for supported alternatives. Extraction uses OpenCV/NumPy/Pillow and its own lock. Imported subscenes/backdrops retain independent snapshots; they are not live links to another target's changing candidate.

## Failure modes and extensions

Unknown record IDs, missing selected source files, stale jobs/results, occupied slots, protected images, unavailable Codex executable, external proxy errors, invalid structured text results, and assembly-mode/provenance mismatch are relevant failure cases. Inspect persisted target job errors and text-attempt artifacts before retrying. An HTTP read can reconcile job state, so it is not necessarily a pure file read.

Add Narrative fields to model defaults, author patch/validation lists, prompt/job snapshots, result application and UI together. Keep queue protocol changes in shared infrastructure and Narrative-specific job semantics here. Do not add calls to `StoryService.stage_scene_render` as a shortcut.

## Tests and design notes

[test_narrative_repository.py](../../tests/test_narrative_repository.py), [test_narrative_scene_service.py](../../tests/test_narrative_scene_service.py), [test_narrative_generation.py](../../tests/test_narrative_generation.py), [test_narrative_phase2.py](../../tests/test_narrative_phase2.py), [test_narrative_references.py](../../tests/test_narrative_references.py), [test_narrative_qwen.py](../../tests/test_narrative_qwen.py). Generation fixtures deliberately forbid legacy story creation/loading/staging. Results verified here are in [DEVELOPMENT](../DEVELOPMENT.md).

[Narrative approach](../../Docs-Joe/Narrative_Scene_Approach.md), [phase 1](../../Docs-Joe/Narrative_Scenes_Phase_1.md), [phase 2](../../Docs-Joe/Narrative_Scenes_Phase_2.md), and [references](../../Docs-Joe/Narrative_Scene_References.md) preserve intent and specifications; check code before treating recommendations as implemented behavior.
