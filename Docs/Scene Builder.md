Implement a “Scene Builder” feature for Zet.

# Goal

Create a proof-of-concept Scene Builder that helps the user define structured scene-layout instructions for image prompts.

The Scene Builder should help specify:

* canvas orientation and aspect ratio
* composition template
* grid layout
* characters in the scene
* where characters appear on screen
* foreground / midground / background depth
* pose, facing direction, gaze target, expression, and interaction details
* background anchors and props
* camera framing
* lighting and mood
* validation warnings
* generated scene brief
* generated image prompt
* generated negative prompt
* saved JSON scene-builder data

The feature should store its structured data in a `.json` file with the same base filename as the associated scene `.md` and `.png` files.

Example associated files:

```text
Scenes/First_Day_at_the_Spire.md
Scenes/First_Day_at_the_Spire.png
Scenes/First_Day_at_the_Spire.json
```

The `.md` file is the human-readable scene prompt/instructions file.

The `.png` file is the rendered/generated image for that scene, when available.

The `.json` file is the structured Scene Builder data used to generate or revise the `.md` prompt.

# Scope

Implement a useful v1 proof of concept. Do not build a full visual map editor or 3D plan view yet.

The v1 feature should include:

* Scene Setup panel
* Character palette/list
* Clickable or selectable composition grid
* Placement editor for selected characters/items
* Depth lane editor
* Environment/background anchor editor
* Camera editor
* Interaction editor
* Prompt generation output
* Validation warnings
* JSON save/load
* Markdown scene prompt export

The UI may be basic but should be functional, clear, and fast to use.

# Implementation Assumptions

Follow existing Zet project conventions.

Before making changes:

1. Inspect the repository structure.
2. Identify the current UI framework and state-management pattern.
3. Identify existing file/path conventions for scenes, generated images, prompts, and project data.
4. Reuse existing components where practical.
5. Use diff-based edits. Do not rewrite unrelated files.
6. Keep implementation modular.

If there is already a scene/image/project data model, integrate with it rather than creating a disconnected system.

If there is no existing scene abstraction, create the smallest practical abstraction needed for this feature.

# Data Storage Rule

For every associated scene markdown file, the Scene Builder JSON file must use the same base filename.

Examples:

```text
My_Scene.md       -> My_Scene.json
My_Scene.png      -> My_Scene.json
Chapter_01_03.md -> Chapter_01_03.json
Chapter_01_03.png -> Chapter_01_03.json
```

The `.json` file should live in the same directory as the `.md` and `.png` unless the project already has a strong convention that requires otherwise.

The code should provide a helper function similar to:

```python
def get_scene_builder_json_path(scene_md_or_png_path: Path) -> Path:
    return scene_md_or_png_path.with_suffix(".json")
```

If implemented in another language, provide equivalent behavior.

The app should be able to:

* create a new `.json` file for a scene
* load an existing `.json` file for a scene
* update the `.json` file when the scene builder data changes
* export/update the associated `.md` prompt file from the structured data
* reference the associated `.png` file if it exists

Do not store binary image data inside the `.json`.

Store only file paths or relative references.

# JSON Data Model

Use this general structure:

