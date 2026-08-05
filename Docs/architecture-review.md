# Zet Architecture and Maintainability Review

Review date: 2026-07-21  
Scope: current working tree, all Python packages/scripts, FastAPI/HTML/JavaScript UI, tests, configuration, and current documentation. The configured Windows library at `C:/Users/Joe/Projects/Zet_Library/Characters` was inspected read-only to verify dynamic pipeline registrations and persisted stages. No source files were changed.

## Executive summary

The backend has a sound intended boundary—repositories persist file-backed models, services own workflows, and FastAPI presents them—but three transitions are incomplete:

1. **P0 — establish a green behavioral baseline.** `python3 -m pytest -q` currently reports **16 failed, 85 passed**. Failures cluster around the new config-root contract, the Scene Builder V3 requirement, changed prompt text, and story rendering. Several tests still assert retired behavior, while others expose uncharacterized behavior changes. Refactoring on this baseline would make regressions hard to distinguish from intentional migration.
2. **P0 — finish or explicitly preserve the `PROMPT_REVIEW` compatibility lane.** New onboarding removes the stage and every configured pipeline in the active library bypasses it, but stage-specific routes, services, an AI worker, config, facade methods, tests, and documentation remain. The current browser “Prompt Review” page already reads Render Console tasks instead of the old prompt-review API. This is a confirmed split between current behavior and compatibility code; removal still requires a human decision about external clients and other libraries.
3. **P1 — move reusable mutations out of `zet/web`.** The web module owns arbitrary source editing, queue-answer writes, prompt-file replacement, queue filtering, filesystem discovery, and backend HTTP discovery. These are reusable workflows and directly violate the documented boundary.
4. **P1 — break the `AssetService` / `AIProxyService` / `PromptReviewService` dependency cycle.** `ZetApp.from_config()` constructs an incomplete proxy service, builds services around it, then mutates `ai_proxy_service.prompt_review_service`. `PromptReviewService` also reaches through `AssetService` into private `WorkerService` methods. This makes construction order and private implementation details part of runtime behavior.
5. **P1 — split the story/render and web monoliths after behavior is characterized.** `StoryService` combines document CRUD, Git, three schemas, migration/defaulting, prompt generation, reference resolution, queue cleanup, and render staging. `zet/web/app.py`, `zet/web/static/zet.js`, and the single HTML template similarly aggregate every page. Their physical sizes (1,765, 2,742, 6,598, and 1,268 lines respectively) are symptoms; the mixed responsibilities are the maintenance problem.
6. **P2 — consolidate repeated infrastructure.** AI queue paths/state scanning, JSON repository serialization/atomic writes, stage compiler scaffolding, view normalization, and worker filesystem primitives are independently implemented in several places.

Risk scale: **High** means persisted state or cross-process queue behavior can change; **Medium** means public APIs/workflow outputs can change; **Low** means internally unreferenced code can be removed after import/entry-point checks.

## Confirmed dead or obsolete code

### D1. Scene Builder legacy helpers are internally unreferenced

**Priority/status:** P2, confirmed within this repository.  
**Symbols:**

- `StoryService.load_scene_v3` (`zet/services/story_service.py:749`)
- `StoryService._scene_builder_markdown_template_path` and `SCENE_BUILDER_MARKDOWN_TEMPLATE_NAME` (`zet/services/story_service.py:117,773`)
- `StoryService.create_default_scene_builder_data_v2` (`zet/services/story_service.py:861`), despite returning `schema_version: 3`
- `StoryService._render_prompt_block`, `find_scene_element_id`, `generate_positive_prompt`, and `generate_negative_prompt` (`zet/services/story_service.py:211,1051,1331,1353`)
- `scene_render_compiler.compile_scene_render` and its `SceneRenderCompilation` return model (`zet/services/scene_render_compiler.py:13,1105`)
- `scene_render_compiler._view_text` and the four `write_*` helpers (`zet/services/scene_render_compiler.py:177,1085-1100`)

**Evidence/trace:** repository-wide Python and test reference searches find only the declarations (and the template constant’s self-reference). Active rendering calls `compile_scene_render_ir`, `final_image_prompt_text`, `local_render_brief`, and prompt-text functions directly from `StoryService.stage_scene_render` (`zet/services/story_service.py:1558-1652`). `ScenePromptAnalysisService` calls `StoryService.compile_scene_prompt`, not `compile_scene_render` (`zet/services/scene_prompt_analysis_service.py:20`).

