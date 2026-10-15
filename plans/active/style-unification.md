# Style unification

Status: implementation in progress; approved 2026-10-14.
Date: 2026-10-14 (America/Los_Angeles).
Related specification: Joe's style-unification request in this chat; no external issue created.

## Goal and authorized scope

Establish a consistent level of realism, material detail, and rendering across Moonsea characters and their scenes. Bring locally bootstrapped Tsaeytte closer to the other party members, with room to simplify reconstructed outside images toward the same target.

Joe approved implementation and live batch review. Prompt/template review is not a gate. Use existing pages and normal AI Proxy workflows. First review: FRONT (8), FRONT_LEFT_3_4 (4), BACK_RIGHT_3_4 (4), through Canonical Adventure Gear. The implementation plan supplied in the latest user message supersedes earlier draft review gates below.

Two intended capabilities:

1. Improve the Body-Reference → Head-Image → Character-Assembly → Costume-Dressing prompt chain and character authoring template. Tsaeytte starts from text, with no old character image supplied to generation. Locally generated upstream references remain necessary for assembly and dressing; jewelry and embroidery references are permitted.
2. Add an Image Generation deconstruct/reconstruct workflow: a selectable vision model describes an outside image without its rendering style; Joe reviews that description; Qwen Image 2.1 generates from text using the destination universe style. The source image goes to analysis only.

Existing Tsaeytte images may be superseded during a later rerun. Preserving their current look is not a goal. This does not require removing integrity checks, rewriting historical artifacts, or changing global lock behavior.

## Investigation evidence

### Images and records inspected

- All three supplied PNGs under `C:/Users/Joe/.codex/attachments/5cd0d8f3-4d2b-4cea-ab57-a9f752cc418e/`.
- The actual selected Final assembly, read directly from authoritative Narrative storage:
  - Universe: `E:/Zet/Zet_Library_v5/Moonsea`.
  - Story `9163fb390cf65e529fc3c95403f1379b`, scene `5eba6ab81b26505c879df8a440017885`.
  - Assembly target `bb316ad2aec45ea9a9b9c15f1465db8f`.
  - Selected candidate `fc71e5ff51004b02a5a3b90e2c68dc6f`, `images/fc71e5ff51004b02a5a3b90e2c68dc6f.png`, 1344 × 768, `harmonize_composite`.
- Read-only SQLite inspection of `catalog.sqlite3`, including Freydis asset `16878a07-a727-401e-a0fd-418f2463e662` ("Freydis From Prompt"), its saved prompt and 768 × 1024 image.
- Tsaeytte Adult's selected/locked front Body, Head, Assembly, and Canonical Adventure Gear images, their batch specs, dependency chain, and saved render prompts.
  - Body: batch `20260930_141908_855839`, candidate `F-004`.
  - Head: batch `20261001_214714_922973`, candidate `F-003`; `front_source` is empty.
  - Assembly: batch `1ad652e5da2c45a7b7401d3c4461378a`, candidate `F-003`.
  - Dressing: batch `8bc12d37389e46d29f12f7d70f4f02bd`, candidate `F-003`; current published asset `81269748-46f2-4fa0-b11b-bdb625855e65`.

The supplied local comparison and current published dressing image look closely related, but their byte hashes differ. They are separate evidence; neither is silently substituted for the other. Older saved render prompts establish actual inputs, while current source files establish what a new compilation would use.

### Findings and implications

