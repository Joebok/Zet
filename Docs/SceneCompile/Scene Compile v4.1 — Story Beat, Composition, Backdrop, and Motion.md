# CODEX Task: Scene Compile v4.1 — Story Beat, Composition, Backdrop, and Motion

## Objective

Update the current JSON-backed scene compiler and Scene Builder data model to improve the global visual readability of generated scene prompts while keeping the system simple and straightforward.

Implement the following six changes:

1. Pass `scene.story_beat` through the compiler and place it near the top of `Final_Image_Prompt.md`.
2. Give `Backdrop` elements special semantics as the scene’s overall visible setting.
3. Add a small `setup.composition` object containing:

   * `focal_point`
   * `left_to_right`
   * `composition_notes`
4. Add a small `motion` object to each placement containing:

   * `state`
   * `direction_screen`
   * `cue`
5. Separate props, interactions, and motion into distinct prompt sections.
6. Change local-render subject counting so it explicitly counts characters rather than all visible scene elements.

Do not introduce a generalized relationship graph, coordinate system, motion path system, multiple backdrop layers, or other advanced composition structures.

This project is still in prototype mode. Do not preserve compatibility with retired scene fields unless a field is explicitly retained below.

---

# Relevant Existing Files

The current render path is primarily implemented in:

* `zet/services/story_service.py`
* `zet/services/scene_render_compiler.py`

Also inspect and update the actual Scene Builder editor/UI code responsible for:

* creating new scene JSON files;
* loading existing scene JSON files;
* editing scene setup fields;
* editing placements;
* saving normalized scene JSON;
* displaying field helper text.

Do not change the legacy markdown render path unless necessary to avoid a regression. These changes apply to the current JSON-backed Scene Builder path.

Use narrow, diff-based edits. Do not rewrite entire files unnecessarily.

---

# Design Principles

Follow these principles throughout the implementation:

1. The scene JSON remains the canonical human-authored scene definition.
2. The render IR remains the normalized compiler-facing representation.
3. `Final_Image_Prompt.md` should describe the image globally before providing detailed element preservation instructions.
4. Backdrop, composition, placement, motion, and interaction are distinct concepts.
5. Scene Builder fields should remain understandable without cinematic or technical terminology.
6. Optional empty fields should be omitted from generated prose rather than producing empty headings or awkward sentences.
7. Compiler output must use display names rather than internal element IDs.
8. Validation should remain non-blocking except for existing hard file-resolution failures.
9. Do not add backward-compatibility migrations for retired fields. Normalize directly to the new canonical shape.

---

# Full Scene JSON Data Model

The following is the intended canonical scene `.scene.json` model after this change.

This is a complete structural description of the current model, including retained existing fields and the new fields introduced by this task.

```json
{
  "schema_version": 3,
  "file_kind": "scene",

  "scene": {
    "id": "string",
    "name": "string",
    "slug": "string",
    "sequence": null,

    "story_settings_path": "string",
    "associated_png_path": "string",
    "associated_md_path": "string",

    "story_beat": "string",
    "author_notes": "string",
    "notes": "string"
  },

  "setup": {
    "canvas": {
      "orientation": "landscape | portrait | square | string",
      "aspect_ratio": "string",
      "width": null,
      "height": null
    },

    "composition": {
      "focal_point": "string",
      "left_to_right": [
        "scene_element_id"
      ],
      "composition_notes": "string"
    },

    "environment": {
      "location": "string",
      "lighting": "string",
      "mood": "string",
      "weather_or_atmosphere": "string",

      "important_exclusions": [
        "string"
      ],

      "general_background_notes": "string",
      "general_foreground_notes": "string"
    }
  },

  "scene_elements": [
    {
      "id": "string",
      "display_name": "string",

      "resource_type": "Character | Person | Place | Object | Scene-Only | string",
      "element_type": "Character | Monster | Prop | Backdrop | Effect | Vehicle",

      "character": "string",
      "phase": "string",
      "costume": "string",

      "aux_category": "string",
      "aux_resource_id": "string",

      "reference_images": [
        {
          "tag": "string"
        }
      ],

      "fallback_visual_description": "string",
      "element_visual_override": "string",

      "notes": "string"
    }
  ],

  "placements": [
    {
      "id": "string",
      "scene_element_id": "string",

      "position_within_cell": "left | center | right | string",
      "depth": "foreground | midground | background | string",

      "frame_coverage": "string",
      "distance_from_camera": "string",
      "visual_scale": "string",

      "pose": {
        "summary": "string",
        "temporary_condition": "string",
        "gaze_target_element_id": "scene_element_id | empty string",
        "expression": "string",
        "left_arm_action": "string",
        "right_arm_action": "string",
        "leg_foot_detail": "string",
        "balance_weight_detail": "string"
      },

      "motion": {
        "state": "stationary | moving",
        "direction_screen": "left | right | toward camera | away from camera | up | down | up-left | up-right | down-left | down-right | empty string",
        "cue": "string"
      },

      "placement_notes": "string"
    }
  ],

  "props_and_states": [
    {
      "...": "retain the current props_and_states item model unchanged"
    }
  ],

  "interactions": [
    {
      "subject_element_id": "scene_element_id",
      "relationship": "string",
      "target_element_id": "scene_element_id",
      "note": "string"
    }
  ],

  "dialogue": [
    {
      "id": "string",
      "speaker_element_id": "scene_element_id",
      "text": "string",
      "target_element_id": "scene_element_id | empty string",
      "pointer_target": "string",
      "max_lines": 1,
      "notes": "string"
    }
  ],

  "reference_assignments": [
    {
      "...": "retain the current reference assignment model unchanged"
    }
  ],

  "avoid": {
    "scene_specific": [
      "string"
    ],
    "notes": "string"
  },

  "render_settings": {
    "final_image_prompt": {
      "enabled": true,
      "output_path": "string"
    },

    "local_render_brief": {
      "enabled": true,
      "output_path": "string"
    },

    "local_render_prompt": {
      "enabled": true,
      "output_path": "string"
    },

    "scene_render_ir": {
      "enabled": true,
      "output_path": "string"
    }
  },

  "metadata": {
    "created_at": "ISO-8601 datetime string",
    "updated_at": "ISO-8601 datetime string",
    "created_by": "string"
  },

  "depth_lanes": {
    "foreground": [
      "scene_element_id"
    ],
    "midground": [
      "scene_element_id"
    ],
    "background": [
      "scene_element_id"
    ]
  }
}
```

