# Best-of-N Search for the Single Character Lab

## Summary

Turn the Single Character Lab into a repeatable **search → review → select** workflow. Phase 1 will support large candidate sets, controlled parameter comparisons, modern model adapters, and persistent human reviews with optional automated scoring.

Build on the existing Lab, ComfyUI compiler registry, AI proxy queue, and image-quality review service. Keep scene rendering, finalist refinement, masked repair, and LoRA training outside Phase 1.

## 1. Reproducible searches and durable execution

- Add two modes:
  - **Recipe search:** explicit parameter combinations evaluated against shared seeds and poses.
  - **Seed search:** one frozen recipe evaluated across many fresh seeds.
- Retain small runs; offer 16, 64, and 128 candidates, with a configurable initial ceiling of 256. Show the complete candidate count before submission; never silently truncate a matrix.
- Freeze each experiment’s prompts, reference images, pose inputs, rubric, workflow version, model identifiers, and effective parameters. Record seeds as strings to preserve precision in JavaScript.
- Separate the immutable experiment specification from mutable candidate execution and review records. Give every candidate a stable identifier before submission.
- Persist candidate progress individually. Successful images become reviewable immediately; one failed candidate must not discard the remaining results.
- Support stop-after-current, resume, and explicit retry of failed candidates. Reconcile existing proxy jobs before resubmission so restarting Zet does not duplicate work.
- Use the existing AI proxy execution path with one outstanding Lab render initially and tensor batch size one. Group work by model to reduce reloads; run optional visual reviews in a separate queued pass.
- Record queue, render, and review durations separately. Estimate remaining time from measured throughput; label estimates unavailable until sufficient evidence exists.

Expose these operations through focused backend services. FastAPI routes and browser code handle presentation and interaction only.

## 2. Search spaces and model adapters

Extend the existing ComfyUI registry with explicit workflow capabilities and compatibility checks.

| Adapter | Phase 1 capability |
|---|---|
| Existing SDXL | Preserve TastyRice baseline; compare compatible checkpoints and appearance-only, pose-only, combined conditioning, and low-denoise reference variants. |
| FLUX.2 Klein 4B | Add distilled generation and reference-driven candidate generation first. ComfyUI supports single- and multi-reference editing. [Official documentation](https://blog.comfy.org/p/flux2-klein-4b-fast-local-image-editing) |
| Qwen-Image-Edit-2511 | Add reference-driven candidate generation after memory and throughput qualification. ComfyUI provides an instruction-editing workflow. [Official documentation](https://blog.comfy.org/p/qwen-image-edit-2511-and-qwen-image) |

- Expose supported axes: model/workflow, appearance reference set, pose, reference strength/timing, pose strength/timing, steps, guidance, sampler/scheduler, resolution, and denoise.
- Keep prompts fixed within each experiment. Compile the same character/costume/pose intent into model-appropriate text; do not send SDXL weighted-prompt syntax indiscriminately to modern models.
- Label pose guidance accurately: a pose reference supplied to an editing model is not equivalent to skeletal ControlNet conditioning.
- Discover diffusion models, text encoders, VAEs, and required nodes as well as checkpoints. Reject incompatible or missing components before queueing.
- Cache prepared references and control maps by source content, preprocessing settings, and dimensions.
- Preserve the current validated SDXL resolution/settings as the baseline. Use reduced-step or reduced-resolution profiles only after checking that they remain useful for selection.
- Treat identical seed numbers across model families as bookkeeping, not equivalent noise or paired visual outcomes.

Start with a **72-image SDXL screen:** three appearance strengths × three pose strengths × eight shared seeds. Default strengths are appearance `0.35/0.45/0.65` and pose `0.5/0.75/1.0`; other settings remain frozen. Follow promising recipes with fresh-seed searches and cross-pose validation.

Modern-model workflows use their own supported parameter sets and published starting settings. They generate candidates from canonical references; iterative editing of selected finalists remains deferred.

## 3. Review, comparison, and selection

- Replace the all-images-at-once display with paginated thumbnail galleries, incremental progress, fullscreen comparison, and paginated contact-sheet export.
- Show candidate, appearance reference, and requested pose together. Provide stable randomized review order and an optional blind mode hiding recipe details and machine scores.
- Persist **keep, reject, undecided**, shortlist membership, failure tags, notes, and optional cleanup-time estimates. Make decisions editable.
- Version the existing rubric for Lab use. Preserve identity, costume, anatomy, and composition gates; score identity, costume, pose/orientation, composition/framing, technical quality, and style separately on the existing 0–4 scale.
- Keep human judgments and machine assessments separate. Missing or uncertain scores remain unknown, never zero.
- Extend the existing automated reviewer to inspect appearance, pose, and candidate images against explicit requirements. Store per-dimension evidence, uncertainty, failure tags, model identity, rubric version, and input hashes.
- Automated scoring is opt-in for selected candidates or an entire run. Failures do not block human review; automatic assessments never delete or hide candidates by default.
- Provide component sorting and recipe summaries rather than one dominant aesthetic score. Report human acceptance rate with its reviewed denominator, review coverage, failure distribution, cleanup time, and generation cost.
- Preserve human shortlists and allow saving a winning recipe for subsequent searches. Selecting a Lab winner does not automatically replace a locked library asset.

Add service-backed APIs for experiment preview, candidate pagination, execution controls, human decisions, optional review requests, and saved recipes. Keep existing run-list/detail compatibility; display old runs without requiring migration or rerendering.

## 4. Delivery and validation

Implement Phase 1 in four increments:

1. **Search foundation:** immutable manifests, candidate planning, incremental execution, recovery, and SDXL parameter search.
2. **Human review:** persistent decisions, reference comparisons, blind review, shortlists, and recipe summaries.
3. **Modern adapters:** FLUX first, then Qwen qualification and integration.
4. **Optional machine review:** queued component scoring and calibration against human decisions.

Extend existing service, compiler, review, and browser tests to cover:

- Deterministic matrix expansion, seed precision, unsupported combinations, and candidate limits.
- Snapshot preservation after source/config changes.
- Restart reconciliation, partial failures, retries, stopping, and duplicate prevention.
- Adapter graph construction and missing-component errors.
- Three-image review inputs, malformed responses, uncertainty, and stale-review invalidation.
- Persistent human decisions, pagination, blind mode, and legacy-run loading.

Run live qualification incrementally: small smoke runs before 72–128-image experiments. Measure actual memory use, throughput, review latency, and dashboard responsiveness.

Evaluate promoted recipes across at least four poses and fresh seeds. Retain the existing qualification target: **at least 25% human-accepted yield across at least 16 images, with median cleanup no more than five minutes**. Report best-of-6, best-of-16, best-of-64, and best-of-128 results where sample size permits; include total compute and review time.

## Assumptions and subsequent phases

- Hardware figures in repository documentation—16 GB VRAM and approximately 26 GB system RAM—are provisional until checked.
- Downloads, ComfyUI upgrades, and missing dependencies require approval before installation. An unavailable adapter remains explicitly unavailable.
- Existing uncommitted changes must be preserved. This planning pass modified no files and ran no tests.
- **Phase 2:** after reviewing Phase 1 evidence, plan scene-control packages, per-character references, spatial regions, pose/depth inputs, and scene-specific reviews.
- **Phase 3:** plan finalist refinement and local repair; consider LoRA training only where measured failures justify it.
- Progressive seed pruning is deferred research work. Phase 1 completes candidates and selects among them; it does not intervene during denoising.
