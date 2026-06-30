Implement the first end-to-end Body-Reference pipeline and a simple template editing input page.

Context:
We are building a character image prompt compiler. The goal is to generate Final_Image_Prompt.md deterministically from structured Character_Image_Template.md sections. For early technical pipelines, including body-reference through costume-fitment, the final prompt must be Python-owned and statically generated. Do not use an AI prompt finalizer for body-reference.

This milestone should concentrate on body-reference only, while laying groundwork for later pipelines.

Primary objectives:
1. Create a config-driven body-reference compiler.
2. Generate Final_Image_Prompt.md directly from template sections.
3. Generate Compiled_Sections.md.
4. Generate dependency_manifest.json.
5. Generate review stub files.
6. Advance jobs through the body-reference flow.
7. Add a simple dashboard/input page that lets a user edit template section text without touching ZET markers.
8. Add a pipeline selector to that page so only sections relevant to the selected pipeline are exposed.

Do not render images.
Do not call external APIs.
Do not call local AI models.
Do not create an AI prompt-finalization step.

================================================================================
PART 1 — FINALIZE / ADD CONFIG FILES
================================================================================

Create these files if they do not already exist:

Config/
  Prompt_Task_Bundles.json
  Prompt_View_Aliases.json
  Prompt_View_Text.json
  Prompt_Review_Checklists.json
  Prompt_Templates/
    body_reference_v1.md

If the project already has an equivalent Config location, use the existing convention, but keep the names clear and stable.

--------------------------------------------------------------------------------
1. Config/Prompt_Task_Bundles.json
--------------------------------------------------------------------------------

Add a body-reference bundle.

The include/skip behavior must live in this config, not hardcoded in Python.

Body-reference bundle:

{
  "body-reference": {
    "description": "Static technical full-body reference prompt. No AI prompt finalizer.",
    "prompt_builder": "static",
    "required_sections": [
      "GENERAL_DESCRIPTION_FACTS",
      "BODY_DESCRIPTION_FACTS",
      "IDENTITY_PRESERVATION_CORE",
      "IDENTITY_PRESERVATION_BODY",
      "FITMENT_RENDERING_RULES",
      "TECHNICAL_MODESTY_LAYER",
      "NEGATIVE_GUIDANCE_GENERAL"
    ],
    "optional_sections": [
      "BODY_DESCRIPTION_VIEW_{VIEW}",
      "NEGATIVE_GUIDANCE_JOB_SPECIFIC"
    ],
    "forbidden_sections": [
      "*_PICARESQUE",
      "HEAD_DESCRIPTION_*",
      "HAIR_DESCRIPTION_*",
      "COSTUME_DESCRIPTION_*",
      "EQUIPMENT_DESCRIPTION_*",
      "EXPRESSION_DESCRIPTION_*",
      "SCENE_RENDERING_*"
    ],
    "static_prompt_template": "body_reference_v1",
    "review_checklist": "body_reference_prompt_review_v1",
    "resources": {
      "allow_external_images": false,
      "allow_cached_images": false,
      "allow_job_declared_images": false
    },
    "output_files": {
      "compiled_sections": "Compiled_Sections.md",
      "final_prompt": "Final_Image_Prompt.md",
      "dependency_manifest": "dependency_manifest.json",
      "prompt_review": "Prompt_Review.md",
      "image_review": "Image_Review.md"
    },
    "next_status": "READY_FOR_PROMPT_REVIEW",
    "next_actor": "HUMAN"
  }
}

Important:
- Python may have fallback validation, but section selection should come from this file.
- Make the config loader tolerant of future tasks being added.
- Do not require other pipeline bundles yet.

--------------------------------------------------------------------------------
2. Config/Prompt_View_Aliases.json
--------------------------------------------------------------------------------

Create a view alias map.

Include at least:

