Update Zet Scene Builder from v1 to v2.

# Goal

Migrate the Scene Builder data model and UI from the original v1 structure to a cleaner v2 model.

The v2 model should:

1. Replace separate `characters`, `foreground_props`, and `background_anchors` collections with a unified `scene_elements` collection.
2. Add support for a new scene element type: `Monster`.
3. Store placements as a separate top-level collection linked to scene elements by ID.
4. Move remaining environment properties under general setup.
5. Update generation, validation, save/load, and markdown export to use the v2 model.
6. Update the Scene Builder UI to a 3-column layout:

   * left: general scene settings
   * middle: grid preview
   * right: scene element list plus selected element/placement editor

# Important Implementation Rule

Use diff-based changes and preserve existing behavior where possible.

Before editing:

1. Inspect existing Scene Builder files.
2. Find all uses of:

   * `characters`
   * `placements`
   * `foreground_props`
   * `background_anchors`
   * `environment`
   * prompt generation
   * validation
   * markdown export
   * JSON save/load
3. Update the data model and all dependent code together.
4. Add migration logic so existing v1 `.json` files can be opened and converted to v2.

# v2 Data Model

Use this structure as the target schema.

```json
{
  "schema_version": 2,
  "scene": {
    "name": "",
    "slug": "",
    "associated_md_path": "",
    "associated_png_path": "",
    "notes": ""
  },
  "setup": {
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
    "environment": {
      "location": "",
      "lighting": "",
      "mood": "",
      "weather_or_atmosphere": "",
      "important_exclusions": [],
      "general_background_notes": "",
      "general_foreground_notes": ""
    }
  },
  "scene_elements": [
    {
      "id": "Tsaeytte",
      "display_name": "Tsaeytte",
      "element_type": "Character",
      "asset_tag": "{{ASSET:Tsaeytte:Adult:31}}",
      "image_tag": "",
      "identity_prompt": "",
      "default_visual_description": "",
      "role": "protagonist",
      "importance": "primary",
      "notes": ""
    }
  ],
  "placements": [
    {
      "id": "placement_001",
      "scene_element_id": "Tsaeytte",
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
      "gaze_target_element_id": "Teacher",
      "gaze_target_description": "looking up at the teacher",
      "expression": "alert and wary",
      "interaction_target_element_id": "Teacher",
      "occlusion": "none",
      "placement_notes": ""
    }
  ],
  "depth_lanes": {
    "foreground": [],
    "midground": [],
    "background": []
  },
  "interactions": [
    {
      "subject_element_id": "Tsaeytte",
      "relationship": "looking at",
      "target_element_id": "Teacher",
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

# Scene Element Types

Allowed `element_type` values:

```text
Character
Monster
Prop
Anchor
```

Use a single string value, not an array.

## Type meanings

```text
Character
A named person or recurring identity-sensitive figure.

Monster
A creature, enemy, beast, demon, undead, construct, or other non-person threat or creature. May still have identity if recurring.

Prop
A movable object or foreground/midground object: sword, book, staff, skull, potion, table, chair, corpse, scroll.

