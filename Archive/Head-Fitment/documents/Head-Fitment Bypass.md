Question: Right now the character assembly process is quite complicated and time consuming despite recent efforts to make it easier. Is there any value in the head-fitment pipeline? Is there any reason we can't skip it entirely and just go from the head-image and body-reference to character-assembly? If not, how should we reconfigure head-image and character-assembly to work directly together?

## 1. Is the Head-Fitment stage worth keeping?

For the current Zet workflow, I would **remove Head-Fitment from the normal pipeline and make direct Head-Image → Character-Assembly the default**.

I would retain Head-Fitment only as an optional fallback/debugging path rather than delete the capability entirely.

The important reason is architectural: **Character-Assembly is already solving almost the same problem that Head-Fitment is intended to solve.**

Your Head-Fitment stage takes the finished head, consults the body, and tries to manufacture a standardized neck width, axis, and cut position while preserving the head.  But Character-Assembly then explicitly treats the head/neck/shoulder junction as adaptive and is allowed to reconstruct the neck width, taper, attachment position, neck length, shoulder transition, shading, and hair overlap. 

So the current pipeline is effectively:

> good head → generatively solve neck → generatively solve neck again

The intermediate solution is not even strongly authoritative to the final stage.

### What Head-Fitment theoretically buys you

There are legitimate reasons to have such an asset:

| Potential value                              |                           Current importance |
| -------------------------------------------- | -------------------------------------------: |
| Standardized attachment geometry             |                                          Low |
| Transparent reusable head module             |                                 Low–moderate |
| Fixed neck cut for deterministic compositing |                     Potentially high someday |
| Isolated asset for debugging                 |                                     Moderate |
| Reuse of one head across many bodies         |                 Limited because views differ |
| Less work for Character-Assembly             | Low, because Assembly reconstructs it anyway |

If Zet eventually uses **true deterministic compositing**, masks, warping, ControlNet-like geometry, or another process where the neck module is literally pasted into a known socket, Head-Fitment could become useful again.

But with a **generative Character-Assembly stage**, standardizing a neck in a previous generative pass has much less value.

### What it costs you

It costs considerably more than one extra generation.

Every Head-Image → Head-Fitment transformation gives the model another opportunity to change:

* apparent age;
* facial texture;
* eyelid and under-eye structure;
* jaw and cheek structure;
* hair silhouette;
* hair length;
* ears;
* rendering details;
* gaze;
* head orientation;
* overall identity.

Your Head-Fitment prompt has accumulated extensive preservation language precisely because this transformation keeps trying to modify material that theoretically should not need modification. 

That is a sign that the stage is fighting the underlying nature of the tool.

And Elder Tsaeytte is almost a worst-case example. In the images you supplied, the shoulder-length hair obscures much of the neck. The fitment asset therefore doesn't even provide a particularly useful clean neck socket. It mainly turns a very good natural portrait into a technically cropped asset while introducing another opportunity for identity and age drift.

Meanwhile, the Head-Image is already deliberately designed to be a strong canonical source: it has the correct age, face, hair, view, gaze, ears, rendering, and enough neck/shoulder context to understand how those parts naturally relate. 

I would use that stronger source directly.

---

# Recommended pipeline

I would change the primary pipeline to:

**Body Reference**
+
**Head Image**
↓
**Character Assembly**

And retain:

**Head Image → Head Fitment → Character Assembly**

only as something like:

`legacy_fitment` / `fallback_fitment` / `diagnostic_fitment`

rather than a required production step.

This also gives you a useful troubleshooting distinction:

* If the **Head Image is wrong**, fix Head-Image generation.
* If the **body is wrong**, fix Body-Reference generation.
* If the **connection is wrong**, fix Character-Assembly.

There is no intermediate artifact muddying the diagnosis.

---

# 2. Changes to Head-Image

The existing Head-Image prompt is already very close to what you want. In fact, its current rendering rules explicitly say:

> “Do not impose head-fitment neck geometry, a fixed neck cut, transparency, or shoulder-removal requirements.”

That is appropriate for the direct pipeline. 

I would make one conceptual change:

**The Head-Image should deliberately provide good anatomical context for assembly, without pretending that its shoulders belong to the final body.**

I would replace the relevant rendering language with something along these lines:

```markdown
## Character-Assembly Reference

This image is the canonical visual source for the character's head. It is not a neck-fitment asset.

Render a natural head-and-shoulders reference in the requested view.

Include:

- the complete head and hair silhouette;
- the complete jaw and chin;
- a naturally proportioned neck;
- enough upper shoulder context to show how the neck, hair, and shoulders normally relate.

Do not crop through the jaw or upper neck.

Do not lengthen or expose the neck merely to make it easier to see beneath the hairstyle.

Hair may naturally overlap the neck and visible shoulders.

The visible shoulders, upper torso, clothing, and background are contextual only. They do not define the final character's body geometry and may be discarded during Character-Assembly.

The Character Head source controls the final character's face, identity, age presentation, expression, gaze, ears, hairstyle, head orientation, and visible head rendering.
```

That establishes a very clean contract.

### I would also tighten one existing choice

Currently you allow:

> “Head-only, head-and-shoulders, bust, or a small amount of upper torso…”



For assembly sources, I would no longer encourage **head-only**.

Prefer:

> **natural head-and-shoulders or limited bust framing**

because the neck/shoulder context is useful information for assembly even though those shoulders are non-authoritative.

Your first attached Elder image is almost ideal for this purpose.

It contains much more useful anatomical information than the cropped fitment version.

---

# 3. Bigger changes belong in Character-Assembly

This is where I think you can simplify things substantially.

The current Character-Assembly prompt is already headed in the right direction. In particular:

> “The head–neck–shoulder junction is an adaptive assembly region rather than a rigid source boundary.”

and:

> “Adjust the local neck width, taper, attachment position, jaw-to-neck transition, neck-to-shoulder transition…”



Those instructions effectively make Head-Fitment redundant.

However, I would change the source contract now that the Head Image may contain shoulders and background.

## Change this

```markdown
Replace the mannequin head and placeholder neck of the Reference Body with the supplied fitted Character Head.
```

to:

```markdown
Replace the mannequin head and placeholder neck of the Reference Body using the supplied Character Head image.

The Character Head image may be a natural head-and-shoulders or limited bust reference. It does not need to be a fitted or cropped neck module.
```

---

# Add an explicit context-discard rule

This is probably the most important new instruction:

```markdown
# Character Head Context Rule

The Character Head image may contain neck, shoulders, upper torso, clothing, or background.

These elements provide visual and anatomical context only.

Do not copy the Character Head source's shoulders, torso, clothing, framing, or background into the final image.

The Reference Body is authoritative for the final shoulders, torso, body geometry, clothing, framing, and background.

The Character Head is authoritative for the final head identity, face, age presentation, expression, gaze, ears, hairstyle, head orientation, and visible rendering of those features.
```

This tells the model very clearly why it is being shown two overlapping bodies.

---

# Narrow the adaptive region

I would change this part of the existing Assembly prompt.

Right now you say:

> “The head–neck–shoulder junction is an adaptive assembly region…”

and then:

> “Neither source is pixel-locked within this local region.”



I think **“head–neck–shoulder” is too broad**.

It can implicitly license repainting the head—which is exactly what has been causing de-aging.

I'd redefine it as:

```markdown
# Adaptive Assembly Region

The adaptive assembly region is the neck and immediate neck/hair/shoulder junction.

The face, jaw, chin, ears, skull, expression, and main hairstyle mass of the Character Head are not part of the adaptive region.

The Reference Body's overall shoulder geometry and body silhouette are not part of the adaptive region.

Within the adaptive region, reconstruct only what is necessary to create a natural continuous connection between the supplied Character Head and Reference Body.

Allowed local changes include:

- neck width and taper;
- visible neck length;
- jaw-to-neck transition;
- neck-to-shoulder transition;
- local skin shading;
- small hair-end placement and overlap;
- edge cleanup and antialiasing.

Do not broadly repaint either source.
```