**Cost:** the unused V2/V3 vocabulary obscures which schema is supported and leaves two prompt-generation implementations beside the active IR compiler.  
**Refactoring risk:** Low for private helpers; Medium for public-looking functions in case an untracked external script imports them.  
**Tests before change:** an import scan of deployed scripts; golden tests for `stage_scene_render` and `compile_scene_prompt`; one test proving the configured markdown template is intentionally unused or one caller that makes it active.

### D2. `PROMPT_REVIEW` stage code is obsolete for the current configured runtime, but may be a compatibility surface

**Priority/status:** P0, confirmed runtime drift; probable removal candidate.  
**Symbols/paths:**

- New phase normalization explicitly removes the stage: `CharacterOnboardingService._normalize_foundation_pipelines` (`zet/services/character_onboarding_service.py:288-305`).
- Stage-only actions remain in `AssetService.approve_prompt_review`, `fail_prompt_review`, and the `PROMPT_REVIEW_NEEDS_HUMAN` branch (`zet/services/asset_service.py:172-195,530-543`).
- Duplicate facade exposure remains in both `AssetRef` and `ZetApp` (`zet/app.py:62-79,457-497`).
- Old APIs remain at `/api/prompt-review/*` (`zet/web/app.py:1885-1974`).
- The dynamic worker remains at `zet/workers/ai_prompt_review_worker.py` and config remains in `ConfigService`, `PipelineControlService`, and `[AIPromptReview]` (`zet/services/config_service.py:33-34,91,141-145`; `zet/services/pipeline_control_service.py:28-29,110-111,133-155`).
- `PromptReviewService.is_prompt_review_asset` has no repository caller (`zet/services/prompt_review_service.py:39`).

**Evidence/usage trace:** all ten current pipeline definitions under the configured Windows library use `...PROMPT,RENDER...`, none contains `PROMPT_REVIEW`, and the 103 persisted assets are only `LOCKED` (101) or `ERROR` (2). The browser’s `loadPromptReviewTasks` and `selectPromptReviewTask` use `/api/render-console/tasks` (`zet/web/static/zet.js:4224-4266`), not `/api/prompt-review/*`. The old APIs are referenced by tests at `tests/test_web_app.py:516-535`, but not by the current browser. Dynamic configuration means another library could still name `zet.workers.ai_prompt_review_worker`; that external possibility prevents classifying the whole lane as confirmed dead.

**Cost:** two meanings of “prompt review” coexist: a retired pipeline stage and the active review/edit view over queued render prompts. Branches, UI routes, config fields, docs, and tests can disagree about which meaning applies.  
**Refactoring risk:** High until external libraries/API clients are inventoried; Low-to-Medium after an explicit migration cutoff.  
**Tests before change:** enumerate every supported `Pipelines.json`; contract-test any external API client; migrate or delete the old `/api/prompt-review/*` tests; retain tests for render-prompt inspection/recompile on `RENDER` tasks.

### D3. Documentation describes removed entry points and nonexistent APIs/files

**Priority/status:** P1, confirmed obsolete documentation.  
**Evidence:**

- `README.md:46,68,91,121` directs users to `python -m zet.app`, but `zet/app.py` ends with facade methods and has no `main` block. The supported launcher invokes `python3 -B -m zet.web.app` (`run_zet_web.bat:12`).
- The README API table lists `/api/characters/{name}`, `/api/assets/search`, `/api/prompts/review`, and `/api/render/console/status` (`README.md:125-128`); none is registered in `zet/web/app.py`.
- `README.md:141`, `Docs/Zet.md:575-579`, and `Docs/Zet_Data_Schema_Object_Model_Decisions.md:460` reference `AI_Manager/comfyui_proxy_worker.py`, which does not exist.
- The README names `Tests/` (`README.md:112`) while the directory is `tests/`.
- `Docs/Zet.md:28,127-167,290,427` and `Docs/Zet_Data_Schema_Object_Model_Decisions.md:243,290,376` document the retired prompt-review stage.
- The documented `Asset` field list omits `reference_files`, `identity_key_id`, `expression_definition_path`, and `costume_path` now present at `zet/models/asset.py:24-28`; the “current repositories” list at `Docs/Zet_Data_Schema_Object_Model_Decisions.md:123` omits the turnaround, identity-key, and auxiliary-resource repositories.

**Cost:** onboarding and troubleshooting instructions fail before reaching runtime, while schema documents encourage new code to reproduce an obsolete model.  
**Refactoring risk:** Low, after the prompt-review decision.  
**Tests before change:** launcher smoke test; route inventory generated from the FastAPI app; documentation link/path checker.

## Duplication and DRY opportunities

### R1. AI queue layout and task-state scanning have several sources of truth

