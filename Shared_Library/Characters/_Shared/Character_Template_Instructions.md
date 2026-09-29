# Character Template Instructions

Use this manual when an existing character design and one or more approved images are being converted into `Character.md`. Write for an image-generation system, not for a reader of fiction.

## Rules for the whole file

- Preserve every `ZET:BEGIN` and `ZET:END` marker exactly. Do not add, remove, rename, or reorder markers.
- Preserve the metadata field names. Fill Character Name, Character Phase, Species / Ancestry, Canonical Art Style, and Gender Presentation.
- Use short, direct visual facts and imperatives. Prefer one observable fact per bullet.
- Do not write biography, motivation, personality, scene action, atmosphere, or decorative narrative.
- Separate observation from inference. If a fact is uncertain, state the uncertainty narrowly or leave an optional section empty; never invent a defining feature.
- Record canonical sides as `anatomical-left` or `anatomical-right`; generation prompts resolve these to screen-left/screen-right in front and back views, and near-side/far-side in three-quarter and profile views.
- Mark a side-dependent line with `<!-- ZET:SPATIAL asymmetry -->` for geometry such as hair mass or sweep, or `<!-- ZET:SPATIAL fixed -->` for a physical identity feature. Put the annotation after any leading view tag.
- Fixed-feature annotations require an explicit view tag or section `ZET:VIEW_DEFAULT`. Use `state=partial`, `state=occluded`, or `state=hidden` when that visible-state instruction applies to the tagged views. Split facts with different visibility into separate bullets.
- Do not use bare left/right in spatial facts. Keep facing direction separate from side placement; a front-left three-quarter view faces screen-left while its anatomical-left side is near.
- Put stable facts in `*_FACTS`; put view-dependent visibility, overlap, or silhouette information in `*_VIEW_OVERRIDES`.
- Begin view-dependent bullets with comma-separated view tags such as `* [f,fr] ...`; untagged facts intentionally apply to all views.
- Use `<!-- ZET:VIEW_DOMAIN head -->` or `body` inside a marked section when its line tags should use the head or body orientation. Costume sections use `body`.
- Use `<!-- ZET:VIEW_DEFAULT face_visible -->` to set a section default, `[all]` to restore all views on one bullet, and `<!-- ZET:CANON_ONLY -->` for documentation that must never reach generation prompts.
- Do not add technical fitment clothing. Zet selects the global modesty layer: Youth for any youth phase, adult feminine or masculine for recognized adult phases, and Default for Elder and every other phase.

## Metadata

Metadata identifies the character and selects global behavior. Character Phase controls phase-specific assets and technical modesty. Gender Presentation affects modesty only for phases containing `adult`. Canonical Art Style should be a compact render-facing style directive.

## Body sections

### `BODY_DESCRIPTION_FACTS` — required

Used by body-reference. Record stable build, proportions, height impression, torso, shoulders, waist, hips, limbs, hands, feet, skin, and silhouette. Exclude face, hair, costume, pose, camera direction, and fitment clothing.

### `BODY_DESCRIPTION_VIEW_OVERRIDES` — required for all eight views

Used by body-reference. Add tagged bullets only where body visibility, overlap, or silhouette changes by view. Keep positive construction details in `*_VIEW_OVERRIDES`; reserve `BODY_DESCRIPTION_VIEW_SUPPRESSION` for anti-drift guidance.

## Head and hair sections

### `HEAD_DESCRIPTION_FACTS` — required

Used by head-image. Record head shape, facial geometry, apparent age, skin, eyes, brows, nose, mouth, ears, markings, and other stable head-only identity facts. Do not mention shoulders, torso, body proportions, clothing, pose, or full-body framing.

### `HEAD_DESCRIPTION_VIEW_OVERRIDES` — required for all eight views

Used by head-image. Add tagged bullets for visible facial planes, ear visibility, occlusion, and asymmetry. Keep it head-only; place anti-drift guidance in `HEAD_DESCRIPTION_VIEW_SUPPRESSION`.

