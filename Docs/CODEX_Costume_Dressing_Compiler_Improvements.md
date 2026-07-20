# CODEX Instructions: Improve Costume-Dressing Prompt Compilation

## Objective

Improve the deterministic compiler for `costume-dressing` jobs so the generated `Final_Image_Prompt.md` behaves more like the improved scene compiler:

1. State clearly and immediately what image must be created.
2. Establish the supplied Character-Assembly image as the locked authority for identity, pose, orientation, camera, and framing.
3. Make exact body/head orientation preservation a first-class instruction.
4. Present costume details only after the image task and locked source are understood.
5. Suppress empty, redundant, irrelevant, and duplicated information.
6. Preserve the existing deterministic compilation architecture, source maps, dependency manifests, review files, and job outputs.

The supplied Character-Assembly image already shows the correct character, body view, head view, neutral pose, proportions, framing, lighting, and generic fitment clothing. The task is to replace the generic fitment costume without changing the character or the technical turnaround pose.

Do not add an AI prompt-finalization stage. This remains a deterministic compiler.

---

## Primary Files and Systems to Inspect

Begin by locating and reviewing the complete costume-dressing compilation path, including:

- `Run_Costume_Dressing_Jobs.py`
- The bundle loaded by:
  - `load_bundle(project_root, "costume-dressing")`
- The static prompt template used by that bundle
- `Config/Prompt_View_Text.json`
- `Compile_Character_Template.py`
- `Job_File_Utils.render_static_prompt_artifacts`
- `Run_Body_Reference_Jobs.view_instruction`
- Existing tests and fixtures for body-reference, head-fitment, character-assembly, and costume-dressing jobs
- Representative costume templates, especially `Costume_Apprentice_Outfit.md`
- A representative current generated `Final_Image_Prompt.md`

The current runner already:

- normalizes body and head view tokens;
- loads canonical view configuration;
- validates a `character_assembly` reference;
- loads character-template sections;
- replaces character-template costume/equipment sections with sections from the selected costume file;
- selects sections through the costume-dressing bundle;
- renders final prompt, compiled sections, and source map through the shared static renderer.

Preserve that architecture. Prompt organization should primarily remain bundle/template/config-driven. Do not hardcode the entire final prompt as a large Python string inside `Run_Costume_Dressing_Jobs.py`.

---

## Required Prompt Design

Reorganize the generated prompt into the following conceptual order.

Exact heading names may follow established project conventions, but the information hierarchy must remain:

1. `# Render Task`
2. `# Locked Source`
3. `# Orientation Lock`
4. `# Pose and Camera Lock`
5. `# Background`
6. `# Costume Design`
7. `# View-Specific Costume Details` — only when useful
8. `# Equipment and Jewelry` — only when useful
9. `# Identity Preservation` — concise
10. `# Final Constraints`

The beginning of the prompt must let the image model form the correct overall image before it encounters detailed costume specifications.

---

## Required Opening Summary

The first section must describe the actual finished image, not merely identify the workflow.

Generate wording equivalent to:

```markdown
# Render Task

Create one finished full-body technical costume-dressing image of Tsaeytte, Youth, wearing the Apprentice Outfit.

Requested body view: FRONT.
Requested head view: FRONT.

Use the supplied Character-Assembly image as the locked source.
Preserve the character exactly as supplied and replace only the generic fitment clothing, jewelry, equipment, and footwear required by the costume.

Produce one character, one view, and one finished image.
```

Requirements:

- Include character name and phase.
- Include costume name.
- Include normalized body and head view labels.
- Explicitly call the output a **technical costume-dressing image** or **technical turnaround-source image**, not a portrait or scene.
- State the single allowed transformation near the beginning.
- Do not lead with art style, metadata, background details, or long negative lists.
- Do not include `Costume Role` in the final prompt unless the bundle already uses it for a concrete visual instruction. Keep it available in metadata/source maps, but suppress descriptive workflow metadata that does not materially affect the image.

---

## Locked Source Section

Replace the long and repetitive image-editing/source-authority passages with one concise authoritative section.

Generate wording equivalent to:

```markdown
# Locked Source

The supplied Character-Assembly image already defines the correct:

- character identity;
- face, hair, ears, neck, age, and species;
- body proportions and anatomy;
- body pose and stance;
- body orientation and head orientation;
- camera angle and perspective;
- full-body framing and crop;
- lighting and rendering style.

Preserve these elements exactly as shown.

Change only the clothing, jewelry, equipment, and footwear specified by the costume.
The costume must conform to the existing body. Do not alter the body to fit the costume.
```

The prompt should not repeatedly restate this authority in later sections.

Avoid overly literal phrases such as “preserve all pixels” when the actual objective is semantic image editing. The source is visually authoritative, but the prompt should remain clear and natural.

---

## Orientation Lock: First-Class Compiler Output

Exact view preservation is the most important functional improvement.

The current compiler exposes:

- `BODY_VIEW_TOKEN`
- `BODY_VIEW_LABEL`
- `BODY_VIEW_INSTRUCTION`
- `HEAD_VIEW_TOKEN`
- `HEAD_VIEW_LABEL`
- `HEAD_VIEW_INSTRUCTION`

Use these inputs to generate one consolidated costume-dressing orientation block near the top of the prompt.

### Common orientation lock

Always generate wording equivalent to:

```markdown
# Orientation Lock

The supplied Character-Assembly image already has the correct body and head orientation.

Preserve the body direction, head direction, neck angle, shoulder angle, torso angle, hip angle, knee direction, foot direction, face direction, and gaze direction exactly as supplied.

Do not rotate the head toward the viewer.
Do not twist the neck or torso.
Do not mirror the image.
Do not reinterpret the requested view.
Only replace the costume.
```

### Same body/head view

When normalized body and head view tokens are the same, add an alignment rule equivalent to:

```markdown
Head, neck, shoulders, torso, hips, knees, and feet remain aligned to the same requested direction.
Do not introduce a separate head turn or sidelong eye contact.
```

This is particularly important for profile, back, and three-quarter views.

### Different body/head views

The job schema permits separate body and head views. Do not assume they are always identical.

When the normalized body and head view tokens differ, do not force them into the same direction. Instead generate:

```markdown
Preserve the supplied relationship between body orientation and head orientation exactly.
Do not increase, reduce, reverse, or otherwise reinterpret the existing head turn.
```

The Character-Assembly reference remains the final authority.

### View-specific lock text

Use view-specific compiler/config text to describe the expected visible orientation. The exact canonical meaning of each view token must come from the existing view configuration rather than from duplicated ad hoc definitions.

For each supported view, ensure the costume-dressing instruction clearly communicates these concepts:

- `FRONT`
  - body and head square to camera when both are front;
  - no added three-quarter turn;
  - symmetrical front-facing stance remains intact.

- `BACK`
  - body and head remain facing away when both are back;
  - do not reveal more face than the supplied source;
  - do not turn the character toward the viewer.

- `LEFT_PROFILE`
  - preserve a true left-facing profile;
  - do not rotate face or torso toward camera.

- `RIGHT_PROFILE`
  - preserve a true right-facing profile;
  - do not rotate face or torso toward camera.

- front three-quarter views
  - preserve the exact supplied front three-quarter angle;
  - do not repaint the face into a direct front view;
  - do not create independent eye contact.

- back three-quarter views
  - preserve the exact supplied away-facing three-quarter angle;
  - the back remains the dominant body surface;
  - do not rotate the head or torso toward the viewer;
  - reveal the face only to the degree already present in the Character-Assembly source.

Do not add one generic “three-quarter orientation lock” section to every job. Emit only the rules relevant to the normalized body/head views.

### Configuration and provenance

Prefer storing canonical per-view wording in the existing view configuration or another small, clearly named deterministic configuration file.

Do not spread conflicting view descriptions among:

- the costume file;
- the static prompt template;
- the runner;
- multiple unrelated helper modules.

The source map must identify whether each orientation instruction came from:

- normalized runtime values;
- `Prompt_View_Text.json`;
- another explicit orientation-lock configuration.

---

## Pose and Camera Lock

Create one concise section near the top of the prompt:

```markdown
# Pose and Camera Lock

Preserve the supplied pose exactly.

Do not change:

- arm or hand position;
- leg or foot position;
- weight distribution;
- hip, shoulder, or spine alignment;
- camera distance;
- lens perspective;
- crop or full-body framing.

Do not convert the technical stance into a fashion pose, action pose, contrapposto, walking pose, or narrative gesture.
```

Do not repeat these rules in the costume, identity, good-output, bad-output, and negative-constraint sections.

### Footwear and ground contact

Retain costume-specific footwear contact requirements, but compile them once.

Use the costume metadata fields already loaded by `costume_metadata()`:

- `FOOTWEAR`
- `FOOTWEAR_CONTACT`
- `FOOTWEAR_GROUNDING`

Consolidate duplicate grounding statements. The final prompt should contain the specific `FOOTWEAR_CONTACT` rule once, in the pose/fit section or costume section.

Avoid simultaneously emitting all of the following when they convey the same instruction:

- generic body-reference grounding rules;
- `FOOTWEAR_CONTACT`;
- `FOOTWEAR_GROUNDING`;
- a repeated stance list;
- a repeated final negative list.

Preserve the most specific costume-authored rule.

---

## Background

Keep the background section concise.

Generate the configured `BACKGROUND_TREATMENT` once, after pose/camera locks and before costume details.

Do not repeat background prohibitions in the final negative list unless a separate rule adds meaning.

---

## Costume Design

Use the costume file as the authoritative source for:

- silhouette;
- upper garment;
- waist/midsection;
- lower garment;
- legwear;
- footwear;
- jewelry;
- equipment;
- materials;
- colors;
- fit;
- forbidden costume drift;
- view-specific visibility details.

The costume description should remain detailed enough to define the clothing, but remove markdown-template noise from the compiled prompt.

For example, avoid output like:

```markdown
* Costume name: `Apprentice Outfit`.
* Equipment: `None.`.
```

Prefer clean rendered prose or bullets:

```markdown
# Costume Design

- Overall silhouette: Fitted blouse over a split overskirt ending above the knees at the back, worn over leggings and knee-high boots.
- Upper garment: Rich teal fitted linen blouse...
- Waist: Broad brown leather belt...
```

Strip unnecessary backticks and doubled terminal punctuation during rendering where it can be done safely and deterministically.

Do not modify the source costume markdown merely to make one prompt cleaner. Apply prompt-specific normalization during compilation.

---

## Deterministic Suppression of Empty Information

Add a deterministic normalization/compaction stage for costume-dressing sections.

This stage must operate only on compiled output. It must not silently rewrite the source costume file.

### Empty values

Suppress bullet items or labeled fields whose semantic value is exactly one of:

- blank;
- `None`;
- `None.`;
- `N/A`;
- `Not applicable`;
- equivalent values wrapped in backticks.

Comparison should be case-insensitive after trimming whitespace, markdown backticks, and a final period.

Do not suppress sentences merely because they contain words such as “no” or “none” as part of an actual rule. For example, preserve:

- `Forbidden drift: no capes, trains, or extra equipment.`
- `No fitment clothing remains visible.`

Only suppress entries whose complete value is empty/not-applicable.

### Entire sections

Suppress an optional section if no meaningful content remains after normalization.

Examples:

- Do not emit an `Equipment and Jewelry` section containing only `None` fields.
- Do not emit a view-specific equipment section when there is no equipment and it adds no jewelry visibility rule.
- Do not emit a view-specific costume section that contains only a generic “no equipment” statement already established elsewhere.

Required bundle validation must not fail merely because an optional section becomes empty after normalization. Adjust bundle required/optional declarations accordingly.

### Anatomical left/right rules

Only emit extended anatomical left/right reminders when the costume contains sided equipment, containers, wrist items, or other asymmetrical placement that could be swapped.

When there is no sided equipment:

- omit `Right side: None`;
- omit `Left side: None`;
- omit the front-view anatomical-right/viewer-left reminder;
- omit swapped-side warnings.

A short general statement may remain only if some costume feature genuinely depends on anatomical side.

### Equipment section logic

When jewelry exists but equipment does not, emit a concise section such as:

```markdown
# Jewelry

Blue gemstone pendant centered on the chest and matching small drop earrings.
No weapons, tools, containers, or additional attachments.
```

Do not output a long equipment inventory where every category is `None`.

When real equipment exists, preserve:

- exact items;
- scale;
- anatomical side;
- order and placement;
- view-specific visibility or occlusion.

### View stubs

Treat costume and equipment view stubs as optional refinements, not mandatory boilerplate.

Include the selected view stub only when it contributes at least one meaningful detail beyond the general facts, such as:

- visible overlap or opening;
- hem behavior;
- equipment visibility or occlusion;
- left/right placement;
- a back closure;
- a profile silhouette;
- a required item that must remain visible.

Suppress a stub whose only remaining content is already present verbatim or semantically in the general costume/equipment facts.

Use a conservative deterministic rule. Do not add fuzzy AI deduplication.

---

## Reduce Duplicated Identity and Costume Preservation Text

The current generated prompt repeats costume details in:

- costume design facts;
- view-specific costume facts;
- equipment facts;
- costume preservation rules;
- good-output rules;
- bad-output rules;
- negative constraints;
- final summary.

Reduce this duplication.

### Costume preservation section

For costume-dressing jobs, the full `IDENTITY_PRESERVATION_COSTUME` section is normally redundant with the authoritative `COSTUME_DESCRIPTION_FACTS`.

Preferred behavior:

- Do not include `IDENTITY_PRESERVATION_COSTUME` in the costume-dressing final prompt by default.
- Continue loading it for workflows that require it, such as scene prompt injection.
- If an existing costume contains critical preservation information that is not represented in the facts section, migrate that information into the facts section rather than preserving two competing costume specifications.

Do not remove the section from the costume file format.

### Character identity

Because the Character-Assembly image is authoritative, character identity text should be concise.

Prefer:

```markdown
# Identity Preservation

Preserve the exact character from the supplied Character-Assembly source, including face, age, species, hair, ears, body proportions, and rendering style. Do not substitute a generic fantasy or anime face.
```

If the character template contains a compact identity-anchor section, it may be included after this sentence.

Do not emit the full long-form face, hair, ear, body, expression, and turnaround preservation manual unless the costume-dressing bundle has a demonstrated need for it.

Review the currently selected character-template sections and narrow the costume-dressing bundle to the minimum identity information necessary for this image-editing task.

---

## Remove Good Output / Bad Output Boilerplate

Do not generate separate `GOOD OUTPUT` and `BAD OUTPUT` sections for costume-dressing prompts.

Their useful content should already be expressed through:

- Render Task;
- Locked Source;
- Orientation Lock;
- Pose and Camera Lock;
- Costume Design;
- Final Constraints.

Replace them with one concise final section.

Example:

```markdown
# Final Constraints

Produce one complete full-body character image in the supplied view.

Do not change identity, anatomy, pose, orientation, camera, framing, lighting, or rendering style.

Do not leave generic fitment clothing visible.
Do not redesign or simplify the specified costume.
Do not add unlisted clothing, jewelry, equipment, weapons, or props.
Do not create a portrait crop, narrative scene, collage, split image, labeled diagram, or multi-view sheet.
```

Add task-specific drift rules only when they are not already stated in the costume facts.

---

## Bundle and Template Changes

Update the costume-dressing bundle and static prompt template so prompt order is explicit and stable.

The bundle should distinguish:

### Required information

- render-task metadata;
- locked-source instructions;
- body/head orientation lock;
- pose/camera lock;
- background treatment;
- general costume facts;
- concise identity preservation;
- final constraints.

### Optional information

- selected costume view stub;
- selected equipment facts;
- selected equipment view stub;
- anatomical side rules;
- special footwear contact text;
- extra costume-specific forbidden drift.

Do not mark optional costume/equipment view sections as required.

Ensure `Compiled_Sections.md` still shows what was selected and what was suppressed. When practical, record that a section was suppressed because it normalized to empty or redundant content.

---

## Runner Changes

Keep `Run_Costume_Dressing_Jobs.py` focused on compilation orchestration.

Add small helpers only where runtime composition is genuinely needed.