{
  "front": "FRONT",
  "front-left-3/4": "FRONT_LEFT_3_4",
  "front left 3/4": "FRONT_LEFT_3_4",
  "front-left-three-quarter": "FRONT_LEFT_3_4",
  "front left three quarter": "FRONT_LEFT_3_4",
  "front-right-3/4": "FRONT_RIGHT_3_4",
  "front right 3/4": "FRONT_RIGHT_3_4",
  "front-right-three-quarter": "FRONT_RIGHT_3_4",
  "front right three quarter": "FRONT_RIGHT_3_4",
  "left-profile": "LEFT_PROFILE",
  "left profile": "LEFT_PROFILE",
  "right-profile": "RIGHT_PROFILE",
  "right profile": "RIGHT_PROFILE",
  "back-left-3/4": "BACK_LEFT_3_4",
  "back left 3/4": "BACK_LEFT_3_4",
  "back-left-three-quarter": "BACK_LEFT_3_4",
  "back left three quarter": "BACK_LEFT_3_4",
  "back-right-3/4": "BACK_RIGHT_3_4",
  "back right 3/4": "BACK_RIGHT_3_4",
  "back-right-three-quarter": "BACK_RIGHT_3_4",
  "back right three quarter": "BACK_RIGHT_3_4",
  "back": "BACK"
}

Normalization should be case-insensitive and trim whitespace.

--------------------------------------------------------------------------------
3. Config/Prompt_View_Text.json
--------------------------------------------------------------------------------

Create plain-language view instructions.

Include:

{
  "FRONT": {
    "label": "front view",
    "folder_name": "Front",
    "output_name_fragment": "Front",
    "instruction": "Render the character from a direct front view, facing the viewer squarely."
  },
  "FRONT_LEFT_3_4": {
    "label": "front-left three-quarter view",
    "folder_name": "Front_Left_3_4",
    "output_name_fragment": "Front-Left-3-4",
    "instruction": "Render the character from a front-left three-quarter view. The character faces partly toward the viewer, with the character's left side more visible than the right. Do not render this as a straight front view or profile view."
  },
  "FRONT_RIGHT_3_4": {
    "label": "front-right three-quarter view",
    "folder_name": "Front_Right_3_4",
    "output_name_fragment": "Front-Right-3-4",
    "instruction": "Render the character from a front-right three-quarter view. The character faces partly toward the viewer, with the character's right side more visible than the left. Do not render this as a straight front view or profile view."
  },
  "LEFT_PROFILE": {
    "label": "left profile view",
    "folder_name": "Left_Profile",
    "output_name_fragment": "Left-Profile",
    "instruction": "Render the character from a direct left profile view, showing the character's left side."
  },
  "RIGHT_PROFILE": {
    "label": "right profile view",
    "folder_name": "Right_Profile",
    "output_name_fragment": "Right-Profile",
    "instruction": "Render the character from a direct right profile view, showing the character's right side."
  },
  "BACK_LEFT_3_4": {
    "label": "back-left three-quarter view",
    "folder_name": "Back_Left_3_4",
    "output_name_fragment": "Back-Left-3-4",
    "instruction": "Render the character from a back-left three-quarter view. The character is turned partly away from the viewer, with the character's left side more visible than the right. Do not render this as a straight back view or profile view."
  },
  "BACK_RIGHT_3_4": {
    "label": "back-right three-quarter view",
    "folder_name": "Back_Right_3_4",
    "output_name_fragment": "Back-Right-3-4",
    "instruction": "Render the character from a back-right three-quarter view. The character is turned partly away from the viewer, with the character's right side more visible than the left. Do not render this as a straight back view or profile view."
  },
  "BACK": {
    "label": "back view",
    "folder_name": "Back",
    "output_name_fragment": "Back",
    "instruction": "Render the character from a direct back view, facing away from the viewer squarely."
  }
}

The compiler should use:
- label in Final_Image_Prompt.md
- instruction in Final_Image_Prompt.md
- folder_name for output directory derivation if the job does not provide a specific Output Directory
- output_name_fragment for expected image name derivation if the job does not provide Expected Output