**Priority/status:** P1, confirmed duplication.  
**Canonical candidate:** `AIProxyPathService` already defines `Ollama_Proxy`, `Ask`, `Claims`, `Claimed`, `Answer`, `Failed`, `Archive`, `Control`, and `Monitor` (`zet/services/ai_proxy_path_service.py:8-67`).  
**Duplicate implementations:**

- `RenderConsoleQueue.proxy_root/ask_root/answer_root` (`zet/render_console/queue.py:51-61`)
- `PromptReviewService._condense_queue_items` (`zet/services/prompt_review_service.py:134-169`)
- `ScenePromptAnalysisService.queue/status` (`zet/services/scene_prompt_analysis_service.py:20-76`)
- `StoryService._clear_scene_render_queue_items` and `stage_scene_render` (`zet/services/story_service.py:1522-1556,1615`)
- `ai_prompt_review_worker._has_pending_review` (`zet/workers/ai_prompt_review_worker.py:159-177`)
- both proxy workers’ `ensure_dirs`/normalization (`AI_Manager/ollama_proxy_worker.py:155-175`; `AI_Manager/local_image_proxy_worker.py:82-102`)

**Cost:** adding or renaming a queue state requires coordinated edits across the app and two processes. The current scanners already differ in which roots they inspect.  
**Refactoring risk:** High because the folder protocol is cross-process and may be shared over Dropbox.  
**Tests before change:** protocol characterization for Ask → Claims/Claimed → Answer/Failed → Archive; mixed worker task tests; stale claim and concurrent claim tests; Windows/macOS path tests.

### R2. Pipeline compilers share a duplicated orchestration skeleton and import one another

**Priority/status:** P2, confirmed duplication.  
**Evidence/trace:** `Run_Head_Fitment_Jobs`, `Run_Character_Assembly_Jobs`, `Run_Costume_Dressing_Jobs`, and `Run_Expression_Jobs` import field parsing, view normalization, bundle loading, output naming, and metadata functions from `Run_Body_Reference_Jobs`; the latter three also import reference validation from `Run_Head_Fitment_Jobs` (`Scripts/Run_Head_Fitment_Jobs.py:17-35`; `Scripts/Run_Character_Assembly_Jobs.py:17-35`; `Scripts/Run_Costume_Dressing_Jobs.py:19-36`; `Scripts/Run_Expression_Jobs.py:16-29`). Each compiler then repeats required-field parsing, task validation, bundle/section selection, output-path expansion, metadata/source maps, auxiliary reference collection, dependency manifest/review writes, and result-dict construction.

**Cost:** Body Reference and Head Fitment are accidental utility modules as well as entry points. A stage-specific edit can change downstream imports, and result/manifest fields can drift.  
**Refactoring risk:** Medium; generated prompts and source maps are behaviorally sensitive.  
**Tests before change:** golden artifact trees for all five compilers; malformed job/reference cases; source-map line provenance; exact manifest/result schema tests. Extract only the stable orchestration primitives, leaving stage-specific prompt composition in each pipeline script.

### R3. File-backed repositories repeat model conversion and atomic JSON persistence

**Priority/status:** P2, confirmed duplication.  
**Evidence:** `AssetRepository`, `TurnaroundRepository`, `IdentityKeyRepository`, and `AuxiliaryResourceRepository` each independently implement dataclass required/default-field handling, serialization through `fields()`, payload validation, timestamped backups, temp writes, JSON rereads, and replacement (`zet/repositories/asset_repository.py:47-92`; `turnaround_repository.py:53-93`; `identity_key_repository.py:48-87`; `auxiliary_resource_repository.py:45-83`). Behavior already differs: missing `Assets.json` is an error, while the other stores synthesize empty payloads; backup directory and temp-file naming also differ.

**Cost:** schema-evolution and durability fixes must be repeated and are likely to diverge.  
**Refactoring risk:** Medium because backup and missing-file semantics are domain decisions.  
**Tests before change:** characterize each repository’s missing/malformed/wrong-shape behavior, unknown fields, defaulted fields, backup creation, failed temp validation, and save/delete semantics. Share codecs and atomic-write primitives, not necessarily a generic repository base class.

### R4. View and path normalization are duplicated with different fallback semantics

**Priority/status:** P2, confirmed duplication and probable correctness hazard.  
**Evidence:** `AssetService._view_folder_for_asset` (`zet/services/asset_service.py:91-104`) and `PromptReviewService.view_folder_for_asset/load_view_options` (`zet/services/prompt_review_service.py:278-292`) independently parse `Prompt_View_Text.json`; scripts use `normalize_view` in `Run_Body_Reference_Jobs.py:41-60`. `PathService.resolve_path` returns unknown relative paths unchanged (`zet/services/path_service.py:32-42`), while `Scripts.Library_Paths.resolve_library_path` resolves them against `project_root` (`Scripts/Library_Paths.py:39-49`). `StoryService` adds a third library-relative conversion pair (`zet/services/story_service.py:779-789`).

