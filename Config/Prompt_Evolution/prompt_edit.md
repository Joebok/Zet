Apply only the supplied high-confidence interventions to the reusable Stable Diffusion prompt cores. Make the minimum changes necessary, preserve stable successes, use concise comma-delimited wording, and do not add pose, expression, framing, background, quality, or style terms.

Positive core:
{{POSITIVE_CORE}}

Negative core:
{{NEGATIVE_CORE}}

Eligible interventions:
{{INTERVENTIONS}}

Protected stable successes:
{{STABLE_SUCCESSES}}

Return complete updated cores and one change-log item per applied intervention. Return JSON only:
{"positive_core":"","negative_core":"","changes":[{"intervention_id":"i1","old":"","new":"","reason":""}]}
