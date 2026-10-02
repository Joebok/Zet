# Character Image Template

Character Name: `[Character Name]`
Character Phase: `[Adult / Youth / Variant / Costume Phase]`
Species / Ancestry: `[Species]`
Gender Presentation: `[Optional, non-sensitive rendering descriptor]`
Canonical Art Style: `[Painterly semi-realistic, anime-influenced facial proportions, etc.]`

---

# Body Description

## Body Description — Just the Facts

<!-- ZET:BEGIN BODY_DESCRIPTION_FACTS -->

[Technical body description. Use stable, measurable, non-sensational language.]

Suggested fields:

* Build:
* Height impression:
* Proportions:
* Posture:
* Shoulder shape:
* Torso shape:
* Arm shape:
* Hand shape:
* Hip/leg proportions:
* Foot stance:
* Movement baseline:

<!-- ZET:END BODY_DESCRIPTION_FACTS -->

## Body Description — View-Specific

<!-- ZET:BEGIN BODY_DESCRIPTION_VIEW_OVERRIDES -->
<!-- ZET:VIEW_DOMAIN body -->

* [f] Front view body notes:
* [f] [Shoulder width, stance, symmetry, limb visibility, etc.]
* [fl] Front-left 3/4 body notes:
* [fl] [Rotation, visible side, silhouette, overlap rules, etc.]
* [pl] Left profile body notes:
* [pl] [Profile posture, torso depth, leg alignment, etc.]
* [bl] Back-left 3/4 body notes:
* [bl] [Back silhouette, shoulder/hip rotation, limb visibility, etc.]
* [b] Back view body notes:
* [b] [Back posture, hair/clothing overlap, shoulder/hip symmetry, etc.]
* [br] Back-right 3/4 body notes:
* [br] [Back silhouette, shoulder/hip rotation, limb visibility, etc.]
* [pr] Right profile body notes:
* [pr] [Profile posture, torso depth, leg alignment, etc.]
* [fr] Front-right 3/4 body notes:
* [fr] [Rotation, visible side, silhouette, overlap rules, etc.]

<!-- ZET:END BODY_DESCRIPTION_VIEW_OVERRIDES -->

<!-- ZET:BEGIN BODY_DESCRIPTION_VIEW_SUPPRESSION -->
<!-- ZET:VIEW_DOMAIN body -->

* [b] `[State body-facing details that must remain hidden in a direct rear view.]`
* [bl,br] `[Keep rear three-quarter views from rotating toward the front.]`

<!-- ZET:END BODY_DESCRIPTION_VIEW_SUPPRESSION -->

---

# Head Description

## Head Description — Just the Facts

<!-- ZET:BEGIN HEAD_DESCRIPTION_FACTS -->
<!-- ZET:VIEW_DOMAIN head -->
<!-- ZET:VIEW_DEFAULT face_visible -->

[Technical head and face description.]

Suggested fields:

* Face shape:
* Jaw/chin:
* Cheekbones:
* Nose:
* Mouth:
* Eye shape:
* Eye color:
* Eyebrows:
* [all] Ears:
* [all] Neck:
* [all] Head-to-body proportion:

<!-- ZET:END HEAD_DESCRIPTION_FACTS -->

## Head Description — View-Specific

<!-- ZET:BEGIN HEAD_DESCRIPTION_VIEW_OVERRIDES -->
<!-- ZET:VIEW_DOMAIN head -->

* [f] Front view head notes:
* [f] [Face symmetry, both eyes visible, ear visibility, etc.]
* [fl] Front-left 3/4 head notes:
* [fl] [Visible cheek, far eye visibility, ear visibility, nose angle, etc.]
* [pl] Left profile head notes:
* [pl] [Profile nose/chin/ear rules, eye visibility, etc.]
* [bl] Back-left 3/4 head notes:
* [bl] [Hair mass, ear edge visibility, cheek/jaw hints, etc.]
* [b] Back view head notes:
* [b] [Back of skull, hair silhouette, ear tips if visible, neck connection, etc.]
* [br] Back-right 3/4 head notes:
* [br] [Hair mass, ear edge visibility, cheek/jaw hints, etc.]
* [pr] Right profile head notes:
* [pr] [Profile nose/chin/ear rules, eye visibility, etc.]
* [fr] Front-right 3/4 head notes:
* [fr] [Visible cheek, far eye visibility, ear visibility, nose angle, etc.]

<!-- ZET:END HEAD_DESCRIPTION_VIEW_OVERRIDES -->

<!-- ZET:BEGIN HEAD_DESCRIPTION_VIEW_SUPPRESSION -->
<!-- ZET:VIEW_DOMAIN head -->

* [b] `[Keep the face and eyes hidden in a direct rear view.]`
* [bl,br] `[Keep rear three-quarter views from rotating toward the front.]`