**Cost:** the same stored path/view can resolve differently depending on which workflow reads it.  
**Refactoring risk:** High for persisted paths; Medium for view lookup.  
**Tests before change:** a path matrix covering absolute, project-relative, library-relative, legacy `_Lib`, known top-level, and unknown relative inputs on Windows/macOS; alias/folder/output-name view tests.

### R5. Proxy workers repeat filesystem protocol primitives

**Priority/status:** P2, confirmed duplication.  
**Evidence:** `ollama_proxy_worker.py` and `local_image_proxy_worker.py` both implement timestamp/logging, JSON reads/writes, directory creation, queue directory maps, proxy-root normalization, claim-file creation, claim/release/move-to-answer, monitoring, and answer-manifest scaffolding. `proxy_worker.py` then imports the Ollama implementation as the de facto shared library (`AI_Manager/proxy_worker.py:19-24,41-99`).

**Cost:** a text-specific executable is the protocol utility provider for the unified and image workers; standalone and unified behavior can drift.  
**Refactoring risk:** High because claiming must remain atomic across processes.  
**Tests before change:** multi-process claim contention, transient release, stop handling, monitor response, corrupt manifest, and answer atomicity tests.

## Data-model inconsistencies

### M1. `reference_files` is an untyped family of incompatible record shapes

**Priority/status:** P1, confirmed fragmentation.  
**Evidence/serialization path:**

- Models expose `list[dict]`: `Asset.reference_files`, `AIProxyAsk.reference_files`, and `WorkerResult.reference_files` (`zet/models/asset.py:24`; `zet/models/ai_proxy.py:25`; `zet/models/worker.py:24`).
- Asset references use roles such as `body_reference`, `headshot`, `character_assembly`, and `identity_key`; auxiliary references add `category`, `resource_id`, `label`, and `tag` (`zet/services/reference_service.py:24-122`; `Scripts/Auxiliary_Resource_Tags.py:79-89`).
- Story references add a `kind` vocabulary and are converted into a queue manifest (`zet/services/story_service.py:1440-1516,1602-1652`).
- Scene JSON separately calls logical bindings `reference_assignments` (`zet/services/story_service.py:846,1278`; `zet/services/scene_render_compiler.py:89`).
- The data is copied Asset → Worker job (`zet/workers/*_prompt_worker.py`) → compiler result → `WorkerResult` → Asset (`zet/services/asset_service.py:479-483`) → `AIProxyAsk` → `ask_manifest.json` (`zet/services/ai_proxy_service.py:139-252`) → `ManualRenderTask.manifest` (`zet/render_console/queue.py:63-100`). Every boundary reparses raw keys.

**Cost:** required keys and role/kind terminology are validated ad hoc, so malformed references fail late in compilers/render adapters. Conversion code grows with each reference type.  
**Refactoring risk:** High because manifests are a cross-process persisted protocol.  
**Tests before change:** inventory real stored reference records; define backward-compatible decoders per schema version; round-trip each role/kind through Asset, worker, ask, render console, harvester, and story scene.

### M2. Service/domain result models are scattered outside `zet/models`

**Priority/status:** P2, confirmed inconsistency.  
**Evidence:** story records/documents/render tasks/git results are declared at the top of `StoryService` (`zet/services/story_service.py:25-108`); render-console tasks live in the retired-feature namespace (`zet/render_console/queue.py:17-44`); worker/batch results live inside `asset_service.py:32-58`; costume/expression result models live in their services. Persistent models live under `zet/models`.

**Cost:** callers cannot tell whether a type is a persistence model, workflow command/result, or web DTO. The web layer compensates with many custom `_..._payload` conversion functions (`zet/web/app.py:299-807`).  
**Refactoring risk:** Low-to-Medium if moves preserve imports temporarily.  
**Tests before change:** serialization snapshots for public API payloads and import-compatibility tests. Prefer explicit categories—persistent records, service command/results, and web DTOs—over moving every dataclass mechanically.

### M3. Scene schema naming and compatibility policy conflict

