
### 1. Introduce an explicit pass/fail hierarchy

Right now almost every authored constraint can become a veto. Luna is therefore behaving rationally when it sees:

> no cast shadow, contact shadow...

and turns a harmless floor shadow into a hard failure.

I would establish three severity classes in the QA instructions:

* **Primary / fail-worthy:** body proportions, anatomy, requested orientation, framing, stance, gross body-type drift, mannequin-vs-character-head failure, missing required species morphology.
* **Secondary / fail only when materially wrong:** fitment clothing, silhouette readability, background clutter, lighting that obscures anatomy.
* **Incidental / never sufficient alone to fail:** faint grounding shadows, tiny color differences, minor seams, subtle background gradients, slight surface texture, inconsequential rendering artifacts.

Most importantly, explicitly say that **the purpose of the review is to determine whether the image functions as a usable body reference, not whether every generation instruction was literally satisfied**.

Something like this near the very beginning would substantially change Luna's behavior:

```text
Judge whether the candidate is a usable technical body reference, not whether it is a literal pixel-level realization of every generation instruction.

Apply constraints by material importance.

PRIMARY requirements can cause failure:
- correct body proportions and anatomy
- correct head-to-body scale
- correct requested body/head orientation
- complete full-body framing
- neutral readable stance
- required species morphology
- absence of major unrequested elements that obscure the body

SECONDARY requirements should cause failure only when the deviation materially reduces the usefulness of the image as a body reference:
- fitment clothing details
- studio background treatment
- lighting
- small rendering or surface differences

Do not fail an otherwise valid reference solely for incidental differences such as a faint floor contact shadow, subtle ambient shadow, small background gradient, minor clothing seams, or similarly non-obstructive details.
```

That gives Luna permission to exercise the judgment you actually want.

### 2. Define exactly what "head size" means for nonhuman anatomy

This is the most important fix for the local model.

Your present wording says:

> First assess head-to-body scale...

but never defines the geometry being compared. A small model sees the complete visible head silhouette—including ears—and concludes that it is enormous.

Add a specific measurement rule:

```text
For head-to-body proportion, evaluate the CRANIUM / MANNEQUIN HEAD MASS, not the total silhouette created by species appendages.

For elves, pointed ears are species morphology and must be excluded when estimating head width or head-to-shoulder proportion. Measure apparent head width from the left and right sides of the cranial/skull mass approximately where human temples and cheeks would lie. Do not measure from ear tip to ear tip.

Likewise, do not treat long ears, horns, antlers, hair, headgear, or similar protruding structures as part of cranial size unless the specification explicitly says otherwise.
```

I would make that unusually explicit. Small vision-language models often benefit from a procedural definition rather than a conceptual instruction.

You can reinforce it with:

```text
A wide ear-tip-to-ear-tip span is not evidence of an oversized head.
```

That single sentence may eliminate a surprising number of false negatives.

### 3. Change "first assess..." into "assess independently"

This passage may also be contributing:

> First assess head-to-body scale ... A visibly oversized or undersized head ... is a primary failure...

It heavily primes the reviewer to find a proportion problem. This is useful when correcting a systematic image-generator defect, but it also increases false positives.

I would retain head scale as important, but make the reviewer establish evidence rather than hunt for a defect:

```text
Assess each primary body property independently. Do not presume that a defect exists because a property is listed as important. Fail a proportion only when the visible anatomical mass clearly departs from the requested adult proportions.
```

And later:

```text
When judging proportion, distinguish apparent width caused by perspective, pose, ears, hair, clothing, or other extensions from the underlying anatomical proportion.
```

### 4. Give the reviewer a "materiality test"

This should help Luna particularly.

Before issuing a failure, require it to ask:

```text
Materiality test:
Would correcting this defect materially improve the image's usefulness as a technical body reference?

If no, the defect is not sufficient for failure.
```

For your example:

* Correcting the head size? Yes, **if** the actual cranium were oversized.
* Removing that soft floor shadow? No.
* Correcting a rotated torso in a front reference? Yes.
* Changing an olive-green short seam? No.

This converts the analyzer from a compliance checker into a QA reviewer.

### 5. Explicitly distinguish "grounding" from a problematic shadow

If you still want shadows evaluated, I would define the actual failure mode:

```text
Background/lighting should support an unobstructed technical read.

A faint diffuse contact or grounding shadow is acceptable. Fail for shadowing only when it is strong, directional, dramatic, confusing, merges the feet into the floor, obscures anatomy, distorts the apparent silhouette, or substantially departs from a neutral technical-reference presentation.
```

That is much closer to your apparent intent than literal `no contact shadow`.

### 6. Don't give the analyzer every generator constraint at equal apparent authority

This is probably the larger architectural improvement.

The generator prompt is a **construction specification**. The analyzer prompt should be a **validation specification**. They should not be identical.

