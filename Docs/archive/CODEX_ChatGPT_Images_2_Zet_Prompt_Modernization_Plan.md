# Zet Prompt Compiler Modernization Plan for ChatGPT Images 2.0

**Prepared:** 2026-09-04  
**Audience:** CODEX / Zet maintainers  
**Scope:** Modernize the deterministic `Final_Image_Prompt.md` generation pipeline and related reference-image workflow for the current ChatGPT Images 2.0 generation/editing behavior.

---

## 2026-09-09 — ChatGPT Images 2.5 Addendum

ChatGPT Images 2.5 strengthens the preservation, precise-editing, and multi-turn behavior this plan targets. Zet now identifies newly compiled manual-render artifacts with engine profile `chatgpt_images_2_5_v1`; existing 2.0 artifacts remain historical and are not migrated.

Zet's `render_mode` is an internal image-authority contract, not an OpenAI API field. The supported values remain `generate`, `edit`, and `composite`. A future repair attempt will remain an `edit` and carry separate attempt lineage instead of adding a fourth render mode.

The current V2 prompt text remains the initial 2.5 baseline. Preservation and orientation constraints will not be removed based on the release announcement alone: OpenAI's 2.5 prompting guidance recommends testing unchanged prompts and complete edit sequences, and warns that repeated edits can still change details intended to remain fixed.

Manual final-image submission now records whether follow-up image generations were needed, how many additional images were generated, and an optional process note. These immutable answer records provide first-pass and refinement statistics before Zet commits to guided or automatic repair prompts. Dashboard metrics begin with the 2.5 rollout on 2026-09-09; missing telemetry encountered from that date forward is reported as unknown, while older 2.0 artifacts remain untouched and outside the live dashboard scan. Flare/Sunburst selection remains out of scope while production rendering is performed manually in ChatGPT rather than through the Images or Responses API.

Official references:

- https://developers.openai.com/api/docs/guides/image-prompting
- https://developers.openai.com/api/docs/guides/image-generation

---

## 1. Executive Summary

The existing Zet image pipeline has a strong architectural foundation: deterministic Python compilation, explicit source maps, versioned prompt templates, typed pipeline stages, reference manifests, human image review, and scene IR. Those pieces should be preserved.

The main change should **not** be “make prompts shorter” as an isolated goal. The change should be:

> **Compile a smaller number of higher-value, non-conflicting semantic constraints, with explicit image-input roles and explicit change-vs-preserve contracts.**

The current pipeline still contains defensive prompt patterns developed for earlier image models:

- repeated “preserve exactly / do not reinterpret / do not change” language;
- a mandatory generic anatomy/avoid/final-verification tail appended to every scene;
- large canonical identity blocks repeated even when a strong visual reference is already supplied;
- reference metadata that is stored in the IR but not fully honored by the final prompt compiler;
- normalization that discards exactly the spatial and relational facts that the current engine handles well when they are stated explicitly;
- scene placement code that can generate generic or contradictory prose such as a falling group that “stands” in the background;
- manual corrective facts—relative scale, expected occlusion, supporting-subject facing—being added only after a failed render instead of existing as first-class structured fields.

OpenAI's current guidance for ChatGPT Images 2.0 / `gpt-image-2` is consistent with this direction:

1. clear prompts do not need to be long;
2. use skimmable structure for complex requests;
3. explicitly distinguish what changes from what remains invariant;
4. for people, state framing, gaze, scale, pose, and object interactions;
5. index multiple input images and state each image's role;
6. improve images through small targeted edits rather than continually overloading one giant prompt.

The recommended architecture is therefore:

1. **Keep Python-owned deterministic compilation.**
2. **Introduce typed image-input roles and one explicit edit-base/canvas authority.**
3. **Restore structured spatial/interaction facts to the IR instead of flattening or dropping them.**
4. **Replace the unconditional generic tail with a conditional risk-constraint compiler.**
5. **Emit compact identity anchors when a visual reference exists; emit full descriptive identity only when needed for text-only fallback.**
6. **Treat corrective rerenders as edit/revision jobs against the previous candidate whenever possible.**
7. **Add regression fixtures based on the actual recent Zet failures and corrections.**
8. **Roll out as a versioned V2 compiler behind a flag with side-by-side prompt generation and A/B render evaluation.**

Do not rewrite the current pipeline as an AI prompt-refinement system. `Final_Image_Prompt.md` should remain deterministic and statically generated from structured data and authored templates.

---

## 2. Research Basis: Current OpenAI Image Behavior

The recommendations in this plan use the current public OpenAI guidance as of 2026-09-04.

### 2.1 ChatGPT Images 2.0

OpenAI introduced **ChatGPT Images 2.0 on 2026-04-21** as the current image-generation model in ChatGPT. Paid ChatGPT plans can also use image generation with Thinking, where the model can plan/refine the requested image before generation.

Relevant sources:

- OpenAI: https://openai.com/index/introducing-chatgpt-images-2-0/
- OpenAI Help: https://help.openai.com/en/articles/11084440-chatgpt-images
- OpenAI release notes: https://help.openai.com/en/articles/6825453

### 2.2 Prompting guidance that matters to Zet

OpenAI's current ChatGPT image guide says that many good image prompts are only a few clear sentences; material constraints should be stated directly; image edits should distinguish the requested change from everything that should remain the same; multiple uploaded images should be referred to by order and relationship; and iterative improvements work best as small, targeted revisions.

Source:

- OpenAI Academy: https://openai.com/academy/image-generation/

The current developer prompting guide for `gpt-image-2` recommends:

- a consistent prompt order;
- short labeled sections for complex requests;
- concrete framing, viewpoint, placement, gaze, and object interaction;
- explicit preserve/change invariants for edits;
- explicit image indexing for multi-image inputs;
- small iterative changes instead of continually adding more instructions.

It also identifies `gpt-image-2` as the recommended image model for new builds and specifically calls out identity-sensitive editing and compositing.

Source:

- OpenAI Developer Cookbook: https://developers.openai.com/cookbook/examples/multimodal/image-gen-models-prompting-guide

### 2.3 Important applicability note

Zet's current story render path is a **manual ChatGPT render queue**, not a direct `gpt-image-2` API call (`story_render_service.py:202-214` in the representative snapshot). Therefore:

- apply the **prompting and workflow principles** from the `gpt-image-2` guide;
- do **not** hardcode API-only parameters into `Final_Image_Prompt.md`;
- keep engine/model capabilities behind an engine profile so a later API renderer can use `quality`, size, transparency, or other API parameters without changing scene data;
- do not assume ChatGPT's internal orchestration and the public API are byte-for-byte the same implementation.

---

## 3. What Should Be Preserved From the Existing Architecture

The current system has several design decisions that remain good and should survive the modernization.

### 3.1 Deterministic compiler ownership

The job runners compile prompts from authored sections and metadata without AI finalization. Keep that principle.

This matters because a failed render should be traceable to:

- structured scene data;
- a source template;
- a compiler rule;
- a reference assignment;
- or the image model itself.

Do not insert a nondeterministic LLM “make this prompt better” pass between the IR and `Final_Image_Prompt.md`.

### 3.2 Provenance and source mapping

Keep artifacts such as:

- `Final_Image_Prompt.md`
- `Compiled_Sections.md`
- `Prompt_Source_Map.json`
- `Scene_Render_IR.json`
- `dependency_manifest.json`
- prompt/image review artifacts

