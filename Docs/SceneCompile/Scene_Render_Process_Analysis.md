# Scene Render Process Analysis and Recommended Revision

## Scope

This analysis is based on the documented compile trace and example artifacts in `SceneCompile.zip`, plus the supplied Youth Tsaeytte character and woodland costume templates. The primary goal is a stronger `Final_Image_Prompt.md` for a ChatGPT image render with attached reference images. The secondary goal is a cleaner Stable Diffusion WebUI Forge / SD 1.5 local-preview path.

## Executive conclusion

The Scene Builder JSON should become the canonical source for spatial staging, camera, environment, character placement, pose, gaze, interaction, dialogue, and reference assignment. It should be compiled deterministically into an intermediate scene representation, then rendered into two different prompt products:

1. `Final_Image_Prompt.md`: structured natural-language instructions optimized for ChatGPT with attached reference images.
2. `Local_Render_Prompt.md` or `Local_Render_Prompt.json`: compact visual facts optimized for SD 1.5, normally omitting dialogue text and story prose.

Do not use an LLM to rediscover the scene layout from a prose scene file. The LLM may polish or condense an already structured prompt, but it should not control character count, left/right placement, body facing, hand actions, gaze, interactions, or required props.

## What the current pipeline does well

- Story-level and scene-level source boundaries are explicit.
- Reference tags resolve to concrete files and are carried into manifests.
- Prompt creation is reproducible and leaves useful artifacts.
- Local render parameters are captured before the HTTP call.
- The Scene Builder already captures a useful base vocabulary: canvas, grid, camera, environment, scene elements, placements, depth, gaze, and importance.

## Main problems in the current example

### 1. The strongest source is ignored

`Chapter-04-A-Lending-Hand.json` contains structured staging information, but `stage_scene_render()` compiles only bounded sections from the story and scene markdown files. The user must manually restate the Builder data in `SCENE_DESCRIPTION`, creating two sources of truth.

The example proves the sources have already diverged:

- Scene Builder: landscape, 16:9, wide shot.
- Scene markdown: portrait, 4:5.
- Local override: landscape.
- API payload: 768 × 512, which is 3:2 rather than 16:9.

### 2. The final prompt is organized as source-document concatenation rather than render instructions

The current prompt gives ChatGPT a story title, long dialogue styling rules, full premise, continuity notes, scene prose, raw reference tags, and partially empty rendering notes. It does not present the scene in the order an image model needs:

1. output format and canvas;
2. camera;
3. spatial composition;
4. each character's identity and exact staging;
5. interactions and props;
6. environment and lighting;
7. reference-image roles;
8. prohibitions and final checks.

### 3. Reference files are resolved but not semantically assigned in the prompt

The render manifest knows each file's label and path, but `Final_Image_Prompt.md` only contains raw tags. The prompt should explicitly say what each attached image controls and what it does not control, for example:

- Tsaeytte reference: identity, hair, ears, and woodland outfit only; ignore source pose and background.
- Valindia reference: identity, hair, outfit, and proportions only; ignore source pose and background.
- Archway reference: architecture and location design only; adapt perspective and lighting to this scene.

This is one of the highest-value prompt improvements for ChatGPT rendering.

### 4. Important facts conflict

The example has conflicts that should create validation errors or warnings:

- Valindia is `amused` in the Builder but `empathetic` in scene prose.
- Builder mood is `tense`; prose suggests a sympathetic gesture.
- Tsaeytte is described as 16–17 with a “long bob” in the Builder, while the supplied canonical Youth template says 17–18 with a short jaw/nape-length rumpled bob.
- The prompt requests a dialogue panel, then ends with “Do not stamp text, captions...”
- Several names and dialogue words are misspelled: `Valinia`, `Valinida`, and `Disciplene`.
- The Builder has placeholder values such as `(arch visual description)` and `(v head facing)` but reports no validation warnings.
- Tsaeytte's `image_tag` is empty in the Builder even though the scene markdown contains a Tsaeytte costume reference.
- The interaction list is empty although the central action is a book handoff.