Anchor
A location-defining visual feature, usually architectural or environmental: doorway, tower, window, bridge, statue, stair landing, throne, altar, pit, skyline.
```

# Why Placements Are Top-Level

Do not nest placements inside `scene_elements`.

Use top-level `placements` linked by `scene_element_id`.

Reason:

* long-term cleaner for editing
* easier to list all placements on the grid
* easier to support multiple placements of the same element
* easier to support future drag/drop, z-order, grouping, regional prompting, and ComfyUI export
* avoids duplicating element identity data when one element appears more than once

A scene element defines what something is.

A placement defines where and how it appears in this scene.

# Required Migration Behavior

When loading a Scene Builder JSON file:

1. If `schema_version` is `2`, load normally.
2. If `schema_version` is `1` or missing, migrate it to v2 in memory.
3. After migration, allow the user to save the migrated v2 JSON.
4. Do not destroy the original file until save is explicitly performed.
5. Preserve unknown fields if practical.

# v1 to v2 Mapping

## Top-Level Fields

v1:

```json
{
  "schema_version": 1,
  "scene": {},
  "canvas": {},
  "composition": {},
  "camera": {},
  "characters": [],
  "placements": [],
  "environment": {},
  "depth_lanes": {},
  "interactions": [],
  "generation_outputs": {},
  "metadata": {}
}
```

v2:

```json
{
  "schema_version": 2,
  "scene": {},
  "setup": {
    "canvas": {},
    "composition": {},
    "camera": {},
    "environment": {}
  },
  "scene_elements": [],
  "placements": [],
  "depth_lanes": {},
  "interactions": [],
  "generation_outputs": {},
  "metadata": {}
}
```

## Canvas

Move:

```text
v1.canvas -> v2.setup.canvas
```

## Composition

Move:

```text
v1.composition -> v2.setup.composition
```

## Camera

Move:

```text
v1.camera -> v2.setup.camera
```

## Environment

Move general fields:

```text
v1.environment.location -> v2.setup.environment.location
v1.environment.lighting -> v2.setup.environment.lighting
v1.environment.mood -> v2.setup.environment.mood
v1.environment.weather_or_atmosphere -> v2.setup.environment.weather_or_atmosphere
v1.environment.important_exclusions -> v2.setup.environment.important_exclusions
```

If v1 has extra environment fields, preserve them if possible under:

```text
v2.setup.environment.general_background_notes
v2.setup.environment.general_foreground_notes
```

or preserve as unknown fields inside `setup.environment`.

## Characters

Convert each v1 character into a v2 scene element:

v1:

```json
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
```

v2:

```json
{
  "id": "Tsaeytte",
  "display_name": "Tsaeytte",
  "element_type": "Character",
  "asset_tag": "{{ASSET:Tsaeytte:Adult:31}}",
  "image_tag": "",
  "identity_prompt": "",
  "default_visual_description": "",
  "role": "protagonist",
  "importance": "primary",
  "notes": ""
}
```

Migration details:

```text
v1.character.id -> v2.scene_element.id
v1.character.display_name -> v2.scene_element.display_name
v1.character.asset_tag -> v2.scene_element.asset_tag
v1.character.identity_prompt -> v2.scene_element.identity_prompt
v1.character.default_costume -> append or map to v2.scene_element.default_visual_description
v1.character.role -> v2.scene_element.role
v1.character.importance -> v2.scene_element.importance
v1.character.notes -> v2.scene_element.notes
```

If `id` is missing, create a stable slug from `display_name`.

## Foreground Props

If v1 has:

```json
"foreground_props": []
```

convert each item to a v2 `scene_element` with:

```json
"element_type": "Prop"
```

If the prop has placement-like fields, move those fields into a new top-level placement linked by `scene_element_id`.

If the prop is only text, create:

```json
{
  "id": "prop_slug",
  "display_name": "Readable Prop Name",
  "element_type": "Prop",
  "asset_tag": "",
  "image_tag": "",
  "identity_prompt": "",
  "default_visual_description": "original prop text",
  "role": "foreground prop",
  "importance": "secondary",
  "notes": ""
}
```

Then create a placement if enough information exists. If no placement exists, leave it unplaced and let validation warn.

## Background Anchors

If v1 has:

```json
"background_anchors": []
```

or:

```json
"environment.background_anchors": []
```

convert each anchor to a v2 `scene_element` with:

```json
"element_type": "Anchor"
```

If the anchor has screen cell/depth information, create a linked top-level placement.

If no placement exists, default depth to `background` only if the old field clearly came from background anchors.

## Existing v1 Placements

v1 placements may look like:

```json
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
```

Convert to v2:

```json
{
  "id": "placement_001",
  "scene_element_id": "Tsaeytte",
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
  "gaze_target_element_id": "Teacher",
  "gaze_target_description": "Teacher",
  "expression": "alert and wary",
  "interaction_target_element_id": "Teacher",
  "occlusion": "none",
  "placement_notes": ""
}
```

Migration details:

```text
v1.placement.character_id -> v2.placement.scene_element_id
v1.placement.label -> discard if it matches the scene element display_name; otherwise preserve in placement_notes
v1.placement.gaze_target -> v2.placement.gaze_target_element_id if target matches known element id/display_name
v1.placement.gaze_target -> v2.placement.gaze_target_description always
v1.placement.interaction_target -> v2.placement.interaction_target_element_id if target matches known element id/display_name
v1.placement.notes -> v2.placement.placement_notes
```

If v1 placement references a character that does not exist, create a placeholder scene element:

```json
{
  "id": "missing_reference_slug",
  "display_name": "Original Label",
  "element_type": "Character",
  "asset_tag": "",
  "image_tag": "",
  "identity_prompt": "",
  "default_visual_description": "",
  "role": "",
  "importance": "secondary",
  "notes": "Created during v1 to v2 migration because a placement referenced this missing element."
}
```

Add a validation warning.

# Interactions Migration

v1 interactions may use:

```json
{
  "subject": "Tsaeytte",
  "relationship": "looking at",
  "target": "Teacher",
  "note": "alert and wary"
}
```

Convert to:

```json
{
  "subject_element_id": "Tsaeytte",
  "relationship": "looking at",
  "target_element_id": "Teacher",
  "note": "alert and wary"
}
```

If subject or target cannot be matched to a known scene element, keep the text if the code supports fallback fields:

```json
{
  "subject_element_id": "",
  "subject_description": "unknown original subject text",
  "relationship": "looking at",
  "target_element_id": "",
  "target_description": "unknown original target text",
  "note": "alert and wary"
}
```

If fallback fields are not supported, create validation warnings.

# Depth Lanes

Rebuild `depth_lanes` from top-level placements when possible.

For each placement:

```text
placement.depth = foreground -> add placement.scene_element_id to depth_lanes.foreground
placement.depth = midground -> add placement.scene_element_id to depth_lanes.midground
placement.depth = background or distant background -> add placement.scene_element_id to depth_lanes.background
```

Avoid duplicate IDs in each lane.

If the old `depth_lanes` contains entries that no longer correspond to any scene element, preserve them only if practical and warn.

# New Helper Functions

Add or update helpers equivalent to:

```python
def migrate_scene_builder_data(data: dict) -> dict:
    """Return schema_version 2 data. Do not mutate caller data if avoidable."""
