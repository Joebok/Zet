### Coordinate-system principle

Templates should express persistent character/costume facts in **anatomical coordinates**:

```text
anatomical left
anatomical right
```

The compiler should resolve those coordinates against the requested view and emit only **view-space directions** into the final image-generation prompt.

The generated prompt should generally avoid mixing anatomical and screen-relative left/right.

### Recommended generation vocabulary

Use a small controlled vocabulary:

```text
screen-left
screen-right
near side
far side
front/center
visible side
hidden side
partially visible
occluded
```

Prefer:

- `screen-left` / `screen-right` for literal horizontal placement in the rendered image.
- `near side` / `far side` for three-quarter and profile relationships.
- `visible side` / `hidden side` when visibility matters more than geometric side.
- `partially visible` / `occluded` when a feature crosses the silhouette or is only partly exposed.

Avoid leaving bare `left` or `right` in compiled spatial instructions.

### Compiler behavior

A template statement such as:

```text
Hair part is on anatomical right.
Hair mass is heavier on anatomical left.
```

might compile for `FRONT` as:

```text
The visible hair part line is on screen-left.
The heavier hair mass is on screen-right.
```

For a three-quarter view, the same canonical facts may be better expressed as:

```text
The visible hair part is on the near side.
The heavier hair mass falls toward the far side.
```

Or, where both concepts help:

```text
The visible hair part is on the near, screen-left side.
```

The important point is that the compiler performs the coordinate reasoning once. Qwen should not be asked to reconcile:

```text
screen-left (anatomical right)
```

unless this is specifically being emitted for debugging rather than generation.

### Do not implement this as simple text substitution

The translation should be semantic rather than a global replacement of `anatomical right` with some screen term.

The correct output depends on:

- requested body/head view;
- whether the feature is physically attached to a side;
- whether that side is near, far, visible, hidden, or partially visible;
- whether the instruction describes placement, asymmetry, orientation, or visibility.

For example:

```text
anatomical-right cheek
```

does not always translate to a particular screen side. In `RIGHT_PROFILE` it is the visible/near cheek. In `LEFT_PROFILE` it is the hidden/far cheek.

### Separate handling for fixed physical features

I would distinguish **directional geometry** from **side-bound physical identity** in the template representation.

Directional geometry includes things like:

```text
hair part
heavier hair mass
cape sweep
skirt opening
pose lean
object placement
```

These can usually be resolved directly into screen/near/far language.

Fixed physical features include:

```text
scar on anatomical right cheek
piercing in anatomical left ear
tattoo on anatomical right arm
mole beneath anatomical left eye
prosthetic anatomical left hand
```

These should retain their anatomical binding in the canonical data, because the side itself is part of the character's identity.

A useful representation would be conceptually:

```text
feature:
  type: scar
  anatomical_side: RIGHT
  location: cheek
```

rather than embedding everything into prose.

The compiler can then determine the feature's **view state**:

```text
VISIBLE_NEAR
VISIBLE_FAR
PARTIALLY_VISIBLE
OCCLUDED
HIDDEN
```

and generate appropriate prompt language.

For example:

```text
Template:
scar on anatomical right cheek
```

`FRONT`:

```text
A scar is visible on the screen-left cheek.
```

`RIGHT_PROFILE`:

```text
A scar is visible on the near-side cheek.
```

`LEFT_PROFILE`:

```text
The opposite-side cheek scar is hidden from view.
```

In many cases the last instruction should simply be omitted rather than telling the image model about an invisible feature.

### Suggested architectural separation

I would model the pipeline roughly as:

```text
CANONICAL TEMPLATE
    |
    | anatomical facts
    v
VIEW RESOLVER
    |
    | requested FRONT / FRONT_RIGHT_3_4 / etc.
    v
SPATIAL TRANSLATOR
    |
    | screen-left / screen-right / near / far
    | visibility state
    v
PROMPT RENDERER
    |
    v
QWEN PROMPT
```

For side-bound features, insert a feature-resolution step:

```text
Canonical feature
    ↓
Anatomical side
    ↓
Requested view
    ↓
Visibility + screen position
    ↓
Generated wording
```

### Useful distinction in the template schema

It may be worth giving directional statements an explicit semantic type rather than relying entirely on natural-language parsing:

```text
[spatial-asymmetry]
Hair part: anatomical-right
Hair mass: anatomical-left
```

versus:

```text
[fixed-feature]
Scar: anatomical-right cheek
```

That lets the compiler know that the first category should be **rephrased spatially**, while the second must preserve its physical anatomical identity before determining visibility.

### Linting rules

The compiled Qwen prompt could enforce several useful checks:

```text
No "anatomical left" or "anatomical right" remains after spatial translation.

No unqualified "left" or "right" appears in translated spatial instructions.

Every translated left/right term is one of:
screen-left
screen-right
near side
far side

Invisible fixed features are normally omitted rather than described.

Contradictory screen and near/far mappings are compilation errors.
```

One additional lint rule would be especially useful for your pipeline:

```text
A compiled spatial statement must not contain both anatomical and view-space coordinate systems.
```

That prevents output such as:

```text
screen-left (anatomical right)
```

from accidentally creeping back into production prompts.

The overall goal is: **templates describe what the character physically is; the compiler describes what the camera sees.** That separation should make the eight-view system considerably less fragile.

### Template annotation contract

Use a line-scoped annotation after any leading view tag. `asymmetry` marks directional geometry; `fixed` marks a feature physically attached to an anatomical side. A fixed feature must have explicit view eligibility from its line tag or a section-level `VIEW_DEFAULT`.

```markdown
* [head:frontish,near_right] <!-- ZET:SPATIAL fixed --> A scar is on the anatomical-right cheek.
* [head:far_right_3q] <!-- ZET:SPATIAL fixed state=partial --> A scar is on the anatomical-right cheek.
* <!-- ZET:SPATIAL asymmetry --> Hair mass is heavier on the anatomical-right side.
```

`state` defaults to `visible`; `partial` adds a partial-visibility instruction, while `occluded` and `hidden` omit the positive feature statement. Split facts into separate bullets when their visibility differs. Annotated clauses must use qualified `anatomical-left` or `anatomical-right`; bare left/right is an authoring error. Existing head/body domains determine which requested view applies.

| Requested view | Anatomical left resolves to | Anatomical right resolves to | Facing direction |
| --- | --- | --- | --- |
| `FRONT` | `screen-right` | `screen-left` | toward camera |
| `FRONT_LEFT_3_4` | `near-side` | `far-side` | screen-left |
| `FRONT_RIGHT_3_4` | `far-side` | `near-side` | screen-right |
| `LEFT_PROFILE` | `near-side` | `far-side` | screen-left |
| `RIGHT_PROFILE` | `far-side` | `near-side` | screen-right |
| `BACK_LEFT_3_4` | `near-side` | `far-side` | away, toward screen-left |
| `BACK_RIGHT_3_4` | `far-side` | `near-side` | away, toward screen-right |
| `BACK` | `screen-left` | `screen-right` | away from camera |
