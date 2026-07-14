# CODEX Task: Rework Scene V3 Local Render Prompt Compilation

## Objective

Change the Scene V3 local-render compiler so it produces a practical Stable Diffusion txt2img composition preview.

The local render is not intended to reproduce final character identity, canonical art style, exact dialogue, or finished-image quality. Its purpose is to determine whether the Scene Builder contains enough information to produce approximately correct:

* subject count;
* left/right placement;
* foreground/background placement;
* relative subject separation;
* facing direction;
* broad pose;
* dominant costume or appearance distinction;
* major location anchors.

Keep the final-image-prompt compiler separate from this work.

---

## 1. Remove story art style from local prompts

Do not include the inherited story art style in:

* `Local_Render_Brief.json`;
* `Local_Render_Prompt.md`;
* optional regional prompt outputs.

The selected checkpoint controls the visual style.

Do not include strings such as:

```text
Painterly semi-realistic fantasy illustration...
```

unless the user explicitly enters a local-render-specific style override.

Do not change the art-style handling of `Final_Image_Prompt.md`.

---

## 2. Treat local prompts as composition prompts

Do not shorten or condense the final image prompt.

Build the local prompt independently from the Scene Render IR.

Prioritize information in this order:

1. canvas and shot;
2. exact visible subject count;
3. overall composition;
4. major background anchors;
5. semantic screen position;
6. facing and gaze direction;
7. broad pose;
8. simple distinguishing appearance;
9. atmosphere;
10. negative layout constraints.

---

## 3. Do not emit editor terminology

The generated prompt must not contain:

```text
cell 1,1
row 1 column 1
Character primary
Anchor secondary
scene_element_id
placement ID
resource_type
importance
z_order
```

Translate editor data into visual language:

```text
column 1 of 3 -> far left or left side
column 2 of 3 -> center
column 3 of 3 -> far right or right side
foreground -> foreground
background -> background
```

Examples:

```text
left foreground
center background
right foreground
```

---

## 4. Infer horizontal ordering

When `composition.left_to_right_order` is empty, infer it from placement columns.

Sort visible placements by:

1. column;
2. `position_within_cell`;
3. deterministic tie-breaker.

For the supplied scene, infer:

```text
Tsaeytte -> Spire entrance arch -> Valindia
```

Use the inferred order both for the plain prompt and regional prompt construction.

Do not leave `left_to_right_order` as an empty protected fact.

---

## 5. Count visible subjects

Count visible character and monster placements where:

```text
must_be_visible == true
```

Do not count:

* places;
* anchors;
* environmental effects;
* props;
* dialogue panels.

Generate an explicit subject-count phrase:

```text
exactly two adult elf women
```

Use the actual resource types and resolved visual descriptions when possible.

The count should appear near the start of the prompt.

---

## 6. Replace proper names with visual descriptors

A generic checkpoint does not know what `Tsaeytte` or `Valindia` means.

Do not rely on character names in the positive prompt.

Names and internal IDs may remain in comments or machine-readable brief fields for traceability.

Generate a short local visual descriptor from resolved identity and costume information.

The local descriptor should normally contain only:

* species or broad subject type;
* approximate age category;
* build when visually useful;
* dominant hair color and shape;
* dominant costume colors and category;
* one signature visual item when important.

Examples:

```text
petite adult elf woman, black chin-length bob, teal off-shoulder adventuring outfit
```

```text
tall adult half-elf woman, crimson-red hair over black underlayers,
black-and-gold academy outfit
```

Do not include:

* identity-preservation language;
* jewelry unless compositionally important;
* exact garment construction;
* material lists;
* forbidden-drift lists;
* statements about matching reference images;
* full canonical character descriptions.

---

## 7. Add a deterministic local-descriptor reducer

Create a helper similar to:

```python
def build_local_visual_descriptor(element: RenderElement) -> str:
    """Return a short checkpoint-readable visual descriptor."""
```

Suggested precedence:

1. `local_render_visual_override`, if one is later added;
2. `scene_visual_override`;
3. compact resolved identity and costume descriptions;
4. `fallback_visual_description`;
5. generic resource-type descriptor.

The reducer should extract or retain:

* subject type;
* stature/build;
* hair;
* dominant outfit colors;
* outfit category;
* major signature item.

