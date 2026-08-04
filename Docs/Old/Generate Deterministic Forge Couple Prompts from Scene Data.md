# CODEX Task: Generate Deterministic Forge Couple Prompts from Scene Data

## Objective

Improve the local Stable Diffusion preview compiler so that Forge Couple configuration is generated deterministically from the structured scene data.

The compiler must use:

* scene elements;
* element types;
* placements;
* depth lanes;
* left-to-right order;
* focal point;
* motion;
* gaze targets;
* visual overrides;
* placement notes;
* backdrop assignments;

to create:

1. one whole-canvas background prompt;
2. one exclusive regional prompt per primary character;
3. deterministic Forge Couple Advanced-mode coordinate mappings;
4. a cleaner negative prompt appropriate to the number of primary characters.

The immediate success case is `Chapter-05.scene.json`, which should produce:

* two separate elf characters;
* Valindia on the left;
* Tsaeytte on the right;
* both walking away through the arch;
* the Spire archway covering the background;
* no blended or merged character identity.

Do not attempt to make the local render perfectly reproduce the final scene. The goal is a structurally useful preview that reflects the scene definition.

---

# Current Problem

The current local-render payload uses Forge Couple Basic mode with:

* one global first line;
* one Valindia line;
* one Tsaeytte line;
* an equal horizontal split.

The resulting image frequently contains:

* one merged elf;
* blended facial or costume features;
* weak background definition;
* inconsistent placement;
* contradictory staging.

The compiler currently flattens prose into regional prompts without building a spatial rendering plan.

Forge Couple should instead be treated as a spatial compilation target.

---

# Required Architectural Change

Add a deterministic intermediate representation for regional rendering.

Suggested name:

```text
ForgeCouplePlan
```

Suggested shape:

```json
{
  "mode": "Advanced",
  "subject_count": 2,
  "global_region": {
    "prompt": "...",
    "mapping": [0.0, 1.0, 0.0, 1.0, 0.65]
  },
  "character_regions": [
    {
      "scene_element_id": "Valindia_8844d004",
      "display_name": "Valindia",
      "order_index": 0,
      "horizontal_slot": "left",
      "depth": "midground",
      "is_focal": false,
      "prompt": "...",
      "mapping": [0.04, 0.47, 0.20, 0.98, 1.0]
    },
    {
      "scene_element_id": "Tsaeytte",
      "display_name": "Tsaeytte",
      "order_index": 1,
      "horizontal_slot": "right",
      "depth": "midground",
      "is_focal": true,
      "prompt": "...",
      "mapping": [0.53, 0.96, 0.20, 0.98, 1.08]
    }
  ]
}
```

Build this plan before generating the final API payload.

Do not construct Forge Couple prompt lines directly from raw scene prose.

---

# Input Data Sources

Use the existing scene JSON as the source of truth.

Relevant sections include:

```text
scene.story_beat
setup.canvas
setup.composition
setup.environment
scene_elements
placements
depth_lanes
interactions
dialogue
avoid
```

For `Chapter-05.scene.json`, the compiler should recognize:

```text
Primary characters:
- Valindia_8844d004
- Tsaeytte

Backdrop:
- Spire_Archway_efbf29cc

Left-to-right order:
- Valindia_8844d004
- Tsaeytte

Focal point:
- Tsaeytte

Character depth:
- midground

Backdrop depth:
- background

Shared motion:
- moving away from camera
```

---

# Primary Subject Classification

Count only primary renderable characters as subjects.

Include scene elements where:

```python
element_type == "Character"
```

and where the element has an associated placement.

Do not count the following as primary subjects:

* Backdrop elements;
* Place elements;
* environmental scenery;
* incidental background people;
* dialogue panels;
* architecture;
* props unless explicitly represented as independent foreground subjects.

For the Chapter 05 scene:

```text
primary_subject_count = 2
```

The arch must not be counted as a third subject.

---

# Backdrop Classification

Treat any scene element with:

```python
element_type == "Backdrop"
```

as a whole-canvas environmental element.

Backdrop content belongs only in the global prompt.

Do not create a separate character-style subject prompt for the backdrop.

Default backdrop mapping:

```json
[0.0, 1.0, 0.0, 1.0, 0.65]
```

The weight may be configurable, but use `0.65` as the initial default.

---

# Character Ordering

Resolve character order deterministically.

