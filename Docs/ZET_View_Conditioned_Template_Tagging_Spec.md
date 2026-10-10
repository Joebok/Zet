# ZET View-Conditioned Template Tagging Specification

## Purpose

This specification defines a view-conditioning system for ZET character and costume templates.

The goal is to prevent image-generation prompts from including visually irrelevant or contradictory information for the requested camera-relative view. In particular, it addresses a recurring failure mode in which detailed front-facing descriptions of the face, costume, jewelry, or garment construction remain present in prompts for rear-oriented views and encourage the image generator to rotate the subject toward the viewer.

The central principle is:

> A compiled prompt should contain canonical information only when that information is visually relevant to the requested view, plus explicit view-specific guidance for what should be visible.

The tagging system does **not** change canon. It controls **prompt emission**.

A fact can remain canonically true while being intentionally omitted from a prompt for a view in which it should not be visible.

---

# 1. Supported Views

ZET uses eight canonical body/head view identifiers.

| Short Tag | Canonical Name | Meaning |
|---|---|---|
| `f` | `FRONT` | Subject faces directly toward the camera. |
| `fl` | `FRONT_LEFT_3_4` | Subject's anatomical left side is nearer the camera; mostly front-facing. |
| `pl` | `LEFT_PROFILE` | Subject's anatomical left side faces the camera. |
| `bl` | `BACK_LEFT_3_4` | Subject's anatomical left side is nearer the camera; mostly back-facing. |
| `b` | `BACK` | Subject faces directly away from the camera. |
| `br` | `BACK_RIGHT_3_4` | Subject's anatomical right side is nearer the camera; mostly back-facing. |
| `pr` | `RIGHT_PROFILE` | Subject's anatomical right side faces the camera. |
| `fr` | `FRONT_RIGHT_3_4` | Subject's anatomical right side is nearer the camera; mostly front-facing. |

`LEFT` and `RIGHT` always refer to the **subject's anatomical left and right**, never image-left or image-right.

These view identifiers are valid for both body-view and head-view conditioning.

---

# 2. Basic Line Tag Syntax

A template bullet may optionally begin with a view tag expression.

```md
* [f] Both eyes are visible.
* [fl,fr] The far eye remains visible.
* [b,bl,br] The rear hair silhouette is clearly readable.
* Ears are long and pointed.
```

An untagged line is emitted for **all views**.

Equivalent explicit form:

```md
* [all] Ears are long and pointed.
```

The recommended syntax uses comma-separated tokens.

```md
[fl,fr]
```

Do **not** use concatenated strings such as:

```md
[fflfrprpl]
```

Although mechanically parseable, concatenated tags are difficult to audit and become ambiguous as the tagging language grows.

---

# 3. Core Semantics

Tags describe **prompt visibility**, not canonical truth.

Example:

```md
* [face_visible] Eye color: vivid violet-purple with white sclera.
```

This means:

> Emit this line only when the requested view is expected to visibly depict the eyes.

It does **not** mean:

> The character only has violet eyes in those views.

The source template remains the canonical authority. The compiler creates a view-conditioned projection of that canon.

---

# 4. Built-In View Groups

The compiler SHOULD support named group aliases in addition to individual view identifiers.

## 4.1 Primary Groups

| Group | Expands To | Intended Use |
|---|---|---|
| `all` | `f,fl,pl,bl,b,br,pr,fr` | Visible or relevant in every orientation. |
| `frontish` | `f,fl,fr` | Primarily front-facing views. |
| `rearish` | `b,bl,br` | Primarily rear-facing views. |
| `profiles` | `pl,pr` | Exact side profiles. |
| `front_3q` | `fl,fr` | Front three-quarter views. |
| `back_3q` | `bl,br` | Rear three-quarter views. |
| `three_quarter` | `fl,fr,bl,br` | Any three-quarter orientation. |

## 4.2 Side Groups

| Group | Expands To |
|---|---|
| `leftish` | `fl,pl,bl` |
| `rightish` | `fr,pr,br` |
| `left_side` | `fl,pl,bl` |
| `right_side` | `fr,pr,br` |

