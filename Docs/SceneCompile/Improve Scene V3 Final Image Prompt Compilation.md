# CODEX Task: Improve Scene V3 Final Image Prompt Compilation

## Objective

Update the Scene V3 final-image-prompt compiler so it emits clear, compact, image-oriented instructions rather than serialized JSON data or internal editor identifiers.

The compiler must:

1. Use human-readable scene-element names.
2. label identity, costume, prop, and location descriptions by scene element.
3. translate grid placements into semantic screen positions.
4. omit empty or redundant fields.
5. render interactions as natural visual instructions.
6. use compact scene-specific preservation sections from resolved source templates when reference images are available.
7. keep internal JSON IDs out of the generated image prompt.

Do not change the Scene V3 JSON schema unless a change is specifically required below. This is primarily a compiler and prompt-formatting change.

---

## 1. Create a scene-element name resolver

Create one shared resolver used by every final-prompt section.

Suggested behavior:

```python
def get_element_display_name(
    element_id: str,
    elements_by_id: dict[str, SceneElement],
) -> str:
    element = elements_by_id.get(element_id)

    if element is None:
        return humanize_identifier(element_id)

    return (
        clean_optional_text(element.display_name)
        or clean_optional_text(element.character)
        or clean_optional_text(element.aux_resource_id)
        or humanize_identifier(element.id)
    )
```

All prompt-facing references must use this resolver.

Internal values such as:

```text
Valindia_38f52dd6
Spire_of_Celestial_Wisdom_82ad9430
placement_1784061167747
dialogue_1784000435085
```

must never appear in the final image prompt.

Internal IDs remain valid inside JSON, IR, logs, caches, and lookup operations.

---

## 2. Add a final prompt text-cleaning layer

Before adding any value to the prompt:

* trim whitespace;
* collapse repeated spaces;
* remove accidental duplicate terminal punctuation;
* omit blank strings;
* omit empty arrays;
* omit empty dictionaries;
* omit `null`;
* omit placeholder labels whose values are empty.

For example, do not emit:

```markdown
- Left-to-right order: .
- Foreground: .
- Background: .
- preserve ; ignore .
```

Do not emit a heading when the entire section would otherwise be empty.

Normalize punctuation so:

```text
In front of the archway..
```

becomes:

```text
In front of the archway.
```

Suggested helper:

```python
def clean_prompt_sentence(value: str | None) -> str:
    text = clean_optional_text(value)
    if not text:
        return ""

    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"[.]{2,}$", ".", text)
    return text
```

Do not remove intentional ellipses from dialogue text.

---

## 3. Separate internal IDs from prompt labels

Maintain both:

```python
element.id
element.display_name
```

Use `id` only for relationships and lookups.

Use `display_name` for:

* reference assignments;
* placement instructions;
* interactions;
* dialogue speakers;
* dialogue targets;
* preservation sections;
* focal points;
* left-to-right ordering;
* verification instructions.

The compiler must not attempt to humanize an ID when a valid `display_name` exists.

---

## 4. Improve reference-image assignment formatting

Every reference assignment must explicitly state which visible scene element it applies to.

Recommended output:

```markdown
- Tsaeytte — {{REFERENCE_TAG}}
  Use for Tsaeytte's identity, proportions, and Canonical Adventure Gear.
  Preserve her face, hair, ears, body proportions, costume design, and costume colors.
  Ignore the reference pose, expression, camera angle, framing, background, and lighting.
```

Do not produce:

```markdown
- {{REFERENCE_TAG}}: applies to Tsaeytte; preserve ; ignore .
```

### Default preservation rules by resource type

When explicit assignment instructions are absent, construct useful defaults.

#### Character with costume reference

Preserve:

```text
identity, facial features, hair, ears when applicable, body proportions,
costume design, costume colors, and signature worn items
```

Ignore:

```text
source pose, expression, action, camera angle, framing, background, and lighting
```

#### Character identity-only reference

Preserve:

```text
identity, facial features, hair, ears when applicable, and body proportions
```