---

# Canonical Field Decisions

## Remove `pose.action_direction_screen`

The current placement pose contains:

```json
"action_direction_screen": ""
```

Remove this field from the canonical placement model.

Its responsibility is replaced by:

```json
"motion": {
  "state": "stationary",
  "direction_screen": "",
  "cue": ""
}
```

Because prototype compatibility is not required:

* do not keep writing `pose.action_direction_screen`;
* do not expose it in the Scene Builder;
* do not include it in generated scene JSON;
* remove its use from current JSON compiler logic.

It is acceptable for normalization to ignore the old field if encountered, but do not preserve or re-emit it.

## Existing duplicate visual override field

The example data contains both:

```json
"scene_visual_override": "..."
```

and:

```json
"element_visual_override": "..."
```

Treat `element_visual_override` as canonical.

Do not expand the scope of this task to redesign visual override behavior, but normalization should not introduce or preserve duplicate override fields. If the current normalizer already migrates one to the other, retain that behavior and save only `element_visual_override`.

## Story notes

Use the fields as follows:

* `story_beat`: render-facing statement of the visual moment.
* `author_notes`: private Scene Builder/editor notes; do not pass to render output.
* `notes`: retain existing behavior unless it is clearly obsolete elsewhere in the codebase.

Do not automatically substitute `scene.notes` for `story_beat`. The two fields serve different purposes.

---

# New Scene Defaults

When a new scene is created, initialize:

```json
"composition": {
  "focal_point": "",
  "left_to_right": [],
  "composition_notes": ""
}
```

Every new placement must initialize:

```json
"motion": {
  "state": "stationary",
  "direction_screen": "",
  "cue": ""
}
```

Backdrop placements should default to:

```json
{
  "position_within_cell": "",
  "depth": "background"
}
```

Do not require the user to assign a left, center, or right position to a Backdrop.

---

# Scene Builder UI Changes

Update the Scene Builder UI to expose the following fields.

## Scene Story Beat

Field:

```text
scene.story_beat
```

Label:

```text
Story Beat
```

Helper text:

```text
One sentence describing the visual moment or change the image must communicate. Describe what is happening now, not the surrounding plot.
```

Use an ordinary single-line or compact multiline text field.

Do not hide this field among private notes. It is render-facing.

## Composition

Add a simple Composition section under scene setup.

### Focal Point

Field:

```text
setup.composition.focal_point
```

Label:

```text
Primary Focal Point
```

Helper text:

```text
The person, action, or visual relationship viewers should notice first.
```

Use free text.

Example:

```text
Tsaeytte confronting Valindia
```

### Left-to-Right Visual Read

Field:

```text
setup.composition.left_to_right
```

Label:

```text
Left-to-Right Visual Read
```

Helper text:

```text
Order the important visible elements as the viewer should encounter them from the left side of the image to the right.
```

This must store scene element IDs, not display names.

Use the simplest UI already available in the project for ordering selected scene elements. Prefer one of these existing patterns, in order:

1. an existing reorderable element list;
2. add/remove controls plus move-up/move-down buttons;
3. a simple ordered multiselect.

Do not add a drag-and-drop framework solely for this field.

Display element display names in the UI while saving IDs.

Backdrop elements should normally be excluded from this list because they frame the overall scene rather than participate in the subject reading order.

Do not automatically add all props. Let the user include only visually important props.

### Composition Notes

Field:

```text
setup.composition.composition_notes
```

Label:

```text
Composition Notes
```

Helper text:

```text
Optional brief instruction about framing, overlap, spacing, or a major visual relationship not captured by placement fields.
```

Use free text.

## Placement Motion

Add a Motion subsection to each placement editor.

