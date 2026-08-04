# CODEX Instructions — Revisions to Local Image Generation and Next-Step ComfyUI Enhancements

## Goal

Review the current local image generation pipeline, using `Local_Image_Generation.md` and the included `ComfyUI_Example` as the reference snapshot, and implement the next round of improvements so Zet can move from a proof-of-concept ComfyUI backend to a more robust and extensible local scene-preview system.

The work should:

1. keep `Scene_Render_IR.json` as the canonical backend-neutral source;
2. improve the quality and determinism of ComfyUI scene preview compilation;
3. make the ComfyUI backend extensible for future reference-image and pose-control workflows;
4. improve multi-character layout planning, especially for scenes more complex than 2 characters;
5. update docs and tests to reflect the new behavior.

Do **not** remove Stable Matrix support. Preserve compatibility with the current queue-based local render flow.

---

# High-level review findings to act on

## What is already good

* The current architecture is sound:

  * story scene JSON → `Scene_Render_IR.json` → backend compiler → backend render;
  * queue-based render dispatch and harvest;
  * backend-neutral request/result abstraction;
  * ComfyUI core-node baseline is a real working path.
* The docs are already useful and should be preserved.
* The example shows that even a difficult 4-character scene can get “most of the ingredients” into the frame.

## What needs revision

1. **ComfyUI scene compilation is still too primitive for multi-character scenes.**

   * The current horizontal area-splitting strategy is acceptable for 1–2 characters, but it is too weak for 3–4 characters and mixed depth scenes.
   * Characters that share “left foreground” or similar buckets currently collide conceptually.

2. **Prompt assembly needs cleanup and stronger identity binding.**

   * The compiled prompts contain awkward or lossy phrasing.
   * Some character type labels are incorrect or overly generic (for example, “adult elf woman” where the scene data suggests otherwise).
   * “Looking toward the subject opposite” is too vague; gaze targets should be resolved explicitly when possible.

3. **ComfyUI needs a workflow compiler architecture, not just one hardcoded workflow style.**

   * The current core-node txt2img workflow should remain as the baseline profile.
   * But the code should be reorganized now so future profiles can support:

     * reference-image conditioning;
     * pose/layout conditioning;
     * more advanced workflows.

4. **Reference-image data already exists in the pipeline but is not yet consumed by ComfyUI.**

   * The manifests and IR retain resolved references.
   * This should be the basis for the next enhanced workflow profile.

5. **Documentation should be updated to distinguish the current baseline from the next planned capabilities.**

   * `Local_Image_Generation.md` should be revised to explain:

     * the new layout-planning logic;
     * the new workflow profile architecture;
     * the staged rollout plan for enhanced ComfyUI profiles.

---

# Required implementation phases

---

## Phase 1 — Strengthen the current ComfyUI core preview compiler

### Objective

Improve the current ComfyUI baseline without adding custom nodes yet.

### Required changes

#### 1. Replace the simplistic “horizontal-only” region strategy with a normalized layout planner

Implement a backend-neutral layout planning step that derives explicit normalized layout boxes for local preview rendering.

Use scene information already present in the IR:

* `composition.left_to_right`
* placement `position_within_cell`
* placement `depth`
* `depth_lanes`
* optional `focal_point`
* optional `frame_coverage`, `distance_from_camera`, `visual_scale` if present
* element type and placement ordering

Create a deterministic planner that outputs per-element layout boxes such as:

```json
{
  "element_id": "Tsaeytte",
  "role": "character",
  "x": 0.54,
  "y": 0.40,
  "w": 0.28,
  "h": 0.46,
  "depth": "midground",
  "conditioning_strength": 1.15
}
```

### Rules for the planner

* **1 visible primary character**:

  * give the subject essentially the full useful canvas.
* **2 visible primary characters**:

  * broad left/right overlapping lanes remain acceptable.
* **3 or more visible primary characters**:

  * use a more explicit box layout with:

    * horizontal position from `left_to_right` / `position_within_cell`;
    * vertical/depth banding from `foreground` / `midground` / `background`;
    * nudging when multiple subjects share the same lane;
    * slight overlap only where beneficial.
* The **focal point** should receive:

  * slightly larger box area;
  * slightly stronger conditioning.
