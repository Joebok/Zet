Dude, I think you're heading in the right direction. For Qwen Image 2.1, I would move away from a compiler that assembles a large collection of independent constraints and toward a narrative-first scene specification, supported by a small number of deterministic reference and composition rules.

The important distinction is that the compiler should no longer be responsible for constructing the scene description. Its job should be to supply identities, resolve references, enforce a few essential constraints, and package a scene description that has already been written as coherent prose.

Qwen Image 2.1 is particularly suitable for experimenting with this approach. Its official documentation supports multi-reference character composition, and its own examples use natural-language descriptions of characters interacting rather than elaborate positional schemas. Its official image-edit prompt guidance also explicitly separates the roles of reference images from the intended new composition.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://github.com\&sz=32)

GitHub

+2



There isn't yet a single established prompt anatomy comparable to classic Stable Diffusion prompting. What follows is the structure I would use for Zet, based on the model's documented behavior and the problems you've encountered.

## 1. Recommended prompt anatomy

I would organize the prompt into seven conceptual sections, in this order.

1\. Scene intent

Narrative

What is happening? Who is involved? What is the emotional or dramatic point of the moment?

2\. Cast and references

Deterministic

Bind each named character to an image and specify what that reference controls.

3\. Action and interaction

Narrative

Describe poses, gestures, eye contact, reactions, and physical relationships as one coherent event.

4\. Staging and camera

Composition

Establish screen positions, relative scale, orientation, camera angle, framing, and negative space.

5\. Setting and physical context

Narrative

Provide only the objects and surroundings necessary to support the action.

6\. Visual treatment

Technical

Art style, lighting direction, palette, perspective, and rendering consistency.

7\. Output and compositing constraints

Technical

Crop, canvas, transparency/background treatment, character count, and what must remain available for compositing.

The order matters conceptually, although I wouldn't treat it as a proven hierarchy of model attention.

Start with what the scene means, then identify the people, then explain what they are doing. Only after establishing the action should you constrain how it is photographed or illustrated.

This makes the narrative the organizing principle of the prompt.

You could collapse these seven sections into just four during generation:

1. Scene: Intent, action, interaction, and staging, expressed as natural prose.
2. References: Character identities and any critical distinguishing features.
3. Rendering: Style, lighting, camera, environment.
4. Constraints: Output requirements and compositing restrictions.

The seven-part structure is useful for building and interviewing; the four-part structure is probably closer to what I would actually send to Qwen.

## 2. Example: staging a scene at the Spire

Consider a sub-scene showing Valindia making a cutting remark to Tsaeytte, with Kaeldor observing.

Rather than treating these as three characters with separate pose definitions, write the scene as an interaction between people.

ILLUSTRATIVE COMPILED PROMPT

Scene

Three elven academy students are caught in an uncomfortable social confrontation. Valindia has just made a cutting remark to Tsaeytte, who appears more amused than intimidated. Kaeldor, standing slightly apart, watches the exchange with awkward uncertainty. The mood is tense but playful, with the characters' expressions and body language carrying the story.

Cast and references

\<image1> depicts Tsaeytte. Preserve her recognizable face, violet eyes, black bob, pointed ears, proportions, and clothing. Use this image for her appearance, not her pose or camera orientation.

\<image2> depicts Valindia. Preserve her recognizable identity, distinctive two-tone hairstyle, proportions, and clothing. Her source pose and gaze are not authoritative.

\<image3> depicts Kaeldor. Preserve his appearance and academy clothing. Repose him to participate naturally in the new scene.

Action and interaction

Valindia leans slightly toward Tsaeytte with a superior, dismissive smile, one hand resting on her hip while the other makes a small, pointed gesture toward Tsaeytte. Tsaeytte stands comfortably with her weight shifted onto one leg, head tilted toward Valindia, responding with a sly, knowing smile. Their eyes meet. Kaeldor stands behind and between them, watching Valindia with a slightly uneasy expression, as though deciding whether to intervene.

Their gestures and expressions belong to the same instant of conversation. Each character responds naturally to the others rather than independently posing for the viewer.

Staging and camera