These are useful for regression testing and are especially valuable while changing prompt behavior.

### 3.3 Pipeline stage separation

Keep distinct stages for:

- Body Reference
- Character Assembly
- Costume Dressing
- Scene Appearance
- Expression
- Story/Scene rendering
- Subscene/background rendering

The current image model is better at edits and multiple image inputs, which makes this staged architecture **more useful**, not less useful.

### 3.4 Human review

Keep the human review gate. Modern image generation is more capable but still probabilistic. The better modernization target is **fewer first-pass failures and more surgical corrections**, not elimination of review.

### 3.5 Existing costume-section compaction

`Run_Costume_Dressing_Jobs.py:186-302` already removes empty values, redundant view stubs, irrelevant anatomical-side instructions, and unnecessary equipment sections. Preserve this work and generalize its philosophy to all prompt pipelines.

---

## 4. Key Findings From the Representative Files

This section identifies concrete issues in the uploaded snapshot.

---

### Finding A — Scene elements are normalized to a maximum of one reference image

**File:** `story_service.py`  
**Representative lines:** 1291-1297

Current logic filters `reference_images` and then applies:

```python
][:1]
```

This was a reasonable simplification for an older workflow, but it conflicts with the current engine's useful multi-image behavior.

#### Why this matters

A scene element may legitimately need more than one reference:

- identity + costume;
- identity + expression;
- character + prop arrangement;
- front body source + head source;
- design source + style source;
- accepted group arrangement + individual identity correction.

The current model handles multiple images better when they are explicitly indexed and assigned roles.

#### Required change

Remove the one-reference truncation and replace it with validated typed reference inputs. Preserve deterministic ordering.

---

### Finding B — Custom per-reference `ignore` and `notes` are stored, but the final scene compiler does not honor them

**Files:**

- `scene_render_compiler.py:113-138` stores `roles`, `ignore`, and `notes` in the IR.
- `scene_render_compiler.py:724-757` calculates generic defaults by element/resource type.
- `scene_render_compiler.py:837-854` emits the reference assignment using those defaults.

The final prompt currently derives preserve/ignore behavior from `_reference_defaults()` and does not incorporate the custom `ignore` list or `notes` stored on the reference.

#### Why this matters

The current engine responds well to exact source-scoping instructions such as:

- use Image 2 only for the raven;
- preserve the raven's pendant but ignore its pose;
- preserve costume design but ignore body pose;
- preserve a group's internal arrangement but not its background;
- copy only an object's shape/material/relative scale.

If the scene data already stores this specificity, dropping it is a compiler loss.

#### Required change

The V2 compiler should use:

1. explicit per-reference preserve/change/ignore metadata when supplied;
2. role defaults only as fallback;
3. reference notes as scoped instructions;
4. a validator that reports conflicts between custom rules and role defaults.

---

### Finding C — High-value spatial and interaction fields are explicitly discarded during normalization

**File:** `story_service.py`  
**Representative lines:** 1333-1357

The current normalizer removes:

- `frame_coverage`
- `distance_from_camera`
- `visual_scale`
- `must_be_visible`
- `visible_body_requirements`
- `body_view`
- `head_view`
- `left_hand_detail`
- `right_hand_detail`
- `gaze_description`
- `temporary_condition`
- `left_arm_action`
- `right_arm_action`
- `leg_foot_detail`
- `balance_weight_detail`
- `occlusion`

`scene_render_compiler._compiled_placement()` removes additional pose fields.

#### Why this matters

These are almost exactly the details current OpenAI guidance recommends stating explicitly for people and object interactions.

Recent Zet corrections confirm their importance:

- Tsaeytte's tusk needed an explicit relative height.
- Morrow needed explicit expected occlusion of the near ear.
- Morrow needed a facing relationship independent of Tsaeytte's body placement.
- Falling poses needed explicit body tilt, leg/foot behavior, and garment response.
- Hands/held objects are frequent failure points.

The current design forces these facts into freeform `placement_notes` or pose summaries, where they are harder to validate and easier to contradict.

#### Required change

Restore these concepts as structured IR fields. Do not necessarily restore every legacy field unchanged; define a smaller V2 semantic model that captures the facts the renderer actually needs.

A proposed schema is in Section 7.

---

### Finding D — The final scene prompt tail is mandatory and unconditional

**Files:**

- `scene_prompt_sections.py:7-46`
- `final_image_prompt_tail_v1.md:1-44`
- `scene_render_compiler.py:1043-1047`

The loader requires exactly four non-empty sections in a fixed order:

1. Anatomical Requirements
2. Avoid
3. High-Risk Elements
4. Final Verification

The compiler then appends all of them.

The raw tail is about 213 words before any scene-specific content and includes generic rules such as:

- exactly five fingers;
- crossed legs;
- touching characters;
- long ears;
- hair consistency;
- modern objects;
- generic final verification.

#### Why this matters

Some of these rules are valuable in the relevant scene. The problem is that they are emitted even when irrelevant.

Examples:

- a pure location background does not need hand/finger rules;
- a scene with no seated character does not need crossed-leg warnings;
- a scene with no elves does not need ear rules;
- a close expression reference should not inherit full-body crop rules from some generalized tail;
- a scene whose main problem is a relative-size relation needs that relation emphasized more than generic anatomy boilerplate.

This consumes attention with low-value constraints and makes failures harder to debug.

#### Required change

Replace the monolithic tail with **risk-derived constraints**.

Examples:

- emit hand anatomy only when hands are visible or manipulate props;
- emit close-contact anatomy only when subjects touch/overlap;
- emit long-ear constraints only for a relevant referenced character;
- emit exact-text constraints only when dialogue/text exists;
- emit full-body/feet constraints only for full-body outputs;
- emit no-extra-subject constraints when count is important;
- emit mirrored-view constraints for technical turnaround/reference tasks;
- emit occlusion constraints only when intentional occlusion is specified.

Move “verification” primarily into compiler/image-review checks rather than asking the image generator to perform a generic checklist.

---

### Finding E — Reference assignment and Scene Element Preservation duplicate authority

**File:** `scene_render_compiler.py`  
**Representative lines:** 837-854 and 1011-1047

The prompt first says what each image reference preserves. Later it can emit large resolved identity and costume blocks for the same element.

This is visible in recent generated-scene prompt metadata: Tsaeytte can have a generic visual-reference preservation rule and later receive a long canonical identity paragraph and costume paragraph.

#### Why this matters

When a good visual reference is already attached, repeating the entire canonical identity prose often adds less value than a few identity anchors.

The current engine is capable of identity-sensitive editing and reference use. Text should focus on:

- what the image reference controls;
- any identity traits that are especially regression-prone;
- what changes for this scene.

#### Required change

Introduce two identity text modes:

**Reference-backed mode**
- image is primary authority;
- emit a short authored identity-anchor block only;
- emit full canonical prose only if explicitly requested.

**Text-only/fallback mode**
- emit the fuller descriptive identity/costume text.

Do not use an AI summarizer at compile time. Add compact authored sections to canonical character/costume templates, for example:

```text
<!-- ZET:BEGIN SCENE_CHARACTER_ANCHORS -->
- Petite young-adult high elf; 5'2"; graceful lightly athletic build.
- Soft heart-shaped face; large violet eyes.
- Thick black chin-length bob; long pointed ears.
<!-- ZET:END SCENE_CHARACTER_ANCHORS -->
```

