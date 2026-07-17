# Scene Compile v4.0

## Render Script Files

Render-stage code files used to take a story/scene and produce the final render prompt:

- `zet/web/app.py` - web route entry point when the Render button is pressed.
- `zet/app.py` - application facade; delegates `ZetApp.stage_scene_render(...)` to `StoryService`.
- `zet/services/story_service.py` - render orchestration, source loading, validation, reference resolution, artifact writing, and manual render ask staging.
- `zet/services/scene_render_compiler.py` - scene render IR construction, final prompt text generation, local render brief generation, and local render prompt generation.
- `zet/services/path_service.py` - library, story, scene, pipeline, character, costume, and auxiliary resource path resolution.
- `zet/services/config_service.py` - project configuration loading, including library root, AI queue root, and local render backend settings.
- `zet/repositories/asset_repository.py` - locked asset lookup for `{{ASSET:...}}` reference tags.
- `zet/repositories/auxiliary_resource_repository.py` - auxiliary person/place/object lookup for `{{AUX:...}}` references and preservation templates.
- `zet/repositories/identity_key_repository.py` - identity key lookup for `{{IDENTITY:...}}` reference tags.

This list is only for the render/staging path. It does not include Scene Builder UI/editor code.

## Purpose

The scene render compile process turns a story scene into the files needed for a manual ChatGPT image render. The main output is:

```text
Pipelines/Stories/<story_slug>/<scene_slug>/Final_Image_Prompt.md
```

The same render action also writes debug/source artifacts, local render preview prompts, a dependency manifest, and a manual render ask folder under the AI queue.

For current Scene Builder v3 scenes, the canonical render input is the scene `.scene.json` plus its containing story `.story.json`. The markdown scene/story files are not used by the current JSON render path except as legacy fallback when no scene builder JSON exists.

## Entry Point

From the web UI, the Render button calls `zet/web/app.py`, which calls:

```python
zet_app.stage_scene_render(story_slug, scene_slug)
```

`ZetApp.stage_scene_render(...)` in `zet/app.py` delegates directly to:

```python
StoryService.stage_scene_render(story_slug, scene_slug)
```

The service normalizes the slugs, resolves the source files, compiles the prompt, writes pipeline artifacts, clears stale render queue items for the same story scene, and creates a new manual render ask.

## Source Files

For a current JSON-backed scene, `StoryService.stage_scene_render(...)` reads:

- `Stories/<story_slug>/<scene_slug>.scene.json`
- The story settings file named by `scene.story_settings_path`
- Character, costume, auxiliary, and identity-key source templates referenced by scene elements
- Reference image files named by scene reference tags
- `config.toml`, via `ConfigService`, for library paths, queue paths, and local render settings

For the example scene:

```text
C:\Users\Joe\Projects\Zet_Library\Stories\V3-Test-Story\Test-Scene-01.scene.json
C:\Users\Joe\Projects\Zet_Library\Stories\V3-Test-Story\V3-Test-Story.story.json
```

The copied example source files are under:

```text
Docs\SceneCompile\Scene_Compile_v4.0_Example\V3-Test-Story\Test-Scene-01\used
```

## High-Level Flow

1. Normalize `story_slug` and `scene_slug`.
2. Resolve the story scene pipeline folder.
3. Locate the Scene Builder JSON at `Stories/<story_slug>/<scene_slug>.scene.json`.
4. Load the scene JSON.
5. Resolve image reference tags found in the scene JSON.
6. Normalize the scene builder data.
7. Validate normalized scene data.
8. Load the containing story `.story.json`.
9. Resolve per-element identity/costume/location source sections.
10. Build the normalized scene render IR.
11. Generate `Final_Image_Prompt.md` from the IR.
12. Generate local render preview artifacts from the same IR.
13. Write pipeline artifacts.
14. Write dependency/source manifests.
15. Clear stale manual render asks for this story scene.
16. Create a new manual ChatGPT render ask folder containing `ask_manifest.json` and a copy of `Final_Image_Prompt.md`.

## Scene JSON Normalization

Before compiling, `StoryService._normalize_scene_builder_data(...)` makes the scene data predictable for the compiler.

