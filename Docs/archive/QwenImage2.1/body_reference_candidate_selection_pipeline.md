# Local Body-Reference Candidate Selection Pipeline

Local Body-Reference is the candidate-based Qwen workflow alongside the manual Body-Reference pipeline. It stores its own run snapshots, candidate images, reviews, rankings, and selections in `Zet_Library/Experiments/Character-Pipeline`; it does not advance the canonical asset pipeline. The implementation is in `zet/services/local_body_reference_service.py`, with shared gate policy in `zet/services/local_gate_registry_service.py` and shared freshness rules in `zet/services/local_image_pipeline_policy.py`.

## Current workflow

1. Preview and create a batch for a character and phase. All eight views are planned: `FRONT`, `FRONT_LEFT_3_4`, `FRONT_RIGHT_3_4`, `LEFT_PROFILE`, `RIGHT_PROFILE`, `BACK_LEFT_3_4`, `BACK_RIGHT_3_4`, and `BACK`. The defaults are 8 FRONT candidates and 4 per other view, with a 256-candidate limit. The run snapshots compiled prompts and seeds.
2. Generate and review FRONT first. Candidates pass narrow gates and enter Luna's comparative ranking. A human selects a current, ranked FRONT candidate as the anchor.
3. Proceed with the seven other views. Generation uses the selected FRONT image as a conditioning reference. Their review also compares each candidate's physique against that anchor.
4. Luna ranks only candidates with current applicable gate records. A human can inspect reasons, adjust rank order, keep or reject candidates, and select one current candidate per view. A selection becomes the local asset for that view. Locking makes a verified immutable copy for downstream use. The batch is `COMPLETE` after all eight views have current selections.

An empty survivor set is recorded as `EMPTY`. Render, gate, and ranking failures remain distinct so the corresponding retry or reevaluation action can be used. A changed FRONT anchor invalidates dependent views.

## Gate policy and model responses

The shared **stored verdict** convention is `TRUE = reject`, `FALSE = pass`. Do not assume every **model response** has that meaning. The service converts positive-answer prompts into the shared stored convention:

| Gate | Views and input | Model response | Default policy |
| --- | --- | --- | --- |
| Face | Every view; cropped candidate head | `TRUE` means obvious rendered facial features and rejects. | Active |
| Proportion | Every view; candidate | `TRUE` means plausible head-to-body proportions and passes. | Active |
| Framing | Every view; candidate | `TRUE` means substantially complete full-body framing and passes. | Active |
| Orientation | Every view; candidate and the exact view definition | `TRUE` means the view matches and passes; `FALSE: <brief visible reason>` means mismatch. | **Disabled** |
| Body identity | Views after FRONT; selected FRONT anchor and candidate | `TRUE` means the physiques could plausibly match and passes. | Active |

The orientation gate is still present in the catalog and dashboard but defaults to `Disabled` because its false rejections and inconsistent results have not been resolved. Zet records a current `DISABLED` gate with a passing stored verdict without sending an Ollama request. Its dormant request uses `/api/chat`, `think:false`, and `temperature:1.0`; those settings are not a validated fix. See the [orientation investigation](Orientation%20Gate%20Investigation.md) before changing its policy.

All gates are narrow and conservative. Obvious defects are the basis for rejection; borderline anatomy, rotation, framing, and viewpoint differences should survive to ranking and human review. The gate registry also supports `Warning` (record a verdict or failure without culling) and `Disabled` (do not run). Policy changes or mismatched prompt, image, or anchor hashes make prior reviews stale. The live prompt text and image roles are available from the gate catalog and each batch's gate-prompt view; this document describes their contract rather than duplicating prompts that can change.

The configured local vision model is used for gates (the default alias is `image-analysis-alt:latest`). Luna performs comparative ranking only after required gate records are current, using the accepted FRONT anchor for later views. Human selection is required even when Luna ranks a candidate first. A rejected candidate cannot be selected or locked.

## Recovery and reruns

- Reevaluate a view to keep its rendered images while replacing affected gate records, ranking, and human decisions. Use this after a gate policy or prompt change.
- Retry a failed gate against the existing image; retry a failed render with a new seed. Rerunning failed candidates or a whole view replaces only the relevant generated candidate artifacts and clears their decisions.
- Rerunning FRONT also clears and regenerates its dependent views. Locked local assets and their dependents must be unlocked before changing them.
- A whole-batch rerun resets the existing batch, including FRONT and all other views, and assigns new candidate seeds. Create a separate batch if the previous results must remain available.
- Stopping an active batch leads to cancellation; interrupted batches can be resumed with valid completed work. `CANCELLED` batches are terminal.

## Gate validation

Before enabling or tightening a gate, test labeled positive, negative, and borderline examples for every applicable view. Track false rejections, false accepts, empty answers, and latency. False rejection is especially costly because it removes a candidate before Luna and human review. Keep the gate's criterion separate from broad quality or aesthetic judgment.