<!-- ZET:END HEAD_DESCRIPTION_VIEW_SUPPRESSION -->

---

# Hair Description

## Hair Description — Just the Facts

<!-- ZET:BEGIN HAIR_DESCRIPTION_FACTS -->

[Technical hair description.]

Suggested fields:

* Hair color:
* Hair length:
* Hair texture:
* Hair volume:
* Hairline:
* Part/asymmetry:
* Face-framing behavior:
* Back silhouette:
* Forbidden drift:

<!-- ZET:END HAIR_DESCRIPTION_FACTS -->

## Hair Description — View-Specific

<!-- ZET:BEGIN HAIR_DESCRIPTION_VIEW_OVERRIDES -->
<!-- ZET:VIEW_DOMAIN head -->

* [f] Front view hair notes:
* [f] [How hair frames the face from the front.]
* [fl] Front-left 3/4 hair notes:
* [fl] [Near-side/far-side hair visibility.]
* [pl] Left profile hair notes:
* [pl] [Profile silhouette and face-framing edge.]
* [bl] Back-left 3/4 hair notes:
* [bl] [Back mass, side curve, neck overlap.]
* [b] Back view hair notes:
* [b] [Back silhouette, nape behavior, length endpoints.]
* [br] Back-right 3/4 hair notes:
* [br] [Back mass, side curve, neck overlap.]
* [pr] Right profile hair notes:
* [pr] [Profile silhouette and face-framing edge.]
* [fr] Front-right 3/4 hair notes:
* [fr] [Near-side/far-side hair visibility.]

<!-- ZET:END HAIR_DESCRIPTION_VIEW_OVERRIDES -->

---

# Expression

## Expression Guidance

<!-- ZET:BEGIN EXPRESSION_DESCRIPTION_FACTS -->

[Technical expression rules that apply across this character phase.]

Suggested fields:

* Neutral expression:
* Eye and brow behavior:
* Mouth behavior:
* Expression intensity limits:
* Forbidden expression drift:

<!-- ZET:END EXPRESSION_DESCRIPTION_FACTS -->

---

# Identity Preservation

## Core

<!-- ZET:BEGIN IDENTITY_PRESERVATION_CORE -->

Core identity anchors:

* `[Face shape anchor]`
* `[Eye color and eye shape anchor]`
* `[Hair silhouette anchor]`
* `[Ear shape/visibility anchor]`
* `[Body proportion anchor]`
* `[Costume silhouette anchor]`
* `[Signature item anchor]`

The rendered character must be recognizably the same person across views, expressions, outfits, and rendering passes.

<!-- ZET:END IDENTITY_PRESERVATION_CORE -->

## Face

<!-- ZET:BEGIN IDENTITY_PRESERVATION_FACE -->

Face preservation rules:

* Preserve `[specific face shape]`.
* Preserve `[specific eye shape/color]`.
* Preserve `[specific nose/mouth/chin relationships]`.
* Do not age the character up or down unless the task explicitly requests that phase.
* Do not replace the face with a generic fantasy/anime face.

<!-- ZET:END IDENTITY_PRESERVATION_FACE -->

## Eyes

<!-- ZET:BEGIN IDENTITY_PRESERVATION_EYES -->

Eye preservation rules:

* Preserve `[specific eye shape and color]`.
* Preserve `[iris, pupil, highlight, and eyelid characteristics]`.
* Do not change eye size, spacing, color, or characteristic gaze unless the task explicitly requires it.

<!-- ZET:END IDENTITY_PRESERVATION_EYES -->

## Hair

<!-- ZET:BEGIN IDENTITY_PRESERVATION_HAIR -->

Hair preservation rules:

* Preserve `[canonical haircut / silhouette / length / texture]`.
* Preserve `[face-framing behavior]`.
* Preserve `[asymmetry, if any]`.
* Do not make the hair curly, overly long, overly short, or generically styled unless the task explicitly requests a variant.

<!-- ZET:END IDENTITY_PRESERVATION_HAIR -->

## Ears

<!-- ZET:BEGIN IDENTITY_PRESERVATION_EARS -->

Ear preservation rules:

* Preserve `[ear shape]`.
* Preserve `[ear tip visibility expectations]`.
* Do not hide both ears when the requested view should show at least one ear or ear tip.
* Do not make ears round/human unless the character phase explicitly requires it.

<!-- ZET:END IDENTITY_PRESERVATION_EARS -->

---

# Scene Rendering

## Scene Character Identity

<!-- ZET:BEGIN SCENE_CHARACTER_IDENTITY -->



<!-- ZET:END SCENE_CHARACTER_IDENTITY -->

---

# Body Reference

## Character Requirements