The exact authoring format can follow existing template conventions.

---

### Finding F — Multiple locked render inputs can all be called “the authoritative backdrop”

**File:** `scene_render_compiler.py:824-833`

For every `render_input`, the compiler currently says:

- use this accepted image as the authoritative backdrop;
- preserve its canvas/framing/camera/etc.;
- add only remaining elements.

If there are multiple render inputs, the prompt can claim that multiple different images are simultaneously the full canvas authority.

Recent tactical-scene prompts did exactly this for both a Background and a Sub-Scene.

#### Why this matters

The current model can combine multiple images, but it needs clear roles. Two inputs cannot both unambiguously define the same entire pixel canvas unless they are identical.

#### Required change

Distinguish:

- **edit base / canvas authority** — exactly one image for an edit-stage render;
- **subscene/group reference** — contributes a group, arrangement, or design;
- **background design reference** — contributes location design but not pixel canvas;
- **overlay/composite source** — contributes a subject/group to the base;
- **style reference** — contributes style only.

Add validation:

```text
edit job: exactly one edit_base
generation job: zero edit_base
no two inputs may both claim full-canvas authority
```

If true pixel-level background preservation is required, treat that as an edit/compositing problem, not merely prompt prose. ChatGPT's own image editor documentation warns that selected edits may extend beyond the selected region, so “locked” should not imply mathematical pixel identity unless Zet also performs deterministic masking/compositing/diff protection.

---

### Finding G — Generic staging can contradict the story action

**File:** `scene_render_compiler.py:661-721`

The placement writer defaults most non-place subjects to a “stands” verb when the pose summary does not provide a better action.

Recent compiled prompt metadata for the falling-party scene contained:

> `Falling Party: Stands in the Backdrop background.`

while the story beat and group source explicitly described characters falling/airborne.

The image model often overcame this contradiction, but it should never have to.

#### Required change

Do not invent physical posture.

Use a neutral placement verb when an action is unknown:

```text
Falling Party occupies the background.
```

Better: compile `action_class` or explicit pose/action from the source group.

Validation should flag contradictions such as:

- story/action says `falling`, staging says `standing`;
- motion says `moving`, generated placement prose says stationary;
- character is assigned a held prop but no hand/contact relation exists;
- a gaze target is behind a character while head-view is hard-locked away and no over-shoulder allowance exists.

---

### Finding H — Low-quality semantic fragments leak into final prompts

Recent generated prompt metadata contains examples such as:

- `gripping the rope, gripping the rope`
- `holding scimitar, none`
- motion cue ending in `none`
- a malformed Morrow override fragment: `ion descent`

The current compiler's sentence cleanup normalizes whitespace/punctuation, but semantic cleanup is too shallow.

#### Required change

Add a final deterministic semantic-lint/cleanup pass before writing `Final_Image_Prompt.md`.

Minimum rules:

- suppress semantic null values: `none`, `n/a`, `not applicable`, empty;
- collapse repeated adjacent phrases;
- collapse repeated equivalent bullet clauses;
- reject unresolved placeholders;
- reject malformed fragments below a configurable minimum meaningful-content threshold when sourced from an override;
- reject duplicate section headings;
- ensure each sentence has a subject when emitted from generated staging logic;
- log every suppression/correction in `Prompt_Source_Map.json` or a new `Prompt_Compile_Diagnostics.json`.

Do not silently rewrite arbitrary user prose. Restrict cleanup to compiler-generated fields and known null/duplication patterns.

---

### Finding I — `costume_dressing_v1.md` repeats the same invariant contract too many times

The representative raw template is about 451 words before dynamic costume sections. It repeats essentially the same rules in:

- opening task;
- Locked Source;
- Costume Replacement Rule;
- Orientation Lock;
- Pose and Camera Lock;
- Identity Preservation;
- Final Constraints.

This is much more repetition than the current OpenAI virtual try-on guidance uses.

Importantly, `Run_Costume_Dressing_Jobs.py` already performs useful section compaction. The modernization should build on that rather than discard it.

#### Required change

Reduce the template to approximately these concepts:

1. task;
2. source role;
3. allowed changes;
4. invariants;
5. costume specification;
6. fit/draping/occlusion integration;
7. output constraints.

For example:

```markdown
# Task
Edit Image 1, the locked Character-Assembly source, into the finished
{{COSTUME_NAME}} costume reference.

# Change
Replace only the fitment clothing and the costume-controlled jewelry,
equipment, and footwear with the specified costume.

# Keep unchanged
Keep the character's identity, face, hair, ears, age, body shape, pose,
body/head orientation, camera, framing, lighting, and background unchanged.
Do not mirror the image.

# Costume
{{COSTUME_DESCRIPTION_FACTS}}
{{VIEW_SPECIFIC_COSTUME}}

Fit the costume naturally to the existing body and pose. Preserve believable
fabric drape, folds, occlusion, equipment attachment, and footwear contact.

# Output
One full-body technical reference in the supplied view; no extra subjects,
props, text, or scene redesign.
```

The exact wording should be tuned by A/B rendering, but the structure should remain this compact.

---

### Finding J — `expression_v1.md` is especially over-specified

The representative raw expression template is about 661 words before injected identity/expression sections. It repeats framing/identity constraints across:

- Primary Objective
- Identity Key Framing Authority
- Framing
- Identity Preservation
- Good Output
- Bad Output
- Negative Constraints
- Final Output Summary

#### Required change

Expression editing is an ideal V2 surgical-edit task:

```markdown
# Task
Edit Image 1, the Identity Key, to show: {{EXPRESSION_DEFINITION}}.

# Change
Change only the facial expression and the minimum natural facial/head/neck
tension required to support it.

# Keep unchanged
Keep identity, apparent age, species, face structure, eye color, hairstyle,
ear shape/visibility, costume, body extent, camera, crop, lighting, and
rendering style unchanged.

# Output
Match Image 1's framing. One clean reusable expression reference. No text,
sheet, collage, new props, or narrative scene.
```

Add only expression-specific identity details that have a demonstrated regression risk.

---

### Finding K — `scene_appearance_v1.md` is already close to the current best pattern

The Scene Appearance template is only about 150 raw words and has a good structure:

- task;
- reference assignment;
- required arrangement;
- preservation rules;
- final constraints.

Recent Scene Appearance results were among the most instructive because targeted additions produced clear improvements.

#### Keep this template conceptually intact.

Improve the **data feeding `ARRANGEMENT_INSTRUCTIONS`**, not the amount of generic boilerplate around it.

---

## 5. Findings From Recent Generated Images and Corrections

The recent image results support a shift toward structured relational facts.

### 5.1 Tusk relative scale

An initial direct-front Tsaeytte/Morrow/tusk result rendered the tusk substantially shorter than intended. A revised prompt explicitly stated that the tusk is **4 inches taller than Tsaeytte**, and the revised image rendered the tusk extending above her head.

#### Lesson

Do not rely on a prop reference alone to communicate relative scale.

Store both:

```json
{
  "subject": "utility_tusk",
  "relation": "height_relative_to",
  "target": "Tsaeytte",
  "delta": "4 inches",
  "visual_rule": "with the pointed tip on the ground, the broken base ends about 4 inches above the top of Tsaeytte's head"
}
```

The `visual_rule` is often more useful to the renderer than the raw measurement alone.

---

### 5.2 Morrow's pendant

