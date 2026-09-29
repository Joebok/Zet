# Zet V5 Realignment

Based on everything so far, we have a clearer idea of what is working well and what needs improvement. In addition, Qwen Image 2.1 is proving to be an excellent resource for local image generation.

This is a statement of big-picture goals and open research questions, not an implementation plan. The questions below are prompts for refining the direction; they do not imply that a particular solution has been selected.

Major changes:

- Move from a character-centered workflow to a scene-centered workflow.
- Revise character and costume templates to produce more effective, context-appropriate prompts.
- Start with a fresh library organization aimed at ease of use.
- Make local image generation the primary generation workflow.

Supporting changes:

- Improve the UI, with possible replacement of dashboard technology.
- Automation.

**Questions to clarify the overall direction:**

- Are the supporting changes lower priorities, or are some prerequisites for the major changes? In particular, Universe organization may shape the new library from the beginning.
- What would make V5 successful in everyday use: less reference preparation, more reliable scene composition, faster iteration, easier asset discovery, or something else? Which outcomes matter most?

## Focus on Scenes

Up until now, the primary focus has been to create complete turnaround image sets for each character/phase and costume. See [On the Turnaround Pipelines](On%20the%20Turnaround%20Pipelines.md) for the discussion behind this change in direction.

The current method supplies reference images from a turnaround set in approximately the right orientation and relies on image generation to pose the character appropriately. The new emphasis is to approach a major character in a scene as a "subscene": resolve the pose in that smaller composition, then use the resulting image as a reference for the larger scene.

Rethink whether the current scene structure supports this workflow comfortably. Describing the spatial relationships of elements has been frustrating. A crude 3D staging system is one possible research direction for expressing positions, camera angles, and poses; its role and value are still to be explored.

**Questions:**

- Do complete turnaround sets become optional, with only the references needed for a particular scene generated? What minimum references should establish a character's identity and costume?
- Should subscenes also cover interacting groups of characters? Are their results specific to one scene, reusable across scenes, or both? How should they relate to the enduring character references so that identity does not drift?
- Which parts of scene description feel too rigid: spatial relationships, camera placement, posing, grouping elements, or something else? Would crude 3D primarily help with staging, or also supply visual guidance to image generation?

## Character and Costume Templates

Rear views (back and both rear three-quarter views), and sometimes profile views, are failing regularly for costumes. A suspected cause is the current approach of supplying a complete costume description and then adding view-specific overrides. The body may have the correct orientation while the costume appears to be worn backwards. Similar conflicts sometimes occur in head-image generation and character assembly when forward-facing head and hair descriptions are included by default.

The goal is to include descriptions appropriate to the requested view and generation context. Explore line or section tags indicating which views and pipelines a description applies to. This is a candidate approach, not yet a chosen template format.

See Docs\ZET_View_Conditioned_Template_Tagging_Spec.md and Docs\ZET_View_Conditioned_Template_Tagging_Spec.md. This work has largely been done. However, the shared templates and instructions in Shared_Library\Characters\_Shared should be updated to reflect the new approach.

## Library

The current library combines conventions from different eras: statically numbered assets, Aux Images with naming-convention tags, and newer Library Image organization with several ways to group images.

The goal is a fresh, coherent organization that makes assets easy to find, understand, and reuse. Gather requirements before choosing a structure, taking the proposed Universe boundary into account.

Character pipelines have the mechanims to find and refer to the base images they need to complete their runs. Costume templates allow for additional reference images. But the primary use case is for inclusion in scenes. Generally we have character/phases in a costumes, NPCs, and monsters as Subjects. The subjects may have Props, and scenes have Backdrops.

For non-Character Subjects, they will often start out as "one-shots" but can become recurring.
- Images used in scenes should be tagged so we can know all images for a particiular scene, and we can see what scenes any particular image is in.
- Images should also be associated with a "Scene Element" to facilitate grouping images related to one subject or prop, etc. Changes to the scene builder will be made to allow adding an existing Scene Element to a new scene.
- In the local image mode, generally we will have a set of candidate images, one of which is promoted to locked. The locked image should be stored in the library proper. The candidates stored in a seprate directory structure and are not searchable/insertable into scenes and templates.

### Universe Abstraction Layer

Add a top-level organization for collections of related characters and scenes. Store the art style and other shared image-generation parameters at this level. Each Universe is intended to be a complete library unto itself.

A Universe is fully independent. If there happen to be assets in one Universe that wanted in another, that asset can be imported just as any other image source. The UI does not need to support this option directly - one would simply save an image from one universe to a file, then switch to the other universe and add it. No linkage between them.

Canonical Art Style and the dialog style for scenes are right now the main universal settings I have in mind. There should not be a provision to override these in characters, costumes, or scenes. These are forward looking changes. It is an aethetic decision of the operator on how to address previously generated images. No marking of previous images as "stale" - it should be entirely untracked.

## Local Image Generation

Make local image generation the primary workflow. The expected pattern is to generate single test images while refining a prompt, then generate a batch of candidates to evaluate and select from.

**Questions:**

- Does "primary local" mean local by default with remote generation still available, or a fully local workflow? If remote generation remains, what role should it serve?
- Is evaluation and selection primarily manual, or should existing automated quality checks help filter or rank candidates? What information from an accepted result should remain available to support later refinement or regeneration?

## UI

The current dashboard feels primitive and does not adapt well to different screen sizes. Research ways to provide a more usable, modern interface, including improvements to the current approach and alternative dashboard technologies. The backend work will continue to be handled by Python services.

There are two related goals: responsive layout and responsiveness during long-running work. The UI should hand tasks to Python services asynchronously and remain usable while those tasks run. The method for receiving progress and results is still open for research.

**Questions:**

- Which devices and screen sizes should the UI serve, and should they all support the same workflows?
- Which everyday interactions most need improvement, such as scene editing, reference selection, comparing candidates, or monitoring jobs? These should guide technology research before a replacement is chosen.

## Automation

Continue the "Batch Status" idea to manage local resources and track background work. Substantial activity is expected through AI_Proxy, with no guarantee that Zet or the harvester will be running continuously. Clarify the desired behavior when these components stop or restart before deciding how to coordinate them.

**Questions:**

- When Zet or the harvester is closed, should submitted work continue, wait, or stop? On reopening, what should happen to unfinished jobs and completed results awaiting collection?
- How much control should the user have over competing work: choosing priorities, pausing batches, cancelling jobs, or reserving resources for interactive tests?

## Backwards Compatibility and Transition

Backwards compatibility is not a requirement. Existing character and costume templates will be copied into the new library structure and adapted as the new format takes shape. Many scenes will also be copied and adapted as the new scene structure and workflow develop. The existing Zet library will remain as it is.

There should be no runtime provisions for handling old template formats or image tags. Bringing selected content into V5 means converting it to the new conventions, not supporting the old conventions in V5. The goal is a clean break and clean code.

This project is starting out in the Zet_v5 branch of Zet and will eventually be merged into main. The main branch is available for reference here: C:\Users\Joe\Projects\Zet

**Questions:**

- Is manual adaptation of copied content sufficient, or should one-time conversion assistance be considered separately from runtime compatibility?
- After V5 merges into main, is the old library intended only as a preserved archive, or should a separate older Zet version remain usable with it?