<!-- ZET:BEGIN BODY_REFERENCE_CHARACTER_REQUIREMENTS -->

Rendering priorities:

* `[Body-only art style without face or head traits.]`

<!-- ZET:END BODY_REFERENCE_CHARACTER_REQUIREMENTS -->

---

# Head Image

## Transform Instructions

<!-- ZET:BEGIN HEAD_IMAGE_TRANSFORM_INSTRUCTIONS -->



<!-- ZET:END HEAD_IMAGE_TRANSFORM_INSTRUCTIONS -->

## Local Head-Image Phase Changes

<!-- ZET:BEGIN HEAD_IMAGE_LOCAL_PHASE_CHANGES -->



<!-- ZET:END HEAD_IMAGE_LOCAL_PHASE_CHANGES -->

## Source Instructions

<!-- ZET:BEGIN HEAD_IMAGE_SOURCE_INSTRUCTIONS -->



<!-- ZET:END HEAD_IMAGE_SOURCE_INSTRUCTIONS -->

## Source Rules

<!-- ZET:BEGIN HEAD_IMAGE_SOURCE_RULES -->

Source-image contract:

* Source identity authority: `[What likeness or design information should be taken from a supplied source image.]`
* Preserve from source: `[Identity-defining shapes, proportions, expression, tilt, or other stable traits.]`
* Intentional target-phase changes: `[Age, hair, species, condition, or other changes required by this Character.md.]`
* Template precedence: the target-phase Character.md overrides the source only for explicitly described changes; preserve all other identity-defining source traits.
* The requested target view always overrides the source image's camera angle or head orientation.

<!-- ZET:END HEAD_IMAGE_SOURCE_RULES -->

## Character Requirements

<!-- ZET:BEGIN HEAD_IMAGE_CHARACTER_REQUIREMENTS -->

Rendering priorities:

* Render one clear image of the character's head in the requested view.
* Use the Canonical Art Style.
* Use natural head-and-shoulders or limited-bust framing with the complete head, hair silhouette, jaw, chin, neck, and enough upper-shoulder context for assembly.
* Render on a transparent background with clear readable lighting; do not add a backdrop or environment.
* The visible shoulders, upper torso, and clothing are contextual only and do not define the final assembled body.
* Do not add a narrative scene, prominent props, or unrelated characters.

<!-- ZET:END HEAD_IMAGE_CHARACTER_REQUIREMENTS -->

## Expression Guidance

<!-- ZET:BEGIN HEAD_IMAGE_EXPRESSION_GUIDANCE -->

<!-- ZET:VIEW_DOMAIN head -->
* [head:frontish,profiles] Use a calm, neutral expression with relaxed brows and mouth; keep the lips gently closed, with no smile, frown, or exaggerated emotion. Keep the eyes and gaze aligned with the requested view.

<!-- ZET:END HEAD_IMAGE_EXPRESSION_GUIDANCE -->

## Negative Guidance

<!-- ZET:BEGIN NEGATIVE_GUIDANCE_HEAD_IMAGE -->

* Preserve the exact requested head orientation and view-specific facial visibility.
* Keep the output a reusable head reference rather than a narrative portrait or scene.
* Use only the natural neck and limited shoulder context needed to preserve the complete head and hairstyle silhouette.
* Do not add extra weapons, props, jewelry, decorative accessories, labels, registration text, or visible guide marks.

<!-- ZET:END NEGATIVE_GUIDANCE_HEAD_IMAGE -->

---

# Character Assembly

## Character Requirements

<!-- ZET:BEGIN CHARACTER_ASSEMBLY_CHARACTER_REQUIREMENTS -->



<!-- ZET:END CHARACTER_ASSEMBLY_CHARACTER_REQUIREMENTS -->

---

# Expression Negative Guidance

## Negative Guidance

<!-- ZET:BEGIN NEGATIVE_GUIDANCE_EXPRESSION -->

### General

Avoid:

* Wrong age phase.
* Wrong species markers.
* Incorrect body type.
* Incorrect hair length or texture.
* Missing signature silhouette.
* Incorrect eye color.
* Incorrect left/right equipment placement.
* Overly ornate redesign unless requested.
* Unrequested costume changes.
* Unrequested weapons or props.
* Dramatic pose when a technical pose is requested.
* Narrative acting when a neutral reference is requested.

### Phase-specific

[Add task-specific avoid rules here.]

Examples:

* For body-reference: avoid facial emotion, costume details, dramatic scene lighting.
* For costume-fitment: avoid changing body proportions to fit the costume.
* For turnaround: avoid pose variation between views.
* For expression sheets: avoid changing identity to exaggerate expression.

<!-- ZET:END NEGATIVE_GUIDANCE_EXPRESSION -->
