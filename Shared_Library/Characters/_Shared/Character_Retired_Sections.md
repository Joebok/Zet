# Retired Character Sections

These sections were removed from the active template schema. Their original text is preserved verbatim for review and recovery.

## HEAD_IMAGE_SOURCE_RULES_PRE_REQUIRED_SOURCE

Optional source-image contract:

* Source identity authority: `[What likeness or design information should be taken from a supplied source image.]`
* Preserve from source: `[Identity-defining shapes, proportions, expression, tilt, or other stable traits.]`
* Intentional target-phase changes: `[Age, hair, species, condition, or other changes required by this Character.md.]`
* Template precedence: the target-phase Character.md overrides the source only for explicitly described changes; preserve all other identity-defining source traits.
* Without a source image: construct the character from the factual, identity-preservation, and requested-view sections in this Character.md.
* The requested target view always overrides the source image's camera angle or head orientation.

## BODY_DESCRIPTION_PICARESQUE

[Expressive description of physical presence, gesture, grace, tension, confidence, awkwardness, athleticism, etc.]

Example stub:

* Her movement feels `[fluid / wary / buoyant / precise / theatrical]`.
* Her posture communicates `[confidence / curiosity / nervousness / resolve]`.

## COMPILER_BUNDLE_BODY_REFERENCE

Recommended sections for body-reference:

* BODY_DESCRIPTION_FACTS
* BODY_DESCRIPTION_VIEW_[REQUESTED_VIEW]
* IDENTITY_PRESERVATION_BODY
* BODY_REFERENCE_RENDERING_RULES
* TECHNICAL_MODESTY_LAYER
* NEUTRAL_POSE_STANCE
* NEUTRAL_POSE_STANCE_VIEW_[REQUESTED_VIEW]

## COMPILER_BUNDLE_COSTUME_FITMENT

Recommended sections for costume-fitment:

* GENERAL_DESCRIPTION_FACTS
* BODY_DESCRIPTION_FACTS
* IDENTITY_PRESERVATION_COSTUME
* COSTUME_DESCRIPTION_VIEW_[REQUESTED_VIEW]
* EQUIPMENT_DESCRIPTION_FACTS
* EQUIPMENT_DESCRIPTION_VIEW_[REQUESTED_VIEW]
* IDENTITY_PRESERVATION_CORE
* IDENTITY_PRESERVATION_BODY
* IDENTITY_PRESERVATION_COSTUME
* NEGATIVE_GUIDANCE_GENERAL

## COMPILER_BUNDLE_EXPRESSION_SHEET

Recommended sections for expression sheets:

* GENERAL_DESCRIPTION_FACTS
* HEAD_DESCRIPTION_FACTS
* HAIR_DESCRIPTION_FACTS
* EXPRESSION_DESCRIPTION_FACTS
* IDENTITY_PRESERVATION_CORE
* IDENTITY_PRESERVATION_FACE
* IDENTITY_PRESERVATION_HAIR
* IDENTITY_PRESERVATION_EARS
* NEGATIVE_GUIDANCE_GENERAL

## COMPILER_BUNDLE_HEAD_IMAGE

Use for Head-Image rotation jobs:

* `GENERAL_DESCRIPTION_FACTS`
* `HEAD_DESCRIPTION_FACTS`
* `HEAD_DESCRIPTION_VIEW_{VIEW}`
* `HAIR_DESCRIPTION_FACTS`
* `HAIR_DESCRIPTION_VIEW_{VIEW}`
* `IDENTITY_PRESERVATION_CORE`
* `IDENTITY_PRESERVATION_FACE`
* `IDENTITY_PRESERVATION_EYES`
* `IDENTITY_PRESERVATION_HAIR`
* `IDENTITY_PRESERVATION_EARS`
* `HEAD_IMAGE_REFERENCE_INSTRUCTIONS` (optional; used only when a source image is attached)
* `HEAD_IMAGE_REFERENCE_RULES`
* `HEAD_IMAGE_RENDERING_RULES`
* `NEGATIVE_GUIDANCE_GENERAL`

## COMPILER_BUNDLE_NARRATIVE_SCENE

