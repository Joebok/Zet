# Costume Template Instructions

Use this manual to convert costume reference images and user notes into a Zet `Costume_*.md` file. Write compact image-generation instructions grounded in the supplied evidence. A reference caption describes what that image is meant to show; it is not itself costume canon unless the image or user notes support it.

## Rules for the whole file

- Preserve every `ZET:BEGIN` and `ZET:END` marker exactly. Do not add, remove, rename, or reorder markers.
- Preserve and fill the costume metadata fields.
- Use short visual facts and direct imperatives, normally one fact per bullet. Keep one independently taggable fact on each line.
- Do not write story, mood, personality, action, or decorative narrative.
- Distinguish observation from inference. Leave optional content empty when the references do not support it.
- Record canonical sides as `anatomical-left` or `anatomical-right`; generation prompts resolve these to screen-left/screen-right in front and back views, and near-side/far-side in three-quarter and profile views.
- Mark a side-dependent line with `<!-- ZET:SPATIAL asymmetry -->` for garment or equipment geometry, or `<!-- ZET:SPATIAL fixed -->` for a physically bound feature such as an earring. Put the annotation after any leading view tag.
- Fixed-feature annotations require an explicit view tag or section `ZET:VIEW_DEFAULT`. Use `state=partial`, `state=occluded`, or `state=hidden` when that state applies to the tagged views. Split facts with different visibility into separate bullets.
- Do not use bare left/right in spatial facts. Keep facing direction separate from side placement; a front-left three-quarter view faces screen-left while its anatomical-left side is near.
- Put stable design facts in `*_FACTS`; put view-dependent visibility, overlap, and silhouette in `*_VIEW_OVERRIDES`.
- Untagged facts intentionally apply to all views unless their section declares `ZET:VIEW_DEFAULT`.
- Put a leading view tag on an individual bullet whenever that fact applies only to some views, for example `* [f,front_3q] ...`. Use the documented aliases or explicit views; do not author a complete eight-view checklist when only one view has distinct information.
- A section may declare `<!-- ZET:VIEW_DEFAULT rearish -->` to make untagged lines apply only to that view group. An explicit line tag overrides the default; `[all]` explicitly restores all views.
- Use `<!-- ZET:VIEW_DOMAIN body -->` inside costume sections. Explicit `[head:...]` tags remain available for head-visible items such as earrings.
- Use `<!-- ZET:VIEW_DEFAULT ... -->` for section defaults and `<!-- ZET:CANON_ONLY -->` for documentation excluded from generation prompts.
- Do not describe the wearer's body or face except where a garment's attachment or occlusion requires it.

## Metadata

Costume Name is the dashboard and pipeline label. Keep any existing footwear and contact fields factual and concise. Metadata should identify the design, not add scene behavior.

## Costume design sections

### `COSTUME_DESCRIPTION_FACTS` — required

Used by costume-dressing. Record supported stable garment facts: layers, silhouette, colors, materials, construction, closures, trim, wear, fit, footwear, and attachment points. Use line tags or a section default for visibility-conditioned facts even in `*_FACTS`; the section name means stable design information, not that every line is visible in every view. State explicit absences only when supported or needed to prevent a likely addition. Do not include camera direction or pose. Keep worn and carried item inventories in `EQUIPMENT_JEWELRY_PROPS_FACTS` rather than duplicating them here.

### `COSTUME_DESCRIPTION_VIEW_OVERRIDES` — optional; tag only views that need overrides

Used by costume-dressing. Add tagged bullets only for view-dependent visibility, overlap, foreshortening, rear construction, side profile, and silhouette. Leave empty when the stable facts are sufficient or the references do not establish a view-specific difference. Do not invent unseen rear or side construction. Put anti-drift guidance in `COSTUME_DESCRIPTION_VIEW_SUPPRESSION`.

### `COSTUME_DESCRIPTION_VIEW_SUPPRESSION` — optional

Used by costume-dressing to prevent view rotation or other costume drift. Add concise tagged prohibitions only for likely failures, such as exposing a front closure in a rear view. Keep positive construction facts in `COSTUME_DESCRIPTION_FACTS` or `COSTUME_DESCRIPTION_VIEW_OVERRIDES`.

## Equipment, jewelry, and props

### `EQUIPMENT_JEWELRY_PROPS_FACTS` — optional

Used by costume-dressing. Inventory every supported stable worn or carried item, including jewelry, weapons, tools, containers, and props. Give anatomical side, attachment point, scale, material, and color when known. Record absence only when supported or needed to prevent a likely addition. Do not hide equipment inside garment prose or duplicate the inventory in garment facts.

### `EQUIPMENT_JEWELRY_PROPS_VIEW_OVERRIDES` — optional; tag only views that need overrides

Used by costume-dressing. Add tagged bullets for view-specific item visibility, overlap, side reversal, and occlusion. Do not duplicate the inventory.

## Identity sections

### `COSTUME_IDENTITY_RULES` — optional

Used by expression and character-source workflows. List the few costume traits that must remain unchanged when the face, expression, or source image changes. Focus on recognizable design anchors rather than repeating the full specification.

### `SCENE_COSTUME_IDENTITY` — optional

Used by scene building. Give a compact, complete description that keeps the costume recognizable at scene scale. Include key colors, silhouette, layers, footwear, and signature equipment. Exclude camera view, pose, scene action, and pipeline instructions.

### `SCENE_COSTUME_ANCHORS` — optional

Used by scene building for reference-backed characters. List a few compact, distinctive costume details that should remain stable in the image. Keep this shorter than `SCENE_COSTUME_IDENTITY`; include only visible features that help prevent costume drift.

## Final completeness check

Verify that the name is correct, `COSTUME_DESCRIPTION_FACTS` is complete, all tags use documented view aliases, side-specific items use anatomical left/right, equipment is in the equipment sections, optional sections are empty rather than invented, no character identity or narrative was added, and every marker is unchanged.