```json
{
  "schema_version": 1,
  "scene": {
    "name": "",
    "slug": "",
    "associated_md_path": "",
    "associated_png_path": "",
    "notes": ""
  },
  "canvas": {
    "orientation": "landscape",
    "aspect_ratio": "16:9",
    "width": null,
    "height": null
  },
  "composition": {
    "template": "custom",
    "grid": {
      "columns": 3,
      "rows": 2
    },
    "primary_focal_point": "",
    "composition_notes": ""
  },
  "camera": {
    "shot_type": "wide shot",
    "camera_height": "eye-level",
    "camera_angle": "straight-on",
    "viewer_position": "front",
    "lens_feel": "normal",
    "focus_priority": "whole group",
    "notes": ""
  },
  "characters": [
    {
      "id": "Tsaeytte",
      "display_name": "Tsaeytte",
      "asset_tag": "{{ASSET:Tsaeytte:Adult:31}}",
      "role": "protagonist",
      "importance": "primary",
      "identity_prompt": "",
      "default_costume": "",
      "notes": ""
    }
  ],
  "placements": [
    {
      "id": "placement_001",
      "type": "character",
      "character_id": "Tsaeytte",
      "label": "Tsaeytte",
      "screen_cell": {
        "row": 2,
        "column": 1,
        "name": "lower-left"
      },
      "position_within_cell": "center",
      "depth": "foreground",
      "size_prominence": "large",
      "pose": "crouched with one hand braced on the floor",
      "body_facing": "center-right",
      "head_facing": "same as body",
      "gaze_target": "Teacher",
      "expression": "alert and wary",
      "interaction_target": "Teacher",
      "occlusion": "none",
      "notes": ""
    }
  ],
  "environment": {
    "location": "",
    "foreground_props": [],
    "background_anchors": [
      {
        "id": "anchor_001",
        "label": "glowing arched doorway",
        "screen_cell": {
          "row": 1,
          "column": 3,
          "name": "upper-right"
        },
        "depth": "background",
        "description": "glowing arched doorway casting cool blue light"
      }
    ],
    "lighting": "",
    "mood": "",
    "weather_or_atmosphere": "",
    "important_exclusions": []
  },
  "depth_lanes": {
    "foreground": [],
    "midground": [],
    "background": []
  },
  "interactions": [
    {
      "subject": "Tsaeytte",
      "relationship": "looking at",
      "target": "Teacher",
      "note": "alert and wary"
    }
  ],
  "generation_outputs": {
    "scene_brief": "",
    "positive_prompt": "",
    "negative_prompt": "",
    "validation_warnings": []
  },
  "metadata": {
    "created_at": "",
    "updated_at": "",
    "created_by": "Zet Scene Builder"
  }
}
```

Adjust field names only if needed to match project conventions, but preserve the same conceptual separation:

* `scene`
* `canvas`
* `composition`
* `camera`
* `characters`
* `placements`
* `environment`
* `depth_lanes`
* `interactions`
* `generation_outputs`
* `metadata`

Important: keep character definitions separate from placements.

A character definition describes who the character is.

A placement describes where that character is in this specific scene and what they are doing.

# UI Structure

Build the UI as a single-page Scene Builder, preferably with three working areas:

```text
┌───────────────────────┬───────────────────────────────┬──────────────────────┐
│ Scene Builder Sections │ Live Scene Layout Preview      │ Selected Item Editor │
│                        │                               │                      │
│ 1. Setup               │  grid preview                  │ selected placement   │
│ 2. Characters          │  labels                        │ pose/facing/gaze     │
│ 3. Placement           │  arrows if easy                │ depth/cell fields    │
│ 4. Camera              │  depth indicators              │                      │
│ 5. Environment         │                               │                      │
│ 6. Interactions        │                               │                      │
│ 7. Generate            │                               │                      │
└───────────────────────┴───────────────────────────────┴──────────────────────┘
```

If the existing UI framework makes this exact layout awkward, implement an equivalent form-driven structure.

The goal is speed and clarity, not visual polish.

# Scene Setup Panel

Provide fields for:

* scene name
* associated `.md` file path
* associated `.png` file path, optional
* canvas orientation
* aspect ratio
* composition template
* grid rows
* grid columns
* primary focal point
* notes

Suggested orientation options:

```text
portrait
landscape
square
comic panel
custom
```

Suggested aspect ratio options:

```text
1:1
4:5
3:4
16:9
2:3
custom
```

Suggested composition templates:

```text
custom
single subject
two character conversation
group lineup
confrontation
foreground subject with background threat
teacher addressing students
over-the-shoulder
action scene
establishing shot
comic dialogue panel
```

When the user chooses a template, optionally pre-fill sensible camera/composition defaults.

