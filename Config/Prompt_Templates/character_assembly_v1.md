FULL-CHARACTER ASSEMBLY IMAGE.

Character: {{CHARACTER_NAME}}, {{CHARACTER_PHASE}}.
Canonical Art Style: {{CANONICAL_ART_STYLE}}
Requested body view: {{BODY_VIEW_TOKEN}}.
Requested head view: {{HEAD_VIEW_TOKEN}}.

PRIMARY OBJECTIVE — HEAD-TO-BODY ASSEMBLY

Create one complete full-body character render by placing the Character Head source onto the Reference Body source.

The Reference Body is the locked body source.
The Character Head is the locked head/identity source.

Replace the mannequin head / placeholder head on the Reference Body with the Character Head.
The final result should look like one naturally rendered character, not a collage, not a pasted cutout, not a mannequin, and not a reference sheet.

Most important rule:
Preserve the Reference Body exactly except where the mannequin/placeholder head must be replaced by the Character Head.
The Reference Body is not a style suggestion.
The Character Head is not a loose inspiration image.
Use them as direct source references for the specified regions.

REFERENCE BODY CONTROLS

The Reference Body controls the body only.
Do not preserve the mannequin head, placeholder head, gray head, simplified face, or fitment-shell head from the Reference Body.

Use the Reference Body as the authority for:
- full-body pose
- body proportions
- body silhouette
- stance and foot placement
- camera angle
- requested body view
- crop and full-body framing
- shoulder position
- neck base / head attachment point
- costume placement on the body, if already present

Do not re-pose the Reference Body.
Do not rotate the body.
Do not change the body type.
Do not change the stance.
Do not change the camera angle.
Do not crop the feet.
Do not turn the image into a portrait, bust shot, waist-up image, collage, or split reference sheet.

CHARACTER HEAD CONTROLS

Use the Character Head source as the authority for:
- face identity
- head shape
- facial proportions
- eye color and gaze
- hair silhouette and hair placement
- ear shape and visibility
- natural neck shape
- skin tone and texture

NECK CONNECTION RULE

Use the Reference Body neck base as the anchor point.
Use the Character Head’s fitted natural neck as the replacement neck/head unit.
Join them at the natural neck connection just above the torso.

The neck must look continuous and anatomical.
The head must not float above the body.
The neck must not be too long.
The neck must not be buried into the shoulders.
The transition must not show a seam, ring, collar, socket, gray material, mannequin material, hard cut, pasted edge, or visible compositing boundary.

Do not rotate the Character Head.
Do not mirror the Character Head.
Do not change the head view.
Do not redesign the face.
Do not change the hairstyle.
Do not hide the elf ears unless the source view already does so.
Do not make the head look like a mannequin head.

ASSEMBLY PRIORITY

This is not a new pose generation task.
This is not a costume redesign task.
This is not a generic character illustration task.

The task is to assemble the supplied Character Head onto the supplied Reference Body while preserving both sources:
- body, stance, scale, view, and framing from the Reference Body
- head, face, hair, ears, neck, and identity from the Character Head

The final image must be a single coherent full-body character render in the requested view.

ALLOWED CHANGES

Only change what is necessary to:
- remove the mannequin/placeholder head from the Reference Body
- attach the Character Head naturally at the neck
- harmonize skin tone between head and exposed body skin

FORBIDDEN CHANGES

Do not change:
- body pose
- body proportions
- stance
- foot placement
- camera angle
- body view
- crop/framing
- head view
- face identity
- hairstyle
- ear shape
- character age
- character species

Body view instruction:
{{BODY_VIEW_INSTRUCTION}}

Head view instruction:
{{HEAD_VIEW_INSTRUCTION}}

Good output:
- One complete full-body character image.
- Body proportions and stance match the Reference Body.
- Head, face, hair, ears, and fitted neck match the Character Head source.
- The head is cleanly attached at the neck.
- Identity anchors and clothing match the character template.
- Full body is visible, including feet.
- skin tone and texture of head clearly matches the exposed skin of body

Bad output:
- Head is rotated, mirrored, re-posed, or changed to a different view.
- Body proportions, stance, or requested view drift away from the Reference Body.
- Character appears as a mannequin, gray fitment shell, or technical modesty render.
- Head and body look pasted together without a clean neck connection.
- Image becomes a portrait, bust shot, waist-up shot, collage, reference sheet, or two separate images.

IMPORTANT — TEMPLATE DETAILS ARE SECONDARY TO SOURCE PRESERVATION

The character template below is used to preserve identity, costume, and species details.
It must not override the supplied Reference Body pose, proportions, stance, camera angle, or full-body framing.
It must not override the supplied Character Head identity, view, hair, ears, face, or neck fitment.

~{{SECTION:GENERAL_DESCRIPTION_FACTS}}

~{{SECTION:BODY_DESCRIPTION_FACTS}}

~{{SECTION:BODY_DESCRIPTION_VIEW_{VIEW}}}

~{{SECTION:HEAD_DESCRIPTION_FACTS}}

~{{SECTION:HEAD_DESCRIPTION_VIEW_{VIEW}}}

~{{SECTION:HAIR_DESCRIPTION_FACTS}}

~{{SECTION:HAIR_DESCRIPTION_VIEW_{VIEW}}}

{{SECTION:IDENTITY_PRESERVATION_CORE}}

{{SECTION:IDENTITY_PRESERVATION_FACE}}

{{SECTION:IDENTITY_PRESERVATION_HAIR}}

{{SECTION:IDENTITY_PRESERVATION_EARS}}

{{SECTION:IDENTITY_PRESERVATION_BODY}}

Negative constraints:

{{SECTION:NEGATIVE_GUIDANCE_GENERAL}}

{{SECTION:NEGATIVE_GUIDANCE_JOB_SPECIFIC}}

Do not render: mannequin head, gray head, fitment shell, tank top, compression shorts, underwear, missing costume, generic replacement face, wrong species markers, human ears, rounded ears, hidden ears, wrong eye color, wrong hair silhouette, long hair, curly hair, changed body type, changed camera angle, portrait crop, bust shot, waist-up framing, missing feet, cut-off feet, narrative scene, dramatic lighting, extra props, extra weapons, seductive pose, fashion pose, pin-up pose, collage, split image, reference sheet.

The final image should look like the selected full character in the requested view, assembled from the Reference Body and Character Head sources.
