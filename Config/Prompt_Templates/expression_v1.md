STANDALONE CHARACTER EXPRESSION REFERENCE IMAGE

Character: {{CHARACTER_NAME}}, {{CHARACTER_PHASE}}.
Canonical Art Style: {{CANONICAL_ART_STYLE}}
Expression label: {{EXPRESSION_LABEL}}.
Expression intensity: clear and readable, but not caricatured.
Identity Key: {{IDENTITY_KEY_LABEL}}.
Expression definition: {{EXPRESSION_DEFINITION_PATH}}.
Purpose: one clean standalone expression reference image matching the Identity Key framing.

PRIMARY OBJECTIVE

Create one standalone character expression image that preserves the selected Identity Key's identity, crop range, view angle, costume visibility, lighting, and rendering style, while changing only the facial expression specified by the Expression Definition.

The Identity Key controls identity, crop, view angle, costume visibility, lighting, and style.
It does not override the requested Expression Definition.

Change the facial expression and only the minimum necessary supporting head, neck, or shoulder tension needed to make that expression believable.
Do not redesign the character, costume, hairstyle, pose category, age, species, or personality archetype.

Use the Identity Key reference as the main visual authority for:
- face identity
- view angle and crop scale
- hair silhouette
- ear shape and visibility
- visible neck, shoulders, torso, waist, and costume cues
- lighting and rendering style

Do not render a full body. The output should not show more of the character than the Identity Key framing requires.
Do not create an expression sheet.
Do not create a multi-view sheet, layout page, labeled diagram, collage, or narrative scene.
Do not stamp text into the image.

IDENTITY KEY FRAMING AUTHORITY

The Identity Key reference defines the intended crop range, camera distance, view angle, and visible body extent for this expression image.

Match the Identity Key framing as closely as possible:
- If the Identity Key shows head and shoulders, produce a head-and-shoulders expression image.
- If the Identity Key shows bust or upper torso, produce a bust or upper-torso expression image.
- If the Identity Key shows waist-up framing, produce a waist-up expression image.
- Preserve approximately the same amount of visible hair, neck, shoulders, torso, and costume as the Identity Key.

Do not zoom substantially closer than the Identity Key.
Do not pull back substantially farther than the Identity Key.
Do not crop away body or costume areas that are visible in the Identity Key unless required by the requested expression.

FRAMING

Use a clean portrait-reference crop that matches the Identity Key source.

Preserve the same general visible range shown in the Identity Key:
- top of head and full hair silhouette
- face and ears
- neck
- shoulders
- any upper costume, torso, or waist area visible in the Identity Key

Keep the camera distance, crop scale, and body extent close to the Identity Key.
Preserve enough costume and silhouette information for the character to remain recognizable later as a reference image.

EXPRESSION TARGET

{{EXPRESSION_DEFINITION}}

GENERAL EXPRESSION RULES

{{SECTION:EXPRESSION_DESCRIPTION_FACTS}}

{{EXPRESSION_PROMPT_INSERT_AFTER_EXPRESSION_DESCRIPTION_FACTS}}

IDENTITY PRESERVATION

{{SECTION:IDENTITY_PRESERVATION_CORE}}

{{EXPRESSION_PROMPT_INSERT_AFTER_IDENTITY_PRESERVATION_CORE}}

{{SECTION:IDENTITY_PRESERVATION_FACE}}

{{EXPRESSION_PROMPT_INSERT_AFTER_IDENTITY_PRESERVATION_FACE}}

{{SECTION:IDENTITY_PRESERVATION_HAIR}}

{{EXPRESSION_PROMPT_INSERT_AFTER_IDENTITY_PRESERVATION_HAIR}}

{{SECTION:IDENTITY_PRESERVATION_EARS}}

{{EXPRESSION_PROMPT_INSERT_AFTER_IDENTITY_PRESERVATION_EARS}}

{{SECTION:IDENTITY_PRESERVATION_COSTUME}}

{{EXPRESSION_PROMPT_INSERT_AFTER_IDENTITY_PRESERVATION_COSTUME}}

GOOD OUTPUT

- One clean standalone expression reference image.
- Same character identity, age, species, face structure, violet eyes, elf ears, hair silhouette, and costume cues as the Identity Key.
- The requested expression is clear and readable without becoming caricatured.
- View angle, crop range, visible body extent, lighting, and rendering style stay close to the Identity Key.
- The expression changes emotion without redesigning the character.

BAD OUTPUT

- Character identity changes.
- Hair, ears, eye color, age, species, costume, or face structure changes.
- Output becomes a full-body image, scene, sheet, collage, diagram, label page, or multi-view image.
- Crop is substantially tighter or wider than the Identity Key, or removes important identity/costume cues visible in the Identity Key.
- The expression becomes exaggerated enough to distort identity.
- Text or expression labels are stamped into the image.

NEGATIVE CONSTRAINTS

{{SECTION:NEGATIVE_GUIDANCE_GENERAL}}

{{EXPRESSION_PROMPT_INSERT_AFTER_NEGATIVE_GUIDANCE_GENERAL}}

{{SECTION:NEGATIVE_GUIDANCE_JOB_SPECIFIC}}

{{EXPRESSION_PROMPT_INSERT_AFTER_NEGATIVE_GUIDANCE_JOB_SPECIFIC}}

Do not render: full body unless explicitly required, tiny face, face-only crop unless the Identity Key is also face-only, extreme close-up, narrative scene, action pose, dramatic head tilt, hairstyle redesign, hidden ears, wrong eye color, age drift, species drift, costume redesign, extra props, text labels, caption, diagram, expression sheet, collage, multi-view layout.

FINAL OUTPUT SUMMARY

The final image should be a practical reusable expression reference: same person, same Identity Key framing, same visible costume cues, new expression only.
