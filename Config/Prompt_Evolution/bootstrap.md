Image 1 is the sole source of truth. Extract only visible character identity and costume traits for a reusable Stable Diffusion prompt core.

Exclude pose, expression, action, composition, framing, background, quality tags, and art style. Use short atomic terms. A term must describe one coherent visible trait and must not contain a comma.

Return JSON only:
{"positive_terms":["visible identity or costume trait"],"negative_terms":["concrete identity or costume failure to exclude"]}
