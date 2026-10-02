"""The supported production local renderer; historical profiles remain readable."""
from pathlib import Path
import json


SCENE_PROFILE = "comfyui-qwen-image-2-1-scene"


def require_qwen_profile(project_root: str | Path, name: str, backend: str = "comfyui", checkpoint: str = "", *, presets_path: Path | None = None) -> dict:
    path = presets_path or Path(project_root) / "Config" / "Local_Render_Presets.json"
    profiles = json.loads(path.read_text(encoding="utf-8"))
    profile = profiles.get(name)
    if backend != "comfyui" or not isinstance(profile, dict) or profile.get("backend") != "comfyui" or profile.get("model_family") != "qwen-image-2.1":
        raise ValueError("Local rendering supports only ComfyUI with Qwen Image 2.1. Choose a Qwen Image 2.1 profile.")
    models = {item.get("diffusion_model") for item in profiles.values() if isinstance(item, dict)
              and item.get("backend") == "comfyui" and item.get("model_family") == "qwen-image-2.1"}
    if checkpoint and checkpoint not in models:
        raise ValueError("Local rendering supports only registered Qwen Image 2.1 diffusion models.")
    return profile


def configured_qwen_profile(name: str) -> str:
    """Normalize obsolete saved configuration, without reinterpreting render jobs."""
    try:
        require_qwen_profile(Path(__file__).resolve().parents[2], name)
    except (ValueError, OSError):
        return SCENE_PROFILE
    return name


def configured_qwen_checkpoint(name: str) -> str:
    try:
        require_qwen_profile(Path(__file__).resolve().parents[2], SCENE_PROFILE, checkpoint=name)
    except (ValueError, OSError):
        return ""
    return name
