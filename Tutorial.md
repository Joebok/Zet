# Zet Tutorial

This guide gives a brief, feature-oriented tour of Zet. It follows the dashboard rather than the application's storage layout or internal implementation.

## Start a workspace

Zet has two main workspaces: **Character Development** and **Story Telling**. Switch between them from the top navigation.

Use the **New** menu to create a character, character phase, story, or scene. The current character and phase determine which development assets are shown; the current story determines which scenes are shown.

Use **Tools > To Do** for a small project-wide scratch list.

## Character Development

### Character Overview

Create a character through the onboarding interview. Save a draft as you work, copy the generated ChatGPT prompt when you want help developing the character, and upload the completed character template. Zet validates the result and recommends the next action.

A phase represents a distinct version of a character, such as a different age or era. Create another phase when the character's visual identity needs its own development workflow.

### Assets

Open **Assets** for Batch Status or choose Body-Reference, Head-Image, Character-Assembly, or Costume-Dressing. Review local candidates within the selected pipeline and lock the image you want downstream workflows to use. Traditional character-generation pipelines are retired; their files remain available for historical references.

### Identity Keys

Create reusable crops from verified local locks. Choose a source image, label the crop for its intended use, adjust the preview, and save it. Historical keys remain viewable and usable as scene references; editing a crop requires a current local source.

### Turnarounds

Turnarounds combine local locked views into character reference sheets. Review the candidate against the locked sheet, tune view detection when needed, and save partial sheets for narrower framing such as the head and upper chest. Historical sheets remain viewable.

### Costumes

Add and edit named costume definitions for the selected character phase. Costume-Dressing readiness and counts come from local locks.

### Phase Comparison

Compare local pipeline locks across two phases side by side. Choose the pipeline, view, and costume where applicable, then move through available results to check continuity or intentional visual change.

## Story Telling

### Stories and Narrative scenes

Open Stories in the Story Telling workspace. Create a story, add scenes, and edit
shared setting, camera, lighting and style. Add named subjects, props and environment
elements with reusable images from the library. Current costume references follow
the preferred image for that exact character, phase, costume and view.

Create a backdrop and one or more subject subscenes. Develop their prose, staging,
physical context and framing, then interview/synthesize/render deliberately. Select
and lock useful source images before placing layers in the final assembly. Character
candidate review stays inside its local Assets pipeline.

Candidates reads the configured Adventure Log index without changing it. Import a
brief into a selected Narrative story, open any existing associated scene, or review
changed source text. Acknowledgement preserves authored inputs and images. Imported
briefs are starting points, not automatically working render pipelines.

First Day and Phlan Adventures migrated as 28 editable stubs. Each scene shows its
previous Legacy image below Save scene / Delete scene. These images are preserved
library assets, distinct from new selected final assemblies. Review missing references
and image/prose differences before generation. Scene Builder, old Scene Renders and
3D layout execution are retired; the [offline archive](Archive/scene-builder/README.md)
preserves the layout implementation and source data for future work.

### Zines

Create an eight-panel zine layout from story scenes. Fill the layout from the story, choose front and back covers, assign scene pages, and mark selected pairs as two-page spreads. Generate or regenerate the print layout after making changes.

Use **Image Config** to adjust zine scale, margin, and output width when the default print layout needs tuning.

## Tools and administration

### Source Editor

Open the Source Editor from Prompt Inspection or an asset's governing template. Edit the selected source, review warnings, and save. Prompt-insert blocks can place exceptional text at a deliberate point in a compiled prompt.

After changing a source, recompile or regenerate the affected prompt and review the diff before rendering again.

### AI Controls

Use AI Controls to harvest completed answers, archive harvested jobs, configure automatic harvesting and prompt analysis, choose the final-render backend, and start or stop managed services. Queue summaries show jobs waiting, running, or ready to harvest.

### Image Config

Select Stable Matrix or ComfyUI, then choose a render profile, checkpoint, and global positive or negative prompt text. ComfyUI also exposes its server and timing settings. This page also contains turnaround and zine output sizing.

### Pipeline Inspection

Search active character and story pipelines, select a generated item, and preview its text or image. Copy text or open the containing folder when deeper diagnosis is needed. This view is read-only.

### Pipeline Controls

Review project configuration and the stages, actors, workers, and asset counts for the selected character phase. Batch render reset sends matching assets back for a fresh render while preserving their compiled prompts. Include locked assets only when you intentionally want to replace approved work.

## A typical character workflow

1. Create a character and complete onboarding.
2. Follow the recommended action or open Assets and select a local pipeline.
3. Review candidates and lock the local views needed by downstream work.
4. Create Identity Keys, Turnarounds, and Costume definitions from local locks.
5. Compare local locks across phases when checking continuity.

## A typical story workflow

1. Create a Narrative story and add a scene, or import an Adventure Log candidate.
2. Review the depicted moment, visible participants, continuity and exact dialogue.
3. Bind current costume references and other approved library images.
4. Develop backdrop and subject subscene inputs, then generate/select/lock their images.
5. Place completed sources in the final assembly, synthesize/render and select the result.
6. Use selected final assemblies as zine sources; legacy images remain separate history.
