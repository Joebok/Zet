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

## View visibility tags

The current compiler accepts the following groups. These constrain visibility; they do not change the requested camera angle. Body and head orientations can differ, so use an explicit domain for facial/hair facts and costume/body facts.

| Tags | Intended visibility |
| --- | --- |
| `all`, `frontish`, `rearish`, `profiles` | All views; front and front quarters; back and back quarters; the two profiles |
| `front_3q`, `back_3q`, `three_quarter` | Front quarters; back quarters; all four quarters |
| `leftish`, `left_side`, `near_left` | Front-left quarter, left profile, back-left quarter |
| `rightish`, `right_side`, `near_right` | Front-right quarter, right profile, back-right quarter |
| `face_visible`, `both_eyes_visible`, `single_side_face` | Front, front quarters and profiles; front and front quarters; profiles |
| `rear_head_visible`, `near_ear_visible` | Back and back quarters; quarters and profiles |
| `front_torso_visible`, `rear_torso_visible` | Front/back and their respective quarters, plus both profiles |
| `front_costume_visible`, `rear_costume_visible` | Front/back and their respective quarters, excluding profiles |
| `far_left_3q`, `far_right_3q` | Right quarters / left quarters, where the corresponding anatomical side is farther away |

Individual views also accept `f`, `fl`, `pl`, `bl`, `b`, `br`, `pr`, `fr` or the explicit view tokens. Example: `* [head:both_eyes_visible] Both eyes remain visible.` Give profile and rear visibility their own bullets rather than forcing facial details into every view. The authoritative definitions are in `zet/services/view_conditioning_service.py`; local template-improvement requests and exported compiler guides derive their group list from that parser.

When improving an existing template, preserve its design and change only the requested rules. Use selected images or Luna's first-ranked representative per view; use observations to distinguish recurring defects from random failures in discarded candidates. Correct reference-angle contamination through reference selection rather than increasingly forceful prose.

## Metadata

Metadata identifies the character and selects global behavior. Character Phase controls phase-specific assets and technical modesty. Gender Presentation affects modesty only for phases containing `adult`. Canonical Art Style is a fallback; the selected universe owns the active local rendering style. Keep identity facts independent of medium, linework and shading conventions. Describe distinctive facial proportions explicitly rather than using anime or photographic style labels as identity. Describe supported material construction and texture without inventing scars, wear or decorative detail.

Use the same granular visibility controls as costume authoring: one independently taggable fact per bullet, `head` or `body` domains, and visibility groups such as `[head:face_visible]`, `[head:rearish]` and `[body:front_torso_visible]`. A stable fact is not necessarily visible in every view. Preserve recognizable geometry without requiring hidden features to face the camera or freezing incidental rendering strokes.

Enter optional body measurements as feet and inches (for example, `5 ft 8 in` or `5' 8\"`). Use measured standing barefoot height for 3D character scale; eye height, shoulder width, and body depth refine camera and pawn previews. Leave unknown measurements blank rather than estimating them from prose.

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

Describe length using body landmarks, such as mid-back below the shoulder blades,
and distinguish the actual hem from a crop edge. Head references show the complete
hairstyle where practical, including enough shoulder/back or torso context to
establish its endpoint while retaining usable head detail. Exceptionally long hair
may continue beyond the crop without a false shorter hem. Do not force hidden
lower hair into view or change head/neck proportions to expose it.

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

### `HEAD_IMAGE_EXPRESSION_GUIDANCE` — optional; Head-Image only

Used only by Head-Image jobs. Add view-conditioned facial-expression guidance here, using `<!-- ZET:VIEW_DOMAIN head -->` and tags such as `[head:frontish,profiles]` to limit it to front-facing, three-quarter front, and profile views. This section does not affect expression-image jobs or other pipelines.

### `NEGATIVE_GUIDANCE_HEAD_IMAGE` — optional

Used by head-image. List likely character-specific head or hair failure modes as direct prohibitions. Do not include body or costume negatives.

### `CHARACTER_ASSEMBLY_CHARACTER_REQUIREMENTS` — optional

Used by character-assembly. Include only character-specific join or preservation exceptions. For lower-hair completion, explicitly name the endpoint on the assembled body (for example, mid-back below the shoulder blades), arrangement and silhouette. Assembly may extend cropped or prematurely terminated source hair to that endpoint with natural overlap over shoulders, back and clothing; it preserves underlying body geometry and clothing design. Without an explicitly authored endpoint, it preserves the supplied length, including short hairstyles. Do not author view names or orientation rules; assembly orientation comes exclusively from Zet's view configuration.

### `NEGATIVE_GUIDANCE_EXPRESSION` — required

Used by expression generation. List character- or phase-specific identity drift to prevent while changing expression. Keep costume rules in the costume template.

## Final completeness check

Verify that metadata is filled, every required section contains useful content, view tags use documented tokens, the transform section is either complete or empty, head-image text is body-free, anatomical sides are unambiguous, no technical modesty or stale orientation text was added, uncertain facts were not invented, and every marker is unchanged.


## Independent Head-Image Edit authoring

The optional HEAD_EDIT_* family belongs only to Head-Image Edit. Keep existing head/hair sections unchanged when comparing pipelines. FRONT_DESCRIPTION establishes identity from text; PRESERVE contains concise geometry, hair attachment/length and material constraints that also reach source-backed edits. VIEW_OVERRIDES uses the existing head-domain view tags for anatomical sides and intentional visibility. REFERENCE_GUIDANCE binds only applicable universe LIB:REF images and explains the feature transferred and excluded material, identity, camera and background. Never assume a tag name proves anatomy is correct. EXPRESSION_GUIDANCE applies only to visible features. PHASE_CHANGES is opt-in for uploaded FRONT inputs. REVIEW_CRITERIA describes visible acceptance, including intentional eye concealment.

Use one primary edit canvas, zero for text-only FRONT, followed by optional scoped guides. FRONT independently anchors every base side/rear view. Selected BACK can guide a separate rear-quarter hair finishing attempt; do not combine this with initial rotation or automatically adopt it. Do not prepend FRONT prose to edits, mirror the opposite side, force hidden eyes into view, or substitute shoulder-length framing for authored hair length. Other pipelines do not require these new sections.
