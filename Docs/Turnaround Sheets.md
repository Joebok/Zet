# Assemble Turnaround Sheets

Once we have 8 locked assets, we can create a turnaround sheet.

## Use Python to assemble

See Docs\codex_character_grid_implementation_prompt.md for a detailed implementation plan for taking the images, finding bouding boxes for the characters in the images (assuming the gray background our assets have) and the scaling and putting the images together in a single file as described.

These instructions are no aware of the larger context, so you will have to integrate them into Zet in a way that makes the most sense. 

Additionally, we will probably want to add a "normalization" routine in the pipeline that will scale all the assets of a particular task so they depict the character with the same image height.

## How to store them

Do we want them as an "asset" in our normal table? Or should they be kept track of an managed in their own table? 

- I think they should be in their own. The existing asset table facilitates the pipeline, the ulimate stage of which is the turnaround - and there are no further steps to follow, it is just a thing to be used as a reference for other work. 
