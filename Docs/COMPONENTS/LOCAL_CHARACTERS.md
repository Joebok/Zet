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

The browser polls at two-second intervals while active, including in review. Updates patch slot/status sections and preserve unsaved observations, human decisions, focus and current candidate. Rankings are badges/advice, never grid order. Selected/locked outputs require explicit protection transitions; adding alternatives does not modify immutable library locks. Body ranking waits for gates before comparing the complete active survivor set. See [ADR 0007](../DECISIONS/0007-stable-render-slots.md).

Existing S2 verifies Assembly/Dressing publication. Joe separately approved disposable checks for costume deep-link loading, card containment, current prompt/Recompile behavior and overlapping slot actions. Those checks use prepared renders/rankings; no new maintained tests or live services were added. Full Body/Head generation and general restart recovery remain outside maintained coverage.
