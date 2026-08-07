# Head-Fitment Masked-Local Rendering

Set `HeadFitment.RenderMode` to `masked_local` to use mask-constrained local inpainting. Set it to `prompt` to retain the existing manual ChatGPT render workflow.

## Required models

All files use the shared model root `D:\Comfy-Desktop\ComfyUI-Shared\models`:

- BiRefNet: `background_removal\birefnet.safetensors`, SHA-256 `9ab37426bf4de0567af6b5d21b16151357149139362e6e8992021b8ce356a154`, [download](https://huggingface.co/Comfy-Org/BiRefNet/resolve/main/background_removal/birefnet.safetensors?download=true).
- MediaPipe face: `detection\mediapipe_face_fp32.safetensors`, SHA-256 `a98c4806081d40eba35102a0f6dc0000c2e1388b72cf24e691703d0605bd888a`, [download](https://huggingface.co/Comfy-Org/mediapipe/resolve/main/detection/mediapipe_face_fp32.safetensors?download=true).
- SAM 3.1 multiplex: `checkpoints\sam3.1_multiplex_fp16.safetensors`, SHA-256 `9ba99c92703c2e8b4f47de2d34a539bb8e18923049e238b780d70dbe6368eb03`, [download](https://huggingface.co/Comfy-Org/sam3.1/resolve/main/checkpoints/sam3.1_multiplex_fp16.safetensors?download=true).
- PerfectDeliberate v9: `checkpoints\perfectdeliberate_v90.safetensors`, SHA-256 `aea4ec6c4d248fb9cdc3209bcbf3fccb05acb1a2a901d3f1e805e39810ed0b09`, [recovery download](https://civitai.com/api/download/models/2805032?type=Model&format=SafeTensor).

The checkpoint and required core nodes are verified against ComfyUI's `/object_info` inventory before each render. Requirements are written to `Head_Fitment_Model_Requirements.json` in the asset pipeline workspace.

No ControlNet model, IP-Adapter model, LoRA, separate VAE, or upscaler is required. ComfyUI core `VAEEncodeForInpaint` supplies the mask behavior, and protected Head-Image pixels are restored after generation.

The Head-Fitment RENDER worker stages a `local_image_render` AI Proxy ask with `task_type: head_fitment_inpaint` and queue-local copies of the confirmed init image, semantic mask, mask specification, prompt, checkpoint, and feather setting. Only the serialized AI Proxy local-image worker contacts ComfyUI, writes the protected-pixel composite, and returns the candidate for normal answer harvesting.

## Mask contract

- `0`: remove and keep transparent
- `128`: editable upper-neck region
- `255`: protected source head

The renderer fails closed when the mask is missing, unconfirmed, stale, or the configured checkpoint is unavailable. It never falls back from masked-local mode to full-frame generation.

## Automated mask generation

With `MaskGeneration = "comfyui_ensemble"`, the MANIFEST worker queues a `local_image_render` AI Proxy task instead of creating a synchronous heuristic mask. The proxy worker alone contacts ComfyUI and validates the configured BiRefNet, MediaPipe, and SAM 3.1 nodes and models before running the workflow. Missing or invalid output installs nothing.

The workflow retains all raw masks, the selected semantic mask, overlay, workflow JSON, score report, proxy metadata, and model requirements under `Head_Fitment_Mask_Diagnostics`. Masks passing every hard gate and `MaskAutoConfirmThreshold` are confirmed automatically; other valid candidates remain editable and require manual confirmation. Results are discarded if either source image changed or a confirmed current mask appeared while the task was running.