Suggested helpers or equivalents:

```python
def costume_dressing_orientation_metadata(
    body_view_token: str,
    head_view_token: str,
    body_view_data: dict,
    head_view_data: dict,
) -> dict[str, str]:
    ...
```

This helper should provide values such as:

- `ORIENTATION_LOCK`
- `BODY_ORIENTATION_LOCK`
- `HEAD_ORIENTATION_LOCK`
- `BODY_HEAD_ALIGNMENT_LOCK`

Use names consistent with the existing template metadata system.

Add matching source-map entries. Runtime-composed alignment text should be:

- `source_kind: runtime_generated`
- `editable: False`

Canonical per-view wording should remain editable in configuration and should map back to its JSON pointer.

Suggested normalization helper or equivalent:

```python
def normalize_costume_dressing_sections(
    sections: dict[str, str],
    sources: dict[str, dict],
    body_view_token: str,
) -> tuple[dict[str, str], dict[str, dict], dict[str, str]]:
    ...
```

The third return value may record suppression reasons for debugging/compiled-section output if that fits the existing architecture.

Do not introduce a new broad template engine or duplicate `render_static_prompt_artifacts`.

Do not change:

- job input field names;
- reference role `character_assembly`;
- default output locations;
- output filenames;
- status transitions;
- dependency-manifest structure, except for additive notes/metadata;
- existing public function `compile_costume_dressing_job`.

---

## Review Artifact Updates

Update `Prompt_Review.md` checklist generation to match the new compiler goals.

Suggested prompt-review checklist:

```markdown
- [ ] The opening identifies one full-body technical costume-dressing image.
- [ ] The Character-Assembly source is explicitly locked.
- [ ] Body and head orientation are stated early and match the requested views.
- [ ] The prompt forbids independent head turn, body twist, mirroring, and camera change.
- [ ] Pose, stance, and full-body framing are preserved.
- [ ] Costume details come from the selected costume file.
- [ ] Empty `None` equipment fields and redundant sections are suppressed.
- [ ] Sided equipment rules appear only when needed and use anatomical left/right.
- [ ] The prompt contains no duplicated Good Output/Bad Output boilerplate.
```

Update `Image_Review.md` to explicitly check:

```markdown
- [ ] Body view matches the Character-Assembly source exactly.
- [ ] Head view and relative head-to-body angle match the Character-Assembly source exactly.
- [ ] The character did not turn toward the viewer.
- [ ] Pose, stance, weight distribution, camera, and framing are unchanged.
- [ ] Only costume-related elements changed.
```

Retain the existing costume, jewelry, equipment, footwear, and full-body visibility checks.

---

## Tests

Add or update deterministic tests. Use existing project test conventions.

### 1. Front view, no equipment

Compile the Apprentice Outfit in `FRONT` body/head view.

Assert:

- prompt begins with a concise Render Task;
- character, phase, costume, body view, and head view appear near the top;
- locked-source section precedes costume details;
- orientation lock states front preservation;
- no `None.` inventory entries appear;
- no empty right/left equipment entries appear;
- jewelry remains;
- no Good Output or Bad Output headings appear;
- final constraints remain concise.

### 2. Back three-quarter orientation

Compile a back-left or back-right three-quarter job with matching body/head views.

Assert:

- prompt says the supplied away-facing three-quarter orientation is locked;
- prompt explicitly forbids rotating the head toward the viewer;
- prompt says the back remains dominant or uses the canonical equivalent from configuration;
- head/body alignment rule appears;
- no front-facing instruction leaks into the prompt.

### 3. True profile orientation

Compile left-profile and right-profile cases.

Assert:

- the correct side is named;
- face and torso are told to remain in true profile;
- no direct-viewer gaze instruction appears;
- left and right configurations do not cross-contaminate.

### 4. Different body and head views

Compile a valid Character-Assembly job whose body and head tokens differ.

Assert:

- compiler does not say they must face the same direction;
- prompt preserves the exact supplied relative head-to-body angle;
- prompt forbids increasing, reducing, or reversing the turn.

### 5. Costume with sided equipment

Use a fixture costume containing items on anatomical left and right.

Assert:

