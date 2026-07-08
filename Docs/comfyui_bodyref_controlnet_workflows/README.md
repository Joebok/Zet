# ComfyUI body-reference ControlNet workflows for SD 1.5

These are importable ComfyUI workflow JSON templates for body-reference image generation using a mannequin/reference image to control pose and camera view.

## Files

1. `BodyRef_SD15_DWPose_ControlNet.json`
   - Best first choice when the mannequin is a clear articulated human/artist mannequin.
   - Uses `DWPreprocessor` + `control_v11p_sd15_openpose`.

2. `BodyRef_SD15_MiDaSDepth_ControlNet.json`
   - Fallback for a smooth 3D mannequin, clay model, or featureless gray mannequin where pose keypoints are unreliable.
   - Uses `MiDaS-DepthMapPreprocessor` + `control_v11f1p_sd15_depth`.

3. `BodyRef_SD15_Canny_ControlNet.json`
   - Fallback for a clean line-art/outline mannequin.
   - Uses `CannyEdgePreprocessor` + `control_v11p_sd15_canny`.

## Required local pieces

Install these through ComfyUI Manager or manually:
- ComfyUI's ControlNet Auxiliary Preprocessors / `comfyui_controlnet_aux`
- SD 1.5 checkpoint in `ComfyUI/models/checkpoints`
- Matching SD 1.5 ControlNet models in `ComfyUI/models/controlnet`

Typical model names vary by install. After importing, select your actual local model filenames in:
- `Load SD 1.5 Checkpoint`
- `Load Matching SD1.5 ControlNet`

## Suggested mannequin image style

Use:
- full body, head-to-feet visible
- exact target camera view: FRONT, FRONT_LEFT_3_4, LEFT_PROFILE, etc.
- neutral standing pose
- high-contrast light mannequin on a black or very dark plain background
- no props, no scene, no perspective drama
- 512x768 or 768x1152 portrait framing

For DWPose/OpenPose, an articulated wooden or ball-joint mannequin is better than a smooth featureless body because visible joints help pose detection.

For depth, a smooth matte gray 3D mannequin is fine and may preserve body volume better than pose skeletons.

## First settings to adjust

- `Positive Prompt`: paste your final body-reference prompt.
- `Negative Prompt`: add failure modes you see locally.
- `Load Mannequin / Pose Reference`: choose the reference image.
- `Apply ControlNet Advanced`:
  - strength: start around `0.75–0.85`
  - start_percent: `0.0`
  - end_percent: `0.75–0.90`
- `Empty Latent Image`: start with `512 x 768` for 8GB VRAM.

## Practical notes for Tsaeytte body-reference stages

For technical body-reference images, front-load the prompt with view and framing constraints before character details:

`FULL-BODY TECHNICAL BODY-REFERENCE IMAGE, FRONT_LEFT_3_4 view, entire body visible from top of head to soles of feet, feet fully visible, neutral standing pose, plain studio background...`

Then add the character/body/fitment-shell details after those constraints.

Do not rely on the text prompt alone for view. Use a mannequin image already posed in the exact desired view.