`leftish/rightish` and `left_side/right_side` are semantic aliases. A project SHOULD choose one naming convention and use it consistently.

Recommended project convention: `leftish` and `rightish`.

## 4.3 Visibility Groups

These groups describe common visual-information classes.

| Group | Expands To | Typical Content |
|---|---|---|
| `face_visible` | `f,fl,fr,pl,pr` | Face shape, eyes, eyebrows, nose, mouth. |
| `both_eyes_visible` | `f,fl,fr` | Eye color/spacing when both eyes matter. |
| `single_side_face` | `pl,pr` | Nose-lip-chin profile, one eye/eyelash edge. |
| `rear_head_visible` | `b,bl,br` | Nape, rear skull, rear hair mass. |
| `near_ear_visible` | `fl,pl,bl,fr,pr,br` | Near-side ear detail. |
| `front_torso_visible` | `f,fl,fr,pl,pr` | Neckline, chest panel, front closures. |
| `rear_torso_visible` | `b,bl,br,pl,pr` | Back closure, rear straps, cape attachment. |
| `front_costume_visible` | `f,fl,fr` | Front-biased costume geometry. |
| `rear_costume_visible` | `b,bl,br` | Rear-biased costume geometry. |

Visibility groups are conveniences, not substitutes for judgment. A template author may use individual views when a feature is unusually view-dependent.

---

# 5. Tag Expressions

## 5.1 Inclusion

A line is emitted if the requested view matches **any** token in the tag expression.

```md
* [f,front_3q] Pendant hangs centered at the upper chest.
```

Equivalent expansion:

```md
* [f,fl,fr] Pendant hangs centered at the upper chest.
```

## 5.2 Exclusion

The compiler SHOULD support exclusion tokens prefixed with `!`.

```md
* [all,!b] The ear shape remains readable.
```

This means all views except direct back.

Another example:

```md
* [rearish,!b] A small cheek edge may be visible if anatomically consistent.
```

Equivalent to:

```md
* [bl,br] A small cheek edge may be visible if anatomically consistent.
```

Exclusions are evaluated after inclusions.

## 5.3 Empty Match

If a tag expression resolves to zero views, the compiler SHOULD report a validation warning or error.

Example:

```md
* [b,!b] Invalid line.
```

---

# 6. Recommended Tag Normalization

The compiler SHOULD normalize tag expressions before matching.

Normalization should:

1. trim whitespace;
2. convert tag identifiers to lowercase;
3. resolve aliases;
4. remove duplicates;
5. apply exclusions;
6. compare against the canonical requested view.

These should be equivalent:

```md
[ FL , FR ]
[fl,fr]
[front_3q]
```

---

# 7. Section Defaults

Line-by-line tagging can become noisy. Sections MAY declare a default visibility expression.

Recommended directive:

```md
<!-- ZET:VIEW_DEFAULT face_visible -->
```

Example:

```md
## Face Description

<!-- ZET:VIEW_DEFAULT face_visible -->

* Face shape: soft heart-shaped face with delicate elven structure.
* Jaw/chin: small refined jaw and gentle pointed chin.
* Eye shape: large anime-influenced almond eyes.
* Eye color: vivid violet-purple.

* [all] Skin: light warm golden-beige with warm peach-gold undertones.
```

In this example:

- untagged lines inherit `face_visible`;
- `[all]` overrides the section default.

A new `VIEW_DEFAULT` directive remains active until:

1. another `VIEW_DEFAULT` directive replaces it; or
2. the current compiler-defined structural section ends.

The implementation SHOULD prefer structural section scoping rather than open-ended file-wide state.

---

# 8. Explicit Reset to Global Inclusion

When a section default is active, `[all]` means exactly all eight views.

Example:

```md
<!-- ZET:VIEW_DEFAULT face_visible -->

* Eye color: vivid violet-purple.
* [all] Skin tone: light warm golden-beige.
```

Do not use an empty tag such as `[]` to mean global inclusion.

---

# 9. Canonical Facts Versus Promptable Facts

Templates MAY contain information retained for documentation but never directly emitted into image-generation prompts.

Recommended directive:

```md
<!-- ZET:CANON_ONLY -->
```