* Backdrop elements should not compete equally with characters.

  * Use either:

    * global conditioning only; or
    * a dedicated lower-strength background box if needed.
* Persist the computed layout plan into debug metadata so it can be inspected after a render.

#### 2. Improve prompt compilation quality

Revise ComfyUI prompt compilation so that:

* the global scene prompt stays concise and scene-level;
* each region prompt leads with **binding-critical identity anchors first**;
* costume and action details come after identity anchors;
* vague phrasing is removed;
* duplicated low-value filler phrasing is removed.

### Specific prompt cleanup requirements

* Resolve gaze target phrases explicitly:

  * prefer `"looking toward Tsaeytte"` over `"looking toward the subject opposite"`.
* Resolve expression text cleanly:

  * e.g. `"shy expression"`, `"concerned expression"`.
* Avoid awkward double words like `"background background scenery"`.
* Avoid over-repeating “exactly N visible subjects” in ways that bloat prompts.
* Fix subject descriptor synthesis:

  * do not label obviously male or adolescent subjects as generic or wrong archetypes.
  * derive or preserve correct descriptors from resolved IR content.
* Keep ComfyUI prompt globals appended in a deduplicated way.

#### 3. Remove or prevent contradictory negatives

Audit the current negative prompt assembly so it does not contradict the requested scene.

Examples:

* do not include “front-facing body” in negatives when the scene requires subjects walking toward the camera;
* do not broadly forbid viewer-facing orientations when the scene needs them.

Keep strong negatives for:

* merged characters,
* fused limbs,
* extra people when inappropriate,
* malformed anatomy,
* text/speech-bubble artifacts,
* watermark/caption artifacts.

#### 4. Add layout-plan debug output

In addition to `ComfyUI_Workflow_API.json` and `ComfyUI_Render_Metadata.json`, include enough debug information for review.

At minimum:

* compiled global prompt;
* compiled negative prompt;
* compiled per-region prompts;
* computed per-region rectangles in pixel coordinates and normalized coordinates;
* chosen conditioning strengths;
* resolved subject ordering used by the planner.

Do this either in `ComfyUI_Render_Metadata.json` or in a new adjacent debug JSON file.

---

## Phase 2 — Refactor ComfyUI compilation into a workflow-profile architecture

### Objective

Prepare the codebase for multiple ComfyUI workflow styles.

### Required changes

#### 1. Introduce a ComfyUI workflow compiler registry

Refactor the current ComfyUI implementation so it is not one monolithic compiler.

Create a profile-driven workflow compilation architecture, such as:

* `core_txt2img_scene_preview`
* `core_txt2img_prompt_only`
* future:

  * `ipadapter_scene_preview`
  * `openpose_scene_preview`
  * `ipadapter_openpose_scene_preview`

The exact naming is flexible, but the structure must make it easy to add enhanced profiles.

#### 2. Extend local render profile schema

Update `Config/Local_Render_Presets.json` so ComfyUI profiles can declare workflow intent.

Example concept:

```json
{
  "comfyui-core-preview": {
    "backend": "comfyui",
    "workflow_kind": "core_txt2img_scene_preview",
    "short_side": 640,
    "max_long_side": 960,
    "steps": 28,
    "cfg": 7.0,
    "sampler_name": "dpmpp_2m",
    "scheduler": "karras",
    "denoise": 1.0,
    "seed": "random",
    "output_subdir": "Local_Test_Renders"
  }
}
```

Also add fields as needed for future workflows, even if not yet used, such as:

* `supports_reference_images`
* `supports_pose_control`
* `supports_masks`
* `return_all_images`

Do not break existing profile parsing.

#### 3. Preserve prompt-only mode cleanly

Prompt-only asset local previews should still work when ComfyUI is selected.

The registry should support both:

* scene-IR compilation;
* prompt-only txt2img compilation.

---

## Phase 3 — Add first-class reference-image conditioning support (next enhancement)

### Objective

Implement the first enhanced ComfyUI path that consumes the resolved reference assets already present in Zet.

### Scope

This phase should be implemented as a new profile and workflow compiler, not by mutating the core baseline profile.

### Required behavior

