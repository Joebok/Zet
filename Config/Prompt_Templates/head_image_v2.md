# HEAD-IMAGE {{CHARACTER_PHASE}} CHARACTER REFERENCE

<!-- ZET:BEGIN IMAGE_PROMPT_ONLY -->
# Render Task

Create one head-only reference of {{CHARACTER_NAME}}, {{CHARACTER_PHASE}}, in {{VIEW_LABEL}}.

# Image Inputs

{{CHATGPT_IMAGE_INPUTS}}

# Change Contract

{{CHATGPT_CHANGE_CONTRACT}}

# Preserve Contract

{{CHATGPT_PRESERVE_CONTRACT}}
<!-- ZET:END IMAGE_PROMPT_ONLY -->

<!-- ZET:BEGIN ANALYSIS_PROMPT_ONLY -->
# Review Specification

Judge the candidate image against the visible requirements below and the supplied reference images.

# Reference Images

{{CHATGPT_IMAGE_INPUTS}}
<!-- ZET:END ANALYSIS_PROMPT_ONLY -->

# Requested Change

{{HEAD_IMAGE_TRANSFORM_INSTRUCTIONS}}

{{HEAD_IMAGE_SOURCE_INSTRUCTIONS}}

# Subject Details

{{HEAD_DESCRIPTION_FACTS}}

{{HEAD_DESCRIPTION_VIEW_{VIEW}}}

{{HAIR_DESCRIPTION_FACTS}}

{{HAIR_DESCRIPTION_VIEW_{VIEW}}}

{{HEAD_IMAGE_SOURCE_RULES}}

{{HEAD_IMAGE_CHARACTER_REQUIREMENTS}}

# View and Style

{{VIEW_INSTRUCTION}}

Render in the Canonical Art Style: {{CANONICAL_ART_STYLE}}

# Constraints

{{NEGATIVE_GUIDANCE_HEAD_IMAGE}}

Produce one clean reusable head reference, not a scene, sheet, collage, diagram, or labeled image.
