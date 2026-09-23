# Local Body-Reference Candidate Selection Pipeline

The Body-Reference Qwen Experiment has been a success. This experiment has been renamed as "Local Body-Reference" and will be the 
foundational automated, local pipeline that will run parallel to the traditional Manual GPT pipelines.

## Purpose

This document defines the intended image-selection process for generated body-reference views. This feature does not directly impact 
current Zet Pipeline functionality, however to the extent possible existing prompt templates and compilers should be used with the understanding that for later refinement it may be necessary to have slightly different behavior depending on the downstream processes.
The body-reference template has already had this kind of modification - tags to include or exclude depending on if it is a traditional or the new local pipeline.

The goal is **not** to make a local vision model perform a complete quality review. Local image generation is already producing a high percentage of usable candidates, so broad pass/fail reviews provide limited value and can reject otherwise strong images for minor or subjective reasons.

Instead, the process uses a sequence of **narrow rejection gates** to eliminate only obvious failures. Candidates that survive the gates are then ranked by a stronger model, with the final selection made by a human.

The overall process is:

> **Generate candidates → narrow binary gates → Luna ranking → human selection → selected image becomes an anchor for later views**

This approach treats image generation statistically: generate enough candidates that good results are likely to exist, cheaply remove obvious failures, then spend stronger-model and human attention only on the surviving set.

---

## Model Roles

### Gemma 4 12B

`gemma4:12b` is the first-stage culling model. This is the model in the "Image-Analysis-Alt" alias and is what should be set in the 
configuration.

Its role is deliberately limited:

- Inspect candidates for one specific failure mode at a time.
- Return only a binary `TRUE` or `FALSE`.
- Reject only when the specified defect is obvious.
- Preserve borderline or merely imperfect candidates for later ranking.
- Perform the inexpensive, high-volume part of the selection process.

Gemma is **not** expected to determine which image is best.

### Luna

Luna operates only on candidates that survive the gates.

Its role is comparative rather than binary:

- Rank surviving candidates.
- Identify which candidates most closely satisfy the intended body-reference specification.
- Compare strengths and weaknesses among otherwise viable images.
- For later views, consider consistency with the accepted anchor image.

Luna should not repeat the same coarse pass/fail job already handled by the gates.

### Human Review

Human review makes the final selection for each requested view.

The human reviewer can account for:

- aesthetic preference,
- subtle anatomy or proportion differences,
- character-specific physique,
- minor model inconsistencies,
- rendering quality,
- which candidate best fits the intended reference set.

The selected image becomes authoritative for that view.

---

# Gate Philosophy

## Gates Are Narrow Classifiers

Each gate answers **one question only**.

A gate should not perform a general review of the image and should not allow unrelated defects to affect its answer.

Examples:

- Face Gate asks only whether a detailed face was rendered.
- Proportion Gate asks only whether head-to-body scale is clearly implausible.
- Orientation Gate asks only whether the requested view is clearly wrong.
- Body Identity Gate asks only whether the candidate could plausibly depict the same body as the anchor.

This separation makes individual failures easier to understand, test, tune, and replace.

---

## Rejection Semantics

All gates use the same convention:

> **TRUE = reject the candidate for this defect**  
> **FALSE = do not reject the candidate for this defect**

The gates are intentionally conservative.

A useful shared rule is:

```text
Answer TRUE only when the specified defect is clearly visible.

If the result is borderline, ambiguous, within a plausible range, or primarily an aesthetic judgment, answer FALSE.

Return only TRUE or FALSE.
```

The objective is **high precision when rejecting**, not exhaustive defect detection.

False positives are more costly than false negatives at this stage: an imperfect image that survives can still be ranked poorly by Luna or rejected by the human reviewer, while a good image incorrectly rejected by a gate is permanently lost.

---

# Prompt and Conversation Structure

Each gate should use its own focused prompt.

The gates may be executed within one multimodal chat session so that the candidate image does not need to be repeatedly re-established, but later gates should **not depend on conclusions from earlier gates**.

Each gate should be treated as an independent judgment of the visible image.

A useful instruction for follow-up gate prompts is:

```text
Evaluate only the criterion below.
Do not infer the answer from previous evaluations.
```

Avoid requesting chain-of-thought, explanations, confidence scores, or broad image analysis during the gate stage.

Expected interaction:

```text
[Candidate image supplied]

Face Gate prompt
FALSE

Proportion Gate prompt
FALSE

Framing Gate prompt
FALSE

Orientation Gate prompt
FALSE
```

For later views, the Body Identity Gate also receives the accepted anchor image.

---

# Gate Definitions

## 1. Face Gate

### Purpose

Reject body-reference renders in which the mannequin head has become an actual rendered face.

The intended mannequin may contain basic head geometry, facial planes, shallow construction marks, ears, or minimal indications of feature placement. These should **not** cause rejection.

