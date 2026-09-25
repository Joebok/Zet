# Local Image Pipeline Page Feature Specification

## Purpose

This document defines the common page behavior for the local image pipelines. Local Head-Image is the interaction model: batches of candidate images are rendered, gated, ranked, reviewed, selected per view, and optionally locked as local assets. Pipeline-specific prompts, gates, and reference inputs remain configurable; batch and review behavior should be consistent wherever the operation applies.

The local workflows are separate from the canonical asset workflow until a selected image is locked into the local asset store. Locking and unlocking are explicit user actions.

## Pipeline scope and reference differences

All current pipelines use eight views: `FRONT`, `FRONT_LEFT_3_4`, `FRONT_RIGHT_3_4`, `LEFT_PROFILE`, `RIGHT_PROFILE`, `BACK_LEFT_3_4`, `BACK_RIGHT_3_4`, and `BACK`. A batch allocates one count for FRONT and a second count independently applied to each of the seven other views. New-batch defaults are 8 FRONT candidates and 4 per other view (36 total). Current services cap a batch at 256 candidates.

| Pipeline | Batch identity | Reference inputs | Special behavior |
|---|---|---|---|
| Body-Reference | Character + phase | No pre-existing locked image is required. It generates from the body-reference prompt and later views use the chosen FRONT anchor. | Has a face-gate/review-analysis path and analysis prompt artifacts in addition to rendering and ordinary gates. |
| Head-Image | Character + phase | Optional user-provided FRONT source image. It can be uploaded or pasted, and FRONT can instead use text guidance. Other views require the selected FRONT anchor. | Changing or removing a source on an existing batch clears that batch’s generated images and reviews. |
| Character-Assembly | Character + phase | Requires current locked Body-Reference and Head-Image images for each view. Inputs are copied into the batch, so the batch uses a snapshot. | Per-view reference inputs are shown with the view. |
| Costume-Dressing | Character + phase + costume | Requires a costume selection and current locked Character-Assembly images for each view. Costume template and reference inputs are snapshotted. | Costume is part of the batch identity and filters both batch history and storage. FRONT is reviewed against the FRONT assembly source; later views may also use the selected FRONT costume anchor. |

Every pipeline requires a FRONT anchor before it can render or review other views. This dependency is separate from any pipeline-specific reference image. Character-Assembly and Costume-Dressing batch creation should preview required locked inputs and explain any missing or stale dependency before enabling Create.

## Page layout

Use the following top-to-bottom page structure:

1. **Pipeline navigation and gate settings.** Link among all local pipelines and the main dashboard. Gate settings expose each pipeline gate with `Active`, `Warning`, or `Disabled` policy choices. A policy change applies to existing images after re-evaluation.
2. **Batch controls.** Character and phase selectors; costume selector only for Costume-Dressing; batch-history dropdown; refresh; current batch name; lifecycle actions; and a live status summary. The batch dropdown should be scoped to the selected character/phase/costume and show a useful name, status, Run ID, and completion count. Run ID should be copyable.
3. **New batch builder.** Candidate counts for FRONT and all other views, initially 8 and 4. Show a preview of the view count and total candidate count, and any unmet reference prerequisites. Creating a batch queues it; it does not silently start rendering.
4. **Pipeline-specific reference area.** For Head-Image, show the optional FRONT upload/paste preview and remove action. Other pipelines show the relevant locked/snapshotted references and their roles where useful.
5. **Selected images.** Hide this region until at least one view has a selection. Show one card per selected view with image and ID, selection/lock state, and actions: review, unselect (unless constrained by a locked asset), and Lock or Unlock. The selected FRONT card exposes **Run other views** when an anchor is available.
6. **Per-view candidate galleries.** Include every view, including views with no candidates or no selection. A view section has selection and ranking state, prompt/specification links, and applicable view actions. Each candidate card shows its image or progress placeholder, stable candidate ID, overall candidate status, rejection details, gate results, human decision, and rank position when available. Clicking a rendered image opens the review panel.
7. **Candidate review dialog.** A large side-by-side image comparison with the selected FRONT/anchor (or selected opposite-side view when toggled) on the left and the candidate on the right, plus a scrollable information and action column. Include previous/next controls and keyboard arrows.

The common layout should retain collapsed/expanded view state across refreshes and update active batches periodically without interrupting an open review dialog.

## Batch lifecycle and status display

The page should support:

- Create a queued batch, start it, refresh its current state, rename it, stop active work, resume interrupted work, re-run the full batch, re-evaluate a batch, and delete the batch.
- Disable conflicting actions while a batch is active. Explain destructive effects before replacing a view, replacing a batch, changing a source, or deleting a batch.
- Display overall batch status, completed/total candidates, FRONT anchor ID, selected-view count, gate rejection count, stale selections, and errors when present.
- Keep older Run IDs accessible as batch history. A batch's character/phase/costume identity and snapshotted dependencies must not silently change when the current selectors change.

