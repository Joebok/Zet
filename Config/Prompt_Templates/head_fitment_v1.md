HEAD-FITMENT CHARACTER REFERENCE IMAGE.

Character: {{CHARACTER_NAME}}, {{CHARACTER_PHASE}}.
Canonical Art Style: {{CANONICAL_ART_STYLE}}
Requested body view: {{BODY_VIEW_TOKEN}}.
Requested head view: {{HEAD_VIEW_TOKEN}}.

All necessary information is in these instructions and in the attached reference images.
Follow these instructions exactly.

# INSTRUCTIONS

Render a head shot only image exactly like the Character Head except that the Character neck should be adjusted to fit the Reference Body.

The image should:
 
 * be head and neck only 
 * preserve identity, expression, hair, and all features of the referenced head image above the neck.
 * have transparent background

The image should NOT:

* Have any part of the body below the neck

Reference roles:

- The attached headshot reference is the Character Head source.
- The attached body-reference image is the Reference Body source.

CANONICAL ART STYLE DIRECTIVE

Render the fitted Character Head and neck in the Canonical Art Style listed above.

If the Character Head source uses a different art style, repaint only the rendering style into the Canonical Art Style while preserving the Character Head identity, expression, view angle, face shape, facial proportions, hair silhouette, ear shape, eye color, skin tone, and neck fitment.

The art-style conversion must not redesign the character.
The art-style conversion must not change the head view, camera angle, face identity, hairstyle, ears, expression, age, species, or neck geometry.

**Neck-column anchor**: the midpoint of the visible neck column, clearly above the torso and shoulder mass, halfway between the underside of the jaw/skull and the base of the neck where the neck begins to widen into the shoulders. This anchor is on the neck itself, not on the collarbone, chest, shoulders, or torso.

Neck-column anchor — controls where the head/neck module is centered and vertically placed.

Base-neck docking shape — controls the lower cut/join where the fitted neck will attach back to the body.

Fit the Character Neck to the Reference Body’s neck-column anchor and base-neck docking shape. The neck-column anchor is the midpoint of the visible neck column, clearly above the torso and shoulder mass. Use it to control neck length, width, angle, and vertical placement so the fitted head-and-neck module can join cleanly to the body-reference neck.

The Character Neck may be slightly adjusted so it could blend seamlessly into the Reference Body Neck-column anchor.

CANONICAL ART STYLE REINFORCEMENT

The final fitted head-and-neck module must be rendered in the Canonical Art Style listed at the top of this prompt.

If the Character Head source is not already in the Canonical Art Style, convert only the rendering style. Preserve the Character Head’s identity, expression, face shape, facial proportions, eye color, gaze, hair silhouette, ear shape, skin tone, view angle, camera orientation, and fitted neck geometry.

Do not let the art-style conversion become a redesign.

ART-STYLE CONVERSION BUDGET

Allowed style changes:
- convert line quality, brush texture, shading, rendering finish, and reference-sheet presentation into the Canonical Art Style
- harmonize the fitted neck with the head in the same Canonical Art Style

Forbidden style changes:
- changing facial structure
- changing expression
- changing eye shape or eye color
- changing hair shape, length, part, or silhouette
- changing ear shape, size, angle, or visibility
- changing the requested view angle
- changing the fitted neck length, width, angle, or docking shape

The Character Head MUST NOT BE ROTATED.

Do not change the Character Head view, camera orientation, head shape, face, hair, ears, eye visibility, nose visibility, skin tone, expression, or identity.

Render all visible head-and-neck features in the Canonical Art Style listed above.

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
- mannequin head
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
