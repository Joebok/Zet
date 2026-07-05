The prompt is a strong first costume-dressing attempt. It correctly separates assembled-character authority from costume authority, which is the right conceptual model for this stage. It also preserves the turnaround-sheet goal: neutral pose, controlled view, full body, feet visible, same identity, and costume applied naturally.

The main improvement I would make early is to tighten the hierarchy and reduce repeated constraints. Right now the prompt says the right things, but it says many of them multiple times. That can dilute priority. For costume dressing, I would front-load the most important rule:

Preserve the assembled character’s pose, body, camera, framing, head, face, hair, ears, and view exactly. Replace only the fitment clothing with the specified costume.

That should be the core instruction.

What is already good

The best parts are:

Clear source authority split
The assembled character controls identity, body, pose, stance, framing, and view; the costume file controls clothing, equipment, colors, materials, and placement. That is exactly the right structure.
Good “replace only clothing” language
“Preserve the Assembled Character exactly except where the simple fitment clothing must be replaced by the costume” is probably the most important sentence in the prompt.
Good stance control
The foot-placement section is valuable because turnout/pose drift has been a recurring failure mode.
Good left/right equipment rules
Right hip dagger, left hip pouches/flask/scroll case is stated clearly and repeatedly enough that it has a chance to stick.
Good negative drift list
The forbidden drift section is useful, especially “no armor,” “no cape,” “no sword,” “no staff,” and “do not swap left and right.”
Main issues to fix
1. The prompt may be too redundant

The same concepts appear in several places: identity preservation, costume preservation, good output, bad output, negative constraints, and final summary. Some repetition is good, but too much can make the model treat everything as equally important.

I would consolidate into this hierarchy:

Primary objective.
Source authority rules.
View/pose/framing lock.
Costume replacement rules.
Costume specification.
Equipment placement.
Identity preservation.
Bad-output / negative constraints.

The current prompt has all of that, but it could be made more compact.

2. “Not a reference sheet” may conflict with turnaround-sheet usage

You say the output will become part of a turnaround sheet, but later say “not a reference sheet.” I understand the intent: you do not want the model to generate a multi-panel layout. But “not a reference sheet” could mildly conflict with “technical turnaround source.”

I would change:

not a reference sheet

to:

not a multi-view sheet, not a layout page, not a labeled diagram

That keeps the intent without discouraging clean technical presentation.

3. “Remove fitment clothing” could trigger unwanted body reconstruction

For image-to-image costume dressing, “remove clothing” can sometimes cause the model to overthink anatomy. Better wording:

Fully cover or replace the simple fitment garments with the costume garments. No fitment clothing remains visible.

That avoids making “removal” the focus.

4. The costume description is slightly too permissive

Phrases like “possibly with subtle diamond or seam pattern” and “additional small utility attachments acceptable” may invite drift. For canonical turnaround work, I would avoid optional expansions unless they are specifically needed.

For example, replace:

dark blue or navy leggings visible under the front opening, possibly with subtle diamond or seam pattern

with:

dark navy leggings visible beneath the skirt opening; plain or subtly paneled, not decorative enough to compete with the skirt

And replace:

additional small utility attachments acceptable if they do not crowd the silhouette

with:

no additional attachments beyond the specified dagger, flask, pouches, and scroll case

At this stage, strictness is better.

5. The front-view instruction should explicitly preserve anatomical side

For front view, right and left are easy for models to swap because the viewer’s left is the character’s right. I would add:

Anatomical right means the character’s own right side, appearing on the viewer’s left in a front view. Anatomical left means the character’s own left side, appearing on the viewer’s right in a front view.

This is especially important for dagger/pouch placement.

6. The high-low skirt needs view-specific behavior

For a front costume-dressing pass, the high-low skirt should be short/open in front and not hide the leggings or legs too much. I would add:

In front view, the skirt front remains short/open enough to show both dark leggings, knees, lower legs, and boots clearly. The longer back drape may be visible only as side/back fabric edges, not as a full front-length gown.

This helps prevent the model from turning it into a long formal dress.

7. “Tall brown leather heeled boots” may fight the flat-foot stance

“Heeled” is canonical, but the stance section says feet flat and no raised heel. To avoid the model interpreting “heeled” as fashion pose/tiptoe, specify:

