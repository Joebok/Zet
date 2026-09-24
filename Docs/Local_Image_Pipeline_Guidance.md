# Local Image Pipeline Guidance

Use this guide when planning a local image pipeline in Zet. Pipelines share the candidate workflow and state contract below; prompts, source requirements, view lists, gate criteria, and rendering backends remain specific to each image task.

## Candidate workflow

1. Preview the run with explicit per-view counts, a total candidate limit, and the inputs required to render each view. Use 8 FRONT candidates and 4 for each additional view by default.
2. Snapshot prompts, references, seeds, and relevant input hashes into the run. FRONT is generated and reviewed first. Later views require a current, selected FRONT anchor unless that pipeline defines another dependency.
3. Render each view's candidates, then run narrow, independent rejection gates. Every gate uses `TRUE = reject` and `FALSE = pass`; an ambiguous result should pass. Record prompt, image, and dependency hashes with every completed or disabled gate.
4. Rank only candidates whose required gate records are current. Use Luna for comparative ranking, preserve the ranking inputs and reasons, and let a human make the final view selection.
5. A human selection becomes the local asset for that view. Locking creates a verified immutable copy for downstream use. A run is `COMPLETE` only when every requested view has a current selection.

## State and freshness

Run states describe work across all views: `QUEUED`, `PREFLIGHT`, `RUNNING`, `REEVALUATING`, `AWAITING_FRONT_ANCHOR`, `READY_FOR_VIEWS`, `AWAITING_HUMAN_SELECTION`, `REVIEW_REQUIRED`, `COMPLETE`, `CANCELLED`, `INTERRUPTED`, and `ERROR`. `CANCELLED` is terminal. `INTERRUPTED` can be resumed, reusing completed valid work.

Candidate states describe one image slot: `PENDING`, `QUEUED`, `RUNNING`, `WAITING_FOR_GATES`, `GATE_REJECTED`, `WAITING_FOR_HUMAN_REVIEW`, `COMPLETE`, and `FAILED`. Gate states include `QUEUED`, `RUNNING`, `COMPLETE`, `DISABLED`, `STALE`, and `FAILED`. Ranking states include `QUEUED`, `RUNNING`, `EMPTY`, `COMPLETE`, `STALE`, and `FAILED`.

A gate result is current only when its status and passing verdict are valid and its image, anchor/reference, and prompt hashes match current inputs. A ranking is current only while its candidate set, image hashes, and anchor hash remain current. Hashless legacy reviews must be reevaluated before ranking, selection, or locking. Keep a disabled gate visible as `DISABLED`; do not imply that it ran.

## Reruns, failures, and cleanup

- Reevaluation keeps candidate images but clears affected gates, rankings, human decisions, and selections before review runs again.
- A failed gate can be retried against the same image. A failed render can be retried with a new seed and image.
- A view rerun clears its current selections and review state, withdraws its queued work, and deletes its run-local generated images and gate outputs before replacement. A FRONT change also invalidates and regenerates dependent views.
- Before changing a local asset, verify that it and its locked dependents are unlocked. Remove only files owned by the affected candidate inside that run. Never remove source snapshots, files from another run, or immutable locked copies.
- A whole-batch rerun creates a new run and leaves its source run intact. It can copy a verified FRONT anchor or regenerate FRONT; when regenerating, reuse the previous anchor seed for candidate `c001`.
- An empty survivor set is `EMPTY`, not a ranking-tool failure. Keep render, gate, and ranking failures distinguishable so the correct retry action is available.

## Planning checklist for a new pipeline

- Define requested views, default counts, total limit, required inputs, and view dependencies.
- Define prompt compilation and what must be snapshotted for reproducible reruns.
- Give each gate one visible criterion, conservative rejection semantics, applicable views, and a validation set. Keep disabled gates explicit until validated.
- Define Luna's comparison criteria, model and reasoning settings, structured output validation, and the human selection and lock path.
- Reuse the run, candidate, gate, ranking, cancellation, recovery, and cleanup contracts in `zet/services`; keep reusable behavior out of web routes.
- Specify how FRONT changes, failed render/gate retries, reevaluation, view reruns, and fresh-batch reruns affect images, reviews, selections, and local assets.
- Add tests for path-bounded deletion, locked assets, stale hashes, empty rankings, interruption recovery, and completion only after all views are selected.
- Expose the same run and candidate statuses in APIs and dashboards, then update this guidance when the shared contract changes.

## Existing examples

- [Local Body-Reference candidate-selection process](QwenImage2.1/body_reference_candidate_selection_pipeline.md)
- [Body-Reference orientation gate investigation](QwenImage2.1/Orientation%20Gate%20Investigation.md)
- [Local image generation architecture](Local_Image_Generation.md)
