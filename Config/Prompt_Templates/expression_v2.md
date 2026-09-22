<!-- ZET:BEGIN IMAGE_PROMPT_ONLY -->
# Render Task

Edit the supplied Identity Key into one standalone expression reference for {{CHARACTER_NAME}}, {{CHARACTER_PHASE}}.

Expression: {{EXPRESSION_LABEL}}.
Identity Key: {{IDENTITY_KEY_LABEL}}.

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

Change only the facial expression and the minimum supporting head, neck, or shoulder tension needed to make it believable. Preserve identity, apparent age, species, face structure, hair, ears, costume visibility, pose category, crop, view angle, lighting, and rendering style from Image 1.

# Expression Target

{{EXPRESSION_DEFINITION}}

{{EXPRESSION_DESCRIPTION_FACTS}}

{{EXPRESSION_PROMPT_INSERT_AFTER_EXPRESSION_DESCRIPTION_FACTS}}

# Identity Anchors

{{IDENTITY_PRESERVATION_CORE}}

{{EXPRESSION_PROMPT_INSERT_AFTER_IDENTITY_PRESERVATION_CORE}}

{{IDENTITY_PRESERVATION_FACE}}
{{EXPRESSION_PROMPT_INSERT_AFTER_IDENTITY_PRESERVATION_FACE}}

{{IDENTITY_PRESERVATION_EYES}}
{{IDENTITY_PRESERVATION_HAIR}}
{{EXPRESSION_PROMPT_INSERT_AFTER_IDENTITY_PRESERVATION_HAIR}}

{{IDENTITY_PRESERVATION_EARS}}
{{EXPRESSION_PROMPT_INSERT_AFTER_IDENTITY_PRESERVATION_EARS}}

{{COSTUME_IDENTITY_RULES}}
{{EXPRESSION_PROMPT_INSERT_AFTER_COSTUME_IDENTITY_RULES}}

# Constraints

{{NEGATIVE_GUIDANCE_EXPRESSION}}

{{EXPRESSION_PROMPT_INSERT_AFTER_NEGATIVE_GUIDANCE_EXPRESSION}}

Match Image 1's visible body extent. Do not create a full-body image unless Image 1 is full-body. Do not add a scene, action pose, dramatic head tilt, props, text, labels, a sheet, collage, diagram, or multi-view layout.