- anatomical side rules are included;
- equipment remains ordered and placed correctly;
- front-view viewer-left/viewer-right clarification appears only where relevant;
- source map points to the costume template and view configuration.

### 6. Costume with no jewelry or equipment

Assert:

- equipment/jewelry section is completely absent;
- optional empty sections do not trigger missing-required-section errors;
- final prompt remains grammatically complete.

### 7. View-stub suppression

Use a view stub containing only `None` fields or generic no-equipment text.

Assert:

- the stub is omitted;
- a meaningful view stub containing hem, closure, overlap, or visibility information is retained.

### 8. Source-map integrity

Assert:

- prompt source map still identifies costume-file sections;
- body/head view text points to the correct configuration paths;
- runtime-composed alignment text is labeled runtime-generated;
- suppression/normalization does not falsely attribute generated text to the costume source.

### 9. Output compatibility

Assert the runner still produces:

- `Final_Image_Prompt.md`
- `Compiled_Sections.md`
- `Prompt_Source_Map.json`
- `dependency_manifest.json`
- `Prompt_Review.md`
- `Image_Review.md`

Assert status, next actor, expected output, output directory, and reference files remain compatible.

---

## Acceptance Example

For a matching `BACK_LEFT_3_4` body/head costume-dressing job, the top of the final prompt should read approximately like this:

```markdown
# Render Task

Create one finished full-body technical costume-dressing image of Tsaeytte, Youth, wearing the Apprentice Outfit.

Requested body view: BACK-LEFT THREE-QUARTER.
Requested head view: BACK-LEFT THREE-QUARTER.

Use the supplied Character-Assembly image as the locked source.
Preserve the character exactly as supplied and replace only the generic fitment clothing, jewelry, equipment, and footwear required by the costume.

Produce one character, one view, and one finished image.

# Locked Source

The supplied Character-Assembly image already defines the correct identity, anatomy, pose, stance, body orientation, head orientation, camera, framing, lighting, and rendering style.

Preserve these elements exactly.
The costume conforms to the existing body; the body does not change to fit the costume.

# Orientation Lock

Preserve the supplied back-left three-quarter orientation exactly.

Head, neck, shoulders, torso, hips, knees, feet, face direction, and gaze remain aligned to the same requested direction.
The back remains the dominant body surface.

Do not rotate the head toward the viewer.
Do not repaint the face into a front or front-three-quarter view.
Do not twist the torso or mirror the image.
Only replace the costume.
```

The exact wording may differ, but the visual instruction hierarchy and strength must be equivalent.

---

## Non-Goals

Do not:

- add generative AI to prompt compilation;
- redesign the costume markdown data model unless a small additive field is clearly necessary;
- remove scene-oriented costume preservation sections from costume files;
- add migration code for obsolete prototype formats;
- introduce fuzzy semantic deduplication;
- alter character-assembly asset selection;
- change the current job queue/status workflow;
- solve pose drift by adding ever-longer repeated negative lists.

The improvement should come primarily from better prompt hierarchy, exact orientation locks, selective section inclusion, and deterministic suppression.

---

## Implementation Procedure

1. Inspect the full bundle/template/config path before editing.
2. Add or revise tests that capture the current undesirable prompt.
3. Reorder the costume-dressing prompt through the bundle/static template.
4. Add compiler-generated body/head orientation locks with same-view and different-view handling.
5. Narrow selected character/body-reference sections to those useful for costume dressing.
6. Add deterministic empty-value and optional-section suppression.
7. Remove redundant Good Output, Bad Output, repeated identity manuals, and repeated negative blocks.
8. Update source-map provenance for all new generated/configured text.
9. Update prompt and image review checklists.
10. Compile representative front, profile, three-quarter, back, no-equipment, and sided-equipment fixtures.
11. Compare the new generated prompt with the prior output and confirm that it is shorter, clearer, and stronger about exact pose/view preservation.
12. Run the relevant test suite and report:
    - files changed;
    - prompt structure changes;
    - suppression rules implemented;
    - tests added or updated;
    - sample before/after prompt excerpts;
    - any remaining limitations.

Implement the changes rather than returning only an implementation proposal.