Target approximately 8–25 prompt terms per subject.

Do not pass the full preservation paragraphs directly into the local prompt.

---

## 8. Convert gaze relationships into screen direction

For local composition previews, screen direction is more useful than exact anatomical view terminology.

When a subject has a valid gaze target:

```python
if target.column > subject.column:
    facing = "facing screen-right"
    gaze = "looking toward the subject opposite"
elif target.column < subject.column:
    facing = "facing screen-left"
    gaze = "looking toward the subject opposite"
```

Use this to reinforce inward-facing interactions.

For the supplied scene:

```text
left character -> facing screen-right
right character -> facing screen-left
```

The explicit body and head views can remain available in the IR, but they should not override an obvious screen-facing relationship in the local preview prompt.

Do not emit vague phrases such as:

```text
looking at another character
```

---

## 9. Build a composition-first global clause

Generate a short global clause before individual subjects.

For the supplied scene, it should express concepts equivalent to:

```text
wide shot, landscape 16:9, exactly two adult elf women,
full bodies visible, separated confrontation composition,
monumental gothic entrance arch centered in the background,
open empty space in the center foreground
```

Important composition concepts may be mildly repeated in the individual subject clauses.

This repetition is acceptable because layout reliability is more important than prose elegance.

---

## 10. Describe anchors as scenery

Do not emit:

```text
Spire of Celestial Wisdom; Anchor secondary
```

Instead generate:

```text
monumental gothic stone entrance arch centered in the background,
top of arch visible
```

Use:

* semantic horizontal region;
* depth;
* resolved compact place description;
* visible requirements;
* placement notes.

When a center-background anchor shares a column with no foreground character, explicitly describe the center foreground as open or empty.

Do not invent an empty region when a visible foreground element occupies it.

---

## 11. Simplify pose instructions

Include broad, checkpoint-readable actions:

```text
arms crossed
one hand raised in warning
standing
kneeling
running
```

Avoid technical prose or left/right anatomical details unless they are essential to the layout.

Expression may be included as a single term:

```text
angry
worried
smiling
```

When the placement expression is blank and a dialogue tone expresses a visible emotion, the local compiler may use the dialogue tone even when dialogue text itself is excluded.

For the supplied scene, Valindia may be described as `worried`.

---

## 12. Keep dialogue excluded by default

Respect:

```json
"include_in_local_render": false
```

Do not include:

* dialogue text;
* dialogue panels;
* speech bubbles;
* panel style;
* lettering;
* pointer instructions.

Continue adding these terms to the negative prompt:

```text
text, letters, caption, speech bubble, watermark
```

---

## 13. Rework the negative prompt

Remove local negatives that depend on canonical identity, such as:

```text
inconsistent character identity
wrong costume
```

The local preview cannot reliably validate those properties.

Add composition-related negatives:

```text
extra people
third person
crowd
duplicate character
same character twice
merged characters
fused bodies
overlapping characters
characters touching
both characters on the same side
person in the center foreground
centered foreground character
cropped body
cropped feet
back turned toward the other character
looking at viewer
```

Retain useful anatomy and text negatives:

```text
extra limbs
malformed hands
text
letters
caption
speech bubble
watermark
```

Deduplicate all negative terms while preserving stable ordering.

---

## 14. Redesign `Local_Render_Brief.json`

Add:

```json
{
  "schema_version": 2,
  "purpose": "composition_preview",
  "include_dialogue": false,
  "subject_count": 2,
  "canvas": {},
  "global_prompt": "",
  "regions": [],
  "plain_txt2img": {
    "prompt": "",
    "negative_prompt": ""
  },
  "forge_couple_basic": {
    "direction": "Horizontal",
    "background": "First Line",
    "background_weight": 0.5,
    "separator": "\\n",
    "prompt_lines": []
  }
}
```

Each region should contain:

```json
{
  "region": "left",
  "row": 1,
  "column": 1,
  "x_range": [0.0, 0.3333],
  "y_range": [0.0, 1.0],
  "depths": ["foreground"],
  "element_ids": ["Tsaeytte"],
  "prompt": "..."
}
```

Internal element IDs are permitted in this JSON because they are lookup and traceability data.

They must not appear in generated positive or negative prompt strings.

---

## 15. Preserve the existing plain prompt format

