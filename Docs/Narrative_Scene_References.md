# Reuse Narrative backdrops and import subscenes

On a Narrative scene page, choose **Reference backdrop from another scene** or
**Import subscene from another scene**. The source picker starts with the current
story and also offers stories in the active universe. Preview the source inputs,
prompt and image before applying it. These actions leave the source unchanged.

## Backdrops

On an existing backdrop page, **Attach source backdrop** pins a source image
without replacing destination inputs, candidates or selection. A source's
selected image is the default. If none is selected, choose a completed candidate.

The destination keeps its own copy of the image and source metadata. Later source
edits do not propagate. **Use current source selection** explicitly refreshes the
pinned image and metadata, while retaining destination edits and existing images.
Pinned images remain usable after deleting the original source.

The source panel distinguishes the inputs recorded for the chosen image from the
source's current authoring text. Older candidates may have no recoverable prompt
or generation inputs; the panel labels those omissions. **Copy current source
inputs** and **Copy generation inputs** explicitly replace the destination's text,
dimensions and local visual overrides. They do not replace its element assignments
or editable prompt. Expand **Source inputs and prompt** to inspect the original
prompt and use it as editing material.

- **Use unchanged image** adds the exact original bytes to an empty local slot.
- **Create cropped image** adds a crop without generation. The visual crop box
  follows the output aspect ratio. Center sliders position it; zoom reduces its
  size. The rectangle stays inside the source. **Preview crop** shows the output.
- **Expand** uses Width/Height, the expansion side, and adaptation direction to
  generate additional environment through Qwen.
- **Change viewpoint** or **Other edits** uses adaptation direction and the
  destination inputs to generate a revised backdrop. The interview can develop
  those directions before writing a prompt.

Local reuse and cropping preserve existing candidates and require an empty slot.
They select the new candidate only when no image is selected. Select and lock
additional images through the usual controls. Reused and adapted images are
ordinary local backdrop candidates and can be added to final assemblies.

Generated edits bind the pinned backdrop as image 1, followed by assigned element
references. The total limit remains ten images. **Render edited prompt** sends
its visible text unchanged, so manually edited reference numbers must match this
order. Choose a generated operation before using the image-generation buttons;
unchanged reuse and cropping use their local buttons instead.

Jobs freeze their prompt, dimensions, source image, ordered references, adaptation
direction and seed. A failed adaptation's **Retry** reuses that request even after
refreshing the source or changing the destination. Late text responses remain in
history but do not replace inputs or prompts after a source/adaptation change.

Expansion and viewpoint changes are generated interpretations. They can redraw
detail and cannot recover unseen architecture from a single 2D image. Compare
candidates before selecting a result; the workflow does not reconstruct a 3D set.

## Subscene imports

Importing creates a new subscene with copied narrative, staging, physical context,
framing and dimensions. Only its assigned elements are imported, including their
appearance notes and library bindings. Each defaults to a new local element;
choose **Use existing** to map one explicitly to an element already in the
destination scene. Names never trigger automatic merging.

Destination scene visual context is the default. Check **Copy source visual
context as local overrides** to preserve the source's camera, setting, lighting,
perspective and style for the new target.

The new subscene starts with no prompt, interview history, jobs, candidates or
selection. Its source panel preserves the original text and prompt for inspection.
Edit its moment and poses manually or through the interview, then write a prompt
and generate normally. The rendered source subscene image is not an image
reference; only the imported elements' library bindings enter generation.

Source text and copied element definitions remain independent. Library image
bindings continue to use the existing library lifecycle and availability checks.

## Validation

Focused backend coverage is in `tests/test_narrative_references.py`. The Narrative
browser suite covers cross-scene source picking, unchanged byte preservation,
cropping, adaptation, import, interview and ordinary generation using fixture
worker responses. These checks do not assess live model image quality.

```powershell
.venv\Scripts\python.exe -m pytest tests/test_narrative_repository.py tests/test_narrative_scene_service.py tests/test_narrative_generation.py tests/test_narrative_phase2.py tests/test_narrative_qwen.py tests/test_narrative_references.py -q
npx playwright test tests/browser/narrative-scenes.spec.mjs --reporter=line
node --check zet/web/static/narrative.js
.venv\Scripts\python.exe -m ruff check zet/services/narrative_reference_service.py tests/test_narrative_references.py
git diff --check
```

A disposable copy of the real Arrival backdrop also verified byte-identical
unchanged reuse and a visually inspected 768 × 768 crop. The original Narrative
Phase 1 Test records were not modified. No live adaptation jobs were submitted.
