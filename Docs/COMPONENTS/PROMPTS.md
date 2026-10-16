# Prompt compilation and reference contracts

Prompt generation spans character templates, structured scenes, and independent Narrative prose. This document owns shared compilation and attachment mechanics; scene workflow details live in [SCENE_BUILDER](SCENE_BUILDER.md) and [NARRATIVE](NARRATIVE.md).

## Character compilation path

Inputs are character/costume Markdown, job metadata/views/references, [Prompt_Task_Bundles.json](../../Config/Prompt_Task_Bundles.json), [Prompt_Templates](../../Config/Prompt_Templates/), and supporting section/view configuration.

1. [Compile_Character_Template.py](../../Scripts/Compile_Character_Template.py) `load_template_sections_with_sources` parses section markers with source provenance; `select_sections_for_prompt` resolves template-requested required/optional sections. Unknown/missing/invalid markers are compiler errors, not invitations to fabricate text.
2. [PromptTemplateService](../../zet/services/prompt_template_service.py) conditions sections through [view_conditioning_service.py](../../zet/services/view_conditioning_service.py), filters generation/analysis variants and local/traditional mode blocks, and passes selected text/metadata to the static renderer.
3. [Build_Static_Final_Prompt.py](../../Scripts/Build_Static_Final_Prompt.py) `render_static_prompt_with_source_map` resolves placeholders, metadata tokens and referenced-image citations. [Job_File_Utils.py](../../Scripts/Job_File_Utils.py) and [pipeline_compiler_support.py](../../zet/services/pipeline_compiler_support.py) centralize job/bundle/reference support.
4. `compile_*_job` functions in [Run_Body_Reference_Jobs.py](../../Scripts/Run_Body_Reference_Jobs.py), [Run_Head_Image_Jobs.py](../../Scripts/Run_Head_Image_Jobs.py), [Run_Character_Assembly_Jobs.py](../../Scripts/Run_Character_Assembly_Jobs.py), and [Run_Costume_Dressing_Jobs.py](../../Scripts/Run_Costume_Dressing_Jobs.py) produce artifacts used by active local services. [Run_Expression_Jobs.py](../../Scripts/Run_Expression_Jobs.py) and [Run_Scene_Appearance_Jobs.py](../../Scripts/Run_Scene_Appearance_Jobs.py) compiler files remain present; traditional generation retirement still applies.

Outputs include `Compiled_Sections.md`, final/analysis prompt variants where supported, `Prompt_Source_Map.json`, diagnostics, dependency manifests, and ordered image bindings. Source maps are the first tool for tracing unwanted text; edit canonical sources/templates rather than patching generated output as a lasting fix.

## View-conditioned source language

Use [shared templates/instructions](../../Shared_Library/Characters/_Shared/) and the authoritative parser for exact syntax. `ZET:VIEW_DOMAIN` chooses body or head context; `ZET:VIEW_DEFAULT` supplies visibility defaults; bullet view tags filter prose; `ZET:CANON_ONLY` and `ZET:SPATIAL` carry specialized semantics. Body and head can have independent orientations. `normalize_view` accepts supported aliases, while `resolve_anatomical_side` translates anatomical sides into screen/depth language for the requested view. Fixed spatial features require explicit visibility; unqualified left/right in spatial annotations can fail compilation.

Generation and analysis templates use `IMAGE_PROMPT_ONLY`/`ANALYSIS_PROMPT_ONLY` blocks; malformed/nested/unclosed variants fail. Consult the mode-filter implementation before changing local/traditional content. [View tagging specification](../../Docs-Joe/ZET_View_Conditioned_Template_Tagging_Spec.md) provides preserved design intent, but parser/tests own supported behavior.

## Scene and Narrative prompt paths

The structured scene compiler, Qwen scene prompt compiler, measured spatial guidance and cleanup are preserved in the [offline archive](../../Archive/scene-builder/README.md). They are not active producers. Shared character helpers and the Narrative/Qwen prompt path no longer import that geometry/compiler.

[narrative_prompt_service.py](../../zet/services/narrative_prompt_service.py) uses `llm_request` for structured interview/synthesis requests and `assemble_prompt` to combine coherent prose with deterministic image/reference bindings. It does not use the Scene Builder compiler as its authoring engine.

