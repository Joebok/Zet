# Local character assets

The active character workflow produces and reviews **batches of candidates** for Body-Reference, Head-Image, Character-Assembly, and Costume-Dressing. It reuses prompt compilers while keeping its own run/selection state. Traditional stage-driven generation is retired via [pipeline_retirement.py](../../zet/services/pipeline_retirement.py); retained traditional assets are not local batch IDs.

## Interfaces and workflow

| Responsibility | Implementation / consumer |
| --- | --- |
| Body generation/review | [LocalBodyReferenceService](../../zet/services/local_body_reference_service.py), [Run_Body_Reference_Jobs.py](../../Scripts/Run_Body_Reference_Jobs.py) |
| Head generation/review | [LocalHeadImageService](../../zet/services/local_head_image_service.py), [Run_Head_Image_Jobs.py](../../Scripts/Run_Head_Image_Jobs.py) |
| Assembly and costume-qualified dressing | [LocalCharacterAssetPipelineService](../../zet/services/local_character_asset_pipeline_service.py): `preview`, `create_run`, `execute_run`, `select_view`, `lock_preview`, `lock_selected_view`, rerun/resume/stop methods |
| Shared review/run semantics | [local_image_pipeline_policy.py](../../zet/services/local_image_pipeline_policy.py), [candidate_review_contract.py](../../zet/services/candidate_review_contract.py), [local_candidate_review_contract.py](../../zet/services/local_candidate_review_contract.py), [local_image_ranking_service.py](../../zet/services/local_image_ranking_service.py) |
| Selection, lock and publication | [LocalAssetStoreService](../../zet/services/local_asset_store_service.py), checksum-verified [LocalAssetSourceService](../../zet/services/local_asset_source_service.py), entity image library |
| Overview and sequenced automation/recovery | [LocalCharacterOverviewService](../../zet/services/local_character_overview_service.py), [LocalRunAllRemainingService](../../zet/services/local_run_all_remaining_service.py), [local router](../../zet/web/local_character_asset_pipeline_router.py), app startup recovery |

Inputs include character/phase, normalized requested views, costume qualifier when applicable, source batch/candidate selections, source templates, profile and seed controls. Runs retain specs, snapshots, candidate state, gate/ranking jobs, and selections. Outputs include candidate image artifacts and, after locking, approved library image/reference bindings.

1. Preview validates inputs and dependencies. Assembly uses body/head references; dressing uses an assembled character and costume source. Read the service's source resolution before assuming every input must already be locked: selected-batch workflows also exist.
2. Creation snapshots source material and records the run. Rendering queues work through the shared File Proxy; answer harvesting and view-specific evaluation progress persisted state.
3. Narrow defect gates and comparison ranking provide review data. Front-anchor/order requirements differ by pipeline; use the owning service rather than a universal view loop.
4. Human decisions, current gate/ranking state, and selection determine eligibility. Selection and locking are separate operations; promotion may collect a source chain.
5. Lock publication preserves approved image bytes/checksum and a stable logical reference. Verified locks feed identity keys, turnarounds, costumes, phase comparison and scene references.

## Contracts, failures, and extension

Candidate, source-snapshot, and local asset-lock records persist library-owned paths relative to the bound universe using format version 1. Storage helpers resolve paths before file access, so service and HTTP consumers continue to receive usable filesystem paths while newly written JSON remains portable. Image bytes, checksums, selections, and lock state remain governed by their existing workflow contracts. See [portable library references](../DECISIONS/0011-portable-library-references.md).

The supported production renderer is ComfyUI with registered Qwen Image 2.1 profiles in [Local_Render_Presets.json](../../Config/Local_Render_Presets.json), enforced by [local_render_policy.py](../../zet/services/local_render_policy.py). Historical Stable Matrix/other profiles are not allowed production choices. Use AI Proxy; follow AGENTS before direct ComfyUI operation.

Active edit profiles use the shared Qwen reference sizing policy described in
[PROMPTS](PROMPTS.md). Prepared snapshots preserve source order and are retained
with pending workflow artifacts so retries keep the original edit inputs.

Preserve the review semantics, live-batch/checksum lock requirements, universe ownership, and immutable dependent locks in [INVARIANTS](../INVARIANTS.md). Failure modes include unavailable external rendering/review models, stale gate/rank results, changed/missing source snapshots, invalid batch IDs, missing `spec.json`, missing locked bytes, and interrupted runners. Stop/resume/rerun and recovery must respect superseded work; do not reset persisted state blindly.

For a new gate, update shared policy/registry and the owning pipeline inputs/prompts and relevant approved scenario assertions; new coverage requires approval. For a new local asset operation use the local store/services and downstream source provider, not `Assets.json` stage mutation. Data formats belong to [DATA_MODEL](../DATA_MODEL.md); prompt mechanics belong to [PROMPTS](PROMPTS.md).

## Verification and decisions

