# Narrative Scenes — Phase 1

Open **Story Telling → Narrative Scenes**, or `/narrative` in Zet Web.
This workflow stores new records in the active universe's `NarrativeStories`
folder. It does not create or load existing Scene Builder documents.

## Using the workflow

1. Create a narrative story and scene. Set the scene's camera, perspective,
   lighting, style, and physical setting.
2. Create scene elements using concise descriptions or existing library images.
3. Create a subscene or backdrop. Its page contains only its assigned elements,
   inherited visual context, inputs, interview, prompt, and eight image slots.
4. Describe the moment directly, or use **Continue interview** to draft narrative
   and staging. Follow-up questions are optional and LLM fields apply immediately.
5. **Generate from inputs** saves the inputs, writes a coherent prompt, and queues
   one or four images. **Render edited prompt** sends the visible text unchanged.
   Regenerating a slot uses the visible prompt when one exists.
6. Select the preferred image; optionally lock additional candidates. Selection
   and locking survive input edits. Clearing protected images or deleting their
   containing records asks for confirmation naming the affected images.
   Bulk rendering uses empty slots first, then replaces unprotected candidates;
   a full grid does not require clearing images individually to keep iterating.

Changes save automatically. Jobs persist and continue through the server's
background harvester even after navigating away. An inline retry is available
for failed LLM jobs and render slots. Late answers cannot replace newer slots
or concurrent edits. There are no prompt approval or stale-image gates.

## Configuration and boundaries

`[AIModels] NarrativeScene = "general:latest"` independently selects the
AI_Proxy LLM alias. Image requests use `comfyui-qwen-narrative` and the
`qwen_narrative_prompt` workflow. The AI_Proxy worker must run this repository
version, including the new preset and workflow module.

References are explicit, ordered library image bindings. Existing prompt
templates, global prompt additions, layout instructions, condensation,
scene IR, ranking, and legacy promotion do not enter this path.
Whole-scene character actions do not enter target interviews or synthesis;
only the target's own direction, assigned elements and shared visual settings
are supplied. This prevents unrelated actors leaking into backdrop prompts.

Subscenes default to a plain neutral background at 1216 × 832; backdrops
default to 1344 × 768. Returned image bytes, including alpha, are preserved.
Final assembly and background removal are covered in
[Phase 2](Narrative_Scenes_Phase_2.md).
Cross-scene backdrop reuse and independent subscene imports are covered in
[Narrative scene references](Narrative_Scene_References.md).

## Fresh-story acceptance

The real acceptance runner uses existing Tsaeytte, Valindia, and Kaeldor
references in a new **Narrative Phase 1 Test** story. Its three scenes cover
a single-subject action, a two-person parchment handoff, and a three-person
social exchange. Each has an independent backdrop.

```powershell
python3 Scripts/narrative_phase1_acceptance.py --advance
```

Repeat after work completes to queue a revised candidate for each target.
`--retry-failed` explicitly retries incomplete targets with no active job.
Open the printed page URLs to compare, select, and lock images. This runner
does not select images automatically: visual quality and preference need
review. A saved `acceptance.json` inside the new story records its progress.

Automated validation covers isolation, context, prompt/reference ordering,
zero-to-ten-reference Qwen graphs, failures, restart/background recovery,
concurrent edits, late answers, and protected deletion. Browser tests exercise
the complete interview/render/select loop and backdrop rendering using fixture
worker answers. Those tests validate behavior, not Qwen image quality.

## Validation record

The focused regression selection passed 84 Python tests:

```powershell
python3 -m pytest tests/test_narrative_repository.py tests/test_narrative_scene_service.py tests/test_narrative_generation.py tests/test_narrative_qwen.py tests/test_config_service.py tests/test_comfyui_render_service.py tests/test_file_proxy_producers.py tests/test_file_proxy_worker_contracts.py tests/test_entity_library_service.py tests/test_web_workflow_services.py -q
```

The two narrative browser tests and the existing universe smoke test passed:

```powershell
npx playwright test tests/browser/narrative-scenes.spec.mjs tests/browser/dashboard.spec.mjs --grep "narrative|backdrop|universe pages create" --reporter=line
```

The real acceptance story completed two candidates for each of its three
subscenes and three backdrops. Six reviewed baseline images were selected and
locked, and selection was verified with a fresh application instance. The
arrival revision corrected the rolled parchment; the handoff remained readable.
Backdrop regeneration verified that removing whole-scene actor context produces
empty environments instead of leaking the scene's cast into the backdrop.

Remaining visual limitations: the three-person exchange can reverse positions
or assign a gesture to the wrong person despite correct prompt text. The
`general:latest` alias also occasionally exhausted its response budget; explicit
retries succeeded. These remain visible iteration issues, without approval gates.

Two broader existing checks failed outside this change: the ad hoc image
generation test expects a prompt without the reference labels already added by
its HEAD service; the legacy scene startup browser test expects the obsolete
"Open/Create Scene Batch" label instead of "Open Scene Renders". They were
reported and left outside this implementation.