```

```python
def is_v1_scene_builder_data(data: dict) -> bool:
    """Return true if data appears to be schema v1 or old layout."""
```

```python
def create_default_scene_builder_data_v2(scene_md_path: Path | None = None) -> dict:
    """Create a new v2 scene builder document."""
```

```python
def normalize_scene_element_id(display_name: str) -> str:
    """Create a stable ID for scene elements when missing."""
```

```python
def find_scene_element_id(data: dict, text: str) -> str | None:
    """Match by id or display_name."""
```

```python
def rebuild_depth_lanes_from_placements(data: dict) -> dict:
    """Rebuild depth lanes from placements."""
```

Use equivalent functions if the codebase is not Python.

# Validation Updates

Update validation to use v2.

At minimum, detect:

* no scene name
* no associated `.md` path
* no scene elements
* no placements
* scene element has missing id
* scene element has duplicate id
* scene element has invalid `element_type`
* scene element has invalid `importance`
* placement references missing `scene_element_id`
* placement row/column outside grid bounds
* primary Character or Monster is placed in background or distant background
* expression is specified but size/prominence is small or distant
* multiple primary Character/Monster elements in the same cell
* too many primary/secondary Character/Monster elements for a small canvas
* interaction references missing subject or target element
* gaze target references missing element
* interaction target references missing element
* camera says rear/behind but gaze says looking at viewer
* no lighting specified
* no focal point specified
* no environment location specified
* unplaced primary scene elements

Validation should distinguish between element types:

```text
Character and Monster:
- pose, facing, gaze, expression may be important

Prop:
- pose/expression/gaze usually irrelevant

Anchor:
- pose/expression/gaze usually irrelevant
```

Do not require character-specific fields for Props and Anchors.

# Generation Updates

Update scene brief, positive prompt, negative prompt, and markdown export to use:

```text
scene_elements + placements
```

Generation should resolve placements by joining:

```text
placement.scene_element_id -> scene_elements[id]
```

Prompt generation should group output in a natural order:

1. canvas/composition/camera
2. location/environment
3. foreground elements
4. midground elements
5. background elements
6. interactions
7. lighting/mood
8. exclusions/negative prompt concepts

For each placement, generate wording based on element type.

## Character wording

Use:

```text
In the lower-left foreground, Tsaeytte crouches with one hand braced on the floor, body angled toward center-right, looking up at the teacher with an alert, wary expression.
```

## Monster wording

Use:

```text
In the upper-center midground, the Minotaur Guardian looms forward, dominant in scale, axe lowered at its side, glaring toward Tsaeytte.
```

## Prop wording

Use:

```text
A broken staff lies in the lower-left foreground near Tsaeytte.
```

## Anchor wording

Use:

```text
A glowing arched doorway fills the upper-right background, casting cool blue magical light across the hall.
```

# Markdown Export Updates

Update markdown export to include:

```markdown
# Scene: <scene name>

