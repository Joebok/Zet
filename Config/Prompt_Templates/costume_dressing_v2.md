<!-- ZET:BEGIN IMAGE_PROMPT_ONLY -->
# Render Task

Edit the supplied assembled character into one finished full-body costume reference of {{CHARACTER_NAME}}, {{CHARACTER_PHASE}}, wearing {{COSTUME_NAME}}.

Requested body view: {{BODY_VIEW_DISPLAY}}.
Requested head view: {{HEAD_VIEW_DISPLAY}}.

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

{{LOCAL_COSTUME_REFERENCE_GUIDANCE}}

{{LOCAL_CANONICAL_ART_STYLE}}

Replace only the generic fitment clothing, jewelry, equipment, and footwear controlled by the costume. Preserve identity, anatomy, body proportions, pose, body and head orientation, camera, and crop from Image 1. The costume conforms to the existing body; the body does not change to fit the costume.

Preserve the dimensional facial planes, skin variation and hair detail of Image 1 at the output scale. Render the new costume in the same visual treatment, distinguishing woven cloth and seams, weighted folds, leather grain and creases, metal highlights and gemstone reflections where these materials are specified. Do not simplify the face or exposed body while adding the costume. Supporting design images control their assigned designs and visible details, not the overall rendering style.

# Costume

{{COSTUME_DESCRIPTION_FACTS}}

{{COSTUME_VIEW_HEADING}}

{{COSTUME_DESCRIPTION_VIEW_OVERRIDES}}

{{EQUIPMENT_HEADING}}

{{EQUIPMENT_JEWELRY_PROPS_FACTS}}

{{EQUIPMENT_VIEW_HEADING}}

{{EQUIPMENT_JEWELRY_PROPS_VIEW_OVERRIDES}}

{{COSTUME_DESCRIPTION_VIEW_SUPPRESSION}}

# Pose, Contact, and Background

{{BODY_ORIENTATION_LOCK}}

{{HEAD_ORIENTATION_LOCK}}

{{FOOTWEAR_CONTACT}}

<!-- ZET:BEGIN IMAGE_PROMPT_ONLY -->
{{BACKGROUND_TREATMENT}}
<!-- ZET:END IMAGE_PROMPT_ONLY -->

# Constraints

Do not leave generic fitment clothing visible. Do not add unlisted garments, jewelry, equipment, weapons, or props. Do not change the character into a fashion or action pose, mirror the view, crop the body, or create a scene, collage, diagram, or multi-view sheet.