Use this priority:

1. `setup.composition.left_to_right`
2. explicit horizontal placement data
3. relational placement notes
4. original placement order
5. stable scene element order

Example:

```json
"left_to_right": [
  "Valindia_8844d004",
  "Tsaeytte"
]
```

This must result in:

```text
character region 1 = Valindia
character region 2 = Tsaeytte
```

Do not reorder characters based on display name, element ID, focal point, or source-file order when `left_to_right` is present.

Validate that every listed ID resolves to a Character scene element.

Ignore unresolved IDs with a warning rather than failing the entire render.

---

# Horizontal Placement Resolution

Normalize raw placement descriptions into regional slots.

Supported normalized slots:

```text
far_left
left
center_left
center
center_right
right
far_right
```

Use explicit `left_to_right` ordering as the main source.

Use `position_within_cell` only as refinement.

Use placement notes for relational corrections such as:

```text
Tsaeytte is walking to the right of Valindia.
```

For a two-character scene, normalize the final regional slots to:

```text
first character  -> left
second character -> right
```

Do not preserve the literal word `center` when it conflicts with explicit relative placement.

In Chapter 05:

```text
Valindia position_within_cell = left
Tsaeytte position_within_cell = center
placement note = Tsaeytte is to the right of Valindia
```

Required normalized result:

```text
Valindia = left
Tsaeytte = right
```

---

# Advanced Forge Couple Mode

Switch generated local-render payloads from Forge Couple Basic mode to Advanced mode whenever:

* there is at least one backdrop; and
* there are two or more primary characters.

Use Basic mode only as a fallback for extremely simple compositions where no backdrop or spatial data is available.

The generated script configuration should use:

```json
"alwayson_scripts": {
  "forge couple": {
    "args": [
      true,
      true,
      "Advanced",
      "",
      null,
      null,
      null,
      [
        [0.0, 1.0, 0.0, 1.0, 0.65],
        [0.04, 0.47, 0.20, 0.98, 1.0],
        [0.53, 0.96, 0.20, 0.98, 1.08]
      ],
      "{ }",
      false,
      true,
      null,
      null,
      null,
      null,
      null,
      null
    ]
  }
}
```

Preserve the existing API argument positions expected by the installed Forge Couple extension.

Do not change unrelated script arguments unless required by the current integration.

---

# Region Coordinate Templates

The scene schema currently does not provide exact normalized screen coordinates.

Use deterministic templates based on:

* primary character count;
* horizontal order;
* depth;
* canvas orientation;
* focal point.

## Two Characters, Portrait Canvas, Midground

Use:

```json
{
  "global": [0.0, 1.0, 0.0, 1.0, 0.65],
  "left": [0.04, 0.47, 0.20, 0.98, 1.0],
  "right": [0.53, 0.96, 0.20, 0.98, 1.0]
}
```

This intentional separation reduces fused bodies.

## Two Characters, Landscape Canvas, Midground

Use:

```json
{
  "global": [0.0, 1.0, 0.0, 1.0, 0.65],
  "left": [0.02, 0.49, 0.16, 0.98, 1.0],
  "right": [0.51, 0.98, 0.16, 0.98, 1.0]
}
```

## Focal Point Weight

If a character is the focal point, add:

```text
+0.08
```

to the regional weight.

Clamp character weights to a sensible range:

```text
0.8 to 1.2
```

For Chapter 05:

```text
Valindia weight = 1.0
Tsaeytte weight = 1.08
```

## Depth Adjustments

Apply deterministic vertical ranges:

```text
foreground: y1 = 0.05, y2 = 1.00
midground:  y1 = 0.20, y2 = 0.98
background: y1 = 0.30, y2 = 0.90
```

Do not assign primary character regions to background depth unless the scene data explicitly places them there.

---

# Global Prompt Construction

The first prompt line must describe the complete composition.

It must include:

* canvas orientation or aspect;
* number of primary characters;
* character separation;
* shared action;
* shared camera-facing direction;
* left-to-right placement;
* backdrop;
* location;
* depth;
* lighting;
* overall style;
* full-body requirement when appropriate.

Use compact visual language.

Do not put detailed character identity or costume descriptions in the global line.

Suggested deterministic format:

```text
[canvas description], exactly [N] separate primary characters,
[shared subject summary], [shared action], [shared view direction],
[ordered placement statement], [depth statement], [backdrop statement],
[lighting], [art style]
```

