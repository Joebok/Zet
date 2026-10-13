# Optimize Qwen Image 2.1 reference sizing
Status: complete
Related issue/specification: User-approved implementation plan in task conversation.

## Goal

Reduce Qwen Image 2.1 reference-encoding work across active Narrative and local-character ComfyUI workflows while preserving ordered source references, prompt bindings, output dimensions, existing cache behavior, and pending submission recovery. Keep output model, checkpoint, sampling steps, and queue protocol unchanged.

## Current behavior

`Scripts/Local_Render_Adapters/comfyui_adapter.py` loads the selected preset, applies a small allowlist of per-render overrides, compiles a ComfyUI graph, checks a pending graph fingerprint, and polls ComfyUI. The Narrative and Qwen local edit compilers in `zet/services/narrative_qwen_workflow.py` and `zet/services/comfyui_workflow_registry.py` set Qwen encoder resolution from the output's longest edge. The shipped profiles already configure CPU/int8 reference prefix caching. The Group Photo's six source images occupy approximately 7.5 million pixels; the encoder resizes each to 1344 by 1024 alignment (about 10.8 million total pixels).

`config.toml` and multiple relevant source/docs files contain pre-existing user changes. The current checkout retires Scene Builder rendering; do not restore its Qwen scene compiler as part of this work.

## Desired behavior

Prepare private, ordered, EXIF-oriented, alpha-preserving PNG snapshots with Lanczos downscaling, 32-pixel downward alignment, no crop/padding/upscaling, per-image limit 1,048,576 pixels, and aggregate limit 6,291,456 pixels. Configure the machine policy under `[ComfyUI.QwenImage21]`, override preset defaults with valid machine settings, and pass prepared inputs to active Qwen encoders at `resolution=0`. Keep the output latent dimensions and sampling settings unchanged. Preserve explicit Qwen prefix-cache settings, with defaults CPU/int8 and support for ComfyUI's `auto` device.

Record source/prepared checksums and dimensions, ordering, pixel budgets/totals, policy version, and configured cache placement/precision in debug/render metadata. Freeze the compiled workflow, references, and configuration across pending submission recovery; support existing legacy pending artifacts. Provide an opt-out for new submissions. Do not modify source/library bytes or queue protocol.

## Impact analysis

Implementation ownership: shared policy in a new `zet/services/qwen_reference_preparation_service.py`; configuration, compilation, pending-resume validation, and output metadata in `Scripts/Local_Render_Adapters/comfyui_adapter.py`; Narrative resolution in `zet/services/narrative_qwen_workflow.py`; Qwen local-edit resolution in `zet/services/comfyui_workflow_registry.py`; machine defaults in `config.toml`. Update PROMPTS, NARRATIVE, LOCAL_CHARACTERS, DATA_MODEL, INVARIANTS, and CODE_MAP knowledge owners. No persisted story/job schema, frontend, dependency, dispatcher, or test suite changes.

## Invariants and constraints

Preserve ordered image bindings and frozen inputs, universe/attempt ownership, approved profiles, current pending fingerprint and ambiguous-submission rules. No direct ComfyUI operation, live render comparison, or new tests. Do not claim pixel limits guarantee VRAM fit, output quality, or speed.

## Implementation steps

### WP1 — Shared sizing policy and machine configuration
- Dependencies: none.
- Files/interfaces: new `zet/services/qwen_reference_preparation_service.py`; `Scripts/Local_Render_Adapters/comfyui_adapter.py`; `config.toml`.
- Work: validate the five machine options; resolve machine settings over preset defaults; prepare derived images under the job workspace; return ordered bindings and reproducibility metadata; support disabled legacy preparation.
- Acceptance: no source mutation or image enlargement; aspect-preserving aligned results satisfy per-image and aggregate budgets; reference output sizes do not depend on output canvas size.
- Validation: Python syntax and disposable offline checks for the six captured references, small images, and aggregate-budget scaling. No maintained tests.
- Status: complete; machine config and disposable image-policy checks passed.