* Use resolved reference assignments from the IR / dependency manifest.
* For now, support **a small, controlled subset**:

  * one or more character identity references;
  * optional backdrop reference;
  * only when the profile is explicitly selected.
* Keep the baseline core profile available and unchanged.

### Implementation requirements

1. Introduce a new ComfyUI profile placeholder, such as:

   * `comfyui-ipadapter-preview`
2. Build the code structure so the profile can:

   * load reference images;
   * attach them to the appropriate character or backdrop branches;
   * record which references were used.
3. If the required ComfyUI nodes are unavailable, fail clearly and informatively.
4. Do **not** silently fall back to a different workflow without recording that fallback.

### Important boundary

Do not attempt to support every custom node ecosystem at once.
Implement a **single explicit enhanced path** and document its dependency requirements.

---

## Phase 4 — Add deterministic pose/layout conditioning support (next enhancement after references)

### Objective

Prepare for better staging and gesture control using structured pose/layout input.

### Scope

This phase may begin as scaffolding if full pose rendering is too large for one pass, but the architecture should be set up now.

### Required changes

1. Add a concept of a generated or compiled pose/layout control artifact derived from `Scene_Render_IR.json`.
2. The compiler should eventually be able to use:

   * pose templates;
   * simple body-location control;
   * or a generated pose image / layout map.

### For this pass

At minimum:

* define the internal interfaces for pose-control support;
* add a future workflow kind placeholder such as `openpose_scene_preview`;
* document expected inputs and outputs.

If there is enough implementation budget, add a minimal stub that:

* builds a pose/layout planning record;
* persists it as an artifact, even if it is not yet consumed.

---

## Phase 5 — Improve queue and artifact handling for ComfyUI

### Objective

Make ComfyUI output review more useful and reproducible.

### Required changes

1. Ensure workflow and metadata artifacts are always copied into the pipeline folder for successful ComfyUI runs.
2. If a workflow returns multiple images:

   * keep the first image as the preview result for compatibility;
   * but preserve metadata for all returned images.
3. Record the selected profile and workflow kind everywhere relevant:

   * ask manifest;
   * answer metadata;
   * harvested metadata.
4. Save the resolved seed used by the run in a consistent location.
5. Ensure direct CLI and queue-driven runs write compatible artifact sets.

---

## Phase 6 — Update `Local_Image_Generation.md`

### Objective

Revise the documentation so it accurately reflects the improved architecture and the next-stage enhancement plan.

### Required doc changes

Update `Local_Image_Generation.md` to include:

#### 1. Clear distinction between profile types

Document that ComfyUI now has:

* a **core baseline preview profile**;
* future **enhanced profiles** for reference images and pose control.

#### 2. Layout planning section

Add a short section explaining the local scene layout planner:

* how it derives boxes from IR;
* how focal point and depth influence box sizes;
* why multi-character scenes are more robust now.

#### 3. Reference-image conditioning section

Add a “current / upcoming” section:

* baseline core profile does not use references;
* enhanced profile(s) do.
  If the reference-enhanced path is implemented in this pass, document exactly how it works and what nodes it depends on.

#### 4. Troubleshooting updates

Add troubleshooting entries for:

* missing required custom nodes for an enhanced ComfyUI profile;
* missing reference files;
* profile/workflow mismatch;
* layout-planner edge cases.

#### 5. Example update

If practical, refresh the example snapshot or at least update the doc commentary to explain:

* why the current example is still useful;
* what the new layout planner should improve.

---

# Specific code-quality requirements

## Preserve these invariants

* `Scene_Render_IR.json` remains the canonical local-scene intermediate.
* `Final_Image_Prompt.md` remains the manual/final render path.
* Stable Matrix remains supported.
* Queue-driven local preview flow remains supported.
* Prompt-only asset local preview remains supported.

## Avoid these mistakes

* Do not hardcode project-specific character or place lookup tables inside the ComfyUI compiler.
* Do not make ComfyUI depend on `Local_Render_Brief.json` as its source of truth.
* Do not mix enhanced reference-image behavior into the baseline core profile.
* Do not attempt to generate dialogue/speech bubbles inside diffusion workflows.
* Do not remove useful debug artifacts.