**Priority/status:** P1, confirmed inconsistency.  
**Evidence:** the active default is schema V3 (`StoryService.create_default_scene_builder_data`, `story_service.py:800-859`), while `create_default_scene_builder_data_v2` also returns V3 (`:861-893`), `load_scene_v3` is unused (`:749`), `get_scene_builder_json_path` remains primarily as a test-facing older path helper (`:666`), and a test still names expected outputs “v2” (`tests/test_story_service.py:724`). `_normalize_scene_builder_data` rejects every version other than 3 and silently removes legacy `setup.camera`, `setup.style`, several dialogue keys, `generation_outputs`, and `_validation_warnings` (`story_service.py:905-957`). The current test `test_scene_builder_load_migrates_v1_character` fails.

**Cost:** it is unclear whether old scenes should migrate, be rejected, or be destructively normalized on next save.  
**Refactoring risk:** High because scene JSON is user-authored persisted data.  
**Tests before change:** real V1/V2/V3 fixtures; explicit migration golden files; unknown-field preservation; load-without-write vs save migration; backup/rollback on failed migration.

### M4. Prompt-review terminology now spans three different concepts

**Priority/status:** P1, confirmed.  
**Representations:** retired pipeline stage (`PROMPT_REVIEW`), generated human checklist file (`Prompt_Review.md`), and active browser prompt inspection over render-console tasks. `PromptReviewService` also owns prompt discovery, condense queue status, local rendering, and recompile behavior on both `PROMPT_REVIEW` and `RENDER` (`zet/services/prompt_review_service.py:42-292`).

**Cost:** names no longer reveal lifecycle or ownership, and retiring the stage risks accidentally deleting active prompt-artifact behavior.  
**Refactoring risk:** Medium.  
**Tests before change:** map every UI action and API to stage-independent prompt artifact operations; retain checklist-file behavior separately from stage transitions.

## Architectural concerns

### A1. `zet/web/app.py` owns reusable business workflows

**Priority/status:** P1, confirmed boundary violation.  
**Evidence:**

- Character/phase filesystem discovery: `_discover_characters`, `_discover_phases` (`:233-245`).
- Editable source authorization, JSON Pointer parsing/mutation, markdown-section extraction, persistence, and audit logging: `_record_source_edit` through `_save_edit_source` (`:864-1014`). The module mutates `sys.path` to import compiler/editor internals from `Scripts` (`:26-34`).
- Render backend configuration and network discovery: `_local_render_preset`, `_local_render_checkpoints` (`:1052-1083`).
- Render prompt replacement and queue transitions: direct task prompt write (`:2487`), `queue.write_answer_image` (`:2609`), and `queue.write_failed_answer` (`:2636`).

**Call trace:** FastAPI routes call these helpers directly; no `ZetApp`, focused service, or repository exposes the same workflow. Consequently scripts/other interfaces cannot reuse source editing or render-answer submission without importing the web module.

**Cost:** HTTP concerns, filesystem policy, migration, protocol transitions, and error translation cannot be tested or reused independently.  
**Refactoring risk:** High for source editing and queue writes; Medium for discovery/config reads.  
**Tests before change:** service-level path authorization and JSON Pointer tests; render answer/failure protocol; route tests that assert delegation rather than filesystem details.

### A2. Core services form a construction cycle and cross private boundaries

**Priority/status:** P1, confirmed.  
**Evidence/trace:**

1. `AIProxyService.__init__` sets `prompt_review_service = None` (`zet/services/ai_proxy_service.py:20-33`).
2. `ZetApp.from_config` builds that proxy, injects it into `AssetService`, builds `PromptReviewService(asset_service=...)`, then mutates the proxy with the finished prompt service (`zet/app.py:178-239`).
3. `AssetService` reaches back through `ai_proxy_service.prompt_review_service` (`zet/services/asset_service.py:248-249`).
4. `PromptReviewService.recompile` reaches through `asset_service.worker_service` and calls private `_normalize_worker_name` and `_build_context` (`zet/services/prompt_review_service.py:245-250`).

**Cost:** services cannot be instantiated independently without partial objects or deep mocks; private worker mechanics are effectively public.  
**Refactoring risk:** High because prompt resolution participates in render staging and reset eligibility.  
**Tests before change:** isolated construction tests for each service; worker invocation contract test; render staging with/without condensed prompts; reset eligibility; failure rollback.

**Direction:** extract a stage-independent prompt artifact resolver/compiler runner used by Asset, Proxy, and Prompt workflows; inject it normally. Expose a public `WorkerService.run_named_worker` or move recompile orchestration into `WorkerService`.

### A3. Story and scene rendering have unclear ownership

