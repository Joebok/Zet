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

## Shared contract, failure modes, extension points

[chatgpt_prompt_contract.py](../../zet/services/chatgpt_prompt_contract.py) owns current prompt schema 2, valid render modes (`generate`, `edit`, `composite`), input roles, contract/diagnostic helpers, and reference mappings. Attachment order links prompt citations to exact frozen bytes; preserve it through compile, queue publication, and backend submission. See [INVARIANTS](../INVARIANTS.md).

Common failures: missing required sections/source images, unresolved placeholders, malformed view/mode/variant directives, stale reference descriptions/dependencies, and an attachment order that no longer matches citations. Extend the relevant compiler or source template plus consumers and relevant approved scenario assertions; new coverage requires approval; do not duplicate bundle selection or view conditioning inside a route. Prompt wording changes can affect automated analysis/review as well as rendering.

## Maintained verification

[fast.spec.mjs](../../tests/e2e/fast.spec.mjs) S2 compiles front Assembly/Dressing prompts; S3 exercises Narrative interview/synthesis and assembly packaging using prepared replies. This is not dedicated coverage for all markers, view domains, attachment permutations, structured-scene compilers or model wording quality. The [live check](../../tests/e2e/live.spec.mjs) exercises real Narrative final-assembly synthesis/rendering only when requested. See [Testing](../Testing.md) and [DEVELOPMENT](../DEVELOPMENT.md) for policy and observed results.
