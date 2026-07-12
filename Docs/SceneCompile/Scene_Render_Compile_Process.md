# Scene Render Compile Process

This documents what happens when the dashboard Scene `Render` button is pushed, how `Final_Image_Prompt.md` is created, how `Stable_Matrix_API_Call.json` is formed for local preview rendering, and how prompt condense fits between those two steps.

Complete trace example: `Docs/SceneCompile/Example`.

## Render Button Entry Point

The Scene tab button calls:

1. `zet/web/static/zet.js`
   - `stageSceneRender()`
   - POST `/api/stories/{story_slug}/scenes/{scene_slug}/stage-render`
2. `zet/web/app.py`
   - `scene_stage_render()`
   - calls `zet_app.stage_scene_render(story_slug, scene_slug)`
3. `zet/app.py`
   - `ZetApp.stage_scene_render()`
   - delegates to `StoryService.stage_scene_render()`
4. `zet/services/story_service.py`
   - `StoryService.stage_scene_render()`

The Render button stages a manual ChatGPT render task. It does not directly call Stable Matrix. Stable Matrix payload generation happens later when Render Console local preview rendering is requested.

## Final_Image_Prompt.md Creation

Main compiler function:

- `zet/services/story_service.py`
  - `StoryService.stage_scene_render()`
  - `StoryService._render_story_scene_prompt()`
  - `StoryService._story_scene_sections()`
  - `StoryService._story_scene_template_path()`

Template:

- `Config/Prompt_Templates/story_scene_v1.md`

The template contains these tokens:

```text
{{SECTION:STORY_TITLE}}
{{SECTION:CANONICAL_ART_STYLE}}
{{SECTION:STORY_PREMISE}}
{{SECTION:STORY_VISUAL_CONTINUITY}}
{{SECTION:SCENE_DESCRIPTION}}
{{SECTION:SCENE_IMAGE_REFERENCES}}
{{SECTION:SCENE_RENDERING_NOTES}}
```

`_render_story_scene_prompt()` reads the template, replaces each `{{SECTION:...}}` token with section text from `_story_scene_sections()`, strips the rendered result, verifies no unresolved `{{SECTION:` token remains, and writes a final newline.

### Source Documents

For the example scene:

- Story file: `C:/Users/Joe/Projects/Zet_Library/Stories/FirstDay/FirstDay.md`
- Scene file: `C:/Users/Joe/Projects/Zet_Library/Stories/FirstDay/Chapter-04-A-Lending-Hand.md`
- Scene Builder JSON: `C:/Users/Joe/Projects/Zet_Library/Stories/FirstDay/Chapter-04-A-Lending-Hand.json`
- Prompt template: `C:/Users/Joe/Projects/Zet/Config/Prompt_Templates/story_scene_v1.md`

The Scene Builder JSON is not read directly by `stage_scene_render()`. It is included in the example because it is the editable structured source that can be exported into the scene markdown compiler sections.

### Compiler Sections

Story-level sections read from `FirstDay.md`:

- `STORY_TITLE`
- `CANONICAL_ART_STYLE`
- `STORY_PREMISE`
- `STORY_VISUAL_CONTINUITY`

Scene-level sections read from `Chapter-04-A-Lending-Hand.md`:

- `SCENE_NAME`
- `SCENE_DESCRIPTION`
- `SCENE_IMAGE_REFERENCES`
- `SCENE_RENDERING_NOTES`

Only the template-referenced sections are inserted into `Final_Image_Prompt.md`. `SCENE_NAME` is read and recorded in `Prompt_Source_Map.json`, but `story_scene_v1.md` does not currently include `{{SECTION:SCENE_NAME}}`.

### Outputs

`StoryService.stage_scene_render()` writes:

- `C:/Users/Joe/Projects/Zet_Library/Pipelines/Stories/FirstDay/Chapter-04-A-Lending-Hand/Final_Image_Prompt.md`
- `Prompt_Source_Map.json`
- `dependency_manifest.json`

It also clears stale queued scene render tasks, creates a new manual render ask under the AI queue, and writes:

- `ask_manifest.json`
- queued copy of `Final_Image_Prompt.md`

The ask manifest has:

- `worker_type`: `manual_chatgpt_render`
- `task_type`: `render`
- `prompt_file`: `Final_Image_Prompt.md`
- `render_preset`: `chatgpt-manual`
- `pipeline_path`: the scene pipeline folder
- `governing_template_path`: the scene markdown path
- `reference_files`: resolved references from `SCENE_IMAGE_REFERENCES`

## Reference Resolution

`StoryService._resolve_scene_references()` scans scene text for:

- `{{AUX:category:resource-id}}`
- `{{ASSET:character:phase:asset-id...}}`
- `{{IDENTITY:character:phase:identity-key-id}}`

For this example it resolved:

- `{{ASSET:Tsaeytte:Youth:27:Costume | Left-Profile | Woodland outfit}}`
- `{{AUX:person:valindia-vandemere-profile}}`
- `{{AUX:place:the-spire-archway}}`

Resolved paths and labels are stored in both `dependency_manifest.json` and the render ask manifest.

## Prompt Condense

Prompt condense is controlled by `config.toml`:

```toml
[PromptCondense]
Enabled = true
Model = "qwen2.5vl:3b"
PromptFile = "Config/Prompt_Condense_Tasks/Condense_Zet.md"
```

