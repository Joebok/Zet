# Issues to fix

Turnarounds. Promotion not marking full body turnarounds as "LOCKED". I suspect the routine that checks if all necessary assets are available it overriding it. LOCKED should take precendence. If it happens to be the case that a full body turnaround is LOCKED but the necessary assets are not there anymore, disable the "Generate" button instead.

# New Features

## Add a costume

New page in the Dashboard: Costumes

It will have a list of costumes, a link to the related .md file that opens it in an editor.

A button to add a costume - it will have inputs for all the necessary fields, a place to upload the costume template, and when saved will save the template in the right place and create the 8 assests for that costume with the "Costume-Dressing" pipeline. 

We are also going to need an indicator as to which costime it is. I have a new template for "Formal" that will be the test case for it.

Remove hard-coded references to "Costume_Canonical_Adventure_Gear.md" and replace with parameterized "Costume_{Name}.md" type naming conventions.

## Set "Identity" images.

On the Assets page, for a locked image, add a button after "Promote to LOCKED" that says "Identity Key"

When pressed, go to a new tab - the Identity Keys page. This tab will have 2 views - List and Update

The List view is the default view when clicking the top menu buttons. The list view will show all the identity keys that have been saved. We will just see the label & view associated with the image, the image itself (restricted in height to about 100px or so, will probably want to adjust when I see it), and buttons for "Update" and "Delete"

The delete button deletes the image and the associated .json row.

The update button goes to the Update view described below.

If a user comes from the Assets page via the Identity Key button, then they will see the Update view.

On this tab we will see the image we selected (either from the list of identity keys or from the assets). Above the image, have an input bar with a label and % inputs just like the Partial sheet. Next to that in the bar a button that says "Create Identity Key". This will will do the cropping just like we do on the partial sheets, but just to this one image. Show the cropped image on the right, next to the original. Above the cropped image is a "Save" button. This will save a copy of the image in an appropriate location, and save an entry in a .json file that should reference the original Asset ID, task, and view and store the label and % and any addtional information necessary. Ultimately this .json file will be the basis to specify Identity Keys in expression sheets. So we will link them somehow to an Expression Definition and the manifest stage will make sure it can find it and the Render Console will show it when called for.

If we are editing an existing Identity Key, we default the label and the percent to whatever the stored values are. For a new key, leave the label blank (but require a non-blank label) and 100 for the percent. 

Note also that there can be many Identity Keys based off of the same Asset.

## Expression Preparation

Read Docs\Expressions.md and formulate a template to be used for expressions. These will be pipeline jobs with the full manifest, prompt, render, review. Unlike the others, however, the images are stand-alone, we don't do a full turnaround for every expression. As suggested in the document, we will be targeting a cropped image, not full body. The output will be a group of 8 different expressions, assembled just like the turnaround sheets are. So instead of grouping by task and individuating by view, we will have a whole bunch of "expression" pipeline images, each distinguish by an "expression". We will need to add them on demand. I put "expression" in quotes because this is a user-entered field like the labels for the partial crops and identity keys. We are going to need to also be able to link an "Expression Asset" to a particular Expression Definition.md file in the character/phase folder.

So although processing these images will be just like assets, I think they should be on their own page so we can show the fields that are relevant. I don't know if it would be easier or harder to store them in the asset table along with the rest or not - the choice should be with an eye towards maintainability and future features - I don't want to have to maintain two sets of code that basically do the same thing, so I lean to extending the Assets.json file and using it for everything except our directly derivative items like turnaround sheets and identity keys.

After digesting the Expressions.md file, create a template incorporating elements and section imports like for the other jobs. I'm sure we will be pulling in Character_Image_Template.md sections, and we will likely have some shared dos and don't to include as well, leaving the bulk of the descriptive detail of the expression to the Expression Definition.md file.

## Questions

1. Identity Keys scope: For v1, should Identity Keys only be creatable from locked pipeline assets on the Assets page, or should locked turnaround/partial sheets also be eligible sources?
* Only Locked pipeline assets, including expressions.

2. Identity Key crop behavior: Should Identity Keys use the same crop behavior as partial turnarounds: top-percent height crop first, then automatic width trim with buffer?
* Yes, exactly the same.

3. Identity Key save flow: Should “Save” immediately create/update the Identity Key as the locked/reference image, or should there be a candidate/review/promote step? The ToDo reads like immediate save, but I want to confirm.
* Save immeditely, overwriting the old. Since these are deterministically derived, we can regenerate them at will from actual assets that are protected by the "LOCKED" status.

