# System contracts

These are supported by implementation and repository instructions, with earlier test evidence retained in Git history. [Testing](Testing.md) owns the current S1–S4 baseline and coverage approval. A scenario verifies only its named assertions; many contracts below require source inspection because dedicated tests were retired. Do not add coverage without explicit approval. See [DEVELOPMENT](DEVELOPMENT.md) for observed results.

## 1. Reusable behavior belongs behind the web layer

- **Rule/why:** [AGENTS](../AGENTS.md) requires reusable workflow logic in services/repositories/models or pipeline scripts, with new dashboard actions exposed through `ZetApp`, `AssetRef`, or a focused service. UI technology must not own business transitions. Retired Streamlit and standalone Render Console receive no new features.
- **Implementation/impact:** [zet/app.py](../zet/app.py), [web routers](../zet/web/), [services](../zet/services/). Existing `RenderConsoleQueue` remains queue support used by the current web app; its presence does not revive the standalone UI.
- **Verify:** Review dependency direction and the service interface. S1/S3 exercise dashboard authoring/job actions; no complete static web/backend boundary check remains.

## 2. A universe owns its library, not the shared queue

- **Rule/why:** bound universe paths, request context, and manifest ownership must agree. Shared queue location does not grant access to another universe's results. Browser file reads resolve links before allowing only the selected universe or repository `Shared_Library`; prompt-analysis records are bound to their containing/requested universe.
- **Implementation/impact:** [UniverseService.bind_config](../zet/services/universe_service.py), request `ContextVar` and `/api/file` in [create_app](../zet/web/app.py), [PathService.resolve_served_path](../zet/services/path_service.py), `_ask_belongs_to_run` in [local character service](../zet/services/local_character_asset_pipeline_service.py), and ownership checks in [AIAnswerHarvester](../zet/services/ai_answer_harvester.py). Missing ownership is assigned Moonsea only for legacy config.
- **Verify:** All fast scenarios run in the seeded Test universe. Disposable probes cover allowed/outside/foreign file resolution and malformed universe selection; they do not exercise every cross-universe route. New coverage needs approval.

## 3. Authoritative images and a derived index are different stores

- **Rule/why:** [EntityLibraryRepository](../zet/repositories/entity_library_repository.py) owns `catalog.sqlite3`; [LibraryIndexRepository](../zet/repositories/library_index_repository.py) owns a rebuildable machine-local cache outside Git/Dropbox. Losing the cache must not imply loss of authored state. Published index generations/freshness, not partial scans, drive indexed queries.
- **Implementation/impact:** [LibraryIndexService](../zet/services/library_index_service.py), entity library, SQL-filtered inventory paging, compilation dependencies, image references.
- **Verify:** Inspect repository schema/root validation and generation publication. S1/S2 use library state incidentally; disposable checks cover catalog paging and unavailable-blob metadata, but no dedicated migration/corruption/index freshness scenario remains. Read any rebuild/migration command before use.

## 4. Traditional character generation stays retired

- **Rule/why:** the six traditional character pipelines in [pipeline_retirement.py](../zet/services/pipeline_retirement.py) cannot execute through guarded generation/worker paths. Active local workflows reuse compiler functions without restoring old stage-driven generation.
- **Implementation/impact:** `WorkerService.run_current_worker`/`run_named_worker`, guarded app/web actions, local Body/Head/Assembly/Dressing services. Retained assets may still be inspected/reviewed or used by supported consumers.
- **Verify:** Inspect `require_active_pipeline` callers. S2 verifies active local Assembly/Dressing with seeded prerequisites; it does not exhaustively exercise retirement guards.

## 5. Approved local sources are available publications

- **Rule/why:** `locked_assets` requires a recorded lock and an existing universe-owned permanent image. Original batch/candidate files, saved hashes and advisory upstream drift do not invalidate publication. Manual file replacement is trusted. Explicit catalog archival revokes availability; explicit relocking can restore it. A published chain commits catalog rows/references together and uses a receipt plus journal to recover its separate local JSON state.
- **Implementation/impact:** [LocalAssetStoreService](../zet/services/local_asset_store_service.py), [LocalAssetPublicationRecoveryService](../zet/services/local_asset_publication_recovery_service.py), [StorageRecoveryService](../zet/services/storage_recovery_service.py), [LocalAssetSourceService](../zet/services/local_asset_source_service.py) and entity publication.
- **Verify:** S2 covers publication and downstream prerequisites; disposable checks cover catalog rollback, committed/uncommitted journal recovery, manual replacement, absent history/files and archive/relock. See [ADR 0023](DECISIONS/0023-streamlined-image-integrity.md) and [ADR 0029](DECISIONS/0029-recoverable-local-asset-publication.md).

