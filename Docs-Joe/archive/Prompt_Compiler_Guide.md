# Zet prompt compiler guide

This guide accompanies local batch Prompt Improvement packages. The saved `Final_Image_Prompt.md` for each view is the text sent to the image renderer. Edit suggestions must target the source files, not that generated artifact.

## Source layers

Each task has a static prompt template under `Config/Prompt_Templates`. The compiler combines it with selected marked sections from the character template, optional costume template, shared prompt sections and view metadata. `Compiled_Sections.md` lists the selected sections; `Prompt_Source_Map.json` maps final prompt fragments back to their sources; `dependency_manifest.json` records reference image roles and other render inputs.

Body Reference describes the body and its technical view. Head Image describes the head and hair. Character Assembly combines the selected body and head images for the matching view. Costume Dressing applies the costume to the selected assembled character. Other views may use the selected FRONT image as an additional consistency anchor. Reference images are separate render inputs, even when the prompt mentions them.

## Markers and tokens

Character and costume source sections use paired markers such as `<!-- ZET:BEGIN BODY_PROPORTIONS -->` and `<!-- ZET:END BODY_PROPORTIONS -->`. Names must match and cannot be duplicated or nested. Static templates select sections through tokens such as `{{BODY_PROPORTIONS}}`; view-specific section names can contain `{VIEW}`, which resolves to the active view token. The compiler also supplies metadata and reference tags. `{{IMAGE:...}}` and `{{AUX:...}}` identify managed image references; their meaning and file attachments come from the image catalog and dependency manifest. Keep marker names, token syntax and required sections intact when proposing changes.

The template can mark blocks `IMAGE_PROMPT_ONLY`, `ANALYSIS_PROMPT_ONLY`, `LOCAL_PIPELINE_ONLY` and `TRADITIONAL_PIPELINE_ONLY`. The compiler filters these by prompt variant and pipeline mode before rendering. A suggestion inside the wrong block will not affect the local image prompt.

## Reviewing a change

Use the package's saved final prompt and source map to find where a structural instruction originated. Specify the source file and section to edit, explain how its wording reaches the affected views, and check for conflicting instructions in other layers. Prefer narrow wording that preserves canonical identity and view constraints. A difference between images can also reflect renderer variability; avoid promising that wording alone will eliminate it.