Do not overwrite user-entered data without confirmation or an explicit “Apply Template” action.

# Character Panel

Provide a character list/palette.

Each character should support:

* id
* display name
* asset tag
* role
* importance
* identity prompt
* default costume
* notes

Importance options:

```text
primary
secondary
background
extra
```

The UI should allow:

* add character
* edit character
* remove character
* place character into selected grid cell
* duplicate character placement if needed

Support group actors such as:

```text
background students
guards
crowd
monsters
shadowy figures
```

These should be valid characters/items, but the generated prompt should treat them as less identity-sensitive than named primary characters.

# Layout Preview / Grid

Show a simple rectangle divided by the selected rows and columns.

Each cell should show:

* cell name if practical
* placed character labels
* placed environment anchors/props
* depth indicator if practical

For a 3x2 grid, use names like:

```text
upper-left
upper-center
upper-right
lower-left
lower-center
lower-right
```

For other grid sizes, generate practical names or use row/column notation.

The grid should allow:

* selecting a cell
* adding a selected character to a cell
* adding an environment anchor to a cell
* selecting an existing placement
* editing a placement
* removing a placement

Do not require drag-and-drop for v1. Click/select controls are acceptable.

# Placement Editor

When a placement is selected, show editable fields:

* placement type: character / prop / background_anchor
* character id, if type is character
* label
* row
* column
* generated cell name
* position within cell
* depth
* size/prominence
* pose
* body facing
* head facing
* gaze target
* expression
* interaction target
* occlusion
* notes

Suggested position-within-cell options:

```text
center
left
right
upper
lower
upper-left
upper-right
lower-left
lower-right
```

Suggested depth options:

```text
foreground
midground
background
distant background
```

Suggested size/prominence options:

```text
dominant
large
medium
small
distant
```

Suggested facing options:

```text
toward viewer
toward left
toward right
toward center
away from viewer
toward another character
custom
```

Suggested gaze options:

```text
same as body direction
looking at viewer
looking at another character
looking at object
looking offscreen
custom
```

Suggested expressions can be a simple text field plus optional quick choices:

```text
neutral
curious
alert
wary
amused
confident
focused
angry
frustrated
vulnerable
determined
custom
```

Pose should be free text, with optional snippets if easy to implement.

Example pose snippets:

```text
standing casually
arms crossed
one hand raised in warning
crouched with one hand braced on the floor
kneeling beside an injured ally
turning back over shoulder
holding staff defensively
mid-leap
reaching toward a glowing object
speaking with one hand gesturing
```

# Depth Lane Editor

Provide a simple foreground / midground / background editor.

The editor should show which placements are assigned to each depth lane.

Example:

```text
Foreground:
- Tsaeytte
- broken staff
- glowing runes

Midground:
- Kaeldor
- open hall floor

Background:
- Teacher
- glowing arched doorway
- blurred students
```

Changing a placement’s depth should update the depth lane.

The user should also be able to add non-grid depth notes if helpful.

# Environment Panel

Provide fields for:

* location
* foreground props
* background anchors
* lighting
* mood
* weather/atmosphere
* important exclusions

Background anchors and foreground props should be placeable on the grid when practical.

Example background anchor:

```json
{
  "id": "anchor_001",
  "label": "glowing arched doorway",
  "screen_cell": {
    "row": 1,
    "column": 3,
    "name": "upper-right"
  },
  "depth": "background",
  "description": "glowing arched doorway casting cool blue light"
}
```

# Camera Panel

Provide fields for:

* shot type
* camera height
* camera angle
* viewer position
* lens feel
* focus priority
* camera notes

Suggested shot type options:

```text
close-up
medium shot
full-body shot
wide shot
establishing shot
comic panel shot
```

Suggested camera height options:

```text
low
eye-level
high
overhead
```

Suggested camera angle options:

```text
straight-on
slight upward angle
slight downward angle
dramatic diagonal
over-the-shoulder
custom
```