## Scene Brief

...

## Positive Image Prompt

...

## Negative Prompt

...

## Structured Layout Summary

### Setup

#### Canvas
- Orientation:
- Aspect ratio:

#### Composition
- Template:
- Grid:
- Primary focal point:

#### Camera
- Shot type:
- Camera height:
- Camera angle:
- Viewer position:
- Lens feel:
- Focus priority:

#### Environment
- Location:
- Lighting:
- Mood:
- Weather/atmosphere:
- Important exclusions:

### Scene Elements

| ID | Display Name | Type | Importance | Role | Asset/Image Tag |
|---|---|---|---|---|---|

### Placements

| Element | Cell | Depth | Position | Size | Pose | Facing | Gaze | Expression |
|---|---|---|---|---|---|---|---|---|

### Interactions

...

## Validation Warnings

...
```

The `.json` remains the source of truth.

The `.md` is the readable prompt artifact.

# Updated UI Layout

Change the Scene Builder screen to a 3-column layout.

## Overall Layout

```text
┌─────────────────────────────┬─────────────────────────────┬─────────────────────────────┐
│ Left Column                 │ Middle Column               │ Right Column                │
│ General Scene Settings      │ Grid Preview                 │ Scene Elements + Editor     │
│                             │                             │                             │
│ Setup                       │                             │ Element List                │
│ Composition                 │                             │ Add/Delete Controls         │
│ Camera                      │                             │                             │
│ Environment                 │                             │ Selected Element Properties │
│                             │                             │ Selected Placement Fields   │
└─────────────────────────────┴─────────────────────────────┴─────────────────────────────┘
```

The UI should be functional before it is polished.

## Left Column: General Scene Settings

Contains collapsible or grouped sections:

```text
Setup
Composition
Camera
Environment
```

### Setup Fields

* scene name
* associated `.md` path
* associated `.png` path
* notes

### Composition Fields

* orientation
* aspect ratio
* grid rows
* grid columns
* composition template
* primary focal point
* composition notes

### Camera Fields

* shot type
* camera height
* camera angle
* viewer position
* lens feel
* focus priority
* camera notes

### Environment Fields

* location
* lighting
* mood
* weather/atmosphere
* important exclusions
* general foreground notes
* general background notes

## Middle Column: Grid Preview

The middle column shows the composition grid.

Requirements:

* use current grid rows/columns
* show each cell boundary
* show cell names when practical
* show scene element labels for placements in each cell
* show element type visually if practical, for example:

  * Character
  * Monster
  * Prop
  * Anchor
* show depth labels if practical
* selecting a cell sets the active cell
* selecting a placed item sets the selected placement and selected scene element
* if drag/drop is already easy, allow it; otherwise use click/select controls

Minimum acceptable behavior:

1. User selects a scene element in the right column.
2. User clicks a grid cell.
3. App creates or updates a placement for that element in the selected cell.

If the element already has a placement, either:

* move the existing placement to the clicked cell, or
* ask whether to move existing placement or create another placement.

For v1/v2 proof-of-concept, moving the existing placement is acceptable unless there is an explicit “Add Additional Placement” button.

## Right Column: Scene Element List and Editor

The right column has two major sections.

### Top Right: Element List

Show all `scene_elements`.

Each row/card should show:

* display name
* element type
* importance
* whether it has a placement
* optional asset/image indicator

Controls:

* Add Element
* Delete Selected Element
* Duplicate Element, optional
* Add Placement for Selected Element
* Delete Selected Placement, if applicable

Add Element should ask for or create defaults:

```json
{
  "id": "new_element",
  "display_name": "New Element",
  "element_type": "Character",
  "asset_tag": "",
  "image_tag": "",
  "identity_prompt": "",
  "default_visual_description": "",
  "role": "",
  "importance": "secondary",
  "notes": ""
}
```

Deleting an element should also delete or warn about linked placements and interactions.

Recommended behavior:

* If deleting an element with placements/interactions, show confirmation.
* If confirmed, delete the element and its linked placements.
* Also remove or warn about interactions that referenced it.

### Bottom Right: Selected Element Properties

Fields:

* id
* display name
* element type
* asset tag
* image tag
* identity prompt
* default visual description
* role
* importance
* notes

Element type dropdown:

```text
Character
Monster
Prop
Anchor
```

Importance dropdown:

```text
primary
secondary
background
extra
```

### Bottom Right: Selected Placement Fields

Fields:

* placement id
* screen cell row
* screen cell column
* screen cell name
* position within cell
* depth
* size/prominence
* pose
* body facing
* head facing
* gaze target element
* gaze target description
* expression
* interaction target element
* occlusion
* placement notes

The placement editor should only be active if the selected element has a selected placement.

If selected element has no placement, show:

```text
This element has no placement yet. Select a grid cell or click Add Placement.
```

For Props and Anchors, hide or de-emphasize character-specific fields if easy:

* body facing
* head facing
* gaze target
* expression

Do not remove those fields from the data model; just make the UI less cluttered.

# Save/Load Behavior

Continue using the same base filename rule:

```text
Scenes/First_Day_at_the_Spire.md
Scenes/First_Day_at_the_Spire.png
Scenes/First_Day_at_the_Spire.json
```

When a v1 file is loaded:

* migrate in memory
* mark data as dirty
* show a non-blocking message such as:

  * “This scene used an older Scene Builder schema and has been migrated to v2. Save to update the JSON file.”
* saving writes schema version 2

# Required Tests / Manual Checks

## Migration Test: Character

Input v1:

```json
{
  "schema_version": 1,
  "characters": [
    {
      "id": "Tsaeytte",
      "display_name": "Tsaeytte",
      "asset_tag": "{{ASSET:Tsaeytte:Adult:31}}",
      "role": "protagonist",
      "importance": "primary",
      "identity_prompt": "",
      "default_costume": "adult adventuring outfit",
      "notes": ""
    }
  ],
  "placements": [
    {
      "id": "placement_001",
      "character_id": "Tsaeytte",
      "screen_cell": {
        "row": 2,
        "column": 1,
        "name": "lower-left"
      },
      "depth": "foreground",
      "pose": "crouched",
      "gaze_target": "Teacher",
      "notes": "test note"
    }
  ]
}
```

Expected v2:

```text
schema_version = 2
scene_elements contains Tsaeytte
Tsaeytte.element_type = Character
placements contains placement_001
placement_001.scene_element_id = Tsaeytte
placement_001.placement_notes contains test note
```

## Migration Test: Background Anchor

Input v1 background anchor should become:

```text
scene_element.element_type = Anchor
```

with a linked placement if placement data exists.

## Migration Test: Foreground Prop

Input v1 foreground prop should become:

```text
scene_element.element_type = Prop
```

with a linked placement if placement data exists.

## UI Test

Verify:

1. Left column shows Setup, Composition, Camera, Environment.
2. Middle column shows grid preview.
3. Right column shows Scene Element list.
4. Add Element creates a `scene_elements` entry.
5. Selecting an element shows properties.
6. Clicking a grid cell creates or updates a placement linked by `scene_element_id`.
7. Placement appears in grid preview.
8. Save and reload preserves element and placement.
9. Delete selected element removes linked placement after confirmation.
10. Prompt generation includes the selected element and placement.

## Validation Test

Verify warnings for:

* invalid element type
* duplicate scene element id
* placement linked to missing element id
* interaction linked to missing element id
* no scene elements
* no placements
* primary Character or Monster unplaced
* primary Character or Monster in distant background
* Prop with expression does not crash generation
* Anchor with no pose does not produce awkward prompt wording

# Acceptance Criteria

The update is complete when:

1. New scenes are created using schema version 2.
2. Existing v1 scenes can be loaded and migrated.
3. `characters`, `foreground_props`, and `background_anchors` are no longer required by current code.
4. `scene_elements` supports Character, Monster, Prop, and Anchor.
5. `placements` are top-level and link to scene elements by `scene_element_id`.
6. Environment fields live under `setup.environment`.
7. The updated 3-column UI is functional.
8. Grid preview displays placements from the top-level `placements` list.
9. Selecting an element allows editing its properties and placement fields.
10. Generated scene brief and prompts use v2 data.
11. Markdown export uses v2 data.
12. Validation uses v2 data.
13. Save/load round-trips v2 JSON without data loss.
14. Existing non-Scene-Builder Zet behavior is not broken.

# Non-Goals

Do not implement these unless already trivial:

* full top-down plan view
* 3D staging
* regional prompt masks
* ComfyUI workflow export
* automatic image analysis
* automatic character lookup from the full library
* drag-and-drop if click/select is faster to implement
* complex migration UI
* multiple schema migration history beyond v1 to v2

Focus on clean data model migration, usable UI, and reliable prompt generation.
