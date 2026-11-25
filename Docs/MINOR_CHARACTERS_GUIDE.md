# Minor Characters

Minor Characters are independent workspaces for people who do not need a full Character pipeline. Each workspace keeps one source image, a Style board, and separate boards for Front, Front Left 3/4, Front Right 3/4, Left Profile, and Right Profile. The shared Candidate Board provides rendering, comparison, selection, locking, and review controls. Minor Character tools add workspace management, prompt authoring, interviews, and the Style-to-view handoff.

## Create a workspace

1. Select the intended universe and open **Minor Characters**.
2. Enter a unique name in **New Minor Character** and create the workspace.
3. In **Container Settings**, choose **Choose from Image Inventory** to bind an existing reference. To add a new source, choose or paste an image, enter its Inventory label, then click **Import to Image Inventory and use**. The new image is not bound as the source until the explicit import action succeeds. Use the workspace's **Authoring Model** selector for Intake, interviews, and prompt writing. The selector is shared across Style and the official views. **Luna Review** always uses Luna and has no model selector.
4. Run Intake. Review the fields it fills and correct anything that does not match the source.

The workspace keeps its selected Inventory reference. Add the image to the same universe before creating the workspace.

## Build and refine Style

Style describes the character's identity and appearance across views. Complete its interview before writing the prompt. Style alignment suggestions appear in **Template Improvement**. Inspect the target field, reason, and before/after text, then apply supported changes or dismiss suggestions. Rewriting the prompt uses the saved template and accepted changes.

Use **Draft 1** for a single candidate or **Draft 4** for a batch. Compare candidates with the source image, review rankings with **Luna Review**, and select the best candidate. Lock Style privately when it is ready. This lock becomes the reference for official views; it is not published to Inventory.

For feedback about a rendered candidate, open its review and choose **Interview this candidate**. Add specific feedback and submit only after checking the feedback text. Review the proposal before applying it, then use **Write Prompt** and verify the updated prompt before rendering again.

## Create official views

After Style is locked, use the **View** control to open each requested view. Each board uses the locked Style image as its design reference. Views can be made independently; complete only the ones needed for the project.

Write and inspect the prompt, choose the desired render quality, and use the shared Render Controls to generate candidates. Compare the candidates against the Style reference and the view's intended orientation. Select and lock an acceptable result to publish that official view. Published assets appear in Image Inventory and remain there if the workspace is later deleted.

The official views are Front, Front Left 3/4, Front Right 3/4, Left Profile, and Right Profile. A Style lock is required before official views can render. Use the blocked-view link to return to Style when the lock is missing.

## Rename, delete, and restart

From the Minor Characters list, choose **Rename** and enter the replacement name. Names are unique within the selected universe.

To remove a workspace, choose **Delete** and inspect the protected-effects dialog. It lists candidate images and locks affected by deletion. Approve the listed effects explicitly, then choose **Delete workspace**. Cancel if the list is unexpected or you want to keep the workspace. Active work must finish before deletion. Deletion removes the workspace and its private state while preserving published Inventory images and their references.

To restart a test case, use the dashboard's **Reset existing Zet outputs?** flow. The tester finds the exact case workspace, opens this confirmation dialog, approves its listed effects, deletes the workspace, verifies it is gone, and then starts again. Do not delete a similarly named workspace.

## Troubleshooting

- **Style is not locked:** complete or review Style, choose an acceptable candidate, and lock it before opening an official view.
- **Prompt is stale:** after applying a suggestion, run **Write Prompt** and verify the prompt before rendering.
- **A suggestion is pending:** resolve it by applying supported changes or dismissing it before starting another review.
- **A job is active:** wait for it to complete or reach a terminal failure before retrying or deleting the workspace.
- **The expected source is missing:** add it to Image Inventory in the correct universe, verify the image, and create or bind the workspace to that exact item.

For automated exercises, see the [Zet Tester minor-character cases](../Zet_Tester/cases/minor-character.template.md) when the Tester checkout is next to Zet, and its [Tester README](../Zet_Tester/README.md).
