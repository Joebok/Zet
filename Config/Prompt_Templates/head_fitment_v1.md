Render a standalone head-and-neck fitment module matching the Character Head source. Preserve the entire source head through the complete jaw and chin. Only newly generated or mask-editable neck pixels beneath the existing jaw may change.

{{VIEW_INSTRUCTION}}

HEAD-FITMENT CHARACTER REFERENCE IMAGE

The image should:
 
 * be head and neck only 
 * preserve the complete face, jaw, chin, ears, hair, expression, age presentation, and rendering of the referenced head image.
 * have transparent background

This is a technical fitment asset, not a portrait crop.

SOURCE RENDERING LOCK

Preserve the complete visible rendering of the Character Head source through the entire jaw and chin. This includes identity, feature geometry, apparent age, facial maturity, asymmetry, shading, brushwork, and surface detail exactly as visible in the source.

Do not beautify, idealize, smooth, rejuvenate, cosmetically lift, or otherwise reinterpret the facial anatomy or rendering.

The source image already represents the correct canonical character, age phase, hairstyle, and rendering style. Preserve that existing style and finish; do not reapply a generalized art style. Do not reinterpret the head from the textual character description. Character-template text identifies visible features that must survive the fitment and must not override the source.

Reference roles:

- The attached Head-Image reference, or explicit legacy headshot override, is the Character Head source.
- The attached headshot reference is the Character Head source. This remains supported for backward-compatible legacy jobs.
- The attached body-reference image is the Reference Body source.

Do not regenerate, redesign, or reinterpret the face. Treat the entire Character Head source through the complete jaw and chin as visually final. Only extend, transform, or fit neck pixels beneath the existing jaw.

For a masked-local edit, the semantic mask is authoritative: protected head pixels must be copied from the source after rendering, editable pixels are confined to the upper neck, and removed pixels remain transparent. Never fall back to a full-frame reconstruction.

NECK FITMENT

Use the Reference Body only to determine the fitted neck’s natural width, axis, and cut position.

Cut the image across the upper neck, well above where the neck begins to widen into the trapezius or shoulders. Only the upper neck beneath the jaw is visible.

Do not lengthen the neck to create space beneath the hairstyle, and do not move the neck cut downward to expose it.

Preserve the complete hair silhouette from the Character Head source. Hair may overlap the neck, extend below the neck cut into transparent space, or obscure the cut edge. The cut edge may remain visible where the hairstyle naturally leaves it uncovered.

The output fails if any shoulder slope, trapezius, collarbone, chest, torso, or body geometry is visible, or if the neck widens into the shoulders.

The Character Head MUST NOT BE ROTATED.

Do not change the Character Head view, camera orientation, head shape, face, hair, ears, eye visibility, nose visibility, skin tone, expression, or identity.

Render the fitted neck with a finish continuous with the Character Head source. Any blending or repainting must occur exclusively on the editable neck beneath the jaw; do not blend across the jaw edge, chin, lower face, ears, or hair.

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

Good output:
- The image only has the Character Head and fitted character neck.
- The entire Character Head matches its source without alteration; all fitment changes are confined to neck pixels beneath the existing jaw.
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

The final image should look like the selected Character Head source with its neck fitted for the selected Reference Body neck connection point, with only the fitted head-and-neck module visible.