For Chapter 05, generate approximately:

```text
Portrait 4:5 fantasy scene, exactly two separate young elf women walking side
by side away from the camera through a monumental stone academy archway,
Valindia on the left and Tsaeytte on the right, both full-body midground figures
seen from rear three-quarter views, clear space between their bodies, the
archway spans the background and opens onto the campus grounds, morning
sunlight, painterly semi-realistic fantasy illustration.
```

The final wording does not need to match exactly, but it must preserve this structure.

---

# Shared Motion Synthesis

Inspect the primary character placements.

If all primary characters share:

```text
motion.state
motion.direction_screen
```

generate one shared global action.

Example:

```text
all state = moving
all direction = away from camera
```

Global result:

```text
walking side by side away from the camera
```

If motion differs between characters, do not force a shared action.

Instead use a neutral global statement such as:

```text
two separate characters occupying distinct positions
```

and preserve individual motion in regional prompts.

---

# Character Regional Prompt Construction

Each regional prompt must describe exactly one character.

Use this deterministic structure:

```text
Scene contains exactly [N] separate primary characters.
This region contains [DISPLAY NAME] only.
[horizontal position and depth].
[identity summary].
[view].
[action and motion].
[costume summary].
[prop state].
[expression or posture].
[gaze].
```

The phrases:

```text
This region contains [NAME] only.
```

and:

```text
Scene contains exactly [N] separate primary characters.
```

must appear near the beginning.

Do not begin every regional prompt with only:

```text
exactly two visible subjects
```

That wording is too ambiguous and may cause each region to attempt to generate both characters.

---

# Identity and Costume Content

Continue using the existing identity and costume resolution system.

Character descriptions should be loaded from:

* canonical character definitions;
* costume definitions;
* auxiliary person definitions;
* fallback visual descriptions.

Keep regional character descriptions concise.

Prefer:

```text
Tall elegant half-elf young woman, crimson-red jaw-length bob over black
underlayers, fair skin, pointed ears.
```

Avoid long personality prose or narrative interpretation.

Only include visually renderable traits.

Do not include:

* internal thoughts;
* biography;
* social status unless visually represented;
* narrative motivation;
* abstract personality descriptions that do not affect pose or expression.

---

# Visual Override Precedence

Use the following precedence for staging and appearance:

1. `scene_element.element_visual_override`
2. explicit pose fields
3. explicit motion fields
4. placement notes
5. interactions
6. story beat
7. canonical default visual description

However, do not copy contradictions directly.

Run the resolved values through deterministic compatibility rules.

---

# Contradiction Resolution

Add a normalization phase before prompt generation.

## Motion Versus Pose Summary

Example conflict:

```text
pose.summary = Standing
motion.state = moving
motion.direction_screen = away from camera
element_visual_override = walking next to Tsaeytte
```

Resolution rule:

```text
explicit walking override or moving state wins over generic standing wording
```

Normalize to:

```text
walking away
```

Strip conflicting `standing` wording.

## Arm Position Versus Held Prop

Example conflict:

```text
arms wrapped around herself
holding one of the books
```

Resolution rule:

When a closed arm posture and a held object conflict, combine them into:

```text
holding the object tightly against the torso
```

For Chapter 05:

```text
carrying one book tightly against her torso
```

Do not output both literal instructions.

## Rear View Versus Direct Eye Contact

Example:

```text
rear three-quarter view
walking away
looks directly at other character
```

Resolution rule:

For rear or rear-three-quarter views, convert:

```text
looks directly at
```

to:

```text
glances sideways toward
```

Do not force both faces to turn fully toward the camera.

## Age Contradictions

Never emit contradictory labels such as:

```text
adult character
adolescent high elf
```

Prefer the canonical character phase and identity definition.

For Tsaeytte Youth, emit:

```text
petite adolescent high elf
```

Do not prepend `adult character`.

---

# View Extraction

Derive character view from the strongest available source:

1. explicit element visual override;
2. placement notes;
3. selected reference image tag;
4. motion direction;
5. fallback neutral view.

Recognize normalized forms such as:

```text
front
back
left profile
right profile
front-left three-quarter
front-right three-quarter
back-left three-quarter
back-right three-quarter
```

For Chapter 05:

```text
Valindia = back-right three-quarter
Tsaeytte = back-left three-quarter
```

