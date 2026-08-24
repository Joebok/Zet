from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import random
import re
import time
from typing import Any

from PIL import Image, ImageOps

from zet.services.checkpoint_lab_service import CheckpointLabService
from zet.services.local_render_backend_service import LocalRenderBackendService


DEFAULT_PROFILE = "image-recipe-lab-ipadapter-controlnet-sdxl"
DEFAULT_REFERENCE_WEIGHT = 0.45
DEFAULT_NEGATIVE_PROMPT = (
    "worst quality, low quality, lowres, blurry, pixelated, jpeg artifacts, bad anatomy, "
    "bad proportions, malformed body, deformed hands, extra fingers, missing fingers, "
    "extra limbs, missing limbs, duplicate character, multiple people, cropped head, "
    "cropped feet, out of frame, text, caption, logo, watermark, signature, 3d render, "
    "plastic skin, chibi, super-deformed"
)


class SingleCharacterLabError(ValueError):
    pass


class SingleCharacterLabService:
    def __init__(self, app: Any, project_root: str | Path):
        self.app = app
        self.project_root = Path(project_root).resolve()
        self.runs_root = Path(app.config.base_pipeline_path).resolve() / "Single_Character_Lab"

    @staticmethod
    def _extract_section(text: str, name: str) -> str:
        match = re.search(
            rf"<!-- ZET:BEGIN {re.escape(name)} -->\s*(.*?)\s*<!-- ZET:END {re.escape(name)} -->",
            text,
            re.DOTALL,
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
                if not line.casefold().startswith("forbidden drift:"):
                    continue
                line = line.split(":", 1)[1]
                line = re.sub(r"\b(?:do not|no)\s+", "", line, flags=re.IGNORECASE)
                if line.strip():
                    parts.append(line.strip().rstrip("."))
        return ", ".join(parts)

    @staticmethod
    def _fact_anchor(value: str, label: str, noun: str, weight: float) -> str:
        for line in value.splitlines():
            line = re.sub(r"^\s*[-*]\s*", "", line).strip().replace("`", "")
            if not line.casefold().startswith(f"{label}:".casefold()):
                continue
            fact = line.split(":", 1)[1].strip().rstrip(".")
            fact = re.split(r"\s+with\s+|[,;]", fact, maxsplit=1, flags=re.IGNORECASE)[0].strip()
            return f"({fact} {noun}:{weight:g})" if fact else ""
        return ""

    @staticmethod
    def _view_section(view: str) -> str:
        return re.sub(r"[^A-Za-z0-9]+", "_", view).strip("_").upper()

    def _asset(self, character: str, phase: str, asset_id: int):
        asset = self.app.asset(character, phase, asset_id).get()
        if asset.pipeline != "Costume-Dressing" or asset.asset_state != "LOCKED":
            raise SingleCharacterLabError("Appearance source must be a locked Costume-Dressing asset.")
        image_path = self.app.path_service.locked_image_path(asset).resolve()
        if not image_path.is_file():
            raise SingleCharacterLabError(f"Locked appearance image not found: {image_path}")
        return asset, image_path

    def appearance_options(self, character: str, phase: str) -> list[dict[str, Any]]:
        result = []
        for asset in self.app.list_assets(character, phase):
            if asset.pipeline != "Costume-Dressing" or asset.asset_state != "LOCKED":
                continue
            image_path = self.app.path_service.locked_image_path(asset).resolve()
            if not image_path.is_file():
                continue
            result.append({
                "asset_id": asset.asset_id,
                "costume": asset.costume or "",
                "view": asset.body_view or "",
                "label": f"{asset.costume or 'Costume'} · {asset.body_view or 'Unknown view'}",
                "image_path": str(image_path),
            })
        return sorted(result, key=lambda item: (item["costume"].casefold(), item["view"].casefold()))

    def pose_options(self, character: str, phase: str) -> list[dict[str, str]]:
        rows = self.app.story_service.image_reference_rows(
            character,
            "",
            phase,
            "",
            scope="context",
            include_unavailable=False,
        )
        return [
            {
                "tag": row.tag,
                "label": row.label,
                "view": row.view,
                "image_path": str(Path(row.image_path).resolve()),
            }
            for row in rows
            if row.pipeline == "Body-Reference" and row.kind == "locked-asset" and row.view
        ]

    def checkpoints(self) -> tuple[list[str], str]:
        profiles_path = self.project_root / "Config" / "Local_Render_Presets.json"
        try:
            rows = LocalRenderBackendService(profiles_path).list_checkpoints(
                DEFAULT_PROFILE,
                backend="comfyui",
                server_url=self.app.config.comfyui_server_url,
            )
            checkpoints = [str(row.get("title") or "") for row in rows if row.get("title")]
        except Exception as exc:
            checkpoints = []
            error = str(exc)
        else:
            error = ""
        configured = str(self.app.config.comfyui_checkpoint or "").strip()
        if configured and configured not in checkpoints:
            checkpoints.insert(0, configured)
        return checkpoints, error

    def options(self, character: str, phase: str) -> dict[str, Any]:
        checkpoints, checkpoint_error = self.checkpoints()
        configured = str(self.app.config.comfyui_checkpoint or "").strip()
        preferred = next((item for item in checkpoints if "tastyrice" in item.casefold()), configured)
        return {
            "appearances": self.appearance_options(character, phase),
            "poses": self.pose_options(character, phase),
            "checkpoints": checkpoints,
            "default_checkpoint": preferred,
            "default_profile": DEFAULT_PROFILE,
            "default_reference_weight": DEFAULT_REFERENCE_WEIGHT,
            "checkpoint_error": checkpoint_error,
        }

    def prompt(self, character: str, phase: str, asset_id: int) -> dict[str, str]:
        asset, _image_path = self._asset(character, phase, asset_id)
        character_path = Path(self.app.config.base_character_path) / character / phase / "Character.md"
        costume_path = (
            self.app.path_service.resolve_path(asset.costume_path).resolve()
            if asset.costume_path
            else self.app.path_service.costume_template_path(character, phase, asset.costume or "")
        )
        if not character_path.is_file() or not costume_path.is_file():
            raise SingleCharacterLabError("Character or costume source markdown is unavailable.")
        character_text = character_path.read_text(encoding="utf-8")
        costume_text = costume_path.read_text(encoding="utf-8")
        view = asset.body_view or "Front"
        view_section = self._view_section(view)
        body_facts = self._extract_section(character_text, "BODY_DESCRIPTION_FACTS")
        head_facts = self._extract_section(character_text, "HEAD_DESCRIPTION_FACTS")
        hair_facts = self._extract_section(character_text, "HAIR_DESCRIPTION_FACTS")
        scene_identity = self._extract_section(character_text, "SCENE_CHARACTER_IDENTITY")
        identity_sections = [scene_identity] if scene_identity else [body_facts, head_facts, hair_facts]
        sections = [
            *identity_sections,
            self._extract_section(character_text, f"BODY_DESCRIPTION_VIEW_{view_section}"),
            self._extract_section(character_text, f"HEAD_DESCRIPTION_VIEW_{view_section}"),
            self._extract_section(character_text, f"HAIR_DESCRIPTION_VIEW_{view_section}"),
            self._extract_section(costume_text, "COSTUME_DESCRIPTION_FACTS"),
            self._extract_section(costume_text, f"COSTUME_DESCRIPTION_VIEW_{view_section}"),
            self._extract_section(costume_text, "EQUIPMENT_JEWELRY_PROPS_FACTS"),
        ]
        details = [self._prompt_text(section) for section in sections if section]
        anchors = [
            self._fact_anchor(hair_facts, "Hair color", "hair", 1.3),
            self._fact_anchor(head_facts, "Eye color", "eyes", 1.2),
        ]
        positive = ", ".join([
            "masterpiece, best quality, highly detailed",
            "solo, single character, full body, standing, centered composition, visible from head to toe",
            f"{view} view",
            "painterly semi-realistic fantasy illustration, anime-influenced facial proportions",
            *(anchor for anchor in anchors if anchor),
            *details,
            "neutral unobtrusive background, soft studio lighting, sharp focus, coherent costume design",
        ])
        forbidden = self._forbidden_prompt(sections)
        negative = ", ".join(item for item in (DEFAULT_NEGATIVE_PROMPT, forbidden) if item)
        return {"positive_prompt": positive, "negative_prompt": negative}

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
    def _write(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    @staticmethod
    def _pad_image_to_size(source: Path, destination: Path, width: int, height: int) -> None:
        with Image.open(source) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGB")
            corners = (
                image.getpixel((0, 0)),
                image.getpixel((image.width - 1, 0)),
                image.getpixel((0, image.height - 1)),
                image.getpixel((image.width - 1, image.height - 1)),
            )
            background = tuple(sum(pixel[channel] for pixel in corners) // 4 for channel in range(3))
            resized = ImageOps.contain(image, (width, height), Image.Resampling.LANCZOS)
            canvas = Image.new("RGB", (width, height), background)
            canvas.paste(resized, ((width - resized.width) // 2, (height - resized.height) // 2))
            destination.parent.mkdir(parents=True, exist_ok=True)
            canvas.save(destination)

    def _conditioning_images(self, run: dict[str, Any]) -> tuple[Path, Path, int, int]:
        profile = LocalRenderBackendService(
            self.project_root / "Config" / "Local_Render_Presets.json"
        ).preset(run["render_profile"])
        width = int(profile.get("width") or 0)
        height = int(profile.get("height") or 0)
        if width <= 0 or height <= 0:
            raise SingleCharacterLabError("Render profile must define positive width and height.")
        root = self._run_path(run["run_id"]).parent / "conditioning"
        reference_path = root / "appearance.png"
        pose_path = root / "pose.png"
        self._pad_image_to_size(Path(run["reference_image"]), reference_path, width, height)
        self._pad_image_to_size(Path(run["pose_image"]), pose_path, width, height)
        return reference_path, pose_path, width, height

    def _proxy_failure(self, ask_ids: set[str]) -> str:
        paths = self.app.ai_proxy_service.ai_proxy_path_service
        for path in paths.task_paths("answer"):
            if path.name not in ask_ids:
                continue
            try:
                answer = json.loads((path / "answer_manifest.json").read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if str(answer.get("status") or "").upper() == "ERROR":
                return str(answer.get("error_message") or f"AI proxy render {path.name} failed.")
        return ""

    def _complete_proxy_run(self, run: dict[str, Any]) -> None:
        jobs = run.get("proxy_jobs") or []
        candidates = [
            {
                "candidate_id": f"c{index:03d}",
                "checkpoint": run["checkpoint"],
                "reference_weight": run["reference_weight"],
                "seed": str(job["seed"]),
                "image_path": job["image_path"],
                "ask_id": job["ask_id"],
            }
            for index, job in enumerate(jobs, start=1)
        ]
        root = self._run_path(run["run_id"]).parent / "renders"
        contact_sheet = root / "contact_sheet.png"
        CheckpointLabService._contact_sheet(candidates, contact_sheet)
        manifest_path = root / "experiment.json"
        self._write(manifest_path, {
            "schema_version": 1,
            "created_at": run["created_at"],
            "render_profile": run["render_profile"],
            "positive_prompt": run["positive_prompt"],
            "negative_prompt": run["negative_prompt"],
            "reference_image": run["conditioned_reference_image"],
            "pose_image": run["conditioned_pose_image"],
            "contact_sheet": str(contact_sheet),
            "proxy_jobs": jobs,
            "candidates": candidates,
        })
        run.update({
            "status": "COMPLETE",
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "candidates": candidates,
            "contact_sheet": str(contact_sheet),
            "manifest_path": str(manifest_path),
        })

    def create_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        character = str(payload.get("character") or "").strip()
        phase = str(payload.get("phase") or "").strip()
        asset_id = int(payload.get("asset_id") or 0)
        asset, reference_path = self._asset(character, phase, asset_id)
        pose_tag = str(payload.get("pose_tag") or "")
        pose_path = self._pose_path(character, phase, pose_tag)
        count = int(payload.get("count") or 1)
        if not 1 <= count <= 6:
            raise SingleCharacterLabError("Image count must be between 1 and 6.")
        weight = float(payload.get("reference_weight", DEFAULT_REFERENCE_WEIGHT))
        if not 0 <= weight <= 2:
            raise SingleCharacterLabError("IP-Adapter reference weight must be between 0 and 2.")
        checkpoint = str(payload.get("checkpoint") or self.app.config.comfyui_checkpoint).strip()
        if not checkpoint:
            raise SingleCharacterLabError("Checkpoint cannot be blank.")
        generated_prompt = self.prompt(character, phase, asset_id)
        positive = str(payload.get("positive_prompt") or generated_prompt["positive_prompt"]).strip()
        negative = str(payload.get("negative_prompt") or generated_prompt["negative_prompt"]).strip()
        if not positive:
            raise SingleCharacterLabError("Positive prompt cannot be blank.")
        generator = random.SystemRandom()
        seeds: list[int] = []
        while len(seeds) < count:
            seed = generator.randrange(0, 2**63 - 1)
            if seed not in seeds:
                seeds.append(seed)
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        run = {
            "schema_version": 1,
            "run_id": run_id,
            "status": "QUEUED",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "character": character,
            "phase": phase,
            "asset_id": asset_id,
            "costume": asset.costume or "",
            "view": asset.body_view or "",
            "reference_image": str(reference_path),
            "pose_tag": pose_tag,
            "pose_image": str(pose_path),
            "checkpoint": checkpoint,
            "render_profile": DEFAULT_PROFILE,
            "reference_weight": weight,
            "seeds": [str(seed) for seed in seeds],
            "positive_prompt": positive,
            "negative_prompt": negative,
            "candidates": [],
            "contact_sheet": "",
            "error": "",
        }
        self._write(self._run_path(run_id), run)
        return run

    def detail(self, run_id: str) -> dict[str, Any]:
        path = self._run_path(run_id)
        if not path.is_file():
            raise SingleCharacterLabError(f"Single Character Lab run not found: {run_id}")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise SingleCharacterLabError(f"Invalid Single Character Lab run: {run_id}")
        return data

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
                runs.append(run)
        return sorted(runs, key=lambda item: item.get("created_at", ""), reverse=True)[:20]

    def execute_run(self, run_id: str) -> None:
        run = self.detail(run_id)
        run["status"] = "RUNNING"
        run["updated_at"] = datetime.now().isoformat(timespec="seconds")
        self._write(self._run_path(run_id), run)
        try:
            reference_path, pose_path, width, height = self._conditioning_images(run)
            run.update({
                "conditioned_reference_image": str(reference_path),
                "conditioned_pose_image": str(pose_path),
                "conditioning_width": width,
                "conditioning_height": height,
            })
            self._write(self._run_path(run_id), run)
            prompt_path = self._run_path(run_id).parent / "Prompt.md"
            prompt_path.write_text(
                f"Prompt: {run['positive_prompt']}\nNegative: {run['negative_prompt']}\n",
                encoding="utf-8",
            )
            manifest = {
                "ask_id": f"SingleCharacterLab_{run_id}",
                "asset_id": run["asset_id"],
                "character": run["character"],
                "phase": run["phase"],
                "pipeline": "Single-Character-Lab",
                "pipeline_stage": "RENDER",
            }
            jobs = []
            for index, seed in enumerate(run["seeds"], start=1):
                output_dir = self._run_path(run_id).parent / "renders" / f"proxy-c{index:03d}"
                ask_path = self.app.ai_proxy_service.stage_render_task_local_render_ask(
                    manifest,
                    prompt_path,
                    output_dir,
                    allow_parallel=True,
                    seed=int(seed),
                    checkpoint=run["checkpoint"],
                    render_overrides={
                        "width": width,
                        "height": height,
                        "character_reference_weight": float(run["reference_weight"]),
                    },
                    render_preset=run["render_profile"],
                    image_generation="comfyui",
                    reference_files=[
                        {"role": "prompt_evolution_appearance", "path": str(reference_path)},
                        {"role": "prompt_evolution_pose", "path": str(pose_path)},
                    ],
                )
                ask = json.loads((ask_path / "ask_manifest.json").read_text(encoding="utf-8"))
                jobs.append({
                    "ask_id": ask["ask_id"],
                    "seed": str(seed),
                    "image_path": str(output_dir / "Local_Test_Renders" / ask["expected_output"]),
                })
            run["proxy_jobs"] = jobs
            self._write(self._run_path(run_id), run)
            deadline = time.monotonic() + float(self.app.config.comfyui_timeout_seconds) * len(jobs)
            while not all(Path(job["image_path"]).is_file() for job in jobs):
                self.app.harvest_ai_answers()
                error = self._proxy_failure({job["ask_id"] for job in jobs})
                if error:
                    raise SingleCharacterLabError(error)
                if time.monotonic() >= deadline:
                    raise SingleCharacterLabError("Timed out waiting for AI proxy image renders.")
                time.sleep(max(0.2, float(self.app.config.comfyui_poll_seconds)))
            self._complete_proxy_run(run)
        except Exception as exc:
            run.update({
                "status": "FAILED",
                "updated_at": datetime.now().isoformat(timespec="seconds"),
                "error": str(exc),
            })
        self._write(self._run_path(run_id), run)
