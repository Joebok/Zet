HEAD-FITMENT CHARACTER REFERENCE IMAGE.

Character: {{CHARACTER_NAME}}, {{CHARACTER_PHASE}}.
Requested body view: {{BODY_VIEW_TOKEN}}.
Requested head view: {{HEAD_VIEW_TOKEN}}.

All necessary information is in these instructions and in the attached reference images.
Follow these instructions exactly.

Render an image exactly like the Character Head except that the Character neck should be fitted to the Reference Body.

Reference roles:

- The attached headshot reference is the Character Head source.
- The attached body-reference image is the Reference Body source.

The Character Neck may be slightly adjusted so it could blend seamlessly into the Reference Body neck connection point.

The Character Head MUST NOT BE ROTATED.

Do not change the Character Head view, camera orientation, head shape, face, hair, ears, eye visibility, nose visibility, skin tone, or painterly style.

The only allowed adjustment is to align the Character Head and Character Neck to the Reference Body neck connection point, then suppress the Reference Body and any body/torso material, leaving only a fitted character head-and-neck image.

The output must be a standalone head-and-neck module.

The image only includes:
- Character Head
- character hair
- character ears
- visible character face if visible in the Character Head source view
- fitted character neck
- optional subtle neck connection edge/guide only if required for downstream fitment

The image must not include:
- shoulders
- torso
- bust
- bust wrap
- chest
- upper body
- mannequin body
- mannequin stand
- gray mannequin head
- Reference Body geometry
- fitment shell
- costume
- clothing
- scene background

Reference Body is alignment-only.

Use the Reference Body only for fitment reference geometry:
- neck scale
- neck angle
- neck length
- neck width
- connection height
- base-neck docking position

Do not render any part of the Reference Body.
Do not render any mannequin torso from the Reference Body.
Do not render any mannequin stand.
Remove any shoulders, chest, bust wrap, torso, body mannequin geometry, gray mannequin head, or body-source upper-body material from the final output.

View-drift failure rule:

The output is incorrect if it uses any view angle, camera orientation, or view instruction other than the requested Character Head view.

Head view instruction:
{{HEAD_VIEW_INSTRUCTION}}

Reference Body view instruction:
{{BODY_VIEW_INSTRUCTION}}

Good output:
- The image only has the Character Head and fitted character neck.
- The Character Head matches the headshot source image except for small neck adjustment for smooth fitment.
- Hair matches the source in shape, color, texture, orientation, and visibility.
- Eyes match the source in shape, color, texture, orientation, and visibility where visible.
- Ears match the source in shape, orientation, and visibility.
- Nose matches the source in shape, orientation, and visibility where visible.
- There is no part of a body, mannequin, torso, bust, shoulders, chest, fitment shell, clothing, costume, or stand.

Bad output:
- The image does not match the Character Head.
- Any portion of the Reference Body or mannequin stand is present.
- Any shoulders, torso, bust, bust wrap, chest, upper body, or body-source upper-body material is present.
- The Character Head is rotated, re-posed, mirrored, or converted to a different view.
- Hair, ears, face, skin tone, or camera orientation drift away from the Character Head source.

{{SECTION:FITMENT_RENDERING_RULES}}

{{SECTION:GENERAL_DESCRIPTION_FACTS}}

{{SECTION:HEAD_DESCRIPTION_FACTS}}

{{SECTION:HEAD_DESCRIPTION_VIEW_{VIEW}}}

{{SECTION:HAIR_DESCRIPTION_FACTS}}

{{SECTION:HAIR_DESCRIPTION_VIEW_{VIEW}}}

{{SECTION:IDENTITY_PRESERVATION_CORE}}

{{SECTION:IDENTITY_PRESERVATION_FACE}}

{{SECTION:IDENTITY_PRESERVATION_HAIR}}

{{SECTION:IDENTITY_PRESERVATION_EARS}}

Negative constraints:

{{SECTION:NEGATIVE_GUIDANCE_GENERAL}}

{{SECTION:NEGATIVE_GUIDANCE_JOB_SPECIFIC}}

Do not render: generic replacement face, wrong species markers, human ears, rounded ears, missing ears, hidden ears, wrong eye color, wrong hair silhouette, long hair, curly hair, helmet hair, changed body type, changed costume, changed camera angle, portrait crop, bust shot, waist-up framing, narrative scene, dramatic lighting, props, weapons, extra accessories, seductive pose, fashion pose, pin-up pose.

The final image should look like the selected Character Head source with its neck fitted for the selected Reference Body neck connection point, with only the fitted head-and-neck module visible.
