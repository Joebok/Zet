# From an exchange with ChatGPT:

## Question
I am having frustration and difficulties nailing down all the back views - back and the 3/4 views. This has been an issue from the start and even when I get my reference images down, constructing a scene trying to view the characters from behind often leads to the same frustration. The image generation engines all seem to want to have forward  views in some way or another. This is particularly the case with the costumed views - the un-costumed references seem to come out fine, but all of the costumes templates I have are failing. So what I want to discuss, in the abstract for now, is it even worth it to try to construct a complete turnaround set? This has been my pipeline from the beginning - get a turnaround set, then use the appropriate view for scenes. But there is usually an intermediary step of pose - including when the head is facing a different way than the body. The turnaround images are doing a good job of keeping identity from drifting. But I wonder if it is too much overhead to try to generate and maintain a complete set of 8 views. The other thing going on is that I've implemented a "sub-scene" system for scenes where I can break down a scene into groups of elements, work on those in isolation for a combined image, and then use those completed images as backdrops in the main scene - and it works quite well. I am wondering if a valid path would be to follow this approach - have a main character element be a subscene - the subscene is where I work out the pose and identity, and then the main scene gets that as a reference images - instead of one of turnaround references. Are there best practices out there for doing this kind of work in a digital environment? Given the context you have available, what insight can you offer?

## Answer

Dude, I think your pipeline has reached the point where the **eight-view turnaround should stop being the central abstraction**.

It has clearly been useful: it gave you a controlled way to establish identity, proportions, costume design, and orientation, and it helped you diagnose drift. But the thing you ultimately need for a scene is not “Tsaeytte at one of eight canonical angles.” You need **Tsaeytte in one particular camera-relative pose**, often with the body, head, gaze, arms, equipment, and clothing all oriented differently.

That makes your subscene idea a better fit for the actual problem.

### Turnarounds are specification, not staging

Traditional model-sheet practice supports this distinction. A turnaround establishes what the character *is*: front, profile, rear, three-quarter, proportions, costume construction, colors, etc. The subsequent production process uses those references to construct arbitrary poses rather than selecting one turnaround drawing and transforming it into the shot. One character-design workflow explicitly builds the body construction first and then “dresses the mannequin.” :chatgpt-content-reference{index="0"}

Modern generative workflows are moving toward essentially the same decomposition. IP-Adapter-style conditioning provides appearance/identity information, while pose/depth/ControlNet supplies geometry and staging. Those can be combined rather than forcing one reference image to carry identity, costume, pose, and composition simultaneously. :chatgpt-content-reference{index="1"}

So I would conceptualize your pipeline as:

**Canon → Shot construction → Scene composition**

rather than:

**Eight-view canon → choose nearest view → somehow mutate it into the shot.**

That second step is exactly where you keep fighting the models.

### I would keep turnarounds, but radically reduce their responsibility

I would not throw away the work you've done around deterministic views. I'd change what constitutes a required asset.

For the **body/identity reference**, your existing relatively successful uncóstumed/mannequin references are valuable. They establish height, proportions, silhouette, ears, head/body scale, and so forth. Because those are working, there is little reason to dismantle that part.

For a **costume**, I don't think you necessarily need eight canonical images. I would probably reduce the normal required set to something like:

- **Front** — primary visual design authority.
- **Back** — only because there is genuinely information that cannot be seen from the front.
- **One profile or useful three-quarter** — only when the costume contains important thickness, layering, side equipment, high-low geometry, etc.
- **Detail references** — jewelry, embroidery, belt equipment, weapon, unusual skirt construction, and similar features.

That's much closer to the actual information content of the costume.

Your eight orientations can remain in the compiler as a **coordinate vocabulary**. FRONT RIGHT THREE-QUARTER is still extremely useful for specifying a pose and QA'ing a result. But that does not mean you need a permanent high-quality costume render stored at every one of those coordinates.

In other words:

> **Keep the eight-view coordinate system. Stop requiring an eight-image asset set.**

I think that distinction would eliminate a surprising amount of pipeline overhead.

### Your character-subscene proposal is particularly strong

What you have discovered with your existing subscene system is very similar to **blocking / previs / layered compositing** workflows: solve a smaller visual problem in isolation, approve it, and then use that solved result as an input to the larger problem.

For a major character, I would make the character itself a first-class subscene.

Suppose the final shot calls for Tsaeytte walking away from the camera, torso mostly rear-facing, turning her head over her right shoulder toward another character.

Instead of asking the scene generator to reason from:

`BACK_RIGHT_3_4 costume turnaround + scene prompt + pose prose + head orientation prose`

I'd have a preceding stage whose entire job is:

**Produce Tsaeytte in exactly the pose needed for this shot.**

That stage gets the strongest references available:

`Canonical identity references`  
`+ body/proportion reference`  
`+ costume design references`  
`+ pose/staging constraint`  
`→ Shot-specific Tsaeytte`

Then the final scene gets:

`Shot-specific Tsaeytte`  
`+ other character subscenes`  
`+ environmental subscenes`  
`+ final scene description`

That is a much easier visual inference problem.

Current pose-control workflows explicitly do something analogous: they use one source for identity/appearance and another for pose, rather than expecting the appearance reference to already be in the desired orientation. OpenPose/ControlNet pipelines are specifically designed around “pose comes from this; character comes from that.” :chatgpt-content-reference{index="2"}

### It also explains why your rear views are disproportionately troublesome

I wouldn't read the persistent rear-view failures as evidence that your prompts or templates are fundamentally defective.

A back-facing costumed character is simply an unusually hostile case for generative models.