4. Identity Key storage: Is this acceptable as the default structure?
Images: _Lib/Assets/{Character}/{Phase}/IdentityKeys/
Metadata: _Lib/Characters/{Character}/{Phase}/IdentityKeys.json
* Yes.

5. Expression pipeline scope: For the next implementation pass, should we only build the Identity Key feature plus expression-template/prep artifacts, or should we also start the full Expression pipeline/dashboard workflow?
* Step one is work out a template structure. I will review it, revise if necessary - then we will build the pipeline.

6. Expression assets in Assets.json: You noted that extending Assets.json seems preferable. Should Expression renders be normal assets with pipeline: "Expression" plus expression-specific fields, rather than a separate expression asset registry?
* This seems preferable to me. I think that means that a lot of things will work on them - prompt review, render console, image review, and promoting to lock, regenerate, etc. I see it as exactly the same process as working a "regular" asset, except it links to different templates and could have variable image references to manage. 

7. Expression sheet grouping: Should one Expression Sheet mean “8 expression images for one selected Identity Key / angle / crop,” laid out in a 2x4 grid, rather than a turnaround-style multi-view sheet?
* Right now, one expression at a time, which will be a single image asset. Making an "expression sheet" will be just like a turnaround sheet except that I will pick which expressions to include in a sheet and we won't need the "partial sheet" option.
* One feature that I think we might need/want is to be able to put text labels into the assembled images - so we can label the Angry image "Angry" and the happy one "Happy". Those labels would be the labels that are on the asset. But I don't know if we can stamp those into the image.

8. Expression Definition files: Should each Expression Asset link to one markdown definition file in the character/phase folder, and should there be multiple named definition files over time, or just one canonical Expression Definition.md per character phase?
* I want one expression per sheet. I think they should be in their own folder, character/phase/expression. We will need to link each Expression asset to an expression definition file.

9. Costume page scope: Should the first Costumes page support create/list/open only, or should it also support editing/deleting existing costumes?
* Not delete, not yet anyway - I don't want to deal with orphaned assets. Edits are okay I think - everything would still be wired up to the same assets and if there was a change in the .md file or something, it's the user's problem to go back and re-render it. Bare bones initally - solve all the issues so we can have 2 costumes first.

10. Costume fields: For “Add Costume,” should the required fields be Costume Name, Costume Role, Footwear, Footwear Contact, and the markdown template body, matching the current costume compiler expectations?
* Costume Name. I don't know what "costume role" is? If it isn't wired to anything, we don't need it. Footwear and Footwear Contact should be in the costume markdown I would think? And yes, they should be able to upload a costume markdown file. The save function will enforce a naming convention. The established compiler actions will throw up errors if the user screwed it up.

11. Costume template source: For the new Formal test case, will you provide/upload a completed .md costume template, or should the dashboard generate a starter template from entered fields?
* I have a template right now and am eager to add it.

12. Costume asset creation: When saving a new costume, should it always create all 8 Costume-Dressing assets immediately, using the standard view set and head_view = body_view?
* Yes.

13. Costume duplicate handling: If a costume name already exists, should Save block with an error, or update the existing costume/template and avoid creating duplicate assets?
* The naming convention mentioned in item 10 should mean that the label they give has to be unique, so block on that.

14. Expression asset metadata: Should we extend the Asset model with explicit fields like expression_definition_path and identity_key_id, or use a generic metadata object for expression-only fields? I recommend explicit fields for the known links.
*  Agreed, explicit fields.

15. Expression labels on assembled sheets: For future expression sheets, should labels be stamped into the PNG itself, or only shown in the dashboard next to the image? Stamping is feasible, but it becomes part of the reference image.
* When we do the sheets, we will stamp the expression under the image representing it (not overlay it). The multi-expression sheets are for human consumption. When using expressions for scenes, will reference the individual images, not the sheet, so there will be no labels on what the image generation engine sees.

16. Expression definition folder/name: You wrote character/phase/expression; should that be exactly _Lib/Characters/{Character}/{Phase}/Expressions/, with one markdown file per expression definition?
* Yes

## Implementation Plan

1. Fix the Issues to fix
2. Put any questions or decisions that need to be made in the Questions section above.
3. See answeres to questions, ask any follow-ups including any from the new "Add a Costume" feature.

## Backlog

* Remove the body_view/head_view split wiring. For now, keep the model fields in place but stop emphasizing head_view in dashboard tables.
* Revisit Comfy condense/render options across all pipelines, including how Pipeline Controls should expose backend selection, condense behavior, local preview rendering, and final render routing.
