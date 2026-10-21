<!-- ZET:BEGIN IMAGE_PROMPT_ONLY -->
# Render Task

Create one finished full-character assembly for {{CHARACTER_NAME}}, {{CHARACTER_PHASE}} by joining the supplied head to the supplied body.

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

<!-- ZET:BEGIN LOCAL_PIPELINE_ONLY -->
{{LOCAL_CHARACTER_ASSEMBLY_REFERENCE_GUIDANCE}}
<!-- ZET:END LOCAL_PIPELINE_ONLY -->

Put the head in Image 2 on the body in Image 1.
- Keep the supplied face, hair, ears, apparent age, expression, and gaze unchanged.
- Keep the body's proportions, pose, stance, clothing, framing, background, and orientation unchanged.
- Preserve the head's identity and natural scale relative to the body.
- Make only the changes needed to join the head and neck naturally, with local blending at the junction.
- Preserve the supplied rendering style and detail; do not broadly repaint or reinterpret either source.

# Subject Details

{{CHARACTER_ASSEMBLY_CHARACTER_REQUIREMENTS}}

{{VIEW_INSTRUCTION}}

{{ASSEMBLY_STYLE_INSTRUCTION}}

# Constraints

Do not redirect the gaze, change head scale, alter body geometry, mirror the requested view, or redesign the neck, shoulders, hair, or body beyond a natural join.

Produce one character, one view, and one finished image—not a scene, collage, or multi-view sheet.