Tsaeytte stands at screen-left, Valindia at screen-right, facing inward toward one another in opposing three-quarter views. Kaeldor is farther back, visible in the space between them. Tsaeytte and Valindia occupy the foreground at a consistent scale, with Kaeldor slightly smaller due to perspective. The camera is at approximately chest height, showing all three characters from head to foot with space around their silhouettes.

Setting

The characters stand on level stone paving outside an elven academy. The immediate ground plane establishes their footing, but architectural surroundings are omitted because the figures will be composited into a separately rendered background.

Visual treatment

Painterly semi-realistic fantasy illustration with anime-influenced facial stylization and refined linework. Soft natural daylight from the upper left, consistent lighting across all three figures, believable shadows and fabric folds.

Output constraints

Exactly three characters, each appearing once. No additional people, reflected figures, or duplicated body parts. Preserve all complete character silhouettes, including feet, ears, hair, and clothing. Use a transparent background where supported, with sufficient separation between the figures for the later composite.

This prompt still has substantial structure, but notice what it doesn't do: it doesn't describe each character as an isolated collection of joints, rotations, facial expressions, and costume fields.

Instead, the actions and poses emerge from a single coherent social moment.

### Why I would put the cast after the scene introduction

The opening paragraph gives the model a conceptual understanding of the desired result before introducing the image bindings.

This is not necessarily better than introducing references first for every model or pipeline. In fact, Qwen's official multi-reference instruction format emphasizes an opening operation statement and explicit individual image roles.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://huggingface.co\&sz=32)

Qwen/Qwen-Image-2.1-PE-I2I at main



I would therefore experiment with two short openings:

Narrative-first:

> Three elven students confront one another outside an academy. Create a new illustration of this scene using the three supplied character references.

Operation-first:

> Create a new three-character scene using the supplied images as identity references. The scene shows an uncomfortable confrontation between three elven academy students.

My starting preference would be the second for multi-reference editing, immediately followed by the narrative scene description. It establishes that the images are reference material, not existing canvases whose layouts should be preserved.

That distinction is especially important when your source images are character turnarounds.

## 3. For interaction, relationships are more important than poses

This is probably the single biggest change I would make to your current approach.

A conventional character-placement schema might contain:

| Character | Pose                       | Gaze     | Position    |
| --------- | -------------------------- | -------- | ----------- |
| Tsaeytte  | Standing, hand on hip      | Valindia | Left        |
| Valindia  | Leaning forward, gesturing | Tsaeytte | Right       |
| Kaeldor   | Standing, hands relaxed    | Valindia | Center rear |

These fields are individually valid, but they don't explain why the gestures belong together.

The narrative version is more informative:

> Valindia leans toward Tsaeytte as she makes a cutting remark, her superior smile emphasizing the insult. Tsaeytte answers with a knowing grin rather than the embarrassment Valindia expects. Kaeldor watches from a short distance behind them, visibly uncomfortable with the exchange.

This expresses a small dramatic event. The body positions, gazes, and expressions have a common cause.

I'd use three levels of specificity:

- Narrative direction: The social, emotional, or physical action. This should be freeform.
- Spatial anchors: Who is left, right, in front, behind, touching, or looking at whom. These should be explicit when important.
- Hard constraints: A few nonnegotiable facts such as character count, visible objects, or required orientations.

The key is to avoid stating the same fact in all three levels unless it is genuinely critical.

For example, if Tsaeytte is supposed to be looking at Valindia, don't independently describe her gaze, nose direction, head rotation, torso orientation, and target character in several sections. Usually the interaction description plus one orientation instruction is enough to start.

## 4. Separate the sub-scene's narrative composition from its placement in the final scene

Because you're rendering sub-scenes independently, I think you need two coordinate systems.

Image: Docs\Narrative_Scene_Approach.svg

Conceptual separation: Qwen determines the figures' relationships inside the sub-scene; Zet determines where the resulting group belongs in the final canvas.

Local composition concerns the characters' relationship to one another:

- Who stands on which side?
- Are they facing each other?
- Do they overlap?
- Which figure is in the foreground?
- What is the camera perspective?