[S2 in fast.spec.mjs](../../tests/e2e/fast.spec.mjs) previews, creates and starts a front-only Character-Assembly run, applies prepared image/gate responses, waits for ranking, selects/locks it, and repeats for Costume-Dressing. Body/Head prerequisites are seeded with valid batch specs/locks. This does not verify Body/Head generation, other views, multi-candidate rankings, cancellation or recovery. The former Python cutover failures are historical, not outstanding baseline failures. See [Testing](../Testing.md) for the approved baseline and coverage policy.

[ADR 0003](../DECISIONS/0003-local-character-production-boundary.md) records the retirement/renderer boundary. [V5 Realignment](../../Docs-Joe/Zet%20V5%20Realignment.md) describes intent and open questions; it does not authorize a new implementation phase.

## Fixed render slots (2026-10-12)
All four local character pages display eight stable slots per view. Initial FRONT/other-view counts are integers 1–8 (defaults 8/4); planned candidates awaiting an anchor are reserved, not empty. Add renders fills empty positions only. Generate/Regen use the current view prompt with fresh seeds; the view’s Recompile checkbox also applies to these actions and compiles current templates first. Already submitted asks retain their frozen inputs. Regen replaces an unselected candidate with a new identity; render Retry retains the failed render inputs/seed. Failed advisory review keeps its separate retry behavior.

[CharacterRenderSlots](../../zet/services/render_slot_service.py) owns atomic allocation and protection behind [LocalImagePipelineWorkflowService](../../zet/services/local_image_workflow_service.py). Detail includes `slots_by_view`, `slot_controls`, candidate slot numbers and action reasons. Render actions persist `slot_render_ids` before scheduling; an independent per-run collector submits/reconciles them without taking the batch runner lock. Other slots remain usable while renders run. Clear detaches running candidates so late answers cannot fill replacement slots. Startup recovery reattaches this collector. Candidate definitions added after creation live separately from mutable review state so rerun resets retain them. Clear detaches active membership and retains provenance/artifacts. Legacy galleries over eight remain visible; clear surplus unprotected candidates to reach capacity.

The browser polls at two-second intervals while active, including in review. Updates patch slot/status sections and preserve unsaved observations, human decisions, focus and current candidate. Once a view has a complete ranking, candidate cards and previous/next review navigation follow Luna order, with unranked occupied candidates after ranked candidates in physical slot order; empty slots remain after candidates. This is presentation only: each card retains its physical slot label and its actions remain bound to that slot. Incomplete, stale or failed rankings leave cards and review navigation in physical slot order. Selected/locked outputs require explicit protection transitions; adding alternatives does not modify immutable library locks. Body ranking waits for gates before comparing the complete active survivor set. See [ADR 0007](../DECISIONS/0007-stable-render-slots.md).

Existing S2 verifies Assembly/Dressing publication. Joe separately approved disposable checks for costume deep-link loading, card containment, current prompt/Recompile behavior and overlapping slot actions. Those checks use prepared renders/rankings; no new maintained tests or live services were added. Full Body/Head generation and general restart recovery remain outside maintained coverage.

## Style-unification batch review (2026-10-14)

Body and Head bootstrap from text; other views may use newly generated local front anchors. Assembly and Dressing use that local chain, with costume-only references remaining narrowly bound. Shared character instructions use the existing fine-grained head/body visibility tags to separate visible identity facts from rendering treatment. Prompt wording seeks dimensional anatomy and differentiated materials; it does not establish observed image quality.

Joe approved initial Tsaeytte batch review for FRONT (8), FRONT_LEFT_3_4 (4), and BACK_RIGHT_3_4 (4), through Canonical Adventure Gear, in existing galleries. Provisional selected-batch sources can advance this chain without replacing published locks. New images require explicit source-layer refresh before appearing in an already frozen Narrative assembly. Local implementation checks passed; live batch review remains pending rollout of the new prompt templates.

Local Head, Assembly and Dressing candidates track the staged ask�s `target_output_file`, matching the background harvester�s destination. A runner must not wait on a separate candidate filename after the generic harvester has consumed the answer. The live style-unification trial exposed this handoff race; existing successful outputs were recovered by matching ask receipts and seeds without rerendering.

Costume-Dressing batch lookup compares normalized workspace qualifiers, so a costume display name and its underscore slug resolve the same batch. Costume links also accept either identifier when selecting the existing gallery control. Other costume qualifiers remain isolated.


## Quick Character reconstruction and true-up (2026-10-15)

`QuickCharacterWizardService` offers source-style preservation or opt-in universe-style reconstruction. New sessions default to universe reconstruction in the UI, with preserve/change inputs, model choice, frozen style, editable brief and unseen-detail proposals/questions. Legacy sessions retain source-style semantics. The wizard remains independent of Body/Head/Assembly/Dressing prerequisites.

Shared reconstruction creates the edited target; front generation uses text only. Review shows original/candidate images and selectable corrections. True-up uses the styled candidate and retains intentional edits. Joe approves the front before three-quarter/profile generation from that anchor. Requested angle/visibility applies to head and torso together; hidden details are not automatically defects. Full body/portrait and left/right retain their existing output choices.

