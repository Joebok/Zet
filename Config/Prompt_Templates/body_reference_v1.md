This is a text-to-image generation request. No existing image is referenced, attached, or should be used. Generate a completely new full-body technical body-reference image from this description only.

Depict {{CHARACTER_NAME}}, an {{CHARACTER_PHASE}} {{CHARACTER_RACE}} {{CHARACTER_GENDER}}, in a neutral standing pose from a {VIEW} view.

{{VIEW_INSTRUCTION}}

Entire body visible from top of head to soles of feet, with both feet fully visible and no cropping.
Use a neutral standing pose and a full-body composition, not portrait, bust, waist-up, or thigh-up framing.
Prioritize readable body proportions, a clean silhouette, and the requested view angle.

BODY PROPORTIONS

{{SECTION:BODY_DESCRIPTION_FACTS}}

{{SECTION:BODY_DESCRIPTION_VIEW_{VIEW}}}

{{SECTION:IDENTITY_PRESERVATION_BODY}}

STANCE AND FOOT PLACEMENT — CRITICAL

{{NEUTRAL_POSE_STANCE}}
{{NEUTRAL_POSE_STANCE_VIEW_{VIEW}}}

FITMENT CLOTHING

{{SECTION:TECHNICAL_MODESTY_LAYER}}

MANNEQUIN HEAD — REQUIRED

Use a simplified neutral light-gray {{CHARACTER_RACE}} mannequin head. The head is part of the technical body reference, not a character portrait.

Include:

* smooth simplified mannequin geometry
* minimal construction lines only
* correct head scale, neck attachment, and requested orientation
{{RACE_BODY_REFERENCE_POSITIVE}}

Do not include:

* skin or skin-colored head material
* hair
* eyes, eyebrows, eyelashes, nose detail, or lips
* facial expression, facial aging, makeup, or character likeness
{{RACE_BODY_REFERENCE_NEGATIVE}}

The mannequin head is the intended final result, not a placeholder for a finished face.

BACKGROUND AND RENDERING

{{SECTION:BODY_REFERENCE_RENDERING_RULES}}

{{BACKGROUND_TREATMENT}}
Even studio lighting.

Do not render a wrong view, dramatic or fashion pose, narrative scene, props, weapons, accessories, ornate costume, or body-type drift.

The final image should be sober, neutral, readable, and technically useful.
