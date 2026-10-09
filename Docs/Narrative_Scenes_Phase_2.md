# Narrative Scenes — Phase 2

Open **Story Telling → Narrative Scenes**. On a scene page, choose **Create
final assembly**. Subscenes, backdrops, and final assemblies share the target
selector and the same two-column authoring/generation layout.

## Assemble a scene

**Continue interview** and **Write prompt** work before adding sources. They
snapshot the text inputs and any pinned source layers without preparing cutouts.
Image generation and composite previews require one visible base backdrop.

1. Generate and select source images on their existing subscene/backdrop pages.
2. In the assembly, choose a backdrop under **Add source**, then **Add selected
   image**. Add the subscenes the same way. If a source has no selection, its
   first completed candidate is used; the candidate selector offers alternatives.
3. Keep one visible **Base backdrop**. **Cover** crops to fill the canvas;
   **contain** fits the whole backdrop with white space around it. Additional
   backdrops can be ordinary masked layers.
4. Position groups by dragging the preview or editing X/Y. X and Y are fractions
   of canvas width/height, measured from the source image's top-left corner.
   **Width / canvas** controls uniform scale; higher **Depth** places a group
   above another. The corner handle resizes a group.
5. **Auto** uses meaningful native transparency, or extracts a neutral background
   with OpenCV when the source is opaque or has only near-opaque alpha noise.
   **Alpha** preserves source transparency exactly; **opaque** keeps the full
   image. Background tolerance controls neutral-background detection.
6. Use **Keep / remove corrections** to paint in original source coordinates.
   Save corrections to refresh the overlay and cutout. These corrections stay
   aligned when the group moves or scales. Changing the source candidate resets
   corrections, because they belong to that image.
7. **Refresh raw composite** shows the backend composition on the same page.
   Its PNG can be downloaded without an image-generation job.
8. In **Prompt and generation**, choose **Assembly mode** (described below).
   Write a prompt, generate one or four candidates, or render the
   visible edited prompt. Select and optionally lock the preferred final image.

Sources are pinned and copied into the assembly. Changing a source's selection
does not change the assembly; **Use current selection** explicitly updates it.
Clearing or deleting the original source leaves the pinned image intact.

Image jobs freeze their mode, sources, corrections, placement, dimensions,
prompt, and seed. The default **Finish placed composite** sends Qwen the
flattened composite as its composition reference.
The backend merges its proposal only into background joins and contact-shadow
regions. Foreground pixels, including antialiased edges, and background outside
the edit mask remain identical to the raw composite. Wrong-sized results fail
inline. Each final candidate exposes its exact prompt, source summary, and
original raw composite for inspection.

**Assemble from references** sends the original pinned backdrop first, followed
by visible groups in back-to-front depth order (layer order breaks depth ties).
It supports up to ten visible sources, including one base backdrop. Placement
instructions describe each full source-image rectangle using the same X/Y and
width controls, source aspect ratio, backdrop fit, overlap order and canvas
clipping. Qwen preserves identities, clothing, poses, props and internal group
arrangements while integrating lighting, edges and contact shadows. The complete
generated image is saved; no local seam mask or pixel-preserving blend is applied.
Wrong-sized results fail inline in either mode.

Reference assembly does not use cutout extraction or keep/remove corrections.
Those controls still affect the placement preview and composite finishing.
Exact placement is a model instruction rather than a pixel guarantee; compare
both modes on the same sources before concluding that artifacts have improved.
Reference candidates show their mode and source summary without a raw-composite
comparison link. Retrying a failed assembly image reuses its frozen prompt,
sources, dimensions, mode and seed even after the current assembly changes.

Switching modes preserves the prompt text but requires **Write prompt** or a
manual edit before rendering a prompt from the previous mode. Choosing a previous
prompt restores its recorded mode. In-flight jobs keep their original mode and
cannot replace the active prompt after a mode switch. Interviews and prompt
writing remain available before any source images are added.

## Change interview and prompt models

Every subscene, backdrop, and final assembly has independent **Interview model**
and **Prompt model** controls. Blank inherits `[AIModels] NarrativeScene`;
the next-run label shows the effective choice. Choices save with the target
without changing global configuration.

Choose an Ollama model/alias or a `codex:<model>` identifier. The controls offer
existing model suggestions and accept newly available identifiers. **Refresh
models** refreshes Ollama discovery; a discovery failure preserves the current
choices. Codex requests use the installed CLI, read-only execution, the requested
JSON schema, and high reasoning effort. Ollama text and Qwen image requests
continue through AI_Proxy. No provider silently substitutes another model.

- **Continue interview** uses current inputs, direction, and history.
- **Re-run last interview** uses that run's original inputs and direction, with
  the newly selected interview model. Both responses and expandable drafts remain
  in the history.
- **Write prompt** uses current inputs and the prompt model.
- **Re-run last prompt** repeats the last prompt request's original inputs with
  the newly selected prompt model. It does not generate images.
- **Previous prompt outputs** lets you preview earlier outputs and explicitly
  choose **Use this prompt**.
- **Generate from inputs** writes a fresh prompt and queues images. **Render
  edited prompt** sends visible text unchanged and invokes no text LLM.

Each text job records its requested model before dispatch. Interview responses,
prompt outputs, and image candidates retain their original model labels after
selectors change. Manual prompt edits are marked and retain their originating
model. Legacy output without recoverable model information displays **Model not
recorded**. Provider runtime evidence is retained when available.

Codex requests and results persist under the target's `text-jobs` folder.
Restart recovery creates a new attempt for interrupted execution; late answers
cannot overwrite its result or newer user edits. Failures have an inline retry.

## Validation and visual limits

Focused Python tests cover compatible records, independent model selection,
request snapshots, reruns, output history, Codex execution/failure/recovery,
source isolation and deletion, alpha/cutout corrections, backdrop fitting,
placement, clipping, protected finishing, and protected candidate deletion.
Browser tests cover the existing Phase 1 flow plus model switching/history and
the assembly → placement/corrections → generation → selection/lock → download
flow. Provider results are fixtures; these tests do not assess model quality.

```powershell
python3 -m pytest tests/test_narrative_repository.py tests/test_narrative_scene_service.py tests/test_narrative_generation.py tests/test_narrative_phase2.py tests/test_narrative_qwen.py tests/test_file_proxy_producers.py tests/test_file_proxy_worker_contracts.py tests/test_web_workflow_services.py -q
npx playwright test tests/browser/narrative-scenes.spec.mjs tests/browser/dashboard.spec.mjs --grep "narrative|model selectors|final assembly|backdrop|universe pages create" --reporter=line
```

Recorded validation: **69 Python tests passed**, **6 browser tests passed**.
`node --check zet/web/static/narrative.js` and `git diff --check` passed. The
installed Codex CLI supports the schema/output and read-only execution flags.
Repeated real-image composite previews were byte-identical after fixing the
OpenCV extraction seed.

Local visual checks assembled the selected images from the three **Narrative
Phase 1 Test** scenes into separate copied records under
`test-results/narrative-phase2-visual-check`. Original library records were not changed.
Their previews retain recognizable subjects and props. Native Qwen RGBA images
had near-opaque alpha noise, which Auto now treats as an extraction case.

Hair edges, residual source flooring, and contact shadows still need visual
review and sometimes keep/remove corrections. Protected source-floor pixels
cannot be repaired by finishing; remove unwanted flooring in the cutout first.
Source perspectives and poses must already fit the scene. Real Qwen finishing
and live Codex/Ollama model output quality require review in the running workflow;
no production generation jobs were submitted during automated validation.
