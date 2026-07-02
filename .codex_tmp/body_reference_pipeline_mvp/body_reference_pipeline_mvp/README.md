# Body-Reference Pipeline MVP

This package contains a drop-in MVP for compiling `body-reference` jobs into:

- `Final_Image_Prompt.md`
- `Compiled_Sections.md`
- `dependency_manifest.json`
- `Prompt_Review.md`
- `Image_Review.md`

The final prompt is Python-owned and statically generated. No AI prompt finalizer is used.

## Files

```text
Config/
  Prompt_Task_Bundles.json
  Prompt_View_Aliases.json
  Prompt_View_Text.json
  Prompt_Review_Checklists.json
  Prompt_Templates/
    body_reference_v1.md
Scripts/
  Run_Body_Reference_Jobs.py
Job_List.example.json
```

## Minimal job flow

```text
READY_FOR_COMPILE / PYTHON
  -> READY_FOR_PROMPT_REVIEW / HUMAN
```

## Run

From your project root:

```bash
python Scripts/Run_Body_Reference_Jobs.py --job-list Job_List.json
```

Or test with the included example after adapting the template path:

```bash
python Scripts/Run_Body_Reference_Jobs.py --job-list Job_List.example.json
```

## Required template sections

Your `Character_Image_Template.md` must include these marked sections:

```markdown
<!-- ZET:BEGIN GENERAL_DESCRIPTION_FACTS -->
...
<!-- ZET:END GENERAL_DESCRIPTION_FACTS -->

<!-- ZET:BEGIN BODY_DESCRIPTION_FACTS -->
...
<!-- ZET:END BODY_DESCRIPTION_FACTS -->

<!-- ZET:BEGIN IDENTITY_PRESERVATION_CORE -->
...
<!-- ZET:END IDENTITY_PRESERVATION_CORE -->

<!-- ZET:BEGIN IDENTITY_PRESERVATION_BODY -->
...
<!-- ZET:END IDENTITY_PRESERVATION_BODY -->

<!-- ZET:BEGIN BODY_REFERENCE_RENDERING_RULES -->
...
<!-- ZET:END BODY_REFERENCE_RENDERING_RULES -->

<!-- ZET:BEGIN TECHNICAL_MODESTY_LAYER -->
...
<!-- ZET:END TECHNICAL_MODESTY_LAYER -->

<!-- ZET:BEGIN NEGATIVE_GUIDANCE_GENERAL -->
...
<!-- ZET:END NEGATIVE_GUIDANCE_GENERAL -->
```

Optional view-specific section example:

```markdown
<!-- ZET:BEGIN BODY_DESCRIPTION_VIEW_FRONT_LEFT_3_4 -->
...
<!-- ZET:END BODY_DESCRIPTION_VIEW_FRONT_LEFT_3_4 -->
```

Optional job-specific negative guidance:

```markdown
<!-- ZET:BEGIN NEGATIVE_GUIDANCE_JOB_SPECIFIC -->
...
<!-- ZET:END NEGATIVE_GUIDANCE_JOB_SPECIFIC -->
```

## Notes

- Include/skip behavior is configured in `Config/Prompt_Task_Bundles.json`.
- View aliasing is configured in `Config/Prompt_View_Aliases.json`.
- Plain-language view reinforcement is configured in `Config/Prompt_View_Text.json`.
- Static prompt structure is configured in `Config/Prompt_Templates/body_reference_v1.md`.
- The runner currently supports JSON job lists: either a list or `{ "jobs": [...] }`.
- If your existing Job List is Markdown/YAML/CSV, adapt only the `load_jobs()` and `save_jobs()` functions.