| Finding | Evidence | Implication |
| --- | --- | --- |
| The requested style itself invites anime treatment. | Moonsea `universe.json`: "Painterly semi-realistic fantasy illustration with anime-influenced facial stylization and refined linework." The saved scene style independently requests anime-influenced facial proportions. | Replace ambiguous stylistic shorthand with explicit anatomy, shading, edges, and material expectations. Updating the universe alone will not remove saved scene wording. |
| Tsaeytte's identity prose repeats that treatment. | Adult `Character.md` and the actual front Head prompt request "large anime-influenced almond eyes" and "slightly stylized large-eyed fantasy proportions". Core identity prose also mentions anime proportions. | Separate recognizability from the old rendering conventions. Preserve violet almond eyes, face shape, ears, skin tone, bob and adult age; make the intended eye proportions explicit. |
| Body establishes a relatively smooth, visibly painted surface before assembly. | Inspected published Body image and saved `Qwen_Body_Reference_Prompt.md`. | Address body volume, skin shading and surface finish upstream as well as the face. Do not mistake the deliberately simplified gray mannequin head for a defect. |
| Head already contains fine hair and eye detail, but retains stylized facial construction. | Inspected published 1024 × 1024 head and saved `Qwen_Head_Image_Prompt.md`. | "More detail" alone is insufficient. Facial planes, eye treatment, contour emphasis and material response need separate attention. Fine detail also becomes less visible at full-body/scene scale. |
| Assembly deliberately carries the input style forward. | `character_assembly_v2.md`; `character_assembly_style_instruction()` defaults to `MATCHED_STYLE`, allowing mostly junction work. `HARMONIZE_STYLE` matches the head to the body and disallows repainting the body. | Generate compatible sources first. Existing HARMONIZE_STYLE is not a general restyling operation. Scope preservation to identity/geometry, and explicitly state the limited surface changes a stage may make. |
| Dressing preserves all non-costume content and lighting. | Current and actual saved Dressing prompts. Costume sources already describe materials and accept separate jewelry/embroidery bindings. | Richer garment material instructions can improve clothing, but cannot reliably repair a stylized face or body under the current contract. Do not make dressing responsible for rebuilding anatomy. |
| Freydis used the same universe style sentence successfully. | Saved asset prompt starts with that sentence, then supplies roughly 1,758 words including skin variation, hair strands, leather construction, fur, fabric weight, wear and metalwork. | The checkpoint can render the desired material richness. Content-specific construction cues are a plausible contributor; this is an inference, not a controlled comparison. Prompt length itself is not the proposed fix. |
| Fine view control is already shared infrastructure. | `view_conditioning_service.py`, `PromptTemplateService.select_sections`, costume instructions, and `costume_dressing_orientation_metadata()`. Assembly already supplies separate body/head contexts too. | Reuse existing view domains, aliases, defaults, spatial annotations and provenance. Earlier character sources can use more precise tagging without a second parser or a wholesale pipeline rewrite. |
| Visibility filtering does not itself relax a preserve contract. | Tagged sections are selected before broad preserve prose is rendered by task templates and `chatgpt_prompt_contract.py`. | Both the emitted source facts and the task-level preservation wording must agree. A hidden face should not cause a turn merely to satisfy an identity checklist; visible identity need not imply frozen linework or shading. |
| Image Prompt Generation currently copies source style. | `ImagePromptGenerationService.INSTRUCTIONS` explicitly requests art style; the model comes from a global setting; jobs are currently in memory. | Add a distinct reconstruction analysis purpose and a request-specific model choice. Preserve existing Generate Prompt and Generate Identity behavior. |
| Image Generation's style action is a browser text prepend. | `zet.js` "Add Universe art style" handler; `AdHocImageGenerationService` renders supplied prompt text. Its displayed model is a Qwen status label, not an analysis-model selector. | Reconstruct must explicitly compose destination style with reviewed content, with a separate analysis selector. Avoid accidental repeated style insertion. |
| Narrative currently inherits scene values, not live universe style. | `NarrativeSceneService.target()` builds inherited/effective context from scene fields and target overrides. The selected assembly prompt asks for coherent light/color/shading but contains no explicit target material-detail standard. | Give Narrative an explicit way to use current universe style and carry it through synthesis, including harmonization. Preserve intentional scene/target overrides. |
| Assembly layers bind frozen source images. | This assembly's Tsaeytte/Snarlspark layer binds candidate `8a8045ffe1eb4b87b05791b3a2162912`; the subscene currently selects a different candidate. | New locks or selections alone do not update this composite. Later calibration must regenerate the pair and explicitly refresh/rebind its assembly layer. |

### Authoritative implementation and documentation

- [Prompt ownership](../../Docs/COMPONENTS/PROMPTS.md), [local character lifecycle](../../Docs/COMPONENTS/LOCAL_CHARACTERS.md), [Narrative](../../Docs/COMPONENTS/NARRATIVE.md).
- [Architecture](../../Docs/ARCHITECTURE.md), [data model](../../Docs/DATA_MODEL.md), [invariants](../../Docs/INVARIANTS.md), [code map](../../Docs/CODE_MAP.md), [testing boundary](../../Docs/Testing.md).
- Four active `*_v2.md` prompt templates named below; their corresponding `Scripts/Run_*_Jobs.py` compilers; `pipeline_compiler_support.py` and `chatgpt_prompt_contract.py`.
- `Shared_Library/Characters/_Shared/Character_Template.md`, `Character_Template_Instructions.md`, and the costume template/instructions as the existing granular-view example.
- `image_prompt_generation_service.py`, `ad_hoc_image_generation_service.py`, `image_generation_workspace_service.py`, their web routes and the Image Generation controls in `zet.js`/`index.html`.
- Existing S1–S3 scenarios and fixture behavior. No live generation was requested or performed in this investigation.

## Implemented visual target

Aim initially for detailed naturalistic fantasy illustration between current Tsaeytte and Freydis. Keep an illustrated finish and expressive faces while reducing graphic eye/contour treatment and introducing believable material differences. Uniformity means common rendering rules, not identical age, dirt, wear, skin texture, or contrast on every character.