The revised direct-front request explicitly called out Morrow's orange feather pendant, and the final result made it legible.

#### Lesson

Small signature features on supporting subjects should be part of that image input's scoped preserve list or compact anchor block.

---

### 5.3 Expected occlusion

In a front-left three-quarter Scene Appearance image, simply placing Morrow on Tsaeytte's anatomical left shoulder did not guarantee the desired visual overlap. The corrective instruction explicitly stated that Morrow would occlude Tsaeytte's near ear, producing the intended relationship more reliably.

#### Lesson

Occlusion is not a side effect. It is scene geometry and should be structured.

Proposed:

```json
{
  "occluder": "Morrow",
  "occluded": "Tsaeytte",
  "target_part": "near ear",
  "amount": "partial-to-major",
  "required": true
}
```

For eight-view reference work, derive `near anatomical side` / `far anatomical side` from the view table rather than making the renderer infer it.

---

### 5.4 Supporting-subject facing

In the back-right three-quarter Scene Appearance result, Morrow initially oriented his head more toward the camera than Tsaeytte. The correction was:

> Have Morrow face in the same direction as Tsaeytte, away from the camera.

#### Lesson

A supporting subject's orientation is independent of:

- placement;
- parent character orientation;
- gaze;
- reference-image pose.

Store it explicitly:

```json
{
  "subject": "Morrow",
  "facing": {
    "mode": "same_as",
    "target": "Tsaeytte",
    "camera_relation": "away"
  }
}
```

---

### 5.5 Falling-party scenes

The recent falling scenes show that the current engine can handle:

- several distinct characters;
- a dramatic vertical environment;
- recognizable character designs;
- Tsaeytte cradling Morrow;
- complex airborne silhouettes.

However, follow-up refinements focused on **action geometry**: Tsaeytte needed to read more clearly as falling face-up, with lower legs/feet and clothing responding to descent.

#### Lesson

For dynamic poses, identity prose is not the primary bottleneck. Encode:

- body tilt;
- torso orientation to camera/gravity;
- leg/foot state;
- center-of-mass/balance cues;
- garment/hair response to motion;
- screen movement direction.

These should not be stripped by normalization.

---

### 5.6 Rope-line / sandstorm scenes

The final rope-line images are visually coherent and the later blue-magic revision is a good example of a focused targeted edit.

The associated compiled prompt, however, contained duplicate and null-like phrases.

#### Lesson

The model can succeed despite compiler noise, but that is not a reason to keep the noise. The V2 compiler should make every emitted clause earn its place.

The blue-magic follow-up is a model for the proposed **revision-stage prompt**: preserve the accepted scene and change only the magical treatment of the rope.

---

### 5.7 Dialogue

Recent scenes rendered short dialogue such as `Hey!` clearly, and the tactical discussion scene produced readable dialogue panels.

#### Lesson

Do not carry old assumptions that in-image text is categorically unusable.

Keep exact dialogue as:

```text
Tsaeytte says exactly: "..."
```

For unusual names or highly important short labels, support an optional `spell_out` form. Text constraints should be conditional: a no-text rule must never coexist with dialogue.

---

## 6. New General Prompting Architecture

V2 prompts should be compiled from three contracts.

### Contract 1 — Image Input Contract

Answers:

- What images are attached?
- Which one is the edit base?
- What does each image control?
- What must be copied/preserved?
- What must be ignored?
- What may change?

### Contract 2 — Scene/Edit Contract

Answers:

- What is the requested output?
- What is happening?
- Where is each subject?
- What are the key body/view/gaze/hand/contact/scale/occlusion relationships?
- What text must appear?
- What visual style/environment is required?

### Contract 3 — Risk Contract

Contains only constraints relevant to the actual render:

- hands;
- held props;
- intentional occlusion;
- close contact;
- exact count;
- exact text;
- turnaround orientation;
- transparency;
- unusual anatomy;
- full-body framing;
- locked edit base.

This ordering should replace the current pattern of repeating preservation rules in several unrelated sections.

---

## 7. Proposed Scene Render IR V5 Extensions

Prefer a backward-compatible migration from V4 rather than replacing the entire schema at once.

### 7.1 `image_inputs`

Replace ambiguous `references`/`render_inputs` prompt behavior with a normalized input layer.

```json
{
  "image_inputs": [
    {
      "id": "input_character_base",
      "tag": "{{ASSET:...}}",
      "input_role": "edit_base",
      "applies_to_element_ids": ["Tsaeytte"],
      "priority": 100,
      "preserve": [
        "identity",
        "face",
        "hair",
        "ears",
        "body proportions",
        "costume",
        "body orientation",
        "head orientation",
        "camera",
        "framing",
        "lighting",
        "background"
      ],
      "ignore": [],
      "allow_changes": [
        "right arm",
        "right hand",
        "contact with utility tusk",
        "natural shoulder contact with Morrow"
      ],
      "notes": ""
    },
    {
      "id": "input_morrow",
      "tag": "{{AUX:person:morrow:morrow-raven-form}}",
      "input_role": "subject_reference",
      "applies_to_element_ids": ["Morrow"],
      "priority": 50,
      "preserve": ["species appearance", "plumage", "orange feather pendant"],
      "ignore": ["pose", "camera", "background", "lighting"],
      "allow_changes": ["orientation", "perching pose"],
      "notes": ""
    }
  ]
}
```

### 7.2 Supported input roles

At minimum:

- `edit_base`
- `identity_reference`
- `subject_reference`
- `costume_reference`
- `prop_reference`
- `location_reference`
- `style_reference`
- `layout_reference`
- `group_reference`
- `background_design_reference`

Do not use `authoritative backdrop` as a generic synonym for every dependency.

### 7.3 Input ordering

Compile deterministic image numbering.

Example:

```markdown
# Image Inputs
- Image 1 — edit base: Tsaeytte's locked Costume-Dressing image.
- Image 2 — Morrow reference: use only for Morrow's appearance and pendant.
- Image 3 — Utility Tusk reference: use only for tusk shape, material, and design.
```

The manual render manifest must preserve this same order when attaching images.

Add a validation error if prompt numbering and manifest ordering differ.

---

### 7.4 `edit_contract`

```json
{
  "edit_contract": {
    "base_input_id": "input_character_base",
    "mode": "surgical_edit",
    "allowed_changes": [
      "Tsaeytte right arm and hand",
      "add Morrow",
      "add utility tusk"
    ],
    "invariants": [
      "character identity",
      "body proportions",
      "costume",
      "body/head view",
      "camera",
      "framing",
      "lighting",
      "neutral background"
    ]
  }
}
```

For a fresh full-scene generation, `edit_contract` can be absent.

---

### 7.5 Placement V2

Suggested shape:

```json
{
  "placement": {
    "scene_element_id": "Tsaeytte",
    "depth": "foreground",
    "screen_region": "left",
    "frame_requirement": "full_body",
    "visibility": {
      "feet_visible": true,
      "must_be_visible": ["face", "right hand"]
    },
    "body": {
      "view": "FRONT_LEFT_3_4",
      "facing": "Rin",
      "tilt": "",
      "posture": "standing"
    },
    "head": {
      "view": "FRONT_LEFT_3_4",
      "facing": "Rin",
      "gaze_target_element_id": "Rin"
    },
    "hands": {
      "left": {"action": "gesturing", "holds": null},
      "right": {"action": "holding", "holds": "Utility_Tusk"}
    },
    "motion": {
      "state": "stationary",
      "screen_direction": "",
      "physical_cue": ""
    }
  }
}
```

