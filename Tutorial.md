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

The Assets page is the operational view of character-development work. Select an asset to see its current stage, status, history, candidate image, and locked image.

Use **Advance All** to run eligible work in the selected scope. Asset actions let you regenerate work, promote an approved result, create an identity key, or open the source governing its prompt. Include locked or superseded assets only when you need to inspect older work.

### Manifest

Some pipelines pause at a manifest so you can choose their inputs. For head fitment, select the body reference and headshot that should guide the render, then save the references to continue.

### Prompt Inspection

Review a compiled prompt before rendering. Search within it, copy it, inspect which source contributed each section, or open that source in the editor. When local analysis is configured, **Analyze Prompt** provides an additional AI review.

Prompt Inspection is a review tool; opening or reading a prompt does not advance its pipeline.

### Render Console

The Render Console is the handoff point for manual image generation. Copy the prompt and reference images into your image tool, then return the generated image to Zet with an optional note.

You can also generate a local test image when a backend is configured or fail the task with a reason when it cannot be completed.

### Image Review

Compare a candidate with the currently locked image and record review notes. **Promote to LOCKED** accepts the candidate. **Fail to RENDER** requests another attempt with the existing prompt; **Fail to REGENERATE** restarts the asset so its generated materials can be rebuilt.

### Local Image Review

Generate and compare local test images for queued render tasks. Choose the number of images, try the current model or all configured models, and clear experiments when finished. Local images are review aids and do not become approved assets automatically.

### Identity Keys

Create reusable crops from approved character art. Choose a source image, label the crop for its intended use, adjust the preview, and save it. Identity keys provide focused visual references when a full turnaround is unnecessary.

### Turnarounds

Turnarounds combine approved views into character reference sheets. Review the candidate against the locked sheet, tune view detection when needed, and save partial sheets for narrower framing such as the head and upper chest. Auxiliary sheets can preserve additional useful crops.

### Costumes

Add and edit named costume definitions for the selected character phase. Each costume can feed its own dressing workflow and display its locked turnaround when completed.

### Expressions

Add expressions that should be rendered consistently for the selected character phase. The page tracks each definition and shows the locked expression once approved.

### Phase Comparison

Compare two phases of a character side by side. Choose the pipeline, view, and costume where applicable, then move through available results to check continuity or intentional visual change.

## Story Telling

### Story Overview

Create, rename, edit, view, or delete a story. The overview provides a phone-style scene viewer and navigation through the finished sequence. Save story text as it changes; use the Git controls when the story is managed through its configured repository workflow.

### Scenes

Create and order scenes within the selected story. Edit the scene text, choose image references, open the structured builder, or stage the scene for rendering. Scenes can be renamed, moved to another story, or deleted.

The image view shows the published scene image and any candidate awaiting review.

### Scene Builder

Use the Scene Builder to turn a scene into structured visual instructions. Add character, auxiliary-resource, or scene-only elements; describe composition and relationships; attach references; and continue from an earlier scene when visual continuity matters.

Review the compiled result before staging a render. Prompt Inspection and the Render Console remain available for the final handoff and review cycle.

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
2. Follow the recommended action or use Assets to advance the first pipeline.
3. Supply references when a Manifest requests them.
4. Inspect the compiled prompt.
5. Complete the render in the Render Console or with a configured local backend.
6. Review the candidate and promote it when satisfied.
7. Build identity keys, turnarounds, costumes, and expressions from approved work.

## A typical story workflow

1. Create a story and add scenes.
2. Write each scene and select reusable references.
3. Structure the visual composition in Scene Builder.
4. Inspect and render the compiled prompt.
5. Review and publish the scene image.
6. Arrange finished scenes into a zine and generate the print layout.