### Motion State

Field:

```text
placement.motion.state
```

Label:

```text
Motion
```

Allowed values:

```text
stationary
moving
```

Display labels may be:

```text
Stationary
Moving
```

Default:

```text
stationary
```

Helper text:

```text
Whether this element is still or visibly moving in the scene.
```

### Screen Direction

Field:

```text
placement.motion.direction_screen
```

Label:

```text
Movement Direction
```

Allowed values:

```text
""
left
right
toward camera
away from camera
up
down
up-left
up-right
down-left
down-right
```

Helper text:

```text
The direction the element is visibly moving within the finished image.
```

Disable or visually de-emphasize this field while state is `stationary`, if that is easy within the existing UI.

Do not delete a value merely because the field becomes disabled unless that matches existing form behavior.

### Motion Cue

Field:

```text
placement.motion.cue
```

Label:

```text
Motion Cue
```

Helper text:

```text
A short visual description showing movement, such as trailing hair, a lifted foot, flying fabric, falling debris, or a blurred limb.
```

Example:

```text
striding quickly toward the arch, with her skirt and hair trailing behind
```

Use free text.

---

# Normalization Changes

Update `StoryService._normalize_scene_builder_data(...)` and any related normalization helpers.

Ensure the following top-level collections and objects always exist:

```python
scene
setup
setup.canvas
setup.composition
setup.environment
scene_elements
placements
props_and_states
interactions
dialogue
reference_assignments
avoid
render_settings
metadata
depth_lanes
```

Normalize `setup.composition` to:

```python
{
    "focal_point": clean_string,
    "left_to_right": list_of_nonempty_strings,
    "composition_notes": clean_string,
}
```

Requirements:

* Preserve the user-defined order of `left_to_right`.
* Do not sort it.
* Remove blank values.
* Do not silently remove unresolved IDs during normalization; validation should report them.
* It is acceptable to remove exact duplicate IDs while preserving first occurrence, but validation should still be capable of warning when duplicate input was supplied if the existing validation architecture permits that before normalization.

Normalize every placement with:

```python
"motion": {
    "state": "stationary",
    "direction_screen": "",
    "cue": ""
}
```

Rules:

* Missing or blank `motion.state` becomes `stationary`.
* Unknown `motion.state` should remain available for validation or normalize to `stationary` while producing a warning. Prefer retaining the invalid value until validation if consistent with current architecture.
* Missing direction and cue become empty strings.
* Remove `pose.action_direction_screen` from normalized canonical output.
* Continue ensuring every scene element has one paired placement.
* Continue rebuilding `depth_lanes` from placements.
* Force or default Backdrop placement depth to `background`.
* Backdrop `position_within_cell` may remain blank.

Do not add a schema-version bump solely for this change. Retain:

```json
"schema_version": 3
```

unless the repository already has a strict policy requiring a version bump for additive fields.

---

# Backdrop Semantics

A scene may have zero or one primary Backdrop.

A primary Backdrop is any scene element whose:

```json
"element_type": "Backdrop"
```

Do not add a separate `primary_backdrop_id` field at this time.

## Compiler behavior

When exactly one Backdrop exists:

* treat it as the overall visible setting;
* emit it in a dedicated `# Backdrop and Setting` section;
* do not emit it as an ordinary staging line such as:

  * `Spire of Celestial Wisdom occupies the background`;
* do not count it as a character or local-render subject;
* use its resolved location-preservation description as the leading backdrop description;
* integrate `setup.environment.location` and `general_background_notes` without duplicating identical text;
* make clear that all characters, props, effects, and vehicles exist naturally inside or in front of this setting.

When no Backdrop exists:

* omit the `# Backdrop and Setting` section unless environment data alone justifies it;
* preserve the current environment behavior.

When more than one Backdrop exists:

* emit a non-blocking validation warning;
* choose the first Backdrop in `scene_elements` order as the primary Backdrop for compilation;
* do not invent multi-backdrop compositing behavior.

## Backdrop prompt wording

Use output similar to:

```markdown
# Backdrop and Setting

- The scene takes place at the entrance courtyard of the Spire of Celestial Wisdom.
- The Spire of Celestial Wisdom defines the overall background and surrounding setting.
- Show the monumental ivy-covered Gothic stone arch, emerald-and-gold banners, ornate wrought-iron gates, and the Spire visible beyond.
- Integrate all characters, props, and action naturally within this setting.
```

Generate only lines supported by available data.

Avoid redundant output such as:

```text
background background scenery
```

Do not repeat the Backdrop location-preservation text word-for-word in both the global and regional local-render prompts unless needed by the local backend.

The full canonical location-preservation text should still appear later in `# Scene Element Preservation`.

---

# Render IR Changes

Update `compile_scene_render_ir(...)`.

Add scene-level data:

```json
"scene": {
  "id": "string",
  "name": "string",
  "slug": "string",
  "story_beat": "string"
}
```

Do not include `author_notes` in the render IR unless the IR already intentionally carries private source metadata. It must not be consumed by prompt generation.

Add composition:

```json
"composition": {
  "focal_point": "string",
  "left_to_right": [
    "scene_element_id"
  ],
  "composition_notes": "string"
}
```

Retain each placement’s normalized `motion` object in the IR.

Optionally add a convenient compiler-derived Backdrop field:

```json
"backdrop": {
  "element_id": "string",
  "display_name": "string"
}
```

This is optional. It is also acceptable to derive the primary Backdrop from `ir["elements"]` wherever needed.

Do not duplicate the full Backdrop element in multiple IR locations unless that meaningfully simplifies the compiler.

---

# Final Prompt Section Order

Update `final_image_prompt_text(ir)` to use this order:

1. `# Render Task`
2. `# Story Beat`, when non-empty
3. `# Reference Image Assignment`, when references exist
4. `# Canvas`
5. `# Composition`, when any composition field is non-empty
6. `# Backdrop and Setting`, when a Backdrop or relevant setting data exists
7. `# Character and Object Staging`
8. `# Motion Cues`, when moving elements exist
9. `# Props and States`, when props/state records exist
10. `# Interactions`, when interactions exist
11. `# Environment`, when remaining environment text exists
12. `# Lighting and Mood`, when relevant data exists
13. `# Dialogue Panel`, when dialogue exists
14. `# Scene Element Preservation`, when relevant data exists
15. `# Avoid`
16. `# Final Verification`

Keep `# Reference Image Assignment` near the top because it corresponds to attached render references, but ensure the Story Beat appears before it.

Do not emit empty sections.

Rename the current:

```markdown
# Character and Location Staging
```

to:

```markdown
# Character and Object Staging
```

Backdrops and Place resources serving as the Backdrop should not appear as ordinary placement lines in this section.

A non-Backdrop Place element may still appear in staging if it represents a distinct placed architectural or environmental object rather than the overall setting.

---

# Story Beat Compilation

Compile `scene.story_beat` nearly verbatim.

Example input:

```json
"story_beat": "Tsaeytte confronts Valindia. Valindia knows she has gone too far."
```

Expected output:

```markdown
# Story Beat

Tsaeytte confronts Valindia. Valindia knows she has gone too far.
```

Requirements:

* trim surrounding whitespace;
* normalize terminal punctuation using the compiler’s existing sentence helper if appropriate;
* do not rewrite, summarize, infer, or embellish the text;
* omit the section when blank;
* do not use `author_notes` or `scene.notes` as automatic fallback.

---

# Composition Compilation

When any composition field is populated, emit:

```markdown
# Composition
```

## Focal point

Input:

```json
"focal_point": "Tsaeytte confronting Valindia"
```

Output:

```markdown
- Primary focal point: Tsaeytte confronting Valindia.
```

Do not resolve IDs inside free-text `focal_point`.

## Left-to-right visual read

Input:

```json
"left_to_right": [
  "Tsaeytte",
  "Squirrel_929d978f",
  "Valindia_a14ff5be"
]
```

Output:

```markdown
- Left-to-right visual read: Tsaeytte → Squirrel → Valindia.
```

Requirements:

* resolve every valid ID to its display name;
* preserve array order;
* use a clear arrow separator;
* skip unresolved IDs in final prompt output after validation has warned about them;
* omit the line if fewer than two valid elements remain;
* do not include the Backdrop automatically.

## Composition notes

Input:

```json
"composition_notes": "The Spire entrance arch frames both women behind the confrontation."
```

Output:

```markdown
- The Spire entrance arch frames both women behind the confrontation.
```

Pass through as a normal sentence.

---

# Placement and Staging Compilation

Retain existing placement prose for:

* Character
* Monster
* Prop
* Effect
* Vehicle
* non-Backdrop Place elements

Exclude the primary Backdrop from ordinary staging output.

Continue using:

* display name;
* position;
* depth;
* pose summary;
* gaze target;
* expression;
* left arm action;
* right arm action;
* placement notes.

Do not add motion prose to the ordinary staging line. Motion belongs in `# Motion Cues`.

Avoid saying that a Prop “stands” unless that is grammatically appropriate. Use a neutral verb or placement phrasing for non-character elements.

Examples:

```markdown
- Tsaeytte stands with her arms crossed in the left foreground. She looks directly at Valindia and appears angry.
- Valindia stands in the right foreground with one hand raised in warning. She looks directly at Tsaeytte and appears wary.
- A gray squirrel is positioned in the center midground.
```

Do not undertake a broad prose rewrite outside what is necessary for these changes, but fix obviously incorrect generic wording when touching the placement formatter.

---

# Motion Compilation

Add a helper such as:

```python
def _motion_lines(
    ir: dict[str, Any],
    elements_by_id: dict[str, dict[str, Any]],
) -> list[str]:
    ...
```

Emit `# Motion Cues` only when at least one eligible element has:

```json
"motion.state": "moving"
```

Do not list stationary elements by default. Their stillness is implicit.

Eligible moving elements include:

* Character
* Monster
* Prop
* Effect
* Vehicle

Exclude:

* Backdrop
* Place elements functioning as the overall setting

## Output rules

