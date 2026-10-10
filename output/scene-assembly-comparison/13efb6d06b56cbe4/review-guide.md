# Blinded visual review

## Open the images and score them

In PowerShell from `C:\Users\Joe\Projects\Zet_v5`, run:

```powershell
.\.venv\Scripts\python.exe -m zet.scripts.scene_assembly_comparison review 13efb6d06b56cbe4
```

This opens the local review page in the Codex browser. It shows one full-size candidate at a time, lets you move through all 72 images, and saves your ratings and reasons directly to this experiment. The “Open comparison sheet” link shows the three blinded methods for that seed together. Keep the terminal running while you use the page. Ratings are saved into `evaluation.json` and `review-scorecard.csv` automatically.

An “assistant-only provisional review” would mean I look at the images and suggest scores, which you would then need to verify. No such review has been performed; the scores in this run are intended to come from your visual judgment.

## Shorthand in review reasons

- **A:** Kaeldor and the schoolboys subscene is duplicated/overlaid.
- **B:** Tsaeytte’s or Valindia’s boots are partly or fully missing.
- **C:** Valindia and Tsaeytte have merged.
- **D:** Depth order is reversed: Kaeldor and the schoolboys should be foreground; Tsaeytte and Valindia should be behind them in the midground.
- **E (Chapter 01):** The Kaeldor-and-schoolboys subscene is duplicated and floating; Tsaeytte's hair is missing or transparent, with strange marks around her shoes.

Score every token independently within its scene and seed, before opening `unblinding-key.json`.
Use `pass`, `fail`, or `unassessable`, and give a short reason for each rating. Score native and
lettered variants separately. A pass requires the criterion to be clearly satisfied in the image.

| Criterion | Review question |
|---|---|
| `cast_and_identity` | Are the required four/five people visible and recognizable in the accepted identities and costumes? |
| `pose_and_expression` | Are the accepted poses, expressions, and internal group arrangement preserved? |
| `props_and_source_retention` | Are source props retained? In Chapter 03, five books pass source retention even though five violates the authored requirement. |
| `facing_and_gaze` | Do facing and gaze relationships match the intended interaction? |
| `scale_depth_and_grounding` | Are relative sizes, foreground/background order, cropping, contact, and overlaps readable? |
| `background_continuity` | Is the arch/background coherent, with inscriptions retained and no distracting holes or duplicated structures? |
| `native_dialogue` / `lettered_dialogue` | Is the exact dialogue present once, legible, attached to the correct speaker, and safely placed? |
| `integration_quality` | Are seams, halos, contact shadows, lighting, and pasted appearance acceptable? |
| `narrative_readability` | Does the scene read as intended, including departure motion or Chapter 03's aftermath? |
| `authored_requirements` | Does it satisfy authored requirements separately from inherited source defects? Chapter 03 calls for four books and readable walking. |

For the lettering stage, use `reuse` when the native balloon is correct, `replace` when a usable
balloon needs new lettering, `add` when a balloon is missing, and `unsafe` when a repair would overlap
or repaint a character. `balloon_box` and `speaker_anchor` use normalized canvas coordinates.
