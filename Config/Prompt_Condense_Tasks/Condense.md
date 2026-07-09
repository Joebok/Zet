# Zet Prompt Condense Task

You are preparing a concise image-generation prompt for Stable Matrix.

Condense the source prompt into short, direct visual instructions.

Preserve:
- requested camera/view
- full-body framing
- pose
- the required subject identity
- specified clothing
- background
- lighting
- negative constraints

Remove:
- explanatory text
- section labels
- repetition
- implementation commentary

Do not add new costume details, props, weapons, jewelry, scene story, or extra character features.

Return only the condensed render prompt text. Do not include Markdown headings or commentary.

AssetID: {{ASSET_ID}}
Character: {{CHARACTER}}
Phase: {{PHASE}}
Pipeline: {{PIPELINE}}
BodyView: {{BODY_VIEW}}

Source Final_Image_Prompt.md:
-----
{{FINAL_IMAGE_PROMPT}}
-----
