# Narrative image production workflow
Status: complete
Related issue/specification: [Image Production Abstraction](../../Docs-Joe/Image%20Production%20Abstraction.md)

## Goal
Make Narrative the first consumer of the shared image production workflow. Story is the Asset Container, Scene is the Asset, and each target owns a Candidate Board. Preserve existing Narrative authoring and compatibility. Character Pipelines and Minor Characters are excluded.

## Current behavior
Narrative stores Story/Scene/target records in NarrativeStories. Targets have a mixed-quality eight-slot board. NarrativeGenerationService prepares, queues, retries, and collects through NarrativeProxyService. ImageCandidateBoardService currently owns allocation only. Narrative candidate actions, scene-text confirmation, backdrop reuse, assembly source binding, and draft cleanup write board state through separate paths. Cross-story backdrop candidates are exposed by the source picker before Inventory publication. Subscene Inventory save copies a selected or locked image as an independent item. The Narrative UI renders board cards itself and polls detail while jobs are active.

## Desired behavior
Expose reusable board policies while preserving Narrative ownership of authoring, storage, queue dispatch and finishing. Freeze a typed render handoff and captured inputs for generation and retry. Keep same-story working references, require a locked Inventory publication for new cross-story references, and preserve old pinned snapshots and NARRATIVE tags. Share board presentation and active-only progress refresh. Preserve mixed-quality v2 records and safely handle legacy records.

## Impact analysis
Board rules: zet/services/image_candidate_board_service.py, narrative_generation_service.py, narrative_scene_service.py, narrative_reference_service.py, narrative_assembly_service.py, narrative_scene_text_service.py.
Render handoff: narrative_generation_service.py, narrative_proxy_service.py, AI Proxy request interfaces and the supported render preset/settings adapters.
Publication and sources: entity_library_service.py, Narrative reference services, story_reference_service.py, image_catalog_service.py, zine/source consumers, narrative_router.py.
UI/docs: narrative.js, narrative.html, render_slots.js, Narrative component guide, code map, invariants, ADR index.
Compatibility uses existing Narrative JSON and Inventory catalog, with additive fields only where needed. Preserve universe isolation, ordered bindings, attempt fencing, confirmed destructive effects, Inventory authority, frozen retries, and ADR 0045 finished-image rules.

## Implementation steps
### WP1 — Candidate Board policy and state transitions
- Dependencies: none.
- Files/interfaces: image_candidate_board_service.py and Narrative target, generation, reference, assembly and scene-text services.
- Work: Add reusable target-scoped membership, flexible count allocation, explicit replacement, selection/lock transitions and protected-effect previews. Route every Narrative selection/lock/clear/reuse path through it. Lock implies selection; unlock retains selection; scene-text confirmation cannot switch away from a lock. Use state-bound approvals for individual and bulk destructive actions, rechecked under the repository lock. Remove candidate-owned artifacts only after board state commits.
- Acceptance: Counts 1–8 fill empty slots; replacement requires an explicit unchanged slot and current approval; lock/selection invariant holds for every route; captured downstream copies and Inventory records survive candidate deletion.
- Validation: Existing S3 plus disposable transition, confirmation and interrupted-cleanup checks.
- Status: complete. Flexible 1–8 allocation and shared membership/selection/lock helpers are implemented. Candidate actions, scene-text confirmation and local backdrop reuse use the helpers. Target reads repair a lone lock/selection mismatch and flag multiple locks. Explicit slot replacement now sends the expected occupant ID and the server refuses stale slot state. Candidate image/lettering cleanup is persisted before deletion and retried on refresh. A disposable API flow verified the bulk preview lists selection and lock, incomplete approval is refused, and complete approval clears the Draft.

### WP2 — Frozen render request and recovery
- Dependencies: WP1.
- Files/interfaces: Add an ImageRenderRequest service/model boundary; adapt NarrativeGenerationService and NarrativeProxyService; update supported AI Proxy manifest compilation if request settings require it.
- Work: Freeze universe/target/candidate, exact prompt, ordered input snapshots, render mode, dimensions, profile/checkpoint/settings, seed and readable provenance before dispatch. Reuse frozen requests for queue recovery and failed image Retry. Retry keeps candidate/slot/seed; Generate again makes a new candidate from current inputs. Keep text preparation retries distinct. Maintain old record readers and ownership/attempt fences. Cleanup shared snapshots only when no candidate or retained replay owns them.
- Acceptance: Frozen ordered inputs and settings are used after authoring changes; stale attempts cannot attach; restart reads old and new records; cleanup preserves surviving owners.
- Validation: Existing S3 and isolated prepared-answer/recovery checks. No live renderer.
- Status: complete. Added immutable ImageRenderRequest serialization. New candidates persist prompt, ordered snapshotted inputs, seed, effective Narrative profile/settings and provenance. The proxy dispatches from that request and tags the candidate identity for answer ownership checks. Recovery reads new requests directly and retains parent-job fallback for prior records. Disposable fixtures passed both recovery paths.

