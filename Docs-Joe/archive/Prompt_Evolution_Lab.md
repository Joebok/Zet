# Prompt Evolution Lab

Prompt Evolution v3 optimizes a reusable Stable Diffusion prompt across seeds without category scores.

Each run selects its image backend independently from project-wide image settings. Stable Matrix retains its existing profiles. ComfyUI provides managed SD 1.5 txt2img, img2img, ControlNet, and combined img2img/ControlNet workflows. Pose conditioning supports DWPose/OpenPose, MiDaS depth, and Canny; required custom nodes and matching ControlNet models must already be installed.

ComfyUI conditioning defaults to the locked canonical reference. Separate img2img or pose images can be selected from Zet's image library or uploaded with the run. Inputs are normalized to 768 × 1024, copied into the run, hashed, and held constant across every seed and batch. Final selection writes `render_recipe.json` alongside the backend-neutral prompt core and evaluation wrapper.

Each batch contains fixed benchmark seeds and fresh generalization seeds. Two independent visual critics compare every render with the canonical reference without seeing the prompt or each other's reports. A text-only synthesizer identifies recurrent, intermittent, and isolated deviations plus stable successes. The diagnostician then sees the synthesis, current prompt cores, and reference image. Only one to three high-confidence interventions reach the conservative prompt editor.

Character and costume sidecars contain optional desired-condition regression checks with `id`, `requirement`, `question`, and `correction`. Checks return pass, fail, or indeterminate evidence; they never score or cap a candidate.

Automatic evolution stops at the configured batch limit, when no prompt-level priority remains, or when no high-confidence intervention is available. Final review presents every prompt version in randomized order using its fixed-seed image grid; fresh-seed evidence is expandable. Prompt text, chronology, and the decision log remain hidden until selection. The selected reusable core and render wrapper are written to `prompt_core.json` and `evaluation_wrapper.json`.

After selection, each batch exposes a read-only decision audit containing both critic reports, regression checks, cross-seed synthesis, diagnosis, editor change log, and prompt diff. The audit bundle retains exact LLM prompts, attachments, responses, and transport manifests.

Legacy run schemas are not listed or readable by v3.

## Local smoke test

1. Start Ollama, the selected Stable Matrix or ComfyUI service, File Proxy, Zet auto-harvest, and the dashboard.
2. Open **Tools → Prompt Evolution** and select a locked Costume-Dressing reference.
3. Select two visual critics, an analysis model, a regression-check model, image backend, workflow, and checkpoint. For ComfyUI pose workflows, also select the preprocessor and matching ControlNet model.
4. Use six images, three fixed seeds, two batches, and start the run.
5. Verify every candidate queues two isolated critic asks and that the second batch reuses three seeds while replacing three.
6. Verify the run advances through observing, synthesis, diagnosis, and editing without displaying scores.
7. In final review, verify choices are randomized prompt-version grids with hidden prompt history and expandable fresh-seed evidence.
8. Select a prompt version and verify `prompt_core.json`, `evaluation_wrapper.json`, and the post-selection decision audit.
