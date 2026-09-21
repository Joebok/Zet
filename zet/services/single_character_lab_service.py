from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import random
import re
import shutil
import statistics
import time
from typing import Any

from PIL import Image, ImageOps

from zet.models.ai_proxy import AI_PROXY_PROTOCOL_VERSION
from zet.services.checkpoint_lab_service import CheckpointLabService
from zet.services.image_quality_review_service import ImageQualityReviewError, ImageQualityReviewService
from zet.services.local_render_backend_service import LocalRenderBackendService
from zet.services.workflow_storage import supersede_task

DEFAULT_PROFILE = "image-recipe-lab-ipadapter-controlnet-sdxl"
DEFAULT_REFERENCE_WEIGHT = 0.45
DEFAULT_POSE_WEIGHT = 0.75
MAX_CANDIDATES = 256
DEFAULT_NEGATIVE_PROMPT = (
    "worst quality, low quality, lowres, blurry, pixelated, jpeg artifacts, bad anatomy, "
    "bad proportions, malformed body, deformed hands, extra fingers, missing fingers, extra limbs, missing limbs, "
    "duplicate character, multiple people, cropped head, cropped feet, out of frame, text, caption, logo, watermark, "
    "signature, 3d render, plastic skin, chibi, super-deformed"
)


class SingleCharacterLabError(ValueError):
    pass