Important normalization behavior:

- Ensures expected top-level collections exist.
- Ensures scene elements have stable defaults such as `reference_images`, `element_visual_override`, and `fallback_visual_description`.
- Converts older `image_tag` values into `reference_images`.
- Moves older `default_visual_description` into `fallback_visual_description`.
- Removes retired placement/body-view/grid fields from normalized placement data.
- Ensures each scene element has one paired placement.
- Rebuilds `depth_lanes` from placements.
- Recomputes generated prompt/brief metadata for the builder document.

There is no backward-compatibility preservation in the compiler output contract; normalized current-shape data is what render compilation uses.

## Validation

`StoryService.validate_scene_builder_data(...)` runs before prompt compilation. It returns warnings and writes them to:

```text
Scene_Render_Validation.json
```

Current render validation is non-blocking unless a required file lookup fails. It checks:

- `schema_version` is `3`.
- `file_kind` is `scene`.
- Scene id, name, story settings path, scene elements, and placements exist.
- The story settings file exists.
- Scene element ids are present and unique.
- `element_type` is one of `Character`, `Monster`, `Prop`, or `Backdrop`.
- Any element without a non-empty image reference tag has a `fallback_visual_description`.
- Placements reference existing scene elements.
- Prop/Backdrop expressions are unusual and produce a warning.
- Gaze targets, interactions, dialogue speakers, and reference assignments point at existing elements.
- Lighting and environment/location are present.

The current implementation writes warnings but still writes render artifacts if there are no hard file-resolution failures.

## Reference Resolution

`StoryService._resolve_scene_references(...)` scans the scene JSON text for image reference tags.

Supported tag forms:

```text
{{AUX:<category>:<resource_id>:<image_id>}}
{{ASSET:<character>:<phase>:<asset_id>...}}
{{IDENTITY:<character>:<phase>:<identity_key_id>}}
```

Resolution behavior:

- `{{AUX:...}}` resolves through `AuxiliaryResourceRepository`.
- `{{ASSET:...}}` resolves through `AssetRepository` and requires the asset to be locked with a final image output.
- `{{IDENTITY:...}}` resolves through `IdentityKeyRepository`.
- Duplicate tags are ignored after first resolution.
- Resolved references are written to `dependency_manifest.json`.
- The same reference list is placed in the manual render `ask_manifest.json`.

The final prompt also gets a `# Reference Image Assignment` section from the IR's `references` collection. Each entry states which element the tag applies to, what to preserve, and what to ignore.

## Element Source Resolution

`StoryService._resolve_scene_element_sources(...)` reads preservation sections from the source material for each element.

For `resource_type: "Character"`:

- Reads `Characters/<character>/<phase>/Character_Image_Template.md`.
- Extracts `IDENTITY_PRESERVATION_SCENE`.
- If a costume is set, reads the costume template.
- Extracts `IDENTITY_PRESERVATION_COSTUME_SCENE`.

For auxiliary `Person`, `Place`, and `Object` resources:

- Uses `AuxiliaryResourceRepository` to find the resource template.
- Extracts `IDENTITY_PRESERVATION_SCENE`.
- For `Person`, also extracts `IDENTITY_PRESERVATION_COSTUME_SCENE`.

The extracted text is added to each scene element as `resolved_source_sections` before IR compilation.

## Render IR

`compile_scene_render_ir(...)` in `zet/services/scene_render_compiler.py` builds a normalized render IR.

The IR contains:

- Source file paths and hashes placeholder.
- Canvas data.
- Story art style and visual continuity rules.
- Environment data.
- Scene elements.
- Placements.
- Props/states.
- Interactions.
- Dialogue.
- Reference assignments.
- Avoid terms.
- Final verification checklist.
- Resolved source metadata.

The IR is written to:

```text
Scene_Render_IR.json
```

This file is the best debugging artifact when the final prompt is missing or misrepresenting data.

## Final Prompt Generation

`final_image_prompt_text(ir)` formats the final ChatGPT render prompt.

The output sections are:

1. `# Render Task`
2. `# Reference Image Assignment`, only when references exist
3. `# Canvas`
4. `# Character and Location Staging`
5. `# Props and Interactions`
6. `# Environment and Depth`, only when environment text exists
7. `# Lighting and Mood`, only when lighting/mood/atmosphere/style exists
8. `# Dialogue Panel`, only when dialogue exists
9. `# Scene Element Preservation`, only when continuity/source/override/fallback text exists
10. `# Avoid`
11. `# Final Verification`

### Staging

For each placement, the compiler looks up the related scene element. It includes placements for:

```text
Character, Monster, Place, Backdrop, Prop, Effect, Vehicle
```

`Character` and `Monster` elements use `stands` language. `Place`, `Backdrop`, and `resource_type: "Place"` use `occupies` language.

Placement output uses:

- `scene_element_id`
- `position_within_cell`
- `depth`
- `pose.summary`
- `pose.gaze_target_element_id`
- `pose.expression`
- `pose.left_arm_action`
- `pose.right_arm_action`
- `placement_notes`

Internal ids are hidden by resolving display names with `get_element_display_name(...)`.

### Interactions

Interactions are deduplicated. Reciprocal gaze relationships such as A looking at B and B looking at A become:

```text
A and B hold direct eye contact.
```

Other interaction relationships become simple one-line sentences.

### Dialogue

Current dialogue output includes:

- Speaker display name.
- Exact dialogue text.
- Optional target instruction when `target_element_id` is present.

Retired dialogue fields such as tone, panel style, local render, and preferred region are not used by the compiler.

### Preservation

The preservation section combines story continuity rules and per-element source sections.

For each element heading, the compiler may write:

- `**Identity:** ...`
- `**Location design:** ...` for `Place`/`Backdrop` resources
- `**Costume - <costume name>:** ...`
- `**Element Override:** ...`
- `**Visual description:** ...`

`element_visual_override` is emitted after identity and costume sections as:

```text
**Element Override:** <element_visual_override>
```

`fallback_visual_description` is emitted as:

```text
**Visual description:** <fallback_visual_description>
```

Fallback visual descriptions are only emitted for elements without a non-empty image reference tag.

### Avoid Terms

Avoid terms are combined from:

- `story_settings.style_defaults.default_avoid`
- `scene_data.avoid.scene_specific`
- `setup.environment.important_exclusions`

Duplicates are removed while preserving order.

## Local Render Outputs

The same IR also feeds local render preview artifacts.

`local_render_brief(ir)` creates `Local_Render_Brief.json` with:

- Purpose: `composition_preview`
- Subject count
- Canvas
- Global prompt
- Region prompts
- Plain txt2img prompt/negative prompt
- Forge Couple Basic prompt line data

`local_render_prompt_text(brief)` creates:

```text
Local_Render_Prompt.md
```

`local_render_forge_couple_prompt_text(brief)` creates:

```text
Local_Render_Forge_Couple_Prompt.md
```

The Forge Couple prompt is only written when `LocalRender.LayoutBackend` is `forge_couple_basic`.

## Pipeline Artifacts

For JSON-backed scenes, the pipeline folder is:

```text
Pipelines/Stories/<story_slug>/<scene_slug>
```

The render stage writes:

- `Final_Image_Prompt.md` - source of truth for manual ChatGPT image rendering.
- `Scene_Render_IR.json` - normalized compiler IR.
- `Scene_Render_Validation.json` - non-blocking warnings/errors.
- `Local_Render_Brief.json` - structured local preview input.
- `Local_Render_Prompt.md` - plain local preview prompt.
- `Local_Render_Forge_Couple_Prompt.md` - Forge Couple Basic local preview prompt, when enabled.
- `Prompt_Source_Map.json` - story settings file, scene JSON file, final prompt path, compiler id, and artifact list.
- `dependency_manifest.json` - story slug, scene slug, and resolved reference image files.

## Manual Render Ask

After writing pipeline artifacts, `stage_scene_render(...)` clears stale queued render work for the same story and scene from:

```text
<base_ai_queue_path>\Ollama_Proxy\Ask
<base_ai_queue_path>\Ollama_Proxy\Answer
<base_ai_queue_path>\Ollama_Proxy\Claimed
<base_ai_queue_path>\Ollama_Proxy\Failed
<base_ai_queue_path>\Ollama_Proxy\Claims
```

Then it creates:

```text
<base_ai_queue_path>\Ollama_Proxy\Ask\Ask_Story_<story_slug>_<scene_slug>_RENDER_<timestamp>
```

The ask folder contains:

- `ask_manifest.json`
- `Final_Image_Prompt.md`

The manifest includes:

- Story and scene slugs.
- Pipeline stage: `RENDER`.
- Worker type: `manual_chatgpt_render`.
- Prompt file: `Final_Image_Prompt.md`.
- Expected output filename: `<scene_slug>.png`.
- Target output file in the story folder.
- Pipeline path.
- Reference files.
- Aspect ratio.

## Legacy Markdown Fallback

If no `.scene.json` exists, `stage_scene_render(...)` falls back to the old markdown path:

- Reads the story markdown file.
- Reads the scene markdown file.
- Validates required bounded sections.
- Resolves references from scene markdown.
- Compiles with the older story/scene prompt template path.
- Writes `Final_Image_Prompt.md`, `Prompt_Source_Map.json`, `dependency_manifest.json`, and the manual render ask.

This is not the current Scene Builder v3 render path.

## V3-Test-Story / Test-Scene-01 Example Copy

The example copy lives at:

```text
Docs\SceneCompile\Scene_Compile_v4.0_Example\V3-Test-Story\Test-Scene-01
```

It was regenerated through:

```python
from zet.app import ZetApp
app = ZetApp.from_config("config.toml")
task = app.stage_scene_render("V3-Test-Story", "Test-Scene-01")
```

Generated pipeline path:

```text
C:\Users\Joe\Projects\Zet_Library\Pipelines\Stories\V3-Test-Story\Test-Scene-01
```

Generated ask path:

```text
C:\Users\Joe\Library\CloudStorage\Dropbox\AI_Queue\Ollama_Proxy\Ask\Ask_Story_V3-Test-Story_Test-Scene-01_RENDER_20260717_082109_599724
```

### Copied Used Files

```text
used\story\Test-Scene-01.scene.json
used\story\V3-Test-Story.story.json
used\templates\Character_Image_Template.md
used\templates\Costume_Canonical_Adventure_Gear.md
used\templates\spire-of-celestial-wisdom_Template.md
used\templates\valindia_Template.md
used\references\arch.png
used\references\Costume-Dressing_Front-Right-3-4_Front-Right-3-4_Canonical-Adventure-Gear.png
used\references\costume.png
```

### Copied Created Files

```text
created\pipeline\dependency_manifest.json
created\pipeline\Final_Image_Prompt.md
created\pipeline\Local_Render_Brief.json
created\pipeline\Local_Render_Forge_Couple_Prompt.md
created\pipeline\Local_Render_Prompt.md
created\pipeline\Prompt_Source_Map.json
created\pipeline\Scene_Render_IR.json
created\pipeline\Scene_Render_Validation.json
created\render_ask\ask_manifest.json
created\render_ask\Final_Image_Prompt.md
```

## Troubleshooting

Use these artifacts in order:

1. `Scene_Render_Validation.json` - check for data warnings.
2. `dependency_manifest.json` - confirm all reference image tags resolved to files.
3. `Prompt_Source_Map.json` - confirm the compiler used the intended scene JSON and story settings file.
4. `Scene_Render_IR.json` - inspect normalized elements, placements, references, resolved source sections, avoid terms, and final verification data.
5. `Final_Image_Prompt.md` - inspect the final human-facing render instructions.
6. `ask_manifest.json` - confirm the render queue target, reference files, aspect ratio, and expected output file.

Common failure points:

- Missing story settings file.
- Missing or stale reference image tag.
- Asset reference points to an asset that is not locked.
- Asset reference has no final image output.
- Auxiliary resource template or image path is missing.
- Scene element has neither an image reference tag nor a fallback visual description.
- Placement references a missing scene element.
- Gaze or interaction target references a missing element.

