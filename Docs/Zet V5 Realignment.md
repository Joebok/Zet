# Major Refactor, Realignment

Based on everthing so far, we have a clearer idea of what is working well and what needs improvement. In addition, Qwen Image 2.1 is proving to be an excellent resource for local image generation.

Major 
- Move away from focus on Character to focus on Scenes
- Character and Costume template changes to facilitate more efficent prompts
- Library rearrangement - start with fresh organization aimed at ease of use
- Move to primary local image generation

Minor
- UI Improvements, possible replacement of dashboard technology
- Automation
- Add "Universe" abstraction layer

## Focus on Scenes

Up until now, primary focus has been to create complet turnaround image sets for each character/phase and costume. See Docs\On the Turnaround Pipelines.md for the genesis of this idea.

Current methodology is to provide reference images from a turnaround set in approximately the right orientation and hope the image generation can pose the character appropriately. The new emphasis will be approaching a (major) character in a scene as a "subscene" where the work of posing will largely be done in a subscene to become the reference image for the scene.

Rethink the current scene data structure. Is it too rigid? Many frustrations with trying to describe the 3d position of elements - what about a crude 3D system?

## Character and Costume Templates

Back views (Back and both 3/4 views) and sometimes profile views are failing on costumes with regularity. The reason for this is the general philosphy of a complete costume description and then adding in view-specific overrides. This tends to result in the body of the character in the correct view but "wearing" the costume backwards. This effect is sometimes seen in head-image and character assembly, particulary related to forward-facing head and hair descriptions being in the prompt by default.

Explore ideas around line/section tags to indicate which views and pipelines the line applies.

## Library

Current library organization is a hodgepodge of different eras. We have statically numbered assets, we have Aux Images with naming convention tags, and we have more recent Library Image organization that has several different ways to group images. 

Step one here will be to gather requirements.

## Local Image Generation

Main difference here is that local image generation will largely be producing single "test" images for prompt refinement, and then running batches of several images from which to evaluate and pick

## UI

The FastAPI pages seem primitive and are not doing responsive design very well. Compare/contrast other technology to provide a modern UI experience. The UI still will use Python calls to do all the back end work.

## Automation

Continue the "Batch Status" idea to manage local resources. It is expected that there will be a lot of background activity through AI_Proxy that will need to be run asynchronously with no guarantee Zet or the harverster is always running.

## 'Universe' abstration layer

Add a top level organization to the library in which to keep collections of related characters and scenes. Art style and other global parameters for image generation within that "universe" are stored here. Each Universe is a complete library unto itself.

# Backwards Compatibility

Not a requriement. Existing character and costume templates will be copied into the new library structure and modified as the new template format takes shape. Also many scenes will be copied over initially and modified as the new scene structure and methods take shape. But the existing Zet library will remain as it is.

There should be NO PROVISIONS for handling an old template or image tag. A clean break so we have clean code.

This project is starting out in the Zet_v5 branch of Zet and will eventually be merged into main. The main branch is available for reference here: C:\Users\Joe\Projects\Zet