Recognized run states across the shared local workflow include `QUEUED`, `PREFLIGHT`, `RUNNING`, `STOPPING`, `REEVALUATING`, `READY_FOR_VIEWS`, `AWAITING_FRONT_ANCHOR`, `AWAITING_HUMAN_SELECTION`, `REVIEW_REQUIRED`, `COMPLETE`, `CANCELLED`, `INTERRUPTED`, and `ERROR`. Not every pipeline or review schema emits every state; `STOPPED` is also handled by some UI resume controls. Render user-facing labels rather than displaying raw enum spelling, and preserve unknown future states visibly.

Candidate states include `PENDING`, `QUEUED`, `RUNNING`, `WAITING_FOR_GATES`, `GATE_REJECTED`, `WAITING_FOR_HUMAN_REVIEW`, `COMPLETE`, and `FAILED`. Show failed gate identity and distinguish a gate rejection from a render/review failure. Candidate IDs are stable within a batch and should be displayed on cards and in review.

Gate job states include `QUEUED`, `RUNNING`, `COMPLETE`, `DISABLED`, `STALE`, and `FAILED`. Also display each gate's verdict, reason/evidence, and effective policy (`Active`/`Warning`/`Disabled`); `Warning` results remain visible but do not block like active rejection. Ranking states include `QUEUED`, `RUNNING`, `EMPTY`, `COMPLETE`, `STALE`, and `FAILED`, with an error/reason when applicable.

## Shared generation and review flow

1. Select character and phase; additionally select a costume for Costume-Dressing. The batch-history list updates for that exact identity.
2. Enter FRONT and other-view counts. Validate positive counts and the pipeline's total-candidate limit. Preview required inputs and the resulting views/candidate count.
3. Create the batch. The batch receives a stable Run ID, candidate IDs, per-candidate seed, and a snapshot of required references. Its initial state is queued.
4. Start the batch. Render FRONT candidates first. Track each render and resulting image independently.
5. Run the applicable gates for each rendered candidate. Show gate statuses, policy, verdicts, and reasons. Gate configuration is pipeline-specific. Re-evaluation reruns applicable reviews against existing candidate images; it should not render replacement images.
6. Run Luna ranking for survivors of each view, preserving rank order and the reasons. Candidates with stale gates or rankings must be identifiable and re-evaluated/re-ranked before selection as needed. Allow a user to move a candidate up or down in the saved ranking.
7. Review FRONT survivors and save a human decision (`Undecided`, `Pass`, or `Fail`) and notes. A human-passed, reviewed FRONT candidate can become the FRONT anchor. Selecting the anchor unlocks processing/review of other views.
8. Use **Run other views** on the selected FRONT card to queue every other view that has not already been run. Process those views sequentially, using the selected FRONT anchor as required. Do not replace completed or already-started views as an implicit side effect. Per-view rerun remains an explicit action.
9. For each other view, render candidates, run gates, rank survivors, review candidates against the FRONT anchor, and optionally use the opposite-side toggle to compare against a selected paired view (left/right profile, front three-quarter pair, or back three-quarter pair).
10. Select one eligible candidate per view. A selectable candidate must have a current completed ranking entry and must not have a human rejection; a gate-rejected candidate may be selected only after an explicit human pass where policy permits.
11. Lock selected views individually to create/update local assets. Unlock before replacing a locked asset. Locking all desired views completes the asset-selection workflow; selecting alone does not lock or update canonical assets.

The selected-image strip is an overview and action surface, not a second source of truth: it reflects the batch's `selected_views` and whether those selections match currently locked local assets.

## View section actions and candidate operations

Each view section should provide:

- A link to the rendered image prompt and the review specification/prompt for that view.
- **Re-run** to replace all candidates for that view, their images, automated evaluations/rankings, and human reviews as defined by the service. Confirm replacement.
- **Re-run Failed** to replace only failed/gate-rejected/human-rejected candidates in that view (the exact eligible statuses must be explicit and consistent).
- **Re-evaluate** to rerun gates/review analysis on existing images without replacing images.
- **Rank survivors** to run or refresh Luna ranking for that view.
- Candidate-level **Retry** for a failed gate/review/render job where the service supports retry; label the retried stage accurately.
- Candidate-level **Select** only when selection eligibility rules are met.
- Visible gate details, human review state, rank position/reason, selected state, and candidate status.

The full batch **Re-run** resets the batch to FRONT generation and clears generated images/reviews/selections owned by that run while preserving its batch identity and applicable source snapshot. The **Run other views** operation is distinct: it queues only not-yet-run non-FRONT views after a FRONT anchor exists.

## Candidate review panel

The dialog should show:

- Candidate image on the right; the FRONT anchor/selection on the left for non-FRONT candidates. FRONT candidates can use the available reference/identity comparison appropriate to that pipeline. If no comparison image exists, show a clear empty-state explanation.
- For paired views, a toggle to compare the selected opposite-side view when available; otherwise disable or hide the toggle.
- Candidate ordinal within the review sequence, candidate ID, view, overall status, method/seed where available, and rejection/failure reason.
- Gate results with names, current/stale/disabled status, verdict, policy, and rationale. When a gate fails, expose its prompt/specification where supported.
- Luna rank and rationale, with rank-up/rank-down controls that update the order.
- Human review decision and notes, plus an explicit save action.
- Selection action where eligible. For FRONT, expose the anchor action after required review conditions are met.
- Gate regression-data action to add the candidate image and the necessary reference images to Gate Test Data, selecting the relevant gate and expected answer.
- Previous/next buttons and left/right keyboard navigation. Before changing candidates, save the current human decision and notes; if saving fails, remain on the current candidate and show the error. Avoid interpreting arrow keys as navigation while the user is editing an input, textarea, or select.