Current Moonsea **Canonical Art Style**, applied with original files backed up before editing:

> Detailed naturalistic fantasy illustration with a restrained painterly finish. Use believable adult anatomy and dimensional facial planes, with expressive eyes proportionate to the face and the character's species. Model forms through gradual light and shadow, subtle warm and cool skin variation, and natural highlights. Distinguish skin, hair, woven cloth, leather, metal and gemstones through their construction, texture and response to light. Keep detail legible at full-body and scene scale, with controlled edges and consistent visual density. Avoid flat cel-shaded regions, heavy contour outlines, plastic skin and oversized anime eyes. Preserve each character's authored age, species and distinctive features. Lighting direction, pose, framing and background come from the task.

Use this existing multiline setting first; it can contain the general artistic rules without adding a parallel style-settings schema. The technical Body task still gets a featureless mannequin head, simple fitment clothing, and a neutral background. Those are scoped task requirements and do not suppress naturalistic treatment of the exposed body.

Tsaeytte authoring changes implemented; rendered image quality remains subject to batch review:

- Replace "large anime-influenced almond eyes" with "expressive violet-purple almond eyes, slightly large within believable adult elven facial proportions; defined eyelids, naturally seated eyes and restrained highlights".
- Replace the stylized head/body statement with adult elven proportions and a specific reminder that her petite build does not imply a childlike face or enlarged head.
- Keep her soft heart-shaped face, small refined nose/chin, warm golden-beige skin, distinctive outward/upward ears, violet color and thick asymmetrical black bob.
- Apply coherent wording to the visible head facts, identity sections and view-specific restatements actually used by this chain. Do not add unrelated character redesigns.
- Use naturalistic skin variation, cheek/nose/eyelid planes, grouped hair strands and small highlights; avoid adding Freydis's scars, dirt or weathering to Tsaeytte merely to create texture.
- Retain the garment design and its reference bindings. Describe woven cloth, seams, gathers, weighted folds, leather grain/creasing and distinct metal/gem highlights at the approved visual density.

## Style and preservation contract

1. Universe style owns the shared visual treatment. Character/costume sources own identity, construction and materials. Task prompts own framing, orientation, lighting and allowed transformations.
2. Existing view conditioning determines which authored facts are visible. Use `[head:face_visible]`, `[head:rearish]`, `[body:front_torso_visible]`, explicit views, section defaults and spatial annotations where appropriate. Reuse existing alias meanings; visibility groups are authoring filters, not a new guarantee of geometric visibility.
3. Preserve identity, geometry and orientation independently from rendering treatment. Explicitly allow the shading/edge/material changes assigned to the stage. Scope exceptions consistently in both generic change/preserve contracts and task-specific prose.
4. Do not add independent head turns or relax Assembly's supported same-view inputs as part of this work. Better visibility authoring does not authorize new geometry workflows.
5. Head FRONT and Body FRONT bootstrap from text. Subsequent views may use their new local front anchors; Assembly and Dressing use the new local source chain. No legacy Tsaeytte portrait, full-body image or group composite enters that bootstrap render manifest.
6. Reconstruction source bytes are analysis inputs only. Extracted content plus the current destination style form a text-to-image request. Keep source provenance distinct from `source_asset_id`, whose current meaning is an editable source/replacement workflow.
7. Freeze the effective prompt/style and model/source provenance when submitting work. Retry reuses frozen inputs. Regenerate/Recompile explicitly takes current sources. Style edits do not rewrite submitted jobs or saved prompts.

## Implementation status

All implementation uses existing pages and one agent. The approved implementation plan in chat supersedes the earlier prompt/draft approval gates.

| Packet | Status | Result / validation |
| --- | --- | --- |
| WP1 Shared style | Complete locally | Shared reader/composer, compiler source attribution; disposable composition/snapshot checks passed. |
| WP2 Authoring | Complete locally | Shared character template/instructions and Moonsea Tsaeytte Adult character/costume source edits; originals under Moonsea `backups/style-unification-20261014/`. |
| WP3 Body/Head | Complete locally | Active templates establish dimensional anatomy, facial planes, skin/hair detail; three-view disposable compilation passed. FRONT remains text bootstrap. |
| WP4 Assembly/Dressing | Complete locally | Preserve source detail and geometry; costume material detail and supporting design-image roles are explicit. Existing S2 passed. |
| WP5 Narrative | Complete locally | Explicit universe-style scene choice, legacy defaults, target overrides, frozen provenance, harmonization guidance and existing editor controls. S1/S3 and disposable precedence checks passed. |
| WP6 Reconstruction backend | Complete locally | Durable universe-owned analysis and automatic text-only render handoff, validated sources/models and slot ownership. Prepared-response checks passed. |
| WP7 Existing Image Generation UI | Complete locally | Library/upload/paste source, per-request analysis model, Reconstruct & Generate, optional text editing, dirty/stale reply protection, existing result slots. Disposable desktop/narrow browser checks passed. |
| WP8 Provenance/replay | Complete locally | Analysis source/model/style/content and actual render prompt/seed retained through save/load, retry, edited regeneration and import. Disposable checks passed. |
| WP9 Validation/knowledge/live batches | In progress | Code checks/knowledge updated; production rollout and actual three-view batches remain outstanding. |