Ignore:

```text
source costume unless explicitly assigned, pose, expression, action,
camera angle, framing, background, and lighting
```

#### Place or architectural reference

Preserve:

```text
architecture, structural design, identifying materials, and location-defining features
```

Ignore:

```text
source camera composition, framing, people, lighting, weather, and temporary objects
```

#### Prop reference

Preserve:

```text
shape, construction, materials, colors, scale, and identifying details
```

Ignore:

```text
source position, orientation, hand placement, framing, background, and lighting
```

Do not infer whether an asset is costume-based only from the filename. Prefer structured asset metadata when available. The current reference tag may be used as a fallback hint.

---

## 5. Support compact scene-preservation descriptions

The final scene prompt should not inject full technical Character Image Template descriptions when a suitable reference image is assigned.

For scene rendering, compact preservation text comes from bounded template sections already resolved by scene element `resource_type`.

```markdown
<!-- ZET:BEGIN IDENTITY_PRESERVATION_SCENE -->
Compact scene-oriented identity text.
<!-- ZET:END IDENTITY_PRESERVATION_SCENE -->

<!-- ZET:BEGIN IDENTITY_PRESERVATION_COSTUME_SCENE -->
Compact scene-oriented costume text.
<!-- ZET:END IDENTITY_PRESERVATION_COSTUME_SCENE -->
```

Do not add Scene V3 JSON fields for these descriptions unless a later task explicitly changes the schema.

Scene rendering should resolve source sections as follows:

* Character elements read `IDENTITY_PRESERVATION_SCENE` from `Character_Image_Template.md`.
* Character elements with a costume read `IDENTITY_PRESERVATION_COSTUME_SCENE` from the selected costume template.
* Auxiliary Person, Place, and Object resources may provide scene preservation through the same scene-specific bounded section mechanism.
* Non-scene render pipelines continue using their existing preservation section names.

Recommended precedence:

### Identity description

1. `scene_visual_override`, when supplied by the scene author.
2. `resolved_source_sections.identity_preservation_core`, populated from `IDENTITY_PRESERVATION_SCENE`.
3. `fallback_visual_description`.
4. no injected description when a strong identity reference is available and no description can be resolved.

### Costume description

1. scene-specific costume override, if supported.
2. `resolved_source_sections.identity_preservation_costume`, populated from `IDENTITY_PRESERVATION_COSTUME_SCENE`.
3. no injected costume description when a clear costume reference is available and no compact description can be resolved.

Do not inject the complete technical construction specification into normal narrative prompts by default.

The detailed description may still be used for:

* reference-image generation;
* turnaround sheets;
* costume fitment;
* validation;
* regeneration after identity drift;
* prompts without usable reference images.

---

## 6. Add the compact Tsaeytte descriptions

Store the following in the appropriate Tsaeytte Adult phase and costume templates without replacing the existing full technical descriptions.

### Adult `IDENTITY_PRESERVATION_SCENE`

Add this bounded section to Tsaeytte Adult `Character_Image_Template.md`:

```text
Petite young-adult high elf with a soft heart-shaped face, delicate pointed chin, fair skin, large expressive violet eyes, and long pointed ears. Her thick black hair forms a tousled chin-length bob with inward-curving ends framing both cheeks. Preserve her lithe, graceful build and recognizable facial identity from the reference image.
```

### Canonical Adventure Gear `IDENTITY_PRESERVATION_COSTUME_SCENE`

Add this bounded section to the Canonical Adventure Gear costume template:

```text
Teal off-shoulder ruffled crop top with short puff sleeves ending clearly above the elbows, exposed midriff, and a broad brown utility belt. Teal high-low skirt with a short open front, longer sides, and longest back, worn over visible dark navy leggings and tall brown heeled adventuring boots. Preserve her blue-violet pendant and earrings, teal-and-brown color palette, and elegant sorceress-adventurer silhouette.
```

These are scene-only preservation sections. Do not replace or delete the existing full technical descriptions used by other render pipelines.

---