## 6. Ranking and human review define candidate eligibility

- **Rule/why:** rendered candidates enter human review and ranking without an intermediate defect verdict. Rankings must contain every submitted survivor exactly once, with unique IDs/reasons. Body-Reference ranking excludes human-rejected candidates; other pipelines retain their existing human-review behavior. Automatic FRONT selection requires the current original Luna #1, valid current image bytes, and no human rejection. Manual rank adjustments preserve Luna's original order.
- **Implementation/impact:** [local_candidate_review_contract.py](../zet/services/local_candidate_review_contract.py), [local_image_evaluation_service.py](../zet/services/local_image_evaluation_service.py), [local_image_pipeline_policy.py](../zet/services/local_image_pipeline_policy.py), and the four local pipeline services.
- **Verify:** S2 waits for a one-candidate ranking before selection/lock. It does not cover multi-candidate ordering, stale evaluation or human-rejection overrides; inspect the shared ranking and selection checks. Gate-free records use `review_version: 3`; library path-format versions remain independent.

## 7. Queue publication and consumption preserve ownership and readiness

- **Rule/why:** publish a complete hidden staging bundle by atomic rename; inspect answers using metadata; admit them only after inventory verification with applicable producer/local routing. Verify bytes while copying shared answers into local staging, atomically publish admission, then remove shared payload. Admitted local files are not repeatedly rehashed. Superseded attempts and durable receipts prevent late/duplicate application.
- **Implementation/impact:** [FileProxyClient](../zet/services/file_proxy_client.py), [AIQueueLifecycleService](../zet/services/ai_queue_lifecycle_service.py), [workflow_storage.py](../zet/services/workflow_storage.py), [AIAnswerHarvester](../zet/services/ai_answer_harvester.py), manual publication/submission. Changes affect all AI producers and consumers.
- **Verify:** S2/S3 exercise private prepared answers and result application; S3 includes one render failure/retry. Generic harvester, foreign/missing-route, stale-attempt, copy-failure and duplicate branches are not independently covered. A separately requested live check exercises actual Narrative dispatch, not all these cases.

## 8. Persistence updates preserve revisions and locking

- **Rule/why:** traditional asset batches belong to one character/phase with unique IDs and current revisions; saves increment revisions and preserve unrelated stored keys. Workflow lock files intentionally persist to avoid splitting owners across different inodes; same-thread nested locks are supported. Atomic writes protect individual files, not arbitrary multi-file sequences.
- **Implementation/impact:** [AssetRepository.save_assets](../zet/repositories/asset_repository.py), [json_storage.py](../zet/repositories/json_storage.py), [atomic_file_service.py](../zet/services/atomic_file_service.py), [file_lock](../zet/services/workflow_storage.py); all state/review writers. Do not remove lock files as routine cleanup.
- **Verify:** Inspect revision comparison, atomic replacement and lock boundaries when changing writers. S1/S3 verify save/reload/persistence; concurrency, rollback and traditional-asset revision conflicts have no dedicated maintained scenario.

## 9. Reference order, view domains, and schema gates are contracts

Local character batch advice requires an existing current-candidate image file;
historical receipt or checksum metadata does not block review. Explicit Re-evaluate
refreshes hashes as bookkeeping. Admission remains fenced by the domain lock,
cancellation and current candidate/attempt/evaluation ownership. Wizard/Minor Character advice also uses current owned files without historical
receipt/hash requirements; input/attempt/selection fences remain. See
[ADR 0021](DECISIONS/0021-file-based-local-image-availability.md), which supersedes
the local batch availability portion of ADR 0017.
Local ComfyUI/Ollama work stays non-preemptive and serial,
while the two independent Codex slots may execute only requests already published
by those domain owners. [ADR 0017](DECISIONS/0017-image-harvest-admission.md) records
this completion barrier and its isolated validation boundary.

- **Rule/why:** prompts, numbered image citations, `image_inputs`, and bundled bytes must share ordering. Render modes/roles and prompt schema are validated centrally. Body/head view conditioning is independent; anatomical left/right differs from screen left/right. Unsupported document/catalog versions fail rather than being guessed.
- **Implementation/impact:** [chatgpt_prompt_contract.py](../zet/services/chatgpt_prompt_contract.py), [PromptTemplateService](../zet/services/prompt_template_service.py), [view_conditioning_service.py](../zet/services/view_conditioning_service.py), [ImageCatalogRepository](../zet/repositories/image_catalog_repository.py); compilers, queue snapshots, render adapters.
- **Verify:** S2/S3 exercise limited compilation/attachment packaging. View-tag permutations, unsupported schemas and exhaustive ordering validation have no dedicated scenario. Inspect compilers and both producer/consumer; do not sort references after compilation.