boots have low practical heels; both soles and heels are planted flat on the floor

Or:

practical adventuring heels, not high-fashion heels; no tiptoe posture

Suggested early-stage revised opening

This is the part I would most strongly revise:

```
FULL-BODY COSTUME DRESSING IMAGE

Character: Tsaeytte, Adult
Costume: Canonical Adult Adventuring Sorceress Outfit
Requested body view: FRONT
Requested head view: FRONT
Purpose: single full-body turnaround-source image in a neutral pose.

PRIMARY OBJECTIVE

Create one complete full-body render of the assembled character naturally wearing the specified costume.

Use the assembled character image as the locked identity, body, pose, stance, camera, framing, and view source. Preserve the assembled character’s body proportions, head, face, hair, ears, neck, pose, foot placement, camera angle, and full-body framing exactly.

Change only the clothing, jewelry, belt equipment, and footwear needed to replace the simple fitment garments with the canonical costume.

Do not redesign the character.
Do not change the pose.
Do not change the camera angle.
Do not rotate the head or body.
Do not mirror the image.
Do not create a multi-view sheet, collage, labeled reference page, or narrative scene.

The final result should look like the same assembled character in the same front-facing neutral turnaround pose, now naturally dressed in the canonical adventuring outfit.
```

Suggested costume section tightening

I would also simplify the costume section into something like this:

```
COSTUME DESIGN

Dress Tsaeytte in her canonical adult adventuring sorceress outfit.

Overall silhouette: elegant, mobile fantasy adventurer outfit with exposed shoulders, teal ruffled crop top, visible midriff, high-low teal skirt, dark navy leggings, tall brown boots, broad brown utility belt, compact dagger, left-side pouches, scroll case, and blue-violet jewelry.

Top: rich dark teal off-shoulder ruffled crop top with fitted bodice, decorative seams, and subtle gold/star-like ornamentation. The neckline sits below the shoulders with no straps.

Sleeves: separate or gathered off-shoulder puff sleeves ending above the elbow with layered ruffles. Forearms remain exposed.

Midriff: visible adult non-explicit midriff and navel between the crop top and belt/skirt.

Skirt: teal high-low skirt with layered drape, short/open in front and longer in back. In front view, the skirt must not become a long gown; both legs, leggings, and boots remain clearly visible.

Legwear: dark navy leggings visible beneath the skirt opening.

Boots: tall warm brown leather adventuring boots with practical low heels, straps, panels, buckles, and worn travel texture. Both soles and heels remain planted flat on the floor.

Belt: broad brown leather utility belt with large central buckle.

Jewelry: layered dark necklace with central blue-violet teardrop pendant; matching dangling blue-violet earrings in gold-toned settings.

Materials and colors: dark teal cloth, gold embroidery or trim, dark navy leggings, warm brown leather, metal buckles, polished blue-violet stones.

Forbidden costume drift: no armor plates, corset-only redesign, long formal gown, modern clothing, visible straps, cape, sword, staff, wand, bow, shield, backpack, spellbook, glowing artifact, or extra weapons.
```

Suggested equipment placement language

This section is worth making very explicit:

```
EQUIPMENT PLACEMENT

Use anatomical left and right.

In front view:

* Tsaeytte’s anatomical right side appears on the viewer’s left.
* Tsaeytte’s anatomical left side appears on the viewer’s right.

Right hip: compact dagger in a sheath. The dagger is practical and small, not a sword.

Left hip/front-left belt: potion or round flask near the front of the left hip.

Left hip: large buckled leather pouch and smaller buckled pouch.

Rear-left or left-side belt: cylindrical scroll case mounted to the belt.

Do not swap left and right. Do not add extra weapons or large props.
```

Biggest practical recommendation

For the actual pipeline, I would separate this into modules rather than one long prompt:

Costume_Dressing_Header.md
Source_Authority_Rules.md
Neutral_Turnaround_Pose.md
View_FRONT.md
Tsaeytte_Identity_Anchors.md
Tsaeytte_Canonical_Adventure_Costume.md
Costume_Dressing_Negatives.md

Then Python can assemble the final prompt with the most important lock rules first. This will make it easier to swap FRONT, FRONT_LEFT_3_4, PROFILE, etc. without rewriting the whole costume prompt.