Continue generating `Local_Render_Prompt.md` with exactly:

```text
prompt: ...
negative: ...
```

Do not add regional metadata to this file if an existing parser expects the two-field format.

Generate the improved ordinary txt2img prompt here.

This file must remain usable without any WebUI extension.

---

## 16. Add Forge Couple output

Forge Couple is installed and enabled.

Regional rendering is an environment/backend capability, not story content.

Add an application or local-render profile setting:

```text
local_layout_backend:
    plain_txt2img
    forge_couple_basic
```

Default:

```text
plain_txt2img
```

When `forge_couple_basic` is enabled, optionally generate:

```text
Local_Render_Forge_Couple_Prompt.md
```

Suggested format:

```text
mode: Basic
direction: Horizontal
background: First Line
background_weight: 0.5
separator: newline

prompt:
<global line>
<column 1 line>
<column 2 line>
<column 3 line>

negative:
<negative prompt>
```

Do not initially implement:

* Forge Couple Advanced mode;
* masks;
* ControlNet;
* regional LoRAs;
* automatic pose-image generation;
* Regional Prompter support.

Keep normalized region rectangles in `Local_Render_Brief.json` so Advanced mode can be added later without changing scene data.

---

## 17. Forge Couple Basic line generation

For a horizontal Scene Builder grid:

1. Produce one global line.
2. Produce one regional line per column, ordered left to right.
3. Set Forge Couple direction to `Horizontal`.
4. Set global effect to `First Line`.
5. Use newline as the separator.
6. Never add a trailing empty line.

For each regional line:

* repeat the total subject count;
* identify what belongs in that region;
* describe screen-facing direction;
* describe whether foreground should remain empty;
* describe major background elements.

Example structure:

```text
GLOBAL
LEFT COLUMN
CENTER COLUMN
RIGHT COLUMN
```

For a vertical-only composition, rows may later map to `Vertical`.

For multi-row and multi-column grids, continue using the plain prompt until a later 2D regional implementation is added.

---

## 18. Expected plain prompt for the supplied scene

The generated positive prompt should be semantically equivalent to:

```text
wide shot, landscape 16:9, exactly two adult elf women,
full bodies visible, separated confrontation composition,
monumental gothic stone entrance arch centered in the background,
open empty space in the center foreground,
left woman positioned on the far left,
petite elf woman with a black chin-length bob and teal off-shoulder
adventuring outfit, arms crossed, angry, facing screen-right,
looking toward the woman opposite her,
right woman positioned on the far right,
tall half-elf woman with crimson-red and black jaw-length hair and
a black-and-gold academy outfit, one hand raised in warning, worried,
facing screen-left, looking toward the woman opposite her,
evening dusk, partly cloudy
```

Exact punctuation may differ.

---

## 19. Tests

Add tests covering:

### Style omission

Assert that the inherited story art-style string is absent from the local brief and prompt.

### Internal terminology omission

Assert that the prompt does not contain:

```text
cell
row 1 column
Character primary
Anchor secondary
scene_element_id
```

### Subject count

Assert that the prompt contains the equivalent of:

```text
exactly two adult elf women
```

### Inferred ordering

Given placements in columns 1, 2, and 3, assert:

* Tsaeytte compiles to the left clause;
* the Spire arch compiles to the center-background clause;
* Valindia compiles to the right clause.

### Screen-facing direction

Given reciprocal gaze across columns:

* left subject compiles as facing screen-right;
* right subject compiles as facing screen-left.

### Anchor handling

Assert that the Spire is described as architecture or scenery and not as an `Anchor secondary`.

### Proper-name independence

Assert that the final local positive prompt remains meaningful after proper names are removed.

Names may remain in JSON traceability fields.

### Dialogue omission

Assert that:

```text
wait...
```

does not appear in the local prompt.

### Regional line count

For a three-column scene using Forge Couple Basic mode:

* one global line is emitted;
* three regional lines are emitted;
* no trailing empty line is emitted.

### Negative prompt

Assert that layout-failure terms are present and identity-preservation terms are absent.

---

## 20. Scope

Keep this implementation intentionally small.

Implement:

* improved plain txt2img prompt;
* revised structured local brief;
* Forge Couple Basic prompt generation;
* tests.

Do not implement a full regional-rendering engine or ControlNet workflow at this stage.