### 5. The Builder's generated outputs are too shallow and can become stale

`generation_outputs.scene_brief`, `positive_prompt`, and `negative_prompt` are stored inside the editable scene file. They omit many scene facts and can drift whenever raw Builder fields change. Generated prompt products should be compiler outputs with source hashes, not canonical editable inputs.

### 6. The local payload shows a parser failure

The scene markdown contains:

```text
negative_prompt:denoising_strength:
```

The API payload consequently begins its negative prompt with `denoising_strength:`. Empty colon-delimited override fields should not be parsed as prompt text. Store local overrides as strict JSON, TOML, or YAML, validate their types, and omit empty keys.

### 7. The local path is not using references

The generated API request is plain `/sdapi/v1/txt2img`. The resolved reference files never reach the image generator. Better text descriptions can improve approximate appearance, but exact character identity and multi-character consistency cannot be expected from the current local request alone.

## Recommended source ownership

### Story markdown owns

- story title;
- canonical art style;
- short story visual continuity rules;
- optional dialogue-panel style;
- brief narrative context.

Move dialogue style out of `CANONICAL_ART_STYLE` into its own section and include it only when the scene has dialogue.

### Scene Builder JSON owns

- canvas orientation and aspect ratio;
- camera and framing;
- environment, lighting, atmosphere, and exclusions;
- all scene elements;
- all placements and depth ordering;
- body facing, head facing, gaze, expression, and pose;
- hand-specific actions;
- props and their locations;
- interactions and contact/distance rules;
- dialogue content and speaker;
- image reference assignment;
- scene-specific avoid rules;
- local-render settings that are genuinely scene-specific.

### Scene markdown owns

Keep it as a human-readable narrative companion and optional override source, not a duplicate layout source. Useful sections would be:

- `SCENE_NARRATIVE_INTENT`;
- `SCENE_STORY_CONTEXT`;
- `SCENE_SPECIAL_RENDER_INSTRUCTIONS`;
- freeform author notes.

The markdown can be generated from the JSON for readability, or the two files can coexist with clearly non-overlapping responsibilities.

### Character template owns

- identity anchors;
- face, hair, ears, species, age phase, and body proportions;
- short narrative personality/presence cues.

For a narrative scene, extract only compact identity sections. Do not import technical fitment, neutral stance, bare-foot, or turnaround rules.

### Costume template owns

- current swappable costume;
- materials, colors, silhouette, footwear, equipment, and costume drift rules.

The separate costume template should override duplicated costume text inside the character template. This avoids conflicts such as bare feet in technical metadata versus boots in the selected narrative costume.

## Recommended precedence rules

From highest to lowest priority:

1. explicit scene-specific override;
2. structured placement, interaction, dialogue, and prop fields in scene JSON;
3. selected costume template;
4. canonical character identity template;
5. scene element fallback description;
6. story continuity defaults;
7. generic rendering defaults.

Identity anchors should be protected. A scene may override expression, pose, view, hand action, and temporary condition, but should not silently override age phase, species, face, eye color, canonical hair, or selected costume.

## Add a normalized Prompt Scene IR

Compile all inputs into a backend-neutral object before producing any prompt. Suggested structure:

```json
{
  "canvas": {
    "orientation": "landscape",
    "aspect_ratio": "16:9",
    "shot_type": "wide shot",
    "camera_height": "eye-level",
    "camera_angle": "straight-on",
    "lens_feel": "normal"
  },
  "composition": {
    "planning_grid": {"rows": 1, "columns": 3},
    "focal_point": "the exchange between Valindia and Tsaeytte",
    "left_to_right_order": ["Valindia", "open book", "Tsaeytte"],
    "draw_grid": false
  },
  "characters": [],
  "props": [],
  "interactions": [],
  "environment": {},
  "lighting": {},
  "dialogue": [],
  "references": [],
  "avoid": [],
  "source_lineage": []
}
```

