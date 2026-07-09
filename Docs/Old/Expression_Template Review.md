# Expression Review.

I asked ChatGPT to comment on the Config\Prompt_Templates\expression_v1.md. In particular I was interested in trying to get the image to follow the key image in terms of what to show - so if I give a head & shoulders key, I get a head & shoulders expression. And If I give a waist-up key then the same prompt gives me a waist up expression.

I believe that expressions are relatively loose compared to what we wanted for the reference images, so we are hoping to get close enough. We don't want expression instructions to be overwhelmed with the view cropping.

Please review and implement unless it impacts shared areas. List those at the bottom to review.

## ChatGPTs thoughts

This template is already pointed in the right direction. It clearly says: one standalone expression reference, identity key is visual authority, change expression only, do not make a sheet/collage/text-labeled image. That is exactly the right baseline.

The main change I would make is to generalize the framing so the Identity Key controls the crop, rather than hard-coding “head-and-shoulders” everywhere.

Main recommended change

Right now the template says:

Purpose: one clean head-and-shoulders expression reference image.

and:

Create one standalone head-and-shoulders character image...

and:

Use a clean head, neck, shoulders, and upper chest crop.

That will fight you later if the Identity Key is waist-up. I would replace “head-and-shoulders” with something like:

Purpose: one clean standalone expression reference image matching the Identity Key framing.

Then in the objective:

Create one standalone character expression image that preserves the selected Identity Key’s identity, view angle, crop range, and framing, while changing only the facial expression specified by the Expression Definition.

This lets the same template work for:

head-and-shoulders identity key → head-and-shoulders expression
bust identity key → bust expression
waist-up identity key → waist-up expression
Add an “Identity Key Framing Authority” section

I would add a dedicated section after PRIMARY OBJECTIVE or before FRAMING.

Suggested text:

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

This is the most important addition.

Revise the existing FRAMING section

Current:

Use a clean head, neck, shoulders, and upper chest crop.
Keep the crop consistent with the Identity Key source.
Preserve enough shoulder and costume information for the character to remain recognizable later as a reference image.

Suggested:

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

This avoids hard-coding one crop type.

Change the title

Current:

STANDALONE CHARACTER EXPRESSION IMAGE

This is okay. I might make it slightly more specific:

STANDALONE CHARACTER EXPRESSION REFERENCE IMAGE

“Reference” reinforces that this is not a narrative render.

Add a “Do not copy expression from Identity Key” line

Because the Identity Key probably has a neutral or default expression, you want to be clear that the key controls identity/framing, not emotion.

Add this under PRIMARY OBJECTIVE:

The Identity Key controls identity, crop, view angle, costume visibility, lighting, and style. It does not override the requested Expression Definition.

This is useful if the Identity Key is neutral but the requested expression is angry, grieving, amused, etc.

Add a “facial expression only, not personality redesign” distinction

Your template already says “changing only the facial expression,” which is good. I would strengthen it slightly:

Change the facial expression and only the minimum necessary supporting head/neck/shoulder tension needed to make that expression believable.
Do not redesign the character, costume, hairstyle, pose category, age, species, or personality archetype.

This is useful because some expressions require subtle body support: anger may tense shoulders; grief may lower the head slightly; amusement may lift the cheeks. But you do not want full acting or a scene pose.

Consider adding “Expression intensity” as an injected field

Right now you have:

Expression label: {{EXPRESSION_LABEL}}.
Expression definition: {{EXPRESSION_DEFINITION_PATH}}.

I would consider adding:

Expression intensity: {{EXPRESSION_INTENSITY}}.

Possible values:

subtle
moderate
strong
extreme / theatrical

For production references, I would usually target moderate to strong, not extreme. Extreme expressions can distort identity.

Example:

Expression intensity: {{EXPRESSION_INTENSITY}}.
Default if unspecified: clear and readable, but not caricatured.
Consider adding “mouth state” as an injected field

For expression sheets, mouth state matters a lot. “Angry” could mean clenched teeth, open yelling, tight-lipped glare, or shocked fury.

Optional metadata:

Mouth state: {{MOUTH_STATE}}.
Eye/brow state: {{EYE_BROW_STATE}}.

That may be too much for v1, but it will help later.

For example:

Expression label: Angry — yelling.
Mouth state: open shout.
Eye/brow state: brows lowered, eyes intense.

This would avoid ambiguity.

Suggested organization

I would restructure slightly like this:

STANDALONE CHARACTER EXPRESSION REFERENCE IMAGE

Character: {{CHARACTER_NAME}}, {{CHARACTER_PHASE}}.
Canonical Art Style: {{CANONICAL_ART_STYLE}}
Expression label: {{EXPRESSION_LABEL}}.
Expression intensity: {{EXPRESSION_INTENSITY}}.
Identity Key: {{IDENTITY_KEY_LABEL}}.
Expression definition: {{EXPRESSION_DEFINITION_PATH}}.
Purpose: one clean standalone expression reference image matching the Identity Key framing.

PRIMARY OBJECTIVE

IDENTITY KEY FRAMING AUTHORITY

FRAMING

EXPRESSION TARGET

GENERAL EXPRESSION RULES

IDENTITY PRESERVATION

GOOD OUTPUT

BAD OUTPUT

NEGATIVE CONSTRAINTS

FINAL OUTPUT SUMMARY

Your current order is already close. The main addition is IDENTITY KEY FRAMING AUTHORITY.

Text edits I would make directly
Replace this:
Purpose: one clean head-and-shoulders expression reference image.

with:

Purpose: one clean standalone expression reference image matching the Identity Key framing.
Replace this:
Create one standalone head-and-shoulders character image that preserves the selected Identity Key while changing only the facial expression specified by the Expression Definition.

with:

Create one standalone character expression image that preserves the selected Identity Key’s identity, crop range, view angle, costume visibility, lighting, and rendering style, while changing only the facial expression specified by the Expression Definition.
Replace this:
Do not render a full body.

with:

Do not render a full body unless the Identity Key itself is full-body and the job explicitly asks for full-body framing.

Or, if you want to forbid full body for expression references entirely:

Do not render a full body. The output should not show more of the character than the Identity Key framing requires.

I prefer the second version for now.

Replace this:
Use a clean head, neck, shoulders, and upper chest crop.

with:

Use a clean portrait-reference crop that matches the Identity Key source.
Replace this bad-output line:
Crop is too tight to show shoulders and upper costume.

with:

Crop is substantially tighter or wider than the Identity Key, or removes important identity/costume cues visible in the Identity Key.
Replace this negative list item:
Do not render: full body, tiny face, face-only crop, extreme close-up...

with:

Do not render: full body unless explicitly required, tiny face, face-only crop unless the Identity Key is also face-only, extreme close-up...

But I would probably avoid face-only Identity Keys for this pipeline. Head/shoulders or waist-up will work better.

One thing I would not add

I would not ask the model to generate labels, captions, or expression names in the image. You already correctly forbid this.

Keep labels in filenames, metadata, or the assembled human-facing sheet — not in the individual expression reference image.

Bottom line

The template is good. The main weakness is that it currently assumes head-and-shoulders as the fixed output. Since your desired behavior is “match whatever the Identity Key shows,” I would make the Identity Key the authority for framing and remove hard-coded crop language.

The key sentence I would add is:

The Identity Key reference defines the intended crop range, camera distance, view angle, and visible body extent for this expression image.

That single idea should make the template much more flexible.

## Put Edits to Review Here

* Consider adding explicit Expression asset fields for `expression_intensity`, `mouth_state`, and `eye_brow_state` when the Expression pipeline/page is implemented. The template currently uses a fixed default intensity line so it does not require unsupported placeholders before the worker exists.
* Decide whether face-only Identity Keys should be allowed for expression assets. The template can technically follow them, but head/shoulders, bust, or waist-up Identity Keys will likely preserve costume and silhouette better.
* Decide whether assembled expression sheets should stamp labels into the composite sheet later. Individual expression reference images should continue to forbid text labels/captions.
* When the Expression worker is added, make the Identity Key metadata available to the prompt manifest so the Render Console can show the selected key image and the expression definition together.

