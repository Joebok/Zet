# Scenes and Stories

## Objective

Build a framework to manage the construction of "scenes" under an umbrella of a "story"

A **story** conceptually is
* a markdown file telling/describing the story.
* contains one or more scenes

Practically a story is a subfolder in the Stories library folder (currently C:\Users\Joe\Projects\Zet_Library\Stories)

A **scene** conceptually is
* narrative description of the scene (markdown file)
* an associated image

Practially a scene is a markdown file in the Story folder.

## Git management

C:\Users\Joe\Projects\Zet_Library is it's own git repo. It is just going to have the "main" branch - the purpose of git for the library is just to sync between machines, not to preserve change history.

I will want the Dashboard to manage fetch, pull, stage, and commit operations for the Stories folder.

## Dashboard

### Stories Page

A "Stories" page. This will list the Stories that have been started in a sidebar on the left. There is no .json management - it's all file-system based. So just list the subfolders in the library Stories folder. Each row should have an "Open Story File" button and an "Edit Scenes" button. The bulk of the screen is an edit box.

Have an "Add New" button that will take the title of the story. When clicked:

1. Make the story title filename safe (replace all weird characters with '-', including spaces)
2. Create a subfolder of the library Stories folder of that safe Title
3. Inside the new subfolder, make a copy of <LibraryPath>\Stories\_Story_Template.md with the safe name of the story + ".md"

The "Open Story File" button should open the <LibraryPath>\Stories\<Safe_Story_Name>.md into the edit box. If there isn't one, then make one just as if it was a new story and open that up. 

On save, validate by making sure the Title: Canonical Art Style: have been filled in. 

The "Edit Scenes" button should open a new Dashboard page "Scenes"

### Scenes Page

Dropdown at the top left of all the Stores from the <LibraryPath>\Stories folder. If opened from the Story "Edit Scenes" button, pre-select that Story. If not, then use the last story that was used by the Scenes page. For the very first time, use the top one on the list.

Under the story selection, have a left sidebar listing the scenes. These will be all the .md files NOT named <Safe_Story_Name>.md. Sort them alphabetically. Keep the list minimal - nothing but the name to conserve as much screen space as possible.

When clicked, open the selected scene up in an edit box that will take up the bulk of the screen. On save, validate the ## Render Prompt section to make sure there is a scene name specified and that the {{SECTION:STORY_TITLE}} keys are there {{SECTION:CANONICAL_ART_STYLE}}

At the top of the leftsidebar there should be a "New Scene" button. This will collect the scene name, make it file safe, and then make a copy of <LibraryPath>\_Scene_Template.md in the <LibraryPath>\Stories\<Safe_Story_Name> folder named <Safe_Scene_Name>.md

### Image Picker

I will want an easy way to find then copy and paste image references into the scenes. We already have a good way to tag Aux Resources, we need to extend that to all of the Locked costume and expression images.

* Extend this functionality by constructing a naming convention to reference the assets mentioned if we don't already have that.
* Make a copy link function like is on Aux Resources to put where we show individual images - so the Assets page and the Expressions page. (Not costumes since on that page we don't pick individual poses). 
* Add easy filter controls to the Image Picker so I can quickly find what I want. Mostly this will be a text-box filter, but we might need selectors for character and possibly phase.
* The picker should show thumbnails of the filtered list to choose from.
* The filters should persist while editing the scene.

Format of the Image Picker
* Right-side sidebar. Filter box at the top for text filters, then dropdown for Character. 
* The filter should search all the phases of the character and all the Aux Resource types.
* When one of the rows of the image picker is clicked, it should copy the right tag to be pasted into the scene document.

## Story Pipeline

We will want to have a story Pipeline that will create Assets for each Scene and then compile image prompts and marshall the refered images to send to the Render Console.

It will not be necessary to track these in the same way as assets - the final images will be stored in Story folder and not managed by the Dashboard. For the purposes of going through the pipeline process we might consider making "temporary" asset rows - I don't know. Whatever is the easiest to use exiting functionality to get to the Render Console and Image Review. At Image Review, if accepted, the image is put into the Story folder and the pipeline's job is done.