This IR should be written as `Scene_Render_IR.json` for debugging.

## Scene Builder fields to add or strengthen

### Placement and framing

- semantic screen region: left third, center, right third, upper/lower area;
- optional normalized anchor coordinates;
- frame coverage: full body, knees-up, waist-up, etc.;
- distance from camera;
- visible feet requirement;
- relative height or scale separate from narrative importance;
- overlap order and “must not occlude” constraints.

`size_prominence` currently mixes visual importance, camera distance, and body scale. Split those concepts so the compiler does not accidentally make one character anatomically larger.

### Orientation

Use explicit enums rather than “toward left”:

- body view relative to camera: front, front-left 3/4, left profile, back-left 3/4, back, etc.;
- head view relative to camera;
- screen direction of action;
- gaze target.

Keep “screen left/right” distinct from “anatomical left/right.”

### Pose and hands

Keep a concise pose summary, but add:

- left arm action;
- right arm action;
- left hand item/contact;
- right hand item/contact;
- leg and foot details when important;
- balance/weight distribution;
- temporary body condition such as kneeling, falling, or reaching.

The current scene relies on exact left/right book handling, so this should not live only in prose.

### Props

Props should be scene elements with placements and states:

- owner/holder;
- hand used;
- open/closed;
- orientation;
- ground/contact state;
- interaction target;
- count;
- whether the prop must remain visible.

For this scene, five books should be represented explicitly: two held by Tsaeytte, one she reaches toward, one open and upside down on the path, and one offered by Valindia.

### Interactions

Make the book offer a first-class interaction:

```json
{
  "source": "Valindia",
  "action": "offers",
  "prop": "offered_book",
  "target": "Tsaeytte",
  "source_hand": "left",
  "contact": "no contact",
  "distance": "just outside Tsaeytte's reach"
}
```

Also represent mutual gaze as a relationship rather than duplicating text on both placements.

### Dialogue

Store dialogue separately from visual staging:

- speaker;
- exact text;
- panel style ID;
- pointer target;
- preferred screen region;
- allowed line count;
- whether dialogue is included in final ChatGPT render;
- whether dialogue is excluded from local preview.

### Reference assignment

Each element should select one or more references with a role:

```json
{
  "tag": "{{ASSET:...}}",
  "applies_to": "Tsaeytte",
  "roles": ["identity", "hair", "costume"],
  "ignore": ["source pose", "source background", "source framing"]
}
```

## Recommended `Final_Image_Prompt.md` structure

1. **Render task** — one finished image, intended orientation and aspect ratio.
2. **Reference-image assignment** — identify each attached reference and its exact role.
3. **Camera and composition** — shot, height, lens feel, focal point, and spatial order.
4. **Character staging** — one subsection per character with identity, placement, pose, body/head view, gaze, expression, hands, and visible costume.
5. **Props and interactions** — counts, positions, states, ownership, and distances.
6. **Environment and depth** — foreground, midground, background, architecture.
7. **Lighting, mood, and storytelling beat**.
8. **Dialogue panel** — only if present.
9. **Must preserve** — protected identity/costume/location facts.
10. **Avoid** — scene-specific failure modes.
11. **Final verification** — concise checklist for character count, placement, gaze, props, text, and cropping.

Do not lead with the full story premise. Include at most one short “story beat” sentence after the visual facts.

## Example improved ChatGPT prompt

The example below treats the Scene Builder's landscape 16:9 setting as canonical and resolves the Valindia expression toward the scene prose. A production compiler should stop or warn instead of silently choosing when sources conflict.

See the accompanying `Final_Image_Prompt_v2_Example.md`.

## Local render recommendation

### Immediate path: compile directly from the Scene IR

Generate a dedicated local prompt directly from structured facts. Do not condense the entire ChatGPT prompt.

The local prompt should include:

- subject count and broad identity;
- landscape/portrait and shot type;
- left/center/right staging;
- coarse poses and mutual gaze;
- key props and environment;
- lighting and art style;
- scene-specific negative terms.

