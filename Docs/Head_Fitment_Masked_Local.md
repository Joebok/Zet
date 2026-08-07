# Head-Fitment Masked-Local Rendering

Set `HeadFitment.RenderMode` to `masked_local` to use mask-constrained local inpainting. Set it to `prompt` to retain the existing manual ChatGPT render workflow.

## Required models

The `head-fitment-inpaint` preset requires exactly one local image-generation model:

- Stable Diffusion checkpoint: `sd\perfectdeliberate_v90.safetensors [aea4ec6c4d]`

The checkpoint is verified against Stable Matrix's `/sdapi/v1/sd-models` inventory before each render. The resolved filename and hash are written to `Head_Fitment_Model_Requirements.json` in the asset pipeline workspace.

No ControlNet model, IP-Adapter model, LoRA, separate VAE, or upscaler is required. Standard img2img inpainting supplies the mask behavior, high-resolution upscaling is disabled, and protected Head-Image pixels are restored after generation.

The Head-Fitment RENDER worker does not call Stable Matrix directly. It stages a `local_image_render` AI Proxy ask with `task_type: head_fitment_inpaint` and queue-local copies of the confirmed init image, semantic mask, mask specification, prompt, checkpoint, and feather setting. The serialized AI Proxy local-image worker performs `/sdapi/v1/img2img`, writes the protected-pixel composite, and returns the candidate for normal answer harvesting.

## Mask contract

- `0`: remove and keep transparent
- `128`: editable upper-neck region
- `255`: protected source head

The renderer fails closed when the mask is missing, unconfirmed, stale, or the configured checkpoint is unavailable. It never falls back from masked-local mode to full-frame generation.