For direction and cue:

```json
"motion": {
  "state": "moving",
  "direction_screen": "right",
  "cue": "scampering between them with its tail streaming behind"
}
```

Output:

```markdown
- Squirrel is moving screen-right, scampering between them with its tail streaming behind.
```

For direction only:

```markdown
- Squirrel is moving screen-right.
```

For cue only:

```markdown
- Squirrel is moving, tumbling through the air.
```

Direction wording:

| Stored value       | Prompt wording          |
| ------------------ | ----------------------- |
| `left`             | `screen-left`           |
| `right`            | `screen-right`          |
| `toward camera`    | `toward the camera`     |
| `away from camera` | `away from the camera`  |
| `up`               | `upward`                |
| `down`             | `downward`              |
| `up-left`          | `up and screen-left`    |
| `up-right`         | `up and screen-right`   |
| `down-left`        | `down and screen-left`  |
| `down-right`       | `down and screen-right` |

Do not invent movement based solely on pose, interaction, or relationship text.

A character may have an active-looking pose while still being marked stationary.

---

# Props and Interactions

Replace the combined section:

```markdown
# Props and Interactions
```

with separate sections.

## Props and States

Emit:

```markdown
# Props and States
```

only when `props_and_states` contains compiled output.

Retain the existing props/state data model and current behavior unless minor formatting changes are necessary.

## Interactions

Emit:

```markdown
# Interactions
```

only when interaction lines exist.

Retain reciprocal gaze deduplication.

Example:

```markdown
- Tsaeytte and Valindia hold direct eye contact.
```

## Interaction notes

The interaction model contains:

```json
"note": "string"
```

Use this field intentionally rather than silently ignoring it.

For a non-empty note, append it as a second sentence or concise clause after the base interaction.

Example:

```json
{
  "subject_element_id": "Tsaeytte",
  "relationship": "looking at",
  "target_element_id": "Valindia_a14ff5be",
  "note": "Valindia is the first to break her composure."
}
```

Possible output:

```markdown
- Tsaeytte and Valindia hold direct eye contact. Valindia is the first to break her composure.
```

For deduplicated reciprocal interactions with two different notes:

* preserve meaningful nonduplicate notes;
* append each unique note in source order;
* do not output internal IDs;
* avoid repeating semantically identical notes if exact trimmed strings match.

Do not use interactions to store or infer motion.

---

# Environment Compilation

Avoid duplicating Backdrop information between:

* `# Backdrop and Setting`;
* `# Environment`;
* `# Scene Element Preservation`.

Use these responsibilities:

## Backdrop and Setting

Describes the visible overall setting and primary architecture.

Sources may include:

* Backdrop display name;
* Backdrop resolved identity/location-preservation text;
* `setup.environment.location`;
* `setup.environment.general_background_notes`.

## Environment

Describes remaining environmental details not already consumed, especially:

* general foreground notes;
* weather or atmospheric environmental description if not better placed under Lighting and Mood;
* other scene-wide environmental information.

## Scene Element Preservation

Contains the full canonical identity, costume, prop, object, and location-preservation source text.

Do not perform complex semantic deduplication. Simple exact normalized-string deduplication is sufficient.

---

# Reference Assignment

Retain existing reference assignment behavior.

However:

* do not emit an empty reference-assignment entry for a Scene-Only element whose reference tag is blank;
* the example currently produces an empty `Squirrel -` reference assignment, which should be omitted;
* only elements with at least one non-empty resolved or source reference tag should appear in `# Reference Image Assignment`.

This is a small cleanup directly related to clearer prompt structure.

---

# Local Render Brief Changes

Update `local_render_brief(ir)`.

## Rename subject count

Replace:

```json
"subject_count": 2
```

with:

```json
"character_count": 2
```

`character_count` should count visible placed elements whose `element_type` is:

```text
Character
Monster
```

Do not count:

* Prop
* Backdrop
* Place
* Effect
* Vehicle

If some existing local-render code needs the old internal variable name, it may remain internal, but the emitted brief must use `character_count`.

Do not emit both fields unless an external consumer demonstrably requires the old one. Prefer updating consumers.

## Character count wording

Generate count phrases such as:

```text
exactly two visible characters
```

rather than:

```text
exactly two visible subjects
```

Use:

* `one visible character`
* `exactly two visible characters`
* `exactly three visible characters`
* etc.

Do not let this phrase suppress an intended animal, prop, vehicle, or effect.

## Negative prompt wording

Use character-specific negatives:

```text
extra character
third character
duplicate character
same character twice
```

Do not use broad negatives like:

```text
extra subject
third subject
```

when the scene intentionally contains props or other visible elements.

## Backdrop

Use the primary Backdrop as the global/background setting.

Do not:

* count it as a character;
* include `exactly N visible characters` redundantly in every region unless the backend genuinely needs it;
* generate phrases such as `background background scenery`.

The Backdrop may remain a background region if the local backend benefits from a background regional prompt.

## Composition ordering

Use `setup.composition.left_to_right` to influence ordering of foreground/midground regional prompts when possible.

Requirements:

* preserve explicit composition order for elements represented in regions;
* append any unlisted regional elements using existing placement sorting;
* do not reorder the background Backdrop as though it were a foreground subject.

Do not redesign the regional prompting backend.

## Motion

For each moving element, append its direction and cue to its regional prompt.

Examples:

```text
moving screen-right, skirt and hair trailing behind
```

Do not add the word `stationary` to local prompts for still elements.

## Story beat

Do not automatically inject the full Story Beat into local Stable Diffusion prompts.

The Story Beat is often narrative rather than visually literal. Keep local prompts grounded in the structured composition, placement, interaction, and motion fields.

---

# Validation Changes

Update `StoryService.validate_scene_builder_data(...)`.

Retain all current validation and add the following non-blocking warnings.

## Story Beat

Warn when:

```text
scene.story_beat is missing or blank
```

Suggested message:

```text
Scene story_beat is blank; the final render prompt will not include a high-level visual moment.
```

## Backdrop

Warn when more than one element has:

```json
"element_type": "Backdrop"
```

Suggested message:

```text
Scene has more than one Backdrop element; only the first Backdrop will define the overall setting.
```

Warn when a Backdrop has a non-empty left/right position:

```text
Backdrop '<display name>' has a screen position that will be ignored; Backdrops define the overall setting.
```

Warn when a Backdrop depth is not `background`:

```text
Backdrop '<display name>' is not assigned to background depth; Backdrops are compiled as background settings.
```

Normalization may still correct the depth.

## Composition

Warn when `setup.composition.left_to_right` references a missing element:

```text
Composition left_to_right references missing scene element '<id>'.
```

Warn when an element appears more than once:

```text
Composition left_to_right contains duplicate scene element '<display name>'.
```

Warn when a Backdrop appears in `left_to_right`:

```text
Backdrop '<display name>' appears in left_to_right; Backdrops normally frame the scene rather than participate in subject reading order.
```

Warn when fewer than two valid elements are present but the list is non-empty:

```text
Composition left_to_right needs at least two valid elements to produce a visual reading order.
```

Optionally warn when a visible foreground or midground Character/Monster is absent from a non-empty `left_to_right` list.

Only implement this optional warning if it is straightforward and does not create noisy false positives.

Do not warn about incidental Props being absent.

## Motion

Allowed states:

```text
stationary
moving
```

Warn for invalid state:

```text
Placement for '<display name>' has invalid motion state '<value>'.
```

Warn when state is stationary but direction is populated:

```text
Placement for '<display name>' is stationary but has a movement direction.
```

Warn when state is moving but both direction and cue are blank:

```text
Placement for '<display name>' is moving but has neither a direction nor a motion cue.
```

Warn for invalid direction values.

Allowed directions:

```text
left
right
toward camera
away from camera
up
down
up-left
up-right
down-left
down-right
```

Warn if a Backdrop or Place setting is marked moving:

```text
Backdrop '<display name>' is marked moving; setting elements are normally stationary.
```

Do not make any of these warnings blocking.

---

# Final Verification Changes

Update the generated final-verification checklist to include composition and motion when present.

Base checklist may become:

```markdown
# Final Verification

- Character count and identities match the scene JSON.
- The Story Beat is visually clear.
- The primary focal point and left-to-right visual read match the composition instructions.
- Left/right placement and depth match the placements.
- Motion direction and motion cues are readable for all moving elements.
- Hands, props, gaze, and interactions are readable.
- The Backdrop clearly defines the overall setting.
- Setting, lighting, mood, and art style match the source data.
```

Only include conditional lines when applicable:

* Story Beat line only when Story Beat exists.
* Composition line only when focal point or left-to-right data exists.
* Motion line only when at least one moving element exists.
* Backdrop line only when a Backdrop exists.

Retain the existing story-profile option controlling whether final verification is emitted.

---

# Expected Example Scene Update

Update the copied or test example scene to use meaningful values.

```json
{
  "scene": {
    "id": "test_scene_01",
    "name": "Test Scene 01",
    "slug": "Test-Scene-01",
    "sequence": null,
    "story_settings_path": "Stories/V3-Test-Story/V3-Test-Story.story.json",
    "associated_png_path": "Stories/V3-Test-Story/Test-Scene-01.png",
    "associated_md_path": "",
    "story_beat": "Tsaeytte confronts Valindia, while Valindia realizes she has gone too far.",
    "author_notes": "Private setup notes.",
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
      "focal_point": "Tsaeytte confronting Valindia",
      "left_to_right": [
        "Tsaeytte",
        "Squirrel_929d978f",
        "Valindia_a14ff5be"
      ],
      "composition_notes": "The Spire entrance arch frames both women behind the confrontation."
    },

    "environment": {
      "location": "The entrance courtyard of the Spire of Celestial Wisdom.",
      "lighting": "Soft natural daylight.",
      "mood": "Tense and confrontational.",
      "weather_or_atmosphere": "Clear air with a slight breeze.",
      "important_exclusions": [],
      "general_background_notes": "",
      "general_foreground_notes": ""
    }
  }
}
```