For falling:

```json
{
  "body": {
    "posture": "airborne",
    "tilt": "face-up, torso tipped backward"
  },
  "legs": {
    "detail": "knees and feet float naturally rather than forming a standing stance"
  },
  "motion": {
    "state": "moving",
    "screen_direction": "down",
    "physical_cue": "hair and overskirt lift upward relative to descent"
  }
}
```

---

### 7.6 Relationship constraints

Add a generic relationship model rather than encoding everything in prose.

```json
{
  "relationships": [
    {
      "type": "contact",
      "subject": "Morrow",
      "subject_part": "feet",
      "target": "Tsaeytte",
      "target_part": "anatomical left shoulder"
    },
    {
      "type": "occlusion",
      "subject": "Morrow",
      "target": "Tsaeytte",
      "target_part": "near ear",
      "required": true
    },
    {
      "type": "relative_scale",
      "subject": "Utility_Tusk",
      "target": "Tsaeytte",
      "rule": "4 inches taller"
    },
    {
      "type": "orientation",
      "subject": "Morrow",
      "target": "Tsaeytte",
      "rule": "face same direction"
    }
  ]
}
```

The compiler can convert these to concise English.

---

## 8. View and Coordinate Semantics

The current Spatial Coordinate Contract is worth keeping, but it should be backed by structured data rather than compensating for missing fields.

### 8.1 Keep distinct concepts

Never collapse:

- screen-left / screen-right;
- anatomical left / anatomical right;
- near side / far side;
- body facing;
- visible body view;
- head facing;
- head view;
- gaze;
- motion direction.

### 8.2 Add deterministic near/far mapping for the eight canonical views

Use the existing view configuration as the source of truth.

For each view define:

```json
{
  "FRONT_LEFT_3_4": {
    "near_anatomical_side": "left",
    "far_anatomical_side": "right"
  },
  "BACK_RIGHT_3_4": {
    "near_anatomical_side": "right",
    "far_anatomical_side": "left"
  }
}
```

Validate this against existing orientation rules before adoption.

This enables the compiler to say:

```text
Morrow is on Tsaeytte's anatomical left shoulder. In this view that is the
near shoulder, and Morrow partially occludes the near ear.
```

when required.

Do not have the image model infer whether an anatomical side is near or far if Zet can determine it.

---

## 9. Conditional Risk-Constraint Compiler

Replace `final_image_prompt_tail_v1.md` with a registry of small constraint fragments.

Possible file:

```text
Prompt_Templates/render_constraint_fragments_v2.json
```

Example:

```json
{
  "full_body": [
    "Keep the complete body visible from head through both feet."
  ],
  "visible_hands": [
    "Visible hands must have natural finger count, attachment, and grip."
  ],
  "held_object": [
    "Keep the named object in the specified anatomical hand with a believable grip and contact."
  ],
  "close_contact": [
    "Keep contacting bodies anatomically separate; do not merge limbs or silhouettes."
  ],
  "intentional_occlusion": [
    "Preserve the specified occlusion; do not reveal anatomy that should be hidden."
  ],
  "exact_character_count": [
    "Render exactly the listed subjects; do not duplicate or add characters."
  ],
  "turnaround_orientation": [
    "Do not mirror the image or rotate the body/head away from the requested technical view."
  ],
  "exact_dialogue": [
    "Render quoted dialogue exactly once and do not add other text."
  ]
}
```

### Risk detection examples

```python
if output_contract.full_body:
    risks.add("full_body")

if any(hand_is_visible_or_used(p) for p in placements):
    risks.add("visible_hands")

if relationships_of_type("held_by"):
    risks.add("held_object")

if relationships_of_type("occlusion"):
    risks.add("intentional_occlusion")

if render_kind in {"body_reference", "character_assembly", "costume_dressing", "scene_appearance"}:
    risks.add("turnaround_orientation")

if dialogue:
    risks.add("exact_dialogue")
```

The generated tail should normally be a few bullets, not four generic sections.

---

## 10. Task-Specific V2 Strategies

### 10.1 Body Reference

**Mode:** text-to-image generation  
**Keep:** deterministic body specification, requested view, full-body framing, neutral stance, fitment layer, mannequin-head requirement.

Current `body_reference_v1.md` is fairly reasonable. Modernize mainly by:

- moving the positive target description before exclusions;
- removing repeated negative variations that are already implied by the technical task;
- retaining explicit full-body / feet-visible wording;
- retaining exact view language;
- retaining race-specific body/head constraints where they materially matter;
- keeping neutral background;
- making anatomy risk fragments conditional rather than global.

Do not turn Body Reference into an edit pipeline.

---

### 10.2 Character Assembly

**Mode:** multi-image edit/composite

Current conceptual instruction—“put this head on this body”—is good.

Add explicit image roles:

```markdown
# Image Inputs
- Image 1 — Body Reference: defines body, pose, stance, body view, camera, framing, and background.
- Image 2 — Character Head: defines face identity, apparent age, hair, ears, head view, gaze, and local head rendering.

# Task
Edit Image 1 by replacing its mannequin head with the character head from Image 2.

# Change
Change only the head/neck integration area needed for a natural anatomical join.

# Keep
Keep Image 1's body, pose, stance, proportions, camera, framing, and background.
Keep Image 2's face, age, hair, ears, head orientation, and gaze.

# Output
One seamless full-body character reference with a natural head/neck/shoulder transition.
```

If the renderer supports a region selection/mask in the future, this stage is an ideal candidate.

---

### 10.3 Costume Dressing

**Mode:** single-base edit plus optional clothing/prop references

This is directly analogous to OpenAI's current virtual try-on guidance.

Use one compact invariant block:

- identity;
- face/hair/ears/age;
- body shape;
- pose;
- orientation;
- camera/framing;
- background/lighting.

Allow only costume-controlled changes.

Add positive integration requirements:

- garment conforms to existing body;
- believable drape/folds;
- correct occlusion;
- equipment attaches naturally;
- footwear maintains expected ground contact.

Avoid repeating the same lock in five sections.

Keep the useful existing normalization logic from `Run_Costume_Dressing_Jobs.py`.

---

### 10.4 Scene Appearance

**Mode:** surgical edit of a locked Costume-Dressing image with supporting references

This pipeline is already the closest to the target design.

Keep its concise structure and add structured arrangement facts.

For the Tsaeytte/Morrow/tusk example, the compiled prompt should look approximately like:

```markdown
# Task
Create one full-body Scene Appearance reference of Tsaeytte in FRONT-LEFT THREE-QUARTER view.

# Image Inputs
- Image 1 — edit base: locked Tsaeytte Costume-Dressing image for this exact view.
- Image 2 — Morrow reference: use only for Morrow's raven appearance and orange feather pendant.
- Image 3 — Utility Tusk reference: use only for tusk design, material, and shape.

# Change
Add exactly one Morrow perched on Tsaeytte's anatomical left shoulder.
Add exactly one utility tusk held vertically in Tsaeytte's anatomical right hand.
Move only the right arm/hand as needed for the grip.

# Geometry
- The tusk's pointed end touches the ground; broken jagged base points upward.
- The tusk ends about 4 inches above the top of Tsaeytte's head.
- Morrow is on the near shoulder in this view and partially occludes Tsaeytte's near ear.
- Morrow faces the same direction as Tsaeytte.

# Keep unchanged
Keep Image 1's identity, costume, proportions, stance, body/head view, camera,
framing, lighting, and neutral background unchanged.

# Output
One coherent technical reference; no duplicate subjects, extra props, scenery, text, or layout sheet.
```

