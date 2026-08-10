# Prompt Evolution Lab

Open **Tools → Prompt Evolution** and select a locked Costume-Dressing costume/view. Zet creates a non-destructive, subject-aware 768 × 1024 reference derivative and renders every experiment candidate at the same dimensions.

Runs and their template snapshots, prompts, scores, and images are stored under the selected asset's `Prompt_Evolution` pipeline folder. Strategy-v2 runs keep a reusable identity/costume prompt core separate from the controlled full-body render wrapper. Each new batch retains its prior winner's seed and randomizes the remaining seeds.

Evaluations return a score, visible observation, corrective instruction, and confidence for every category. Refinement receives the two weakest corrections, triggered hard-checklist corrections, the reference image, and the selected candidate. It edits atomic prompt terms by stable ID; invalid, duplicate, contradictory, or no-op mutations are rejected and retried once.

Automatic runs explore all configured batches, then pause at `AWAITING_FINALIST`. Finalists are randomized and shown without scores or prompt text. A human selects the final reusable core or keeps the incumbent. The selected `prompt_core.json` and `evaluation_wrapper.json` are persisted separately.

Evaluation checklist items are configured in `Config/Prompt_Evolution/checklist.json` and character/costume sidecars. Version-2 items use `id`, `item`, `question`, `correction`, `category`, and `max_rating`. The checklist model returns true, false, or indeterminate; only a true violation caps the category. New runs snapshot the current checklist, while legacy item-only checklists remain readable.

Archived candidates can be replayed through `POST /api/prompt-evolution/runs/{run_id}/replay`. Replay artifacts are stored separately under `Prompt_Evolution_Experiments`; polling `GET /api/prompt-evolution/replays/{experiment_id}` advances repeated evaluations and text-only versus image-grounded corrective refinements without modifying the source run.

Identity categories use a calibrated 0–10 scale, with 5 as the true midpoint, 7 as generally successful with visible defects, and 9–10 reserved for extremely close or effectively exact matches.

## Local smoke test

1. Start Ollama, Stable Matrix with its API enabled, File Proxy, Zet auto-harvest, and the dashboard.
2. Confirm **Tools → AI Controls** lists the services as available.
3. Open **Tools → Prompt Evolution**, select a locked costume/view, a vision model, checkpoint, and Stable Matrix profile.
4. Set **Images** to `5`, **Batches** to `2`, and choose **Manual selection**.
5. Start the run and verify the derivative preview is 768 × 1024.
6. Confirm the second row retains the winning seed, uses new comparison seeds, and shows category scores and an effective-prompt diff.
7. After the final batch, verify the run enters `AWAITING_FINALIST`, hides scores and prompts, and shows randomized finalists.
8. Select a finalist or keep the incumbent. Verify the run enters `COMPLETE` and writes `prompt_core.json` and `evaluation_wrapper.json`.