## 10. Machine-local storage is configured and bounded

- **Rule/why:** machine-local operational state and disposable indexes resolve beneath `[Storage].Root` through [StoragePathService](../zet/services/storage_path_service.py); relative child paths cannot escape or overlap the creative library/shared queue. Missing configured volumes fail clearly rather than redirecting writes to the old C: location. The shared `BaseAIQueuePath` remains transport-owned.
- **Retention:** keep one published index generation and parsed payloads only for current source fingerprints. Retain completed queue details for seven days by original completion time, and prune only after a verified success receipt. Missing receipts, errors, unknown ownership, image-admission proof and lock files are protected. `catalog.sqlite3`, authored library data, and library-owned workflow records are outside machine-storage maintenance.
- **Implementation/impact:** [ConfigService](../zet/services/config_service.py), [LibraryIndexRepository](../zet/repositories/library_index_repository.py), [StorageMaintenanceService](../zet/services/storage_maintenance_service.py), [manage_storage](../zet/scripts/manage_storage.py), queue lifecycle/coordinator and task workflow root.
- **Verify:** the four fast E2E scenarios run on isolated configured storage. Use the read-only storage report/preview before migration. `--apply`, `--rebuild-index` and `--compact-indexes` are explicit operations; old storage removal requires a reviewed, quiescent cutover manifest.

Qwen Image 2.1 prepared references are job-local derivative snapshots: source bytes
and ordering remain intact, dimensions only shrink to aligned sizes, and pending
submission recovery verifies the saved workflow fingerprint and prepared-image
hashes before resuming. Configuration changes apply only to new submissions.

  ## 10. Legacy geometry is archived; migration preserves history

- **Rule/why:** saved 3D layouts and their coordinate conventions remain historical; Narrative migration derives preliminary prose staging from reviewed final images. It never converts geometry or makes legacy outputs selected Narrative candidates.
- **Implementation/impact:** [offline archive](../Archive/scene-builder/README.md), [NarrativeMigrationService](../zet/services/narrative_migration_service.py), Narrative records and entity image imports.
- **Verify:** all 28 imported final-image checksums match their sources; each migrated scene has backdrop/subscene/assembly targets. Existing sources and other stories are preserved. No maintained scenario exercises archived geometry.

## 11. Narrative owns its records and frozen job inputs

- **Rule/why:** Narrative authoring/generation must not call Scene Builder creation/loading/staging. Jobs pin reference bytes and assembly inputs; source changes must not silently alter a submitted job. Selected/locked images require protection checks before deletion. Server-owned layer filenames/metadata cannot be accepted as arbitrary client paths.
- **Background and assembly policy:** new subscene text jobs freeze the transparency preference; mismatched or legacy-absent flags cannot automatically replace current prompt/review state. Render sends entered prompt text unchanged. Harmonization preserves the placed composite as a frozen reference/comparison, but retains the full output rather than enforcing pixel protection; finishing retains its original protection contract.
- **Implementation/impact:** [NarrativeRepository](../zet/repositories/narrative_repository.py), [NarrativeGenerationService](../zet/services/narrative_generation_service.py), [NarrativeAssemblyService](../zet/services/narrative_assembly_service.py), [NarrativeSceneService](../zet/services/narrative_scene_service.py), router.
- **Verify:** S1/S3 operate exclusively through Narrative UI/API/storage and verify persisted assembly publication/display. Inspect source freezing, layer binding, protected deletion and attempt checks directly; the fast suite does not assert every protection/provenance case.

## 12. Production local renders use supported profiles