Intent/description changes invalidate approvals; a new front invalidates views using the prior anchor. Failed review retries separately; failed renders with saved inputs retry the submitted prompt/references/seed. Background submission is fenced against abandonment/revision/front changes. Transactional publication records target/style, actual correction lineage, comparison and seed, with source evidence distinct from approved outputs. Freydis's artistic acceptance is pending; disposable checks do not establish identity improvement. See [ADR 0013](../DECISIONS/0013-shared-reconstruction-target-and-true-up.md).

Operator trial update (2026-10-15): Joe accepted the Freydis improvement as sufficient to proceed. The wizard now emphasizes Generate, custom feedback, Try these changes and Use this image. Analysis, suggestions and earlier attempts are optional details; generating uses the current description without a separate approval checkbox. Failed automated review does not block choosing or refining a rendered image. Custom feedback composes directly without model compatibility approval; see PROMPTS.md and ADR 0013.


## Minor Characters: alignment and true-ups (2026-10-15)

`MinorCharacterService` handles named universe-local workspaces, input analysis and publication. `MinorCharacterWorkflow` in `minor_character_workflow_service.py` owns current boards, stage prompts, rendering and review. New workspaces use the current workflow only; retired records are excluded without migration or file deletion. The Quick Character notes above describe preceding view/history rules, superseded by [ADR 0015](../DECISIONS/0015-minor-character-alignment.md).

Style alignment reconstructs identity, costume and details in universe style without enforcing an official view. Suggested changes/custom feedback refine it. Select a style image before generating any view. Every view independently uses this selected image with a short direction-only prompt, without the full character brief. Select an aligned view and Continue to true-ups before refining it. Only generated view true-up candidates can lock into Inventory; style candidates and carried alignment images never lock. Pending/failed review does not block selection or custom refinement.

Each stage has one four-slot board. Refinement edits the previewed candidate and carries the selected image, if any, in its same slot as Prior selection; other slots clear. Repeated carry is allowed. Clear/Regen removes that slot's working selection. Additional renders replay the frozen recipe with fresh seeds. Current images retain their own prompt/kind. Revisions reject stale mutations and late results cannot restore discarded slots.
Restarting a view clears that view's working round and selection, returns it to alignment, and starts a fresh render from the selected style image. Restarting Style clears required changes, additional direction and analysis results, resets every stage's working board, and re-analyzes the retained original references. If any view work exists, Style restart requires confirmation that view images and revisions will be discarded. Immutable Inventory locks remain. The current board template candidate's final prompt is shown below custom feedback; it represents the latest round even when an older image is advanced.

Undo true-up restores one prior prompt/supporting state, including frozen findings, checked suggestions and feedback, with every slot and working selection cleared. There is no redo or image history. Regenerate from that recipe or choose different corrections using its private source binding. Private immutable inputs can remain for reproducibility, without discarded-image access. Inventory locks survive clear, refinement, undo and workspace deletion.

Paired review has independent navigation. Right arrows/keyboard keys move among rendered current slots. Small left arrows loop through original and occupied style slots during style work; during view work they loop through original, selected style and selected other views. Images deduplicate by checksum and unavailable entries are skipped. Comparison choice affects display only, independently of primary identity and reference order.

Main Minor Characters navigation saves edits and opens the complete list, including from an editor. Direct character links/history and Inventory handoffs remain. The All Minor Characters button and iteration history are removed. Board actions use `/api/minor-characters/{sid}/boards/{view}/{action}` and `/boards/{view}/slots/action`; mutations carry expected board revisions and services enforce eligibility. See [data model](../DATA_MODEL.md) and [prompts](PROMPTS.md). Disposable checks cover this workflow; S1-S3 are regression coverage, not artistic acceptance.

## Unified AI jobs (2026-10-16)
Local gates, ranking, prompt observations and Minor Character analysis/review/render
requests use the common AI job boundary. Generic execution moved to AI_Proxy;
Minor Character continuations persist and resume without session-page reads.
Domain eligibility, immutable publication, revisions and image binding rules stay
here. [Shared AI jobs](AI_JOBS.md) owns collection/receipts, queue activity and the
capability-aware model popup.

Image-based gates and ranking require the current render's successful harvest
receipt, validated bytes and committed image hash. Gate staging uses the run's
state lock and a durable publication reservation, so restart between publication
and gate-state commit reuses its ask. Minor review uses a deterministic workflow
identity and process-shared session locks; its candidate image is committed before
review starts. Admission rechecks current membership, cancellation, hashes and
evaluation immediately around publication. Queued render/gate work does not fail
solely because a subscriber's 30-minute wait elapsed.

Reconstruction preparation verifies its frozen input fingerprint and reuses its
saved record after suspension. Draft-application and analysis-to-candidate
checkpoints prevent replay from creating another reconstruction or candidate.
See [AI jobs](AI_JOBS.md) for common lifecycle/receipt ownership.