---

# Suggested files / areas likely to need edits

Adjust exact paths to the real codebase, but expect changes in or around:

* scene IR compiler / render service

  * `StoryRenderService`
  * `compile_scene_render_ir(...)`
* local render dispatch

  * `Scripts.Local_Render_Adapters.render_image(...)`
  * `LocalRenderRequest`
  * `LocalRenderResult`
* ComfyUI integration

  * `compile_ir_to_comfyui_workflow(...)`
  * `run_comfyui_workflow(...)`
  * direct CLI `zet.scripts.render_comfyui_preview`
* queue worker

  * `AI_Manager/local_image_proxy_worker.py`
* config / profile definitions

  * `Config/Local_Render_Presets.json`
  * config model / Image Config handling
* docs

  * `Local_Image_Generation.md`

If it helps maintainability, split the ComfyUI code into modules such as:

* `layout_planner.py`
* `prompt_compiler.py`
* `workflow_registry.py`
* `workflow_core.py`
* `workflow_ipadapter.py`
* `workflow_runner.py`

---

# Tests to add or update

Add or extend tests for:

## Layout planning

* 1-character scene → full-canvas / near-full-canvas subject box.
* 2-character scene → left/right overlapping boxes.
* 4-character mixed-depth scene → distinct boxes reflecting left/right and depth.
* focal point receives stronger or larger box.

## Prompt compilation

* no contradictory negative terms for toward-camera scenes;
* explicit gaze target text when a target exists;
* subject descriptor synthesis does not mislabel known characters.

## Workflow compilation

* core profile compiles deterministic workflow JSON;
* prompt-only mode still compiles correctly;
* profile registry chooses the correct workflow compiler;
* enhanced workflow profile fails clearly when required assets or nodes are missing.

## Queue / artifact handling

* ComfyUI artifacts copied to answer/harvest destinations;
* metadata includes workflow kind, profile, seed, prompts, and layout boxes.

## CLI

* `--compile-only` still works;
* direct render with a fixed seed records deterministic metadata;
* profile override works.

Use the included `ComfyUI_Example` as a regression fixture wherever practical.

---

# Acceptance criteria

The work is complete when all of the following are true:

1. **Baseline ComfyUI preview quality improves for multi-character scenes**

   * The compiler no longer relies on naive horizontal-only splitting for 3+ character scenes.
   * Layout boxes are deterministic and inspectable.

2. **Prompt quality improves**

   * Region prompts are cleaner, less repetitive, and use stronger identity anchors.
   * Gaze targets are explicit when known.
   * Subject descriptor synthesis is no longer obviously wrong.

3. **ComfyUI architecture is extensible**

   * There is a workflow compiler registry or equivalent profile-driven design.
   * The current core workflow is one profile, not the only path.

4. **Reference-image enhancement path is scaffolded or implemented**

   * There is a clear path for ComfyUI reference-image conditioning.
   * If implemented, it is profile-gated and documented.

5. **Documentation is updated**

   * `Local_Image_Generation.md` accurately documents the revised baseline and the next enhancement stage.

6. **Tests pass**

   * Run:

     * `python3 -m pytest -q`
     * `node --check .\zet\web\static\zet.js`
     * `git diff --check`

---

# Recommended implementation order

Do the work in this order:

1. Refactor ComfyUI compiler into a workflow-profile architecture.
2. Implement the new layout planner.
3. Improve prompt compilation and negative-prompt handling.
4. Add debug metadata for layout boxes and compiled prompts.
5. Update queue/artifact plumbing.
6. Update docs.
7. Add scaffolding or implementation for the first enhanced reference-image profile.
8. Add pose-control scaffolding.

---

# Short summary for Codex

Implement the next version of Zet local image generation by improving the ComfyUI core preview compiler, especially for multi-character scenes; add a real layout planner; clean up prompt synthesis; refactor ComfyUI into profile-based workflow compilers; preserve the current queue architecture; update docs and tests; and prepare or implement the first enhanced ComfyUI profile for reference-image conditioning, with pose-control support scaffolded for the following phase.

---

If you want, I can also turn this into a **clean `.md` file formatted exactly like your other CODEX instruction documents**.