It should normally omit:

- story title and premise;
- long continuity prose;
- reference tags;
- dialogue text and speech-panel instructions;
- implementation notes;
- instructions intended only for ChatGPT.

For composition previews, put `text, letters, speech bubble, caption` in the negative prompt and add dialogue later in ChatGPT or post-processing.

### Optional local LLM

A local LLM can still help, but give it `Local_Render_Brief.json`, not `Final_Image_Prompt.md`. The brief should already separate positive and negative facts and mark protected tokens:

- exact subject count;
- character names;
- left/right placement;
- poses;
- gaze;
- required props;
- camera and aspect ratio.

Validate the LLM output to ensure every protected fact survives. If validation fails, use the deterministic prompt.

### Create a scene-specific preset

Do not use `body-reference-preview` for narrative scenes. Add a `scene-preview-sd15` preset with scene-appropriate dimensions and globals. Resolve width/height from the exact Builder aspect ratio, not only from orientation.

### Longer-term local improvement

The Builder can generate a simple layout/pose guide image from its grid, placements, and pose data. That guide can later drive img2img or a control mechanism. Character reference images can later be supplied through an identity/reference-conditioning path. These are more likely to improve multi-character staging and identity than further prose expansion alone.

## Validation requirements

Before writing either prompt, validate:

- no placeholder values such as `(notes)` remain in required fields;
- one canonical orientation/aspect ratio;
- output dimensions match that ratio within tolerance;
- each primary character has a placement and reference or canonical identity source;
- all gaze and interaction targets exist;
- every held prop has one holder and one hand;
- prop counts are internally consistent;
- body/head facing values are explicit;
- required dialogue is not contradicted by global no-text rules;
- dialogue spelling is acknowledged or corrected;
- scene-specific expression/mood conflicts are surfaced;
- swappable costume overrides character-template costume defaults;
- no technical body-reference rules leak into narrative prompts;
- local override syntax is valid and empty values are omitted.

Write `Scene_Render_Validation.json` with errors, warnings, and auto-resolutions.

## Revised output set

Recommended artifacts per scene pipeline:

- `Scene_Render_IR.json` — normalized, backend-neutral facts.
- `Scene_Render_Validation.json` — conflicts and resolutions.
- `Final_Image_Prompt.md` — ChatGPT-specific prompt.
- `Local_Render_Brief.json` — SD-relevant facts only.
- `Local_Render_Prompt.md` — deterministic or validated LLM output.
- `Stable_Matrix_API_Call.json` — final API payload.
- `Prompt_Source_Map.json` — field-level source lineage using JSON pointers and section names.

## Implementation order

### Priority 0 — correctness fixes

1. Parse local overrides as a strict typed format.
2. Remove empty override values.
3. Fix dialogue/no-text contradiction.
4. Add conflict and placeholder validation.
5. Make canvas aspect ratio determine API dimensions.
6. Add a narrative-scene local preset.

### Priority 1 — better `Final_Image_Prompt.md`

1. Read the Scene Builder JSON directly in `stage_scene_render()`.
2. Build `Scene_Render_IR.json`.
3. Resolve character and costume source sections.
4. Resolve and label reference roles.
5. Render the new structured ChatGPT prompt.
6. Expand `Prompt_Source_Map.json` to field-level lineage.

### Priority 2 — better local preview

1. Produce `Local_Render_Brief.json` from the IR.
2. Add deterministic SD 1.5 positive/negative formatters.
3. Make local LLM condensation optional.
4. Validate protected facts after LLM condensation.
5. Exclude dialogue from local preview by default.

### Priority 3 — structural conditioning

1. Generate a layout/pose guide from Scene Builder placements.
2. Add a control/img2img path.
3. Add explicit character reference conditioning when the local stack supports it.

## Core design rule

Use structured data to determine facts. Use templates to determine identity and costume. Use an LLM only to improve wording. Never require an LLM to reconstruct the scene's geometry from prose that the application already knows.
