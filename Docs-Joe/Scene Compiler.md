In the scene batch I named "TooManyPeople" for FirstDay / Chapter-01-Standing-in-Wonder, the Schoolboys and Kaeldor subscene consistently rendered too many people. An analysis of this failure is below. The images and the subscene prompt are in C:\Users\Joe\Projects\Zet_v5\output\TooManyPeople.

# Failure Analysis

Dude. There are several things in the prompt that can encourage Qwen Image 2.1 to duplicate characters, and the attached result is particularly revealing: it produced **five people instead of three**, and the extras look like alternate realizations of the specified characters rather than genuinely new characters.

The biggest issue is that the prompt effectively **introduces each character multiple times in different compositional contexts**.

### 1. Kaeldor is simultaneously given two spatial narratives

These instructions conflict:

> Kaeldor at right grins and points at the Schoolboy 2.

> Kaeldor appears in the right midground.

> Kaeldor is approaching from the far side of the archway.

> Entering the scene from the background, moving along the pathway.

The generated image interprets those almost literally as **two Kaeldors**: one standing at right pointing, and another entering through the archway.

This is probably the clearest cause of duplication in this particular image.

You intend:

**one Kaeldor who has just approached through the archway and is now at right.**

But the prompt describes both the final position and the action of entering from another spatial position. Image models can interpret that as two visual instances of the subject.

I would remove the narrative history entirely. Describe only the captured instant:

> Kaeldor stands at right, just beyond the archway, grinning and pointing toward Schoolboy 2.

Or, if he really needs to be inside the arch:

> Kaeldor is visible within the archway at right, walking toward the two schoolboys and pointing toward Schoolboy 2.

But not both.

### 2. The schoolboys are also effectively described twice

You first establish:

> Exactly three separate young elven males...

Then describe the complete interaction.

Later you restart:

> Schoolboy 1 appears in the left midground.  
> Schoolboy 1: ...

and then:

> Schoolboy 2 appears in the center midground.  
> Schoolboy 2: ...

This isn't inherently wrong, but generative image models don't parse prompts like a compiler resolving references to previously declared objects. Repeated descriptions can sometimes function almost like **additional subject declarations**.

Notice what happened in the generated image. There are effectively:

- red-haired Schoolboy 1
- dark-haired Schoolboy 2
- **another dark-haired schoolboy**
- large foreground Kaeldor
- background Kaeldor

That's suspiciously close to the structure of the prompt itself.

### 3. The prompt contains both a group-level scene specification and individual scene specifications

You have three conceptual layers:

**Group composition**

> From left to right: Schoolboy 1, then Schoolboy 2, then Kaeldor.

**Interaction composition**

> Red-haired Schoolboy 1 at left gently shoves dark-haired Schoolboy 2 at center...

**Individual composition**

> Schoolboy 1 appears in the left midground...

These all independently describe where people should appear.

For an LLM this redundancy reinforces the same semantic facts. For an image diffusion model, redundancy can sometimes reinforce the **visual objects themselves**.

I would distinguish between **declaring subjects** and **describing subjects** much more sharply.

### 4. "Moving" and "approaching" are risky in a single-frame composition

These lines are especially unnecessary:

> Schoolboy 1 moves right.

> Schoolboy 2 moves right.

> Kaeldor is approaching...

> Entering the scene from the background...

You're asking for:

> A single captured moment ... not a sequence

but subsequently describing temporal movement.

That can encourage something analogous to motion/time duplication: the model depicts a person at multiple implied stages of the action. It's the same family of problem seen when prompts say things such as "a woman walks from the doorway toward the table."

For a still image, I'd describe **pose and orientation**, not movement:

> Schoolboy 2 leans toward screen-right.

rather than:

> Schoolboy 2 moves right.

### 5. "Exactly three" is good, but I'd make the cardinality constraint structural

You already have:

> Exactly three separate young elven males

and:

> No other people

Those are good instructions. The problem is that they are fighting the rest of the prompt.

I'd make cardinality the first compositional rule and explicitly bind identities to slots:

> **SUBJECT COUNT: Exactly 3 people total.**  
> There are only three figures anywhere in the image.  
> Each named character appears exactly once.  
> 1. LEFT — Schoolboy 1  
> 2. CENTER — Schoolboy 2  
> 3. RIGHT — Kaeldor  
> No background figures, duplicate figures, distant figures, reflections, or additional students.

Then subsequent descriptions should modify those three already-established slots rather than seemingly instantiate them again.

### 6. The archway makes the Kaeldor duplication particularly easy

This is an interesting compositional issue illustrated by your result.

An empty archway naturally creates a **visual slot for another person**. Then the prompt says Kaeldor is both on the right and "approaching from the far side of the archway." Qwen has an extremely convenient solution available:

**Put Kaeldor in both places.**

If the archway isn't actually required for this subscene, I'd omit it entirely. Your initial environmental description only says:

> A simple stretch of stone pathway. Simple unobtrusive light background.

Yet later Kaeldor suddenly gets an archway. That effectively introduces another scene element and another location for him.

### How I would restructure this

I'd have your compiler produce something closer to:

> Create a landscape scene containing **exactly three people total**. Each character appears exactly once. There are no other people or background figures.
>
> From screen-left to screen-right, the three figures are **Schoolboy 1, Schoolboy 2, Kaeldor**. All three are shown full body, head to toe, together in the same captured moment on a simple stone pathway against an unobtrusive light background.
>
> Schoolboy 1 is a slim youthful male elf with pale warm skin, tousled copper-red hair and freckles, wearing [costume]. He stands at left, smiling as he gently places one hand against Schoolboy 2's shoulder in a playful shove.
>
> Schoolboy 2 is a youthful male elf with medium olive skin and short dark-brown hair, wearing [costume]. He stands at center, leaning away toward screen-right, laughing with both hands raised in mock protest.
>
> Kaeldor is a young male elf with warm tan skin, short light-brown hair with shaved geometric sides, wearing [costume]. He stands at right, grinning and pointing toward Schoolboy 2.
>
> The three figures interact as one cohesive group. Harmless schoolboy horseplay. Morning sunlight, clear optimistic atmosphere.
>
> **Exactly three people. Schoolboy 1 once, Schoolboy 2 once, Kaeldor once. No additional people, duplicate characters, background people, distant figures, or repeated depictions of any character.**

Then keep the image-reference instructions before this, but avoid repeating the scene positions/actions in those reference declarations.

I suspect the **highest-value compiler rule** is actually broader than this scene:

> **Describe only the character's state in the captured frame. Do not describe how the character arrived at that state or a previous/future spatial position.**

So instead of *"Kaeldor is approaching from the far side of the archway, entering the scene from the background"* → *"Kaeldor stands at right near the archway."*

And instead of *"Schoolboy 1 moves right"* → *"Schoolboy 1's body leans toward screen-right."*

That distinction between **pose/state** and **narrative/action history** should make your scene compiler substantially less prone to accidental character multiplication.