**Priority/status:** P1, confirmed.  
**Evidence:** `StoryService` owns markdown CRUD/Git (`:216-523`), path/schema/default/migration logic (`:524-1035`), scene editing and validation (`:1037-1438`), reference resolution (`:1440-1517`), queue cleanup/render staging (`:1522-1652`), and image-picker projections (`:1655-1764`). `scene_render_compiler.py` separately owns IR, validation-like transforms, final prompt, local brief, and Forge Couple layout. `StoryService.stage_scene_render` still writes all artifacts and constructs the queue manifest itself instead of delegating orchestration.

**Cost:** schema, compilation, and queue protocol changes touch a 1,765-line service; unused earlier compilers remain beside the active compiler.  
**Refactoring risk:** High.  
**Tests before change:** split current story tests into document repository, schema/migration, compiler golden, reference resolver, and render-staging protocol suites. Do not split until the current V3 policy is decided and failures are resolved.

### A4. Multi-file domain operations are not transactional

**Priority/status:** P1, confirmed design gap.  
**Evidence:** `CostumeService.create_costume` writes a template then calls `AssetRepository.create_asset` eight times (`zet/services/costume_service.py:112-153`); any later failure leaves a partial costume. Rename writes/unlinks the template before sequentially saving affected assets (`:157-205`). `ExpressionService.create_expression` writes the definition before creating its asset (`zet/services/expression_service.py:124-175`), and update renames/unlinks before saving the asset (`:181-231`). Each `create_asset/save_asset` rewrites and backs up `Assets.json` independently.

**Cost:** disk errors or validation failures can leave files and asset records disagreeing, while repeated writes create eight backups for one logical costume command.  
**Refactoring risk:** High for rollback semantics and existing partially completed data.  
**Tests before change:** fault-injection after each write; idempotent retry; batch asset creation/update; rollback and recovery journal behavior. A small domain transaction/unit-of-work around staged temp files is preferable to a database-scale abstraction.

### A5. Runtime imports depend on repository layout and `sys.path` mutation

**Priority/status:** P2, confirmed.  
**Evidence:** all five prompt workers mutate `sys.path` to import `Scripts/Run_*` modules; `CharacterOnboardingService`, `PromptReviewService`, and the web module do the same (`zet/workers/*_prompt_worker.py:6-12`; `zet/services/character_onboarding_service.py:19-28`; `zet/services/prompt_review_service.py:15-20`; `zet/web/app.py:26-34`). Tests repeat the same setup. There is no `pyproject.toml` or `setup.py`, although the README suggests `pip install -e .` (`README.md:134`).

**Cost:** imports work only from the expected checkout layout; scripts are both command entry points and private libraries. Packaging, tooling, and isolated testing are fragile.  
**Refactoring risk:** Medium.  
**Tests before change:** launch from a non-project working directory; import every worker in a clean process; invoke each script by file and module; Windows/macOS smoke tests.

### A6. Application and browser composition are monolithic

**Priority/status:** P2, confirmed maintainability concern.  
**Evidence:** `ZetApp` is an 814-line constructor/facade and `AssetRef` duplicates many service/facade operations (`zet/app.py:35-813`). Every route calls `_app(config_path)`, rebuilding the complete graph (`zet/web/app.py:37-38` and route call sites). `create_app` registers all API domains in one function (`zet/web/app.py:1085-2723`). One global JavaScript file owns all page state and handlers (`zet/web/static/zet.js`), while one HTML file owns all page markup.

**Cost:** unrelated feature edits collide in the same files, dependency construction is repeated per request, and route/frontend tests become broad fixtures.  
**Refactoring risk:** Medium. A naïve singleton would change live config reload behavior, so lifecycle must be decided first.  
**Tests before change:** app lifecycle/config reload; router contract tests; frontend smoke tests per page; shared context/state navigation tests.

### A7. The current test suite mixes characterization with stale implementation contracts

**Priority/status:** P0, confirmed by execution.  
**Evidence:** `python3 -m pytest -q` on this working tree produced 16 failures/85 passes. Examples:

- Three Body Reference race-rule tests build `Config/` and `_Lib/` fixtures without `config.toml`; the compiler now reloads config through `Scripts.Library_Paths` and fails before the behavior under test.
- Story tests still expect Markdown-only render staging, V1 migration, and “v2” outputs, while `StoryService.stage_scene_render` now requires `.scene.json` V3.
- Costume prompt tests assert exact old orientation text after configuration/compiler changes.
- `test_stage_scene_render_with_builder_writes_v2_artifacts` asserts exact sentence casing rather than semantic placement; current output contains the same fact with capitalization after the bullet label.

**Cost:** failures do not cleanly distinguish regression from intentional migration, and exact prose assertions inhibit safe prompt compiler refactoring.  
**Refactoring risk:** High until triaged.  
**Tests before change:** first classify each failure as expected migration or regression; then replace accidental string/casing assertions with stable semantic/artifact contracts where exact prompt text is not itself the product requirement.