--------------------------------------------------------------------------------
4. Config/Prompt_Templates/body_reference_v1.md
--------------------------------------------------------------------------------

Create this static prompt template.

Use these placeholders:
- {{CHARACTER_NAME}}
- {{CHARACTER_PHASE}}
- {{VIEW_TOKEN}}
- {{VIEW_LABEL}}
- {{VIEW_INSTRUCTION}}
- {{SECTION:SECTION_NAME}}

Suggested template:

Create a full-body technical body-reference image for {{CHARACTER_NAME}}, {{CHARACTER_PHASE}}.

Requested view:
{{VIEW_LABEL}}

View token:
{{VIEW_TOKEN}}

View instruction:
{{VIEW_INSTRUCTION}}

This is a neutral technical reference image, not a narrative scene.

The character should be shown standing in a neutral, readable pose on a plain studio background with even lighting. The full body must be visible from head to feet.

Use this image only as a body proportion, fitment, silhouette, and reference-alignment source for later pipeline stages.

{{SECTION:GENERAL_DESCRIPTION_FACTS}}

{{SECTION:BODY_DESCRIPTION_FACTS}}

{{SECTION:BODY_DESCRIPTION_VIEW_{VIEW}}}

{{SECTION:IDENTITY_PRESERVATION_CORE}}

{{SECTION:IDENTITY_PRESERVATION_BODY}}

{{SECTION:FITMENT_RENDERING_RULES}}

{{SECTION:TECHNICAL_MODESTY_LAYER}}

{{SECTION:NEGATIVE_GUIDANCE_GENERAL}}

{{SECTION:NEGATIVE_GUIDANCE_JOB_SPECIFIC}}

Do not add costume, weapons, props, scene storytelling, emotional acting, dramatic lighting, narrative environment, spell effects, decorative background elements, or unrelated character-design details.

The final image should be sober, neutral, readable, and technically useful.

Important:
- The generated Final_Image_Prompt.md must not contain unresolved placeholders.
- Optional sections that are missing or empty should be omitted cleanly.
- Final_Image_Prompt.md should contain no ZET markers.

--------------------------------------------------------------------------------
5. Config/Prompt_Review_Checklists.json
--------------------------------------------------------------------------------

Create a simple review checklist config.

Add:

{
  "body_reference_prompt_review_v1": {
    "required_phrases": [
      "full-body technical body-reference",
      "neutral technical reference image",
      "plain studio background",
      "even lighting",
      "full body must be visible",
      "technical fitment shell"
    ],
    "forbidden_phrases": [
      "picaresque",
      "seductive",
      "flirtatious",
      "dramatic scene",
      "battle",
      "spellcasting"
    ],
    "required_sections": [
      "GENERAL_DESCRIPTION_FACTS",
      "BODY_DESCRIPTION_FACTS",
      "IDENTITY_PRESERVATION_BODY",
      "TECHNICAL_MODESTY_LAYER"
    ],
    "forbidden_section_patterns": [
      "*_PICARESQUE",
      "COSTUME_DESCRIPTION_*",
      "EQUIPMENT_DESCRIPTION_*",
      "SCENE_RENDERING_*",
      "EXPRESSION_DESCRIPTION_*"
    ],
    "fail_on_unresolved_placeholders": true,
    "fail_on_zet_markers": true
  }
}

For now, this can be used to generate review stubs and optionally run basic static checks.

================================================================================
PART 2 — SCRIPT BEHAVIOR
================================================================================

Create or update scripts as appropriate. Prefer integrating with existing project conventions if similar scripts already exist.

Suggested script files:

Scripts/
  Compile_Character_Template.py
  Build_Static_Final_Prompt.py
  Run_Body_Reference_Jobs.py
  Review_Prompt_Static.py
  Advance_Job.py
  Validate_Render_Output.py

If existing scripts already provide these responsibilities, update them instead of duplicating functionality.