### WP3 — Story boundary and Inventory publication
- Dependencies: WP1.
- Files/interfaces: NarrativeReferenceService, NarrativeSceneService, EntityLibraryService publication entry point, Narrative router, StoryReferenceService and external source discovery.
- Work: Scope uncommitted image choices to the owning Story. Require locked, published outputs for new cross-Story references and validate again on commit. Preserve explicit same-story choices and text-only imports. Add candidate-scoped, idempotent Inventory publication for locked target outputs, retain exact prompt and stable Inventory identity, and leave published records independent after unlock/deletion. Preserve pinned inputs and resolve existing NARRATIVE tags for saved consumers.
- Acceptance: Two-Story flow refuses unpublished cross-Story candidates, succeeds after publication, preserves the published image after unlock/deletion, and keeps pinned snapshots and existing zine tags working.
- Validation: Disposable isolated catalog/two-Story checks and existing S1/S3 regressions.
- Status: complete. Target review now exposes Inventory publication for every locked candidate. Publication uses a candidate-scoped catalog origin key, persists the returned Inventory ID, and preserves prompt whitespace. Cross-Story source listing, create-time pinning and Image Catalog discovery require a locked candidate with an approved Inventory publication; pins read published bytes and new discovery emits a LIB:ASSET tag. Disposable two-Story flow refused unpublished input, then succeeded after publication and matched captured bytes to Inventory.

### WP4 — Shared board presentation and compact progress
- Dependencies: WP1–WP3.
- Files/interfaces: Extract shared board module from narrative.js; integrate render_slots.js, narrative.html and Narrative endpoints.
- Work: Board receives slots/candidates and action callbacks, renders stable slot state and review controls, prompt/input inspection and lock/selection markers. Narrative provides authoring, quality/sizing, publication and finishing controls. Add bounded count/generate and explicit replacement UI. Poll compact status only during visible active work, then refresh detail at settlement, entry, relevant actions and tab return. Preserve unsaved edits.
- Acceptance: Existing Narrative task flows remain usable; review stays available during lock; no idle detail polling; active work settles into current detail.
- Validation: S1/S3 and disposable browser checks for replacement, lock review, inputs, scene-text and polling. No new permanent scenarios.
- Status: complete. Extracted shared Candidate Board card rendering to candidate_board.js and wired Narrative-specific slot actions through callbacks. Added a bounded 1–8 Generate count control while retaining the existing Draft/Final 1/4 shortcuts. Added compact progress and conditional detail refresh. Disposable browser check observed active progress/detail refresh and no recurring idle requests.

### WP5 — Compatibility, docs and final verification
- Dependencies: WP1–WP4.
- Files/interfaces: migrate_narrative_image_board.py, Narrative docs, CODE_MAP.md, INVARIANTS.md, ADR index/new ADR.
- Work: Preserve valid v2 locks of either quality and make a lone lock the selection on the next write; report ambiguous/invalid states. Ensure legacy conversion adopts only a Final lock. Keep conversion explicit and backed up. Document shared boundaries and compatibility choices. Record observed validation and archive this plan only after completion.
- Acceptance: Disposable v2 Draft-lock and legacy Draft-only/Final-lock cases behave as specified; docs match implementation.
- Validation: Approved `npm.cmd run test:e2e`, focused disposable checks, Python/JS syntax checks as affected, and `git diff --check`. Live Narrative check remains opt-in.
- Status: complete. Updated the Narrative component guide, code map and invariants, added ADR 0047 and indexed it with an encoding-safe append. Legacy conversion now adopts only Final-quality locks. Disposable full conversion verified backup creation and Draft-only versus Final-lock adoption.

## Validation
The approved fast E2E suite passed 4/4 (45.8s) on the final implementation. Changed Python modules compiled, `node --check` passed for changed browser modules, and `git diff --check` passed. Focused disposable fixtures covered board transitions, frozen retries and recovery, active/idle polling, cross-Story publication, protected deletion, interrupted cleanup, discovery tags, and legacy conversion. No live renderer ran.

## Risks and decisions
Standard Inventory imports preserve prior behavior. Narrative publication opts into exact prompt whitespace preservation. Existing NARRATIVE tags must remain readable, while new cross-Story source selection must resolve through published Inventory identity. Keep request/settings additions backward-readable. Do not impose new source freshness checks on completed images.