Active Narrative and local-character Qwen Image 2.1 renders use
[shared preparation service](../../zet/services/qwen_reference_preparation_service.py)
to prepare private reference snapshots. Machine settings in
`[ComfyUI.QwenImage21]` override the selected preset's per-reference and aggregate
pixel budgets. The default limits are 1,048,576 pixels per image and 6,291,456 total;
resizing preserves aspect ratio, alpha, reference order, and source bytes, aligns
dimensions down to multiples of 32, and never enlarges. Prepared graphs set
`TextEncodeQwenImage21.resolution=0`, so the encoder keeps the prepared reference
size instead of scaling it to the output canvas. Output latent dimensions remain
separate. Pending submissions recover their saved graph and prepared-image hashes;
they do not pick up changed settings. See [NARRATIVE](NARRATIVE.md) and
[DATA_MODEL](../DATA_MODEL.md) for settings and recovery details.
The same machine table configures the Qwen prefix cache (`cache_device` accepts
`auto`, `cpu`, `gpu`, or `off`; `cache_dtype` accepts `default`, `int8`, or
`int4`). Metadata records configured placement/precision separately from whether
ComfyUI inserted and ran the cache node.

Narrative text synthesis requests the shortest complete scene/rendering prose rather than fixed
word/character limits. It explicitly retains equipment exclusions, anatomy, gesture ownership
and the strength of relative-height comparisons. Action belongs in scene; rendering supplies
visual treatment without repeating action. This is model guidance, not a guarantee of live output.
Reference metadata does not establish physical height from source-image framing.

Subscene `use_transparent_background` controls interview/synthesis context and
deterministic final-prompt background constraints. Checked replaces the effective
visible setting with transparency, retains authored settings as labeled context,
and prioritizes genuine RGBA zero-alpha background over scenery prose. It retains
required subjects/props/supports and their lighting. Unchecked uses saved context;
neither branch imposes the former plain-neutral-background rule. Render does not
append or rewrite these constraints: users must use Write Prompt to update saved
text. Older frozen requests without the preference remain distinguishable.

Assembly `harmonize_composite` requests integration of the supplied placed image
while preserving layout, count, identities and complete groups. It refers to
pictured subjects/positions rather than individual names and supplies no separate
pair images. The full output survives; the finishing mode's prohibition on subject
redrawing is not used. [Narrative](NARRATIVE.md) owns mode/result handling and limits.

`_bind_reference_names` tags only the first mention of each reference label across scene then
rendering prose. The complete References section remains authoritative for frozen image order.
Case-insensitive duplicate labels still fail; longer names match before shorter ones, possessives
are preserved and backdrop-source offsets remain intact. Assembly/source-specific rules remain
separate. Interview proposal/review semantics are owned by [Narrative](NARRATIVE.md).

## Shared contract, failure modes, extension points

[chatgpt_prompt_contract.py](../../zet/services/chatgpt_prompt_contract.py) owns current prompt schema 2, valid render modes (`generate`, `edit`, `composite`), input roles, contract/diagnostic helpers, and reference mappings. Attachment order links prompt citations to exact frozen bytes; preserve it through compile, queue publication, and backend submission. See [INVARIANTS](../INVARIANTS.md).

Common failures: missing required sections/source images, unresolved placeholders, malformed view/mode/variant directives, stale reference descriptions/dependencies, and an attachment order that no longer matches citations. Extend the relevant compiler or source template plus consumers and relevant approved scenario assertions; new coverage requires approval; do not duplicate bundle selection or view conditioning inside a route. Prompt wording changes can affect automated analysis/review as well as rendering.

## Maintained verification

[fast.spec.mjs](../../tests/e2e/fast.spec.mjs) S2 compiles front Assembly/Dressing prompts; S3 exercises Narrative interview/synthesis and assembly packaging using prepared replies. This is not dedicated coverage for all markers, view domains, attachment permutations, structured-scene compilers or model wording quality. The [live check](../../tests/e2e/live.spec.mjs) exercises real Narrative final-assembly synthesis/rendering only when requested. See [Testing](../Testing.md) and [DEVELOPMENT](../DEVELOPMENT.md) for policy and observed results.

## Runtime configuration binding