--------------------------------------------------------------------------------
1. Compile_Character_Template.py
--------------------------------------------------------------------------------

Responsibilities:
- Read a Character_Image_Template.md file.
- Extract sections marked with:

  <!-- ZET:BEGIN SECTION_NAME -->
  ...
  <!-- ZET:END SECTION_NAME -->

- Return a dictionary:
  section_name -> section_text

Rules:
- Preserve section text exactly except for trimming leading/trailing blank lines where necessary.
- Detect duplicate section names and raise a clear error.
- Detect malformed marker pairs and raise a clear error.
- Do not interpret Markdown headings.
- ZET markers are the source of truth.

Expose functions similar to:

- load_template_sections(template_path) -> dict
- resolve_section_name(section_name, view_token) -> str
- select_sections(all_sections, bundle, view_token) -> compiled result

Compiled result should track:
- included required sections
- included optional sections
- missing required sections
- missing optional sections
- forbidden pattern matches if any included section violates the bundle

Use fnmatch-style wildcard matching for forbidden patterns.

--------------------------------------------------------------------------------
2. Build_Static_Final_Prompt.py
--------------------------------------------------------------------------------

Responsibilities:
- Load the static prompt template named by the bundle.
- Replace metadata placeholders.
- Replace section placeholders.
- Resolve {VIEW} inside section placeholders.
- Omit missing optional section placeholders cleanly.
- Error on missing required section placeholders.
- Error on unresolved placeholders remaining in the final prompt.
- Error if ZET markers remain in the final prompt.
- Write Final_Image_Prompt.md.
- Write Compiled_Sections.md.

Compiled_Sections.md should show:
- job metadata
- task
- normalized view token
- included required sections
- included optional sections
- missing optional sections
- each included section name and exact content

Suggested format:

# Compiled Sections

Job ID:
Task:
Character:
Phase:
View Token:

## Included Required Sections

- SECTION_NAME

## Included Optional Sections

- SECTION_NAME

## Missing Optional Sections

- SECTION_NAME

---

# SECTION_NAME

[exact content]

--------------------------------------------------------------------------------
3. Run_Body_Reference_Jobs.py
--------------------------------------------------------------------------------

This is the main coordinator for this milestone.

Responsibilities:
1. Read the Job List using existing project conventions.
2. Find jobs with:
   Task = body-reference
   Status = READY_FOR_COMPILE
   Next Actor = PYTHON

3. Validate required job fields:
   - Job ID
   - Task
   - Character
   - Phase
   - View
   - Template Path

4. Normalize view using Config/Prompt_View_Aliases.json.
5. Load view data using Config/Prompt_View_Text.json.
6. Load body-reference bundle using Config/Prompt_Task_Bundles.json.
7. Read Character_Image_Template.md.
8. Extract required and optional sections.
9. Generate output directory if needed.

If Output Directory is present on the job, use it.
If not present, derive:

Characters/{Character}/{Phase}/Body_Reference/{folder_name from Prompt_View_Text.json}

10. Determine expected output filename.

If Expected Output is present on the job, use it.
If not present, derive:

Body-{output_name_fragment from Prompt_View_Text.json}.png

11. Generate:
   - Final_Image_Prompt.md
   - Compiled_Sections.md
   - dependency_manifest.json
   - Prompt_Review.md
   - Image_Review.md

12. Update the job:
   Status = READY_FOR_PROMPT_REVIEW
   Next Actor = HUMAN
   Final Prompt = path
   Compiled Sections = path
   Dependency Manifest = path
   Prompt Review = path
   Image Review = path
   Expected Output = expected output image path
   Last Updated = current timestamp

13. On error:
   Status = ERROR
   Error Code = stable short code
   Error Message = readable explanation
   Last Updated = current timestamp

Do not render images.
Do not call any AI.
Do not use cached image resources.

--------------------------------------------------------------------------------
4. dependency_manifest.json
--------------------------------------------------------------------------------

For body-reference, write:

{
  "job_id": "...",
  "task": "body-reference",
  "character": "...",
  "phase": "...",
  "view_token": "...",
  "resources_allowed": false,
  "resources": [],
  "resource_policy": {
    "allow_external_images": false,
    "allow_cached_images": false,
    "allow_job_declared_images": false
  },
  "notes": [
    "Body-reference uses no external, cached, discovered, or prior-rendered image resources unless explicitly allowed by future task configuration."
  ]
}

Read the resource policy from the bundle.

--------------------------------------------------------------------------------
5. Prompt_Review.md stub
--------------------------------------------------------------------------------

Generate a human-friendly review file.

Suggested content:

# Prompt Review

Job ID:
Task:
Character:
Phase:
View:
Prompt File:

Review Status: PENDING
Reviewer: HUMAN
Reviewed At:

## Checklist

- [ ] Prompt specifies full-body technical body-reference.
- [ ] Prompt includes requested view token and plain-language view instruction.
- [ ] Prompt includes body facts.
- [ ] Prompt includes identity/body preservation rules.
- [ ] Prompt includes technical fitment shell.
- [ ] Prompt avoids costume sections.
- [ ] Prompt avoids picaresque/flavor sections.
- [ ] Prompt avoids narrative scene instructions.
- [ ] Prompt avoids emotional acting.
- [ ] Prompt avoids props/weapons/equipment.
- [ ] Prompt contains no unresolved placeholders.
- [ ] Prompt contains no ZET markers.

## Static Review Findings

[Populate with PASS/FAIL/WARN items if Review_Prompt_Static.py is implemented.]

## Notes

--------------------------------------------------------------------------------
6. Image_Review.md stub
--------------------------------------------------------------------------------

Generate:

# Image Review

Job ID:
Task:
Character:
Phase:
View:
Image File:

Review Status: PENDING
Reviewer: HUMAN
Reviewed At:

## Checklist

- [ ] Full body visible from head to feet.
- [ ] Requested view is correct.
- [ ] Body proportions match the template.
- [ ] Fitment shell is correct.
- [ ] No costume details were added.
- [ ] No props or weapons were added.
- [ ] No narrative scene was added.
- [ ] Lighting/background are neutral.
- [ ] Image is useful for later head/costume fitment.

## Notes

--------------------------------------------------------------------------------
7. Review_Prompt_Static.py
--------------------------------------------------------------------------------

Optional but preferred.

Responsibilities:
- Read Final_Image_Prompt.md.
- Read checklist config from Config/Prompt_Review_Checklists.json.
- Run simple deterministic checks:
  - required phrases present
  - forbidden phrases absent
  - no unresolved {{...}} placeholders
  - no <!-- ZET: markers
- Append or populate Static Review Findings in Prompt_Review.md.

Do not block the pipeline at first unless existing job flow expects it.
The purpose is early diagnosis, not rewriting.

--------------------------------------------------------------------------------
8. Validate_Render_Output.py
--------------------------------------------------------------------------------

Optional first version.

Responsibilities:
- For jobs in READY_FOR_RENDER, check whether Expected Output exists.
- If present, update:
  Status = READY_FOR_IMAGE_REVIEW
  Next Actor = HUMAN
- If absent, leave unchanged or write a nonfatal note depending on existing convention.

Do not auto-mark DONE.

================================================================================
PART 3 — JOB STATE MODEL
================================================================================

For body-reference, use these statuses:

READY_FOR_COMPILE
READY_FOR_PROMPT_REVIEW
READY_FOR_RENDER
READY_FOR_IMAGE_REVIEW
DONE
ERROR

Expected flow:

READY_FOR_COMPILE
  -> READY_FOR_PROMPT_REVIEW
  -> READY_FOR_RENDER
  -> READY_FOR_IMAGE_REVIEW
  -> DONE

This milestone only needs to automate:

READY_FOR_COMPILE -> READY_FOR_PROMPT_REVIEW

Optionally implement output validation:

READY_FOR_RENDER -> READY_FOR_IMAGE_REVIEW

Prompt review and image review can remain human-driven for now.

================================================================================
PART 4 — TEMPLATE INPUT PAGE / DASHBOARD
================================================================================

Add a simple input page to help users fill in Character_Image_Template.md without touching markers.

Use existing dashboard/web UI conventions if present. If no dashboard exists yet, create the simplest local implementation consistent with the project. A simple Flask app or existing local web framework is acceptable if already used in the project. Do not introduce a heavy frontend build unless the project already uses one.

Primary goal:
The user should edit section text only. Python/dashboard assembles the template with the correct ZET markers.

--------------------------------------------------------------------------------
1. Page behavior
--------------------------------------------------------------------------------

Create a page/tool called something like:

Template Section Editor
or
Character Template Editor

The page should allow the user to select:

- Character
- Phase
- Pipeline

For this milestone, pipeline selector only needs:

- body-reference

But the implementation should be data-driven from Config/Prompt_Task_Bundles.json so additional pipelines can appear later.

When the user selects a pipeline, the page should expose only the sections relevant to that pipeline.

For body-reference, expose:
- required_sections
- optional_sections after resolving {VIEW} if a view is selected

Because BODY_DESCRIPTION_VIEW_{VIEW} is view-specific, the page should also include a View selector if the selected pipeline contains any {VIEW} sections.

For body-reference, the page should expose these text inputs:

Required:
- GENERAL_DESCRIPTION_FACTS
- BODY_DESCRIPTION_FACTS
- IDENTITY_PRESERVATION_CORE
- IDENTITY_PRESERVATION_BODY
- FITMENT_RENDERING_RULES
- TECHNICAL_MODESTY_LAYER
- NEGATIVE_GUIDANCE_GENERAL

Optional:
- BODY_DESCRIPTION_VIEW_{VIEW}
- NEGATIVE_GUIDANCE_JOB_SPECIFIC

If View = FRONT_LEFT_3_4, expose:
- BODY_DESCRIPTION_VIEW_FRONT_LEFT_3_4

Do not expose forbidden sections.
Do not expose picaresque sections for body-reference.

--------------------------------------------------------------------------------
2. Page fields
--------------------------------------------------------------------------------

Each section should display:

- Section name
- Required/optional badge
- Short description if available
- Large textarea containing only the section body text
- Save button

The textarea must not include:

<!-- ZET:BEGIN ... -->
<!-- ZET:END ... -->

The backend is responsible for wrapping saved text with the correct markers.

--------------------------------------------------------------------------------
3. Template assembly behavior
--------------------------------------------------------------------------------

When saving:

- Load the existing Character_Image_Template.md if it exists.
- Parse all existing ZET-marked sections.
- Update only the sections shown/edited on the page.
- Preserve all other sections exactly.
- Rebuild the file with proper markers.
- Do not duplicate markers.
- Do not allow nested markers inside user-entered text.
- If user text contains "<!-- ZET:BEGIN" or "<!-- ZET:END", reject with a validation error.
- If the file does not exist, create a new Character_Image_Template.md from known section names.

For the initial version, acceptable creation behavior:
- Create only the sections relevant to the selected pipeline.
- Future sections can be added later.

Better creation behavior if easy:
- Create a full starter Character_Image_Template.md from the earlier full template skeleton, but only expose selected pipeline sections on the page.

--------------------------------------------------------------------------------
4. Section ordering
--------------------------------------------------------------------------------

Use a stable section order.

For body-reference editor display order:

1. GENERAL_DESCRIPTION_FACTS
2. BODY_DESCRIPTION_FACTS
3. BODY_DESCRIPTION_VIEW_{VIEW}
4. IDENTITY_PRESERVATION_CORE
5. IDENTITY_PRESERVATION_BODY
6. FITMENT_RENDERING_RULES
7. TECHNICAL_MODESTY_LAYER
8. NEGATIVE_GUIDANCE_GENERAL
9. NEGATIVE_GUIDANCE_JOB_SPECIFIC

