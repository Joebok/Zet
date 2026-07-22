# Scenes and Stories Implementation Plan

## Goal

Add story and scene authoring to the dashboard using the external library folder as the source of truth. Stories are filesystem folders under `Zet_Library/Stories`; scenes are markdown files inside a story folder; generated scene images eventually land back in the story folder.

## Phase 1 - Library Path Support

1. Add `PathService.stories_path()`, `story_path(story_slug)`, `story_file_path(story_slug)`, and `scene_template_path()` helpers.
2. Keep all story behavior in backend services, not in `zet/web` route logic.
3. Treat story folders as filesystem records. No story inventory JSON.
4. Preserve legacy path support already added for `_Lib/...`, but use `Stories/...` as the new library-relative convention.

## Phase 2 - Story Service

Create `zet/services/story_service.py`.

Responsibilities:

1. List story folders under `<LibraryPath>/Stories`, excluding folders/files that begin with `_`.
2. Create a story:
   - slugify title with hyphen replacement
   - create `<Stories>/<StorySlug>/`
   - copy `<Stories>/_Story_Template.md` to `<Stories>/<StorySlug>/<StorySlug>.md`
   - replace story title and compiler `STORY_TITLE` placeholders with the entered title
3. Open/create the story file when requested.
4. Save the story file.
5. Validate save:
   - `Title:` is present and not placeholder text
   - `Canonical Art Style:` is present and not placeholder text
   - compiler sections `STORY_TITLE` and `CANONICAL_ART_STYLE` exist

## Phase 3 - Stories Page

Add a `Stories` dashboard tab.

Layout:

1. Left sidebar:
   - `Add New`
   - table/list of story folders
   - row buttons: `Open Story File`, `Edit Scenes`
2. Main panel:
   - story markdown editor
   - `Save Story`
   - validation/message area

Behavior:

1. `Add New` prompts for story title and opens the created story markdown.
2. `Open Story File` loads the story markdown into the editor, creating it from template if missing.
3. `Edit Scenes` switches to the Scenes page and preselects that story.

## Phase 4 - Scene Service

Add scene operations to `StoryService` or a focused `SceneService`.

Responsibilities:

1. List scenes for one story:
   - all `.md` files in the story folder except `<StorySlug>.md`
   - exclude files beginning with `_`
   - sort alphabetically
2. Create a scene:
   - slugify scene name with hyphens
   - copy `<Stories>/_Scene_Template.md` to `<Stories>/<StorySlug>/<SceneSlug>.md`
   - replace scene name and compiler `SCENE_NAME` placeholders
3. Load scene markdown.
4. Save scene markdown.
5. Validate save:
   - `## Render Prompt` exists
   - render prompt contains `{{SECTION:STORY_TITLE}}`
   - render prompt contains `{{SECTION:CANONICAL_ART_STYLE}}`
   - scene name is specified and not placeholder text
   - compiler section `SCENE_NAME` exists

## Phase 5 - Scenes Page

Add a `Scenes` dashboard tab.

Layout:

1. Top/left:
   - Story dropdown populated from story folders
   - `New Scene`
2. Left sidebar:
   - compact scene list by filename/display name
3. Main panel:
   - scene markdown editor
   - `Save Scene`
   - validation/message area
4. Right sidebar:
   - Image Picker

Behavior:

1. If opened from Stories, preselect that story.
2. Otherwise use last selected story from persistent browser storage.
3. First-time fallback is the first story alphabetically.
4. Scene selection persists while filters change.

## Phase 6 - Image Reference Tags

Extend reference tags beyond auxiliary resources.

Proposed tag families:

1. Auxiliary resources:
   - existing `{{AUX:thing:tsaeytte-dagger}}`
2. Locked assets:
   - `{{ASSET:Tsaeytte:Adult:41}}`
3. Locked costume/expression outputs by semantic path:
   - `{{LOCKED:character:phase:pipeline:asset_id}}`
   - or, if preferred for readability, `{{REF:Tsaeytte:Adult:Expression:Amused}}`

Implementation:

1. Add a backend image-reference service that indexes:
   - Aux Resources
   - locked assets across all phases
   - expression assets
   - costume-dressing locked assets
2. Return rows with:
   - tag
   - label
   - character
   - phase
   - category/pipeline
   - image path
   - thumbnail path
3. Add copy-tag buttons where individual images already appear:
   - Assets detail panel
   - Expressions page rows/panel
   - Image Picker

## Phase 7 - Image Picker

Right-side panel on the Scenes page.

Controls:

1. Text filter.
2. Character dropdown.
3. Optional phase dropdown if the result set becomes too noisy.
4. Include Aux Resources in the same result list.

Behavior:

1. Filter searches label, tag, character, phase, pipeline/category.
2. Results show thumbnails.
3. Clicking a result copies its tag to clipboard.
4. Filter state persists while editing scenes.

## Phase 8 - Story Pipeline

Build a Story pipeline without forcing permanent character-style asset rows unless needed.

Recommended approach:

1. Introduce story render tasks separate from `Assets.json`.
2. Store task work under `<LibraryPath>/Pipelines/Stories/<StorySlug>/<SceneSlug>/`.
3. Reuse render-console queue infrastructure:
   - compile prompt
   - resolve referenced images
   - stage manual render ask
   - harvest/save answer
4. At Image Review approval:
   - copy accepted image to `<Stories>/<StorySlug>/<SceneSlug>.png`
   - optionally write `<SceneSlug>.render.json` sidecar with prompt path, references, timestamps, and review status

Why not normal `Assets.json`:

1. Scenes are not character/phase assets.
2. Scene outputs belong in the story folder.
3. Temporary rows in character `Assets.json` would blur ownership and make filtering harder.

## Phase 9 - Compiler

Add a story prompt compiler.

Inputs:

1. Story markdown file.
2. Scene markdown file.
3. Referenced image tags from scene sections and render prompt.

Compiler steps:

1. Load story sections:
   - `STORY_TITLE`
   - `CANONICAL_ART_STYLE`
   - `STORY_PREMISE`
   - `STORY_VISUAL_CONTINUITY`
2. Load scene sections:
   - `SCENE_NAME`
   - `SCENE_DESCRIPTION`
   - `SCENE_IMAGE_REFERENCES`
   - `SCENE_RENDERING_NOTES`
3. Render the scene `## Render Prompt` block by replacing `{{SECTION:...}}`.
4. Resolve image tags into render-console reference files.
5. Write:
   - `Final_Image_Prompt.md`
   - `Prompt_Source_Map.json`
   - `dependency_manifest.json`
   - optional `Prompt_Review.md`
   - optional `Image_Review.md`

## Phase 10 - Library Git Controls

Add a Library Git panel or a compact Stories-page Git strip.

Actions:

1. `Fetch`
2. `Pull`
3. `Status`
4. `Stage Stories`
5. `Commit Stories`

Guardrails:

1. Work only in `Config.base_library_path`.
2. Scope stage operation to `Stories/` unless a later control explicitly supports broader library commits.
3. Show command output in the dashboard.
4. Require a commit message.
5. No branch management for now; assume `main`.

## Questions

1. For story render tasks, do you prefer a separate story-task JSON/sidecar system, or should we reuse temporary asset-like rows outside character `Assets.json`?

* I prefer a separate story-task sidecar system.

2. What tag format do you prefer for locked assets: compact asset id tags like `{{ASSET:Tsaeytte:Adult:41}}`, or semantic tags like `{{REF:Tsaeytte:Adult:Expression:Amused}}`?

* `{{ASSET:Tsaeytte:Adult:41}}`

3. Should scene images always be named exactly `<SceneSlug>.png`, or should accepted versions preserve timestamps/history?

* The Image review should present the existing `<SceneSlug>.png` if it exists already in the Story folder. The "Promote" means replace it with the new one. No need to preserve history. (I have other backups that do that in case of emergency).

4. Should story render prompts require Prompt Review by default, or go directly to Render Console at first?

* Skip prompt review. These prompt are going to be a lot looser than the others. The only thing the compiler has to do is include the requested resources and make sure the art style is there.