## Recommended refactoring sequence

1. **Freeze and classify the current behavior (P0).** Resolve the 16 failures without broad refactoring. Record golden V3 scene files, compiler outputs, queue manifests, and active pipeline definitions. This is a dependency for every later step.
2. **Decide and execute the `PROMPT_REVIEW` migration (P0).** Inventory external libraries and clients. Either document a supported compatibility window with explicit adapters, or remove the stage-only worker/routes/facade/config/tests and rename active prompt-inspection concepts. Update docs in the same stage.
3. **Define persisted protocol types (P1).** Version and type reference records, scene schemas, and queue manifests with tolerant readers. Do this before moving code so structural refactors do not silently change persisted formats.
4. **Centralize queue protocol paths and scanning (P1).** Extend `AIProxyPathService` or a focused queue repository; make Story, analysis, prompt artifact, Render Console, and proxy workers consume the same protocol primitives. Preserve the on-disk layout.
5. **Break the service cycle (P1).** Extract prompt artifact resolution/compilation and a public named-worker execution API. Remove post-construction mutation and private-method calls.
6. **Extract web-owned workflows (P1).** In order: character/phase discovery; local backend discovery; source editor service; manual render submission service. Routes should validate HTTP input, call `ZetApp`/services, and serialize results.
7. **Make compound writes recoverable (P1).** Add batch repository operations and staged writes/rollback for costume and expression commands.
8. **Split story responsibilities (P1/P2).** Separate story document/Git operations, V3 scene document normalization/migration, reference resolution, render compilation, and render-task staging. Delete the confirmed legacy helpers after characterization.
9. **Consolidate compiler and repository infrastructure (P2).** Extract shared compiler orchestration, dataclass codecs, atomic JSON writer, view resolver, and worker protocol utilities one at a time behind existing behavior.
10. **Modularize composition/UI (P2).** Split FastAPI routers and browser page modules after backend boundaries stabilize. Decide config reload/lifecycle before caching the application facade.

Dependencies: 1 → all; 2 → documentation cleanup and prompt terminology; 3 → 4/7/8; 4 → moving Render Console workflow; 5 → web route extraction; 8 → deletion of scene legacy code; backend router boundaries should precede JavaScript/HTML splitting.

## Required characterization tests

Before implementation approval, add or repair these suites:

1. **Active pipeline inventory:** load every supported `Pipelines.json`, dynamically import every configured worker, and assert legal stages/actors/workers. Include an explicit policy test for `PROMPT_REVIEW` presence or absence.
2. **Asset transition matrix:** each pipeline/stage/actor, missing-reference `ADD_REF`, worker failure, render retry, regeneration, lock promotion, and legacy-stage migration.
3. **Queue protocol:** exact manifests and folder transitions for text, local image, manual render, scene render, prompt analysis, stop/monitor, transient retry, archive, stale claims, and concurrent claims.
4. **Reference round trips:** every reference role/kind through storage, workers, compilers, queue, Render Console, and harvester; unknown fields and old schema versions.
5. **Scene migrations:** real V1/V2/V3 fixtures, load-only behavior, normalized V3 output, unknown fields, backups, and failed migration rollback.
6. **Prompt compiler goldens:** all five asset pipelines plus scene final/local/Forge Couple prompts, source maps, dependency manifests, and validation outputs. Mark which prose is contractual and which assertions should be semantic.
7. **Compound command failures:** injected failures at every costume/expression template and asset write; retry and recovery.
8. **Web boundary contracts:** routes mock public facade/service methods only; source-edit authorization; render answer/failure; live config reload.
9. **Documentation smoke checks:** supported launcher, configured route inventory, referenced files, and schema field inventory.
10. **Cross-platform paths/imports:** run from outside the checkout with absolute/project/library/legacy paths on Windows and macOS.

## Items requiring human decisions

1. **Is `PROMPT_REVIEW` unsupported everywhere, or only retired for newly onboarded/current library pipelines?** This determines whether legacy routes, AI worker/config, stage transitions, and tests are deleted or isolated behind a compatibility adapter.

`PROMPT_REVIEW` is unsupported everywhere.

2. **Should the browser “Prompt Review” name remain for render-queue prompt inspection?** If yes, reserve “prompt artifact review” for that UI and remove stage terminology; otherwise rename it to avoid collision with the retired stage.

Change the browser "Prompt Review" to "Prompt Inspection" to avoid confusion.