Global composition concerns how the finished sub-scene fits into your larger scene:

- Where is the group positioned?
- What scale should it have relative to other sub-scenes?
- How much available space does it occupy?
- What is its layer depth and relationship to the final background?

I would keep global placement largely out of the Qwen prompt.

For example, there is no need to tell Qwen that this confrontation is to occupy the bottom-left 35% of a 16:9 master scene if Zet is going to scale and translate the resulting image during composition.

What Qwen does need to know is that the camera looks slightly downward, that the figures are full-length, that their feet are all on the same physical ground plane, and that Valindia's gesture must remain visible.

There is one caveat: the camera and perspective must be coordinated with the master scene. You cannot freely move an eye-level foreground group into an elevated background position and expect the composite to look correct.

So camera angle, viewing direction, light direction, and relative character scale should be inherited from the master scene, even when global placement isn't.

For transparency, Qwen Image 2.1 now supports native RGBA output according to its official documentation. That makes it worth testing true transparent sub-scenes, but I would still validate alpha edges, fine hair, and shadows rather than assume every output is compositing-ready.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://github.com\&sz=32)

GitHub



## 5. Design the interview around storytelling, not prompt fields

I would make the input process resemble a brief conversation with an illustrator or scene director.

Start with one open-ended question:

> Describe what is happening in this sub-scene. Who is involved, what are they doing, and what is the important moment you want to capture?

Then have an LLM analyze the response and identify what it still needs.

The interview should resolve five concerns, but not necessarily ask five questions.

| Concern     | What the interview needs to establish                                            |
| ----------- | -------------------------------------------------------------------------------- |
| Narrative   | What moment is being depicted? What reactions or emotions matter?                |
| Cast        | Which characters and reference assets should be used?                            |
| Staging     | Are there important positions, gestures, orientations, or physical interactions? |
| Context     | What props, surfaces, or environmental details are needed for the action?        |
| Composition | What must be visible? How is the scene framed?                                   |

For example, if you say:

> Valindia makes a snide comment to Tsaeytte, who reacts with amusement. Kaeldor stands behind them looking uncomfortable.

The LLM might identify only two meaningful ambiguities:

- Should Valindia and Tsaeytte face one another directly, or should both be oriented partly toward the viewer?
- Is this a full-body scene or a waist-up conversation?

It shouldn't ask about the art style, costume, eye color, or lighting if those can already be obtained from Zet's assets and master scene settings.

An especially useful improvement would be letting the LLM propose a staging description, rather than asking you to specify individual poses. You could accept the proposal or make a correction, and the system would rewrite the narrative accordingly.

## 6. Keep structured data, but change what it represents

I wouldn't eliminate the schema or compiler. I would significantly reduce the amount of creative information they attempt to encode.

The fundamental architecture I would aim for is:

Scene interview

User describes story and directs revisions

Narrative scene description

Coherent, editable prose defining the interaction

Deterministic enrichment

Character and costume references

Master scene camera and lighting

Relevant props and objects

Composition and output rules

Final Qwen prompt and ordered image references

A concise narrative prompt with explicit reference bindings and rendering instructions

The scene record could be quite small:

```

subscene:
  id: academy_confrontation

  narrative: |
    Valindia makes a cutting remark to Tsaeytte,
    who responds with amused confidence.
    Kaeldor watches uncomfortably from behind.

  staging: |
    Tsaeytte and Valindia face each other
    in opposing three-quarter views.
    Kaeldor stands slightly behind them.

  cast:
    - character: Tsaeytte
      reference: tsaeytte_adventure_front
    - character: Valindia
      reference: valindia_academy
    - character: Kaeldor
      reference: kaeldor_academy

  framing: full_body
  camera: inherit_master_scene
  lighting: inherit_master_scene
  style: inherit_master_scene
  output: transparent

```

Notice that this doesn't attempt to store every body orientation, eye direction, elbow angle, or interpersonal relationship as a separate machine-readable property.

The schema holds the instructions and asset bindings, not an exhaustive model of the finished image.

