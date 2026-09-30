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

### Story Overview

Create, rename, edit, view, or delete a story. The overview provides a phone-style scene viewer and navigation through the finished sequence. Save story text as it changes; use the Git controls when the story is managed through its configured repository workflow.

### Scenes

Create and order scenes within the selected story. Edit the scene text, choose image references, open the structured builder, or stage the scene for rendering. Scenes can be renamed, moved to another story, or deleted.

The image view shows the published scene image and any candidate awaiting review.

### Scene Builder

Use the Scene Builder to turn a scene into structured visual instructions. Add character, auxiliary-resource, or scene-only elements; describe composition and relationships; attach references; and continue from an earlier scene when visual continuity matters.

Review the compiled result before staging a render. Prompt Inspection and the Render Console remain available for the final handoff and review cycle.

### Prompts, Render, and Image Review

These production pages operate on story scenes. Review scene prompts, stage manual or local scene renders, and approve or discard scene candidates here. Character candidate review remains inside each local Assets pipeline.

### Auxiliary Images

Store reusable non-character subjects such as locations, creatures, vehicles, or props. Organize resources by category, add one or more labeled images, and use the generated reference tag in scene content or the Scene Builder.

### Scene Image Review

The first accepted scene render becomes the published image. Later renders appear as candidates beside the published image. Promote a candidate to replace the published version, or discard it to keep the current image.

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

1. Create a story and add scenes.
2. Write each scene and select reusable references.
3. Structure the visual composition in Scene Builder.
4. Inspect and render the compiled prompt.
5. Review and publish the scene image.
6. Arrange finished scenes into a zine and generate the print layout.
