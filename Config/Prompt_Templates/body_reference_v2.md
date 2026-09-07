# Render Task

Create one new full-body technical body reference for {{CHARACTER_NAME}}, {{CHARACTER_PHASE}}. This is text-to-image generation with no source image.

# Image Inputs

{{CHATGPT_IMAGE_INPUTS}}

# Change Contract

{{CHATGPT_CHANGE_CONTRACT}}

# Preserve Contract

{{CHATGPT_PRESERVE_CONTRACT}}

# Output Contract

- One character, one {{VIEW_LABEL}} view, one finished image.
- Entire body visible from the top of the head through both soles; no cropping.
- Neutral standing pose, readable proportions, clean silhouette, and exact requested view.
- Neutral technical background clearly separated from the character; no cast shadow, contact shadow, halo, or vignette.

# Subject

{{CHARACTER_PHASE}} {{CHARACTER_RACE}} {{CHARACTER_GENDER}}.

{{VIEW_INSTRUCTION}}

Render in the Canonical Art Style: {{CANONICAL_ART_STYLE}}

## Body and stance

{{BODY_DESCRIPTION_FACTS}}

{{BODY_DESCRIPTION_VIEW_{VIEW}}}

{{NEUTRAL_POSE_STANCE}}
{{NEUTRAL_POSE_STANCE_VIEW_{VIEW}}}

## Fitment clothing

{{TECHNICAL_MODESTY_LAYER}}

## Mannequin head

Use a simplified neutral light-gray {{CHARACTER_RACE}} mannequin head with correct scale, neck attachment, and orientation. Use smooth geometry and minimal construction lines. Do not add skin color, hair, facial features, expression, makeup, or character likeness.

{{RACE_BODY_REFERENCE_POSITIVE}}
{{RACE_BODY_REFERENCE_NEGATIVE}}

# Constraints

{{BODY_REFERENCE_CHARACTER_REQUIREMENTS}}

{{BACKGROUND_TREATMENT}}

Do not add a dramatic pose, narrative scene, props, weapons, accessories, ornate costume, or body-type drift.