- **Rule/why:** [require_qwen_profile](../zet/services/local_render_policy.py) accepts ComfyUI profiles with `model_family=qwen-image-2.1` and registered diffusion models. Historical Stable Matrix files are not production-policy exceptions. AGENTS says ComfyUI normally runs through AI Proxy; direct operation requires asking for ComfyUI Desktop.
- **Worker boundary:** ordinary issue-worker loads of local/production configuration remain blocked. The explicit `ConfigService.load(..., worker_render_root=...)` path returns a Config with creative paths confined to an existing private `test-results/` directory; AI_Proxy queue, storage and preset settings remain available for a separately budgeted render harness. It does not authorize writing to the normal creative library.
- **Implementation/impact:** [LocalRenderBackendService](../zet/services/local_render_backend_service.py), queue producers, ConfigService normalization, [Local_Render_Presets.json](../Config/Local_Render_Presets.json).
- **Verify:** Inspect profile validation and producer/backend consumers. Fast tests use prepared images. The separately requested live check verifies configured Narrative final-assembly rendering; skipped or unrequested live checks establish no service/model availability.

Narrative logical costume references resolve approved current exact-view images;
unavailable/stale bindings remain review issues. Jobs freeze the resolved bytes and
ordered references at submission. Legacy-image catalog blobs survive scene deletion.
Costume deletion uses the same exact costume asset set for confirmation and
purge; a character/phase origin prefix alone does not establish costume ownership.
Candidate imports and migration resumes are idempotent; changed source briefs cannot
silently overwrite authored inputs or selected/locked outputs. Retired owned answers
are superseded without publishing into source or Narrative records.

## 13. Image editor saves are atomic and preferred keys preserve aliases

- **Rule/why:** One editor save updates image fields, organization, asset descriptors, and preferred reference together. A failed validation leaves the authored asset unchanged. A preferred-key change does not deactivate older keys that existing templates or scenes may use.
- **Implementation/impact:** `EntityLibraryService.update_asset`, `assets.preferred_reference_key` in entity catalog schema 3, and `PATCH /api/entity-library/assets/{asset_id}`. Inventory reads do not synchronize pipeline images; publication writes and explicit reconciliation own discovery.
- **Verify:** Run disposable schema/backfill, collision, alias, rollback, and targeted-read diagnostics. The approved E2E suite does not cover inventory edit/save races or preference migration; obtain approval before adding that coverage.

Explicit archival deactivates bound logical references in the catalog transaction.
Discovery cannot archive images or restore an explicit archive based on source
absence/presence. Destructive library actions require confirmed image IDs and
managed-version tokens, show recorded consumers, and may proceed with usages.
Surviving authored references are retained and may become unresolved.

## 14. Render positions are independent of candidates and ranking
Eight-slot grids keep stable physical positions and candidate bindings. A completed Luna ranking may change the browser's card presentation order, but it never changes the candidate's physical slot or its slot actions. Supplemental generation fills empty slots only; reserved prerequisites and failed renders are occupied. Replacement candidates/jobs have distinct identities, and changed character evaluations receive a new fence. Late results cannot fill another candidate's position. Selected and locked images require explicit protection transitions before slot replacement. Clear detaches membership while retaining historical artifacts; normal reruns still follow their existing explicit destructive behavior.

Character slot changes hold the state lock and persist pending candidate IDs before background submission. An independent slot collector owns `slot_runner.lock`; it does not block unrelated slot actions on the batch runner. Existing batch runners exclude these independently managed additions. Empty capacity is not Run All Remaining work. Image Generation workspace assignments are universe-owned and server persisted; newly generated results return by child index, never completion order. Services own these transitions, browsers own only presentation/draft inputs. [ADR 0007](DECISIONS/0007-stable-render-slots.md) and [render_slot_service.py](../zet/services/render_slot_service.py) own the contract. Existing S2/S3 cover baseline compatibility; the separately approved disposable checks cover the reported slot issues. Full Body/Head generation and general restart recovery remain unverified by maintained scenarios.

## 15. Recorded image usages preserve identity

- **Rule/why:** Direct asset IDs remain anchored to their image even beside historical logical keys; key-only usages follow the current key. Zet mutations update just their affected consumers, with local pending markers for recovery. Ordinary reads/startup/saves never rebuild global usages. Unreadable consumers retain their observations during explicit audits/rebuilds.
- **Implementation/impact:** [ImageUsageService](../zet/services/image_usage_service.py), `NarrativeRepository.write`, template/source writers and `EntityLibraryService.usage_for_asset`. `GET /api/entity-library/usages` reads observations; POST `/usages/check` reports and POST `/usages/rebuild` explicitly refreshes readable consumers. Resolve actual files when compiling/submitting/assembling/exporting; failure affects only that dependent operation.
- **Verify:** S1/S3 cover representative authoring; disposable service/API/browser checks cover replay, direct/key identity, external edits, audits and confirmed deletion. No new permanent scenarios.

## 16. Library-owned paths are universe-relative and versioned