Example stationary placement:

```json
{
  "id": "placement_tsaeytte",
  "scene_element_id": "Tsaeytte",
  "position_within_cell": "left",
  "depth": "foreground",

  "frame_coverage": "",
  "distance_from_camera": "",
  "visual_scale": "",

  "pose": {
    "summary": "arms crossed",
    "temporary_condition": "",
    "gaze_target_element_id": "Valindia_a14ff5be",
    "expression": "angry",
    "left_arm_action": "",
    "right_arm_action": "",
    "leg_foot_detail": "",
    "balance_weight_detail": ""
  },

  "motion": {
    "state": "stationary",
    "direction_screen": "",
    "cue": ""
  },

  "placement_notes": ""
}
```

Example moving squirrel:

```json
{
  "id": "placement_squirrel",
  "scene_element_id": "Squirrel_929d978f",
  "position_within_cell": "center",
  "depth": "midground",

  "frame_coverage": "",
  "distance_from_camera": "",
  "visual_scale": "",

  "pose": {
    "summary": "",
    "temporary_condition": "",
    "gaze_target_element_id": "",
    "expression": "",
    "left_arm_action": "",
    "right_arm_action": "",
    "leg_foot_detail": "",
    "balance_weight_detail": ""
  },

  "motion": {
    "state": "moving",
    "direction_screen": "right",
    "cue": "scampering between the two women with its tail streaming behind"
  },

  "placement_notes": ""
}
```

Example Backdrop placement:

```json
{
  "id": "placement_spire",
  "scene_element_id": "Spire_of_Celestial_Wisdom_750e56ef",
  "position_within_cell": "",
  "depth": "background",

  "frame_coverage": "",
  "distance_from_camera": "",
  "visual_scale": "",

  "pose": {
    "summary": "",
    "temporary_condition": "",
    "gaze_target_element_id": "",
    "expression": "",
    "left_arm_action": "",
    "right_arm_action": "",
    "leg_foot_detail": "",
    "balance_weight_detail": ""
  },

  "motion": {
    "state": "stationary",
    "direction_screen": "",
    "cue": ""
  },

  "placement_notes": ""
}
```

---

# Expected Final Image Prompt Shape

The updated example should produce output structurally similar to:

```markdown
# Render Task

Create one finished landscape 16:9 scene image. Do not show the planning grid or split the image into comic panels.

# Story Beat

Tsaeytte confronts Valindia, while Valindia realizes she has gone too far.

# Reference Image Assignment

- Tsaeytte - {{ASSET:Tsaeytte:Adult:27:Costume | Front-Right-3-4 | Canonical Adventure Gear}}
  Preserve identity, facial features, hair, ears when applicable, body proportions, costume design, costume colors, and signature worn items.
  Ignore source pose, expression, action, camera angle, framing, background, and lighting.

- Valindia - {{AUX:person:valindia:costume}}
  Preserve identity, facial features, hair, ears when applicable, body proportions, costume design, costume colors, and signature worn items.
  Ignore source pose, expression, action, camera angle, framing, background, and lighting.

- Spire of Celestial Wisdom - {{AUX:place:spire-of-celestial-wisdom:arch}}
  Preserve architecture, structural design, identifying materials, and location-defining features.
  Ignore source camera composition, framing, people, lighting, weather, and temporary objects.

# Canvas

- Landscape 16:9.
- Render one continuous scene. Do not show the planning grid or divide the image into panels.

# Composition

- Primary focal point: Tsaeytte confronting Valindia.
- Left-to-right visual read: Tsaeytte → Squirrel → Valindia.
- The Spire entrance arch frames both women behind the confrontation.

# Backdrop and Setting

- The scene takes place in the entrance courtyard of the Spire of Celestial Wisdom.
- The Spire of Celestial Wisdom defines the overall background and surrounding setting.
- Show the monumental ivy-covered Gothic stone arch, emerald-and-gold banners, ornate wrought-iron gates, and the Spire visible beyond.
- Integrate all characters, props, and action naturally within this setting.

# Character and Object Staging

- Tsaeytte stands with her arms crossed in the left foreground. She looks directly at Valindia and appears angry.
- Valindia stands in the right foreground with one hand raised in warning. She looks directly at Tsaeytte and appears wary.
- A gray squirrel is positioned in the center midground.

# Motion Cues

- Squirrel is moving screen-right, scampering between the two women with its tail streaming behind.

# Interactions

- Tsaeytte and Valindia hold direct eye contact.

# Lighting and Mood

- Lighting: Soft natural daylight.
- Mood: Tense and confrontational.
- Atmosphere: Clear air with a slight breeze.
- Art style: Painterly semi-realistic fantasy illustration with anime-influenced facial proportions, large expressive eyes, refined linework, and warm storybook-fantasy color handling.

# Dialogue Panel

Valindia says exactly: "wait..."
Place the panel so the dialogue reads as directed toward Tsaeytte.

# Scene Element Preservation

...

# Avoid

...

# Final Verification

- Character count and identities match the scene JSON.
- The Story Beat is visually clear.
- The primary focal point and left-to-right visual read match the composition instructions.
- Left/right placement and depth match the placements.
- Motion direction and motion cues are readable for all moving elements.
- Hands, props, gaze, and interactions are readable.
- The Backdrop clearly defines the overall setting.
- Setting, lighting, mood, and art style match the source data.
```

