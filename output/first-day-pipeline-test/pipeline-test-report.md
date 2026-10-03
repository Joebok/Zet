# First Day scene pipeline test — 2026-10-03

Story: FirstDay. Scene: Chapter-01-Standing-in-Wonder.
Batch: bebc2869c8c04af094a63fc585168ff5.

## Assets and scene setup

Built-in Image Generation produced two independent full-body neutral character references, saved as schoolboy-1.png and schoolboy-2.png in this directory and imported as approved Entity Library assets. Kaeldor retains his existing individual reference. The Schoolboys element now anchors the enabled Schoolboys and Kaeldor element subscene. Its members are Kaeldor and the two boys. The main scene uses the selected group as one background reference, avoiding a second independent Kaeldor placement.

Prompt set for the individual references: painterly semi-realistic fantasy illustration with refined anime-influenced linework; one youthful male elf alone, full body, neutral three-quarter front pose on a plain cream background, clearly visible face, hands and boots, no text or extra people. Both wear ivory rolled-sleeve shirts, burgundy academy waistcoats with a gold crest, charcoal trousers and brown boots. Schoolboy 1 is slim, pale warm-skinned, copper-red-haired and freckled. Schoolboy 2 is slightly stockier, olive-skinned, short dark-haired and hazel-eyed. The source pose and background are explicitly ignored when these references are used in scenes. The configured-scene.json and submitted Qwen prompts preserve the exact scene generation instructions.

Subscene action: red-haired boy gently pushes dark-haired boy's shoulder; the dark-haired boy laughs and leans away with hands raised; Kaeldor stands to their right, grinning and pointing. Main scene: Tsaeytte foreground right, back three-quarter view, holding books and looking upward at the academy arch inscription, with the playful group small in the background. Her dialog is exactly “Potential is nothing without discipline”.

## Defects fixed locally

1. Scene Builder lacked a reachable action to turn an existing element into a subscene. Restored “Use element sub-render” using the existing service and handler.
2. An unavailable legacy Characters/Tsaeytte/Adult/Assets.json stopped dashboard startup before story navigation loaded. Story pages now continue loading when that unrelated catalog request fails.
3. Valid library references still attempted to load removed auxiliary resources (spire-archway and kaeldor). Library references now remain usable when the optional legacy fallback is missing.
4. Compiled scene IR serialized missing optional source paths as empty strings. AI_Proxy rejects blank file references. Missing paths now serialize as null. The two already queued jobs were repaired and their inventory hashes updated.
5. AI_Proxy managed scheduling treated invalid queue entries as executable jobs requiring a trusted backend. That prevented invalid answers from being published and held the entire queue with a misleading backend warning. Invalid entries now publish their normal invalid result without acquiring a backend. The trust requirement remains for executable jobs. This AI_Proxy change requires its next process restart to load; current jobs were unblocked by correcting their payloads.

6. Batch action controls now disable immediately while a mutation is pending, including review dropdowns and batch creation. Batch creation shows progress, and reopening a batch restores its saved name.
7. Qwen prompts omitted dialogue notes, line limits and pointer instructions. Those authored fields now reach the render prompt with an explicit visible-panel request earlier in the composition description.
8. Windows encoded the ranking subprocess input using the system encoding, causing Codex to reject the main prompt as invalid UTF-8. The shared ranking invocation now explicitly uses UTF-8 for input and output.

## Validation

- node --check zet/web/static/zet.js: passed.
- Browser regressions, scene-batches.spec.mjs and scene-pipeline-startup.spec.mjs: 2 passed (startup without old catalog, element subscene creation, candidate harvest, selection, publication and zine fixture workflow; delayed requests verify immediate busy controls and preserved review decisions).
- Full local scene batch and Qwen suites after the dialog fix: 26 passed.
- Library reference source tests: 2 passed.
- Shared image ranking runner suite with Unicode input: 2 passed.
- Scene render compiler and FileProxy client suites: 19 passed.
- AI_Proxy HTTP scheduler suite: 9 passed.
- Live UI: individual import used the existing API because Chrome's file-upload automation permission was unavailable; Scene Builder action, batch creation, queue submission, refresh and subsequent stage controls exercised through the browser.

