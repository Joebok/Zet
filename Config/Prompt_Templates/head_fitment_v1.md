Render a standalone head-and-neck fitment module matching the Character Head source, with no changes above the jawline other than art-style conversion if required. Only the neck geometry may change.

{{VIEW_INSTRUCTION}}

HEAD-FITMENT CHARACTER REFERENCE IMAGE

The image should:
 
 * be head and neck only 
 * preserve identity, expression, hair, and all features of the referenced head image above the neck.
 * have transparent background

This is a technical fitment asset, not a portrait crop.

Reference roles:

- The attached headshot reference is the Character Head source.
- The attached body-reference image is the Reference Body source.

CANONICAL ART STYLE DIRECTIVE

Render the image in the Canonical Art Style: {{CANONICAL_ART_STYLE}}

If the Character Head source uses a different art style, repaint only the rendering style into the Canonical Art Style while preserving the Character Head identity, expression, view angle, face shape, facial proportions, hair silhouette, ear shape, eye color, skin tone, and neck fitment.

The art-style conversion must not redesign the character.
The art-style conversion must not change the head view, camera angle, face identity, hairstyle, ears, expression, age, species, or neck geometry.

NECK FITMENT

Use the Reference Body only to determine the fitted neck’s natural width, axis, and cut position.

Cut the image across the upper neck, well above where the neck begins to widen into the trapezius or shoulders. Only the upper neck beneath the jaw is visible.

Do not lengthen the neck to create space beneath the hairstyle, and do not move the neck cut downward to expose it.

Preserve the complete hair silhouette from the Character Head source. Hair may overlap the neck, extend below the neck cut into transparent space, or obscure the cut edge. The cut edge may remain visible where the hairstyle naturally leaves it uncovered.

The output fails if any shoulder slope, trapezius, collarbone, chest, torso, or body geometry is visible, or if the neck widens into the shoulders.

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
- changing the fitted neck length, width, angle, or cut plane

The Character Head MUST NOT BE ROTATED.

Do not change the Character Head view, camera orientation, head shape, face, hair, ears, eye visibility, nose visibility, skin tone, expression, or identity.

Render all visible head-and-neck features in the Canonical Art Style listed above.

The only allowed adjustment is to align the Character Head and Character Neck to the Reference Body neck connection point, then suppress the Reference Body and any body/torso material, leaving only a fitted character head-and-neck image.

The output is a standalone head-and-neck module. Only the head and upper neck are rendered. The image ends at the neck cut plane.

Do not lengthen the neck merely to expose its lower cut edge beneath the hair. The cut edge may remain visible where the hairstyle naturally leaves it uncovered.

Reference Body is alignment-only.

Use the Reference Body only as geometric alignment data for neck width, neck axis, and neck cut position. Do not render any Reference Body geometry.

Do not render any part of the Reference Body.
Do not render any mannequin stand.

View-drift failure rule:

The output is incorrect if it uses any view angle, camera orientation, or view instruction other than the requested Character Head view.

Reference Body view instruction:
{{BODY_VIEW_INSTRUCTION}}

THREE-QUARTER ORIENTATION LOCK

If the requested view is a three-quarter view, treat the Character Head and fitted neck as one rigid head-and-neck module.
The face plane, nose direction, eye gaze, ears, jaw, skull, and neck axis all share the same requested three-quarter orientation.
The Reference Body controls the fitted neck’s width, axis, and cut position; the Character Head controls the head pose, face, hair, expression, and identity.
Do not turn the eyes toward the viewer, twist the neck, mirror the head, or drift into a direct front, direct back, or profile view.

Good output:
- The image only has the Character Head and fitted character neck.
- The Character Head matches the headshot source image except for small neck adjustment for smooth fitment.
- Hair matches the source in shape, color, texture, orientation, and visibility.
- Eyes match the source in shape, color, texture, orientation, and visibility where visible.
- Ears match the source in shape, orientation, and visibility.
- Nose matches the source in shape, orientation, and visibility where visible.

Bad output:
- The image does not match the Character Head.
- Any portion of the Reference Body or mannequin stand is present.
- The Character Head is rotated, re-posed, mirrored, or converted to a different view.
- Hair, ears, face, skin tone, or camera orientation drift away from the Character Head source.

{{SECTION:HEAD_FITMENT_RENDERING_RULES}}

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
