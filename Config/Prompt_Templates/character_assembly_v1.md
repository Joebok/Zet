# Render Task

Replace only the mannequin head and placeholder neck region of the Reference Body with the supplied fitted Character Head. Preserve all other pixels, geometry, pose, framing, clothing, exposed skin, and background from the Reference Body. Blend only the neck connection needed to form one continuous character.

{{VIEW_INSTRUCTION}}

# Locked Sources

The Reference Body owns everything below the head-replacement boundary, including body geometry, pose, stance, framing, fitment clothing, exposed skin, and background.

The Character Head is a locked fitted source. It owns the head, hair, ears, face, expression, gaze, and fitted upper neck. Preserve those features directly; do not treat the source as loose identity inspiration.

The Reference Body and Character Head must already belong to the same character phase and skin-tone specification. Do not recolor either source during assembly.

Assembly style mode: {{ASSEMBLY_STYLE_MODE}}

{{ASSEMBLY_STYLE_INSTRUCTION}}

# Assembly and Neck Connection

Remove the mannequin head and only the placeholder neck material that overlaps the fitted Character Head. Keep the Reference Body neck base fixed and attach the fitted upper neck at that point.

Blend only the narrow connection needed for a continuous anatomical neck. Do not create a seam, ring, collar, socket, hard cut, pasted edge, floating head, stretched neck, buried neck, mannequin material, or visible compositing boundary.

Do not change body geometry, pose, proportions, stance, foot placement, camera angle, crop, exposed body skin, or background. Do not change head identity, geometry, hairstyle, ears, expression, gaze, or orientation except for the rendering-only permission granted by the selected assembly style mode.

# Acceptance Criteria

- One coherent full-body character is visible, including both feet.
- Everything below the replacement boundary matches the Reference Body exactly.
- The fitted head and upper neck match the Character Head exactly, subject only to the selected assembly style mode.
- Both sources and the final render retain the same requested view and orientation.
- The neck connection is natural, continuous, and free of mannequin or compositing artifacts.
- All locked Reference Body content remains unchanged.
- No costume, prop, accessory, scene, or lighting element is added.
