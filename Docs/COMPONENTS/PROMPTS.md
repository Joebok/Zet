# Prompt compilation and reference contracts

## Character and costume source editing (2026-10-26)

[TemplateValidationService](../../zet/services/template_validation_service.py) validates unsaved canonical phase templates. The shared section parser, existing character/costume schema and required-content checks, and concrete eight-view conditioning provide diagnostics and original-line applicability. It rejects malformed reserved controls, controls outside marked sections, invalid resource syntax and unresolved task-template placeholders in emitted prose. Optional legacy character sections remain optional. Validation is deterministic and does not require a batch, prerequisite images or AI services; resource existence and pipeline-specific runtime inputs remain compilation concerns.

[SourceEditorService](../../zet/services/source_editor_service.py) recognizes `Character.md` and `Costume_*.md` only under the selected universe's canonical character phases. Section links open complete files. Analyze/diff are read-only; Save repeats validation and checks the loaded disk digest under existing template change/promotion locks before an atomic replacement, retaining the original newline convention. Diff compares the draft with current disk text, including final-newline changes. Refreshing Diff never updates the save baseline. Master edits leave accepted batch overlays, frozen asks/retries and image publications unchanged. The separate batch-proposal editor retains its own acceptance/promotion workflow.

## Costume render-mode conditioning (2026-10-26)

`Run_Costume_Dressing_Jobs.compile_costume_dressing_job` takes a rendering mode independently of local/traditional pipeline mode. `CostumeRenderModeService` supplies the same ordered references to slots, staging and text previews. Rotate uses `costume_rotation_v1` with an explicit source/target turn instruction; dressing modes retain Assembly as the edit base. Mode settings and image profiles are captured with each prepared request.

Existing view bullets compose with an optional inline annotation, for example:

```markdown
- [bl,br] Preserve the continuous rear hem. <!-- ZET:RENDER_MODES rotate -->
```

Supported values are `doll-dressing-ref`, `doll-dressing-no-ref`, and `rotate`, comma-separated. Untagged prose applies across modes. The costume compiler filters modes before deriving normalized equipment/visibility facts; `ViewContext.render_mode` also supports mode-conditioned source lines. Compilation strips annotations and records mode decisions/source lines under `render_mode_conditioning` in the source map. Malformed/unknown annotations and annotation leakage fail compilation. Mode tags are for reusable source instructions whose applicability differs across modes, not for duplicating compiler-owned reference binding.

