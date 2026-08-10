Image 1 is the reference and sole source of visual truth. Image 2 is candidate seed {{SEED}}.

Compare only visible character identity and costume. Ignore pose, expression, composition, framing, lighting, background, attractiveness, and general image quality.

For every category return:
- score: 0 to 10 visual similarity;
- observation: one concise visible discrepancy, or an empty string when effectively exact;
- correction: one concrete instruction telling a prompt editor what the next render must change while preserving matching traits, or an empty string when no change is needed;
- confidence: 0 to 1.

The corrected prompt will be used by txt2img and will not receive either image. Every correction must therefore be a self-contained description of the desired visible result. Never use comparative or image-dependent wording such as "match the reference," "like Image 1," "preserve the candidate," "this garment," or "the source."

Categories: face_shape, eyes, hair, species_markers, body_proportions, silhouette_layering, garment_pieces, colors, accessories_footwear.

Within the eyes category, judge and describe iris color separately from sclera color. Never apply the iris color to the whole eye; if either color needs correction, name the iris and sclera explicitly in the observation and correction.

Judge base hair color independently of highlights, shadows, and reflected light. Judge each category independently. Five is the midpoint. A significant mismatch requires 7 or lower. Do not aggregate scores.

Return exactly one JSON object and no surrounding prose:
{"strategy_version":2,"category_feedback":{"face_shape":{"score":0,"observation":"","correction":"","confidence":0},"eyes":{"score":0,"observation":"","correction":"","confidence":0},"hair":{"score":0,"observation":"","correction":"","confidence":0},"species_markers":{"score":0,"observation":"","correction":"","confidence":0},"body_proportions":{"score":0,"observation":"","correction":"","confidence":0},"silhouette_layering":{"score":0,"observation":"","correction":"","confidence":0},"garment_pieces":{"score":0,"observation":"","correction":"","confidence":0},"colors":{"score":0,"observation":"","correction":"","confidence":0},"accessories_footwear":{"score":0,"observation":"","correction":"","confidence":0}}}
