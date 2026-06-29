Implement a config-driven body-reference prompt compiler.

Goal:
Move body-reference include/skip behavior out of Python and into external configuration files. For body-reference, Final_Image_Prompt.md must be entirely Python-owned and statically generated from template sections and config. Do not use an AI prompt-finalizer step.

Create or update these config files:

1. Config/Prompt_Task_Bundles.json
2. Config/Prompt_View_Aliases.json
3. Config/Prompt_View_Text.json
4. Config/Prompt_Templates/body_reference_v1.md

Prompt_Task_Bundles.json should define the body-reference bundle, including:
- required_sections
- optional_sections
- forbidden_sections
- static_prompt_template
- review_checklist
- resource policy
- output filenames
- next_status
- next_actor

For body-reference, required sections should be:
- GENERAL_DESCRIPTION_FACTS
- BODY_DESCRIPTION_FACTS
- IDENTITY_PRESERVATION_CORE
- IDENTITY_PRESERVATION_BODY
- FITMENT_RENDERING_RULES
- TECHNICAL_MODESTY_LAYER
- NEGATIVE_GUIDANCE_GENERAL

Optional sections:
- BODY_DESCRIPTION_VIEW_{VIEW}
- NEGATIVE_GUIDANCE_JOB_SPECIFIC

Forbidden sections:
- *_PICARESQUE
- HEAD_DESCRIPTION_*
- HAIR_DESCRIPTION_*
- COSTUME_DESCRIPTION_*
- EQUIPMENT_DESCRIPTION_*
- EXPRESSION_DESCRIPTION_*
- SCENE_RENDERING_*

Prompt_View_Aliases.json should map user/job view strings such as front-left-3/4 to normalized tokens such as FRONT_LEFT_3_4.

Prompt_View_Text.json should map each normalized view token to:
- label
- instruction

body_reference_v1.md should be a static prompt template using placeholders:
- {{CHARACTER_NAME}}
- {{CHARACTER_PHASE}}
- {{VIEW_TOKEN}}
- {{VIEW_LABEL}}
- {{VIEW_INSTRUCTION}}
- {{SECTION:SECTION_NAME}}

The script should:
1. Read body-reference jobs with Status = READY_FOR_COMPILE and Next Actor = PYTHON.
2. Load the body-reference bundle from Config/Prompt_Task_Bundles.json.
3. Normalize the View using Config/Prompt_View_Aliases.json.
4. Load view label/instruction from Config/Prompt_View_Text.json.
5. Read Character_Image_Template.md.
6. Extract sections marked:
   <!-- ZET:BEGIN SECTION_NAME -->
   ...
   <!-- ZET:END SECTION_NAME -->
7. Resolve {VIEW} tokens in section names.
8. Validate required sections exist and are non-empty.
9. Include optional sections when present and non-empty.
10. Validate that no forbidden section patterns are included.
11. Load Config/Prompt_Templates/body_reference_v1.md.
12. Replace metadata placeholders and section placeholders.
13. Write Final_Image_Prompt.md.
14. Write Compiled_Sections.md showing exactly which sections were included.
15. Write dependency_manifest.json using the resource policy from the bundle. For body-reference, no external or cached images should be used by default.
16. Advance the job to the bundle’s next_status and next_actor.
17. On error, set Status = ERROR and populate stable Error Code and readable Error Message.

Important constraints:
- Do not hardcode body-reference section include/skip behavior in Python except as fallback error handling.
- Do not call any AI model.
- Do not create Render_Packet.md for body-reference unless existing compatibility requires it.
- Do not render images.
- Do not use cached, discovered, or implicit image resources.
- Do not summarize or rewrite extracted template sections.
- Preserve exact extracted section text in Compiled_Sections.md.
- Final_Image_Prompt.md must be clean render-facing text with no ZET markers, compiler notes, JSON, YAML, or implementation commentary.