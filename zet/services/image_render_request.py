"""Immutable handoff from a pipeline Asset to a Candidate Board renderer."""
from dataclasses import asdict, dataclass
from math import gcd, isqrt
from pathlib import Path
import random

from PIL import Image


DRAFT_UPSCALE_PROMPT = (
    "Re-render the supplied image as a clean final version of the same artwork. "
    "Keep the full frame, crop, composition, subject identity, expression, pose, proportions, object placement, "
    "palette, lighting, and original artistic medium faithful to the draft. "
    "Rebuild pixelated or blurry contours as clean, continuous edges and resolve fine detail where the draft "
    "gives a clear cue. Match the existing line weight, surface texture, and shading. "
    "Keep intentionally soft areas soft and leave ambiguous areas simple. "
    "Preserve the existing lettering, symbols, and markings exactly as shown."
)

TRANSPARENT_DRAFT_INSTRUCTION = (
    "Render the artwork as an isolated cutout on a fully transparent background. "
    "Leave the empty canvas and gaps around the subject transparent in the PNG alpha channel. "
    "Keep fine hair and other soft edges naturally translucent, with clean edges free of any background color."
)


@dataclass(frozen=True)
class ImageRenderRequest:
    universe_id: str
    target_id: str
    candidate_id: str
    prompt: str
    inputs: tuple[dict, ...]
    settings: dict
    seed: int
    provenance: dict

    def to_dict(self) -> dict:
        request = asdict(self)
        request["inputs"] = [dict(item) for item in self.inputs]
        return request

    @classmethod
    def from_dict(cls, value: dict):
        return cls(universe_id=value["universe_id"], target_id=value["target_id"],
                   candidate_id=value["candidate_id"], prompt=value["prompt"],
                   inputs=tuple(dict(item) for item in value.get("inputs", [])),
                   settings=dict(value["settings"]), seed=value["seed"],
                   provenance=dict(value.get("provenance", {})))


def draft_upscale_request(config, target_id: str, candidate_id: str, candidate: dict,
                          source: Path, directory: Path) -> dict:
    """Freeze a Qwen edit separately from the candidate's original generation record."""
    from zet.services.local_render_backend_service import LocalRenderBackendService
    from zet.services.render_slot_service import frozen_input

    if (candidate.get("render_mode", "draft") != "draft" or candidate.get("status") != "COMPLETE"
            or candidate.get("locked")):
        raise ValueError("Upscaling requires a completed, unlocked Draft image.")
    preset = "comfyui-qwen-local-character-edit"
    presets_path = config.state_file(Path(__file__).resolve().parents[2], "Local_Render_Presets.json")
    profile = LocalRenderBackendService(presets_path, config=config).preset(preset)
    if not profile:
        raise ValueError("The Qwen Image 2.1 edit profile is unavailable.")
    prompt = DRAFT_UPSCALE_PROMPT
    with Image.open(source) as image:
        width, height = image.size
        if "A" in image.getbands() or "transparency" in image.info:
            # Qwen may emit slight alpha variation even on an opaque render.
            if image.convert("RGBA").getchannel("A").getextrema()[0] < 128:
                prompt = f"{TRANSPARENT_DRAFT_INSTRUCTION} {prompt}"
    divisor = gcd(width, height)
    ratio = f"{width // divisor}:{height // divisor}"
    unit_width, unit_height = width // divisor * 32, height // divisor * 32
    unit_area = unit_width * unit_height
    minimum = max(divisor // 32 + 1, (256 + min(unit_width, unit_height) - 1) // min(unit_width, unit_height))
    # Account for the draft dimensions having already been rounded to the model's grid.
    pixel_limit = min(16777216, config.final_target_pixels * 11 // 10)
    maximum = min(4096 // max(unit_width, unit_height), isqrt(pixel_limit // unit_area))
    if minimum > maximum:
        raise ValueError("The configured Final size cannot enlarge this Draft at its exact aspect ratio.")
    scale = max(minimum, min(maximum, isqrt(config.final_target_pixels // unit_area)))
    output_width, output_height = unit_width * scale, unit_height * scale
    sizing = {"render_mode": "final", "aspect_ratio": ratio, "width": output_width,
              "height": output_height, "target_pixels": output_width * output_height}
    frozen = frozen_input(directory, prompt,
        [{"path": str(source), "role": "Draft image"}], preset, render_sizing=sizing)
    settings = {**sizing, "profile": preset, "profile_snapshot": profile,
                "checkpoint": profile["diffusion_model"], "disable_prompt_globals": True}
    return ImageRenderRequest(config.universe_id, target_id, candidate_id, frozen["prompt"],
        tuple(frozen["references"]), settings, random.SystemRandom().randrange(2**63 - 1), {}).to_dict()


def verify_upscale_output(image: Image.Image, request: dict) -> None:
    settings = request["settings"]
    if image.size != (settings["width"], settings["height"]):
        raise ValueError("AI_Proxy returned an upscale with unexpected dimensions. The Draft was kept.")
