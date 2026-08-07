# Render Task

Replace the mannequin head and placeholder neck of the Reference Body using the supplied Character Head image.

The Character Head may be a natural head-and-shoulders or limited-bust reference. Its neck, shoulders, upper torso, clothing, jewelry, accessories, and transparent surrounding area provide context only. Do not copy those contextual elements into the final image.

Preserve the established character identity, body proportions, pose, framing, clothing, background, and requested view.

Make only localized assembly corrections. Do not redesign either source.

Produce one coherent full-body character in one {{VIEW_LABEL}}.

{{VIEW_INSTRUCTION}}

# HEAD PRESERVATION LOCK

The supplied Character Head is already the finished rendering of the character's head.

Treat everything above the neck attachment as finished Character Head content, not as content to regenerate.

Preserve the supplied Character Head's facial rendering, apparent age and facial maturity, face and skull geometry, skin texture, surface detail, asymmetry, expression, gaze, hairstyle design, ears, facial-plane direction, feature visibility, and head orientation.

Do not re-render, repaint, rejuvenate, beautify, smooth, reinterpret, or redesign the face.

The face, skull, jaw, chin, ears, and main hairstyle mass are not reconstruction regions.

Only the neck attachment and immediate hair/neck/shoulder boundary are adaptive regions.

# RIGID HEAD REGISTRATION

Treat the supplied Character Head above the neck attachment as a finished visual asset.

To fit it to the Reference Body, the permitted geometric operations on the preserved head are:

- uniform scaling;
- horizontal translation;
- vertical translation.

These operations apply to the preserved head as a whole.

Do not solve scale or placement by regenerating, warping, repainting, reshaping, or semantically reinterpreting the head.

Scaling means resizing the existing rendered head, not producing a newly interpreted version of that head at a different size.

# Locked Sources

The Reference Body controls the overall body geometry, body proportions, pose, stance, overall shoulder placement, width and silhouette, framing, fitment clothing, exposed body skin below the neck region, background, requested view, camera orientation, and the correct anatomical scale and placement of the head relative to the body.

The mannequin head is the geometric fitment guide for final skull scale and position.

The Character Head controls character identity, head shape, skull shape, face, apparent age and maturity, species, expression, gaze, hairstyle, ears, skull orientation, facial-plane direction, feature visibility, head orientation, facial rendering, and surface detail.

Everything above the local attachment region is preserved Character Head content, not material to regenerate.

Neither source is pixel-locked inside the adaptive neck/junction region.

The face, jaw, chin, ears, skull, expression, and main hairstyle mass of the Character Head are outside the adaptive region. The Reference Body's overall shoulder geometry and body silhouette are also outside it.

Do not require literal preservation of imperfect neck edges, attachment geometry, hair intersections, shading transitions, or placeholder material.

Preserve the hairstyle's defining length, shape, part, asymmetry, volume, and identity. Adjust only local strand placement and overlap where necessary for the hair to rest naturally around the assembled neck and shoulders.

Preserve the ear shape and visibility shown by the Character Head. Do not invent or expose an ear that is naturally occluded, hide an ear that is visible, or convert pointed ears into human ears.

The Reference Body and Character Head must already belong to the same character phase and skin-tone specification. Do not broadly recolor or globally reinterpret either source.

# Head-to-Body Scale

The Reference Body controls final head scale, placement, and head-to-body proportion.

The mannequin skull is the authoritative geometric fitment guide.

Uniformly scale and position the preserved Character Head so its anatomical skull matches the mannequin skull's crown-to-chin height, approximate skull width and volume, and anatomical position as closely as possible.

Judge skull scale only. Hair, ears, and other projecting features may extend beyond the mannequin silhouette and are not included when measuring head size.

The Character Head controls skull shape, face, identity, hairstyle, ears, and facial detail, but its absolute source-image size is not authoritative.

Ignore the apparent scale created by portrait cropping, shoulders, upper torso, clothing, transparent margins, or source framing. Do not preserve the Character Head's apparent portrait size.

Scale the Character Head uniformly; do not reshape it.

# CONFLICT PRIORITY

Head preservation has higher priority than exact mannequin-skull matching.

Match the mannequin skull as closely as possible using rigid uniform scaling and translation of the supplied Character Head.

If exact skull matching would require changing facial geometry, apparent age, facial maturity, facial rendering, skin texture, skull shape, hairstyle design, ears, expression, gaze, or feature visibility, preserve the Character Head instead.

A small residual scale difference is preferable to facial reinterpretation, regeneration, or de-aging.

# ASSEMBLY PROCEDURE

Perform the assembly conceptually in this order:

1. Register the preserved Character Head to the mannequin skull using uniform scaling and translation only.
2. Lock the registered head.
3. Remove all visible mannequin-head and placeholder-neck material.
4. Construct the natural neck connection and immediate boundary transition beneath the locked head.

Do not revisit, repaint, or regenerate the locked head while repairing the junction.

## Style Mode

{{ASSEMBLY_STYLE_INSTRUCTION}}

# Assembly and Neck Connection

Construct a natural anatomical transition between the locked Character Head and Reference Body.

Adjust only as needed:

- local neck width;
- neck taper;
- neck attachment position;
- jaw-to-neck transition;
- neck-to-shoulder transition;
- visible neck length;
- local skin transition;
- local shading transition;
- hair overlap at the immediate junction;
- small boundary mismatches.

Keep changes localized to the neck and immediate hair/neck/shoulder junction.

Final anatomical continuity takes priority over literal preservation of source neck pixels and local placeholder geometry, but never over the locked Character Head's facial identity, apparent age, maturity, facial geometry, texture, expression, gaze, ears, or main hairstyle design.

The head must not float, appear pasted on, sink into the shoulders, or connect through an unnaturally long, narrow, wide, twisted, cylindrical, or sharply cut neck.

Do not leave a visible seam, mannequin residue, collar, socket, ring artifact, abrupt material change, or mismatched shading around the connection.

# Global Preservation Rules

Do not change the overall body shape, body proportions, pose, stance, foot placement, camera angle, crop, clothing, or background.

Do not change the character's facial identity, age phase, species, hairstyle design, ear design, expression, gaze, head orientation, or feature visibility.

Do not add costume elements, props, accessories, scenery, text, or new lighting effects.

# Acceptance Criteria

- One coherent full-body character is visible, including both feet.
- The final character faithfully preserves the Reference Body's overall body, pose, proportions, stance, framing, clothing, background, and requested view.
- The face is the supplied Character Head rendering at the required assembled scale, not a newly interpreted or regenerated version of that face.
- Apparent age, facial texture, facial maturity, facial geometry, asymmetry, and surface detail do not change.
- The final character skull matches the mannequin skull's anatomical scale and position as closely as possible without altering the preserved Character Head.
- The final head faithfully preserves the Character Head's identity, face, age phase, species, expression, gaze, hairstyle design, ears, orientation, and visible-feature pattern.
- The head, neck, hair, shoulders, and exposed skin form one anatomically natural and visually continuous assembly.
- No mannequin material, source seam, pasted edge, mismatched shading, floating head, stretched neck, buried neck, or ring/socket artifact remains visible.
- The skull, facial plane, neck, and torso preserve the supplied shared orientation; there is no independent head turn.
- In rear-biased views, the final image does not reveal more of the face than the supplied Character Head.
- Local assembly corrections do not cause broader body, head, costume, view, or background drift.
- No costume elements, props, accessories, scenery, text, or new lighting effects are added.
