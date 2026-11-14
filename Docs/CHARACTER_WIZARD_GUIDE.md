# Create a character and run its first Body and Head jobs

The Character Wizard uses reference images to draft Body and Head and hair observations for a new character phase. Publishing the wizard saves `Character.md`, which supplies the text for the two render jobs. Those jobs run separately. A wizard reference does not automatically become a render reference.

## Create the character

1. Open **Character Overview** and confirm the universe in the dashboard header. For testing, use [Zet Test](http://localhost:8082/?page=onboarding) with `ZetTester` selected.
2. Choose **New > Character**. For a clean run, leave **Resume draft** on **Start a new interview**. Enter the **Character Name** and **Character Phase**. Use a name that is free in this universe.
3. Choose a **Vision model**, such as Luna (`codex:gpt-6-luna`). Add one to three **Reference images** using the file controls or **Paste image here**. You can use captions to describe what each image should contribute and **Direction** for any additional instructions. Click **Start interview**.
4. Wait for **Body** and **Head and hair** to show **Ready**. Choose a defined **Species** and fill in **Gender Presentation** for the character. The wizard also prepares Head-Image Edit starter sections. To accept the generated work as-is, leave the observations and starter sections unchanged.
5. Click **Preview Character.md** and check for validation errors. Click **Create character**. Wait for **Character created.** on **Character Overview**, then verify the new character and phase in the header.

If a section shows **Needs attention**, read its notice. For ordinary authoring you can resume the draft and use **Retry section**, or use **Refine section** with a direction to request a replacement. Preview again after any edits. For an as-is acceptance test, record the first error and stop that attempt. Manual edits or using another model would skip the path under test.

## Run Body Reference FRONT

1. Confirm the new character and phase are still selected. Choose **Assets > Body-Reference**.
2. On the FRONT tile, click **Open FRONT Candidate Board**. Use **Preview Prompt** to check that Zet can compile the prompt from the saved character and its governing templates. FRONT starts without a Body anchor.
3. Click **Draft 1** once to request one candidate. Keep the board open while it runs. Wait until the candidate is complete and its image loads. A queued request or an empty slot does not count as completion.

## Run Head Image Edit FRONT with no reference

1. Choose **Assets > Head Image Edit** for the same character and phase, then **Open FRONT Candidate Board**.
2. In **Container settings**, leave **Phase Change** off. Do not use **Upload FRONT** or save a locked source from another phase. If this board has a saved source and you intend to remove it, use **Clear source** and wait for the change to save. Turning off **Phase Change** alone does not clear a saved source.
3. Click **Preview Prompt** and confirm the reference list is empty. This is a separate check from whether the wizard used an image. Click **Draft 1** once and wait for a completed candidate with a loadable image.

## Confirm the result

For a functional run, finish when the wizard has created the character and both FRONT boards have a completed image with no error. Leave ranking, selection and locking for a separate review. If a job fails or stops progressing, record the exact message and the character, phase, pipeline, view and slot. Include the job or candidate ID if available in the board or **AI Queue**, and the release revision shown in the dashboard. Check the existing job before clicking **Draft 1** again.