This says materially more than the current template about the relationships while remaining compact.

---

### 10.5 Expression

**Mode:** surgical edit of Identity Key

Use the compact pattern described in Finding J.

Do not repeat framing in three sections and again in Good/Bad Output.

If expression-specific constraints need detail, keep them under the **Change** section. Keep identity invariants under **Keep unchanged**.

---

### 10.6 Full Story Scene

**Mode:** generation or edit/composite, depending on whether a locked base exists

Recommended order:

```markdown
# Task / Story Beat

# Image Inputs
(indexed roles)

# Canvas and Composition
(framing, focal point, depth-lane order)

# Staging
(only scene-specific placement/action facts)

# Relationships
(gaze, contact, held objects, occlusion, relative scale)

# Motion
(only moving subjects)

# Dialogue
(exact text and panel placement)

# Environment / Style

# Character Anchors
(compact reference-backed anchors; full descriptions only for text-only elements)

# Critical Constraints
(risk-derived only)
```

Keep the current screen-coordinate contract if the scene uses detailed placement.

---

## 11. Identity Text Strategy

### 11.1 Add compact canonical anchors

For characters and costumes, create dedicated compact prompt sections rather than trying to shorten full canonical prose dynamically.

Suggested canonical sections:

```text
SCENE_CHARACTER_ANCHORS
SCENE_COSTUME_ANCHORS
SCENE_PROP_ANCHORS
SCENE_LOCATION_ANCHORS
```

These should contain only features needed to detect/prevent drift.

### 11.2 Prompt selection

```python
if element.has_high_quality_visual_reference:
    emit(compact_anchors)
elif element.has_text_only_source:
    emit(full_identity_description)
```

A strong image reference plus 3–5 anchors is usually preferable to a strong image reference plus a large paragraph of personality/aesthetic prose.

### 11.3 Keep full prose available for provenance

Do not delete the full identity/costume sections from character files. They remain useful for:

- text-only generation;
- reference creation;
- review;
- source maps;
- fallback when a visual reference is incomplete.

The change is **selection**, not data loss.

---

## 12. Revision / Correction Workflow

This is one of the largest opportunities created by the current engine.

Recent corrections were naturally small:

- make tusk 4 inches taller;
- add/restore pendant;
- make Morrow occlude the near ear;
- make Morrow face the same direction;
- tip Tsaeytte farther back while falling;
- make the rope visibly affected by blue magic.

Do not necessarily rerun the entire original generation prompt for these.

### 12.1 Add a structured correction patch

Example:

```json
{
  "parent_candidate": "candidate_003.png",
  "changes": [
    {
      "subject": "Morrow",
      "property": "facing",
      "value": "same direction as Tsaeytte, away from camera"
    }
  ],
  "preserve": [
    "all other subjects",
    "character identity",
    "costumes",
    "composition",
    "background",
    "camera",
    "lighting"
  ]
}
```

Compile to:

```markdown
Edit Image 1, the previous candidate.

Change only Morrow's orientation: have Morrow face the same direction as
Tsaeytte, away from the camera.

Keep everything else unchanged, including Tsaeytte, the tusk, costume,
composition, camera, lighting, framing, and background.
```

### 12.2 Artifact names

Suggested:

- `Render_Correction.json`
- `Revision_Image_Prompt.md`
- `Revision_Source_Map.json`
- `parent_candidate_id` in manifest

### 12.3 When not to use revision mode

Regenerate from the full scene when:

- the composition is fundamentally wrong;
- character count is wrong in several places;
- the wrong base/reference was used;
- the requested camera/view changes;
- the correction would alter most of the image.

---

## 13. Compiler Validation and Prompt Linting

Move more “verification” into deterministic code.

### 13.1 Reference validation

Errors:

- edit job has zero or more than one `edit_base`;
- prompt image index does not match attachment order;
- a reference role is unknown;
- a reference has contradictory preserve and allow-change entries;
- reference tag is unresolved;
- expected supporting subject has no visual/text source.

Warnings:

- more than a small number of active image inputs;
- style reference also claims geometry authority;
- group reference and individual reference disagree on assigned scope.

### 13.2 Placement validation

Errors or high-severity warnings:

- same prop assigned to two hands/characters without an explicit shared-hold relationship;
- required held prop has no holding hand;
- intentional occlusion targets an element that is required fully visible;
- relative-scale target missing;
- dialogue speaker missing;
- body/head view missing on technical reference stages;
- mirroring requested accidentally by conflicting view mappings.

### 13.3 Semantic prompt lint

Before write:

- no unresolved `{{PLACEHOLDER}}`;
- no literal semantic `none` / `n/a`;
- no duplicated phrase like `gripping the rope, gripping the rope`;
- no duplicate character-reference blocks;
- no repeated identical constraint bullets;
- no multiple `authoritative backdrop` claims;
- no full-body constraint in a non-full-body output;
- no no-text constraint if dialogue/text exists;
- no “stands” generated for explicit airborne/falling/swimming/lying action;
- no missing Image N mapping for any attached input.

Write diagnostics to a machine-readable artifact.

---

## 14. File-by-File Implementation Plan

The exact repository contains additional helpers not included in this review. CODEX should trace the shared helpers before editing because some behavior may be centralized elsewhere.

### 14.1 `story_service.py`

**Change:**

1. remove `reference_images[:1]`;
2. normalize all references into stable ordered typed records;
3. stop discarding V2 spatial fields;
4. migrate legacy fields into V2 structures;
5. preserve occlusion/visibility/scale/hand data;
6. add semantic validation;
7. keep V4 read compatibility during migration.

**Specific representative code to replace:**

- `_normalized_scene_elements()` reference truncation around 1291-1297;
- `_normalized_placements()` field removals around 1333-1357.

### 14.2 `scene_render_compiler.py`

**Change:**

1. add V2 input-role compiler;
2. honor custom reference preserve/ignore/notes;
3. explicitly number images;
4. compile `edit_contract`;
5. compile relationship facts;
6. replace generic “stands” with action-aware/neutral wording;
7. separate compact reference-backed anchors from full text fallback;
8. use risk-derived constraints instead of appending every tail section;
9. add deterministic dedup/null cleanup;
10. generate diagnostics;
11. preserve existing spatial depth/read-order logic that is working.

**Important:** `_reference_defaults()` should become fallback defaults, not override explicit reference metadata.

### 14.3 `scene_prompt_sections.py`

Deprecate the requirement that all four global tail sections must always exist and be non-empty.

Replace with a loader for versioned constraint fragments, or allow optional sections driven by detected risks.

Keep V1 loader for compatibility while dual-writing prompts.

### 14.4 `final_image_prompt_tail_v1.md`

Do not modify in place initially.

Create a V2 fragment registry and keep V1 for regression comparison.

Eventually retire the monolithic tail after V2 acceptance.

### 14.5 `story_render_service.py`

Add to the render manifest:

```json
{
  "prompt_schema_version": 2,
  "engine_profile": "chatgpt_images_2_0_v1",
  "image_input_order": [
    {"index": 1, "input_id": "...", "role": "edit_base"},
    {"index": 2, "input_id": "...", "role": "subject_reference"}
  ],
  "render_mode": "generate|edit|revision"
}
```

Preserve current manual ChatGPT queue behavior.

During migration, optionally write:

- `Final_Image_Prompt_V1.md`
- `Final_Image_Prompt_V2.md`

and allow the selected engine profile to choose one.

### 14.6 `Run_Body_Reference_Jobs.py`

Keep current deterministic compilation and review architecture.

Add:

- prompt schema/version to manifest;
- V2 technical-output contract;
- risk-derived constraint fragments;
- prompt lint.

Do not add image inputs unless the task itself changes.

### 14.7 `Run_Character_Assembly_Jobs.py`

The dependency manifest already knows the roles `body_reference` and `head_image`. Ensure that those roles are carried all the way into:

- deterministic attachment ordering;
- prompt image numbering;
- edit/change scope.

Do not let the final prompt call them ambiguously “this head” and “this body” if the actual render interface is receiving multiple images.

### 14.8 `Run_Costume_Dressing_Jobs.py`

Keep `normalize_costume_dressing_sections()`.

Refactor the surrounding V1 template repetition into one compact invariant contract.

If costume image references are added later, support them as `costume_reference` inputs rather than stuffing more prose into the costume description.

### 14.9 `scene_appearance_v1.md`

Create `scene_appearance_v2.md` rather than rewriting V1.

Add sections/fields for:

- source indexing;
- allowed edit scope;
- relative scale;
- expected occlusion;
- supporting-subject facing;
- contact points;
- held-hand assignment.

Keep the general V1 brevity.

### 14.10 `body_reference_v1.md`

Create a V2 only after A/B testing. It is not the highest priority.

Priority is to fix the scene/reference semantics first.

### 14.11 `character_assembly_v1.md`

Create V2 with explicit Image 1 / Image 2 roles and one edit-scope section.

### 14.12 `costume_dressing_v1.md`

High-priority V2 rewrite because repetition is substantial and the current engine's try-on/edit pattern maps directly to the task.

### 14.13 `expression_v1.md`

High-priority V2 rewrite because it is the most repetitive representative template.

---

## 15. Shared Helpers CODEX Must Inspect

The uploaded files are representative, not complete. Before implementing, trace at least:

- `render_static_prompt_artifacts`
- `select_prompt_sections`
- `reference_files_for_job`
- `reference_files_payload`
- `pipeline_compiler_support`
- `scene_prompt_cleanup`
- view configuration (`Prompt_View_Text.json`)
- the code that physically attaches reference files to the manual ChatGPT render request
- scene render target projection and dependency ordering
- any image catalog/reference-set resolver

The most important question is:

> **Does the order in `reference_files` exactly determine the image order seen by ChatGPT?**

If not, add a deterministic ordering layer. Prompt numbering is only useful if attachment numbering is stable.

---

## 16. Engine Profile

Avoid baking 2026 behavior into every compiler function.

Suggested config:

```json
{
  "id": "chatgpt_images_2_0_v1",
  "supports_multi_image": true,
  "supports_image_edit": true,
  "supports_exact_text": true,
  "supports_revision_edit": true,
  "prompt_style": "structured_compact",
  "number_image_inputs": true,
  "conditional_risk_constraints": true,
  "reference_backed_identity_mode": "compact_anchors",
  "default_render_mode_for_locked_source": "edit"
}
```

Future API-specific profiles can add:

```json
{
  "api_model": "gpt-image-2",
  "quality": "high",
  "size": "...",
  "background": "opaque"
}
```

Do not put those API parameters into the manual prompt unless they are semantically meaningful to ChatGPT.

---

## 17. Regression Test Suite Based on Real Zet Cases

Create a small, stable render-evaluation pack.

### Fixture 1 — Tsaeytte direct front + Morrow + tusk

Assert:

- exactly one Tsaeytte;
- exactly one Morrow;
- exactly one tusk;
- Morrow on anatomical left shoulder;
- tusk held in anatomical right hand;
- tusk point on ground;
- broken base up;
- tusk top about 4 inches above Tsaeytte's head;
- orange feather pendant visible;
- full-body technical framing;
- no extra props/scenery.

### Fixture 2 — Front-left three-quarter shoulder occlusion

Assert:

- correct body/head view;
- Morrow on near anatomical-left shoulder;
- Morrow partially occludes near ear;
- no invented extra ear;
- tusk relation preserved.

### Fixture 3 — Back-right three-quarter supporting orientation

Assert:

- Tsaeytte faces away in requested view;
- Morrow faces same general direction;
- Morrow does not turn toward camera unless explicitly asked.

### Fixture 4 — Tactical discussion

Assert:

- foreground Tsaeytte then Rin;
- midground Freydis, Snarlspark, Poets in requested order;
- Tsaeytte and Rin look at each other;
- specified gestures;
- dialogue exact and readable;
- no duplicate characters;
- locked-base/reference roles are unambiguous.

### Fixture 5 — Falling party

Assert:

- all group members read airborne/falling;
- no prompt sentence says they “stand”;
- Tsaeytte reads face-up/tipped back;
- legs/feet do not form a ground-standing pose;
- clothing responds to descent;
- Morrow is securely cradled.

### Fixture 6 — Sandstorm rope line

Static prompt asserts:

- no duplicated `gripping the rope`;
- no literal `none`;
- no malformed fragments;
- each character/group has one coherent staging line.

Visual asserts:

- rope visibly connects the group;
- Tsaeytte is foreground;
- devil is background;
- requested spell effect follows the rope when enabled.

### Fixture 7 — Locked background / subscene composition

Test both semantics:

**Semantic reference mode**
- background design remains recognizable.

**Edit-base mode**
- one input is explicitly the base canvas;
- only specified additions change;
- no second input claims full-canvas authority.

If pixel identity is required, add an automated image-diff or mask/compositing test rather than trusting prompt wording.

### Fixture 8 — Costume Dressing

Assert:

- body/head orientation unchanged;
- identity unchanged;
- only costume-controlled areas change;
- fitment clothing fully removed;
- costume drapes naturally;
- no duplicated lock boilerplate in prompt.

### Fixture 9 — Expression

Assert:

- framing matches Identity Key;
- identity/costume/camera remain stable;
- only expression changes;
- prompt contains one invariant block rather than Good/Bad/Negative repetition.

---

## 18. Prompt-Level Automated Metrics

Track these before and after V2.

Do not set a hard token target initially. Use quality metrics.

### Required metrics

- total prompt words;
- number of repeated sentences;
- number of repeated semantic clauses;
- unresolved placeholders;
- semantic-null leakage (`none`, `n/a`);
- reference input count;
- prompt-index ↔ manifest-index match;
- number of generic risk constraints emitted;
- number of scene-specific relationship constraints emitted;
- number of identity words per reference-backed subject;
- count of contradictory action/posture terms;
- count of full-canvas authority inputs.

### Expected direction

- substantially fewer repeated constraints;
- more explicit relationship facts;
- zero null/duplicate leakage;
- zero lost reference metadata;
- zero discarded required spatial fields;
- easier prompt diffing between revisions.

Do not optimize for the shortest prompt if it removes a critical relational instruction.

---

## 19. Visual Evaluation Metrics

For A/B testing, use a simple rubric rather than “looks better.”

Score each render:

| Category | Pass condition |
|---|---|
| Identity | Referenced character remains recognizably the same |
| Count | Correct number of characters/props |
| Placement | Correct screen region and depth |
| Orientation | Correct body/head view; no mirror |
| Gaze | Correct target/direction |
| Hand/prop | Correct anatomical hand and believable grip |
| Relative scale | Key relative-size rule is satisfied |
| Occlusion | Required overlap is present |
| Action | Pose/motion reads correctly |
| Costume | Correct design and no unintended drift |
| Text | Exact dialogue/label when required |
| Background | Correct preservation mode |
| Extras | No unrequested subjects/props/text |

Track:

- first-pass acceptance rate;
- average correction turns;
- high-severity failure rate;
- identity drift rate;
- layout/relationship failure rate.

The primary success criterion should be **fewer correction turns for the same visual fidelity**.

---

## 20. Migration Plan

### Phase 0 — Baseline

1. Snapshot current V1 prompts for representative jobs.
2. Save current accepted/candidate images.
3. Record prompt word/repetition metrics.
4. Create the regression fixture list above.
5. Add tests for current source-map/manifest stability.

No prompt output changes yet.

### Phase 1 — IR preservation fixes

1. Remove one-reference truncation.
2. Preserve high-value spatial fields.
3. Add typed reference normalization.
4. Add relationship structures.
5. Add backward-compatible migration from V4 fields.

Still emit V1 prompts if necessary.

### Phase 2 — Compiler correctness fixes

1. Honor custom reference `ignore`/`notes`.
2. Add stable Image N ordering.
3. Fix generic `stands` behavior.
4. Suppress semantic `none`.
5. Deduplicate compiler-generated fragments.
6. Add prompt diagnostics.
7. Add reference/placement semantic validation.

These fixes should improve even V1 output.

### Phase 3 — V2 constraint system

1. Add risk-fragment registry.
2. Add conditional risk detection.
3. Stop unconditional V1-tail append in V2.
4. Add compact identity-anchor selection.
5. Add explicit edit contract.

Dual-write V1 and V2 prompts.

### Phase 4 — Task templates V2

Priority order:

1. `scene_appearance_v2.md`
2. `costume_dressing_v2.md`
3. `expression_v2.md`
4. `character_assembly_v2.md`
5. full scene V2
6. `body_reference_v2.md` last

Reason: Scene Appearance has the best observed corrective examples; Costume/Expression have the most obvious repetition; Body Reference is comparatively stable.

### Phase 5 — Revision jobs

1. Add `Render_Correction.json`.
2. Compile `Revision_Image_Prompt.md`.
3. Use previous candidate as edit base.
4. Preserve provenance.
5. Add acceptance/reject path back to full generation.

### Phase 6 — A/B evaluation

For each regression fixture:

- render V1;
- render V2;
- use same current ChatGPT Images setting where possible;
- grade with the rubric;
- record correction turns.

Do not default V2 based only on prompt aesthetics.

### Phase 7 — Default V2

After the regression suite is acceptable:

- make V2 default for ChatGPT manual renders;
- preserve a V1 compatibility flag;
- keep old templates for reproducibility;
- document migration in repository notes.

---

## 21. Suggested CODEX Commit Sequence

### Commit 1 — Regression harness

- add prompt snapshot tests;
- add static lint tests;
- add fixture metadata for recent failure cases;
- no production behavior change.

### Commit 2 — Reference model V2

- remove `[:1]`;
- add input roles;
- stable ordering;
- preserve custom ignore/notes;
- tests.

### Commit 3 — Spatial relationship model

- restore view/hand/visibility/occlusion/scale concepts;
- V4 migration;
- semantic validator;
- tests.

### Commit 4 — Compiler cleanup

- neutral/action-aware placement verbs;
- semantic-null suppression;
- duplicate cleanup;
- diagnostics artifact.

### Commit 5 — Conditional constraint compiler

- add risk fragments;
- V2 prompt tail;
- compact anchors;
- dual-write V1/V2.

### Commit 6 — V2 technical edit templates

- Scene Appearance;
- Character Assembly;
- Costume Dressing;
- Expression.

### Commit 7 — Story scene V2

- input contracts;
- one canvas authority;
- compact identity;
- relationship section;
- dialogue/text logic.

### Commit 8 — Revision workflow

- correction patch;
- revision prompt;
- parent candidate manifest linkage.

### Commit 9 — V2 default

- engine profile switch;
- docs;
- compatibility flag;
- migration notes.

---

## 22. Definition of Done

The modernization is complete when all of the following are true:

- [ ] `Final_Image_Prompt.md` is still deterministic and Python-owned.
- [ ] Multiple reference images survive normalization.
- [ ] Every image input has a stable role and deterministic Image N index.
- [ ] Prompt image numbering matches attachment order.
- [ ] Custom reference preserve/ignore/notes are honored.
- [ ] Technical spatial facts are not discarded during normalization.
- [ ] Occlusion is a first-class relationship.
- [ ] Relative scale is a first-class relationship.
- [ ] Hand-to-prop assignment is structured and validated.
- [ ] Body view, head view, facing, gaze, and motion remain independent fields.
- [ ] At most one image claims edit-base/full-canvas authority.
- [ ] Generic anatomy/avoid rules are conditional rather than unconditional.
- [ ] Reference-backed characters use compact anchors by default.
- [ ] Full identity prose remains available for text-only fallback.
- [ ] No compiler-generated `none`, duplicate phrases, malformed fragments, or stale default verbs reach the final prompt.
- [ ] Scene Appearance regression cases pass.
- [ ] Falling and rope-line static prompt regressions pass.
- [ ] Costume and expression prompts contain one clear invariant contract rather than repeated lock sections.
- [ ] Targeted revision jobs can edit a prior candidate without restating the entire scene.
- [ ] V1 remains reproducible during migration.
- [ ] A/B evaluation shows equal or better visual constraint adherence with fewer high-severity correction turns.

---

## 23. Priority Recommendations

If only a small amount of work can be done initially, do these in order:

### P0 — Correct data loss

1. remove one-reference truncation;
2. stop stripping occlusion/view/hand/scale/visibility data;
3. honor custom reference ignore/notes.

These are correctness issues, not prompt-style preferences.

### P1 — Correct prompt contradictions/noise

1. fix `stands` defaults;
2. remove `none` leakage;
3. deduplicate generated fragments;
4. ensure only one canvas authority.

### P2 — Change prompt strategy

1. conditional risk constraints;
2. compact reference-backed identity anchors;
3. explicit Image N roles;
4. compact change-vs-preserve blocks.

### P3 — Exploit modern editing

1. revision/correction stage;
2. edit-base semantics for locked technical references;
3. optional masks/compositing for truly locked backgrounds.

---

## 24. Final Architectural Principle

The older pipeline often tries to obtain reliability by saying the same invariant several different ways.

For the current image engine, Zet should instead obtain reliability by making the **scene model itself more precise**.

The compiler should know:

- which image is authoritative for which property;
- exactly what may change;
- exactly what must remain invariant;
- which hand holds which object;
- which body side is near the camera;
- what overlaps what;
- how large one object is relative to another;
- where the subject looks;
- how the subject is moving;
- whether a prior image is being edited or a new image is being generated.

Then `Final_Image_Prompt.md` becomes a concise rendering of that truth rather than a defensive accumulation of warnings.

That is the main modernization goal.