Suggested viewer position options:

```text
front
front-left
front-right
side
behind character
custom
```

Suggested lens feel options:

```text
normal
wide
compressed / telephoto
```

Suggested focus priority options:

```text
one primary character
two main characters
whole group
environment
specific object
```

# Interaction Editor

Add a simple interaction list.

Each interaction should have:

* subject
* relationship
* target
* note

Relationship options:

```text
looking at
speaking to
reaching toward
attacking
protecting
standing beside
reacting to
illuminated by
blocking
following
chasing
pointing at
holding
custom
```

Example:

```json
{
  "subject": "Tsaeytte",
  "relationship": "looking at",
  "target": "Teacher",
  "note": "alert and wary"
}
```

These interactions should be included in the generated scene brief and prompt.

# Generation Outputs

The Generate section should produce:

1. Scene Brief
2. Positive Image Prompt
3. Negative Prompt
4. Validation Warnings
5. JSON Preview

The user should be able to copy these outputs.

The app should also support saving the generated scene brief / prompt into the associated `.md` file.

# Scene Brief Generation

The scene brief should be human-readable and concise.

It should integrate the structured data into clear composition language.

Example:

```text
Landscape wide shot of a magic academy hall using a 3-column by 2-row composition. In the lower-left foreground, Tsaeytte crouches with one hand braced on the stone floor, body angled toward the center-right, looking up alertly at the teacher. In the lower-center midground, Kaeldor stands casually with one hand near his amulet, watching the glowing doorway. In the upper-center background, the teacher stands elevated on a stair landing. A glowing arched doorway fills the upper-right background, casting cool blue magical light across the hall. Warm lantern light mixes with the cool magical glow, creating a tense theatrical mood.
```

# Positive Prompt Generation

The positive prompt should be suitable for image generation.

It should include:

* art style, if the project has a canonical art style setting
* canvas/composition
* camera
* environment/location
* characters with screen position and depth
* pose/facing/gaze/expression for each important character
* interactions
* lighting and mood
* background anchors
* foreground props
* clarity instructions

Example structure:

```text
Painterly semi-realistic fantasy illustration with anime-influenced facial proportions and large expressive eyes. Landscape wide shot of a magic academy hall, composed as a 3-column by 2-row scene layout. In the lower-left foreground, Tsaeytte crouches with one hand braced on the stone floor, body angled toward the center-right, looking up alertly at the teacher. In the lower-center midground, Kaeldor stands casually with one hand near his visible amulet, watching the glowing doorway. In the upper-center background, the teacher stands elevated on a stone stair landing. A glowing arched doorway occupies the upper-right background and casts cool blue magical light across the hall. Warm lantern light mixes with cool magical glow. Clear spatial staging, readable silhouettes, coherent character placement, no cropped primary characters.
```

Use existing project style settings if available. Do not hardcode a style if the project already has a canonical style source.

# Negative Prompt Generation

Generate a practical negative prompt from the scene data and common layout failure modes.

Example:

```text
confused layout, merged characters, duplicated characters, extra limbs, wrong character placement, cropped primary character, obscured faces, unreadable poses, inconsistent gaze direction, incorrect facing direction, cluttered composition, oversized speech bubbles, text artifacts, malformed hands, distorted anatomy
```

Allow the user to edit the negative prompt.

# Markdown Export

When exporting to the associated `.md` file, include sections like:

```markdown
# Scene: First Day at the Spire

## Scene Brief

...

## Positive Image Prompt

...

## Negative Prompt

...

## Structured Layout Summary

### Canvas

- Orientation:
- Aspect ratio:
- Grid:

### Camera

- Shot type:
- Camera height:
- Camera angle:
- Viewer position:

### Characters and Placements

...

### Environment

...

### Interactions

...

## Validation Warnings

...
```

Do not include raw JSON in the `.md` unless there is already a project convention for embedded metadata.