If there is a hard requirement, such as Tsaeytte holding something in her anatomical right hand, you could still store that as a specific constraint and let the compiler apply your left/right translation system.

Most scenes won't require many such constraints.

### A small but important architectural choice

I'd distinguish between:

Authoritative information

Fixed details such as character identities, chosen costume references, and the intended number of subjects.

Creative direction

Narrative instructions describing how those characters behave in the particular scene.

Inherited context

Style, camera, perspective, and lighting requirements from the overall scene.

This should prevent the compilation process from repeatedly injecting broad character descriptions that conflict with the requested view or action.

Your existing per-view character templates could still be useful as asset metadata, particularly for critical identity features, without injecting the entire template into every scene.

## 7. Let the LLM compose the final prompt

I would go one step further than simply concatenating the seven sections.

Have the LLM produce the final Qwen prompt from the narrative description and deterministic context.

Give the LLM rules such as:

- Preserve named character bindings and essential scene facts.
- Describe interactions as coherent events rather than unrelated poses.
- Integrate staging instructions naturally into the action.
- Include only character details that help distinguish or preserve identities beyond the supplied reference images.
- Do not invent additional characters or significant props.
- Eliminate contradictory or redundant instructions.
- Keep critical technical constraints explicit.

This introduces some nondeterminism in the wording, but not necessarily in the underlying scene requirements.

You could preserve the intermediate narrative, reference bindings, and final generated prompt separately, allowing you to reproduce a job exactly or deliberately regenerate the wording.

I would also keep a mode that performs deterministic assembly of the same inputs. That gives you an easy comparison between the LLM-authored prompt and a conventional compiler-assembled prompt.

## 8. Test the approach before rebuilding Zet

I would avoid a major redesign until you've compared a few prompt structures on the same scenes.

Try three alternatives:

| Approach               | Description                                                        | What it tests                                |
| ---------------------- | ------------------------------------------------------------------ | -------------------------------------------- |
| A. Structured          | Existing compiler-produced prompt                                  | Baseline                                     |
| B. Narrative sections  | Seven-part structure, assembled directly                           | Whether narrative emphasis and ordering help |
| C. Narrative synthesis | LLM rewrites scene + references + constraints into a fluent prompt | Whether coherent prose improves results      |

Use the same character references, scene specification, camera, dimensions, and comparable seeds across each set of runs. Evaluate multiple candidates per approach.

I would focus evaluation on four outcomes: correct character identities, convincing interaction, successful staging, and compositing suitability.

It's particularly important to distinguish a failure of the image model from a failure of the prompt structure. For example, if all approaches have difficulty producing three simultaneous correct gaze directions, that may point to a model limitation rather than a prompt-format problem.

There is no need to invent a comprehensive new evaluation system for this experiment. Your existing multi-candidate review process can provide the comparisons.

## My suggested starting point

I would adopt this compact target anatomy as the first prototype:

Target prompt layout — Version 1

```
1. SCENE
   Brief narrative describing the moment,
   characters, action, and emotional tone.

2. REFERENCES
   Named cast members bound to <imageN>.
   What to preserve and what to ignore.

3. INTERACTION AND STAGING
   Coherent description of gestures,
   reactions, spatial relationships,
   orientations, and visible props.

4. CAMERA AND COMPOSITION
   Framing, perspective, relative scale,
   visibility, and overlap.

5. VISUAL TREATMENT
   Style, environment, lighting,
   and inherited master-scene context.

6. OUTPUT CONTRACT
   Exact cast count, full silhouettes,
   background/alpha, and essential
   compositing constraints.
```

This is deliberately less formal than your current scene compiler, but it remains systematic enough to generate through an interview and integrate into Zet.

One final consideration: I would give the scene narrative priority over the reference descriptions, and the reference descriptions priority over generic aesthetic instructions. That is a design policy for the prompt-generation system, not a claim that Qwen automatically obeys this priority order.

The main principle I'd use for the redesign is:

Describe the event first. Describe the characters as participants in that event. Use the structured system to guarantee identity and technical consistency, not to choreograph every movement.

That strikes me as the most productive change to test before making any substantial modifications to your existing schema or compiler.