## 7. Label preservation text by scene element and category

The compiler should render `resolved_source_sections.identity_preservation_core` and `resolved_source_sections.identity_preservation_costume` under a prompt-facing `Scene Element Preservation` heading.

Replace the current repeated format:

```markdown
- Tsaeytte: These rules should be included...
- Tsaeytte: * Costume name...
```

with:

```markdown
# Scene Element Preservation

## Tsaeytte

**Identity:** Petite young-adult high elf ...

**Costume — Canonical Adventure Gear:** Teal off-shoulder ...
```

For auxiliary people:

```markdown
## Valindia

**Identity:** Tall, elegant half-elf ...

**Costume:** Tailored black academy attire ...
```

For locations:

```markdown
## Spire of Celestial Wisdom Entrance Arch

**Location design:** Monumental ivy-covered Gothic stone arch ...
```

Only include categories that contain actual text.

---

## 8. Translate grid cells into semantic composition language

Do not expose editor phrases such as:

```text
cell 1,1 row 1 column 1
```

The planning grid is an authoring mechanism, not an image-generation concept.

Create a function that maps grid coordinates to semantic regions.

For a three-column, one-row grid:

```text
column 1 -> left
column 2 -> center
column 3 -> right
```

For two columns:

```text
column 1 -> left
column 2 -> right
```

For four or more columns, use normalized bands such as:

```text
far left
left of center
right of center
far right
```

For rows:

```text
one row -> no vertical qualifier
two rows -> upper / lower
three rows -> upper / middle / lower
```

Combine the semantic region with depth:

```text
left foreground
center background
right midground
upper-right background
```

Respect `position_within_cell` when it provides meaningful additional information.

Example:

```markdown
- Tsaeytte stands in the left foreground.
- Valindia stands in the right foreground.
- The Spire entrance arch occupies the center background.
```

---

## 9. Infer left-to-right order when the explicit array is empty

When:

```json
"left_to_right_order": []
```

derive the order from placements.

Sort visible placed elements by:

1. screen-cell column;
2. `position_within_cell`, when needed;
3. z-order only as a final deterministic tie-breaker.

For the supplied scene, infer:

```text
Tsaeytte → Spire of Celestial Wisdom → Valindia
```

Exclude elements that do not have a meaningful horizontal position.

If the explicit `left_to_right_order` array is populated, preserve the author's order and resolve each ID to its display name.

---

## 10. Render placement data as natural instructions

Replace semicolon-separated field dumps such as:

```text
Tsaeytte; Character primary; cell 1,1 row 1 column 1; foreground;
arms crossed; front-right 3/4; right profile; looking at another
character; angry.
```

with natural visual language:

```text
Tsaeytte stands in the left foreground, arms crossed. Her body is shown
in front-right three-quarter view, with her head turned into right
profile toward Valindia. She looks directly at Valindia with an angry
expression.
```

The compiler should identify the meaning of each view:

```text
body_view -> body is shown/facing...
head_view -> head is turned/shown...
gaze_target_element_id -> looks toward DISPLAY NAME
expression -> with a/an EXPRESSION expression
```

Do not render `gaze_description` as “looking at another character” when a valid `gaze_target_element_id` is available.

Use the target's display name instead.

If both body and head views are identical, combine them:

```text
Her body and head are shown in left profile.
```

If they differ, state them independently.

---

## 11. Deduplicate gaze and interaction instructions

The current scene contains gaze information in both:

* placement pose data;
* the interactions array.

Do not repeat the same instruction several times.

Normalize interactions into semantic records and deduplicate by:

```python
(
    subject_element_id,
    normalized_relationship,
    target_element_id,
)
```

Recognize reciprocal gaze:

```text
Tsaeytte looking at Valindia
Valindia looking at Tsaeytte
```

and compile it as:

```text
Tsaeytte and Valindia hold direct eye contact.
```

If the placement section already clearly establishes mutual eye contact, either:

* omit the separate interaction line; or
* retain one concise interaction sentence.

Do not output Python dictionary representations:

```text
{'subject_element_id': ..., ...}
```

---

## 12. Improve expression handling from dialogue tone

Do not silently override a character's explicit placement expression.

However, when the placement expression is blank and that character has dialogue with a tone, the compiler may use the tone as a secondary expression cue.

For this scene:

```json
"tone": "worried"
```

and Valindia's placement expression is blank.

The compiled staging may therefore say:

```text
Valindia looks worried.
```

Recommended precedence:

1. explicit placement expression;
2. explicit scene visual override;
3. dialogue tone;
4. no expression instruction.

Only convert tones that describe visible emotional presentation. Do not turn delivery instructions such as “quietly,” “formally,” or “sarcastically” directly into facial expressions without an explicit mapping.

---

## 13. Improve dialogue speaker and target resolution

Use display names in dialogue:

```markdown
- Valindia says exactly: “wait...”
```

Do not emit:

```markdown
- Valindia_38f52dd6: render exactly "wait...".
```

Keep the dialogue text verbatim, including capitalization and punctuation.

The dialogue panel instruction may state:

```text
Aim the pointer toward Valindia's mouth.
```

If a target exists, it may also state:

```text
Place the panel so the dialogue reads as directed toward Tsaeytte.
```

Internal target IDs must not appear.

---

## 14. Reduce duplication between reference and preservation sections

The reference section should explain:

* which image applies to which element;
* what visual information to preserve;
* what source-image properties to ignore.

The Scene Element Preservation section should provide only compact canonical descriptions that reinforce identity or design.

Do not repeat full costume specifications under both:

* Reference Image Assignment;
* Must Preserve.

Do not repeat global instructions such as “preserve recurring characters” for every character.

A suitable structure is:

```markdown
# Reference Image Assignment
# Camera and Composition
# Character and Location Staging
# Props and Interactions
# Environment and Depth
# Lighting and Mood
# Dialogue Panel
# Scene Element Preservation
# Avoid
# Final Verification
```

Rename `Must Preserve` to `Scene Element Preservation` if no downstream process depends on the old heading.

---

## 15. Use resource-type-aware nouns

Do not describe every placed item as a character or monster.

Generate staging groups or natural nouns based on `element_type` and `resource_type`:

```text
Character -> character
Monster -> creature or monster
Place/Anchor -> location anchor or architectural element
Prop -> prop
Effect -> visual effect
Vehicle -> vehicle
```

The Spire entrance arch should appear in a location or anchor instruction, not under `Character and Monster Staging`.

A combined heading such as `Character and Location Staging` is acceptable for small scenes.

---

## 16. Avoid redundant grid and depth data

The final prompt should express the resulting visual composition, not the source editor representation.

Do not include all of these simultaneously:

```text
cell 1,1
row 1
column 1
left foreground
depth foreground
```

Compile them into one phrase:

```text
left foreground
```

The Scene Render IR may retain the complete coordinates.

---

## 17. Normalize focal point names

Resolve `primary_focal_point` through the scene-element lookup when it contains an element ID.

Output:

```text
Primary focal point: Tsaeytte.
```

If it contains arbitrary author text rather than an element ID, preserve it as authored.

---

## 18. Improve environment sentence composition

Avoid separate empty fields.

Instead of:

```markdown
- Location: In front of the archway..
- Foreground: .
- Background: .
```

output:

```markdown
# Environment and Depth

The confrontation takes place in front of the Spire entrance arch. The two
women occupy the foreground, while the arch rises in the center background
with its upper structure clearly visible.
```

Only synthesize information directly supported by the scene data.

Do not invent landscaping, crowds, buildings, props, or weather effects beyond the supplied fields and resolved location description.

---

## 19. Expected output for the supplied scene

The important compiled portions should resemble:

```markdown
# Camera and Composition

- Landscape 16:9.
- Wide shot at eye level, straight-on, with a normal lens feel.
- Primary focal point: Tsaeytte.
- Left-to-right order: Tsaeytte → Spire of Celestial Wisdom entrance arch → Valindia.
- Render one continuous scene. Do not show the planning grid or divide the image into panels.

# Character and Location Staging

- Tsaeytte stands in the left foreground, arms crossed. Her body is shown in front-right three-quarter view, with her head turned into right profile toward Valindia. She looks directly at Valindia with an angry expression.
- Valindia stands in the right foreground facing Tsaeytte. Her body and head are shown in left profile. She raises one hand in warning, looks directly at Tsaeytte, and appears worried.
- The Spire entrance arch occupies the center background between and behind the two women. Keep the top of the arch visible.

# Interaction

Tsaeytte and Valindia hold direct eye contact across the space between them.

# Dialogue Panel

Valindia says exactly: “wait...”

Render the text inside a compact rectangular parchment dialogue panel with softly rounded corners, a warm ivory parchment background, subtle paper texture, and a thin dark bronze border. Use a short unobtrusive pointer aimed toward Valindia's mouth. Keep the panel only slightly larger than the text and do not obscure faces, hands, or important scene details.
```

Exact wording may differ, but the semantic behavior must match.

---

## 20. Tests

Add focused tests for the prompt compiler.

### Name resolution

Given an internal ID and a scene element with a display name:

```text
Valindia_38f52dd6 -> Valindia
```

Assert that the internal ID does not occur anywhere in the final prompt.

### Empty field omission

Given blank foreground notes, background notes, and left-to-right order:

* no empty bullet is emitted;
* no sentence ending in `: .` is emitted;
* no `preserve ; ignore .` text is emitted.

### Semantic placement

For a three-column grid:

```text
column 1 -> left
column 2 -> center
column 3 -> right
```

Assert that raw `cell`, `row`, and `column` labels are absent from the final prompt.

### Inferred order

Given placements in columns 1, 3, and 2, assert that the final order is sorted as 1, 2, 3.

### Interaction serialization

Assert that no output contains:

```text
{'subject_element_id'
```

or other Python/JSON dictionary syntax.

### Reciprocal gaze

Given reciprocal `looking at` interactions, assert that the output contains one mutual-eye-contact instruction rather than two raw relationship records.

### Dialogue

Assert that:

* the display name is used;
* dialogue text remains exactly `wait...`;
* the internal speaker ID is absent.

### Compact preservation prompts

When a reference image and `IDENTITY_PRESERVATION_SCENE` are both present:

* include the compact scene identity prompt;
* do not include the full technical Character Image Template identity rules.

When a costume reference and `IDENTITY_PRESERVATION_COSTUME_SCENE` are present:

* include the compact costume prompt;
* do not include the full technical costume specification.

### Punctuation normalization

Assert that:

```text
In front of the archway..
```

is compiled as:

```text
In front of the archway.
```

Do not modify dialogue ellipses.

---

## 21. Scope and compatibility

* Keep the Scene V3 JSON schema backward-compatible.
* Do not migrate existing scene files.
* Do not remove existing detailed identity or costume data.
* Restrict `IDENTITY_PRESERVATION_SCENE` and `IDENTITY_PRESERVATION_COSTUME_SCENE` usage to scene rendering.
* Do not alter local-render prompts unless they share the same faulty formatting helpers.
* Prefer shared formatting and name-resolution helpers so final-image and local-render compilers cannot diverge accidentally.
* Use diff-based changes rather than rewriting unrelated compiler modules.
* Add or update tests before considering the task complete.

---

## Questions

* Should scene rendering support old section names such as `SCENE_IDENTITY_PRESERVATION`, `SCENE_IDENTITY_PRESERVATION_CORE`, and `SCENE_IDENTITY_PRESERVATION_COSTUME` as temporary fallback aliases, or should templates be required to use only the new names?

Only new names. I believe I have already updated all the relevant templates in the library.

* For auxiliary Place/Object resources, should `IDENTITY_PRESERVATION_COSTUME_SCENE` be ignored unless the resource type is Person/Character-like?

Correct - costumes only apply to person/character elements, not objects and places.