Library_Paths reads ZET_CONFIG_PATH when the application/fixture supplies an active
configuration, and uses its explicit persistent universe-selection path. This
prevents code-relative config.toml from resolving production data during isolated
worker checks or ignoring config.runtime.toml in a release. Standalone scripts
retain their project-relative default when no active config is supplied.

## Shared visual style and reconstruction (2026-10-14)

`universe_style_service.py` reads the existing `canonical_art_style` and returns text/source/SHA-256; `compose_style` combines separate destination style, content and optional notes. The compiler adapter retains editable universe source-map attribution. Body/Head prompts establish dimensional form and material response, with mannequin-head/fitment simplification scoped explicitly. Assembly/Dressing preserve those details and assign supporting images to their stated design roles. Existing style modes and geometry/view contracts remain unchanged.

`image_reconstruction_service.py` extracts visible content without source rendering conventions and automatically dispatches Qwen txt2img. Codex analysis uses the Codex CLI; Ollama structured analysis is staged through [AI_Proxy](QUEUES.md#publication-and-answer-lifecycle) by `OllamaModelService`. Its frozen source snapshot is analysis-only. The Image Generation page offers a job-specific model, library/upload/paste sources, optional notes and optional text editing. No prompt-review gate precedes rendering. See [ADR 0012](../DECISIONS/0012-universe-style-and-reconstruction.md) and [data model](../DATA_MODEL.md).

### Shared target and true-up

V2 reconstruction shares analysis/composition with the Quick Character Wizard. Source observations remain evidence; effective description/identity applies explicit preserve/change instructions before generation. Observations are not blindly appended into the intended result. Bound hair length using visible face/neck landmarks; unseen completions remain proposals. Universe style is composed separately and frozen for replay.

`ImageTrueUpService` compares candidate, source evidence and approved front when applicable. It distinguishes drift/missed edits from successful intentional edits and hidden details. Selected suggestions and custom feedback compose an edit directly, without a model compatibility gate. Latest operator feedback takes precedence over earlier artistic direction; unaffected details remain as rendered. Original pixels stay out of rendering; corrections use a styled candidate and wizard side views use the selected styled front. Initial Image Generation reconstruction stays automatic after analysis; unresolved source questions retain clarification guidance. See [ADR 0013](../DECISIONS/0013-shared-reconstruction-target-and-true-up.md). Prompt correctness and model reports do not establish rendered fidelity.

The live Freydis front trial exposed costume drift missed by a broad resemblance review. Comparison instruction version 3 explicitly checks garment coverage (midriff, thighs/trousers), knee guards/boot construction and clasp materials. A real re-evaluation found those mismatches while preserving axe removal as intentional. One correction pass repaired some details while leaving hair/midriff drift; further visual acceptance remains necessary.

The live trial exposed false compatibility conflicts, including restoring an exposed midriff. Instruction version 5 removes that model approval step: selected suggestions and operator feedback compose directly, with operator feedback taking precedence. Comparison receives wizard refinement context; Image Generation carries custom feedback into the next target. Automatic comparison can still miss or misjudge features.

Correction renders compose the scoped edit with the frozen universe style, earlier requested changes and view context. They do not prepend the initial analyzed appearance again: generic original wording such as a shoulder-fastened cloak can dilute a later specific correction to cover both shoulders. Earlier edits remain in effect unless operator feedback explicitly changes them. Custom-only edits can proceed without a successful comparison.

The shared workflow is an operator-driven loop: render, compare source and candidate, choose useful findings or supply custom feedback, render a new attempt, then review again. Findings are suggestions and may be incomplete or mistaken; approval does not require an empty report. The operator decides when a result is close enough to select or import. Freydis is a live example, not a set of character-specific rules; individual artistic polish may still require manual work.

Minor Character style reconstruction retains preserve/change intent, model choice and editable description/identity/proposals. Ordered references and primary identity inform analysis; comparison selection remains display-only. Style generation uses detailed target/universe style without enforcing an official view. View alignment bypasses full target composition: exactly one selected style image and a short orientation prompt. All views start independently from selected style. True-ups use only the candidate and frozen selected corrections/custom feedback, preserving unaffected details. Review retains detailed target, accepted direction and an explicitly labeled style anchor. Originals remain analysis/comparison evidence in universe reconstruction. Shared Image Generation behavior is unchanged. See [ADR 0015](../DECISIONS/0015-minor-character-alignment.md).
