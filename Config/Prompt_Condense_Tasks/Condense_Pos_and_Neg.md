# Zet Prompt Condense Task

You are preparing Stable Diffusion WebUI Forge - Neo prompt text from a fully described image-generation prompt.

Your task is to condense the source prompt into two fields:

* `prompt`: short, direct positive visual instructions describing what should appear in the image.
* `negative`: short, direct negative prompt terms describing what must be avoided.

The output will be parsed by a Python script, so the response format must be exact.

## Condensing Rules

Condense the source prompt into compact Stable Diffusion-style prompt language.

Preserve all essential visual requirements from the source prompt, especially:

* requested camera/view
* full-body framing
* pose
* required subject identity
* specified clothing
* background
* lighting
* art style
* important anatomy or orientation constraints
* required expression or mood
* required props or equipment
* all negative constraints

Move anything that describes what should appear into `prompt`.

Move anything that describes what should not appear, must be avoided, is forbidden, or is a quality/anatomy failure into `negative`.

Do not add new costume details, props, weapons, jewelry, scene story, background elements, body features, or character features.

Do not add new style terms unless they are already present in the source prompt.

Remove:

* explanatory text
* section labels from the source prompt
* repetition
* implementation commentary
* pipeline metadata that does not affect the rendered image

## Required Output Format

Return only the following two fields and nothing else.

Do not use Markdown headings.

Do not wrap the response in a code block.

Do not include commentary before or after the fields.

Use this exact field format:

prompt: <condensed positive Stable Diffusion prompt>

negative: <condensed negative Stable Diffusion prompt>

## Metadata

AssetID: {{ASSET_ID}}
Character: {{CHARACTER}}
Phase: {{PHASE}}
Pipeline: {{PIPELINE}}
BodyView: {{BODY_VIEW}}

## Source Final_Image_Prompt.md

---

## {{FINAL_IMAGE_PROMPT}}
