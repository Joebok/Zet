# Asked if turnaround sheet is ready for expressions

Overall assessment

The sheet preserves the major identity anchors well:

Strongly preserved

Black chin-length bob with asymmetrical face framing.
Violet/blue-toned eyes and large anime-influenced facial proportions.
Pointed elf ears.
Off-shoulder teal ruffled crop top.
Teal high-low skirt over dark leggings.
Brown adventuring boots and broad belt.
Slim athletic build and youthful adult presentation.
General “confident mischievous elven sorceress” read.

The character reads as the same person across most views. The front, front-3/4, side, rear-3/4, and rear views all feel like one coherent model.

Identity preservation

I would rate identity preservation as good to very good, with a few weaknesses.

The front view and front-right 3/4 view preserve identity best. The facial structure, hairstyle, outfit, and body proportions are all aligned.

The profile and rear-3/4 views are also convincing, though the face becomes a little more generic from profile. That is not unusual; expression sheets will mostly depend on the front and 3/4 views anyway.

The bottom-right front-left 3/4 view is the weakest identity match. The face is partly obscured by hair, the expression is more downcast, and the head angle changes the personality read. It still looks related, but less like the same canonical “Tsaeytte” than the top-left/top-middle versions.

What looks especially successful

The outfit is much more consistent than many generated turnaround sheets. The teal costume language, belt, boots, skirt silhouette, and adventuring accessories carry across views well.

The body proportions are also stable enough for expression-sheet work. Since expression sheets will focus on head, neck, shoulders, and maybe upper torso, this turnaround gives you enough information to define the canonical face/hair/costume crop.

The hair is particularly useful: it establishes a recognizable silhouette from the front, side, and back. That matters a lot for expression consistency.

Main issues to fix or document

The biggest issue is not that the sheet is unusable; it is that some details drift and need to be locked before downstream use.

1. Accessory placement is inconsistent

The dagger, pouches, flask, and scroll case move around between views. For expression sheets, this only matters if the crop includes the belt, but for the larger pipeline it should be documented.

Recommended canonical rule:

Right hip: dagger only.
Left hip, front to rear: potion flask, large pouch, small pouch, scroll case.

Then treat deviations in this sheet as visual reference, not final truth.

2. Hair obscures the face differently across views

In some views, the hair helps; in the bottom-right view, it hides too much of the face and changes the emotional read.

For expression sheets, I would define:

Hair frames both sides of the face, but both eyes remain readable unless the expression specifically calls for partial concealment.

That will help prevent expression sheets from turning into “mysterious hair-over-eye” portraits.

3. Face is not equally locked in every view

The front face is your best identity source. I would use the top-left as the primary face reference and the top-middle as the secondary 3/4 face reference.

The bottom-right should not be used as a primary face reference. It is useful for costume and angle, but not for expression identity.

4. The canonical outfit is mostly there but not fully exact

This version has small straps or trim-like elements around the top in some views, and the ruffles vary. If your locked outfit is “off-shoulder teal ruffled crop top, no straps,” you should explicitly preserve that and not let this sheet overwrite it.

The boots are excellent overall, but the heel height and buckle complexity vary a bit. That is acceptable unless you need strict model-sheet precision.

Recommended next steps
Step 1: Extract a canonical identity packet

Before expression sheets, make a short “Tsaeytte expression identity lock” using this sheet. It should include only the features that must survive expressions:

young adult high-elf woman
fair skin
violet eyes
soft heart-shaped face
delicate elven features
black chin-length bob, subtly asymmetrical
pointed ears visible
playful, confident, curious baseline personality
teal off-shoulder ruffled crop top visible at shoulders/upper chest
no major hairstyle redesign between expressions

This should become the front-loaded part of every expression prompt.

Step 2: Choose primary visual references

Use these as reference hierarchy:

Top-left front view: primary identity and face.
Top-middle front 3/4 view: secondary face/angle identity.
Top-right or bottom-middle profile/3/4 views: hair silhouette and ear placement.
Rear views: costume/hair-back reference only.

