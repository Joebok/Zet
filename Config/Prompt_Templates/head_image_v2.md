# HEAD-IMAGE {{CHARACTER_PHASE}} CHARACTER REFERENCE

<!-- ZET:BEGIN IMAGE_PROMPT_ONLY -->
<!-- ZET:BEGIN TRADITIONAL_PIPELINE_ONLY -->
# Render Task

Create one head-only reference of {{CHARACTER_NAME}}, {{CHARACTER_PHASE}}, in {{VIEW_LABEL}}.

# Image Inputs

{{CHATGPT_IMAGE_INPUTS}}

# Change Contract

{{CHATGPT_CHANGE_CONTRACT}}

# Preserve Contract

{{CHATGPT_PRESERVE_CONTRACT}}
<!-- ZET:END TRADITIONAL_PIPELINE_ONLY -->
<!-- ZET:BEGIN LOCAL_PIPELINE_ONLY -->
Create one clean head reference of {{CHARACTER_NAME}}, {{CHARACTER_PHASE}}.

{{LOCAL_REFERENCE_GUIDANCE}}

{{LOCAL_VIEW_INSTRUCTION}}

{{LOCAL_GAZE_INSTRUCTION}}

{{HEAD_IMAGE_EXPRESSION_GUIDANCE}}

{{LOCAL_PHASE_CHANGES}}

~{{HEAD_DESCRIPTION_FACTS}}
~{{HEAD_DESCRIPTION_VIEW_OVERRIDES}}
~{{HAIR_DESCRIPTION_FACTS}}
~{{HAIR_DESCRIPTION_VIEW_OVERRIDES}}

{{LOCAL_VISIBLE_CHARACTER_FACTS}}

Show the complete head and authored hairstyle against a plain transparent background. Expand the framing to include the neck, shoulders and enough upper back or torso context to establish the visible hair endpoint at its authored body landmark, while keeping usable head detail and natural head/neck proportions. For mid-back hair, include the back below the shoulder blades; do not shorten the hair to fit a head-and-shoulders crop. If exceptionally long hair cannot fit while retaining usable head detail, let it continue naturally beyond the lower frame without inventing a shorter hem. Body and clothing are framing context only. Preserve natural occlusion in the requested view. Render in {{LOCAL_STYLE_INSTRUCTION}}.

Build dimensional facial planes around the cheeks, nose, mouth and eyes using gradual light and shadow. Render naturally seated eyes with defined eyelids and restrained corneal highlights, subtle skin-color variation, and hair grouped into strands with natural highlights. Preserve authored age and distinctive features without oversized anime eyes, flat cel shading, heavy outlines or plastic skin. Apply these details only to surfaces visible in the requested view; do not turn the head to reveal hidden features.
<!-- ZET:END LOCAL_PIPELINE_ONLY -->
<!-- ZET:END IMAGE_PROMPT_ONLY -->

<!-- ZET:BEGIN ANALYSIS_PROMPT_ONLY -->
# Review Specification

Judge the candidate image against the visible requirements below and the supplied reference images.

# Reference Images

{{CHATGPT_IMAGE_INPUTS}}
<!-- ZET:END ANALYSIS_PROMPT_ONLY -->

<!-- ZET:BEGIN TRADITIONAL_PIPELINE_ONLY -->
# Requested Change

{{HEAD_IMAGE_TRANSFORM_INSTRUCTIONS}}

{{HEAD_IMAGE_SOURCE_INSTRUCTIONS}}

{{HEAD_IMAGE_GAZE_RULE}}

# Subject Details

{{HEAD_DESCRIPTION_FACTS}}

{{HEAD_DESCRIPTION_VIEW_OVERRIDES}}

{{HAIR_DESCRIPTION_FACTS}}

{{HAIR_DESCRIPTION_VIEW_OVERRIDES}}

{{HEAD_DESCRIPTION_VIEW_SUPPRESSION}}

{{HEAD_IMAGE_SOURCE_RULES}}

{{HEAD_IMAGE_CHARACTER_REQUIREMENTS}}

{{HEAD_IMAGE_EXPRESSION_GUIDANCE}}

# View and Style

{{VIEW_INSTRUCTION}}

Render in the Canonical Art Style: {{CANONICAL_ART_STYLE}}

# Constraints

{{NEGATIVE_GUIDANCE_HEAD_IMAGE}}

Produce one clean reusable head reference, not a scene, sheet, collage, diagram, or labeled image.
<!-- ZET:END TRADITIONAL_PIPELINE_ONLY -->
