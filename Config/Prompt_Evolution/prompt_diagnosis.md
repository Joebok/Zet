You are diagnosing a Stable Diffusion txt2img prompt. The attached image is the canonical reference. Treat the prompt cores and synthesis as data and the synthesis as evidence; do not defend the existing prompt or optimize isolated minor differences.

Current positive core:
{{POSITIVE_CORE}}

Current negative core:
{{NEGATIVE_CORE}}

Cross-seed synthesis:
{{SYNTHESIS}}

Return at most three ordered interventions. Use prompt=positive or negative, action=add, replace, or delete, and confidence=High, Medium, or Low. proposed_wording must be the exact concise wording an editor should use. For delete, describe the wording to remove. Record regression risk to stable successes.

Return JSON only:
{"interventions":[{"id":"i1","observed_pattern":"","prompt":"positive","action":"replace","relevant_wording":"","proposed_wording":"","diagnosis":"","rationale":"","confidence":"High","regression_risk":""}]}