Avoid letting the bottom-right image dominate expression generation.

Step 3: Generate expression sheets from head/upper-torso crops first

Do not start with full-body expressions. Start with head, neck, shoulders, and upper chest. That will test whether the model preserves:

face identity
eye shape/color
ears
hair framing
neckline/top
expression clarity

Once that works, move to half-body or full-body expression variants.

Step 4: Keep expression prompts narrowly constrained

For each expression, keep pose and camera stable:

Same character identity as reference. Head-and-shoulders portrait. Same hairstyle, same elf ears, same teal off-shoulder ruffled top. Preserve face shape and violet eyes. Change only the facial expression.

Then vary one expression at a time.

Step 5: Build a rejection checklist

For expression sheet outputs, reject when:

hair becomes long, curly, or covers one eye completely
ears disappear or change size dramatically
eye color shifts away from violet
face becomes too mature, too childlike, or too generic
top becomes strapped, armored, or modernized
expression changes the identity instead of just the emotion
head angle differs too much between cells
Bottom line

This is a very good base. It is not perfect as a strict production model sheet, but it is absolutely good enough to begin expression-sheet development.

The main thing I would do now is lock the top-left/front face as the identity source, use the 3/4 views as support, and create a compact expression prompt that says: same person, same hair, same ears, same upper costume, expression change only.

# Asked about Layout

An expression sheet is not just a pretty extra. In your pipeline, it should become a working reference document for later scene generation, especially for:

facial emotion
eye shape / brow behavior
mouth shapes
how the hair frames the face in different emotional states
the “personality read” of the character

So yes, later you absolutely could do something like:

“The dragon stole Tsaeytte’s gold. Tsaeytte is furious. Draw her yelling at the dragon.”

…and use the Anger expression sheet as one of the visual references.

But I would treat it as supporting reference, not the only instruction. The best prompt would still also state the scene action and body language, for example:

Tsaeytte is yelling
brows drawn down
mouth open in anger
posture forward and confrontational
eyes intense
expression should match her Anger reference sheet

That gives the model both:

the emotion target, and
the scene behavior.
What layout should you target?

If your goal is practical downstream use, I would strongly recommend a clean technical layout, not a fancy one.

Best layout: “production reference sheet”

The most useful layout is usually:

simple grid
consistent crop
same lighting/background
same character styling
clear labels
minimal decoration

Think of it as a tool, not a poster.

My recommendation: make two kinds if you want
1. Primary sheet: practical / technical

This is the one your pipeline should use later as reference.

Suggested characteristics
neutral plain background
consistent framing
same costume neckline / visible shoulders
same hair
same lighting
same rendering style
all expressions shown from the same main angle
labels under each image

This should be your canonical reference sheet.

2. Optional secondary sheet: fancy / presentation

If you enjoy making a more decorative one, that is fine too — but I would keep it separate.

That one can be:

prettier
more stylized
more atmospheric
more “portfolio” or “character bible”

But it should not replace the clean working sheet.

The single most useful layout

For actual scene work, I think the most useful format is:

Head-and-shoulders grid

Not full body, not tiny face crops.

Why?

Because it preserves:

face
neck
shoulders
hair silhouette
upper costume identity

That gives later prompts enough information to keep the character recognizable.

If you crop too tightly:

you lose shoulders and outfit cues

If you go full body:

the face becomes too small
the expression becomes less readable
some cells may waste space

So the sweet spot is:

Head, neck, shoulders, and upper chest

Recommended sheet structure
Option A: One-angle expression sheet

This is the best place to start.

Layout
2 rows x 4 columns, or 3 rows x 4 columns
all images from the same view angle
usually front or front-left 3/4
Best use
fastest to compare expressions
easiest to keep identity consistent
best for prompt reference later
My recommendation

Use front-left 3/4 as the primary angle if that angle preserves her personality best.

Why not pure front only?

front is very clear
but 3/4 often gives more life and better cheek/ear/hair read

A good compromise is:

most expressions in front-left 3/4
maybe a small separate neutral front view as an anchor
Option B: Dual-angle sheet

Once the first sheet works, make a second version where each expression has:

primary image: front-left 3/4
secondary image: front

This is more work, but much stronger as a reference system.

Why useful?
Because when later scenes are generated, the model may swing between front and 3/4 views. Having both gives more coverage.

What expressions should be included?

Since your list is already fairly mature, I’d group them like this.

Core sheet 1 — “most used in scenes”

These are the high-frequency expressions:

Neutral / Observant
Curious
Confident
Focused
Amused
Determined
Angry
Encouraging

This makes a very practical 8-expression sheet.

Sheet 2 — emotional depth

These are more specialized:

Flirtatious
Vulnerable
Grieving
Quiet Resolve
Frustrated

This can be a second sheet, maybe 5–6 expressions.

That way your first sheet covers common scene work, and the second covers emotional nuance.

Recommended layout details

Here is the format I would target:

Page format
portrait page
clean margin
title at top: Tsaeytte — Expression Sheet
subtitle: Adult / Canonical Appearance
Per cell

Each cell should contain:

expression portrait
expression label
optional one-line emotional note

Example:

Angry
“Fury / confrontation / yelling”
Curious
“Wondering / intrigued / delighted”
Focused
“Intense concentration”

That little note helps later when the sheet is used as reference.

Best framing for each cell

Use one framing and do not vary it much:

top of head visible
full hair silhouette visible
ears visible if possible
neck visible
shoulders visible
upper chest / neckline visible

Avoid:

overly tight face-only crops
dramatic head tilt unless the expression requires it
wildly different camera distances

Consistency is more useful than flair.

How this helps later scene prompting

Yes, an expression sheet can absolutely serve as a later scene reference.

But I would use it in a structured way.

Good pattern for later prompts

When prompting a scene, think in layers:

1. Identity layer

Who is she?

Tsaeytte, adult high-elf woman
black chin-length bob
violet eyes
delicate elven features
teal outfit
2. Scene layer

What is happening?

yelling at a dragon
dragon stole her gold
confrontation
cave / treasure setting
3. Expression reference layer

What should her face feel like?

match the Angry expression sheet
intense glare
open mouth shouting
brows lowered
jaw tense
4. Pose/body language layer

What is the body doing?

leaning forward
one hand pointing
other hand clenched
shoulders tense

That is much stronger than just saying “use the anger sheet.”

What the expression sheet should NOT try to do

To stay useful, I would avoid turning the sheet into:

a scene sheet
a body-pose sheet
a costume showcase
a mood poster

Those are all useful things, but separately.

An expression sheet should answer:

“What does Tsaeytte’s face look like when she feels X?”

That clarity is what makes it reusable.

My strongest recommendation

If you want the most useful single layout, I would choose this:

8-cell head-and-shoulders expression sheet
clean neutral background
consistent lighting
same crop in every cell
same costume / hair / ears
all from front-left 3/4 or front
labeled clearly
Expressions:
Neutral / Observant
Curious
Confident
Focused
Amused
Encouraging
Angry
Determined

That is the best “working sheet” to start with.

Suggested next-step pipeline order

Here is what I would do next:

Phase 1

Create one technical expression sheet:

8 expressions
single consistent angle
head-and-shoulders layout
Phase 2

Test it in actual prompting:

generate a few small narrative scenes
reference one expression at a time
see whether the emotion transfers well
Phase 3

If it works, expand:

second sheet with more nuanced emotions
maybe a dual-angle version
maybe add mouth-open variants for yelling, laughing, crying, etc.
Bottom line

Yes — your intuition is right.

A clean expression sheet should become a working reference for scene generation later.

And the most useful layout is not the fanciest one.

It is:

a clean, labeled, consistent head-and-shoulders grid designed for reuse

If you want, I can help you design a specific expression-sheet template next — for example:

exact page layout
number of cells
which expressions go on sheet 1
what each label/description should say
and even a prompt format for generating it consistently.