# Enhanced Aux Resources

Aux Resources are currently just an image file. Instead, each Aux Resource shoud be a folder. I the folder is a template that will contain information used in combination with scene builder .json file to compile prompts.

This will mean splitting the "add" functionality into two pieces - adding the resource folder and then adding images to it.

## Adding a New Aux Resource

Use the resouce category and label to: 

- Save creates a folder in <Zet_Library>\AuxiliaryResources\Images with the "safe" name of the resource to add.
- Into that folder, put a copy of <Zet_Library>\AuxiliaryResources\_Shared\AuxResource_Template.md named "<safe name>_Template.md"
- Set the template fields:
Resource_Name: `Resource Name`
Resource_Category: `Category`

## Adding a New Image

- Add a new "image label" field.
- Add a new "Save Image" button
- when an image is pasted or a file selected and the "Save Image" button is clicked, store the image with the safe name o fthe image label into the folder for the resource.

## New Tag Formet

To accomodate this change, the image tags need to include the resource folder:

{{AUX:<categroy>:<resource_folder>:<image_label>}}

All actions that set or use these tags will need to be updated to use the new format to find the correct images.

## Aux Resources Screen Edits

Make the left column narrower.

In the right column:

- Move "Save Resource" button up, directly under the Label input.
- "Save Resource" should only create the folder and template.
- In a new container under "Save Resource" put:

List of existing images (if any - show "no images" if there are none)

Under list put the Auxiliary Resource Preview. When an image from the list above is selected, display that image in the preview.

Under the preview put the image paste/file selector.

Under the preview put a "New Image" button.

Under the selector put an input box that shows the name (if any) of the image selected from the list.

If an image has been selected, then show an "Update Image" button. If clicked then

- If the new image name is different than the original one, then the old image should be renamed with the new name
- If there is an image in the paste/file selector box, then replace the image with the new one.

If the "New Image" button has been clicked:

- Deselect any row from the list.
- Clear the Image Name field
- Change the label on the "Update Image" to "Save Image"

If save image is clicked, then save the image into the resource folder and add it to the list.


## Backward compatibility

No backward compatibility is required.