Example:

```md
<!-- ZET:CANON_ONLY -->
* Her eyes are violet-purple and are one of her strongest identity anchors.
```

`CANON_ONLY` content remains available to template tooling, editors, or reference documentation but is excluded from normal compiled generation prompts.

A section or line may alternatively use:

```md
[canon_only]
```

but directive-based use is preferred because `canon_only` is not a view.

Recommended rule:

> View tags determine **where promptable information is emitted**. `CANON_ONLY` determines **whether information is promptable at all**.

---

# 10. View-Specific Override Blocks

Existing view-specific description blocks remain useful and SHOULD be retained.

Recommended form:

```md
<!-- ZET:BEGIN HEAD_VIEW_OVERRIDES -->

* [f] Front view head should show both large violet eyes, the heart-shaped face, small chin, delicate nose, and partial pointed-ear visibility.
* [fl] Front-left 3/4 should strongly show the left cheek and left ear while keeping the far eye visible.
* [fr] Front-right 3/4 should strongly show the right cheek and right ear while keeping the far eye visible.
* [pl] Left profile should show the nose-to-lips-to-chin line, one eye or eyelash edge, and a clearly pointed left ear.
* [pr] Right profile should show the nose-to-lips-to-chin line, one eye or eyelash edge, and a clearly pointed right ear.
* [bl] Back-left 3/4 should emphasize the rear bob mass, nape, and left ear; only a minimal cheek or jaw hint may appear if consistent with the requested rotation.
* [br] Back-right 3/4 should emphasize the rear bob mass, nape, and right ear; only a minimal cheek or jaw hint may appear if consistent with the requested rotation.
* [b] Back view should show the compact rear skull and bob silhouette at the nape; the face and eyes are not visible.

<!-- ZET:END HEAD_VIEW_OVERRIDES -->
```

These lines are positive rendering instructions, not replacements for general tagged facts.

---

# 11. View-Specific Suppression Rules

Rear and profile views often require explicit suppression of front-view bias.

The compiler SHOULD support a project-level or template-level suppression section.

Example:

```md
<!-- ZET:BEGIN VIEW_SUPPRESSION -->

* [b] Do not turn the head toward the viewer. Do not reveal the face or eyes.
* [bl,br] Keep the head primarily rear-facing. Do not rotate far enough to become a front three-quarter view.
* [pl,pr] Maintain a true side profile. Do not rotate toward a front three-quarter presentation.

<!-- ZET:END VIEW_SUPPRESSION -->
```

These lines should normally be emitted **after** descriptive facts and view-specific positive guidance.

Recommended compiled ordering:

1. global identity / construction facts;
2. view-relevant section facts;
3. view-specific positive overrides;
4. view-specific suppression rules.

This gives the model a positive target before stating anti-drift constraints.

---

# 12. Rear-View Prompt Hygiene

Rear-oriented prompts require stricter filtering than front views.

For `b`, `bl`, and `br`, the compiler SHOULD aggressively omit:

- eye color;
- eye shape;
- eyebrow shape;
- front-facing facial expression;
- detailed nose shape unless a rear three-quarter view genuinely exposes part of the profile;
- mouth/lip detail unless naturally visible;
- front neckline geometry;
- chest-centered jewelry positioning;
- front belt buckles;
- front skirt openings;
- front embroidery placement;
- other front-only costume details.

Rear prompts SHOULD positively emphasize:

- rear skull shape;
- nape;
- rear hair mass;
- near-side ear and any intentionally visible far-side ear tip;
- neck attachment;
- shoulder line;
- rear garment construction;
- back closures;
- rear straps;
- cape attachment;
- rear belt treatment;
- rear overskirt or coat fall;
- rear embroidery or trim;
- silhouette.

Omission alone is not sufficient. Rear views should receive strong rear-positive content.

---

# 13. Avoiding Semantically Front-Biased Wording

Some apparently global statements contain words that can accidentally encourage front-facing imagery.

Example to avoid in all-view text:

```md
* Head-to-body proportion: slightly stylized large-eyed fantasy proportions.
```

For a direct back view, `large-eyed` is irrelevant visual information and may encourage the engine to reveal the face.

