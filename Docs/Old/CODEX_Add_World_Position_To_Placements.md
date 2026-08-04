# CODEX Instructions: Add `world_position` to Scene Placements

## Goal

Add an optional `world_position` field to each scene placement.

This field describes where an element is located within the fictional environment, independently of its camera-based placement.

Examples:

- `at the edge of the pit`
- `inside the doorway`
- `beside the laboratory table`
- `halfway down the stairs`
- `behind the wagon`
- `under the arch`

The existing placement fields continue to describe the element's position in the image:

- `position`: horizontal screen region, such as `left`, `center`, or `right`
- `depth`: camera depth, such as `foreground`, `midground`, or `background`

The new field must not replace or alter these existing fields.

---

## Conceptual Separation

Treat placement as three distinct concepts:

### Camera placement

Describes where the element appears in the rendered image.

```json
{
  "position": "center",
  "depth": "foreground"
}
```

Compiler output:

```text
Tsaeytte in the center foreground region.
```

### World position

Describes where the element exists within the scene environment.

```json
{
  "world_position": "at the edge of the pit"
}
```

Compiler output:

```text
World position: at the edge of the pit.
```

### Pose

Describes body position, orientation, gesture, or action.

```json
{
  "pose": "Looking straight down into the depths of the pit."
}
```

Compiler output:

```text
Pose: Looking straight down into the depths of the pit.
```

Do not treat `world_position` as pose text and do not merge it into the camera-placement fields in stored scene data.

---

## Schema Change

Add the following optional property to the placement block:

```json
{
  "world_position": "string"
}
```

Recommended placement shape:

```json
{
  "element_id": "tsaeytte",
  "position": "center",
  "depth": "foreground",
  "world_position": "at the edge of the pit",
  "pose": "Looking straight down into the depths of the pit."
}
```

Requirements:

- `world_position` is optional.
- Existing scene files without the field must remain valid.
- Empty strings and whitespace-only values should be treated as absent.
- Do not assign a default world position.
- Do not infer a world position from `position`, `depth`, or `pose`.
- Preserve the exact user-authored text except for trimming leading and trailing whitespace.
- Do not automatically add a preposition such as `at`, `in`, `beside`, or `near`.
- The stored value should be a short spatial phrase, not a full camera instruction.

---

## UI Change

Add an editable field to the Placement block:

```text
World Position
```

Suggested helper text:

```text
Location within the scene, such as "at the edge of the pit" or "inside the doorway."
```

Behavior:

- Leave blank when no world-relative location is needed.
- Save the value directly to `placements[].world_position`.
- Load and display the value when reopening a scene.
- Do not populate it from the pose field.
- Do not modify existing `position` and `depth` controls.

Place it near the existing placement controls, preferably in this order:

1. Position
2. Depth
3. World Position
4. Pose
5. Expression
6. Motion or interaction fields

---

## Final Image Prompt Emission

The current compiler emits placement direction in a form similar to:

```text
Element <pose> in the <position> <depth> region.
```

Update this logic so `world_position` is emitted as a separate world-space clause while preserving the existing camera-space direction.

### Required semantic order

Emit information in this order:

1. Element name
2. World position, when present
3. Pose
4. Camera placement

Recommended final form:

```text
<Element>: <world_position>. <pose> Place <Element> in the <position> <depth> region.
```

Example:

```text
Tsaeytte: At the edge of the pit. Looking straight down into its depths. Place Tsaeytte in the center foreground region.
```

This makes the distinction explicit:

- `at the edge of the pit` is world-space staging
- `looking straight down into its depths` is pose/action
- `center foreground region` is camera composition

---

## Interaction with Existing Camera Direction

The existing camera instruction must remain authoritative for screen placement:

```text
Place <Element> in the <position> <depth> region.
```

`world_position` must supplement this instruction, not replace it.

For example:

```json
{
  "position": "right",
  "depth": "background",
  "world_position": "inside the doorway",
  "pose": "Raising both hands in warning."
}
```

Emit:

```text
Rin: Inside the doorway. Raising both hands in warning. Place Rin in the right background region.
```

Do not emit:

```text
Rin inside the doorway background.
```

Do not emit:

```text
Rin in the right doorway.
```

Do not merge world-space and camera-space location into a single ambiguous phrase.

---

## Preferred Prompt Template

Use this structure for each element staging entry:

```text
- **<Element Name>:**
  World position: <world_position>.
  Pose: <pose>.
  Camera placement: <position> <depth>.
```

Example:

```text
- **Tsaeytte:**
  World position: at the edge of the pit.
  Pose: looking straight down into its depths.
  Camera placement: center foreground.
```

This labeled form is preferred when the final prompt already uses structured markdown sections.

If the compiler currently emits compact single-line staging, use:

```text
- **Tsaeytte:** At the edge of the pit. Looking straight down into its depths. Place Tsaeytte in the center foreground region.
```

Do not emit both the labeled and compact forms.

---

## Capitalization and Punctuation

Normalize only for prompt readability.

Rules:

- Trim leading and trailing whitespace.
- Preserve internal wording.
- Capitalize the first emitted character when practical.
- Add terminal punctuation when missing.
- Avoid doubled punctuation.
- Do not rewrite the phrase semantically.

Stored value:

```text
at the edge of the pit
```

Emitted value:

```text
At the edge of the pit.
```

Stored value:

```text
inside the doorway.
```

Emitted value:

```text
Inside the doorway.
```

---

## Conditional Emission

### World position and pose both present

Input:

```json
{
  "world_position": "at the edge of the pit",
  "pose": "Looking straight down into its depths.",
  "position": "center",
  "depth": "foreground"
}
```

Output:

```text
Tsaeytte: At the edge of the pit. Looking straight down into its depths. Place Tsaeytte in the center foreground region.
```

### World position present, pose absent

Input:

```json
{
  "world_position": "inside the doorway",
  "position": "right",
  "depth": "background"
}
```

Output:

```text
Rin: Inside the doorway. Place Rin in the right background region.
```

### Pose present, world position absent

Input:

```json
{
  "pose": "Raising both hands in warning.",
  "position": "right",
  "depth": "background"
}
```

Output:

```text
Rin: Raising both hands in warning. Place Rin in the right background region.
```

### Neither world position nor pose present

Input:

```json
{
  "position": "right",
  "depth": "background"
}
```

Output:

```text
Place Rin in the right background region.
```

### Camera placement incomplete

Preserve existing compiler behavior for missing `position` or `depth`.

Do not invent values.

Examples:

```text
Place Rin in the right region.
```

```text
Place Rin in the background region.
```

If the current compiler omits camera direction when either field is missing, retain that existing behavior rather than introducing a new policy as part of this change.

---

## Avoid Repetition

The compiler should avoid duplicate world-position statements when the same phrase also appears at the beginning of the pose.

Example input:

```json
{
  "world_position": "at the edge of the pit",
  "pose": "At the edge of the pit, looking straight down."
}
```

Preferred behavior:

- Do not attempt aggressive natural-language deduplication.
- Preserve both fields unless an exact normalized prefix match is detected.
- Optionally remove the duplicated exact prefix from the emitted pose.

Acceptable output:

```text
Tsaeytte: At the edge of the pit. Looking straight down. Place Tsaeytte in the center foreground region.
```

Do not add broad semantic rewriting in this change. Exact or near-exact prefix cleanup is sufficient.

---

## Backward Compatibility

Existing scene data such as:

```json
{
  "position": "center",
  "depth": "foreground",
  "pose": "At the edge of the pit. Looking straight down into its depths."
}
```

must continue to compile exactly as before.

Do not automatically migrate pose text into `world_position`.

A future migration tool may optionally separate known location phrases, but this task should not perform heuristic migration.

---

## Serialization

When saving a scene:

- Include `world_position` only when it contains non-whitespace text.
- Omit the property when blank.
- Preserve placement object ordering where practical.
- Recommended property order:

```json
{
  "element_id": "tsaeytte",
  "position": "center",
  "depth": "foreground",
  "world_position": "at the edge of the pit",
  "pose": "Looking straight down into its depths."
}
```

When loading:

- Missing field becomes an empty UI value.
- Unknown additional properties must remain unaffected.
- Existing files must not be rewritten merely because they were opened.

---

## Compiler Helper

Create or update a helper responsible for formatting one placement.

Suggested pseudocode:

```python
def format_placement(element_name, placement):
    world_position = normalize_sentence(placement.get("world_position"))
    pose = normalize_sentence(placement.get("pose"))
    camera = format_camera_region(
        element_name,
        placement.get("position"),
        placement.get("depth"),
    )

    parts = []

    if world_position:
        parts.append(world_position)

    if pose:
        parts.append(remove_exact_repeated_prefix(pose, world_position))

    if camera:
        parts.append(camera)

    if not parts:
        return None

    return f"- **{element_name}:** " + " ".join(parts)
```

Suggested camera formatter:

```python
def format_camera_region(element_name, position, depth):
    if position and depth:
        return f"Place {element_name} in the {position} {depth} region."
    if position:
        return f"Place {element_name} in the {position} region."
    if depth:
        return f"Place {element_name} in the {depth} region."
    return ""
```

Do not concatenate `world_position` directly between `position` and `depth`.

---

## Examples

### Tsaeytte

Scene data:

```json
{
  "element_id": "tsaeytte",
  "position": "center",
  "depth": "foreground",
  "world_position": "at the edge of the pit",
  "pose": "Looking straight down into its depths. Expression: excited."
}
```

Final prompt:

```text
- **Tsaeytte:** At the edge of the pit. Looking straight down into its depths. Expression: excited. Place Tsaeytte in the center foreground region.
```

### Freydis

Scene data:

```json
{
  "element_id": "freydis",
  "position": "right",
  "depth": "background",
  "world_position": "near the doorway in the far wall",
  "pose": "Looking directly at Tsaeytte. Expression: alarm."
}
```

Final prompt:

```text
- **Freydis:** Near the doorway in the far wall. Looking directly at Tsaeytte. Expression: alarm. Place Freydis in the right background region.
```

### Galen

Scene data:

```json
{
  "element_id": "galen",
  "position": "right",
  "depth": "background",
  "world_position": "beside Freydis near the doorway",
  "pose": "His free hand covers his forehead in exasperation."
}
```

Final prompt:

```text
- **Galen:** Beside Freydis near the doorway. His free hand covers his forehead in exasperation. Place Galen in the right background region.
```

### Environmental prop

Scene data:

```json
{
  "element_id": "utility-tusk",
  "position": "left",
  "depth": "foreground",
  "world_position": "on the stone floor behind Tsaeytte",
  "pose": "Its thick broken base drags along the floor while she holds the tapered end."
}
```

Final prompt:

```text
- **Utility Tusk:** On the stone floor behind Tsaeytte. Its thick broken base drags along the floor while she holds the tapered end. Place the Utility Tusk in the left foreground region.
```

---

## Tests

Add tests for schema, serialization, loading, and prompt compilation.

### Schema tests

- Placement accepts a valid string `world_position`.
- Placement accepts a missing `world_position`.
- Existing placement JSON remains valid.
- Blank `world_position` is treated as absent.

### Serialization tests

- Non-empty value is saved.
- Blank value is omitted.
- Loaded value round-trips without alteration other than outer whitespace trimming.

### Prompt compiler tests

#### Both fields present

Expected:

```text
Tsaeytte: At the edge of the pit. Looking straight down. Place Tsaeytte in the center foreground region.
```

#### Only world position present

Expected:

```text
Tsaeytte: At the edge of the pit. Place Tsaeytte in the center foreground region.
```

#### Only pose present

Expected:

```text
Tsaeytte: Looking straight down. Place Tsaeytte in the center foreground region.
```

#### Neither present

Expected:

```text
Place Tsaeytte in the center foreground region.
```

#### World position differs from camera position

Input:

```json
{
  "position": "left",
  "depth": "foreground",
  "world_position": "inside the doorway"
}
```

Expected:

```text
Tsaeytte: Inside the doorway. Place Tsaeytte in the left foreground region.
```

This test is important because it verifies that world-space and camera-space placement remain independent.

#### No merged location phrase

Assert that output does not contain forms such as:

```text
in the left doorway foreground
```

or:

```text
at the edge of the pit center foreground
```

---

## Acceptance Criteria

The change is complete when:

1. Placements support an optional `world_position` string.
2. The Scene Builder UI can edit and preserve it.
3. Existing scene files remain valid without migration.
4. The compiler emits world position separately from pose.
5. The compiler retains the existing `<position> <depth> region` camera direction.
6. World-space and camera-space placement are never merged into one phrase.
7. Blank values are omitted from saved JSON and final prompts.
8. Automated tests cover all combinations of world position, pose, position, and depth.
9. Existing prompt output remains unchanged for placements that do not use `world_position`.