## Progress and decisions
- 2026-11-06: Inspected current v2 board, queue, Narrative source and Inventory paths. User chose enforcing Inventory publication for new cross-Story image references.
- 2026-11-06: Amended the existing S3 locator to target the first `data-action="synthesize"` button while retaining both Write Prompt controls and their shared action. Approved E2E suite passed 4/4 (45.8s). Changed Python modules compiled and `git diff --check` passed.
- 2026-11-06: Extended publication across Narrative target types and added Inventory-backed cross-Story source filtering/validation. Python compilation, JS syntax and diff checks passed. Approved E2E suite passed 4/4 (42.3s).
- 2026-11-06: Added `ImageRenderRequest`, candidate/job persistence and frozen profile settings to the Narrative proxy handoff. Added a bounded Generate count control alongside current shortcuts, plus compact queue progress and conditional detail refresh. Updated Narrative docs, invariants, code map and ADR 0047. Python compilation, JS syntax and diff checks passed. The approved fast E2E suite passed 4/4 (44.0s).
- 2026-11-06: Updated legacy board conversion to adopt only Final-quality locks.
- 2026-11-06: Disposable conversion checks confirmed a Draft selection remains selected without being adopted as the lock, while a Final lock is adopted. Python compilation, JS syntax and diff checks passed.
- 2026-11-06: Extracted shared board card presentation and added stale occupant fencing for explicit slot replacement. Approved E2E suite passed 4/4 (43.8s); Python/JavaScript syntax and `git diff --check` passed.
- 2026-11-06: Candidate image and lettering removal now persists a cleanup list before filesystem deletion and retries pending entries on refresh. Approved E2E suite passed 4/4 (43.8s). A disposable cleanup fixture passed.
- 2026-11-06: Cross-Story pinning now rechecks lock/publication against the destination Story in the creation transaction. Board transition checks verified count allocation, lock-switch refusal and unlock/selection behavior. Approved E2E suite passed 4/4 (43.4s).
- 2026-11-06: Added an S3 assertion that both Write Prompt controls are present and wired to the same action. Cross-Story publication fence disposable check blocked an unlocked source and accepted its published lock. E2E suite passed 4/4 (43.2s).
- 2026-11-06: Restricted Image Catalog's Narrative assembly discovery to locked, published Inventory assets, emitting LIB:ASSET tags while keeping existing NARRATIVE tag resolution intact.
- 2026-11-06: Disposable two-Story flow rejected an unpublished cross-Story backdrop, accepted it after locking/publishing, and verified the destination snapshot matched Inventory bytes. The temporary acceptance extension was removed after the run. Disposable failure injection confirmed pending cleanup retries successfully. Approved suite passed 4/4 (47.0s).
- 2026-11-06: Disposable browser check changed the saved prompt after a failed render and confirmed Retry retained the original frozen request. It observed progress/detail refresh during active jobs and zero recurring requests after settlement. Temporary assertions were removed. Approved suite passed 4/4 (47.8s).
- 2026-11-06: Pending render recovery now republishes from the candidate/job ImageRenderRequest when the parent record is unavailable and falls back to the legacy parent request for older records. Disposable fixtures passed both paths. Approved E2E suite passed 4/4 (44.4s), Python compilation and diff checks passed.
- 2026-11-06: Disposable bulk deletion flow verified explicit approval for selected and locked Draft effects, with refusal preserving the lock and approval deleting the target image. Initial test placement deleted a backdrop before final assembly and failed; moving the disposable check after assembly resolved it. Approved suite passed 4/4 (45.8s).
- 2026-11-06: Full temporary library conversion created backups and retained a Draft selection without adopting its lock; Final lock was adopted. The disposable library was removed after verification.
- 2026-11-06: Disposable Image Catalog check confirmed unpublished assemblies are omitted and published locked assemblies emit LIB:ASSET tags. Approved E2E suite passed 4/4 (43.5s); Python compilation, JS syntax and diff checks passed.
- All implementation packets and focused disposable acceptance checks are complete.

## Final results
Narrative uses shared Candidate Board policies and presentation while retaining
its own authoring and storage. Candidate requests freeze prompts, ordered inputs,
seeds and effective render settings. Inventory publication, cross-Story source
eligibility and new Image Catalog references use locked published assets. Legacy
conversion adopts only Final locks and creates backups.

Validation recorded through 2026-11-06: approved `npm.cmd run test:e2e` passed
4/4 on the final implementation (45.8s); changed Python modules compiled;
`node --check` passed for changed browser modules; `git diff --check` passed.
Disposable checks covered board transitions, Retry after prompt edits, new and
legacy pending render recovery, active/idle polling, two-Story Inventory
publication with captured-byte equality, protected Draft deletion approval,
interrupted cleanup retry, Image Catalog Inventory tags, and backed-up legacy
board conversion. No live renderer ran. Temporary acceptance extensions were
removed. Final diff review found only plan-scoped code, documentation and the
requested lifecycle assertion.
