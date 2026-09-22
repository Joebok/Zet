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

- Preserve Image 1's body proportions, pose, stance, framing, and orientation.
- Keep the body proportions, pose, stance, framing, and orientation exactly as they are.
- Preserve Image 2's face, hair, ears, apparent age, and gaze.
- Keep the face, hair, ears, and apparent age of the head exactly as they are.
- Change only the head/neck junction and the minimum style integration needed for a natural join.

# Subject Details

{{CHARACTER_ASSEMBLY_CHARACTER_REQUIREMENTS}}

{{VIEW_INSTRUCTION}}

{{ASSEMBLY_STYLE_INSTRUCTION}}

# Constraints

Do not redirect the gaze, change head scale, alter body geometry, mirror the requested view, or redesign the neck, shoulders, hair, or body beyond a natural join.

Produce one character, one view, and one finished image—not a scene, collage, or multi-view sheet.
