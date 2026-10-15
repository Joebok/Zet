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
All four local character pages display eight stable slots per view. Initial FRONT/other-view counts are integers 1â€“8 (defaults 8/4); planned candidates awaiting an anchor are reserved, not empty. Add renders fills empty positions only. Generate/Regen use the current view prompt with fresh seeds; the viewâ€™s Recompile checkbox also applies to these actions and compiles current templates first. Already submitted asks retain their frozen inputs. Regen replaces an unselected candidate with a new identity; render Retry retains the failed render inputs/seed. Failed advisory review keeps its separate retry behavior.

[CharacterRenderSlots](../../zet/services/render_slot_service.py) owns atomic allocation and protection behind [LocalImagePipelineWorkflowService](../../zet/services/local_image_workflow_service.py). Detail includes `slots_by_view`, `slot_controls`, candidate slot numbers and action reasons. Render actions persist `slot_render_ids` before scheduling; an independent per-run collector submits/reconciles them without taking the batch runner lock. Other slots remain usable while renders run. Clear detaches running candidates so late answers cannot fill replacement slots. Startup recovery reattaches this collector. Candidate definitions added after creation live separately from mutable review state so rerun resets retain them. Clear detaches active membership and retains provenance/artifacts. Legacy galleries over eight remain visible; clear surplus unprotected candidates to reach capacity.

The browser polls at two-second intervals while active, including in review. Updates patch slot/status sections and preserve unsaved observations, human decisions, focus and current candidate. Once a view has a complete ranking, candidate cards display in original Luna order, with unranked occupied slots following in physical slot order and empty slots after the candidates. This is presentation only: each card retains its physical slot label and its actions remain bound to that slot. Incomplete, stale or failed rankings leave cards in physical slot order. Selected/locked outputs require explicit protection transitions; adding alternatives does not modify immutable library locks. Body ranking waits for gates before comparing the complete active survivor set. See [ADR 0007](../DECISIONS/0007-stable-render-slots.md).

Existing S2 verifies Assembly/Dressing publication. Joe separately approved disposable checks for costume deep-link loading, card containment, current prompt/Recompile behavior and overlapping slot actions. Those checks use prepared renders/rankings; no new maintained tests or live services were added. Full Body/Head generation and general restart recovery remain outside maintained coverage.

## Style-unification batch review (2026-10-14)

Body and Head bootstrap from text; other views may use newly generated local front anchors. Assembly and Dressing use that local chain, with costume-only references remaining narrowly bound. Shared character instructions use the existing fine-grained head/body visibility tags to separate visible identity facts from rendering treatment. Prompt wording seeks dimensional anatomy and differentiated materials; it does not establish observed image quality.

Joe approved initial Tsaeytte batch review for FRONT (8), FRONT_LEFT_3_4 (4), and BACK_RIGHT_3_4 (4), through Canonical Adventure Gear, in existing galleries. Provisional selected-batch sources can advance this chain without replacing published locks. New images require explicit source-layer refresh before appearing in an already frozen Narrative assembly. Local implementation checks passed; live batch review remains pending rollout of the new prompt templates.

Local Head, Assembly and Dressing candidates track the staged ask’s `target_output_file`, matching the background harvester’s destination. A runner must not wait on a separate candidate filename after the generic harvester has consumed the answer. The live style-unification trial exposed this handoff race; existing successful outputs were recovered by matching ask receipts and seeds without rerendering.

Costume-Dressing batch lookup compares normalized workspace qualifiers, so a costume display name and its underscore slug resolve the same batch. Costume links also accept either identifier when selecting the existing gallery control. Other costume qualifiers remain isolated.


## Quick Character reconstruction and true-up (2026-10-15)

`QuickCharacterWizardService` offers source-style preservation or opt-in universe-style reconstruction. New sessions default to universe reconstruction in the UI, with preserve/change inputs, model choice, frozen style, editable brief and unseen-detail proposals/questions. Legacy sessions retain source-style semantics. The wizard remains independent of Body/Head/Assembly/Dressing prerequisites.

Shared reconstruction creates the edited target; front generation uses text only. Review shows original/candidate images and selectable corrections. True-up uses the styled candidate and retains intentional edits. Joe approves the front before three-quarter/profile generation from that anchor. Requested angle/visibility applies to head and torso together; hidden details are not automatically defects. Full body/portrait and left/right retain their existing output choices.

Intent/description changes invalidate approvals; a new front invalidates views using the prior anchor. Failed review retries separately; failed renders with saved inputs retry the submitted prompt/references/seed. Background submission is fenced against abandonment/revision/front changes. Transactional publication records target/style, actual correction lineage, comparison and seed, with source evidence distinct from approved outputs. Freydis's artistic acceptance is pending; disposable checks do not establish identity improvement. See [ADR 0013](../DECISIONS/0013-shared-reconstruction-target-and-true-up.md).

Operator trial update (2026-10-15): Joe accepted the Freydis improvement as sufficient to proceed. The wizard now emphasizes Generate, custom feedback, Try these changes and Use this image. Analysis, suggestions and earlier attempts are optional details; generating uses the current description without a separate approval checkbox. Failed automated review does not block choosing or refining a rendered image. Custom feedback composes directly without model compatibility approval; see PROMPTS.md and ADR 0013.


## Minor Characters workspace (2026-10-15)

The standalone Minor Characters list/editor replaces the Quick Character Wizard dialog. MinorCharacterService extends the existing engine and universe-local store. One name identifies one ongoing workspace; legacy active/published sessions are adopted and remain editable. Inputs are on the left, with view tabs, candidate thumbnails and designated-original/candidate comparison on the right. The comparison reference is display-only, defaults to the first entered reference and is independent of primary identity. Stable reference IDs preserve entry order.

Select this image establishes a working choice. A selected, unlocked front can generate optional three-quarter/profile views. Lock selected image publishes only that view into Inventory and updates its current reference-set association; front alone is sufficient. Selecting another front or editing inputs does not remove existing images, side selections or locks. Submitted work retains its input snapshots. Later locks preserve earlier published image bytes. Automated review is optional advice, not a selection/publication requirement.

Inventory launches open the owning Minor Character for published outputs, or offer create/continue for other images. Continuing never silently replaces references. See [ADR 0014](../DECISIONS/0014-minor-character-workspaces.md) and [data model](../DATA_MODEL.md). The legacy wizard routes remain compatibility adapters; no new major-character pipeline is introduced.

Minor Character suggestions run separately from rendering, so pending/failed review does not delay subsequent generation. Reference image URLs use stable reference IDs. Local implementation and disposable service/browser validation are complete; no production rollout or live image-quality claim is implied.

### Prompt iterations and comparison review

Generate and Try these changes each start a prompt iteration with one render in a four-slot board. The top strip switches iterations for the current view. Add renders fills empty slots; Regenerate replaces one slot using the saved render payload, including reference pixels and refinement direction, with fresh seeds. Workspace edits apply to new iterations. Clear removes only board membership, preserving candidate files, working selections and Inventory locks. Earlier candidates adopt individual iterations.

Inspect full size and slot thumbnails open one paired review dialog: designated original on the left, candidate on the right, with Select candidate below it. Previous/next buttons and left/right arrow keys navigate rendered slots within the active iteration only. Selection remains separate from locking. The comparison picker changes display only. Slot actions use POST /api/minor-characters/{sid}/iterations/{iteration_id}/slots; allocation and prompt reuse belong to MinorCharacterService.
