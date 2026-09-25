# To Do items

Story First Day / Chapter 01 Standing in Wonder : instructions say only 2 characters, but details of scene imply more.

Comic Panel Create. Specify overall aspect ratio (default 8.5x11) and panel divisions. Select images to place, have zoom and crop controls for assembly.

Story Telling:

Narrative writing not done in Zet. Remove the git functionality related to stories/scenes. De-Emphasize the template editing for stories and scenes. Show scene images on "Scenes" page by default. Show status indicator in side bar as to the state of the scene - does it have a locked image, is an image pending review, is it in the render console?

Responsive Design for phone, lanscape ipad viewports need work.

Setting up HTTPS://

Local Image:
Allow/require naming of runs

Gates:

Create test case suite for head-image orientation gate (create 8 sets of 5 images. Each set has a correct image for a view and images for the 4 most adjacent views - for example, the set for "front" has an actual "front" view and a front left 3/4, a front right 3/4, a left profile and a right profile. These are all for a front gaze view test which is expected to pass the correct one and fail all the others.

Do the same for the body-reference orientation gate. 

Use these tests and the knowledge gained from the new local head-image prompts to craft gate prompt language to try to get the gates working. For the models, start with image-analsysis-alt with thinking on (the default I believe). Analyze the return information to try to refine the prompts if they are not working. Remember to prioritize brevity, simplicity and directness. Try with thinking and off, and also try with luna with high and none thinking levels. If after 3 prompt edits you are still not getting valid results, write a summary of your findings and move on. And a reminder that prompts can be different for different views, you do not have to find one single prompt that universally works for each view.

As a part of this process, make sure to set up and save tests in the gate test rig - make sure that it works as intended. Fix any bugs you find it in, use gate test rig services to run the tests to make sure that it works.

Full automation after front anchor

Gate config - setting for regen after fail T/F, max re-tries

Library Integration - 

Drop-In Character Creation: drop in an image. LLMs process the image with a series of prompts to fill in the character template and the first costume template. Should also check if there is a species profile already, or if one needs to be created.