Preferred view-neutral wording:

```md
* Head-to-body proportion: slightly stylized fantasy proportions with a modestly enlarged head scale relative to realistic anatomy, while remaining adult and semi-realistic.
```

Template authors SHOULD audit globally emitted text for:

- `eye`;
- `gaze`;
- `smile`;
- `lips`;
- `nose`;
- `brow`;
- `chest`;
- `neckline`;
- `buckle`;
- `pendant`;
- `front`;
- other strongly directional feature terms.

Such words are not forbidden, but global use should be intentional.

---

# 14. Costume-Specific Guidance

Costume templates are especially likely to contain front-biased semantic information.

Every costume feature SHOULD be classified mentally as one of:

1. **all-around construction**
2. **front-biased**
3. **rear-biased**
4. **side-biased**
5. **view-specific**

## 14.1 All-Around Examples

Typically safe as untagged or `[all]`:

- base fabric color;
- material;
- sleeve length;
- overall skirt length;
- boot height;
- general trim language;
- overall silhouette;
- garment layer count when visible from all directions.

## 14.2 Front-Biased Examples

Usually tagged `[frontish]`, `front_torso_visible`, or explicit view lists:

- neckline shape;
- chest panel;
- pendant placement;
- front belt buckle;
- front buttons;
- front skirt opening;
- front apron;
- front embroidery;
- exposed midriff wording tied to front garment geometry.

## 14.3 Rear-Biased Examples

Usually tagged `[rearish]` or `rear_costume_visible`:

- rear closure;
- back seam;
- cape attachment;
- rear straps;
- rear lacing;
- back embroidery;
- train;
- rear split;
- rear panel overlap.

## 14.4 Side-Biased Examples

Usually tagged `[leftish]`, `[rightish]`, `[profiles]`, or explicit views:

- hip-mounted weapons;
- side pouches;
- asymmetrical drape;
- single-side ornament;
- rapier scabbard;
- one-sided slit.

---

# 15. Near-Side and Far-Side Feature Rules

Three-quarter views frequently require explicit near-side/far-side handling.

For a view:

- `fl`: anatomical left is near side; right is far side.
- `fr`: anatomical right is near side; left is far side.
- `bl`: anatomical left is near side; right is far side.
- `br`: anatomical right is near side; left is far side.

The compiler MAY expose semantic aliases:

| Alias | Relevant Views |
|---|---|
| `near_left` | `fl,pl,bl` |
| `near_right` | `fr,pr,br` |
| `far_left_3q` | `fr,br` |
| `far_right_3q` | `fl,bl` |

However, these aliases are optional. Explicit per-view overrides are generally clearer for identity-critical details such as ears.

Recommended practice:

```md
* [fl] Left ear is strongly visible; right ear tip may remain visible beyond the far side of the head if anatomically plausible.
* [bl] Left ear is the primary visible ear; the far right ear tip should remain visible when not occluded by hair.
```

This is preferable to a single generalized rule when ear visibility is an identity anchor.

---

# 16. Head View and Body View Are Independent

The tagging system MUST distinguish the view being compiled.

A character shot may use:

- body view: `br`
- head view: `pr`

Therefore templates SHOULD be associated with a **view domain**.

Recommended domains:

- `head`
- `body`
- `costume`
- `prop`
- `scene`

For character/head sections, tags normally match the **head view**.

For costume/body sections, tags normally match the **body view**.

If the compiler cannot infer the correct domain structurally, the template SHOULD allow explicit domain directives:

```md
<!-- ZET:VIEW_DOMAIN head -->
```

or:

```md
<!-- ZET:VIEW_DOMAIN body -->
```

Example:

```md
## Head Description
<!-- ZET:VIEW_DOMAIN head -->

## Costume — Torso
<!-- ZET:VIEW_DOMAIN body -->
```

This prevents a turned head from accidentally causing front-only costume details to be emitted for a rear-facing torso.

---

# 17. Domain Override on Individual Lines

If necessary, a line MAY explicitly specify another domain.

Recommended syntax:

```md
* [head:face_visible] Violet eyes are visible.
* [body:rearish] Rear cape attachment is clearly shown.
```

This is an advanced feature and SHOULD be used sparingly.

Simple templates should rely on section-level `VIEW_DOMAIN`.

---

# 18. Tags Are Not Prompt Text

Tags and compiler directives MUST be stripped from generated prompts.

Source:

```md
* [rearish] Hair from behind forms a compact rounded bob at the nape.
```

Compiled prompt:

```md
* Hair from behind forms a compact rounded bob at the nape.
```

The image-generation model should never see `[rearish]`, `VIEW_DEFAULT`, `VIEW_DOMAIN`, or other template control syntax.

---

# 19. Preservation of Markdown Structure

Filtering a line MUST NOT damage surrounding Markdown.

The compiler SHOULD preserve:

- headings;
- retained bullet ordering;
- ZET BEGIN/END markers;
- paragraph spacing;
- non-view compiler metadata unless another compiler stage removes it.

If all bullets under a heading are filtered out, the compiler MAY remove the empty heading if configured to do so.

Recommended default: remove empty prompt-only subsections from the compiled prompt.

---

# 20. Recommended Precedence Rules

When multiple controls apply, use this precedence order:

1. `CANON_ONLY` exclusion
2. explicit line tag
3. section `VIEW_DEFAULT`
4. untagged default = `all`
5. group alias expansion
6. exclusion tokens
7. domain matching
8. requested view matching

An explicit line tag always overrides the section default.

Example:

```md
<!-- ZET:VIEW_DEFAULT face_visible -->

* Eye color: violet-purple.
* [all] Skin tone: warm golden-beige.
* [rearish] Rear jaw/skull transition remains delicate rather than broad.
```

---

# 21. Validation Rules

The compiler or a template linter SHOULD detect the following.

## Errors

- unknown view tag;
- malformed bracket syntax;
- unresolved group alias;
- tag expression resolving to zero views when not intentional;
- invalid domain;
- contradictory structural directives.

## Warnings

- eye/face detail emitted for `[b]`;
- front-only garment terms emitted for `[b]`;
- direct-back instruction allowing visible eyes;
- rear-view override that says `face`, `gaze`, or `smile` without an intentional reason;
- asymmetric feature with no left/right visibility rule;
- section containing a mix of heavily tagged and untagged lines when no `VIEW_DEFAULT` is defined;
- line tagged for all eight individual views instead of `[all]`;
- repeated view-specific instructions that could be collapsed into a group alias.

Warnings should remain advisory; there are legitimate exceptions.

---

# 22. Optional Semantic Linting

A more advanced linter MAY flag probable prompt contamination using term classes.

Example term classes:

```text
FRONT_FACE_TERMS =
    eye, eyes, gaze, eyebrow, brows, smile, lips, nose, nostril

FRONT_COSTUME_TERMS =
    neckline, cleavage, chest panel, pendant, front buckle,
    front opening, front embroidery

REAR_STRUCTURE_TERMS =
    nape, rear, back closure, cape attachment, rear seam,
    rear panel, back lacing
```

Example rule:

> If a line is emitted for `b` and contains a FRONT_FACE_TERM, produce a warning unless the line is explicitly marked as an exception.

Semantic linting SHOULD NOT automatically remove lines.

---

# 23. Optional Exception Marker

For rare intentional cases, a line MAY suppress a linter warning.

Recommended syntax:

```md
* [b] [lint:allow-face-term] Face is completely hidden by the rear orientation.
```

This should affect linting only, not inclusion.

This feature is optional and need not be implemented initially.

---

# 24. Compiled Prompt Ordering

Within each template section, retain source order.

Across logical content types, the preferred conceptual order is:

1. identity and proportion anchors that are valid for the requested view;
2. general visible construction;
3. view-specific positive description;
4. asymmetric/near-side/far-side instructions;
5. suppression / anti-drift guidance.

Do not lead a rear-view prompt with repeated negative instructions. First establish what the model should construct.

---

# 25. Example: Tagged Head Description

