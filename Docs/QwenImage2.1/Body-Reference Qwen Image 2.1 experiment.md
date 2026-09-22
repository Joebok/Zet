# Body-Reference Qwen Image 2.1 experiment

## Summary

Build a Body-Reference experiment inside Zet, separate from the canonical asset pipeline. Generate text-first Qwen candidates in batches, analyze **every image** with both the local vision model and GPT-5.6 Luna High, then present the results for human culling and selection. Keep the existing Body-Reference prompt and manual ChatGPT workflow intact.

The first live run targets **one character and one view**. The main goal is to measure whether AI culling misses images a human considers usable.

## Discrete work units

Complete these in order with one agent. Units 1–7 are bounded implementation tasks suitable for GPT-5.6 Luna High; unit 8 requires human image judgments.

1. **Experiment records and source snapshot.** Add a focused service that validates a selected Body-Reference asset and compiles its current prompt artifacts into `Zet_Library/Experiments/Character-Pipeline`. Store an immutable run specification and separate mutable candidate records: source hashes, semantic facts, manual and Qwen prompts, workflow settings, seeds, images, analyses, and decisions. **Done when:** changing pipeline data after run creation cannot change that run’s recorded inputs, and no canonical asset or pipeline state changes.

2. **Qwen Body-Reference projection and workflow.** Derive a concise natural-language Qwen prompt from the same compiled Body-Reference facts, preserving the current prompt’s successful requirements: full body, exact view, neutral stance, technical fitment clothing, neutral mannequin head, and plain background. Add a dedicated text-to-image compiler to the ComfyUI registry, with no rendered-image inputs. Default to the existing Qwen 2.1 model settings and a portrait 832×1216 canvas; freeze the effective workflow for each run. **Done when:** a fixture compiles to a valid text-first graph and missing ComfyUI nodes or model files produce clear preflight errors.

3. **Durable batch generation.** Add preview and execution for fixed-seed batches of 4, 8, 16, or 32 images, defaulting to 16. Queue one ComfyUI render at a time through Zet’s existing AI Proxy path; save each candidate and its exact workflow under a stable ID. Support stop, resume, and explicit retry without duplicating completed submissions. **Done when:** restart, timeout, and one failed render preserve the other candidates and their provenance.

4. **Body-Reference rubric and local review.** Create a dedicated rubric for visible body facts, view and head alignment, pose, proportions, anatomy, fitment shell, crop, background, and unwanted props or costume. Avoid face and hair identity gates, since the required head is a neutral mannequin. Queue one structured `image-analysis` review per completed image through AI Proxy, recording criterion verdicts, evidence, uncertainty, model runtime details, and input hashes. **Done when:** every generated image has a valid local result or an explicit retryable analysis failure.

5. **Luna image review adapter.** Add a Zet-owned, read-only `codex exec` adapter following the sibling `Zet_Kanban` authentication and environment pattern. Invoke `gpt-5.6-luna` at high reasoning with the candidate attached via `--image`, the same rubric, and `--output-schema`; do not show it the local verdict. Store the CLI version, model ID, prompt and image hashes, output, elapsed time, and error state. **Done when:** one invocation yields validated structured findings, and missing login, malformed output, or interruption leaves the candidate pending and safely retryable. Official OpenAI documentation supports [schema-constrained Codex output](https://learn.chatgpt.com/docs/non-interactive-mode) and [Luna image input with high reasoning](https://developers.openai.com/api/docs/models/gpt-5.6-luna).

6. **Culling, decisions, and lineage.** Compute a reversible disposition only after both valid analyses: **joint pass → main shortlist; joint fail → visible culled bucket; disagreement or uncertainty → human triage**. Keep human labels and overrides separate from model findings. Allow a human to lock one reviewed Qwen candidate as the Body-Reference anchor for later stages; never promote it to canonical Assets. **Done when:** stale analyses, model failures, and unreviewed candidates cannot become anchors.

7. **Focused dashboard page.** Add backend routes under `/api/character-experiments/body-reference` for preview, run creation and status, paginated candidates, stop/resume/retry, human review, and anchor selection. Add a gallery with the three AI buckets, image zoom, both reports, prompt and settings inspection, human labels, and an optional existing manual image for context. **Done when:** a reviewer can inspect and override any culled image without using the canonical asset review actions.

8. **Blind pilot and calibration.** Generate 16 images for one character/view. Have a human label **all 16 without seeing AI dispositions**, then report human-kept yield, joint-pass precision, missed usable images in the joint-fail bucket, disagreements, failure categories, and generation/review time. If any usable image was jointly culled, revise the rubric or review prompts and repeat a 16-image pilot before expanding to 32. **Done when:** all pilot images have two valid analyses and human labels, the culling report is reproducible, and a 32-image confirmation run has no human-kept image in the joint-fail bucket.

## Validation and assumptions

Each implementation unit includes focused service or route tests; run ComfyUI and Luna smoke checks before the live batch. Test source snapshot stability, no-image Qwen compilation, restart recovery, hash-based analysis invalidation, malformed model responses, disposition disagreements, and anchor guards.

`_Kanban` is interpreted as the sibling `C:\Users\Joe\Projects\Zet_Kanban`; Zet will use its invocation pattern without depending on that project at runtime. The manual ChatGPT branch remains available for comparison, while automated manual image generation and later Qwen pipeline stages are outside this Body-Reference increment.