## Improvement packets

Each packet is deliberately small enough for one focused implementation and verification pass.

1. Image import: add a service action that imports a generated local image with entity, label, provenance and reference role in one operation; expose it through the inventory UI. Validate an imagegen output round-trip and duplicate handling.
2. Queue diagnostics: show exact validation errors and trusted worker backend in proxy status and Zet job details; distinguish queued, held, starting backend and sampling. Validate malformed-job failure does not block the following valid job.
3. Legacy migration: validate and repair old auxiliary links when replacing them with library references. Show missing optional fallback as a warning with the valid selected asset still available.
4. Startup/restart feedback: avoid a long silent catalog reconciliation during startup; wait on server readiness after Restart Zet and retain the requested story page throughout recovery.
5. Subscene usability: distinguish background targets from element targets at creation, show membership and inherited placement clearly, and use human labels for candidate IDs. Display prompt reference roles next to each assigned asset.
6. Batch history feedback: refresh the history dropdown status alongside the current status banner, and distinguish a completed render from a rating failure. Candidate-count controls remain under their collapsed disclosure; the missing-name and busy-control defects are fixed.
7. Composition quality: expose exact character count and identity/reference assignment more prominently; check for duplicated characters, extra background structures, gaze direction and exact dialog when rating. First subscene candidate duplicated the dark-haired boy despite the three-character prompt.

8. Qwen field coverage: forward reference change/ignore/notes and structured relationship interactions into the natural-language prompt. They are not currently emitted directly by qwen_scene_prompt.py; this test states the required actions in composition and pose fields as well. Validate changes to each supported UI field alter the corresponding prompt instruction.

## Changed implementation files

Zet: zet/web/static/zet.js, zet/web/static/local_scene_batches.js, zet/web/templates/index.html, zet/services/story_service.py, zet/services/scene_render_compiler.py, zet/services/qwen_scene_prompt.py, zet/services/local_image_ranking_service.py, with their focused Python/browser regression tests. AI_Proxy: file_proxy/engine.py and tests/test_http_scheduler.py. Existing unrelated user edits were preserved. No dependencies installed; no commits or remote publication performed.

## Outcome

The first main generation produced three complete scene candidates containing all four characters and the academy arch. All three omitted the dialogue panel. Their rating exposed the Windows UTF-8 defect. They remain archived when the main group is rerendered using the corrected dialog instructions. The revised main generation completed and rated all three candidates successfully. Each contains Tsaeytte, both schoolboys, Kaeldor, the arch and an exact two-line dialogue box. The UI is left at AWAITING_HUMAN_SELECTION for the main scene; no existing locked main image was replaced. The selected subscene is candidate 002. No manual ComfyUI startup was needed. AI_Proxy started and stopped its managed backend automatically.

| Candidate | Review |
| --- | --- |
| main-001.png | Best distant background scale and upward head tilt; inner arch lettering imperfect. |
| main-002.png | Correct dialogue and all characters; group is large and Kaeldor partly occluded. |
| main-003.png | Clearest arch inscriptions, all three boys and correct dialogue; less obvious upward tilt. Luna rated this first. |

Live review: http://127.0.0.1:8081/?page=scene-batches&story_slug=FirstDay&scene_slug=Chapter-01-Standing-in-Wonder&batch=bebc2869c8c04af094a63fc585168ff5

Review copies, both individual reference images, the chosen subscene, initial candidates, exact submitted prompts, configured scene JSON and final batch metadata are saved in this directory. Validation totals: 58 relevant Python tests and 2 browser tests passed, plus JavaScript syntax checks and git diff --check in both repositories. The remaining refinement list is expressed as focused implementation packets above.
