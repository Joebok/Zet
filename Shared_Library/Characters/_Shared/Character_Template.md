# Character Image Template

Character Name: `[Character Name]`
Character Phase: `[Adult / Youth / Variant / Costume Phase]`
Species: `[Species]`
Gender Presentation: `[Optional, non-sensitive rendering descriptor]`
Canonical Art Style: `[Optional fallback when the universe has no style; e.g. naturalistic fantasy illustration with restrained painterly treatment.]`
Standing Barefoot Height: `[optional; e.g. 5 ft 8 in]`
Eye Height: `[optional; e.g. 5 ft 2 in]`
Shoulder Width: `[optional; e.g. 1 ft 6 in]`
Body Depth: `[optional; e.g. 10 in]`

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

* `[Character-specific technical requirements for the body reference.]`

<!-- ZET:END BODY_REFERENCE_CHARACTER_REQUIREMENTS -->

---

# Character Assembly

## Character Requirements

<!-- ZET:BEGIN CHARACTER_ASSEMBLY_CHARACTER_REQUIREMENTS -->

<!-- Optional legacy assembly requirements. Keep authored changes limited to the
head/body join. Use the dedicated sections below for lower-hair completion and
view-specific silhouette. -->

<!-- ZET:END CHARACTER_ASSEMBLY_CHARACTER_REQUIREMENTS -->

## General Instructions

<!-- ZET:BEGIN CHARACTER_ASSEMBLY_GENERAL_INSTRUCTIONS -->

<!-- ZET:END CHARACTER_ASSEMBLY_GENERAL_INSTRUCTIONS -->

## View Instructions

<!-- ZET:BEGIN CHARACTER_ASSEMBLY_VIEW_INSTRUCTIONS -->

<!-- ZET:END CHARACTER_ASSEMBLY_VIEW_INSTRUCTIONS -->

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


# Head-Image Edit

These sections are optional for existing pipelines. Author them before using Head-Image Edit.

## Front Description

<!-- ZET:BEGIN HEAD_EDIT_FRONT_DESCRIPTION -->
<!-- ZET:VIEW_DOMAIN head -->

[Describe front description for this character; use head-domain view tags where appropriate.]

<!-- ZET:END HEAD_EDIT_FRONT_DESCRIPTION -->

## Preserve

<!-- ZET:BEGIN HEAD_EDIT_PRESERVE -->
<!-- ZET:VIEW_DOMAIN head -->

[Describe preserve for this character; use head-domain view tags where appropriate.]

<!-- ZET:END HEAD_EDIT_PRESERVE -->

## View Overrides

<!-- ZET:BEGIN HEAD_EDIT_VIEW_OVERRIDES -->
<!-- ZET:VIEW_DOMAIN head -->

[Describe view overrides for this character; use head-domain view tags where appropriate.]

<!-- ZET:END HEAD_EDIT_VIEW_OVERRIDES -->

## Reference Guidance

<!-- ZET:BEGIN HEAD_EDIT_REFERENCE_GUIDANCE -->
<!-- ZET:VIEW_DOMAIN head -->



<!-- ZET:END HEAD_EDIT_REFERENCE_GUIDANCE -->

## Expression Guidance

<!-- ZET:BEGIN HEAD_EDIT_EXPRESSION_GUIDANCE -->
<!-- ZET:VIEW_DOMAIN head -->



<!-- ZET:END HEAD_EDIT_EXPRESSION_GUIDANCE -->

## Phase Changes

<!-- ZET:BEGIN HEAD_EDIT_PHASE_CHANGES -->
<!-- ZET:VIEW_DOMAIN head -->



<!-- ZET:END HEAD_EDIT_PHASE_CHANGES -->

## Review Criteria

<!-- ZET:BEGIN HEAD_EDIT_REVIEW_CRITERIA -->
<!-- ZET:VIEW_DOMAIN head -->

[Describe review criteria for this character; use head-domain view tags where appropriate.]

<!-- ZET:END HEAD_EDIT_REVIEW_CRITERIA -->