Use one consistent phrase per character.

Do not include conflicting front and rear views.

---

# Gaze Resolution

Use:

```text
pose.gaze_target_element_id
```

and interactions where relationship is:

```text
looking at
```

Resolve target IDs to display names.

Apply view-compatible wording.

Examples:

```text
front view:
looking toward Valindia

rear three-quarter moving view:
glancing sideways toward Valindia

back view:
head turned slightly toward Valindia
```

Do not emit `direct eye contact` when the selected views make it geometrically implausible.

---

# Prop Resolution

Use:

* pose summaries;
* arm actions;
* placement notes;
* props and states;
* element visual overrides.

Only include props directly associated with the character.

For Chapter 05:

```text
Valindia:
one book held tightly against torso

Tsaeytte:
stack of books held in front
```

Do not introduce extra books, bags, weapons, or jewelry beyond the canonical costume and explicit scene state.

---

# Incidental Background Characters

The scene includes:

```text
Other students coming and going.
```

This conflicts with strict subject-count prompting.

Add a local-preview setting:

```json
"strict_primary_subject_count": true
```

When enabled:

* omit incidental background people from the positive prompt;
* or reduce them to non-subject environmental suggestions only when safe.

Recommended initial behavior:

```text
Suppress incidental people entirely.
```

This produces a cleaner structural preview.

Later, an optional relaxed mode may use:

```text
tiny indistinct distant student silhouettes
```

Do not include the word `crowd`.

---

# Dialogue Handling

Do not attempt to render dialogue panels in the local Stable Diffusion preview.

Exclude:

* exact dialogue text;
* speech bubbles;
* caption instructions;
* pointer instructions.

Keep the following negative terms:

```text
text, letters, caption, speech bubble
```

The final scene renderer remains responsible for dialogue rendering.

---

# Negative Prompt Generation

Generate the negative prompt from the scene structure.

For a two-character scene, include:

```text
solo,
one person,
single person,
merged characters,
fused bodies,
blended faces,
hybrid character,
same character twice,
duplicate character,
overlapping bodies,
extra primary character,
third foreground person,
cropped body,
cropped feet,
extra limbs,
malformed hands,
looking at viewer,
front-facing body,
text,
letters,
caption,
speech bubble,
watermark
```

Do not include:

```text
extra people
crowd
```

when the scene intentionally allows distant background activity, unless strict subject-count mode suppresses background people.

Avoid overloading the negative prompt with semantic contradictions.

---

# Hires Fix Debug Behavior

Add a debug option:

```json
"forge_couple_debug_base_pass": true
```

When enabled:

```json
"enable_hr": false
```

Use base resolution only.

Recommended portrait debug size:

```json
"width": 640,
"height": 800
```

Recommended landscape debug size:

```json
"width": 896,
"height": 512
```

The purpose is to determine whether subject separation succeeds before Hires Fix.

The production preview may restore Hires Fix after successful validation.

---

# Prompt Line and Mapping Alignment

The number and order of prompt lines must exactly match the number and order of Advanced mappings.

For Chapter 05:

```text
line 1 = global backdrop and scene
line 2 = Valindia
line 3 = Tsaeytte
```

Mappings:

```text
mapping 1 = whole canvas
mapping 2 = left character
mapping 3 = right character
```

Add validation:

```python
assert len(prompt_lines) == len(mappings)
```

If the count differs:

* log a clear warning;
* fall back to a safe Basic-mode payload;
* do not silently send malformed Advanced configuration.

---

# Recommended Functions

Add or refactor toward functions similar to:

```python
def build_forge_couple_plan(scene, resolved_assets, settings):
    ...

def collect_primary_characters(scene):
    ...

def collect_backdrops(scene):
    ...

def resolve_character_order(scene, characters):
    ...

def normalize_horizontal_slots(scene, ordered_characters):
    ...

def resolve_character_staging(scene, element, placement):
    ...

def reconcile_staging_conflicts(staging):
    ...

def build_global_forge_prompt(scene, plan):
    ...

def build_character_region_prompt(scene, region):
    ...

def assign_advanced_region_mappings(scene, regions):
    ...

def build_forge_negative_prompt(scene, plan):
    ...

def build_forge_couple_api_args(plan):
    ...

def validate_forge_couple_plan(plan):
    ...
```

Use existing project naming conventions where appropriate.

