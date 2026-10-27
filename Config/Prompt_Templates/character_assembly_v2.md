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
- Keep the supplied face, ears, apparent age, expression, and gaze unchanged. Preserve the hairstyle's color, texture, parting, volume and asymmetry.
- Keep the body's proportions, pose, stance, clothing design, framing, background, and orientation unchanged.
- Preserve the head's identity and natural scale relative to the body.
- Join the head and neck naturally, with local blending at the junction. If Subject Details explicitly specifies a hair endpoint at a body landmark, complete cropped or prematurely terminated lower hair below the neckline to that landmark on the assembled body. That authored endpoint controls lower-hair length; the head reference's crop or accidental short hem does not.
- Continue the established hairstyle naturally across the necessary shoulders, back and clothing, with correct overlap and perspective. Hair may cover those surfaces without changing underlying body geometry or clothing design. Without an explicitly authored endpoint, preserve the supplied hair length rather than inventing an extension. Keep short hairstyles short.
- Preserve the supplied rendering style and detail; do not broadly repaint or reinterpret either source.

# Subject Details

{{CHARACTER_ASSEMBLY_CHARACTER_REQUIREMENTS}}

{{VIEW_INSTRUCTION}}

{{ASSEMBLY_STYLE_INSTRUCTION}}

# Constraints

Do not redirect the gaze, change head scale, alter body geometry, mirror the requested view, or redesign the neck, shoulders, hairstyle or body. Limit reconstruction to the natural join and lower-hair completion explicitly authorized in Subject Details; do not expose features naturally hidden by hair.

Produce one character, one view, and one finished image—not a scene, collage, or multi-view sheet.
