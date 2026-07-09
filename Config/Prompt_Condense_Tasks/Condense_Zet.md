# Zet Prompt Condense Task

You are preparing Stable Diffusion WebUI Forge / SD 1.5 prompt text from a fully described image-generation prompt.

Your task is to condense the source prompt into two single-line fields:

prompt: compact positive Stable Diffusion prompt terms describing what should appear.
negative: compact negative Stable Diffusion prompt terms describing what must be avoided.

The output will be parsed by a Python script, so the response format must be exact.

## Condensing Rules

Condense the source prompt into compact Stable Diffusion-style prompt language.

Preserve all essential visual requirements from the source prompt, especially:

* camera/view
* full-body, half-body, portrait, or crop framing
* pose
* subject count and identity
* age category when visually relevant
* species/race when visually relevant
* clothing
* background
* lighting
* art style
* anatomy/orientation constraints
* expression or mood
* props or equipment
* all negative constraints

Move anything that describes what should appear into `prompt`.

Move anything that describes what should not appear, must be avoided, is forbidden, incorrect, or a quality/anatomy failure into `negative`.

You may add common Stable Diffusion tags only when they directly restate information clearly present in the source prompt.

Allowed common tags include:
solo, 1girl, 1boy, 1woman, 1man, multiple girls, multiple boys, full body, upper body, portrait, looking at viewer, standing, sitting, walking, front view, side view, rear view, three-quarter view, indoors, outdoors, simple background, detailed background.

Do not add new costume details, props, weapons, jewelry, scene story, background elements, body features, character features, or style terms not supported by the source prompt.

Do not add generic quality booster terms unless they are present in the source prompt.

Remove:

* explanatory text
* section labels from the source prompt
* repetition
* implementation commentary
* pipeline metadata that does not affect the rendered image

If the source prompt contains no negative constraints, use this minimal default negative prompt:

negative: low quality, blurry, bad anatomy, bad hands, extra fingers, missing fingers, extra limbs, malformed limbs, distorted face, wrong view, cropped, out of frame, text, watermark

## Required Output Format

Return only the following two fields and nothing else.

Do not use Markdown headings.
Do not wrap the response in a code block.
Do not include commentary before or after the fields.
Each field must be exactly one line.

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

{{FINAL_IMAGE_PROMPT}}