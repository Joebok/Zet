# Costume Template Review

I uploaded the Final_Image_Prompt.md to the ChatGPT thread that I used to design the costume and fill out the template. The feedback is in the "ChatGPTs thoughts" section below.

There are 3 types of issues:
* Text related to the formal gown costume in the formal gown template.
These can be fixed immediately

* Text coming from the generic Config\Prompt_Templates\costume_dressing_v1.md
I believe most of these can be implemented immediately as well

* Text coming from other sources such as the _Lib\Characters\Tsaeytte\Adult\Character_Image_Template.md.
We need to review these potential changes as they will have impact on other pipelines.

Review the following remarks. Make the requested edits in _Lib\Characters\Tsaeytte\Adult\Costume_Formal_Gown.md and in both _Lib\Characters\_Shared\Costume_Template.md and Config\Prompt_Templates\costume_dressing_v1.md if they are generic enough.

If there are other sources for the suggested edits, list them so we can decide.

Put all the edits that need review in the section at the end of this file "Put Edits to Review Here"

And read the suggestions after One architectural suggestion for the future - we should evaluate these and if they seem good, then do them now.

## ChatGPTs thoughts

Overall, I think this is a substantial improvement over the earlier prompts. It has a clear authority hierarchy, separates identity from costume, and is written in a way that should generalize well to other costumes. There are only a handful of things I would change before making this the template for the costume stage. The uploaded prompt is here: .

Things I particularly like
The SOURCE AUTHORITY RULES are very clear. Giving the assembled character authority over everything except clothing is exactly the right approach.
The costume description is concrete and descriptive without becoming literary.
"Replace only the simple fitment clothing..." is much stronger than earlier wording.
The identity preservation section is comprehensive.
The forbidden drift lists are useful because they target common image model failure modes.
1. The biggest missing piece

This stage never explicitly tells the model that it is editing the supplied image.

You repeatedly refer to the "Assembled Character source", but nowhere do you actually say something like:

The supplied image is the authoritative assembled character source.

Edit that image directly.

Preserve all pixels that do not belong to the replaced costume.

Replace only the fitment clothing with the specified costume.

That sounds obvious to us.

It is not obvious to an image model.

Without that instruction some models decide to redraw the character from scratch.

I would make this one of the first things after the title.

2. I would make the edit scope even stronger

Instead of

Replace only...

I'd add

The body, face, hair, ears, neck, pose, anatomy, proportions, lighting,
camera position and framing are already correct.

Do not regenerate them.

Only replace the clothing, jewelry and footwear required by the costume.

That wording tends to suppress unnecessary regeneration.

3. Identity preservation is larger than necessary

This is the only section I think can eventually be reduced.

For example

Soft heart-shaped face
Large violet eyes
black bob
ears

is already coming from your Character Specification.

If your compiler injects those modules anyway, then repeating them here is unnecessary.

Long term I'd prefer

# Identity Preservation

{{Character Identity Module}}

and keep this prompt mostly about dressing.

4. Slight conflict regarding boots

Here you say

brown leather heeled adventuring boots

Later

only small portions may show

Then later

full body is visible, including feet

Technically all three can be true.

However image models often interpret

feet visible

as

show the footwear.

I would instead say

The entire body remains visible.

The skirt hem partially obscures the boots.

The bottoms of the boots remain visible beneath the hem.

That removes ambiguity.

5. Hem wording

Currently you have

one inch above the ground

I'd actually write

The hem hangs consistently approximately one inch above the floor around the entire circumference.

It never becomes shorter in front.

It never forms a train.

It never drags on the floor.

That is exactly the problem you just spent three iterations fixing.

I'd lock it down.

6. Duplicate constraints

Several things appear three or four times.

For example

no cape

appears in several places.

Likewise

no armor
no props
no weapons

Repeated negatives are not terrible, but once a model understands them they don't gain much.

You could shorten this by 15–20%.

7. Equipment section

I would make one tiny clarification.

Instead of

Anatomical right:
loose simple gold bracelets...

I'd write

Right wrist:
two to four loose narrow gold bangles.

Left wrist:
two to four loose narrow gold bangles.

Why?

Because "bracelets" often become cuffs.

"Bangles" consistently produces what you showed me.

8. Good Output section

I'd add one line.

The costume appears naturally tailored to the existing body rather than pasted over it.

That catches another common failure mode.

9. One thing I would add for ALL costumes

This may become one of the most useful universal rules.

The costume must follow the underlying anatomy naturally.

Do not distort the character's body to fit the clothing.

The clothing fits the character, not vice versa.

That prevents strange torso widening and shoulder inflation.

10. I would add a "No Fashion Pose" reminder

Your stance section is already excellent.

I'd simply add

This is a technical turnaround source image.

Do not convert the pose into a fashion pose.

Do not tilt the hips.

Do not arch the back.

Do not angle the shoulders.

Do not shift weight onto one leg.

Fashion dresses almost invite the model to do exactly that.

Overall

I'd rate this as 9.5/10 for a costume-rendering prompt.

The only thing I think is truly missing is the explicit statement that the uploaded assembled character image is being edited, not recreated. Everything else is refinement.

One architectural suggestion for the future: as your compiler matures, consider splitting the generated prompt into clearly labeled blocks such as:

Image Editing Instructions (edit scope, preserve source image)
Pose & Camera Preservation
Costume Definition
Equipment & Jewelry
Character Identity (injected module)
Negative Constraints

That organization makes it easier to maintain, easier to debug when a render fails, and lets you swap modules independently without growing a single monolithic prompt. I think your pipeline is now close to supporting that clean separation.

## Put Edits to Review Here

* Review whether `Config\Prompt_Templates\costume_dressing_v1.md` should reduce the full `IDENTITY_PRESERVATION_*` imports over time and replace them with a smaller "Character Identity Module" for costume dressing. This would touch identity sections from `_Lib\Characters\Tsaeytte\Adult\Character_Image_Template.md` and could affect other pipelines if done by editing the shared source sections instead of the costume prompt bundle.

**Decision:** Leave as-is for now, the full IDENTITY_PRESERVATION stuff. We need to see how actual renders come out to make a final determination.

* Review whether costume-dressing should continue importing `IDENTITY_PRESERVATION_BODY` as part of the prompt, or rely on the new image-editing and anatomy-preservation wording plus the assembled-character source image.

**Decision:** Take it out and rely on the new wording. May change our minds after actual images, but I think its a good direction to remove.

* Review whether `Config\Prompt_View_Text.json` should be updated to remove separate head-view wording for costume dressing after the broader body_view/head_view cleanup is planned. This is related to the backlog item to remove the body_view/head_view split wiring.

**Decision:** Yes, remove head-view working for costume dressing now.

* Consider a future compiler-level split of costume prompts into named modules: Image Editing Instructions, Pose & Camera Preservation, Costume Definition, Equipment & Jewelry, Character Identity, and Negative Constraints. The current prompt template has been reorganized into those blocks where possible without changing compiler behavior.

**Decision:** We will revisit this if necessary after we see how image testing comes out.