```md
# Head Description

## Head Description — Just the Facts

<!-- ZET:BEGIN HEAD_DESCRIPTION_FACTS -->
<!-- ZET:VIEW_DOMAIN head -->

* [face_visible] Face shape: soft heart-shaped face with delicate elven structure.
* [face_visible] Jaw/chin: small refined jaw and gentle pointed chin; not square or heavy.
* [face_visible] Cheekbones: softly defined high cheekbones, visible but not severe.
* [face_visible] Nose: small and refined, slightly upturned or delicate; avoid large or blunt noses.
* [face_visible] Mouth: expressive medium-small mouth; lips natural, not overdone.
* [face_visible] Eye shape: large anime-influenced almond eyes with an alert, luminous look.
* [face_visible] Eye color: vivid violet-purple with white sclera.
* [face_visible] Eyebrows: dark, fine, expressive brows.
* Ears: long pointed elf ears, angled outward and slightly upward; ear tips are an identity anchor.
* Neck: slim graceful neck, proportionate to a petite elven frame.
* Head-to-body proportion: slightly stylized fantasy proportions with a modestly enlarged head scale relative to realistic anatomy, while remaining adult and semi-realistic.
* Skin: light warm golden-beige with a subtle sun-kissed tan, warm peach-gold undertones, and natural healthy color.

* [f] Front view should show both large violet eyes, the heart-shaped face, small chin, delicate nose, and at least partial pointed-ear visibility through or beyond the hair.
* [fl] Front-left 3/4 should strongly show the left cheek and left ear, with the far eye still visible.
* [fr] Front-right 3/4 should strongly show the right cheek and right ear, with the far eye still visible.
* [pl] Left profile should show the delicate nose-to-lips-to-chin line, one eye or eyelash edge, and the clearly pointed left ear.
* [pr] Right profile should show the delicate nose-to-lips-to-chin line, one eye or eyelash edge, and the clearly pointed right ear.
* [bl] Back-left 3/4 should emphasize the rounded rear bob mass, nape, and left ear tip or outer rim; only a small cheek or jaw hint may appear if consistent with the requested rotation.
* [br] Back-right 3/4 should emphasize the rounded rear bob mass, nape, and right ear tip or outer rim; only a small cheek or jaw hint may appear if consistent with the requested rotation.
* [b] Back view should show the compact rounded skull and bob silhouette at the nape; pointed ear tips may protrude at the sides if not covered by hair. The face and eyes are not visible.

<!-- ZET:END HEAD_DESCRIPTION_FACTS -->
```

---

# 26. Example: Costume Torso

```md
## Torso

<!-- ZET:VIEW_DOMAIN body -->

* Base garment color is deep teal.
* Fabric is fitted but mobile, with structured fantasy-tailoring construction.
* [front_torso_visible] The front neckline forms a low, controlled open shape.
* [frontish] The fitted front bodice frames the exposed midriff without covering it.
* [fl,pl,bl] The left side seam remains clean and fitted.
* [fr,pr,br] The right side seam remains clean and fitted.
* [rear_torso_visible] The rear torso construction remains fitted and uninterrupted, with the back closure centered and visually readable.
* [rearish] Do not rotate the torso toward the viewer to reveal the neckline or chest panel.
```

For `BACK`, the compiled torso description would contain no neckline or front-bodice instruction.

---

# 27. Example: Asymmetric Equipment

```md
## Rapier

<!-- ZET:VIEW_DOMAIN body -->

* Rapier is worn at the subject's anatomical left hip.
* [leftish] Rapier and scabbard are strongly visible along the near left hip.
* [rightish] Rapier is mostly on the far side and should not migrate to the right hip merely to remain visible.
* [b] Rapier hangs from the left side of the rear belt silhouette.
```

This prevents the generator from moving asymmetric equipment to whichever side is visually convenient.

---

# 28. Example Compilation

Requested:

```text
BODY_VIEW = BACK_LEFT_3_4
HEAD_VIEW = BACK_LEFT_3_4
```

Source:

```md
* [face_visible] Eye color: vivid violet-purple.
* Ears: long pointed elf ears angled outward and upward.
* [bl] Back-left 3/4 emphasizes rear bob mass, nape, and left ear.
* [frontish] Pendant hangs centered against the upper chest.
* [rearish] Rear blouse closure runs cleanly down the upper back.
```

