Analyze independent visual reports and regression checks from candidates generated with one prompt and different seeds. Do not score candidates, reinterpret the images, diagnose prompt wording, or propose edits.

Classify deviations by recurrence. Each finding must identify affected seeds and whether one or both critics reported it. Treat failed regression checks as supporting evidence, never as automatic priorities. Preserve stable successes. Return at most three prompt-level priorities.

Evidence:
{{BATCH_EVIDENCE}}

Deviation items use {"finding":"","seeds":[1],"observer_agreement":"single|dual"}. Stable successes and cross-feature patterns are concise strings. Priority items use {"problem":"","evidence":"","seeds":[1],"observer_agreement":"single|dual"}.

Return JSON only:
{"recurrent_deviations":[],"intermittent_deviations":[],"isolated_deviations":[],"stable_successes":[],"cross_feature_patterns":[],"next_round_priorities":[]}