The empty Squirrel reference assignment must not appear.

The Spire must not also appear as:

```text
Spire of Celestial Wisdom occupies the background.
```

---

# Tests

Add or update automated tests for the compiler and normalization behavior.

Use the project’s existing test framework and conventions.

At minimum, cover the following.

## Normalization tests

1. Missing `setup.composition` receives empty defaults.
2. Missing placement `motion` receives stationary defaults.
3. `pose.action_direction_screen` is not present in normalized canonical output.
4. Backdrop placement defaults to background depth.
5. `left_to_right` order is preserved.
6. Blank `left_to_right` entries are removed.
7. New scenes and newly added placements receive the new defaults.

## Validation tests

1. Blank Story Beat produces a warning.
2. Multiple Backdrops produce a warning.
3. Missing composition IDs produce warnings.
4. Duplicate composition IDs produce warnings.
5. Backdrop in left-to-right produces a warning.
6. Invalid motion state produces a warning.
7. Invalid motion direction produces a warning.
8. Stationary plus direction produces a warning.
9. Moving without direction or cue produces a warning.
10. Valid new-shape scenes do not produce these warnings.

## IR tests

1. Story Beat is copied into the IR.
2. Composition is copied into the IR.
3. Motion is copied into placements.
4. Backdrop can be identified from IR elements.
5. Author notes do not appear in render-facing IR fields.

## Final prompt tests

1. Story Beat appears near the top.
2. Composition display names resolve correctly.
3. Left-to-right order matches the JSON array.
4. Backdrop receives its own section.
5. Backdrop is excluded from ordinary staging.
6. Moving elements appear in Motion Cues.
7. Stationary elements do not appear in Motion Cues.
8. Props and Interactions are separate sections.
9. Interaction notes are retained.
10. Empty reference tags do not create reference assignments.
11. Empty optional sections are omitted.
12. Final Verification includes only applicable conditional checks.

## Local render tests

1. Brief contains `character_count`, not `subject_count`.
2. Character and Monster elements count as characters.
3. Prop and Backdrop elements do not count as characters.
4. Count wording says `visible characters`, not `visible subjects`.
5. Backdrop leads the global/background prompt.
6. No `background background scenery` duplication occurs.
7. Motion cue appears in the moving element’s region.
8. Stationary is not added to local prompts.
9. Explicit left-to-right order influences region order.
10. A visible squirrel or other Prop is not suppressed by character-count negatives.

## Regression tests

Confirm that:

* existing reference resolution still works;
* preservation source resolution still works;
* dialogue output still works;
* reciprocal gaze deduplication still works;
* dependency manifest output is unchanged;
* render ask staging is unchanged;
* legacy markdown rendering is not broken.

---

# Regenerate the Example Artifacts

After implementation, regenerate the existing `V3-Test-Story / Test-Scene-01` example through the normal application entry point.

Regenerate and inspect:

* `Final_Image_Prompt.md`
* `Scene_Render_IR.json`
* `Scene_Render_Validation.json`
* `Local_Render_Brief.json`
* `Local_Render_Prompt.md`
* `Local_Render_Forge_Couple_Prompt.md`
* `Prompt_Source_Map.json`
* `dependency_manifest.json`
* render ask copies

Confirm that the pipeline and render-ask copies of `Final_Image_Prompt.md` match.

---

# Acceptance Criteria

The task is complete when all of the following are true:

1. A scene author can enter a Story Beat in Scene Builder.
2. Story Beat is preserved in scene JSON, IR, and final prompt.
3. A scene author can define an explicit focal point.
4. A scene author can order important elements from left to right.
5. The final prompt resolves ordered IDs to display names.
6. A Backdrop clearly defines the overall setting.
7. The Backdrop is not treated as an ordinary positioned subject.
8. A placement can be marked stationary or moving.
9. Moving elements can specify screen direction and a short visual cue.
10. Motion output is separate from pose and interactions.
11. Props and interactions use separate final-prompt sections.
12. Interaction notes are no longer discarded.
13. Local-render character count excludes props and Backdrops.
14. The local prompt does not use broad subject-count language that could suppress intended props.
15. Empty reference tags do not generate blank reference assignments.
16. New scenes and placements receive all required defaults.
17. Existing JSON render staging, source resolution, artifacts, and manual ask creation continue to work.
18. Automated tests cover normalization, validation, IR, final prompt, and local-render changes.
19. No unnecessary generalized composition or motion framework is introduced.

---

# Deliverable Summary

When finished, report:

1. Files changed.
2. Canonical data-model changes.
3. Scene Builder UI changes.
4. Compiler and IR changes.
5. Validation changes.
6. Local-render changes.
7. Tests added or updated.
8. Example artifacts regenerated.
9. Any assumptions or deviations from these instructions.