Compiled:

```md
* Ears: long pointed elf ears angled outward and upward.
* Back-left 3/4 emphasizes rear bob mass, nape, and left ear.
* Rear blouse closure runs cleanly down the upper back.
```

The eye color and pendant lines remain canonical but do not contaminate the rear-view generation prompt.

---

# 29. Migration Strategy

Do not attempt to tag every template perfectly in one pass.

Recommended migration order:

## Phase 1 — Highest-Risk Sections

Tag:

1. face;
2. eyes;
3. hair;
4. ears;
5. costume torso;
6. skirt/overskirt;
7. jewelry;
8. asymmetric equipment.

These contain the strongest front-view attractors.

## Phase 2 — Add Rear Positive Overrides

For each major section, ensure `b`, `bl`, and `br` have enough positive information to construct the rear view without borrowing front geometry.

## Phase 3 — Add Section Defaults

Once repeated patterns are clear, use `VIEW_DEFAULT` to reduce tag noise.

## Phase 4 — Add Linting

Add structural validation first, then optional semantic warnings.

---

# 30. Authoring Guidelines

Template authors SHOULD follow these rules:

1. **Untagged means intentional all-view relevance.**  
   Do not leave a line untagged merely because tagging it is inconvenient.

2. **Describe visible evidence, not invisible canon.**  
   If a feature cannot be seen in the requested view, it usually does not belong in that prompt.

3. **Prefer positive rear construction over negative-only guidance.**  
   Tell the generator what the rear should contain.

4. **Use explicit per-view rules for identity-critical asymmetry.**  
   Ears, weapons, hair asymmetry, straps, and one-sided accessories deserve precision.

5. **Keep body view and head view independent.**  
   A turned head must not cause front-only costume information to appear on a rear-facing body.

6. **Keep global wording orientation-neutral.**  
   Avoid front-facing semantic cues in `[all]` text.

7. **Do not use tags to redefine canon.**  
   Tags only control compilation.

8. **Prefer group aliases when the visual logic is genuinely shared.**  
   Use individual view tags when behavior differs materially.

9. **Preserve source readability.**  
   The template is still a human-maintained specification.

10. **Treat the compiled prompt as a view-specific projection of canon.**  
    It does not need to restate everything known about the character.

---

# 31. Minimal Required Implementation

A first implementation only needs:

- eight view tokens;
- comma-separated inclusion tags;
- built-in aliases;
- untagged = all;
- section-level `VIEW_DOMAIN`;
- section-level `VIEW_DEFAULT`;
- tag stripping during compilation;
- line filtering by requested body/head view;
- validation of unknown tags.

Everything else in this specification can be layered on later.

Recommended initial aliases:

```text
all
frontish
rearish
profiles
front_3q
back_3q
three_quarter
leftish
rightish
face_visible
both_eyes_visible
rear_head_visible
front_torso_visible
rear_torso_visible
front_costume_visible
rear_costume_visible
```

---

# 32. Recommended Future Extensions

Possible later additions:

- semantic linting for front/rear contamination;
- automatic suggested tags based on section type;
- template visualization showing which lines compile into each view;
- a compiler diagnostic mode that outputs an eight-column inclusion matrix;
- view-specific token counts;
- regression tests comparing compiled prompts for all eight views;
- automated warnings when `BACK` contains face-visibility language;
- authoring tools that preview the exact compiled prompt beside the source template.

A particularly useful diagnostic would be:

```text
zet template inspect Costume_Canonical_Adventure_Gear.md --matrix
```

producing a table showing every tagged line and the views into which it compiles.

---

# 33. Design Principle Summary

The tagging system exists to enforce one distinction:

> **Canonical truth is not the same thing as visible prompt evidence.**

A complete character or costume template may describe everything known about the subject. A generation prompt should describe only what the requested view should actually reveal, together with enough positive construction detail to make that view stable.

For difficult rear views, the correct strategy is therefore not merely:

> "Ask for BACK more forcefully."

It is:

> "Compile a prompt whose information architecture is itself rear-facing."
