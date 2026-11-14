# Pipeline LLM requirements

This document inventories the task-level requirements of registered creative LLM roles. The role registry in [`llm_role_service.py`](../zet/services/llm_role_service.py) remains authoritative for role keys, default settings, provider/capability constraints, lifecycle status, and Qwen skill selection. Update this inventory when producers, attachments, schemas, or lifecycle status change.

## Shared requirements

Every role in the managed creative LLM registry requires text input and text output. Structured tasks require reliable JSON-schema output. **Vision is required only when the actual request attaches images.** Image references described in text, render instructions, and downstream ComfyUI bindings do not themselves require a vision model. AI_Proxy sends attached files to Ollama through `/api/chat` or `/api/generate` and validates model capabilities through its catalog. Zet freezes ordered attachments with each request. Follow the shared AI job and role documents for publication and inheritance behavior.

Context ranges below estimate the complete request: system instructions, prompt, schema, accumulated workflow history, image tokens, and output allowance. They are planning estimates, not hard limits. Image-token use varies by image size and model. Each Character Wizard pass sends a short section prompt and up to three ordered reference images. The 64K alias setting provides headroom for unusually long requests; validate GPU residency and latency with actual long requests.

## Task categories

| Category and context estimate | Active task families, output, and actual image inputs |
| --- | --- |
| Interview and intake, 4-16K typical and up to 24K for long history | **Character Wizard** returns concise plain-text facts for one section at a time. It uses the same selected model and ordered reference images for Body, Head, Hair, and section refinement. **Narrative interview** proposes scene-field updates, conflicts, and questions. It is text-only unless a new subscene interview explicitly includes one candidate image. **Minor Character interview** proposes editable field replacements and reasons, attaching its locked reference image followed by optional candidate feedback. **Minor Character intake** fills blank shared fields from one Inventory image. **Costume Wizard** asks focused questions while drafting from image-specific observations. Observation calls each attach one corresponding costume reference. Evidence review attaches the original references in session order. |
| Prompt and template authoring or improvement, 8-24K typical, potentially higher for large eight-view reviews | **Narrative prompt synthesis** returns scene and rendering JSON from story, scene, history, style, and ordered render-reference metadata. It attaches no images itself. **Image-to-prompt drafting** attaches one image and writes generation prompt JSON; its separate Inventory identity request also attaches that image but returns stable identity facts. **Reconstruction prompt drafting** attaches the target and source references in request order, with analysis-only sources still attached for vision. **Minor Character prompt writing** attaches the locked STYLE reference for the initial prompt and the style reference plus any selected view evidence for edits. **Character description** writes reusable appearance fragments from its reference images. **Costume template drafting** reconciles serialized observations and user answers, then writes a structured template; the drafting synthesis call is text-only. **Governing-template review** currently uses text-only compiled previews and source templates. The active Character Asset Container review can instead attach one finished candidate. This path selects through `character_prompt_review` and publishes under `template_revision`. **Local prompt improvement**, **post-render Character.md improvement**, and **post-render Costume template improvement** attach the selected render and relevant references, then propose scoped source corrections. **Dedicated character refinement** attaches the selected image and its selected comparison inputs, then returns correction suggestions. Preserve source markers, protected structure, identity, ordered bindings, and exact text where the workflow requires it. |
| Visual observation and QA, 2-12K typical | **Inventory metadata** extracts stable identity and costume facts from one image. **Minor intake** extracts only blank shared template fields from one Inventory image. **Costume observation** extracts visible facts from one image at a time. **Costume evidence review** checks the draft against original references and returns findings without rewriting. **Costume render review** attaches the test render followed by source references and proposes refinements. **Body assessment, Codex and local**, attaches one candidate, its target sources, and an optional FRONT anchor in that order. **Costume trial acceptance review** assesses four private view images against unfinished criteria and does not make the human decision. **Recipe Lab QA** attaches the supplied comparison/reference images and candidate images for a rubric assessment, with no prompt edits. **Reconstruction review** attaches candidate, target/source images, then optional anchor, and returns scoped corrections. **Minor Character review** attaches the candidate and its STYLE/reference evidence. **Character template evidence review** attaches the selected candidate when run in image mode. |
| Comparative ranking, 16-32K or more for a full board | **Comparative candidate ranking** orders up to eight candidates and may attach captured render inputs and comparison images after the candidate images. The prompt maps each candidate to its slot, inputs, and saved prompt. It returns candidate IDs with visible evidence reviews. Current provider restriction is Codex-only, including Luna Review in Zet_Tester. A later local ranking trial would need to validate the full image-and-prompt context; this is outside current alias readiness. |

## Registered roles and lifecycle

This table reconciles all 35 registry entries. “Vision when attached” means capability validation requires vision when the request carries image files; the task may also have a text-only mode. Provider restrictions and role settings remain owned by the registry.

