# Costume Template Instructions

Use this manual to convert an approved costume design and reference images into a Zet `Costume_*.md` file. Write compact image-generation instructions.

## Rules for the whole file

- Preserve every `ZET:BEGIN` and `ZET:END` marker exactly. Do not add, remove, rename, or reorder markers.
- Preserve and fill the costume metadata fields.
- Use short visual facts and direct imperatives, normally one fact per bullet.
- Do not write story, mood, personality, action, or decorative narrative.
- Distinguish observation from inference. Leave optional content empty when the references do not support it.
- “Left” and “right” mean the character's anatomical sides. Clarify viewer-side reversal when needed.
- Put stable design facts in `*_FACTS`; put only view-dependent visibility, overlap, and silhouette in `*_VIEW_*`.
- Do not describe the wearer's body or face except where a garment's attachment or occlusion requires it.

## Metadata

Costume Name is the dashboard and pipeline label. Keep any existing footwear and contact fields factual and concise. Metadata should identify the design, not add scene behavior.

## Costume design sections

### `COSTUME_DESCRIPTION_FACTS` — required

Used by costume-dressing. Record the complete stable garment design: layers, silhouette, colors, materials, construction, closures, trim, wear, fit, footwear, and attachment points. State explicit absences when they prevent common unwanted additions. Do not include camera direction or pose.

### `COSTUME_DESCRIPTION_VIEW_{VIEW}` — optional for all eight views

Used by costume-dressing for the selected body view. Record only view-dependent visibility, overlap, foreshortening, rear construction, side profile, and silhouette. Leave empty when the stable facts are sufficient. Do not restate the view orientation.

## Equipment, jewelry, and props

### `EQUIPMENT_JEWELRY_PROPS_FACTS` — optional

Used by costume-dressing. Inventory every stable worn or carried item, including jewelry, weapons, tools, containers, and props. Give anatomical side, attachment point, scale, material, color, and whether the item is present or absent. Do not hide equipment inside garment prose.

### `EQUIPMENT_JEWELRY_PROPS_VIEW_{VIEW}` — optional for all eight views

Used by costume-dressing for the selected body view. Describe only view-specific item visibility, overlap, side reversal, and occlusion. Do not duplicate the inventory.

## Identity sections

### `COSTUME_IDENTITY_RULES` — optional

Used by expression and character-source workflows. List the few costume traits that must remain unchanged when the face, expression, or source image changes. Focus on recognizable design anchors rather than repeating the full specification.

### `SCENE_COSTUME_IDENTITY` — optional

Used by scene building. Give a compact, complete description that keeps the costume recognizable at scene scale. Include key colors, silhouette, layers, footwear, and signature equipment. Exclude camera view, pose, scene action, and pipeline instructions.

## Final completeness check

Verify that the name is correct, `COSTUME_DESCRIPTION_FACTS` is complete, side-specific items use anatomical left/right, equipment is in the equipment sections, optional sections are empty rather than invented, no character identity or narrative was added, and every marker is unchanged.
