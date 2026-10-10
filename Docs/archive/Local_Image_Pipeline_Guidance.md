# Local Image Pipeline Guidance

Use this guide when planning a local candidate-based image pipeline in Zet. Local Body-Reference and Local Head-Image implement this contract. Prompts, source requirements, view lists, gate criteria, and rendering backends remain specific to each task. [Local Image Generation](Local_Image_Generation.md) covers the separate scene-preview and generic local-render path.

## Candidate workflow

1. Preview the run with explicit per-view counts, a total candidate limit, and the inputs required to render each view. Both current pipelines use all eight canonical views, default to 8 FRONT candidates and 4 for each other view, and cap the run at 256 candidates.
2. Snapshot prompts, references, seeds, and relevant input hashes into the run. FRONT is generated and reviewed first. Later views require a current, selected FRONT anchor unless that pipeline defines another dependency.
3. Render each view's candidates, then run narrow, independent gates. The stored verdict uses `TRUE = reject` and `FALSE = pass`; individual model prompts may ask the positive question and invert the response before storage. Ambiguous visual evidence should pass. Record prompt, image, and dependency hashes with every completed or disabled gate.
4. Rank only candidates whose required gate records are current. Use Luna for comparative ranking, preserve the ranking inputs and reasons, and let a human make the final view selection.
5. A human selection becomes the local asset for that view. Locking creates a verified immutable copy for downstream use. A run is `COMPLETE` only when every requested view has a current selection.

## State and freshness

Run states describe work across all views: `QUEUED`, `PREFLIGHT`, `RUNNING`, `STOPPING`, `REEVALUATING`, `AWAITING_FRONT_ANCHOR`, `READY_FOR_VIEWS`, `AWAITING_HUMAN_SELECTION`, `REVIEW_REQUIRED`, `COMPLETE`, `CANCELLED`, `INTERRUPTED`, and `ERROR`. `CANCELLED` is terminal. `INTERRUPTED` can be resumed, reusing completed valid work.

Candidate states describe one image slot: `PENDING`, `QUEUED`, `RUNNING`, `WAITING_FOR_GATES`, `GATE_REJECTED`, `WAITING_FOR_HUMAN_REVIEW`, `COMPLETE`, and `FAILED`. Gate states include `QUEUED`, `RUNNING`, `COMPLETE`, `DISABLED`, `STALE`, and `FAILED`. Ranking states include `QUEUED`, `RUNNING`, `EMPTY`, `COMPLETE`, `STALE`, and `FAILED`.

A gate result is current only when its policy, status, verdict, image, anchor/reference, and prompt hashes match current inputs. Policies are `Active`, `Warning`, and `Disabled`: an active gate must complete with stored verdict `FALSE`; a warning gate may record either verdict or a failure without rejecting the candidate; a disabled gate is recorded as `DISABLED` and is never run. A ranking is current only while its candidate set, image hashes, and anchor hash remain current. Hashless legacy reviews must be reevaluated before ranking, selection, or locking.

## Current pipeline differences

| Pipeline | FRONT input | Gates | Later-view dependency |
| --- | --- | --- | --- |
| Local Body-Reference | Compiled body facts; no rendered source image required | Face, proportion, framing, orientation, and body identity after FRONT. Orientation defaults to `Disabled` pending validation. | Selected FRONT physique guides generation and body identity review. |
| Local Head-Image | Compiled head facts; optional uploaded FRONT image is snapshotted into the run | Background, framing, and orientation on every view; gaze on FRONT, the two frontal three-quarter views, and both profiles; source identity if a FRONT source was supplied; identity after FRONT. All default to `Active`. | Selected FRONT head guides generation, gaze comparison where applicable, and identity review. |
| Local Character-Assembly | Locked same-view Body-Reference and Head-Image snapshots; selected FRONT Character-Assembly image guides later views | Framing, orientation, body preservation, and head identity. New gates default to `Disabled` until validated. | Select FRONT before generating other views; the FRONT anchor preserves head-to-body scale, proportions, silhouette, and integrated appearance. |
| Local Costume-Dressing | Locked same-view Character-Assembly snapshot; selected FRONT Costume-Dressing image guides later views | Framing, orientation, costume fidelity, and character preservation. New gates default to `Disabled` until validated. | Select FRONT before generating other views; local assets are scoped by costume. |

Gate policy is stored by the shared gate registry and can override these defaults. Changing a Head-Image FRONT source recompiles its prompt and resets that batch's generated results. Consult each service's gate catalog for the current prompt text and exact image roles.

## Reruns, failures, and cleanup

- Reevaluation keeps candidate images but clears affected gates, rankings, human decisions, and selections before review runs again.
- A failed gate can be retried against the same image. A failed render can be retried with a new seed and image.
- A view rerun clears its current selections and review state, withdraws its queued work, and deletes its run-local generated images and gate outputs before replacement. A FRONT change also invalidates and regenerates dependent views.
- Before changing a local asset, verify that it and its locked dependents are unlocked. Remove only files owned by the affected candidate inside that run. Never remove source snapshots, files from another run, or immutable locked copies.
- A whole-batch rerun resets the existing run, including its FRONT selection, generated images, reviews, rankings, and candidate seeds. Create a separate batch if the prior run must remain intact.
- An empty survivor set is `EMPTY`, not a ranking-tool failure. Keep render, gate, and ranking failures distinguishable so the correct retry action is available.

## Planning checklist for a new pipeline

- Define requested views, default counts, total limit, required inputs, and view dependencies.
- Define prompt compilation and what must be snapshotted for reproducible reruns.
- Give each gate one visible criterion, conservative rejection semantics, applicable views, and a validation set. Keep disabled gates explicit until validated.
- Define Luna's comparison criteria, model and reasoning settings, structured output validation, and the human selection and lock path.
- Reuse the run, candidate, gate, ranking, cancellation, recovery, and cleanup contracts in `zet/services`; keep reusable behavior out of web routes.
- Specify how FRONT changes, failed render/gate retries, reevaluation, view and whole-batch reruns, and new-batch creation affect images, reviews, selections, and local assets.
- Add tests for path-bounded deletion, locked assets, stale hashes, empty rankings, interruption recovery, and completion only after all views are selected.
- Expose the same run and candidate statuses in APIs and dashboards, then update this guidance when the shared contract changes.

## Existing examples

- [Local Body-Reference candidate-selection process and current gates](QwenImage2.1/body_reference_candidate_selection_pipeline.md)
- [Body-Reference orientation gate investigation](QwenImage2.1/Orientation%20Gate%20Investigation.md)
- Local Head-Image: `zet/services/local_head_image_service.py` and the Local Head-Image dashboard.
- Local Character-Assembly and Costume-Dressing: `zet/services/local_character_asset_pipeline_service.py` and the local character pipeline dashboard pages.
- [Local image generation architecture](Local_Image_Generation.md)