The `.json` is the source of truth for structured Scene Builder data.

The `.md` is the human-readable prompt artifact.

# Validation

Implement validation warnings.

At minimum, detect:

* no scene name
* no associated `.md` path
* no characters
* no placements
* placement references a missing character
* placement row/column outside grid bounds
* primary character is marked background or distant
* expression is specified but size/prominence is small or distant
* multiple named primary characters in the same cell
* too many named primary/secondary characters for a small canvas
* interaction references missing subject or target
* camera says rear/behind but character gaze says looking at viewer
* no lighting specified
* no focal point specified
* no environment/location specified

Validation should not block saving unless the data is structurally invalid.

Warnings should be displayed in the UI and stored in:

```json
generation_outputs.validation_warnings
```

# File Operations

Implement safe file operations.

Required behavior:

* Load Scene Builder JSON from the same base filename as selected `.md` or `.png`.
* Save Scene Builder JSON atomically if practical.
* Create new JSON if missing.
* Update `metadata.updated_at` on save.
* Preserve unknown fields when loading/saving if practical, to allow future schema evolution.
* Pretty-print JSON with stable indentation.
* Use relative paths when that matches project conventions.
* Do not delete associated `.md` or `.png` files.
* Do not overwrite `.md` automatically unless the user clicks an explicit export/update button.

# Schema Versioning

Include:

```json
"schema_version": 1
```

When loading:

* accept schema_version 1
* handle missing optional fields with defaults
* show a readable error if the JSON is malformed
* do not crash the app on malformed JSON

# Suggested Internal Functions

Implement functions equivalent to:

```python
def get_scene_builder_json_path(scene_path: Path) -> Path:
    return scene_path.with_suffix(".json")
```

```python
def create_default_scene_builder_data(scene_md_path: Path | None = None) -> dict:
    ...
```

```python
def load_scene_builder_data(scene_path: Path) -> dict:
    ...
```

```python
def save_scene_builder_data(scene_path: Path, data: dict) -> None:
    ...
```

```python
def validate_scene_builder_data(data: dict) -> list[str]:
    ...
```

```python
def generate_scene_brief(data: dict) -> str:
    ...
```

```python
def generate_positive_prompt(data: dict) -> str:
    ...
```

```python
def generate_negative_prompt(data: dict) -> str:
    ...
```

```python
def export_scene_markdown(scene_md_path: Path, data: dict) -> None:
    ...
```

Use language/framework equivalents if Zet is not Python in this area.

# Cell Naming

Implement a helper to produce human-readable cell names.

For 3 columns x 2 rows:

```text
row 1 col 1 -> upper-left
row 1 col 2 -> upper-center
row 1 col 3 -> upper-right
row 2 col 1 -> lower-left
row 2 col 2 -> lower-center
row 2 col 3 -> lower-right
```

For 3 columns x 3 rows:

```text
upper-left
upper-center
upper-right
center-left
center
center-right
lower-left
lower-center
lower-right
```

For other grid sizes, use:

```text
row 1 column 1
row 1 column 2
...
```

# Defaults

New Scene Builder data should default to:

```json
{
  "canvas": {
    "orientation": "landscape",
    "aspect_ratio": "16:9"
  },
  "composition": {
    "template": "custom",
    "grid": {
      "columns": 3,
      "rows": 2
    }
  },
  "camera": {
    "shot_type": "wide shot",
    "camera_height": "eye-level",
    "camera_angle": "straight-on",
    "viewer_position": "front",
    "lens_feel": "normal",
    "focus_priority": "whole group"
  }
}
```

# Acceptance Criteria

The implementation is complete when:

1. A user can create or open a scene.
2. The app creates/loads a `.json` file with the same base name as the associated `.md` or `.png`.
3. The user can edit scene setup data.
4. The user can add/edit/remove characters.
5. The user can place characters into grid cells.
6. The user can edit placement details including pose, depth, facing, gaze, and expression.
7. The user can add environment anchors and props.
8. The user can edit camera settings.
9. The user can add interactions.
10. The app displays a simple grid preview with labels.
11. The app generates a scene brief.
12. The app generates a positive image prompt.
13. The app generates a negative prompt.
14. The app displays validation warnings.
15. The app saves the structured data to JSON.
16. The app exports a readable `.md` prompt file.
17. Loading the scene again restores the saved JSON data.
18. The implementation does not break existing Zet behavior.

# Test Cases

Add or manually verify tests for:

## Path Mapping

Input:

```text
Scenes/Test_Scene.md
```

Expected JSON path:

```text
Scenes/Test_Scene.json
```

Input:

```text
Scenes/Test_Scene.png
```

Expected JSON path:

```text
Scenes/Test_Scene.json
```

## Create New Scene

* Create new scene named `Test Scene`.
* Save it.
* Confirm `Test_Scene.json` exists.
* Confirm JSON includes `schema_version: 1`.
* Confirm metadata has `created_at` and `updated_at`.

## Character Placement

* Add character `Tsaeytte`.
* Place her in row 2, column 1.
* Confirm cell name is `lower-left` for a 3x2 grid.
* Set depth to `foreground`.
* Save and reload.
* Confirm placement persists.

## Prompt Generation

Given:

* landscape
* 3x2 grid
* Tsaeytte in lower-left foreground
* Teacher in upper-center background
* glowing doorway in upper-right background

Expected scene brief should mention:

* landscape
* 3-column by 2-row composition
* lower-left foreground Tsaeytte
* upper-center background Teacher
* upper-right background glowing doorway

## Validation

Trigger warnings for:

* placement references missing character
* no lighting
* no environment/location
* primary character placed in distant background
* interaction target missing

# Non-Goals for v1

Do not implement these unless they are already trivial in the project:

* full top-down plan view
* 3D staging
* automatic image segmentation
* regional masks
* Local Image Generation workflow generation
* drag-and-drop if simple click selection is faster
* AI-generated layout suggestions
* automatic character identity lookup from the full character library

The proof of concept should focus on structured scene authoring and prompt generation.

# Development Notes

Keep the code easy to extend.

The likely v2 additions are:

* plan-view camera cone
* drag-and-drop tokens
* saved pose snippets
* reusable composition templates
* regional prompt export
* Local Image Generation area-conditioning export
* automatic character lookup from existing Zet character assets
* direct comparison between scene JSON and rendered `.png`
* iteration history for revised prompts

Design the v1 model so these can be added later without replacing the data structure.

# Questions
* Where should users open the Scene Builder from: a scene file detail page, project dashboard action, or dedicated route?

A button on the Scenes page. Sorten existing button labels as follows:
Stage Render -> Render, Save Scene -> Scene, Delete Scene -> Delete, Toggle Image -> Images
Add "Builder" button between Render and Save that opens the Scene Builder for that Scene.

* Should JSON save be explicit only, autosave, or both?

Both

* When exporting Markdown, should Zet replace the entire `.md` file or update only Scene Builder-managed sections?

Just the Scene Builder-managed sections.

* What is the canonical source for project art style, if one exists?

It is in the Story file that the scene is in, in the <!-- ZET:BEGIN CANONICAL_ART_STYLE --> section.

* Should v1 character entry be manual only, or should it read from existing character/asset data when available?

Should allow selection from existing characters and allow manual entry for NPC characters necessary for scene.

* Should associated paths be stored relative to the project root or exactly as selected by the user?

User should not set any paths - the file structure of the asset library, stories, and scenes is established. The scene they launch the scene builder from has information that can be passed to the scene builder that determines the path. There should be existing helpers that do this or can be modified as necessary. The scene .json file should be in the Story folder in the library, any general lists of dropdown items or validation lists or general templates should be in the Config folder of the zet project.

* Should malformed or unsupported Scene Builder JSON open in a recoverable editor state, or block editing until fixed?

Blocked