## Implemented reconstruction interface

- `GET /api/image-generation/reconstructions/options`: available Codex/Ollama vision choices, configured default and current universe style.
- `POST /api/image-generation/reconstructions`: library `asset_id` or uploaded/pasted `image`, selected `model`, optional artistic `notes`, existing count/width/height. Reserves existing empty slots, snapshots source/style and starts analysis. Successful analysis automatically submits Qwen txt2img with zero source references.
- `GET /api/image-generation/reconstructions/{id}`: durable analysis/handoff status, content, uncertainties, model, style and render request identity. Polling does not resubmit.
- Source and destination render inputs are separate. Main prompt fields are not overwritten by analysis. Optional edited text can populate the existing generator for another render.
- Current model selection is visible and job-specific; it does not change global defaults. Interrupted analysis fails explicitly; completed render handoffs use the ordinary render status/retry controls.

## Observed validation

- Verified `.venv/Scripts/python.exe` is Python 3.
- Approved isolated `npm.cmd run test:e2e`: final run **3 passed (27.5 seconds)**; earlier runs also passed. No permanent tests or dependencies added.
- `test-results/style-unification-check.py`: passed shared style, Narrative compatibility/override/boolean validation, three-view Body/Head compilation, automatic reconstruction, source reference exclusion, source byte preservation, selected model, provenance/save-load/import, edited regeneration, reservation clearing and interrupted-analysis checks using an isolated fixture/private queue and prepared responses.
- `test-results/style-unification-browser.mjs`: passed upload/library selection, selected model, automatic slot allocation, txt2img behavior after an img2img session, unchanged manual text, dirty analysis-field protection, reload, optional editing and 1440/850-pixel layouts. Screenshots visually inspected. Helpers/screenshots are ignored disposable artifacts.
- JavaScript syntax/import/Python syntax checks passed. Final scoped diff review, `git diff --check`, and new-document local-link/whitespace checks passed. Existing unrelated changes remain intact.

## Live rollout constraint and remaining work

The running dashboard reports production revision `2e3ad3517bc46e61f6c57ced46163ef06a3ce97c` from an immutable Zet_Runtime release, not this modified checkout. The local execution environment has `ZET_WORKER_MODE=1`; `ConfigService` correctly refuses loading production config. The one-off direct live helper stopped at that guard, before creating runs or queue submissions. The guard was not removed or bypassed.

New source data/style is saved in Moonsea, but complete new runtime/template behavior requires the validated code to be rolled out through the normal release workflow. That deployment is a separate production action requiring Joe's authorization. Do not submit batches with older templates and label them as validation of the complete new prompt pipeline.

After rollout, use the running dashboard APIs and normal AI Proxy workflow to produce FRONT (8), FRONT_LEFT_3_4 (4), BACK_RIGHT_3_4 (4), through Canonical Adventure Gear. Choose provisional upstream sources using current ranking/gates and image inspection; keep published locks intact. Present whole batches in existing galleries. Review then determines further iterations, remaining views/outfits, and later explicit Narrative group/layer refresh.

Keep this plan active: local implementation is not proof of artistic style unification.

## Closeout checkpoint

Local implementation and isolated verification are complete. Additional checks passed for stale library sources, malformed analysis responses, cross-universe job lookup, preservation of saved-prompt style provenance at render time, settings rebind while analysis is active, and changing the analysis model without applying a late reply over edited text. Legacy migration explicitly retains its authored style.

Joe authorized publication and deployment in chat on 2026-10-15. The scoped change is being isolated for publication through the normal feature PR and deployment workflow. No release was published or promoted, no issue-worker guard was bypassed, and no live render job was submitted. Keep WP9 active pending rollout, the three-view dressed batches and Joe's image review.

## Authorized rollout � 2026-10-15

Joe authorized publication and deployment, followed by the approved three-view batches. A managed release checkout excludes unrelated workspace changes (including the earlier CODE_MAP/LIBRARY edits). In that isolated checkout, S1�S3 passed (28.6s), disposable backend and browser reconstruction checks passed, JavaScript syntax checks passed, and diff whitespace checks passed. Scoped review confirmed saved-prompt style provenance, legacy scene compatibility, analysis-only source references, reservation fencing and frozen retries. Publication and deployment are in progress; live artistic acceptance remains pending.