This order should come from the task bundle:
- required_sections in order
- optional_sections in order

After resolving {VIEW}, display in that order.

--------------------------------------------------------------------------------
5. Section descriptions
--------------------------------------------------------------------------------

Optional but useful: add a config file or inline map for section descriptions.

If adding config, create:

Config/Prompt_Section_Metadata.json

Example:

{
  "GENERAL_DESCRIPTION_FACTS": {
    "label": "General Description — Just the Facts",
    "description": "Brief factual summary of the character without mood, story, or emotional interpretation."
  },
  "BODY_DESCRIPTION_FACTS": {
    "label": "Body Description — Just the Facts",
    "description": "Technical body description for build, proportions, posture, and silhouette."
  },
  "BODY_DESCRIPTION_VIEW_{VIEW}": {
    "label": "Body Description — Requested View",
    "description": "View-specific body notes. The editor resolves this to the selected view."
  },
  "IDENTITY_PRESERVATION_CORE": {
    "label": "Identity Preservation — Core",
    "description": "Core identity anchors that should remain stable across renders."
  },
  "IDENTITY_PRESERVATION_BODY": {
    "label": "Identity Preservation — Body",
    "description": "Rules for preserving the character's body proportions and physical type."
  },
  "FITMENT_RENDERING_RULES": {
    "label": "Fitment Rendering Rules",
    "description": "Rules for neutral technical reference rendering."
  },
  "TECHNICAL_MODESTY_LAYER": {
    "label": "Technical Modesty / Safety Layer",
    "description": "Instructions for the neutral technical fitment shell or equivalent non-sensual reference covering."
  },
  "NEGATIVE_GUIDANCE_GENERAL": {
    "label": "General Negative Guidance",
    "description": "General avoid rules for preventing drift."
  },
  "NEGATIVE_GUIDANCE_JOB_SPECIFIC": {
    "label": "Job-Specific Negative Guidance",
    "description": "Avoid rules specific to the selected pipeline or job."
  }
}

This is preferred because it keeps the page data-driven.

--------------------------------------------------------------------------------
6. Editor routes / commands
--------------------------------------------------------------------------------

If implementing as a web page, suggested routes:

GET /template-editor
- Shows selectors for character, phase, pipeline, and view.

GET /template-editor/edit?character=...&phase=...&pipeline=body-reference&view=front
- Loads relevant sections into textareas.

POST /template-editor/save
- Saves updated section text.

If implementing as a simple local CLI first, create equivalent behavior:
- List sections relevant to a pipeline.
- Export an editable JSON form.
- Import edited JSON form and rebuild Character_Image_Template.md.

But a basic web page is preferred if dashboard work already exists.

--------------------------------------------------------------------------------
7. Backend helper for template editing
--------------------------------------------------------------------------------

Create reusable helper functions rather than embedding parsing logic directly in page handlers.

Suggested module:

Scripts/Template_Section_Editor.py

Responsibilities:
- list_pipeline_sections(pipeline, view_token)
- load_template_sections(template_path)
- save_template_sections(template_path, updated_sections, section_order)
- validate_section_text(text)
- create_template_if_missing(template_path, sections)

Rules:
- User-entered text cannot contain ZET markers.
- Existing unknown sections should be preserved.
- Existing section order should be preserved where possible.
- New sections should be appended in bundle order if not present.

================================================================================
PART 5 — CHARACTER TEMPLATE REQUIREMENTS FOR TESTING
================================================================================

For testing, ensure at least one Character_Image_Template.md exists with these sections:

GENERAL_DESCRIPTION_FACTS
BODY_DESCRIPTION_FACTS
IDENTITY_PRESERVATION_CORE
IDENTITY_PRESERVATION_BODY
FITMENT_RENDERING_RULES
TECHNICAL_MODESTY_LAYER
NEGATIVE_GUIDANCE_GENERAL