- **Rule/why:** Typed paths persisted by a library-owned record use forward-slash paths relative to the owning universe. Readers resolve them from the configured bound root and reject traversal or a foreign universe. Absolute legacy references to an existing exact universe-relative location resolve under the current root, including versionless records; no basename search is performed. Subsequent writes persist portable paths. The offline updater remains available for explicit bulk conversion. Free text, document/job-relative names, source-controlled templates, logical keys, and IDs are not path-migrated.
- **Compatibility:** `library_path_format_version` is independent of workflow/review versions. New readers accept legacy and version 1 records and reject unsupported versions. Deployments and code rollback must check the library marker before opening converted data; recovery to an older release uses the retained library copy.
- **Implementation/impact:** [LibraryReferenceService](../zet/services/library_reference_service.py), [PathService](../zet/services/path_service.py), the storage owners listed in [DATA_MODEL](DATA_MODEL.md), and [normalize_library_references](../zet/scripts/normalize_library_references.py).
- **Verify:** Run the updater only while Zet servers and harvesters are stopped. It applies atomically per record, verifies operational references and saved image hashes, and writes a universe marker only after the full scan and route verification succeed. The approved S1-S3 baseline does not prove every relocation branch; use disposable fixtures for those checks.

## 17. Reconstruction corrections retain explicit intent

Source observations and intended output have different authority. Explicit changes override conflicting source facts; destination style controls rendering treatment. A true-up cannot treat deliberately removed equipment as identity drift. Changed target intent gets new task/revision identity and invalidates old approvals; a corrected front requires explicit selection before downstream views become current.

Original reconstruction sources are analysis-only. Styled candidates may enter true-up img2img renders; selected styled fronts may anchor character views. Reports/corrections bind universe, target hash, managed source version and host candidate/selection/front identity. Snapshot hashes describe captured inputs; existing files are not policed against them. Repeated application reuses an existing attempt; retries retain submitted inputs/seed. Image Generation reserves additional slots and checks the selected source again at dispatch. See [ADR 0013](DECISIONS/0013-shared-reconstruction-target-and-true-up.md). Model reports are optional artistic advice: custom feedback needs no compatibility approval and takes precedence over earlier direction. Failed review does not block choosing a rendered wizard image. Software validation does not prove visual compliance.

Minor Characters use fresh named universe-local workspaces with one current board for style and each view. Selected style enables independent view alignment; selecting an aligned view gates its true-ups. Only generated view true-ups can lock; carry does not change eligibility. Selection requires current slot membership; immutable Inventory locks survive slot replacement, refinement, undo and deletion. Refinement carries at most one selected image in its same slot and clears other slots. One undo per board restores prompt/supporting state with empty slots and no redo. Private frozen sources support replay without image history. Revisions fence stale mutations; late results cannot restore discarded membership. Comparison is display-only. Retired records are excluded without migration. See [ADR 0015](DECISIONS/0015-minor-character-alignment.md); queue ownership and image integrity remain applicable.

Restarting a view removes only that view's current working membership and selection, then creates a fresh alignment from the selected style image. Restarting STYLE resets all stage boards and analysis-derived inputs, while retaining original references and immutable Inventory locks. When any view work exists, the STYLE restart API requires explicit confirmation. Every reset increments board revisions; late results from discarded candidates cannot restore membership.

## GitHub capture and production promotion

Frozen reports bind request IDs to repository/content hashes. Uncertain creation
is reconciled without blind reposting. Screenshot bytes are validated and links
pin evidence commits. Worker ownership is token fenced and never automatically
stolen; original report/images remain acceptance inputs. Unknown quota pauses work.
Production process/config identity and new-boot/revision health fence promotion.
Authored-data migration gates differ from code rollback; no library/queue/catalog
reset is implied. [GitHub task workflow](GitHub_Task_Workflow.md) owns details.

## Shared creative AI ownership (2026-10-16)
All new creative provider execution is proxy-owned. Trusted Codex registrations
use a separate bounded cloud lane; local backend preparation and non-preemption
remain intact. Zet verifies the producer/universe/original request and complete
inventory before application, persists results/receipts before cleanup, and never
replays an ambiguous execution. Foreground and background collection share locks
and handlers. Model restrictions come from one cached capability catalog and are
validated on submission as well as in the popup. See [Shared AI jobs](COMPONENTS/AI_JOBS.md).

## Character template revisions