The gate is intended to catch obvious rendered eyes, lips, detailed noses, expressions, makeup, skin-like facial rendering, or character likeness.

### Prompt

```text
Inspect the head in the image.

Does the head contain clearly recognizable or rendered facial features, such as visible eyes, eyebrows, nose details, lips/mouth, or a human/elf-like facial expression?

Answer TRUE only if obvious facial features are visibly rendered.
Answer FALSE if the head is essentially a smooth mannequin head, even if it has basic face-plane geometry, ears, shallow construction marks, or minimal indications of feature placement.

Return only TRUE or FALSE.
```

### Interpretation

- `TRUE` → reject
- `FALSE` → continue

---

## 2. Proportion Gate

### Purpose

Reject candidates with an obvious head-to-body scale failure.

This gate is deliberately narrower than a general anatomy review. It should not reject an image merely because the reviewer would personally prefer a somewhat smaller or larger head.

The relevant question is whether the head size is clearly outside a plausible range for the depicted adult humanoid physique.

### Prompt

```text
Inspect the figure's head-to-body proportions.

Is the head clearly and materially too large or too small for the body, outside the plausible range for the depicted adult humanoid physique?

Answer TRUE only for an obvious head-to-body proportion error.
Answer FALSE if the proportions are plausible, borderline, or merely a matter of aesthetic preference.

Return only TRUE or FALSE.
```

### Interpretation

- `TRUE` → reject
- `FALSE` → continue

---

## 3. Framing Gate

### Purpose

Reject candidates that cannot function as a complete body reference because essential anatomy is cropped or omitted.

Small margins, slightly uneven positioning, or non-ideal composition should not cause rejection.

The gate should catch cases such as:

- top of head cropped,
- feet cropped,
- significant limb portions outside the frame,
- body incompletely rendered.

### Prompt

```text
Inspect the full-body framing of the figure.

Is any essential part of the figure clearly cropped, cut off, or missing in a way that prevents this image from serving as a complete full-body reference?

Consider the full head, torso, arms, hands, legs, and feet.

Answer TRUE only when meaningful body anatomy is visibly cut off or missing.
Answer FALSE if the entire figure is substantially present, even if margins or centering are imperfect.

Return only TRUE or FALSE.
```

### Interpretation

- `TRUE` → reject
- `FALSE` → continue

---

## 4. Orientation Gate

### Purpose

Reject candidates that clearly depict the wrong requested body view.

This gate should distinguish the eight canonical reference orientations without demanding mathematically exact rotation.

The intended canonical views are:

- FRONT
- FRONT_LEFT_3_4
- LEFT_PROFILE
- BACK_LEFT_3_4
- BACK
- RIGHT_PROFILE
- FRONT_RIGHT_3_4
- BACK_RIGHT_3_4

The directional label describes **which side of the subject is visible**, not which direction the figure appears to face on the image canvas.

For example:

- `FRONT_RIGHT_3_4` means primarily front-facing with the subject's **right side** also visible.
- `FRONT_LEFT_3_4` means primarily front-facing with the subject's **left side** also visible.

The actual prompt should inject the requested view and its concise definition.

### Prompt Template

```text
Evaluate only the requested body orientation.

Requested view: {VIEW}
Definition: {VIEW_DEFINITION}

Does the figure clearly show a substantially different body orientation from the requested view?

Answer TRUE only if the body is obviously in the wrong canonical view.
Answer FALSE if the orientation reasonably matches the requested view, including normal small variation in rotation.

Return only TRUE or FALSE.
```

### Interpretation

- `TRUE` → reject
- `FALSE` → continue

---

## 5. Body Identity Gate

### Purpose

For every view after the initial accepted view, compare the new candidate with the accepted anchor image and reject candidates whose physique is clearly incompatible with the anchor.

This is a **body identity** check, not a character-recognition check.

The comparison should focus on structural physique:

- head-to-body scale,
- shoulder width,
- torso length,
- waist structure,
- hip structure,
- limb length,
- overall body mass,
- general silhouette and build.

The gate should ignore expected differences caused by:

- viewpoint,
- perspective,
- pose,
- foreshortening,
- clothing deformation,
- minor rendering variation,
- lighting,
- mannequin-head appearance.

It should not require pixel-level correspondence.

The question is:

> Could these plausibly be the same underlying body viewed from different directions?

### Prompt

```text
Compare the body proportions and physique of the two figures.

Image 1 is the accepted body-reference anchor.
Image 2 is the candidate.

Ignoring viewpoint, perspective, pose, foreshortening, clothing deformation, and small rendering differences, is there an obvious incompatibility that would prevent these from plausibly representing the same underlying body?

Consider head-to-body scale, shoulder width, torso length, waist and hip structure, limb proportions, overall body mass, and general physique.

Answer TRUE only if the physiques are clearly incompatible.
Answer FALSE if they could plausibly be the same body viewed from different angles.

Return only TRUE or FALSE.
```