---

# Suggested Pseudocode

```python
def build_forge_couple_plan(scene, resolved_assets, settings):
    placements = {
        item["scene_element_id"]: item
        for item in scene.get("placements", [])
    }

    elements = {
        item["id"]: item
        for item in scene.get("scene_elements", [])
    }

    characters = [
        element
        for element in elements.values()
        if element.get("element_type") == "Character"
        and element["id"] in placements
    ]

    backdrops = [
        element
        for element in elements.values()
        if element.get("element_type") == "Backdrop"
    ]

    ordered_characters = resolve_character_order(
        scene=scene,
        characters=characters,
        placements=placements,
    )

    slots = normalize_horizontal_slots(
        scene=scene,
        ordered_characters=ordered_characters,
        placements=placements,
    )

    subject_count = len(ordered_characters)
    focal_id = scene["setup"]["composition"].get("focal_point", "")

    regions = []

    for index, character in enumerate(ordered_characters):
        placement = placements[character["id"]]

        staging = resolve_character_staging(
            scene=scene,
            element=character,
            placement=placement,
            resolved_assets=resolved_assets,
        )

        staging = reconcile_staging_conflicts(staging)

        region = {
            "scene_element_id": character["id"],
            "display_name": character["display_name"],
            "order_index": index,
            "horizontal_slot": slots[character["id"]],
            "depth": placement.get("depth", "midground"),
            "is_focal": character["id"] == focal_id
                or character["display_name"] == focal_id,
            "staging": staging,
        }

        regions.append(region)

    mappings = assign_advanced_region_mappings(
        canvas=scene["setup"]["canvas"],
        regions=regions,
    )

    global_prompt = build_global_forge_prompt(
        scene=scene,
        characters=ordered_characters,
        backdrops=backdrops,
        regions=regions,
    )

    regional_prompts = [
        build_character_region_prompt(
            scene=scene,
            region=region,
            subject_count=subject_count,
        )
        for region in regions
    ]

    plan = {
        "mode": "Advanced",
        "subject_count": subject_count,
        "global_region": {
            "prompt": global_prompt,
            "mapping": mappings["global"],
        },
        "character_regions": [
            {
                **region,
                "prompt": prompt,
                "mapping": mappings["characters"][index],
            }
            for index, (region, prompt)
            in enumerate(zip(regions, regional_prompts))
        ],
    }

    validate_forge_couple_plan(plan)

    return plan
```

---

# Expected Chapter 05 Output

The compiled prompt should be structurally similar to:

```text
Portrait 4:5 fantasy scene, exactly two separate young elf women walking side
by side away from the camera through a monumental stone academy archway,
Valindia on the left and Tsaeytte on the right, both full-body midground figures
seen from rear three-quarter views, clear space between their bodies, the
archway spans the background and opens onto the campus grounds, morning
sunlight, painterly semi-realistic fantasy illustration.

Scene contains exactly two separate primary characters. This region contains
Valindia only, in the left midground. Tall elegant half-elf young woman with a
crimson-red jaw-length bob over black underlayers, fair skin, narrow violet
eyes, and pointed ears. Seen from the back-right three-quarter view, walking
away through the arch beside Tsaeytte. Tailored black academy clothing with
ornate gold embroidery, black stockings, and black heeled ankle boots. She
carries one book tightly against her torso and glances sideways toward Tsaeytte.

Scene contains exactly two separate primary characters. This region contains
Tsaeytte only, in the right midground. Petite adolescent high elf with a short
tousled black bob, woodland-green ribbon, fair skin, violet eyes, and pointed
ears. Seen from the back-left three-quarter view, walking away through the arch
beside Valindia. Light leaf-green blouse, dark forest-green ankle-length wool
skirt, broad brown belt, and sturdy brown lace-up boots. She carries a stack of
books and glances sideways toward Valindia.
```

Mappings:

```json
[
  [0.0, 1.0, 0.0, 1.0, 0.65],
  [0.04, 0.47, 0.20, 0.98, 1.0],
  [0.53, 0.96, 0.20, 0.98, 1.08]
]
```

---

# API Payload Requirements

Generate:

```json
"alwayson_scripts": {
  "forge couple": {
    "args": [
      true,
      true,
      "Advanced",
      "",
      null,
      null,
      null,
      "<GENERATED_MAPPINGS>",
      "{ }",
      false,
      true,
      null,
      null,
      null,
      null,
      null,
      null
    ]
  }
}
```