Repository master-template edits may pass the deployment dirty guard only through
an unchanged captured snapshot, verified merged PR, merge ancestry in the target,
and exact published template blobs. The final check shares a cross-process fence
with master promotion. Publication/reconciliation leaves live templates/index/HEAD
intact; rollback retains the old release's edits. Other tracked edits still block.
See [ADR 0026](DECISIONS/0026-template-edit-publication.md).

New character prompt reviews are text-only and retain frozen sources, all eight compiled view prompts, selectable corrections and master baselines. Exact selected edits must not overlap or apply to changed source baselines. Acceptance creates a compiled READY batch version, including when no changes are chosen. Historical image-evidence proposals remain readable. Only compiled READY versions can become active or update masters; editing a proposal creates a child. Activation changes future render inputs, never queued asks or published image bytes. Explicit master promotion validates every changed source before writing and journals partial failures for explicit replay. Per-view custom references resolve only to a selected, available, non-rejected candidate in the same batch and preserve matching prerequisite bindings/order. See [ADR 0024](DECISIONS/0024-character-template-versions.md).

Post-render observations are operator-triggered. Private Character.md trials in the four non-costume pipelines cannot activate sources, overwrite batch prompt artifacts, occupy gallery slots, or change selections. Two attempts for the selected rendered view use frozen prompt/reference bytes; suggestions may edit any valid Character.md location regardless of view. Cancellation fences late results. Keep requires complete attempts and rechecks the source hash and active batch revision, then writes a recoverable accepted source/version and recompiles available views. Assembly may use such an accepted version for later generation while retaining its original front gate. Unopened views use the accepted version when their real inputs become available.

## Removable storage
Unavailable resources must not be interpreted as empty authored/request state. Preserve the last committed derived index on incomplete scans and never silently recreate an observed authoritative catalog. Automatic recovery retains one execution per transport attempt, owner/attempt fencing and immutable published bytes; a fresh attempt is subscriber-owned. Stopped/cancelled/completed/protected work remains excluded. See [ADR 0022](DECISIONS/0022-removable-storage-recovery.md).


## Staged character refinement

Body/Head character batches require explicit prompt acceptance and Continue to open generation stages; Costume-Dressing uses the independent mode gates below. Skip improvement explicitly accepts a successfully compiled snapshot of current masters without AI analysis. Saving a manual READY proposal leaves active batch inputs and masters unchanged; Use for new renders explicitly accepts it. Restart from masters creates a fresh analysis without inherited overlay text or deleting history. Same-side predecessor references and matching pipeline prerequisites retain ordered roles. Fresh renders resolve current selections and recompile accepted sources; retries replay frozen inputs. Existing batches are not silently enrolled. Changed same-batch references create warnings only: no automatic downstream deletion, reselection, review, generation or publication gate.

Refinement compares a frozen working image with an operator-chosen subset of selected views. Comparisons are analysis-only; targeted renders use exactly the chosen working image as their edit base. Explicit adoption verifies the session and current batch selection, creates a new same-slot candidate, and preserves original/attempt history and immutable published bytes. Late analyses bind their analysis identity; render continuations bind immutable attempt/request identities. See [ADR 0025](DECISIONS/0025-character-review-stages-and-refinement.md).

## Costume rendering and adjustment gates (2026-10-26)

Costume-Dressing requires accepted governing prompts, matching Assembly snapshots and the chosen mode's actual inputs; it does not require Continue stages or an unused FRONT anchor. FRONT retains its existing dressing contract. Other views may reference only a different, available, non-rejected selected view in the same batch. A missing explicit source does not trigger substitution. New renders/staging/previews share preparation; retries preserve frozen inputs. Publishing follows actual captured lineage and existing cycle/ownership/locked-byte guards.

Costume adjustments change only the costume-owned Markdown. Scoped line replacements preserve unchecked view/mode contexts, source structure and reference order; source annotations never enter emitted prompts. Other selected views default unchecked; mirror defaults respect intentional asymmetry. Human diff approval precedes four private target-view renders. Trial images never enter gallery slots, selections or Inventory automatically.

Criteria and human accomplishment status persist at costume/view level across modes and batches. Accomplished items remain visible but are excluded from improvement analysis. Checklist writes and diff approvals reject stale revisions. AI assessments cannot mark accomplishment. Frozen evidence, seeds, profiles, source hashes and active revisions fence replay and promotion. Explicit master save may preserve partial progress and is recoverable/idempotent; late cancelled/obsolete work cannot publish. Existing costume Character.md sessions are read-only, and retired Pilot continuations terminalize before dispatch. See [ADR 0033](DECISIONS/0033-costume-post-render-adjustments.md).