### Interpretation

- `TRUE` → reject
- `FALSE` → continue

### Applicability

The Body Identity Gate is not used when generating the first view because no accepted anchor exists yet.

Once the first view has been selected, that accepted image becomes the body anchor used for all subsequent reference views unless the workflow explicitly promotes a newer or different canonical anchor.

---

# First-View Workflow

The first requested body-reference view establishes the initial accepted physique.

A typical flow is:

```text
Generate candidate batch
        ↓
Face Gate
        ↓
Proportion Gate
        ↓
Framing Gate
        ↓
Orientation Gate
        ↓
Surviving candidates
        ↓
Luna comparative ranking
        ↓
Human selection
        ↓
Accepted first-view image becomes BODY ANCHOR
```

The gate order is not conceptually important, although cheap/high-value gates may be run earlier to avoid unnecessary later evaluations.

---

# Subsequent-View Workflow

After an anchor exists, generation is explicitly guided by that accepted body reference.

The generated candidates then pass through the same basic gates plus the Body Identity Gate.

```text
Accepted body anchor
        +
Requested new canonical view
        ↓
Generate candidate batch
        ↓
Face Gate
        ↓
Proportion Gate
        ↓
Framing Gate
        ↓
Orientation Gate
        ↓
Body Identity Gate
        ↓
Surviving candidates
        ↓
Luna comparative ranking
        ↓
Human selection
        ↓
Accepted image for requested view
```

The anchor serves two distinct purposes:

1. **Generation guidance** — encourage the image generator to preserve physique and body proportions.
2. **Post-generation verification** — allow the Body Identity Gate and Luna ranking to detect body drift.

---

# Luna Ranking Stage

Luna should receive only candidates that survived all applicable gates.

This stage should not be framed as another pass/fail review.

Its purpose is to establish an ordered preference among viable candidates.

The ranking should emphasize properties such as:

- fidelity to the requested canonical view,
- quality and clarity of the body-reference pose,
- believable anatomy,
- desirable and consistent head-to-body proportion,
- overall physique fidelity,
- clean mannequin-head execution,
- complete readable silhouette,
- consistency with the anchor for later views,
- absence of smaller defects not severe enough to trigger a gate.

The exact Luna ranking prompt can evolve independently of the gate prompts.

A useful conceptual instruction is:

> All supplied candidates have already passed coarse rejection checks. Rank them by how well they satisfy the body-reference specification and, where applicable, preserve the physique of the supplied anchor. Do not treat minor imperfections as automatic failures; compare the candidates against one another.

The purpose of ranking is to preserve information that is lost in a binary review. Two images can both be technically acceptable while one is still materially better for the reference set.

---

# Human Selection Stage

The final choice remains a human judgment.

The human reviewer should see:

- the surviving candidates,
- Luna's ranking,
- preferably Luna's concise reasons for the ranking,
- the current anchor when selecting later views.

The human may choose a lower-ranked candidate when subtle visual considerations outweigh Luna's preference.

The selected candidate becomes the accepted image for that canonical view.

---

# Gate Design Rules

When adding future gates, use the same principles.

A useful gate should satisfy all of the following:

1. It targets one recognizable failure pattern.
2. The defect can usually be judged visually without broad interpretation.
3. An obvious failure is sufficient reason to discard the candidate.
4. Borderline cases can safely proceed to Luna and human review.
5. The gate can be expressed as a conservative `TRUE`/`FALSE` question.
6. The gate should not duplicate judgments better handled by comparative ranking.

Avoid converting the gate layer into a comprehensive quality-assurance rubric. Its value comes from being simple, inexpensive, and conservative.

---

# Validation Principle

The appropriate model for the gate stage is determined by practical error behavior, not by general benchmark strength.

For each gate, the key question is:

> Does the gate reliably eliminate obvious failures while almost never eliminating an image a human would have wanted included in the Luna ranking?

The most important failure mode to measure is therefore a **false rejection**.

A useful evaluation set can record:

```text
Candidate
Face Gate
Proportion Gate
Framing Gate
Orientation Gate
Body Identity Gate
Human keep/reject
```

From this, individual gates can be tuned without changing the overall pipeline.

A gate that allows some bad images through may still be useful because Luna and the human reviewer remain downstream.

A gate that frequently eliminates desirable images should be loosened, rewritten, or removed.

---

# Summary

The selection system is intentionally asymmetric:

- **Image generation** explores a large stochastic candidate space.
- **Gemma 4 12B gates** cheaply remove specific obvious failures.
- **Luna** ranks the remaining viable candidates.
- **Human review** makes the final aesthetic and technical choice.
- **Accepted views** become reference anchors that help maintain body identity across the full view set.

The gate layer should remain narrow and conservative.

Its job is not to determine whether a candidate is excellent.

Its job is to answer:

> **Is there one clear, predefined reason this candidate should not consume further review effort?**