Review ordering should be deterministic: view order first, then the current Luna ranking within that view, with unranked images after ranked survivors. Changing ranking or saving a human review should refresh the panel without losing the current candidate.

## Additional functionality identified in Head-Image

These are existing capabilities that belong in the shared feature inventory, subject to whether they make sense for each pipeline:

- Copy Run ID and rename a batch independently from its immutable Run ID.
- Refresh the batch list and periodic polling of a selected batch.
- Gate settings with Active/Warning/Disabled policies and a note that re-evaluation applies policy changes to existing images.
- Inspect gate prompts from candidate results and add candidate/reference examples to Gate Test Data.
- Inspect exact generated image prompts and review specifications per view.
- Human review pass/fail/undecided with notes, persisted automatically when navigating candidates.
- Manual Luna ranking adjustment.
- Candidate-level retry for failed work.
- Unselect a previously selected view, lock/unlock a selected local asset, and highlight when a batch selection differs from a currently locked asset.
- Front-anchor selection and explicit gating of other-view work until an anchor exists.
- Stale gate/ranking/selection visibility after review inputs or policies change; require re-evaluation/re-ranking before stale results can be trusted.
- Batch and per-view replacement confirmations, stop/resume behavior, interruption recovery, and useful failure summaries.

Body-Reference additionally has an analysis prompt/review path. Character-Assembly and Costume-Dressing display their snapshotted source images per view. Keep these as pipeline extensions to shared view/review components rather than removing those useful differences.

## Consistency gaps to resolve when building shared templates/services

The current pages are not yet behaviorally identical:

- Head-Image and Body-Reference have a selected-view strip with lock/unlock/unselect actions; the shared Character-Assembly/Costume-Dressing template currently renders selected status/actions only inside candidate cards and has no equivalent strip.
- Head-Image and Body-Reference expose batch-wide re-evaluation; the generic Character-Assembly/Costume-Dressing toolbar does not.
- Head-Image/Body-Reference have review schema v2 behavior with current gate/ranking freshness and different human/anchor flows. Character-Assembly/Costume-Dressing creation currently writes review version 1 and uses a simpler review flow. Normalize behavior before treating the screens as interchangeable.
- Head-Image's **Run other views** is currently rendered in the FRONT view actions as well as the selected FRONT card. The common contract should make the selected FRONT card the clear canonical entry point, with any duplicate view-section control wired to the same safe operation if retained.
- Button wording, status detail, retry labels, prompt-link naming, preview behavior, and confirmation messages vary. Use common component/service contracts and pipeline configuration to unify these.
- Body-Reference has an additional face gate/analysis path and prompts that should remain pipeline-specific. Gate lists and the meaning of a gate's input references are likewise pipeline-specific.

## Shared template and service boundaries

The shared page contract should accept pipeline configuration for:

- Pipeline key/name, page/API prefix, supported views, review schema capabilities, candidate-count defaults/limits, and batch identity qualifiers (costume when applicable).
- Reference-input discovery/preview, reference snapshots, displayed source roles, and front-anchor prerequisites.
- Image prompt/review-spec/gate-prompt retrieval.
- Gate catalog and policy updates, including gate-specific regression-data reference roles.
- Optional analysis/review stages and per-pipeline candidate details.

Shared services should own batch identity and lifecycle, candidate/render state, gate and ranking transitions, selection eligibility, front-anchor dependency, sequencing of un-run views, stale-state calculations, locking/unlocking, retry/rerun/re-evaluation semantics, and serialization for the page. The web template should render this state and invoke those service actions; it should not reimplement pipeline transitions independently.

Prefer stable action/result contracts across pipelines: `preview`, `create`, `start`, `stop`, `resume`, `rerun_batch`, `rerun_view`, `rerun_failed`, `reevaluate`, `rank`, `move_rank`, `review_candidate`, `select_view`, `unselect_view`, `select_front_anchor`, `run_unstarted_views`, `lock_view`, `unlock_view`, `rename_batch`, `delete_batch`, and `detail`. Pipeline-specific operations such as Body-Reference analysis can extend the common contract without changing the common page flow.

## Source locations inspected

- `zet/web/templates/local_head_image.html`
- `zet/web/templates/local_body_reference.html`
- `zet/web/templates/local_character_pipeline.html` (served for Character-Assembly and Costume-Dressing)
- `zet/services/local_head_image_service.py`
- `zet/services/local_body_reference_service.py`
- `zet/services/local_character_asset_pipeline_service.py`
- `zet/services/local_image_pipeline_policy.py`
- `zet/web/app.py` and `zet/web/local_character_asset_pipeline_router.py`
