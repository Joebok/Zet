# Candidate draft upscale

Status: completed

## Goal

Re-render a completed, unlocked Draft through Qwen Image 2.1 using its image as the only input. Replace it in its slot when the Final result arrives and keep its original prompt.

## Current behavior and impact

Character Asset Containers and Narrative share `candidate_board.js`. Their services own slot and attempt state and use `ImageProductionService` for AI_Proxy transport. Final sizing is configured in `image_sizing_service.py`. The code map, Local Characters, Narrative, and shared queue documentation cover these boundaries.

## Work packets

1. **Frozen edit request**. Add shared preparation in `image_render_request.py` and reuse the Qwen edit profile, captured inputs, and Final size validation. Verify the draft is the sole reference and the output is larger at the same ratio.
2. **Character and Narrative settlement**. Reuse each service's existing dispatch and polling. Keep draft bytes available until successful settlement, fence duplicate attempts and locked images, and keep the original prompt and captured prompt inputs. Verify success, failure, and retained source bytes with disposable service checks.
3. **Board controls**. Add the accessible up arrow and queued feedback in the shared board and its controllers. Reuse existing polling. Verify with JavaScript syntax checks and the approved isolated E2E suite.

## Constraints

Respect current slot ownership, attempt fences, Inventory publication, Narrative lettering, and source preservation. AI_Proxy queue metadata follows the existing lifecycle. No live model check is in scope.

## Final results

All three packets are complete. The shared builder selects a larger, exactly proportional size on the renderer's grid near the configured Final pixel target. The two services retain the Draft while AI_Proxy works and swap in the validated Final in the same slot. The candidate identity, prompt, and captured generation inputs survive the swap. The existing queue lifecycle retains transport history.

Narrative publication keys include the image digest so a Final publication and any earlier Draft publication have independent assets. Assembly lettering placements survive and require a new confirmation before selection.

- `npm run test:e2e` passed all four approved fast scenarios.
- Disposable service checks compiled the real AI_Proxy requests in an isolated fixture and delivered prepared answers. They verified the exact edit prompt and draft bytes, one reference, exact output dimensions, Character lock protection and failed-render recovery, Narrative wrong-size rejection, same-slot Final replacement, original prompt whitespace, and independent Narrative Inventory publication.
- Disposable JavaScript checks covered syntax, card and review eligibility, and the accessible up-arrow glyph.
- `git diff --check` passed. Live render quality remains unverified.