class SingleCharacterLabService:
    def __init__(self, app: Any, project_root: str | Path):
        self.app = app
        self.project_root = Path(project_root).resolve()
        self.runs_root = Path(app.config.base_pipeline_path).resolve() / "Single_Character_Lab"

    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat(timespec="seconds")

    @staticmethod
    def _write(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        temp.replace(path)

    @staticmethod
    def _hash(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def _extract_section(text: str, name: str) -> str:
        match = re.search(
            rf"<!-- ZET:BEGIN {re.escape(name)} -->\s*(.*?)\s*<!-- ZET:END {re.escape(name)} -->",
            text, re.DOTALL,
        )
        return match.group(1).strip() if match else ""

    @staticmethod
    def _prompt_text(value: str) -> str:
        parts = []
        for line in value.splitlines():
            line = re.sub(r"^\s*[-*]\s*", "", line).strip().replace("`", "")
            if line and not line.startswith("#") and not line.casefold().startswith("forbidden drift:"):
                parts.append(line.rstrip("."))
        return ", ".join(parts)

    @staticmethod
    def _forbidden_prompt(values: list[str]) -> str:
        parts = []
        for value in values:
            for line in value.splitlines():
                line = re.sub(r"^\s*[-*]\s*", "", line).strip().replace("`", "")
                if line.casefold().startswith("forbidden drift:"):
                    line = re.sub(r"\b(?:do not|no)\s+", "", line.split(":", 1)[1], flags=re.IGNORECASE)
                    if line.strip():
                        parts.append(line.strip().rstrip("."))
        return ", ".join(parts)

    @staticmethod
    def _fact_anchor(value: str, label: str, noun: str, weight: float) -> str:
        for line in value.splitlines():
            line = re.sub(r"^\s*[-*]\s*", "", line).strip().replace("`", "")
            if line.casefold().startswith(f"{label}:".casefold()):
                fact = re.split(r"\s+with\s+|[,;]", line.split(":", 1)[1].strip(), maxsplit=1, flags=re.IGNORECASE)[0]
                return f"({fact.rstrip('.')} {noun}:{weight:g})" if fact else ""
        return ""

    @staticmethod
    def _view_section(view: str) -> str:
        return re.sub(r"[^A-Za-z0-9]+", "_", view).strip("_").upper()

    @staticmethod
    def _modern_prompt(text: str) -> str:
        return re.sub(r"\(([^():]+):\d+(?:\.\d+)?\)", r"\1", text)

    def _asset(self, character: str, phase: str, asset_id: int):
        asset = self.app.asset(character, phase, asset_id).get()
        if asset.pipeline != "Costume-Dressing" or asset.asset_state != "LOCKED":
            raise SingleCharacterLabError("Appearance source must be a locked Costume-Dressing asset.")
        path = self.app.path_service.locked_image_path(asset).resolve()
        if not path.is_file():
            raise SingleCharacterLabError(f"Locked appearance image not found: {path}")
        return asset, path

    def appearance_options(self, character: str, phase: str) -> list[dict[str, Any]]:
        rows = []
        for asset in self.app.list_assets(character, phase):
            if asset.pipeline != "Costume-Dressing" or asset.asset_state != "LOCKED":
                continue
            path = self.app.path_service.locked_image_path(asset).resolve()
            if path.is_file():
                rows.append({"asset_id": asset.asset_id, "costume": asset.costume or "", "view": asset.body_view or "",
                             "label": f"{asset.costume or 'Costume'} · {asset.body_view or 'Unknown view'}",
                             "image_path": str(path)})
        return sorted(rows, key=lambda item: (item["costume"].casefold(), item["view"].casefold()))

    def pose_options(self, character: str, phase: str) -> list[dict[str, str]]:
        rows = self.app.story_service.image_reference_rows(
            character, "", phase, "", scope="context", include_unavailable=False,
        )
        return [{"tag": row.tag, "label": row.label, "view": row.view,
                 "image_path": str(Path(row.image_path).resolve())}
                for row in rows if row.pipeline == "Body-Reference" and row.kind == "locked-asset" and row.view]

    def _inventory(self) -> tuple[dict[str, Any], str]:
        try:
            return LocalRenderBackendService(
                self.project_root / "Config" / "Local_Render_Presets.json"
            ).comfyui_options(self.app.config.comfyui_server_url), ""
        except Exception as exc:
            return {}, str(exc)

    @staticmethod
    def _contains(values: list[str], *needles: str) -> bool:
        return any(all(needle.casefold() in value.casefold() for needle in needles) for value in values)

    def adapters(self, inventory: dict[str, Any]) -> list[dict[str, Any]]:
        nodes = set(inventory.get("node_types") or [])
        diffusion = inventory.get("diffusion_models") or []
        encoders = inventory.get("text_encoders") or []
        vaes = inventory.get("vaes") or []
        def normalized(value: str) -> str:
            return re.sub(r"[^a-z0-9]+", "", value.casefold())
        flux_models = [item for item in diffusion if all(token in normalized(item) for token in ("flux2", "klein", "4b"))]
        flux_encoders = [item for item in encoders if "qwen_3_4b" in item.casefold()]
        flux_vaes = [item for item in vaes if "flux2" in item.casefold()]
        qwen_models = [item for item in diffusion if all(token in normalized(item) for token in ("qwen", "edit", "2511"))]
        qwen_encoders = [item for item in encoders if "qwen" in item.casefold() and "qwen_3" not in item.casefold()]
        qwen_vaes = [item for item in vaes if "qwen" in item.casefold()]
        def preferred(values: list[str], *names: str) -> str:
            for name in names:
                match = next((value for value in values if value.casefold() == name.casefold()), None)
                if match:
                    return match
            return values[0] if values else ""

        flux_encoder = preferred(flux_encoders, "qwen_3_4b_fp4_flux2.safetensors", "qwen_3_4b.safetensors")
        flux_vae = preferred(flux_vaes, "flux2-vae.safetensors")
        qwen_encoder = preferred(
            qwen_encoders,
            "qwen_2.5_vl_7b_nvfp4.safetensors",
            "qwen_2.5_vl_7b_fp8_scaled.safetensors",
        )
        qwen_vae = preferred(qwen_vaes, "qwen_image_vae.safetensors")
        qualification_path = self.project_root / "Config" / "Modern_Model_Qualifications.json"
        try:
            qualifications = json.loads(qualification_path.read_text(encoding="utf-8")) if qualification_path.is_file() else {}
        except (OSError, json.JSONDecodeError):
            qualifications = {}
        sdxl_missing = sorted({"IPAdapterAdvanced", "ControlNetApplyAdvanced", "DWPreprocessor"} - nodes) if inventory else []
        flux_missing = []
        if not flux_models:
            flux_missing.append("FLUX.2 Klein 4B diffusion model")
        if not flux_encoders:
            flux_missing.append("qwen_3_4b text encoder")
        if not flux_vaes:
            flux_missing.append("FLUX.2 VAE")
        if not LocalRenderBackendService(self.project_root / "Config" / "Local_Render_Presets.json").preset(
            "image-recipe-lab-flux2-klein-4b"
        ):
            flux_missing.append("Zet FLUX.2 workflow profile")
        qwen_missing = []
        if "TextEncodeQwenImageEditPlus" not in nodes:
            qwen_missing.append("TextEncodeQwenImageEditPlus node")
        if not qwen_models:
            qwen_missing.append("Qwen-Image-Edit-2511 diffusion model")
        if not qwen_encoders:
            qwen_missing.append("Qwen Image text encoder")
        if not qwen_vaes:
            qwen_missing.append("Qwen Image VAE")
        if str((qualifications.get("qwen-image-edit-2511") or {}).get("status") or "").casefold() != "qualified":
            qwen_missing.append("completed 16 GB VRAM and throughput qualification")
        if not LocalRenderBackendService(self.project_root / "Config" / "Local_Render_Presets.json").preset(
            "image-recipe-lab-qwen-image-edit-2511"
        ):
            qwen_missing.append("Zet Qwen Image Edit workflow profile")
        return [
            {"id": "sdxl", "label": "SDXL IP-Adapter + pose ControlNet", "available": not sdxl_missing,
             "profile": DEFAULT_PROFILE, "pose_guidance": "skeletal_controlnet", "missing": sdxl_missing},
            {"id": "flux2-klein-4b", "label": "FLUX.2 Klein 4B reference generation", "available": not flux_missing,
             "profile": "image-recipe-lab-flux2-klein-4b", "pose_guidance": "reference_image", "missing": flux_missing,
             "models": flux_models, "default_model": flux_models[0] if flux_models else "",
             "text_encoder": flux_encoder, "vae": flux_vae},
            {"id": "qwen-image-edit-2511", "label": "Qwen Image Edit 2511 reference generation", "available": not qwen_missing,
             "profile": "image-recipe-lab-qwen-image-edit-2511", "pose_guidance": "reference_image", "missing": qwen_missing,
             "models": qwen_models, "default_model": qwen_models[0] if qwen_models else "",
             "text_encoder": qwen_encoder, "vae": qwen_vae},
        ]

    def options(self, character: str, phase: str) -> dict[str, Any]:
        inventory, error = self._inventory()
        checkpoints = list(inventory.get("checkpoints") or [])
        configured = str(self.app.config.comfyui_checkpoint or "").strip()
        if configured and configured not in checkpoints:
            checkpoints.insert(0, configured)
        preferred = next((item for item in checkpoints if "tastyrice" in item.casefold()), configured)
        return {"appearances": self.appearance_options(character, phase), "poses": self.pose_options(character, phase),
                "checkpoints": checkpoints, "default_checkpoint": preferred, "default_profile": DEFAULT_PROFILE,
                "default_reference_weight": DEFAULT_REFERENCE_WEIGHT, "default_pose_weight": DEFAULT_POSE_WEIGHT,
                "candidate_counts": [1, 2, 3, 4, 5, 6, 16, 64, 128], "max_candidates": MAX_CANDIDATES,
                "default_recipe_search": {"appearance_strengths": [0.35, 0.45, 0.65],
                                          "pose_strengths": [0.5, 0.75, 1.0], "seed_count": 8},
                "workflows": [
                    {"id": "combined", "label": "Appearance + skeletal pose control"},
                    {"id": "appearance_only", "label": "Appearance reference only"},
                    {"id": "pose_only", "label": "Skeletal pose control only"},
                    {"id": "low_denoise_reference", "label": "Low-denoise reference variation"},
                ],
                "samplers": inventory.get("samplers") or [], "schedulers": inventory.get("schedulers") or [],
                "adapters": self.adapters(inventory), "comfyui_inventory": inventory, "checkpoint_error": error}

    def prompt(self, character: str, phase: str, asset_id: int) -> dict[str, str]:
        asset, _ = self._asset(character, phase, asset_id)
        character_path = Path(self.app.config.base_character_path) / character / phase / "Character.md"
        costume_path = (self.app.path_service.resolve_path(asset.costume_path).resolve() if asset.costume_path
                        else self.app.path_service.costume_template_path(character, phase, asset.costume or ""))
        if not character_path.is_file() or not costume_path.is_file():
            raise SingleCharacterLabError("Character or costume source markdown is unavailable.")
        character_text, costume_text = character_path.read_text(encoding="utf-8"), costume_path.read_text(encoding="utf-8")
        view, key = asset.body_view or "Front", self._view_section(asset.body_view or "Front")
        body = self._extract_section(character_text, "BODY_DESCRIPTION_FACTS")
        head = self._extract_section(character_text, "HEAD_DESCRIPTION_FACTS")
        hair = self._extract_section(character_text, "HAIR_DESCRIPTION_FACTS")
        scene_identity = self._extract_section(character_text, "SCENE_CHARACTER_IDENTITY")
        sections = [*([scene_identity] if scene_identity else [body, head, hair]),
                    *[self._extract_section(character_text, f"{name}_DESCRIPTION_VIEW_{key}")
                      for name in ("BODY", "HEAD", "HAIR")],
                    self._extract_section(costume_text, "COSTUME_DESCRIPTION_FACTS"),
                    self._extract_section(costume_text, f"COSTUME_DESCRIPTION_VIEW_{key}"),
                    self._extract_section(costume_text, "EQUIPMENT_JEWELRY_PROPS_FACTS")]
        positive = ", ".join(["masterpiece, best quality, highly detailed",
            "solo, single character, full body, standing, centered composition, visible from head to toe", f"{view} view",
            "painterly semi-realistic fantasy illustration, anime-influenced facial proportions",
            *filter(None, [self._fact_anchor(hair, "Hair color", "hair", 1.3), self._fact_anchor(head, "Eye color", "eyes", 1.2)]),
            *[self._prompt_text(section) for section in sections if section],
            "neutral unobtrusive background, soft studio lighting, sharp focus, coherent costume design"])
        return {"positive_prompt": positive,
                "negative_prompt": ", ".join(filter(None, [DEFAULT_NEGATIVE_PROMPT, self._forbidden_prompt(sections)]))}

    def _pose_path(self, character: str, phase: str, tag: str) -> Path:
        match = next((item for item in self.pose_options(character, phase) if item["tag"] == tag), None)
        if match is None:
            raise SingleCharacterLabError("Select a current locked Body-Reference pose.")
        return Path(match["image_path"])

    def _run_path(self, run_id: str) -> Path:
        if not re.fullmatch(r"[0-9_]+", run_id):
            raise SingleCharacterLabError("Invalid Single Character Lab run ID.")
        return self.runs_root / run_id / "run.json"

    @staticmethod
    def _pad_image_to_size(source: Path, destination: Path, width: int, height: int) -> None:
        with Image.open(source) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGB")
            corners = (image.getpixel((0, 0)), image.getpixel((image.width - 1, 0)),
                       image.getpixel((0, image.height - 1)), image.getpixel((image.width - 1, image.height - 1)))
            background = tuple(sum(pixel[channel] for pixel in corners) // 4 for channel in range(3))
            resized = ImageOps.contain(image, (width, height), Image.Resampling.LANCZOS)
            canvas = Image.new("RGB", (width, height), background)
            canvas.paste(resized, ((width - resized.width) // 2, (height - resized.height) // 2))
            destination.parent.mkdir(parents=True, exist_ok=True)
            canvas.save(destination)

    @staticmethod
    def _strengths(value: Any, default: list[float]) -> list[float]:
        result = [float(item) for item in (value if isinstance(value, list) else default)]
        if not result or any(item < 0 or item > 2 for item in result):
            raise SingleCharacterLabError("Conditioning strengths must be between 0 and 2.")
        return result

    @staticmethod
    def _numbers(value: Any, default: list[float], *, minimum: float, maximum: float, label: str) -> list[float]:
        result = [float(item) for item in (value if isinstance(value, list) else default)]
        if not result or any(item < minimum or item > maximum for item in result):
            raise SingleCharacterLabError(f"{label} values must be between {minimum:g} and {maximum:g}.")
        return result

    def preview(self, payload: dict[str, Any]) -> dict[str, Any]:
        mode = str(payload.get("mode") or "seed_search")
        workflow = str(payload.get("workflow") or "combined")
        adapter_id = str(payload.get("adapter_id") or "sdxl")
        if mode not in {"seed_search", "recipe_search"}:
            raise SingleCharacterLabError("Search mode must be seed_search or recipe_search.")
        if mode == "recipe_search":
            seed_count = int(payload.get("seed_count") or 8)
            if adapter_id == "sdxl":
                appearances = self._strengths(payload.get("appearance_strengths"), [0.35, 0.45, 0.65])
                poses = self._strengths(payload.get("pose_strengths"), [0.5, 0.75, 1.0])
                steps = [float(payload.get("steps") or 28)]
                guidance = [float(payload.get("guidance") or 6)]
                denoise = [float(payload.get("denoise") or 1)]
            else:
                appearances, poses = [0.0], [0.0]
                default_steps = 4 if adapter_id == "flux2-klein-4b" else 20
                default_guidance = 3.5 if adapter_id == "flux2-klein-4b" else 1.0
                steps = self._numbers(payload.get("step_values"), [float(payload.get("steps") or default_steps)],
                                      minimum=1, maximum=10000, label="Step")
                guidance = self._numbers(payload.get("guidance_values"), [float(payload.get("guidance") or default_guidance)],
                                         minimum=0, maximum=100, label="Guidance")
                denoise = self._numbers(payload.get("denoise_values"), [float(payload.get("denoise") or 1)],
                                        minimum=0, maximum=1, label="Denoise")
        else:
            appearances = [float(payload.get("reference_weight", DEFAULT_REFERENCE_WEIGHT))]
            poses = [float(payload.get("pose_weight", DEFAULT_POSE_WEIGHT))]
            seed_count = int(payload.get("count") or 1)
            steps = [float(payload.get("steps") or (4 if adapter_id == "flux2-klein-4b" else 20 if adapter_id == "qwen-image-edit-2511" else 28))]
            guidance = [float(payload.get("guidance") or (3.5 if adapter_id == "flux2-klein-4b" else 1 if adapter_id == "qwen-image-edit-2511" else 6))]
            denoise = [float(payload.get("denoise") or 1)]
        if workflow in {"pose_only", "low_denoise_reference"}:
            appearances = [0.0]
        if workflow in {"appearance_only", "low_denoise_reference"}:
            poses = [0.0]
        if adapter_id != "sdxl":
            appearances, poses = [0.0], [0.0]
        count = len(appearances) * len(poses) * len(steps) * len(guidance) * len(denoise) * seed_count
        if seed_count < 1 or count > MAX_CANDIDATES:
            raise SingleCharacterLabError(f"Experiment must contain between 1 and {MAX_CANDIDATES} candidates.")
        return {"mode": mode, "workflow": workflow, "candidate_count": count,
                "recipe_count": len(appearances) * len(poses) * len(steps) * len(guidance) * len(denoise),
                "seed_count": seed_count, "appearance_strengths": appearances, "pose_strengths": poses,
                "step_values": steps, "guidance_values": guidance, "denoise_values": denoise}

    def create_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        character, phase = str(payload.get("character") or "").strip(), str(payload.get("phase") or "").strip()
        asset_id = int(payload.get("asset_id") or 0)
        asset, source_reference = self._asset(character, phase, asset_id)
        pose_tag = str(payload.get("pose_tag") or "")
        source_pose = self._pose_path(character, phase, pose_tag)
        plan = self.preview(payload)
        adapter_id = str(payload.get("adapter_id") or "sdxl")
        inventory, _ = self._inventory()
        adapter = next((item for item in self.adapters(inventory) if item["id"] == adapter_id), None)
        if adapter is None or not adapter["available"]:
            raise SingleCharacterLabError("Selected model adapter is unavailable: " + ", ".join((adapter or {}).get("missing") or ["unknown adapter"]))
        checkpoint = str(
            (payload.get("checkpoint") or self.app.config.comfyui_checkpoint)
            if adapter_id == "sdxl" else adapter.get("default_model") or ""
        ).strip()
        if not checkpoint:
            raise SingleCharacterLabError("Selected model file cannot be blank.")
        profile_name = str(adapter["profile"])
        workflow = str(payload.get("workflow") or "combined")
        if adapter_id == "sdxl":
            profile_name = {
                "combined": DEFAULT_PROFILE,
                "appearance_only": "image-recipe-lab-ipadapter-sdxl",
                "pose_only": "image-recipe-lab-controlnet-sdxl",
                "low_denoise_reference": "image-recipe-lab-img2img-sdxl",
            }.get(workflow, "")
            if not profile_name:
                raise SingleCharacterLabError(f"Unsupported SDXL workflow: {workflow}")
        profile = LocalRenderBackendService(self.project_root / "Config" / "Local_Render_Presets.json").preset(profile_name)
        if not profile:
            raise SingleCharacterLabError(f"Render profile is unavailable: {profile_name}")
        if adapter_id != "sdxl":
            profile = {**profile, "text_encoder": adapter["text_encoder"], "vae": adapter["vae"]}
        width, height = int(payload.get("width") or profile.get("width") or 0), int(payload.get("height") or profile.get("height") or 0)
        if width <= 0 or height <= 0:
            raise SingleCharacterLabError("Render profile must define positive width and height.")
        generated = self.prompt(character, phase, asset_id)
        positive = str(payload.get("positive_prompt") or generated["positive_prompt"]).strip()
        negative = str(payload.get("negative_prompt") or generated["negative_prompt"]).strip()
        if adapter_id != "sdxl":
            positive, negative = self._modern_prompt(positive), self._modern_prompt(negative)
        if not positive:
            raise SingleCharacterLabError("Positive prompt cannot be blank.")
        explicit_seeds = payload.get("seeds")
        if isinstance(explicit_seeds, list):
            seeds = [str(int(item)) for item in explicit_seeds]
            if len(seeds) != plan["seed_count"]:
                raise SingleCharacterLabError("Explicit seed count does not match the planned seed count.")
        else:
            seeds, generator = [], random.SystemRandom()
            while len(seeds) < plan["seed_count"]:
                seed = str(generator.randrange(0, 2**63 - 1))
                if seed not in seeds:
                    seeds.append(seed)
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        root = self._run_path(run_id).parent
        reference_path, pose_path = root / "conditioning" / "appearance.png", root / "conditioning" / "pose.png"
        self._pad_image_to_size(source_reference, reference_path, width, height)
        self._pad_image_to_size(source_pose, pose_path, width, height)
        recipes = []
        for appearance in plan["appearance_strengths"]:
            for pose in plan["pose_strengths"]:
                for steps in plan["step_values"]:
                    for guidance in plan["guidance_values"]:
                        for denoise in plan["denoise_values"]:
                            recipes.append({"recipe_id": f"r{len(recipes) + 1:03d}", "adapter_id": adapter_id,
                                "render_profile": profile_name, "checkpoint": checkpoint, "appearance_strength": appearance,
                                "pose_strength": pose, "steps": int(steps), "guidance": float(guidance),
                                "sampler": str(payload.get("sampler") or profile.get("sampler_name") or "dpmpp_2m"),
                                "scheduler": str(payload.get("scheduler") or profile.get("scheduler") or "karras"),
                                "denoise": float(denoise), "width": width, "height": height,
                                "timeout_seconds": float(profile.get("timeout_seconds") or self.app.config.comfyui_timeout_seconds)})
        candidates = []
        for recipe in recipes:
            for seed in seeds:
                cid = f"c{len(candidates) + 1:03d}"
                candidates.append({"candidate_id": cid, "recipe_id": recipe["recipe_id"], "seed": seed,
                    "status": "PENDING", "image_path": "", "ask_id": "", "error": "", "queue_seconds": None,
                    "render_seconds": None, "review": {"decision": "undecided", "shortlisted": False,
                    "failure_reasons": [], "score_overrides": {}, "notes": "", "cleanup_minutes": None}})
        rubric = self.project_root / "Config" / "Image_Quality_Rubric.json"
        spec = {"schema_version": 2, "run_id": run_id, "created_at": self._now(), "mode": plan["mode"],
            "workflow": workflow,
            "character": character, "phase": phase, "asset_id": asset_id, "costume": asset.costume or "",
            "view": asset.body_view or "", "pose_tag": pose_tag, "positive_prompt": positive, "negative_prompt": negative,
            "reference_image": str(reference_path), "pose_image": str(pose_path),
            "reference_sha256": self._hash(reference_path), "pose_sha256": self._hash(pose_path),
            "rubric": str(rubric.resolve()), "rubric_sha256": self._hash(rubric), "workflow_version": 2,
            "model_adapter": adapter, "profile_snapshot": profile, "recipes": recipes, "seeds": seeds,
            "candidate_count": len(candidates)}
        manifest = root / "experiment.json"
        self._write(manifest, {**spec, "candidate_plan": [
            {"candidate_id": item["candidate_id"], "recipe_id": item["recipe_id"], "seed": item["seed"]}
            for item in candidates
        ]})
        run = {**spec, "status": "QUEUED", "updated_at": self._now(), "stop_requested": False,
            "candidates": candidates, "completed_count": 0, "failed_count": 0, "contact_sheet": "",
            "manifest_path": str(manifest), "error": "", "checkpoint": checkpoint, "render_profile": profile_name,
            "reference_weight": recipes[0]["appearance_strength"], "conditioned_reference_image": str(reference_path),
            "conditioned_pose_image": str(pose_path), "conditioning_width": width, "conditioning_height": height}
        self._write(self._run_path(run_id), run)
        return self._public(run)

    def detail(self, run_id: str) -> dict[str, Any]:
        path = self._run_path(run_id)
        if not path.is_file():
            raise SingleCharacterLabError(f"Single Character Lab run not found: {run_id}")
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise SingleCharacterLabError(f"Invalid Single Character Lab run: {run_id}")
        run = self._normalize_run(value)
        return self._reconcile_automatic_review(run, path)

    @staticmethod
    def _normalize_run(run: dict[str, Any]) -> dict[str, Any]:
        if int(run.get("schema_version") or 1) >= 2:
            return run
        normalized = dict(run)
        candidates = []
        for item in run.get("candidates") or []:
            candidate = dict(item)
            candidate.setdefault("status", "COMPLETE" if candidate.get("image_path") else "PENDING")
            candidate.setdefault("recipe_id", "legacy")
            candidate.setdefault("error", "")
            candidate.setdefault("review", {"decision": "undecided", "shortlisted": False,
                                             "failure_reasons": [], "score_overrides": {}, "notes": "", "cleanup_minutes": None})
            candidate["review"].setdefault("score_overrides", dict(candidate["review"].get("scores") or {}))
            candidates.append(candidate)
        normalized["candidates"] = candidates
        normalized.setdefault("candidate_count", len(candidates))
        normalized.setdefault("completed_count", sum(item["status"] == "COMPLETE" for item in candidates))
        normalized.setdefault("failed_count", sum(item["status"] == "FAILED" for item in candidates))
        normalized.setdefault("mode", "legacy")
        normalized.setdefault("reference_image", run.get("conditioned_reference_image") or "")
        normalized.setdefault("pose_image", run.get("conditioned_pose_image") or "")
        return normalized

    def _review_proxy_record(self, ask_id: str) -> tuple[str, dict[str, Any]]:
        paths = self.app.ai_proxy_service.ai_proxy_path_service
        roots = (("QUEUED", paths.ask_root()), ("RUNNING", paths.running_root()),
                 ("ANSWERED", paths.answer_root()))
        for state, root in roots:
            record = root / ask_id
            if record.is_dir():
                try:
                    answer = json.loads((record / "answer_manifest.json").read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    answer = {}
                return state, answer
        archive = paths.harvested_archive_root()
        if archive.is_dir():
            for record in archive.glob(f"*/{ask_id}"):
                try:
                    answer = json.loads((record / "answer_manifest.json").read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    answer = {}
                return "HARVESTED", answer
        return "UNKNOWN", {}

    def _reconcile_automatic_review(self, run: dict[str, Any], run_path: Path) -> dict[str, Any]:
        review_state = run.get("automatic_review")
        if not isinstance(review_state, dict) or not isinstance(review_state.get("jobs"), list):
            return run
        if review_state.get("status") == "COMPLETE":
            return run
        reviewer = ImageQualityReviewService(self.project_root)
        rubric = reviewer._rubric()
        candidates = {item["candidate_id"]: item for item in run.get("candidates") or []}
        changed = False
        for job in review_state["jobs"]:
            if job.get("status") in {"COMPLETE", "FAILED"}:
                continue
            output = Path(str(job.get("output_path") or ""))
            if output.is_file():
                try:
                    response = json.loads(output.read_text(encoding="utf-8"))
                    if not isinstance(response, dict):
                        raise ImageQualityReviewError("Automatic review output must be a JSON object.")
                    _, answer = self._review_proxy_record(str(job.get("ask_id") or ""))
                    runtime_evidence = {
                        key: answer[key]
                        for key in ("worker_id", "ollama_runtime", "ollama_generation")
                        if key in answer
                    }
                    elapsed = answer.get("elapsed_seconds")
                    result = reviewer.finalize_review(
                        job["candidate_id"], response, rubric, job["input_hashes"],
                        runtime_evidence=runtime_evidence,
                        elapsed_seconds=float(elapsed) if elapsed is not None else None,
                    )
                    result["model"] = review_state.get("model", "")
                    result["rubric_version"] = int(rubric.get("version") or rubric.get("schema_version") or 1)
                    candidate = candidates.get(job["candidate_id"])
                    if candidate is not None:
                        candidate["automatic_review"] = result
                    job.update({"status": "COMPLETE", "completed_at": self._now(), "error": ""})
                except (OSError, ValueError, TypeError, json.JSONDecodeError, ImageQualityReviewError) as exc:
                    job.update({"status": "FAILED", "completed_at": self._now(), "error": str(exc)})
                changed = True
                continue
            proxy_state, answer = self._review_proxy_record(str(job.get("ask_id") or ""))
            answer_status = str(answer.get("status") or "").upper()
            if answer_status in {"ERROR", "RETRY_LATER"}:
                job.update({"status": "FAILED", "completed_at": self._now(),
                            "error": str(answer.get("error_message") or "AI Proxy review failed.")})
                changed = True
            elif proxy_state in {"RUNNING", "ANSWERED", "HARVESTED"} and job.get("status") != "RUNNING":
                job["status"] = "RUNNING"
                changed = True
        completed = sum(item.get("status") == "COMPLETE" for item in review_state["jobs"])
        failed = sum(item.get("status") == "FAILED" for item in review_state["jobs"])
        pending = len(review_state["jobs"]) - completed - failed
        next_status = "COMPLETE" if pending == 0 else (
            "RUNNING" if any(item.get("status") == "RUNNING" for item in review_state["jobs"]) else "QUEUED"
        )
        counts = {"status": next_status, "completed_count": completed, "failed_count": failed,
                  "pending_count": pending}
        if any(review_state.get(key) != value for key, value in counts.items()):
            review_state.update(counts)
            changed = True
        if next_status == "COMPLETE" and not review_state.get("completed_at"):
            review_state["completed_at"] = self._now()
            changed = True
        if changed:
            run["updated_at"] = self._now()
            self._write(run_path, run)
        return run

    @staticmethod
    def _summary(run: dict[str, Any]) -> dict[str, Any]:
        candidates = run.get("candidates") or []
        reviewed = [item for item in candidates if (item.get("review") or {}).get("decision") in {"keep", "reject"}]
        kept = [item for item in reviewed if item["review"]["decision"] == "keep"]
        cleanup = [float(item["review"]["cleanup_minutes"]) for item in reviewed if item["review"].get("cleanup_minutes") is not None]
        failures: dict[str, int] = {}
        for item in reviewed:
            for reason in item["review"].get("failure_reasons") or []:
                failures[reason] = failures.get(reason, 0) + 1
        times = [float(item["render_seconds"]) for item in candidates if item.get("render_seconds") is not None]
        remaining = sum(item.get("status") in {"PENDING", "QUEUED", "RUNNING"} for item in candidates)
        recipe_summaries = []
        for recipe_id in sorted({str(item.get("recipe_id") or "") for item in candidates}):
            recipe_candidates = [item for item in candidates if str(item.get("recipe_id") or "") == recipe_id]
            recipe_reviewed = [item for item in recipe_candidates if (item.get("review") or {}).get("decision") in {"keep", "reject"}]
            recipe_kept = sum((item.get("review") or {}).get("decision") == "keep" for item in recipe_reviewed)
            recipe_summaries.append({"recipe_id": recipe_id, "candidate_count": len(recipe_candidates),
                "reviewed_count": len(recipe_reviewed), "kept_count": recipe_kept,
                "acceptance_rate": round(recipe_kept / len(recipe_reviewed), 3) if recipe_reviewed else None})
        best_of = []
        for size in (6, 16, 64, 128):
            groups = [candidates[start:start + size] for start in range(0, len(candidates) - size + 1, size)]
            reviewed_groups = [group for group in groups if all(
                (item.get("review") or {}).get("decision") in {"keep", "reject"} for item in group
            )]
            if groups:
                successes = sum(any((item.get("review") or {}).get("decision") == "keep" for item in group)
                                for group in reviewed_groups)
                best_of.append({"n": size, "reviewed_groups": len(reviewed_groups),
                                "success_rate": round(successes / len(reviewed_groups), 3) if reviewed_groups else None})
        return {"candidate_count": len(candidates), "reviewed_count": len(reviewed), "kept_count": len(kept),
            "acceptance_rate": round(len(kept) / len(reviewed), 3) if reviewed else None,
            "review_coverage": round(len(reviewed) / len(candidates), 3) if candidates else 0,
            "median_cleanup_minutes": statistics.median(cleanup) if cleanup else None,
            "failure_distribution": failures, "total_render_seconds": round(sum(times), 3),
            "estimated_remaining_seconds": round(statistics.mean(times) * remaining, 1) if times else None,
            "recipes": recipe_summaries, "best_of": best_of}

    def _public(self, run: dict[str, Any]) -> dict[str, Any]:
        return {**run, "summary": self._summary(run)}

    def list_runs(self, character: str, phase: str) -> list[dict[str, Any]]:
        if not self.runs_root.exists():
            return []
        runs = []
        for path in self.runs_root.glob("*/run.json"):
            try:
                run = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if run.get("character") == character and run.get("phase") == phase:
                runs.append(self._public(self._normalize_run(run)))
        return sorted(runs, key=lambda item: item.get("created_at", ""), reverse=True)[:20]

    def candidate_page(
        self, run_id: str, page: int = 1, page_size: int = 24, blind: bool = False, sort: str = "candidate"
    ) -> dict[str, Any]:
        run, page_size, page = self.detail(run_id), min(96, max(1, int(page_size))), max(1, int(page))
        rows = list(run.get("candidates") or [])
        if blind:
            rows.sort(key=lambda item: hashlib.sha256(f"{run_id}:{item['candidate_id']}".encode()).hexdigest())
        elif sort == "decision":
            rows.sort(key=lambda item: ((item.get("review") or {}).get("decision") or "undecided", item["candidate_id"]))
        elif sort in {"identity_fidelity", "costume_fidelity", "pose_orientation", "composition_framing", "technical_quality", "style_fit"}:
            def effective_score(item: dict[str, Any]) -> int:
                override = ((item.get("review") or {}).get("score_overrides") or {}).get(sort)
                automatic = ((item.get("automatic_review") or {}).get("scores") or {}).get(sort)
                return int(override if override is not None else automatic if automatic is not None else -1)
            rows.sort(key=lambda item: (
                -effective_score(item), item["candidate_id"]
            ))
        total, start = len(rows), (page - 1) * page_size
        rows = rows[start:start + page_size]
        if blind:
            rows = [{key: value for key, value in item.items() if key not in {"recipe_id", "seed", "automatic_review"}} for item in rows]
        return {"run_id": run_id, "page": page, "page_size": page_size, "total": total,
                "pages": max(1, (total + page_size - 1) // page_size), "blind": blind, "sort": sort,
                "candidates": rows}

    @staticmethod
    def _recipe(run: dict[str, Any], recipe_id: str) -> dict[str, Any]:
        recipe = next((item for item in run.get("recipes") or [] if item["recipe_id"] == recipe_id), None)
        if recipe is None:
            raise SingleCharacterLabError(f"Unknown recipe: {recipe_id}")
        return recipe

    def _candidate_failure(self, ask_id: str) -> str:
        for path in self.app.ai_proxy_service.ai_proxy_path_service.task_paths("answer"):
            if path.name != ask_id:
                continue
            try:
                answer = json.loads((path / "answer_manifest.json").read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return ""
            if str(answer.get("status") or "").upper() in {"ERROR", "RETRY_LATER"}:
                return str(answer.get("error_message") or f"AI proxy render {ask_id} failed.")
        return ""

    def _candidate_timing(self, ask_id: str, queued_at: str) -> tuple[float | None, float | None]:
        for path in self.app.ai_proxy_service.ai_proxy_path_service.task_paths("answer"):
            if path.name != ask_id:
                continue
            try:
                answer = json.loads((path / "answer_manifest.json").read_text(encoding="utf-8"))
                started = datetime.fromisoformat(str(answer.get("started_at") or ""))
                queued = datetime.fromisoformat(queued_at)
                return max(0.0, round((started - queued).total_seconds(), 3)), float(answer.get("elapsed_seconds"))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                return None, None
        return None, None

    def _finalize(self, run: dict[str, Any]) -> None:
        complete = [item for item in run.get("candidates") or [] if item.get("status") == "COMPLETE"]
        run["proxy_jobs"] = [{"ask_id": item.get("ask_id", ""), "seed": item.get("seed", ""),
                              "image_path": item.get("image_path", "")} for item in run.get("candidates") or []
                             if item.get("ask_id")]
        run["completed_count"] = len(complete)
        run["failed_count"] = sum(item.get("status") == "FAILED" for item in run.get("candidates") or [])
        if complete:
            sheets = []
            for start in range(0, len(complete), 24):
                page = start // 24 + 1
                contact_sheet = self._run_path(run["run_id"]).parent / "renders" / f"contact_sheet_{page:02d}.png"
                CheckpointLabService._contact_sheet(complete[start:start + 24], contact_sheet)
                sheets.append(str(contact_sheet))
            run["contact_sheets"] = sheets
            run["contact_sheet"] = sheets[0]

    def execute_run(self, run_id: str) -> None:
        run = self.detail(run_id)
        if run.get("status") == "RUNNING":
            return
        run.update({"status": "RUNNING", "updated_at": self._now(), "error": ""})
        self._write(self._run_path(run_id), run)
        prompt_path = self._run_path(run_id).parent / "Prompt.md"
        prompt_path.write_text(f"Prompt: {run['positive_prompt']}\nNegative: {run['negative_prompt']}\n", encoding="utf-8")
        for index in range(len(run.get("candidates") or [])):
            run = self.detail(run_id)
            candidate = run["candidates"][index]
            if run.get("stop_requested"):
                run.update({"status": "STOPPED", "updated_at": self._now()})
                self._finalize(run)
                self._write(self._run_path(run_id), run)
                return
            if candidate.get("status") in {"COMPLETE", "FAILED"}:
                continue
            recipe, queued_at = self._recipe(run, candidate["recipe_id"]), time.monotonic()
            output_dir = self._run_path(run_id).parent / "renders" / candidate["candidate_id"]
            try:
                if not (candidate.get("image_path") and Path(candidate["image_path"]).is_file()):
                    if not candidate.get("ask_id"):
                        manifest = {"ask_id": f"SingleCharacterLab_{run_id}_{candidate['candidate_id']}",
                            "asset_id": run["asset_id"], "character": run["character"], "phase": run["phase"],
                            "pipeline": "Single-Character-Lab", "pipeline_stage": "RENDER"}
                        overrides = {"width": recipe["width"], "height": recipe["height"], "steps": recipe["steps"],
                            "cfg": recipe["guidance"], "sampler_name": recipe["sampler"], "scheduler": recipe["scheduler"],
                            "denoise": recipe["denoise"], "character_reference_weight": recipe["appearance_strength"],
                            "control_strength": recipe["pose_strength"]}
                        frozen_profile = run.get("profile_snapshot") or {}
                        for key in ("character_reference_end_at", "ipadapter_model", "clip_vision_model",
                                    "ipadapter_weight_type", "ipadapter_combine_embeds", "ipadapter_embeds_scaling",
                                    "control_preprocessor", "controlnet_model", "control_start", "control_end",
                                    "preprocessor_resolution", "text_encoder", "vae"):
                            if key in frozen_profile:
                                overrides[key] = frozen_profile[key]
                        ask_path = self.app.ai_proxy_service.stage_render_task_local_render_ask(
                            manifest, prompt_path, output_dir, allow_parallel=False, seed=int(candidate["seed"]),
                            checkpoint=recipe["checkpoint"], render_overrides=overrides,
                            render_preset=recipe["render_profile"], image_generation="comfyui",
                            reference_files=[{"role": "prompt_evolution_appearance", "path": run["reference_image"]},
                                             {"role": "prompt_evolution_pose", "path": run["pose_image"]},
                                             {"role": "prompt_evolution_init", "path": run["reference_image"]}])
                        ask = json.loads((ask_path / "ask_manifest.json").read_text(encoding="utf-8"))
                        candidate.update({"ask_id": ask["ask_id"], "status": "QUEUED", "queued_at": self._now(),
                            "image_path": str(output_dir / "Local_Test_Renders" / ask["expected_output"])})
                        run["candidates"][index] = candidate
                        self._write(self._run_path(run_id), run)
                    adapter_timeout = {
                        "flux2-klein-4b": 600.0,
                        "qwen-image-edit-2511": 900.0,
                    }.get(str(recipe.get("adapter_id") or ""), float(self.app.config.comfyui_timeout_seconds))
                    deadline = time.monotonic() + float(recipe.get("timeout_seconds") or adapter_timeout) + 60.0
                    while not Path(candidate["image_path"]).is_file():
                        self.app.harvest_ai_answers()
                        failure = self._candidate_failure(candidate["ask_id"])
                        if failure:
                            raise SingleCharacterLabError(failure)
                        if time.monotonic() >= deadline:
                            raise SingleCharacterLabError("Timed out waiting for the candidate render.")
                        time.sleep(max(0.2, float(self.app.config.comfyui_poll_seconds)))
                queue_seconds, render_seconds = self._candidate_timing(
                    candidate["ask_id"], str(candidate.get("queued_at") or self._now())
                )
                candidate.update({"status": "COMPLETE", "completed_at": self._now(),
                    "queue_seconds": queue_seconds,
                    "render_seconds": render_seconds if render_seconds is not None else round(time.monotonic() - queued_at, 3),
                    "error": ""})
            except Exception as exc:
                candidate.update({"status": "FAILED", "completed_at": self._now(), "error": str(exc),
                                  "render_seconds": round(time.monotonic() - queued_at, 3)})
            latest = self.detail(run_id)
            run = latest
            run["candidates"][index] = candidate
            run.update({"completed_count": sum(item.get("status") == "COMPLETE" for item in run["candidates"]),
                        "failed_count": sum(item.get("status") == "FAILED" for item in run["candidates"]),
                        "updated_at": self._now()})
            self._write(self._run_path(run_id), run)
        run = self.detail(run_id)
        run.update({"status": "COMPLETE_WITH_ERRORS" if any(item.get("status") == "FAILED" for item in run["candidates"])
                    else "COMPLETE", "updated_at": self._now()})
        self._finalize(run)
        self._write(self._run_path(run_id), run)

    def request_stop(self, run_id: str) -> dict[str, Any]:
        run = self.detail(run_id)
        run.update({"stop_requested": True, "status": "STOPPING" if run.get("status") == "RUNNING" else "STOPPED",
                    "updated_at": self._now()})
        self._write(self._run_path(run_id), run)
        return self._public(run)

    def delete_run(self, run_id: str) -> dict[str, Any]:
        run = self.detail(run_id)
        if run.get("status") in {"QUEUED", "RUNNING", "STOPPING"}:
            raise SingleCharacterLabError("Stop or finish the active render before deleting this run.")
        if (run.get("automatic_review") or {}).get("status") in {"QUEUED", "RUNNING"}:
            raise SingleCharacterLabError("Wait for the active AI Proxy review before deleting this run.")
        root = self._run_path(run_id).parent.resolve()
        runs_root = self.runs_root.resolve()
        if not root.is_relative_to(runs_root) or root.parent != runs_root or root.name != run_id:
            raise SingleCharacterLabError("Refusing to delete an invalid Single Character Lab run path.")
        if root.is_symlink() or (hasattr(root, "is_junction") and root.is_junction()):
            raise SingleCharacterLabError("Refusing to delete a linked Single Character Lab run path.")
        queue_root = Path(self.app.config.base_ai_queue_path)
        paths = self.app.ai_proxy_service.ai_proxy_path_service
        for queue_path in paths.task_paths("ask", "running", "answer"):
            try:
                manifest = json.loads((queue_path / "ask_manifest.json").read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            belongs_to_run = (
                str(manifest.get("single_character_lab_run_id") or "") == run_id
                or (
                    str(manifest.get("pipeline") or "") == "Single-Character-Lab"
                    and run_id in str(manifest.get("ask_id") or queue_path.name)
                )
            )
            if belongs_to_run:
                supersede_task(queue_root, queue_path, "Single Character Lab run was deleted.")
        shutil.rmtree(root)
        return {"deleted": True, "run_id": run_id}

    def prepare_resume(self, run_id: str, *, retry_failed: bool = False, candidate_id: str = "") -> dict[str, Any]:
        run = self.detail(run_id)
        for candidate in run.get("candidates") or []:
            if candidate.get("status") == "FAILED" and (retry_failed or candidate["candidate_id"] == candidate_id):
                candidate.update({"status": "PENDING", "ask_id": "", "image_path": "", "error": "", "render_seconds": None})
        run.update({"stop_requested": False, "status": "QUEUED", "updated_at": self._now(), "error": ""})
        self._write(self._run_path(run_id), run)
        return self._public(run)

    def update_review(self, run_id: str, candidate_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        run = self.detail(run_id)
        candidate = next((item for item in run.get("candidates") or [] if item["candidate_id"] == candidate_id), None)
        if candidate is None:
            raise SingleCharacterLabError(f"Unknown candidate: {candidate_id}")
        decision = str(payload.get("decision") or "undecided")
        if decision not in {"keep", "reject", "undecided"}:
            raise SingleCharacterLabError("Decision must be keep, reject, or undecided.")
        cleanup = payload.get("cleanup_minutes")
        if cleanup not in (None, "") and float(cleanup) < 0:
            raise SingleCharacterLabError("Cleanup minutes cannot be negative.")
        rubric = json.loads((self.project_root / "Config" / "Image_Quality_Rubric.json").read_text(encoding="utf-8"))
        allowed_failures = set(rubric.get("failure_reasons") or [])
        failure_reasons = [str(item) for item in payload.get("failure_reasons") or []]
        unknown = sorted(set(failure_reasons) - allowed_failures)
        if unknown:
            raise SingleCharacterLabError("Unknown failure reasons: " + ", ".join(unknown))
        allowed_scores = {item["id"] for item in rubric.get("dimensions") or []}
        submitted_scores = {
            str(key): int(value) for key, value in (payload.get("scores") or {}).items() if value not in (None, "")
        }
        if set(submitted_scores) - allowed_scores or any(value < 0 or value > 4 for value in submitted_scores.values()):
            raise SingleCharacterLabError("Review scores must use rubric dimensions and values from 0 to 4.")
        machine_scores = (candidate.get("automatic_review") or {}).get("scores") or {}
        score_overrides = {
            key: value for key, value in submitted_scores.items()
            if key not in machine_scores or int(machine_scores[key]) != value
        }
        candidate["review"] = {"decision": decision, "shortlisted": bool(payload.get("shortlisted", False)),
            "failure_reasons": failure_reasons, "score_overrides": score_overrides,
            "notes": str(payload.get("notes") or ""), "cleanup_minutes": None if cleanup in (None, "") else float(cleanup),
            "updated_at": self._now()}
        run["updated_at"] = self._now()
        self._write(self._run_path(run_id), run)
        return {"candidate": candidate, "summary": self._summary(run)}

    def save_recipe(self, run_id: str, recipe_id: str, name: str = "") -> dict[str, Any]:
        run, path = self.detail(run_id), self.runs_root / "saved_recipes.json"
        recipe = self._recipe(run, recipe_id)
        payload = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"schema_version": 1, "recipes": []}
        record = {**recipe, "saved_recipe_id": datetime.now().strftime("recipe_%Y%m%d_%H%M%S_%f"),
                  "name": name.strip() or f"{run.get('costume') or 'Character'} {recipe_id}",
                  "source_run_id": run_id, "saved_at": self._now()}
        payload["recipes"].append(record)
        self._write(path, payload)
        return record

    def queue_automatic_review(self, run_id: str, model: str, candidate_ids: list[str]) -> dict[str, Any]:
        run = self.detail(run_id)
        if run.get("status") in {"QUEUED", "RUNNING", "STOPPING"}:
            raise SingleCharacterLabError("Stop or finish rendering before starting automatic review.")
        if (run.get("automatic_review") or {}).get("status") in {"QUEUED", "RUNNING"}:
            raise SingleCharacterLabError("Automatic review is already queued through AI Proxy.")
        selected_ids = set(candidate_ids)
        completed = [item for item in run.get("candidates") or [] if item.get("status") == "COMPLETE"
                     and (not selected_ids or item["candidate_id"] in selected_ids)]
        if not completed:
            raise SingleCharacterLabError("No completed candidates were selected for automatic review.")
        reviewer = ImageQualityReviewService(self.project_root)
        rubric = reviewer._rubric()
        system, prompt, schema = reviewer.review_contract(rubric)
        reference = Path(run["reference_image"])
        pose = Path(str(run.get("pose_image") or ""))
        if not reference.is_file() or not pose.is_file():
            raise SingleCharacterLabError("Frozen appearance and pose inputs are required for automatic review.")
        root = self._run_path(run_id).parent
        review_inputs = root / "review_inputs"
        prepared_reference = reviewer._review_image(reference, review_inputs)
        prepared_pose = reviewer._review_image(pose, review_inputs)
        results_root = root / "automatic_review_results"
        results_root.mkdir(parents=True, exist_ok=True)
        state = {"status": "QUEUED", "model": model, "candidate_ids": [item["candidate_id"] for item in completed],
                 "queued_at": self._now(), "completed_count": 0, "failed_count": 0,
                 "pending_count": len(completed), "jobs": []}
        run["automatic_review"] = state
        self._write(self._run_path(run_id), run)
        proxy = self.app.ai_proxy_service.ai_proxy_path_service.file_proxy_client
        appearance_hash = self._hash(reference)
        pose_hash = self._hash(pose)
        rubric_version = int(rubric.get("version") or rubric.get("schema_version") or 1)
        for candidate in completed:
            candidate_path = Path(str(candidate.get("image_path") or ""))
            if not candidate_path.is_file():
                continue
            input_hashes = {"appearance": appearance_hash, "pose": pose_hash,
                            "candidate": self._hash(candidate_path)}
            previous = candidate.get("automatic_review") or {}
            if previous.get("input_hashes") == input_hashes and previous.get("model") == model:
                state["completed_count"] += 1
                state["pending_count"] -= 1
                continue
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            ask_id = f"Ask_Single_Character_Lab_{run_id}_{candidate['candidate_id']}_{stamp}"
            staging = proxy.create_staging(ask_id)
            image_files = []
            for name, source in (("appearance.jpg", prepared_reference), ("pose.jpg", prepared_pose),
                                 ("candidate.jpg", reviewer._review_image(candidate_path, review_inputs))):
                shutil.copy2(source, staging / name)
                image_files.append(name)
            (staging / "OLLAMA_PROMPT.md").write_text(
                f"SYSTEM INSTRUCTION:\n{system}\n\nREVIEW TASK:\n{prompt}\n", encoding="utf-8"
            )
            output = results_root / f"{candidate['candidate_id']}.json"
            manifest = {
                "version": AI_PROXY_PROTOCOL_VERSION, "ask_id": ask_id, "asset_id": None,
                "character": run.get("character", ""), "phase": run.get("phase", ""),
                "pipeline": "Single-Character-Lab", "pipeline_stage": "AUTOMATIC_REVIEW",
                "ollama_attempt_id": stamp, "worker_type": "ollama_generate", "ollama_model": model,
                "prompt_file": "OLLAMA_PROMPT.md", "image_files": image_files, "json_output": True,
                "response_schema": schema, "expected_output": "response.json",
                "task_type": "single_character_lab_automatic_review", "auxiliary": True,
                "target_output_dir": str(results_root.resolve()), "target_output_file": output.name,
                "single_character_lab_run_id": run_id, "candidate_id": candidate["candidate_id"],
                "input_hashes": input_hashes, "rubric_version": rubric_version,
            }
            (staging / "ask_manifest.json").write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            proxy.publish(staging, ask_id, "ollama_generate")
            state["jobs"].append({"candidate_id": candidate["candidate_id"], "ask_id": ask_id,
                                  "status": "QUEUED", "queued_at": self._now(),
                                  "output_path": str(output), "input_hashes": input_hashes, "error": ""})
            self._write(self._run_path(run_id), run)
        if not state["jobs"]:
            state.update({"status": "COMPLETE", "pending_count": 0, "completed_at": self._now()})
            self._write(self._run_path(run_id), run)
        return state

    def automatic_review(self, run_id: str, *, model: str, candidate_ids: list[str] | None = None) -> dict[str, Any]:
        return self.queue_automatic_review(run_id, model, candidate_ids or [])
