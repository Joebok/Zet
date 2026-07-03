# Assemble Turnaround Sheets

Once we have 8 locked assets, we can create a turnaround sheet.

It would be best if we can implement this directly by creating a new image file and placing the locked assets into it in a defined pattern. This is a purely deterministic operation, an image generator should not be required.

Question: Do we have tools usable by python that can accomplish this task?

## Potential issues:

* It is possible/likely that the images are not all the same size or even aspect ratio. The turnaround assembly would need to account for that. We would have a set height/width for the turnaround page, and the turnaround assembler would need to scale images to fit in section of layout that view was assigned to.

* Within the image proper, the characters maybe differently sized. The images should all have a neutral gray background - but there is variation and hints of shadows. Nevertheless, is there a deterministic, fool-proof way to scale the characters in each image so they will end up on the turnaround at the same height?

* If that character-scaling isn't really feasible, could the operator have a screen to mark out an outline rectangle that the character fits into, and then use that rectangle as a crop marker to then scale everything the same?

## How to store them

Do we want them as an "asset" in our normal table? Or should they be kept track of an managed in their own table? 

- I think they should be in their own. The existing asset table facilitates the pipeline, the ulimate stage of which is the turnaround - and there are no further steps to follow, it is just a thing to be used as a reference for other work. 