You can continue passing the compiled prompt, but tell the analyzer that the authoritative spec contains both:

* requirements that determine whether the reference is valid;
* generation guidance intended to steer appearance.

The analyzer should not automatically promote the latter into rejection criteria.

I would insert:

```text
The supplied authored prompt is a generation specification and therefore contains both essential requirements and generation guidance. Do not assume every sentence is an independent pass/fail criterion. Interpret it according to the QA priority rules above.
```

That may be enough without changing your compiler at all.

### 7. If you do omit compiler-generated sections from QA, I would omit selectively

I would **not** strip most of the Body/stance section, because it contains exactly what the reviewer needs.

The first things I would consider withholding from the analyzer are:

1. The exact background prohibition:

   > `no cast shadow, contact shadow, halo, or vignette`

2. The highly specific background construction language:

   > `plain smooth very light desaturated blue-gray... flat matte light neutral-gray... featureless and uniform...`

Replace its role in QA with the general requirement already in your reviewer prompt: **plain neutral technical background with clear subject separation**.

I would probably also omit:

> `Render in the Canonical Art Style: Painterly semi-realistic fantasy illustration with anime-influenced facial proportions, large expressive eyes...`

for a mannequin-head body reference. It is generator guidance and partly conflicts semantically with:

> `Do not add ... facial features`

Even if the models usually resolve the later instruction correctly, there's little reason for the body-reference reviewer to consider "large expressive eyes" at all.

I would leave the clothing, mannequin-head, species, body, stance, orientation, and framing sections available to QA.

### 8. I'd alter your final failure instruction slightly

Currently:

> For a fail, name the most important visible defect...

That's good, but I'd require a threshold:

```text
Return pass=false only when at least one PRIMARY requirement is visibly violated, or when a SECONDARY defect is severe enough to materially compromise the image as a technical body reference.

When failing, identify the single most consequential defect and describe the visible evidence for it.

Do not fail based on a merely detectable deviation.
```

"Detectable deviation" versus "material defect" is an important distinction for Luna.

### A revised top section

If I were making the minimum practical change, I would replace just your introductory QA prose with roughly this:

```text
You are a Body-Reference visual QA reviewer. Determine whether the candidate is a usable technical body reference that materially satisfies the supplied specification. Judge only visible evidence.

Do not treat every sentence in the generation specification as an equally weighted pass/fail criterion. The specification contains both essential reference requirements and lower-priority generation guidance.

PRIMARY requirements:
- believable head-to-body and overall anatomical proportions for the specified subject
- sound neck attachment, torso-to-leg balance, limb lengths, body mass, shoulder/hip structure, and anatomy
- exact requested body and head orientation
- complete required framing
- neutral readable stance
- required species morphology
- mannequin head requirements when specified

A clear violation of a PRIMARY requirement is a failure.

SECONDARY requirements include fitment-clothing details, exact studio-background treatment, exact lighting treatment, minor color variation, seams, and other presentation details. A SECONDARY deviation causes failure only if it materially interferes with silhouette, anatomical readability, pose evaluation, or usefulness as a technical body reference.

Incidental differences are not sufficient for failure. Examples include faint diffuse floor/contact shadows, subtle background gradients, minor fitment seams, small color deviations, and similarly non-obstructive rendering differences.

When judging head-to-body scale, evaluate the actual cranial/head mass. Exclude species appendages and external extensions from the measurement. For an elf, do not include pointed ears or ear-tip span when estimating head width. Compare the skull/face oval itself with shoulders, torso, and total body height. A wide ear-tip-to-ear-tip span is not evidence of an oversized head.

Assess proportions from anatomical structure rather than total silhouette. Do not infer proportion errors from ears, hair, clothing, headgear, or other protrusions.

Before failing, apply this materiality test: would correction of the visible defect materially improve the image's usefulness as a technical body reference? If not, it is not sufficient for failure.

Then check the supplied specification. Simple fitment clothing specified below, including a tube top and compression shorts when requested, is not costume. Variation in its cut or seams is low priority; fail fitment only if it materially obscures the body silhouette or adds substantial unrequested garments.

When a featureless mannequin head is specified, visible facial features, hair, or character likeness are material failures.

Use uncertain only when an important PRIMARY visual trait truly cannot be judged from the image. Do not use uncertain because a low-priority presentation detail is ambiguous. A clear visual pass must have pass=true and uncertain=false. If uncertain=true, set pass=false and explain the unresolved primary trait.

For a fail, name the single most important material visible defect in failure_reason and cite its image evidence. Do not fail solely because a minor deviation can be detected.

Return only the requested JSON object.
```

I think this would fix both examples without making the analyzer permissive about the things you actually care about. In particular, it changes the model's mental task from **"find a violated sentence"** to **"decide whether this succeeds as a body-reference asset."**