Recommended sections for narrative scene images:

* GENERAL_DESCRIPTION_FACTS
* GENERAL_DESCRIPTION_PICARESQUE
* BODY_DESCRIPTION_FACTS
* BODY_DESCRIPTION_PICARESQUE
* HEAD_DESCRIPTION_FACTS
* HEAD_DESCRIPTION_PICARESQUE
* HAIR_DESCRIPTION_FACTS
* HAIR_DESCRIPTION_PICARESQUE
* IDENTITY_PRESERVATION_COSTUME
* COSTUME_DESCRIPTION_PICARESQUE
* EQUIPMENT_DESCRIPTION_FACTS
* EQUIPMENT_DESCRIPTION_PICARESQUE
* EXPRESSION_DESCRIPTION_FACTS
* EXPRESSION_DESCRIPTION_PICARESQUE
* POSE_GESTURE_FACTS
* POSE_GESTURE_PICARESQUE
* SCENE_RENDERING_FACTS
* SCENE_RENDERING_PICARESQUE
* IDENTITY_PRESERVATION_CORE
* NEGATIVE_GUIDANCE_GENERAL

## COMPILER_BUNDLE_TURNAROUND

Recommended sections for turnaround sheets:

* GENERAL_DESCRIPTION_FACTS
* BODY_DESCRIPTION_FACTS
* HEAD_DESCRIPTION_FACTS
* HAIR_DESCRIPTION_FACTS
* IDENTITY_PRESERVATION_COSTUME
* EQUIPMENT_DESCRIPTION_FACTS
* IDENTITY_PRESERVATION_CORE
* IDENTITY_PRESERVATION_FACE
* IDENTITY_PRESERVATION_HAIR
* IDENTITY_PRESERVATION_EARS
* IDENTITY_PRESERVATION_BODY
* IDENTITY_PRESERVATION_COSTUME
* NEGATIVE_GUIDANCE_GENERAL

## COMPILER_NOTES

Use this file as a structured source document for image-prompt compilation.

Recommended usage:

* Use `*_FACTS` sections for technical/reference jobs such as body-reference, fitment, turnaround sheets, and consistency checks.
* Use `*_PICARESQUE` sections for narrative, expressive, cinematic, or scene-based jobs.
* Use `IDENTITY_PRESERVATION` sections whenever the character’s likeness must remain stable.
* Use view-specific subsections when the task requests a specific camera/view angle.
* Use `HEAD_IMAGE_REFERENCE_RULES` to define how an optional source image contributes identity and which phase changes are intentional.
* If a view-specific subsection is empty, fall back to the general section above it.

## EXPRESSION_DESCRIPTION_PICARESQUE