3. **Must V1/V2 Scene Builder JSON migrate automatically, remain read-only, or be rejected?** Current code rejects it while tests expect migration.

No migration, be rejected.

4. **Are Markdown-only scenes still renderable?** Current `stage_scene_render` requires `.scene.json`; several tests and older docs assume Markdown can stage directly.

No. All scenes must use the current .scene.json format.

5. **What compatibility guarantee applies to queue/reference manifests consumed on other machines?** This sets the versioning/deprecation window before typed models are introduced.

All machines are upgraded together. Manifests with unsupported versions are rejected with a clear error.

6. **Should relative paths outside known library roots mean project-relative or current-working-directory-relative?** Current service and script behavior differs.

Since the scripts live in the project, relative paths should mean project-relative. All paths outside the project should be full paths constructed from config.toml base paths.

7. **Should config changes take effect on every request or only after explicit reload/restart?** This determines whether `ZetApp` can be application-scoped instead of reconstructed for every route.

Explicit reload/restart. Explicit reloads should include the "Save Project Settings" on the Local Image Config page and any other page that exposes config values to change, but no provision needs to be made for config being modified outside of the web dashboard.

8. **What is the atomicity expectation for compound file commands?** If partial costume/expression creation is unacceptable, recovery/rollback is a P1 correctness requirement rather than optional cleanup.

These operations should be atomic - all succeed or rollback.

9. **Are public-looking helpers in `scene_render_compiler.py` and `StoryService` imported by untracked personal scripts?** Confirm before deleting the D1 set.

There are no untracked personal scripts.

## Implementation Status

### P0 implemented and verified.
- Reproduced baseline: 16 failed, 85 passed.
- Removed retired prompt-review worker, routes, transitions, config, and facade actions.
- Enforced rejection of PROMPT_REVIEW.
- Renamed active terminology to Prompt Inspection / AIPromptAnalysis.
- Updated V3-only characterization tests and current docs.
- Fixed Stable Matrix metadata harvesting.
- Diff: 24 files, +172 / -712.
- Tests: python3 -m pytest -q → 101 passed, 1 existing warning.
- git diff --check passed.
- No P1+ work performed.

### P1 implemented and verified.
- Revalidated the P1 findings against the current repository before editing; the documented boundary violations, service cycle, protocol duplication, story ownership, and compound-write risks still matched.
- Added typed/versioned queue and reference protocols with clear unsupported-version errors, and centralized queue paths and state scanning without changing the on-disk layout.
- Removed the Asset/AI proxy/prompt service construction cycle and private worker calls through an injected prompt-artifact service and public named-worker API.
- Extracted reusable discovery, backend lookup, source-edit, and manual-render workflows from `zet/web`; routes now delegate to backend services.
- Split V3 scene normalization, story reference resolution, and render staging from `StoryService` behind compatibility-preserving delegation.
- Added batch asset persistence plus atomic costume/expression writes and rollback behavior.
- Corrected obsolete launcher, route, file, repository, and schema documentation.
- Diff: 38 files, +1,610 / -947.
- Tests: `python3 -m pytest -q` → 121 passed, 2 subtests passed, 1 existing warning.
- `python3 -m compileall -q zet AI_Manager Scripts` and `git diff --check` passed.
- No P2+ work performed.

### P2 implemented and verified.
- Revalidated every P2 finding before editing. D1, R2-R5, M2, A5, and A6 still applied; P1 had already mitigated parts of story ownership, queue paths, prompt view lookup, web import mutation, and AI result-model placement.
- Removed the confirmed declaration-only Scene Builder and scene-render compiler helpers, and moved story workflow dataclasses to `zet/models` with compatibility re-exports.
- Extracted shared compiler support, repository dataclass/atomic-JSON primitives, view resolution, and proxy-worker filesystem transitions while preserving stage- and repository-specific behavior.
- Standardized unknown relative paths as project-relative, retaining the separate scene library-relative storage contract.
- Packaged `Scripts`, replaced application-layer `sys.path` mutation with package imports, preserved direct-file entry points and public helper imports, and added outside-checkout import/launch coverage.
- Made `ZetApp` application-scoped with explicit reconstruction after dashboard config saves, and extracted pipeline-control routes into a focused router.
- Added characterization coverage for repositories, view/path behavior, proxy claim concurrency, packaged imports/entry points, story model compatibility, and application reload lifecycle.
- Tests: `python3 -m pytest -q` → 136 passed, 2 subtests passed, 1 existing warning.
- `python3 -m compileall -q zet AI_Manager Scripts` and `git diff --check` passed.
- Preserved the pre-existing `Docs/ToDo.md` change; no P3 or unrelated cleanup performed.