For Render Console scene tasks, the dashboard calls:

- `zet/web/app.py`
  - `render_console_prompt_condense()`
- `zet/app.py`
  - `ZetApp.stage_render_task_prompt_condense_ask()`
- `zet/services/ai_proxy_service.py`
  - `AIProxyService.stage_render_task_prompt_condense_ask_if_enabled()`

The condense ask uses:

- Template: `Config/Prompt_Condense_Tasks/Condense_Zet.md`
- Source prompt: `Final_Image_Prompt.md`
- Output file: `Condensed_Image_Prompt.md`
- Worker type: `ollama_generate`
- Task type: `prompt_condense`

The condense template inserts metadata values and the full source prompt into `{{FINAL_IMAGE_PROMPT}}`. The expected answer format is exactly:

```text
prompt: <single-line positive prompt>
negative: <single-line negative prompt>
```

Render Console local preview expects `Condensed_Image_Prompt.md` for a normal scene task. The Stable Matrix adapter can also parse an uncondensed prompt, but the documented UI path is: final prompt -> condense ask -> condensed prompt -> local preview render.

## Stable_Matrix_API_Call.json Formation

Stable Matrix local preview is formed by:

- `zet/web/app.py`
  - Render Console local test render endpoint
- `zet/app.py`
  - `ZetApp.stage_render_task_local_render_ask()`
- `zet/services/ai_proxy_service.py`
  - `AIProxyService.stage_render_task_local_render_ask()`
  - `AIProxyService.render_task_local_render_api_params()`
- `Scripts/Local_Render_Adapters/local_render.py`
  - `render_image()`
- `Scripts/Local_Render_Adapters/stable_matrix_adapter.py`
  - `render_preview()`

Preset source:

- `Config/Local_Render_Presets.json`
- `config.toml` `[LocalRender]`

`render_preview()`:

1. Loads the selected preset from `Config/Local_Render_Presets.json`.
2. Reads the selected prompt file.
3. Splits prompt text with `split_labeled_prompt()`.
   - If it finds `prompt:` and `negative:` / `negative_prompt:`, those become Stable Matrix positive and negative fields.
   - Otherwise it falls back to `split_positive_negative_prompt()`.
4. Loads optional `LOCAL_IMAGE_GEN_OVERRIDES` from `governing_template_path`, which is the scene markdown file.
5. Sets render size from `orientation`.
   - `landscape` -> `768 x 512`
   - `square` -> `512 x 512`
   - default portrait -> `512 x 768`
6. Builds the Stable Matrix `/sdapi/v1/txt2img` payload from preset values, prompt text, config prompt globals, and overrides.
7. Writes `Stable_Matrix_API_Call.json`.
8. Posts the payload to the configured Stable Matrix server.

Important: `Stable_Matrix_API_Call.json` is written before the HTTP request. If the backend is unavailable, the API-call artifact can still exist even though no local preview image is produced.

For this example, the scene markdown has:

```text
<!-- ZET:BEGIN LOCAL_IMAGE_GEN_OVERRIDES -->
enable_hr: false
orientation: landscape
<!-- ZET:END LOCAL_IMAGE_GEN_OVERRIDES -->
```

So the example Stable Matrix payload uses:

- `width`: `768`
- `height`: `512`
- `enable_hr`: `false`

Prompt globals from `config.toml` are appended if not already present:

- `[LocalRender].PositivePromptGlobals`
- `[LocalRender].NegativePromptGlobals`

## Example Run

Command used to run the same backend function as the Scene Render button:

```powershell
python3 - <<'PY'
from pathlib import Path
from zet.app import ZetApp

app = ZetApp.from_config(Path("config.toml"))
task = app.stage_scene_render("FirstDay", "Chapter-04-A-Lending-Hand")
print(task)
PY
```

Generated task:

- Ask ID: `Ask_Story_FirstDay_Chapter-04-A-Lending-Hand_RENDER_20260711_154344_447788`
- Pipeline path: `C:/Users/Joe/Projects/Zet_Library/Pipelines/Stories/FirstDay/Chapter-04-A-Lending-Hand`
- Final prompt: `Final_Image_Prompt.md`
- Expected output: `Chapter-04-A-Lending-Hand.png`

Then `render_preview()` was run against the generated prompt to create `Stable_Matrix_API_Call.json`. Stable Matrix was unavailable at `http://127.0.0.1:7860`, so no preview image was generated, but the API-call JSON was written.

## Example Folder Contents

`Docs/SceneCompile/Example` contains:

- `Final_Image_Prompt.md`
- `Stable_Matrix_API_Call.json`
- `Prompt_Source_Map.json`
- `dependency_manifest.json`
- `render_ask_manifest.json`
- `render_ask_Final_Image_Prompt.md`
- `FirstDay.md`
- `Chapter-04-A-Lending-Hand.md`
- `Chapter-04-A-Lending-Hand.json`
- `story_scene_v1.md`
- `Condense_Zet.md`
- `Local_Render_Presets.json`
- `config.toml`

Use `Prompt_Source_Map.json` to identify the high-level source files and compiler section names, then compare `story_scene_v1.md`, `FirstDay.md`, and `Chapter-04-A-Lending-Hand.md` against `Final_Image_Prompt.md` to trace inserted text.