[Flavor description of the character's characteristic emotional range.]

## FREEFORM_NOTES

[Human notes, unresolved decisions, experimental additions, or future compiler ideas.]

## GENERAL_DESCRIPTION_FACTS

[Brief factual summary of the character without mood, story, or emotional interpretation.]

Example stub:

* `[Character Name]` is a `[species/ancestry]` `[role/class/archetype]`.
* Apparent age: `[adult / young adult / etc.]`.
* Overall visual impression: `[short factual description]`.
* Canonical style: `[style]`.

## GENERAL_DESCRIPTION_PICARESQUE

[Flavor-rich description of the character’s presence, attitude, role in the world, or visual storytelling identity.]

Example stub:

* `[Character Name]` carries herself with `[personality impression]`.
* Her visual presence suggests `[story/worldbuilding impression]`.
* In narrative scenes, she should feel like `[dramatic or emotional anchor]`.

## GENERAL_DESCRIPTION_VIEW_BACK

Back view notes:

* `[Any back-view-specific general information.]`

## GENERAL_DESCRIPTION_VIEW_BACK_LEFT_3_4

Back-left 3/4 view notes:

* `[Any back-left 3/4-specific general information.]`

## GENERAL_DESCRIPTION_VIEW_BACK_RIGHT_3_4

Back-right 3/4 view notes:

* `[Any back-right 3/4-specific general information.]`

## GENERAL_DESCRIPTION_VIEW_FRONT

Front view notes:

* `[Any front-view-specific general information.]`

## GENERAL_DESCRIPTION_VIEW_FRONT_LEFT_3_4

Front-left 3/4 view notes:

* `[Any front-left 3/4-specific general information.]`

## GENERAL_DESCRIPTION_VIEW_FRONT_RIGHT_3_4

Front-right 3/4 view notes:

* `[Any front-right 3/4-specific general information.]`

## GENERAL_DESCRIPTION_VIEW_LEFT_PROFILE

Left profile view notes:

* `[Any left-profile-specific general information.]`

## GENERAL_DESCRIPTION_VIEW_RIGHT_PROFILE

Right profile view notes:

* `[Any right-profile-specific general information.]`

## HAIR_DESCRIPTION_PICARESQUE

[Flavor description of how the hair contributes to the character’s identity.]

Example stub:

* Her hair gives her silhouette `[distinctive impression]`.
* In motion, it should `[swing / hook / frame / remain compact / etc.]`.

## HEAD_DESCRIPTION_PICARESQUE

[Expressive face/head description.]

Example stub:

* Her face tends to read as `[watchful / bright / mischievous / thoughtful / guarded]`.
* Her expressions should preserve `[core emotional identity]`.

## HEAD_IMAGE_NEGATIVE_GUIDANCE_GENERAL

Avoid:

* Generic replacement face or loss of character identity.
* Wrong target phase or suppression of explicitly described phase changes.
* Aging, de-aging, beautification, or weathering not supported by the target-phase description.
* Sickly, skeletal, corpse-like, or otherwise unintended facial treatment.
* Wrong species markers, rounded/human ears, or missing expected ear visibility.
* Wrong hairstyle, hair color, length, texture, or silhouette.
* Opaque, parchment, studio, scenic, textured, or colored background. The background must remain truly transparent.
* Cropping any part of the head, hair silhouette, ear tips, jaw, chin, or required neck context.
* Dramatic pose, expressive head tilt, independent head turn, or view drift.

## IDENTITY_PRESERVATION_BODY

Body preservation rules:

* Preserve `[canonical build]`.
* Preserve `[height/proportion impression]`.
* Preserve `[posture/movement identity]`.
* Do not alter body type to match generic fantasy archetypes.

## LOCAL_IMAGE_GEN_OVERRIDES

prompt:
negative_prompt:
denoising_strength:
steps:
cfg_scale:
seed:
s_noise:
sd_model_checkpoint:
sampler_name:
scheduler:
enable_hr:
hr_upscaler:
hr_second_pass_steps:
hr_scale:
orientation:
restore_faces:

## NEUTRAL_POSE_STANCE

Use a neutral anatomical reference stance.

{FOOTWEAR_CONTACT}
No raised-foot pose.
No lifted foot.
No tiptoe stance.
No walking step.
No crossed ankles.
No ballet pose.
No contrapposto.
No weight-shift pose.

The legs remain straight and relaxed, with only a slight natural knee softness.
Both knees point in the same direction as the torso.
Feet are placed directly under the hips, shoulder-width or slightly narrower.
Left and right feet are parallel or nearly parallel.
The feet must align with the requested body view.

For {VIEW} view:

## NEUTRAL_POSE_STANCE_VIEW_BACK

- Feet are side-by-side and symmetrical.
- Knees, ankles, and toes align vertically beneath the hips.
- No staggered foot placement.

Render the specified camera/view orientation while using the neutral stance, leg placement, weight distribution, hip alignment, and foot contact described above.

## NEUTRAL_POSE_STANCE_VIEW_BACK_LEFT_3_4

- {FOOTWEAR_GROUNDING}
- The near foot and far foot may be offset only enough to show depth.
- Do not turn the stance into a walking pose.
- Do not cross the feet or place one foot behind the other dramatically.

Render the specified camera/view orientation while using the neutral stance, leg placement, weight distribution, hip alignment, and foot contact described above.

## NEUTRAL_POSE_STANCE_VIEW_BACK_RIGHT_3_4

- {FOOTWEAR_GROUNDING}
- The near foot and far foot may be offset only enough to show depth.
- Do not turn the stance into a walking pose.
- Do not cross the feet or place one foot behind the other dramatically.

Render the specified camera/view orientation while using the neutral stance, leg placement, weight distribution, hip alignment, and foot contact described above.

## NEUTRAL_POSE_STANCE_VIEW_FRONT

- Feet are side-by-side and symmetrical.
- Knees, ankles, and toes align vertically beneath the hips.
- No staggered foot placement.

Render the specified camera/view orientation while using the neutral stance, leg placement, weight distribution, hip alignment, and foot contact described above.

## NEUTRAL_POSE_STANCE_VIEW_FRONT_LEFT_3_4

- {FOOTWEAR_GROUNDING}
- The near foot and far foot may be offset only enough to show depth.
- Do not turn the stance into a walking pose.
- Do not cross the feet or place one foot behind the other dramatically.

Render the specified camera/view orientation while using the neutral stance, leg placement, weight distribution, hip alignment, and foot contact described above.

## NEUTRAL_POSE_STANCE_VIEW_FRONT_RIGHT_3_4

- {FOOTWEAR_GROUNDING}
- The near foot and far foot may be offset only enough to show depth.
- Do not turn the stance into a walking pose.
- Do not cross the feet or place one foot behind the other dramatically.

Render the specified camera/view orientation while using the neutral stance, leg placement, weight distribution, hip alignment, and foot contact described above.

## NEUTRAL_POSE_STANCE_VIEW_LEFT_PROFILE

- {FOOTWEAR_GROUNDING}
- One foot may partially overlap the other because of the view angle, but neither foot is lifted.
- The body is not stepping forward.

Render the specified camera/view orientation while using the neutral stance, leg placement, weight distribution, hip alignment, and foot contact described above.

## NEUTRAL_POSE_STANCE_VIEW_RIGHT_PROFILE

- {FOOTWEAR_GROUNDING}
- One foot may partially overlap the other because of the view angle, but neither foot is lifted.
- The body is not stepping forward.

Render the specified camera/view orientation while using the neutral stance, leg placement, weight distribution, hip alignment, and foot contact described above.

## POSE_GESTURE_FACTS

[Technical pose rules.]

Suggested fields:

* Neutral standing pose:
* Turnaround pose:
* Fitment pose:
* Action pose limits:
* Hand behavior:
* Foot placement:
* Balance:
* Forbidden pose drift:

## POSE_GESTURE_PICARESQUE

[Flavor description of movement and body language.]

Example stub:

* Her gestures should feel `[expressive / precise / playful / guarded / theatrical]`.
* She carries energy through `[hands / shoulders / eyes / posture / step]`.

## SCENE_RENDERING_FACTS

[Technical scene rules.]

Suggested fields:

* Default camera:
* Default framing:
* Default lighting:
* Default background treatment:
* Character priority:
* Prop priority:
* Crowd/background rules:

## SCENE_RENDERING_PICARESQUE

[Flavor guidance for narrative images.]

Example stub:

* Scenes involving this character should emphasize `[theme / mood / visual contrast]`.
* The environment should support the character without overpowering identity preservation.

## TECHNICAL_MODESTY_LAYER

Clothing rules:

* neutral tan sleeveless tank top.
* neutral tan compression shorts.
* Minimal detail and no additional garments.
* Keep the body silhouette readable.

## TECHNICAL_MODESTY_LAYER_FEMININE

Use simple neutral fitment clothing.

Clothing rules:

* neutral tan tube top.
* neutral tan compression shorts.
* Minimal detail and no additional garments.
* Keep the body silhouette readable.

## TECHNICAL_MODESTY_LAYER_MASCULINE

Use simple neutral fitment clothing.

Clothing rules:

* neutral tan compression shorts.
* No shirt.
* Minimal detail and no additional garments.
* Keep the body silhouette readable.

## TECHNICAL_MODESTY_LAYER_YOUTH

Use simple neutral fitment clothing.

Clothing rules:

* neutral tan shorts.
* neutral tan t-shirt.
* Minimal detail and no additional garments.
* Keep the body silhouette readable.