### WP2 — Connect active Qwen reference workflows
- Dependencies: WP1.
- Files/interfaces: `Scripts/Local_Render_Adapters/comfyui_adapter.py`; `zet/services/narrative_qwen_workflow.py`; `zet/services/comfyui_workflow_registry.py`.
- Work: prepare before compilation and set Qwen reference resolution to zero only for prepared inputs; preserve output latent dimensions and configured cache behavior across Narrative and active Qwen local edit workflows. Do not restore retired Scene Builder compilers.
- Acceptance: each supported reference remains distinct and in original prompt order; reference-free graphs are unchanged.
- Validation: offline inspect representative Narrative and local-character compiled graphs and policy metadata.
- Status: complete; Narrative and local-edit graph inspection passed.

### WP3 — Pending recovery and render evidence
- Dependencies: WP2.
- Files/interfaces: `Scripts/Local_Render_Adapters/comfyui_adapter.py`; existing worker artifact publication.
- Work: validate and resume saved pending workflow/debug artifacts before loading current policy; support legacy artifacts; reject missing, malformed, checksum-mismatched, or fingerprint-mismatched artifacts clearly; include preparation/cache metadata in existing artifacts.
- Acceptance: configuration or source changes cannot cause a pending workflow to be recompiled or resubmitted; existing submission journal and ambiguous state protections remain.
- Validation: disposable offline pending-recovery checks, approved `npm run test:e2e`, and `git diff --check`.
- Status: complete; pending snapshot recovery, legacy recovery, and checksum rejection checks passed.

### WP4 — Knowledge maintenance and completion
- Dependencies: WP3.
- Files/interfaces: `Docs/COMPONENTS/PROMPTS.md`, `Docs/COMPONENTS/NARRATIVE.md`, `Docs/COMPONENTS/LOCAL_CHARACTERS.md`, `Docs/DATA_MODEL.md`, `Docs/INVARIANTS.md`, `Docs/CODE_MAP.md`, this plan.
- Work: document resource tuning, no-upscale sizing, cache options, evidence semantics, and pending recovery boundaries; record checks and uncertainty.
- Acceptance: docs are consistent with current code and do not overstate quality or performance.
- Validation: documentation link and final diff review.
- Status: complete; affected docs describe budgets, alpha/orientation handling,
  cache options and evidence, snapshots, and pending recovery.

## Validation

Run syntax checks and disposable offline policy/compiler/recovery inspections; run the approved `npm run test:e2e` baseline and `git diff --check`. Existing fast E2E scenarios validate adjacent Narrative and local-character lifecycle behavior but do not run ComfyUI or verify generated quality. No live rendering or new automated test scenarios are authorized in this task.

## Risks and alternatives

Smaller references may reduce identity or clothing detail, and a pixel reduction does not imply an equivalent latency or VRAM reduction. Compare the same frozen Group Photo and one representative Assembly/Dressing edit in a separately requested live quality evaluation before tuning defaults. If quality declines, raise the configured budget. Keep the per-reference and aggregate limits configurable; do not infer them from a GPU model or unsupported memory conversion.

## Progress and decisions

- Confirmed local hardware is an RTX 5060 Ti with 16,311 MiB VRAM and 27,669,712,896 bytes system RAM.
- Confirmed the six Group Photo references prepare to 5,192,704 aligned pixels under the proposed defaults, compared with approximately 10,838,016 pixels at the current 1344 encoder resolution.
- Confirmed the working tree already contains broad unrelated edits, including Narrative retirement changes; preserve them.

## Final results

- Added a shared Pillow-based policy and machine configuration, with preset
  defaults and validated machine overrides. Active Narrative and local-character
  Qwen reference graphs use job-local, downscaled snapshots and encoder
  `resolution=0`; output dimensions, checkpoints, steps, and job scheduling stay
  unchanged.
- Pending submissions load their saved graph/debug bundle and ComfyUI server
  address, verify the workflow fingerprint and prepared snapshot hashes, and do
  not recompile. Legacy pending artifacts remain readable. Ambiguous
  `SUBMITTING` state still stops for explicit reconciliation.
- Group Photo references prepare to 5,192,704 pixels total from 7,469,196
  source pixels, while the legacy encoder behavior was approximately 10,838,016
  reference pixels. This pixel reduction is not a runtime or VRAM guarantee.
- Validation passed: disposable policy/compiler/recovery inspections; Python
  AST syntax, preset JSON, and config TOML parsing; approved
  `npm run test:e2e` (3 passed); `git diff --check`.
- No live ComfyUI comparison was run. Likeness/detail and actual time/VRAM
  effects remain unverified and require the separately requested live comparison
  described above.
