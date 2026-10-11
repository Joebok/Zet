# Image and scene workflow recovery

New manual render tasks contain a snapshot of the prompt, ordered reference images,
image assignments, and content hashes. Recompile creates a new attempt. Keep the
task directory with its references: submitted and superseded tasks are retained
deliberately and are hidden from the active render list.

## Recover interrupted work

| Situation | Recovery |
| --- | --- |
| An image upload fails | Retry the same task with the same image and comment. Publication is atomic; an identical completed submission returns the existing answer. A different answer cannot overwrite it. |
| Harvest reports an error | Correct the error shown in the queue, then run Harvest again. The answer and `harvest_error.json` remain available. Other answers continue processing. |
| A newer attempt supersedes an answer | The old files remain in the queue, with a record under `Zet_File_Proxy_State/Superseded`. They cannot advance the newer attempt. |
| Scene candidate was replaced | Each harvested response is retained under the target pipeline's `Render_Attempts`, together with its ask manifest. Previous candidates and provenance are retained there too. |
| Promotion fails partway through | Retry promotion. `Promotion.json` records preparation and completion; candidates remain until the image and provenance are committed. Previous locked images are backed up. |
| ComfyUI times out | Retry with the same inputs. `ComfyUI_Submission.json` contains the remote prompt ID; polling resumes without submitting another render. |
| ComfyUI submission has an unknown outcome | Inspect the server queue/history before resetting the submission journal. Zet deliberately does not automatically resubmit a possibly accepted request. |
| Queue says a route or transfer is missing | Restore the route or complete the transfer identified in the recovery message, then harvest again. Do not discard the answer. |
| Import fails after creating a scene | Retry the same candidate import. Its reservation reuses the original scene slug. Confirmed reimports preserve the previous Scene Builder document under the story pipeline's `_Imports` directory. |
| Interview is interrupted | Reopen Interview in the same browser. Narrative, completed phases, answers, and draft are saved locally. Start New Interview begins again; a changed scene revision prevents applying an outdated draft. |
| Saving reports a stale revision | Keep the current draft and reload the latest scene/asset before reconciling the edits. Zet rejects the overwrite. |

Scenes now require explicit candidate review, including the first render. Promotion
checks current scene inputs and candidate provenance. Existing images without
provenance are reported as unverified rather than assumed current.

Character regeneration and prompt-review invalidation preserve prior generated
artifacts in backup/history directories. These retained files increase disk usage;
this change does not automatically purge them.

The locking and revision protocol coordinates Zet writers on the same filesystem.
External editors must still avoid overwriting active project files. Interview
checkpoints are browser-local and do not survive clearing that browser's storage.