Your character-identity information is heavily concentrated in features like face shape, eyes, hair framing, jewelry, neckline, and other frontal cues. Then you're simultaneously saying, essentially, **“preserve this person very strongly, but conceal most of the strongest evidence that identifies this person.”**

The costume makes that conflict worse. Tsaeytte's outfits contain things like exposed midriff, necklines, breastplate construction, belts, jewelry, overskirt openings, embroidery and other semantically strong features whose canonical presentation tends to be frontal. A plain fitment-clothing mannequin has much less of that competing information, which fits your observation that the un-costumed rear references behave much better.

So you may be spending enormous effort perfecting a case that is intrinsically unstable, even though the resulting image is only an intermediate artifact.

That is a poor return on investment.

### The important safeguard is avoiding generational drift

There is one major danger in the subscene approach.

You do **not** want:

`Canonical Tsaeytte → posed Tsaeytte → scene Tsaeytte → crop from scene → next scene Tsaeytte → ...`

That turns into a visual game of telephone.

The shot-specific subscene should therefore never replace canon. It should be a **derived asset**.

I would make the authority hierarchy explicit:

**Level 1 — Canonical authority**  
Head identity, body identity, proportions, costume specification, props.

**Level 2 — Shot master**  
A generated and QA-approved image establishing the exact pose/orientation required by this particular shot.

**Level 3 — Scene rendering**  
Uses the shot master for composition, but can still receive Level-1 references for identity/costume reinforcement.

That means your final scene generator can effectively be told:

> This posed figure tells you **where she is and what she is doing**.  
> These canonical references tell you **who she is and what her costume actually is**.

That is a very clean division of authority.

### This would also make head/body independence easier

You've already run into the conceptual problem that your eight views combine body orientation and head orientation even though those are independent variables in scenes.

A shot-master stage naturally solves this.

Instead of needing an asset for:

`BACK RIGHT 3/4 body + RIGHT PROFILE head`

you construct that combination when you need it.

The number of possible combinations explodes once you include head direction, gaze, torso twist, limb pose, crouching, leaning, sitting, interacting with props, etc. An eight-view library cannot really solve that space anyway.

It only approximates it.

The subscene is the right place to resolve those variables.

### I would make the turnaround library sparse and lazy

There's another software-engineering analogy that I think fits your project particularly well: **don't eagerly compute the whole matrix.**

Maintain a small canonical set, and generate other views **on demand**.

If you eventually need a very good BACK LEFT THREE-QUARTER image of a particular costume, generate it because a real shot needs it. Once you get a good one, cache it. It may become useful later.

So over time you may end up with:

`FRONT ✓`  
`BACK ✓`  
`LEFT PROFILE ✓`  
`FRONT LEFT 3/4 ✓`  
`BACK RIGHT 3/4 — not generated`  
`BACK LEFT 3/4 ✓ because Chapter 4 needed it`

There is no reason a missing panel has to constitute an incomplete character.

That is particularly appropriate for a statistical generator, where every additional required asset incurs retries, QA, possible prompt adjustment, and possible downstream regeneration.

### There's also room for crude 3D without turning the project into a 3D project

One aspect of conventional digital production that maps extremely well onto what you're doing is using a crude rig purely for staging.

You do **not** need a beautiful 3D Tsaeytte.

A mannequin with approximately correct proportions could produce:

- camera angle,
- head direction,
- body orientation,
- arm and leg placement,
- occlusion,
- perspective,
- depth map,
- pose skeleton.

That image becomes structural conditioning, while your canonical references provide appearance. This is exactly the reason pose and depth controls are useful in contemporary image-generation workflows. :chatgpt-content-reference{index="3"}

Given how well your Face Gate and other targeted QA gates have worked, this fits the philosophy you've already been converging on: **make each stage solve one tractable problem instead of asking one gigantic prompt to solve everything simultaneously.**

### The architecture I think you're converging toward

I'd probably restructure the conceptual pipeline approximately like this:

```text
CHARACTER CANON
    Head identity
    Body identity / proportions
    Costume specification
    Costume front/back/key detail images
    Props
            │
            ▼
SHOT CHARACTER CONSTRUCTION
    Final camera-relative body pose
    Head orientation
    Gaze
    Expression
    Prop interaction
    Costume manifestation
            │
        QA / select
            │
            ▼
    CHARACTER SHOT MASTER
            │
            ├───────────────┐
            ▼               ▼
OTHER SUBSCENES       CANONICAL REFERENCES
            │               │
            └───────┬───────┘
                    ▼
              FINAL SCENE
```

The eight-view terminology stays available throughout that system for describing and evaluating orientation. But **eight finished costume images are no longer a prerequisite for entering it.**

And I would keep one more distinction: when two characters physically interact—embracing, fighting, carrying someone, handing an object over—I would generally make **the interacting pair/group the subscene**, rather than independently rendering each character. Their shared geometry is then solved before composition.

For what you've built so far, that seems like the larger lesson. Your subscene system isn't merely a workaround for complicated scenes. It may actually be the **better fundamental unit of generation**: isolate the smallest group of elements whose geometry must be jointly solved, get that right, freeze it, and move upward through the composition hierarchy.

So, yes: I think it is reasonable to stop treating a complete eight-view turnaround as mandatory. I would preserve the turnaround infrastructure because it has given you excellent **language, QA, and canonical design discipline**, but move the production pipeline toward **minimal canonical reference sets + pose-specific character subscenes + hierarchical composition**. That gets you the value the turnaround system has been providing without continually paying for its least reliable outputs.