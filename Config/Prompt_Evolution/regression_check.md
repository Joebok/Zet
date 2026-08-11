Image 1 is the canonical reference. Image 2 is candidate seed {{SEED}}.

Evaluate each desired-condition check independently from visible evidence. The checks are JSON objects; copy each `id` value exactly, without numbering, brackets, prefixes, or other changes:
{{CHECKS}}

Return exactly one result for every supplied ID. Return pass=true when the desired condition is clearly satisfied, pass=false when it is clearly violated, and pass=null when visibility is insufficient. Do not score, aggregate, or suggest prompt changes.

Return JSON only:
{"checks":[{"id":"configured id","pass":true,"confidence":0,"evidence":"concise visible evidence"}]}