Optional:
BODY_DESCRIPTION_VIEW_FRONT
BODY_DESCRIPTION_VIEW_FRONT_LEFT_3_4
BODY_DESCRIPTION_VIEW_FRONT_RIGHT_3_4
BODY_DESCRIPTION_VIEW_LEFT_PROFILE
BODY_DESCRIPTION_VIEW_RIGHT_PROFILE
BODY_DESCRIPTION_VIEW_BACK_LEFT_3_4
BODY_DESCRIPTION_VIEW_BACK_RIGHT_3_4
BODY_DESCRIPTION_VIEW_BACK
NEGATIVE_GUIDANCE_JOB_SPECIFIC

Do not require completion of head, hair, costume, expression, picaresque, or scene sections for this milestone.

================================================================================
PART 6 — ACCEPTANCE CRITERIA
================================================================================

The milestone is complete when:

1. Config files exist and body-reference include/skip behavior is defined outside Python.
2. A body-reference job in READY_FOR_COMPILE can be processed.
3. The script generates:
   - Final_Image_Prompt.md
   - Compiled_Sections.md
   - dependency_manifest.json
   - Prompt_Review.md
   - Image_Review.md
4. Final_Image_Prompt.md is clean render-facing text.
5. Final_Image_Prompt.md contains no:
   - ZET markers
   - JSON
   - YAML
   - compiler notes
   - unresolved {{...}} placeholders
   - implementation commentary
6. Compiled_Sections.md shows exactly which sections were included.
7. dependency_manifest.json uses no image resources for body-reference.
8. The job advances from:
   READY_FOR_COMPILE / PYTHON
   to:
   READY_FOR_PROMPT_REVIEW / HUMAN
9. Missing required sections produce ERROR with a clear error code and message.
10. Optional missing sections are omitted cleanly.
11. Forbidden section patterns prevent accidental inclusion.
12. A simple template editor/input page exists.
13. The template editor has a pipeline selector.
14. Selecting body-reference exposes only body-reference-relevant sections.
15. The editor provides one textarea per section body.
16. The editor does not expose or require the user to edit ZET markers.
17. Saving through the editor writes valid marked sections into Character_Image_Template.md.
18. Existing unrelated sections are preserved when saving.
19. User-entered ZET markers are rejected.
20. No AI model is used anywhere in this body-reference compile path.

================================================================================
PART 7 — NON-GOALS
================================================================================

Do not implement:
- Head-fitment pipeline
- Costume-fitment pipeline
- Expression pipeline
- Narrative scene pipeline
- AI prompt finalizer
- AI reviewer that rewrites prompts
- Image rendering
- Image analysis
- Complex frontend framework unless already present
- Resource discovery
- Cached image reference use
- Prompt overlay system unless already trivial to integrate

================================================================================
PART 8 — IMPLEMENTATION NOTES
================================================================================

Keep the implementation incremental and readable.

Prefer:
- Small reusable functions.
- Config-driven behavior.
- Clear error messages.
- Minimal logging by default.
- No hidden fallback behavior that silently changes prompts.
- Exact preservation of template section text in Compiled_Sections.md.
- Deterministic generated prompts.

Use stable error codes such as:
- MISSING_JOB_FIELD
- UNKNOWN_VIEW
- MISSING_CONFIG
- MISSING_TEMPLATE
- MALFORMED_TEMPLATE_MARKERS
- DUPLICATE_SECTION
- MISSING_REQUIRED_SECTION
- UNRESOLVED_PLACEHOLDER
- ZET_MARKER_IN_FINAL_PROMPT
- FORBIDDEN_SECTION_INCLUDED
- TEMPLATE_SAVE_REJECTED_MARKER_TEXT

After implementation, provide:
1. List of files created.
2. List of files modified.
3. How to run the body-reference worker.
4. How to open/use the template editor.
5. One example body-reference job entry.
6. One example output folder produced by a successful run.