| Role | Producer and task | Image input | Lifecycle |
| --- | --- | --- | --- |
| `character_wizard` | Character Wizard interview and template changes | 1-3 ordered references; vision required | Active |
| `narrative_interview` | Narrative scene interview | Text; optionally one candidate image | Active |
| `narrative_prompt` | Narrative scene prompt synthesis | Text and reference metadata | Active |
| `image_prompt` | Image Generation prompt drafting | One image; vision required | Active |
| `inventory_identity` | Inventory identity description | One image; vision required; Codex-only | Active |
| `inventory_metadata` | Inventory catalog identity and costume metadata | One image; vision required | Active |
| `reconstruction_prompt` | Image reconstruction prompt drafting | Target and ordered source images; vision required | Active |
| `reconstruction_review` | Reconstruction candidate comparison and correction | Candidate, sources, optional anchor; vision required | Active |
| `minor_intake` | Minor Character blank-field intake | One Inventory source; vision required | Active |
| `minor_interview` | Minor Character field interview | STYLE reference, optional feedback image; vision required | Active |
| `minor_prompt` | Minor Character prompt writing | STYLE reference or reference plus candidate; vision required | Active |
| `character_description` | Quick Character reusable appearance description and fragment writing | Ordered references; vision required | Active producer is legacy/compatibility path |
| `character_review` | Minor/Quick Character visual comparison | Candidate and source/anchor images; vision required | Active for Minor Character; Quick Character service retained |
| `costume_observation` | Costume Wizard source observation | One reference per call; vision required | Active |
| `costume_template` | Costume Wizard template synthesis and revision | Synthesis text-only; vision required when review attachments are supplied | Active |
| `costume_evidence_review` | Costume draft evidence check | Session reference images; vision required | Active |
| `costume_render_review` | Costume test-render corrections | Render then source images; vision required | Active |
| `character_prompt_review` | Governing Character.md template review, text or candidate mode | Text-only or one selected candidate; vision required for candidate mode; Codex default, Ollama supported | Active |
| `template_revision` | Historical image-backed template revision producer | Representative evidence images; vision required; provider follows selection path | Compatibility metadata; current container producer publishes this role |
| `local_prompt_improvement` | Local rendered-image prompt diagnosis | Selected render and labeled comparisons; vision required; Codex-only | Active |
| `post_render_character_prompt` | Post-render Character.md edits | Selected render and evidence images; vision required; Codex-only | Active |
| `post_render_costume_template` | Post-render Costume source corrections | Selected render and evidence images; vision required; Codex-only | Active |
| `post_render_costume_evaluation` | Four-image Costume trial assessment | Four trial renders; vision required; Codex-only | Active |
| `prompt_generator` | Pilot prompt generation | Frozen source references; vision required | Retired |
| `prompt_generator_evaluation` | Pilot image scoring | Candidate images; vision required | Retired |
| `prompt_generator_direction` | Pilot refinement direction | Four images and accepted conclusions; vision required | Retired |
| `character_refinement` | Selected Character image refinement | Selected image and comparison inputs; vision required | Active |
| `image_ranking` | Comparative candidate ranking | Up to eight candidates, optionally source comparisons; vision required; Codex-only | Active |
| `body_review_codex` | Body candidate assessment | Candidate, sources and optional anchor; vision required; Codex-only | Active |
| `body_review_local` | Body candidate assessment | Candidate, sources and optional anchor; vision required | Active |
| `recipe_qa` | Recipe Lab visual rubric QA | Candidate and rubric reference images; vision required | Active |
| `asset_workflow` | Traditional asset-stage responses | No image capability requirement in role contract | Compatibility; traditional character generation retired |
| `prompt_condense` | Traditional prompt condensation | Text-only | Compatibility |
| `scene_builder` | Retired Scene Builder configuration | No active producer | Retired |
| `prompt_analysis` | Retired Scene Builder prompt analysis | No active producer | Retired |

## Model selection and current test scope

Explicit task or session model selection takes precedence over a role override and the original configured model. A model needs vision capability when the current request attaches images, even if a role also supports text-only work. AI_Proxy owns the execution, GPU handoff, and Ollama call. Zet owns task preparation and result validation.

The initial Zet_Tester comparison uses the case-selected authoring model for workflows that honor it and keeps Luna Review fixed. The ranking role is currently Codex-only, so the two Ollama aliases are not yet candidates for changing the ranking model. Test Character Wizard, image-backed template improvement, Minor Character authoring, and Narrative interview and synthesis with identical inputs and fresh names. Record alias/base digest, actual attachments, context, latency, token counts where available, offload, schema/domain validation, and visual observations. Investigate repeated failures before changing prompts.

Directed, text-only Ollama Head-Image Edit template review uses `character_template_line_review` with no image attachment and returns at most one line ID and replacement. Zet maps the ID to a globally unique editable line in the frozen source and reconstructs the existing finding contract. The experimental 384-token cap is recorded in the producer implementation. Five fresh API calls per model passed selection and eight compiled previews; disposable review-criteria and uniquely anchored view-tagged line checks also passed.