Replace `<GENERATED_MAPPINGS>` with the actual nested mapping array, not a serialized JSON string.

Preserve:

```json
"api_path": "/sdapi/v1/txt2img"
```

Do not include `denoising_strength` in a normal base txt2img payload unless another active feature specifically requires it.

---

# Logging and Diagnostics

Write a concise compiler diagnostic block to the local-render brief or log.

Example:

```text
Forge Couple mode: Advanced
Primary subjects: 2
Backdrop regions: 1
Character order:
  1. Valindia_8844d004 -> left
  2. Tsaeytte -> right
Focal region: Tsaeytte
Suppressed incidental background subjects: yes
Conflict corrections:
  - Valindia: standing -> walking
  - Valindia: wrapped arms + book -> book held against torso
  - Mutual direct gaze -> sideways glances
```

This diagnostic output is important because the final prompt is generated deterministically and users need to see how conflicting scene data was normalized.

---

# Tests

Add unit tests for the regional-plan generator.

## Test 1: Chapter 05 Character Count

Assert:

```text
subject_count == 2
```

## Test 2: Backdrop Exclusion

Assert:

```text
Spire_Archway_efbf29cc not in primary character regions
```

## Test 3: Character Order

Assert:

```text
regions[0].scene_element_id == Valindia_8844d004
regions[1].scene_element_id == Tsaeytte
```

## Test 4: Prompt Ownership

Assert Valindia prompt contains:

```text
This region contains Valindia only
```

Assert it does not contain Tsaeytte’s identity or costume description.

Assert Tsaeytte prompt contains:

```text
This region contains Tsaeytte only
```

Assert it does not contain Valindia’s identity or costume description.

Target names may appear only in relational phrases such as:

```text
glances sideways toward Tsaeytte
```

## Test 5: Mapping Count

Assert:

```text
len(prompt_lines) == len(mappings) == 3
```

## Test 6: Focal Weight

Assert:

```text
Tsaeytte regional weight > Valindia regional weight
```

## Test 7: Contradiction Resolution

Assert Valindia regional prompt:

* contains `walking`;
* does not contain `standing`;
* contains `book`;
* does not contain literal conflicting crossed-arm instructions.

## Test 8: View Compatibility

Assert rear-view regional prompts do not contain:

```text
looking directly at viewer
direct eye contact
front-facing
```

## Test 9: Dialogue Suppression

Assert the local render prompt does not contain:

```text
Maybe you should try not to be so
speech panel
pointer
```

## Test 10: Strict Background Suppression

When strict subject count is enabled, assert the prompt does not contain:

```text
other students
crowd
multiple students
```

---

# Acceptance Criteria

The task is complete when:

1. `Chapter-05.scene.json` compiles to Forge Couple Advanced mode.
2. The payload contains one whole-canvas mapping and two character mappings.
3. Valindia receives the left regional prompt.
4. Tsaeytte receives the right regional prompt.
5. The arch appears only in the global/background prompt.
6. Each character regional prompt explicitly owns one character only.
7. Character count is derived from scene elements rather than hard-coded.
8. The compiler resolves the known pose, motion, arm, and gaze contradictions.
9. Incidental background people are suppressed in strict preview mode.
10. Unit tests cover ordering, count, mappings, ownership, focal weighting, and conflict normalization.
11. Existing final-image prompt compilation remains unchanged.
12. Existing local-render outputs remain available, with only the Forge Couple generation path changed.

---

# Non-Goals

Do not:

* redesign the main scene JSON schema;
* require exact normalized coordinates in scene files;
* alter final-image prompt behavior;
* attempt reference-image identity transfer through Forge Couple;
* implement ControlNet or Regional Prompter;
* render dialogue locally;
* guarantee exact character likeness;
* add model-specific prompt syntax throughout the scene compiler;
* encode Chapter 05 character names directly into generic compiler logic.

The implementation must remain data-driven and work with other scenes.

---

# Optional Future Extension

The scene schema may later support optional explicit region overrides:

```json
"local_render_region": {
  "center_x": 0.30,
  "center_y": 0.62,
  "width": 0.38,
  "height": 0.72,
  "weight": 1.0
}
```

Do not require this field now.

The current task must infer usable regions from existing scene data and deterministic templates.