`costume_mode_conditioning_service.scoped_replacement` partitions an existing prose line into disjoint view/mode scopes. Unchecked cells retain original wording; checked cells receive the replacement. Source markers, placeholders, resource declarations and canonical metadata are protected. Costume post-render sessions propose source edits rather than replacing compiled image prompts. The complete session diff is approved before private tests and explicit master save. See [Local Characters](LOCAL_CHARACTERS.md#costume-dressing-modes-and-adjustments-2026-10-26) and [ADR 0033](../DECISIONS/0033-costume-post-render-adjustments.md).

Prompt Generator Pilot drafting/packet services are retired; historical adopted-image prompt provenance remains stored.

## Independent Head-Image Edit authoring (2026-10-22)

[Run_Head_Image_Edit_Jobs.py](../../Scripts/Run_Head_Image_Edit_Jobs.py) compiles
[head_image_edit_v2.md](../../Config/Prompt_Templates/head_image_edit_v2.md), with
source-mapped operation wording in [head_image_edit_operations.md](../../Config/Prompt_Templates/head_image_edit_operations.md).
It does not merge legacy Head-Image view/gaze instructions or head/hair sections.

HEAD_EDIT_* sections are optional for existing onboarding; the new compiler
requires authored FRONT_DESCRIPTION, PRESERVE, VIEW_OVERRIDES and REVIEW_CRITERIA.
Reference, expression and opt-in FRONT phase guidance remain optional.
Existing head-domain tags, supplemental-image resolution and schema-2 contracts
apply. Source-backed edits omit FRONT_DESCRIPTION and attach one primary canvas
first, then scoped guides. Same-phase edits retain concise preservation and
matching view notes.
The compiler chooses one FRONT instruction mode: FRONT_DESCRIPTION for generation,
PRESERVE for a same-phase source edit, or the single nonempty PHASE_CHANGES section
for an enabled phase change. The phase-change operation names no specific source
phase. Other views omit phase rules and edit the target batch's selected FRONT.
Governing-template revisions may edit only the new character sections and the two
new task templates, preserving legacy sections and global sources.

`ZET:PROMPT_PACKET` declarations in operation substitutions are analysis metadata.
The static renderer removes them before final marker validation and source-map
line construction, retaining declarations in `prompt_packet_declarations` alongside
those from the task template. Residual ZET marker errors identify the actual
marker text, final-prompt line, and mapped source file/section when available.
This also applies to declarations supplied by selected sections; it does not
relax the character/costume editor's authored-source validation rules.

Dedicated versioned presets use the trial checkpoint and 1024-square output,
empty negative text and disabled prompt globals. Staging disables reference-label
appending. Saved inputs retain ordered private bytes/hashes, recipe/template
revision and render settings. Optional `render_config.overrides` carries frozen
steps, CFG, sampler, scheduler, denoise, text encoder and VAE through Image
Generation submission/retry; absent overrides preserve existing behavior. Prepared
provider requests retain their immutable graph/reference policy. Scheduling and
human acceptance limits belong to [Local Characters](LOCAL_CHARACTERS.md#independent-head-image-edit-2026-10-22).

Prompt generation spans character templates, structured scenes, and independent Narrative prose. This document owns shared compilation and attachment mechanics; scene workflow details live in [SCENE_BUILDER](SCENE_BUILDER.md) and [NARRATIVE](NARRATIVE.md).

## Character compilation path

Inputs are character/costume Markdown, job metadata/views/references, [Prompt_Task_Bundles.json](../../Config/Prompt_Task_Bundles.json), [Prompt_Templates](../../Config/Prompt_Templates/), and supporting section/view configuration.

1. [Compile_Character_Template.py](../../Scripts/Compile_Character_Template.py) `load_template_sections_with_sources` parses section markers with source provenance; `select_sections_for_prompt` resolves template-requested required/optional sections. Unknown/missing/invalid markers are compiler errors, not invitations to fabricate text.
2. [PromptTemplateService](../../zet/services/prompt_template_service.py) conditions sections through [view_conditioning_service.py](../../zet/services/view_conditioning_service.py), filters generation/analysis variants and local/traditional mode blocks, and passes selected text/metadata to the static renderer.
3. [Build_Static_Final_Prompt.py](../../Scripts/Build_Static_Final_Prompt.py) `render_static_prompt_with_source_map` resolves placeholders, metadata tokens and referenced-image citations. [Job_File_Utils.py](../../Scripts/Job_File_Utils.py) and [pipeline_compiler_support.py](../../zet/services/pipeline_compiler_support.py) centralize job/bundle/reference support.
4. `compile_*_job` functions in [Run_Body_Reference_Jobs.py](../../Scripts/Run_Body_Reference_Jobs.py), [Run_Head_Image_Jobs.py](../../Scripts/Run_Head_Image_Jobs.py), [Run_Character_Assembly_Jobs.py](../../Scripts/Run_Character_Assembly_Jobs.py), and [Run_Costume_Dressing_Jobs.py](../../Scripts/Run_Costume_Dressing_Jobs.py) produce artifacts used by active local services. [Run_Expression_Jobs.py](../../Scripts/Run_Expression_Jobs.py) and [Run_Scene_Appearance_Jobs.py](../../Scripts/Run_Scene_Appearance_Jobs.py) compiler files remain present; traditional generation retirement still applies.

Outputs include `Compiled_Sections.md`, final/analysis prompt variants where supported, `Prompt_Source_Map.json`, diagnostics, dependency manifests, and ordered image bindings. Source maps are the first tool for tracing unwanted text; edit canonical sources/templates rather than patching generated output as a lasting fix.

Local character template trials use [TemplateSourceService](../../zet/services/template_source_service.py): context-local source text overrides preserve canonical source paths in source maps without changing masters. The four adapters compile through `compile_with_revision`; final prompt artifacts receive a revision stamp, and source hashes identify the text actually compiled. Static templates, marked sections and metadata-field readers share this overlay. Library/project source IDs rebind across relocation/releases. [Local characters](LOCAL_CHARACTERS.md#prompt-review-staged-generation-and-image-refinement-2026-10-18) owns proposal, trial and promotion behavior.

Custom same-batch reference recipes preserve matching prerequisite inputs and replace only the optional anchor. Compilers label the actual source view and distinguish design continuity from target orientation; individual asks freeze ordered reference bytes. Generated compiler guidance lists visibility sets directly from the parser rather than relying on a missing historical guide. The [character authoring manual](../../Shared_Library/Characters/_Shared/Character_Template_Instructions.md#view-visibility-tags) provides the human-readable group list.

## View-conditioned source language

Use [shared templates/instructions](../../Shared_Library/Characters/_Shared/) and the authoritative parser for exact syntax. `ZET:VIEW_DOMAIN` chooses body or head context; `ZET:VIEW_DEFAULT` supplies visibility defaults; bullet view tags filter prose; `ZET:CANON_ONLY` and `ZET:SPATIAL` carry specialized semantics. Body and head can have independent orientations. `normalize_view` accepts supported aliases, while `resolve_anatomical_side` translates anatomical sides into screen/depth language for the requested view. Fixed spatial features require explicit visibility; unqualified left/right in spatial annotations can fail compilation.

Costume reference prompts are compiled for a known body and head view. Put visibility choices in view-tagged source lines so the emitted prompt states important visible or hidden details directly. The Tsaeytte rear-view repair uses this pattern for the overskirt, jewelry, and near-side earring; the local costume orientation text fixes the rear-quarter face contour and hides the eye.

Generation and analysis templates use `IMAGE_PROMPT_ONLY`/`ANALYSIS_PROMPT_ONLY` blocks; malformed/nested/unclosed variants fail. Consult the mode-filter implementation before changing local/traditional content. [View tagging specification](../../Docs-Joe/ZET_View_Conditioned_Template_Tagging_Spec.md) provides preserved design intent, but parser/tests own supported behavior.

For local Head-Image, place view-specific image instructions such as
`* [bl] Ear Reference Image, use for ear shape: {{LIB:REF:elf-ears-back-left}}`
inside `HEAD_DESCRIPTION_VIEW_OVERRIDES` under `ZET:VIEW_DOMAIN head`.
Source-backed prompts omit `HEAD_DESCRIPTION_FACTS` unless applying phase changes;
view overrides remain visible. Tags are filtered before image resolution, so only
the matching view's resource is appended. Static rendering replaces image tags
inside compiler-composed metadata text as well as ordinary marked sections.
Head compilation resolves resources in
the supplied universe, and both batch rendering and fresh/cached render slots
freeze the compiler's ordered references. Existing submitted inputs remain frozen.
An accepted batch template revision overrides subsequent master edits: make and
accept a manual child revision to bring those edits into an existing batch, then
recompile before generating new renders. Manual child edits may change valid
`LIB:REF` bindings; compiler placeholders and section markers remain protected,
and model-proposed edits retain the stricter reference-preservation rule. Acceptance
still recompiles all eight previews and validates the referenced image files.

Post-render Character.md trials use the same context-local source overlay and
ordered render-input freezer. Selected corrections affect only Character.md;
the compiled eight-view previews and two private renders per affected rendered
view do not change the batch prompt artifacts. Keep writes the accepted source
and active revision, then recompiles currently renderable batch prompts. Assembly
now consults an accepted post-render revision during future compilation while
continuing to skip pre-render prompt acceptance.

### Supplemental template images (2026-10-19)

Template image tags supplement pipeline prerequisites; their presence is not an
unexpected-reference error. Body-Reference validates its optional batch design
anchor separately, then appends images from the view-filtered template. Head and Dressing retain their required source roles. Local Assembly now excludes
supplemental images and tags, as described below. Supplemental resolution
uses the supplied universe; images never substitute for missing required sources.
Compilers and render slots preserve the complete ordered resource manifest for
fresh and cached prompts, including initial Body candidates. Retry still replays
the previously frozen prompt and images.

The shared Body/Head Qwen workflows bind every supplied image in citation order,
including a front Head render supplied only with a template anatomy image. They
validate files and the ten-image backend limit; prerequisite semantics belong to
the pipeline compiler. Reference-count cache metadata describes all bindings.
The historical text/edit profile names do not impose zero/one-image limits.

For anatomy references, put scope and exclusions in a section actually emitted by
the local prompt. Head view overrides survive source-backed compilation; the
local Head prompt does not emit the traditional-only source-rule and character-
requirement placeholders. Specify which anatomy the reference governs and which
reference background, material, framing or display geometry should be ignored.

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

Narrative text synthesis now uses the repo-owned Qwen skill to govern scene/rendering prose,
including length and structure. Generic shortest/concise instructions and forced openings no
longer compete with that guidance. It retains equipment exclusions, anatomy, gesture ownership
and relative-height comparisons. Action belongs in scene; rendering supplies visual treatment
without repeating action. [LLM roles](LLM_ROLES.md) owns skill adapters and routing. This is
model guidance, not a guarantee of live output.
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

Character view staging is a separate input handoff through
[ImageGeneratorStagingService](../../zet/services/image_generator_staging_service.py).
`POST /api/local/{pipeline}/runs/{run_id}/views/{view}/image-generation-stage`
accepts `recompile` and costume context and returns `inputs` plus the reset
`workspace`. Its compiled prompt already describes its ordered image bindings, so
Image Generation preserves those bytes/roles and does not append its usual label
paragraph. Optional `render_config` carries the validated preset/checkpoint and
prompt-global/label-appending policies through submissions and Retry. Character
prompt-document formatting is retained for equivalent shared AI_Proxy compilation;
ordinary ad hoc generation keeps its existing defaults. See
[Local characters](LOCAL_CHARACTERS.md#fixed-render-slots-2026-10-12).

Costume staging accepts `rotation: true` to use the alternate
[costume_rotation_v1](../../Config/Prompt_Templates/costume_rotation_v1.md) template
through `compile_costume_dressing_job(..., rotation=True)`. This mode is local
generation only: it requires a dressed `costume_rotation_source` with prompt role
`edit_base` first, and matching `character_assembly` with prompt role
`layout_reference` second. Existing view conditioning, accepted template sources,
auxiliary image resolution, citations and schema-2 edit validation remain shared.
The ordinary dressing/anchor contract is not appended. Temporary compilation does
not rewrite saved pipeline prompts or recipes. Authored costume construction takes
precedence over source-image mistakes; orientation comes from Assembly and finished
appearance from the dressed source. Generic opening/hem rules apply only to
garments actually specified, without adding a costume-specific master edit.

### Shared target and true-up

V2 reconstruction shares analysis/composition with the Quick Character Wizard. Source observations remain evidence; effective description/identity applies explicit preserve/change instructions before generation. Observations are not blindly appended into the intended result. Bound hair length using visible face/neck landmarks; unseen completions remain proposals. Universe style is composed separately and frozen for replay.

`ImageTrueUpService` compares candidate, source evidence and approved front when applicable. It distinguishes drift/missed edits from successful intentional edits and hidden details. Selected suggestions and custom feedback compose an edit directly, without a model compatibility gate. Latest operator feedback takes precedence over earlier artistic direction; unaffected details remain as rendered. Original pixels stay out of rendering; corrections use a styled candidate and wizard side views use the selected styled front. Initial Image Generation reconstruction stays automatic after analysis; unresolved source questions retain clarification guidance. See [ADR 0013](../DECISIONS/0013-shared-reconstruction-target-and-true-up.md). Prompt correctness and model reports do not establish rendered fidelity.

The live Freydis front trial exposed costume drift missed by a broad resemblance review. Comparison instruction version 3 explicitly checks garment coverage (midriff, thighs/trousers), knee guards/boot construction and clasp materials. A real re-evaluation found those mismatches while preserving axe removal as intentional. One correction pass repaired some details while leaving hair/midriff drift; further visual acceptance remains necessary.

The live trial exposed false compatibility conflicts, including restoring an exposed midriff. Instruction version 5 removes that model approval step: selected suggestions and operator feedback compose directly, with operator feedback taking precedence. Comparison receives wizard refinement context; Image Generation carries custom feedback into the next target. Automatic comparison can still miss or misjudge features.

Correction renders compose the scoped edit with the frozen universe style, earlier requested changes and view context. They do not prepend the initial analyzed appearance again: generic original wording such as a shoulder-fastened cloak can dilute a later specific correction to cover both shoulders. Earlier edits remain in effect unless operator feedback explicitly changes them. Custom-only edits can proceed without a successful comparison.

The shared workflow is an operator-driven loop: render, compare source and candidate, choose useful findings or supply custom feedback, render a new attempt, then review again. Findings are suggestions and may be incomplete or mistaken; approval does not require an empty report. The operator decides when a result is close enough to select or import. Freydis is a live example, not a set of character-specific rules; individual artistic polish may still require manual work.

Minor Character style reconstruction retains preserve/change intent, model choice and editable description/identity/proposals. Ordered references and primary identity inform analysis; comparison selection remains display-only. Style generation uses detailed target/universe style without enforcing an official view. View alignment bypasses full target composition: exactly one selected style image and a short orientation prompt. All views start independently from selected style. True-ups use only the candidate and frozen selected corrections/custom feedback, preserving unaffected details. Review retains detailed target, accepted direction and an explicitly labeled style anchor. Originals remain analysis/comparison evidence in universe reconstruction. Shared Image Generation behavior is unchanged. See [ADR 0015](../DECISIONS/0015-minor-character-alignment.md).


## Character prompt review previews (2026-10-18)

[LocalPromptPreviewService](../../zet/services/local_prompt_preview_service.py) runs the four character compilers for all eight orientations using explicit declared reference roles before generated anchors exist. The context-local `prompt_preview_compiler` boundary marks results and dependency manifests non-renderable; declared references fail normal validation and cannot enter frozen render inputs. Composition, source selection, view conditioning and source maps remain shared with real rendering. Preview source maps retain compact provenance without repeating every fragment's text. Actual generation recompiles the accepted batch sources with real ordered references. Template acceptance and staged/image refinement behavior belong to [Local characters](LOCAL_CHARACTERS.md#prompt-review-staged-generation-and-image-refinement-2026-10-18).

Preview and render inputs share stable selected-view descriptions, including preserve/ignore guidance, without candidate IDs in prompt prose. Body, Head and Dressing declare the same-side predecessor; Body-Reference BACK instead uses selected FRONT, while Head/Dressing BACK use the chosen rear quarter. Assembly declares only matching body/head inputs. Matching Body/Head/Assembly inputs and compiler-added costume resources retain their order. Preview `reference_inputs` come from the compiler result, including those additional resources. Head's uploaded FRONT remains an optional input. The reviewer is told that future inputs and `renderable: false` are intentional.

Preview listings follow the progression service's actual generation stages: FRONT, both front quarters, both profiles, both rear quarters, then BACK. Review guidance includes those same stages and identifies the general supported-view list as orientation order, not execution order. The clockwise view catalog must not be interpreted as a generation schedule. Assembly runs FRONT first, requires a selected FRONT for ranking comparisons, then runs the remaining requested views together; its previews remain a listing of independent matching-view body/head render tasks.

The local Body compiler accepts one explicitly supplied batch design reference, validates it at the normal file boundary, and compiles its image-input contract and dependency manifest before the shared Qwen wrapper is applied. Its task wording says no source image only when no reference is supplied. Traditional Body compilation still rejects image inputs. Saved reviews and frozen asks are not rewritten. New body proposals replace the former literal no-image clause in inherited task-template text with the compiler-controlled input placeholder, preserving other source edits; reanalyze and accept a new version to update an existing batch.

## Simple local Assembly prompt (2026-10-20)

`compile_character_assembly_job` limits local generation and previews to ordered `body_reference`/`head_image` inputs. The required head retains its existing internal `subject_reference` schema role. Additional anchor/subject references and embedded supplemental-image tags are omitted. The task template follows the older natural-join wording: preserve supplied body, head, orientation, gaze and style; blend only the immediate junction. No canonical-style restyling directive is added. Local Assembly no longer compiles through accepted governing-template overlays. Its ranking-only FRONT attachment is owned by the ranking service and is absent from render prompts/manifests. Traditional pipeline retirement remains unchanged.

## Prompt skill boundary (2026-10-22)

Qwen guidance is applied only to appropriate existing LLM authoring, fragment and review calls. Analysis-only reconstruction images do not make a prompt an edit. Existing schemas, source markers, canvas settings, ordered reference bindings and deterministic character/alignment/correction compilation remain authoritative. [LLM roles](LLM_ROLES.md) owns the integration and package update procedure.

Minor Character deterministic render prompts identify ordered multi-image style references with Qwen `<imageN>` tags while retaining their original bytes and order. One-image alignment and true-up prompts refer to the image naturally. Alignment changes viewpoint by visible anatomical side and keeps character design fixed; true-ups identify the input as the canvas and scope edits to selected corrections and operator feedback. The image service does not append its generic reference-label block to these prompts. Candidate payloads freeze the instruction for regeneration and retry.