That is considerably more precise.

---

# Move the useful Head-Fitment preservation rule into Assembly

There *is* something valuable in the Head-Fitment prompt that should survive: its strong emphasis on preserving the already-successful head rendering.

I would put a short version directly into Character-Assembly:

```markdown
# Character Head Rendering Lock

Treat the supplied Character Head as visually final.

Preserve its apparent age, facial maturity, feature geometry, skin texture, eye and eyelid structure, under-eye contours, cheek structure, jaw and chin, asymmetry, expression, gaze, ears, hairstyle, shading, brushwork, and surface detail.

Do not beautify, smooth, rejuvenate, cosmetically lift, anime-stylize, or otherwise reinterpret the supplied face.

Do not reconstruct the character from textual description when the visible Character Head source already supplies the feature.

Textual character information identifies properties that must survive assembly; it does not override the rendered Character Head.
```

That captures the useful part of the elaborate Source Rendering Lock from Head-Fitment without needing the Head-Fitment transformation itself. 

For Elder Tsaeytte in particular, this should help substantially with the de-aging problem.

---

# Define the neck as something Assembly creates

I'd make the core geometry concept extremely simple:

```markdown
# Neck Reconstruction

Use the Character Head to determine where the neck naturally begins beneath the jaw.

Use the Reference Body to determine where the neck naturally joins the shoulders.

Construct one short, naturally proportioned neck connecting those two anatomical regions.

Match the Reference Body's neck axis and overall body orientation while preserving the Character Head's existing head orientation.

Do not stretch the neck to create clearance beneath the hair.

Do not move the head upward merely to expose more neck.

Hair may naturally obscure part or most of the neck and may overlap the shoulders.
```

This is simpler than manufacturing a standardized neck socket first and then asking Assembly to correct it.

---

# One other change I would make

Your existing Assembly prompt says:

> “Final anatomical continuity and visual integration take priority over literal preservation of either source within this region.”



That's reasonable, but I'd qualify it:

```markdown
Final anatomical continuity takes priority over literal preservation of source neck pixels and local attachment geometry.

It does not take priority over preservation of the Character Head's facial identity, age presentation, expression, gaze, ears, or main hairstyle design.
```

Otherwise “integration takes priority” can become an excuse for the model to smooth or repaint the face.

---

# The conceptual division becomes much cleaner

With these changes, each artifact has exactly one job.

| Asset                  | Authority                                                                         |
| ---------------------- | --------------------------------------------------------------------------------- |
| **Head Image**         | Face, age, identity, ears, hair, expression, gaze, head pose, rendered appearance |
| **Body Reference**     | Body anatomy, proportions, pose, shoulders, stance, clothing, framing, background |
| **Character Assembly** | Joining those two at the neck/hair/shoulder boundary                              |

There is no need for an asset whose job is:

> “pre-join the head to approximately the body geometry so another process can join it again.”

That is essentially what Head-Fitment has become.

## I would therefore make this the new Zet rule

**Head-Fitment is not required for Character-Assembly. Character-Assembly normally consumes the canonical Head-Image directly.**

**Head-Fitment remains available only when a downstream process specifically requires an isolated transparent head-and-neck module or when direct assembly repeatedly fails for a particular case.**

I would not delete the Head-Fitment code yet. I'd bypass it by default and run the direct path through **all eight canonical views** for at least Adult and Elder Tsaeytte. If the direct pipeline performs comparably or better—which I expect it will—you can effectively deprecate Head-Fitment. The reduction in generative transformations alone should improve identity and age preservation while removing one of the most troublesome and time-consuming stages of the pipeline.
