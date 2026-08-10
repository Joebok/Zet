Image 1 is the sole reference. Image 2 is the rendered candidate to improve.

Rewrite the reusable Stable Diffusion prompt cores so the next render better matches Image 1. Use the evaluation feedback, the current prompts, and both images as evidence. Preserve visible identity and costume traits that already match, but do not limit yourself to minimal edits when a broader rewrite would produce a better image.

The returned strings will be used as the positive and negative prompt cores in an Automatic1111 txt2img API call. Write normal Automatic1111-compatible, comma-delimited prompt text. Do not include pose, expression, action, framing, background, quality, or art-style terms.

Evaluation feedback:
{{EVALUATIONS}}

Priority corrections:
{{CORRECTIONS}}

Current positive prompt core:
{{POSITIVE_PROMPT}}

Current negative prompt core:
{{NEGATIVE_PROMPT}}

Previously rejected prompt changes to avoid repeating:
{{REJECTED_MUTATIONS}}

Within the eyes category, describe iris color and sclera color separately. Never apply the iris color to the whole eye.

Return JSON only with `positive_core` and `negative_core` containing the complete revised comma-delimited Automatic1111 prompt cores. The positive core must not be empty. The negative core may be empty.

{{OUTPUT_SCHEMA}}