### `HAIR_DESCRIPTION_FACTS` — required

Used by head-image and expression work. Record color, texture, density, hairline, part, length, arrangement, and stable silhouette.

### `HAIR_DESCRIPTION_VIEW_OVERRIDES` — required for all eight views

Used by head-image. Add tagged bullets for visible layers, overlaps, concealed areas, and view-specific silhouette. Do not add body guidance.

## Expression and identity sections

### `EXPRESSION_DESCRIPTION_FACTS` — required

Used by expression generation. Describe how expressions appear on this face: normal intensity, crease behavior, mouth range, eyebrow behavior, and features that must remain recognizable. Do not prescribe one specific expression.

### `IDENTITY_PRESERVATION_CORE` — required

Used by expression and character-source workflows. List the few highest-priority traits whose loss would make the result a different person.

### `IDENTITY_PRESERVATION_FACE`, `IDENTITY_PRESERVATION_EYES`, `IDENTITY_PRESERVATION_HAIR`, `IDENTITY_PRESERVATION_EARS` — required

Used by expression generation. Give concise preservation constraints for the named feature only. Avoid repeating the full description; state what must not drift when expression changes.

### `SCENE_CHARACTER_IDENTITY` — required

Used by scene building. Provide a compact, complete identity summary sufficient to keep the character recognizable in a multi-character scene. Include phase-defining age and species traits. Exclude camera view, scene action, costume, technical modesty, and pipeline instructions.

## Pipeline-specific character requirements

### `BODY_REFERENCE_CHARACTER_REQUIREMENTS` — required

Used only by body-reference. Include character-varying technical requirements that are not body facts, such as species-specific mannequin anatomy. Do not repeat global stance, background, fitment clothing, framing, or view instructions.

### `HEAD_IMAGE_TRANSFORM_INSTRUCTIONS` — optional alternative path

Used when the supplied source depicts a different phase or presentation and the job must transform that same person. Write one complete source-to-target transformation contract. When this section is filled, Zet uses it instead of `HEAD_IMAGE_SOURCE_INSTRUCTIONS`, the head and hair fact/view sections, `HEAD_IMAGE_SOURCE_RULES`, and `HEAD_IMAGE_CHARACTER_REQUIREMENTS`. Include every identity anchor, intentional change, source precedence rule, and output requirement needed for the transformation. Do not duplicate this text into the standard sections.

### `HEAD_IMAGE_SOURCE_INSTRUCTIONS` — optional; standard path

Used when `HEAD_IMAGE_TRANSFORM_INSTRUCTIONS` is empty. State how the attached source should be interpreted as identity evidence. Keep it head-only. A Head-Image job always has exactly one source image.

### `HEAD_IMAGE_SOURCE_RULES` — optional; source image only

Used in the standard path. State character-specific source precedence and preservation constraints. Do not repeat general source handling.

### `HEAD_IMAGE_CHARACTER_REQUIREMENTS` — required

Used in the standard path. Include only character-varying head-output requirements not already captured as head or hair facts. Exclude body, clothing, framing, background, and generic rendering rules.

### `NEGATIVE_GUIDANCE_HEAD_IMAGE` — optional

Used by head-image. List likely character-specific head or hair failure modes as direct prohibitions. Do not include body or costume negatives.

### `CHARACTER_ASSEMBLY_CHARACTER_REQUIREMENTS` — optional

Used by character-assembly. Include only character-specific join or preservation exceptions. Do not author view names or orientation rules; assembly orientation comes exclusively from Zet's view configuration.

### `NEGATIVE_GUIDANCE_EXPRESSION` — required

Used by expression generation. List character- or phase-specific identity drift to prevent while changing expression. Keep costume rules in the costume template.

## Final completeness check

Verify that metadata is filled, every required section contains useful content, view tags use documented tokens, the transform section is either complete or empty, head-image text is body-free, anatomical sides are unambiguous, no technical modesty or stale orientation text was added, uncertain facts were not invented, and every marker is unchanged.
