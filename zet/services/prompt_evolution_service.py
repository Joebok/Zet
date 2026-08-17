from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import random
import shutil
import tempfile
from typing import Any
import zipfile

from PIL import Image

from zet.models.ai_proxy import AI_PROXY_PROTOCOL_VERSION
from zet.services.ai_proxy_path_service import AIProxyPathService
from zet.services.character_grid_service import CharacterGridOptions, CharacterGridService


CANVAS_WIDTH = 768
CANVAS_HEIGHT = 1024
RUN_VERSION = 3
DEFAULT_VISION_MODEL = "qwen3.5-prompt-evo"
DEFAULT_CHECKLIST_MODEL = "qwen3-VL-prompt-evo"
TEMPLATE_NAMES = (
    "bootstrap", "visual_critic", "regression_check", "batch_synthesis",
    "prompt_diagnosis", "prompt_edit", "repair", "directed_refinement",
)
DEFAULT_DETECTION_TOLERANCE = 50.0
REFERENCE_PADDING_RATIO = 0.10
GRAY_BACKGROUND_TERM = "gray background"
LEGACY_GRAY_BACKGROUND_TERM = "plain smooth neutral gray studio background"
INITIAL_POSITIVE_PREFIX = ("masterpiece", "top quality", "full body shot", "standing pose", "centered", "visible from head to toe")
INITIAL_POSITIVE_SUFFIX = ("semi-realistic anime proportions", "large expressive detailed eyes", "soft shaded skin", "textured brushstrokes", "sharp focus")
INITIAL_NEGATIVE_PREFIX = (
    "(worst quality, low quality:1.4)", "cropped", "out of frame", "cut off", "head crop", "feet cut off", "close-up",
    "bust shot", "portrait shot", "upper body shot", "lowres", "blurry", "bad anatomy", "bad hands", "jpeg artifacts",
)
EVALUATION_POSITIVE_TERMS = (*INITIAL_POSITIVE_PREFIX, GRAY_BACKGROUND_TERM, *INITIAL_POSITIVE_SUFFIX)
EVALUATION_NEGATIVE_TERMS = INITIAL_NEGATIVE_PREFIX

VISUAL_REPORT_SCHEMA = {
    "type": "object", "required": ["major_differences", "secondary_differences", "stable_matches"],
    "properties": {
        "major_differences": {"type": "array", "items": {"type": "object", "required": ["reference", "candidate"], "properties": {"reference": {"type": "string"}, "candidate": {"type": "string"}}}},
        "secondary_differences": {"type": "array", "items": {"type": "object", "required": ["reference", "candidate"], "properties": {"reference": {"type": "string"}, "candidate": {"type": "string"}}}},
        "stable_matches": {"type": "array", "items": {"type": "string"}},
    },
}
SYNTHESIS_SCHEMA = {
    "type": "object", "required": ["recurrent_deviations", "intermittent_deviations", "isolated_deviations", "stable_successes", "cross_feature_patterns", "next_round_priorities"],
    "properties": {name: {"type": "array"} for name in (
        "recurrent_deviations", "intermittent_deviations", "isolated_deviations", "stable_successes", "cross_feature_patterns", "next_round_priorities",
    )},
}
SYNTHESIS_SCHEMA["properties"]["next_round_priorities"]["maxItems"] = 3
_SYNTHESIS_FINDING_SCHEMA = {
    "type": "object", "required": ["finding", "seeds", "observer_agreement"],
    "properties": {"finding": {"type": "string"}, "seeds": {"type": "array", "items": {"type": "integer"}}, "observer_agreement": {"enum": ["single", "dual"]}},
}
for _name in ("recurrent_deviations", "intermittent_deviations", "isolated_deviations"):
    SYNTHESIS_SCHEMA["properties"][_name]["items"] = _SYNTHESIS_FINDING_SCHEMA
for _name in ("stable_successes", "cross_feature_patterns"):
    SYNTHESIS_SCHEMA["properties"][_name]["items"] = {"type": "string"}
SYNTHESIS_SCHEMA["properties"]["next_round_priorities"]["items"] = {
    "type": "object", "required": ["problem", "evidence", "seeds", "observer_agreement"],
    "properties": {"problem": {"type": "string"}, "evidence": {"type": "string"}, "seeds": {"type": "array", "items": {"type": "integer"}}, "observer_agreement": {"enum": ["single", "dual"]}},
}
DIAGNOSIS_SCHEMA = {
    "type": "object", "required": ["interventions"], "properties": {"interventions": {"type": "array", "maxItems": 3, "items": {
        "type": "object", "required": ["id", "observed_pattern", "prompt", "action", "relevant_wording", "proposed_wording", "diagnosis", "rationale", "confidence", "regression_risk"],
        "properties": {"id": {"type": "string"}, "observed_pattern": {"type": "string"}, "prompt": {"enum": ["positive", "negative"]}, "action": {"enum": ["add", "replace", "delete"]}, "relevant_wording": {"type": "string"}, "proposed_wording": {"type": "string"}, "diagnosis": {"type": "string"}, "rationale": {"type": "string"}, "confidence": {"enum": ["High", "Medium", "Low"]}, "regression_risk": {"type": "string"}},
    }}},
}
EDIT_SCHEMA = {
    "type": "object", "required": ["positive_core", "negative_core", "changes"], "properties": {
        "positive_core": {"type": "string"}, "negative_core": {"type": "string"},
        "changes": {"type": "array", "minItems": 1, "maxItems": 3, "items": {"type": "object", "required": ["intervention_id", "old", "new", "reason"], "properties": {"intervention_id": {"type": "string"}, "old": {"type": "string"}, "new": {"type": "string"}, "reason": {"type": "string"}}}},
    },
}
PROMPT_CORE_SCHEMA = {
    "type": "object", "required": ["positive_core", "negative_core"],
    "properties": {"positive_core": {"type": "string"}, "negative_core": {"type": "string"}},
}
BOOTSTRAP_SCHEMA = {
    "type": "object", "required": ["positive_terms", "negative_terms"],
    "properties": {"positive_terms": {"type": "array", "items": {"type": "string"}}, "negative_terms": {"type": "array", "items": {"type": "string"}}},
}


class PromptEvolutionError(ValueError):
    pass


class PromptEvolutionRepairPending(RuntimeError):
    pass


class PromptEvolutionPlaceholderResponse(PromptEvolutionError):
    pass


class PromptEvolutionService:
    """Persist and advance reference-driven Stable Diffusion prompt experiments."""

    def __init__(self, app: Any, project_root: str | Path):
        self.app = app
        self.project_root = Path(project_root).resolve()
        self.proxy = AIProxyPathService(app.config).file_proxy_client
        self.templates_root = self.project_root / "Config" / "Prompt_Evolution"
        self.template_names = TEMPLATE_NAMES

    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat(timespec="seconds")

    def _log(self, run: dict[str, Any], message: str, level: str = "info", **details: Any) -> None:
        event = {"at": self._now(), "level": level, "message": message}
        event.update({key: value for key, value in details.items() if value is not None})
        run.setdefault("activity_log", []).append(event)

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(f".{path.name}.tmp")
        temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(temp, path)

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise PromptEvolutionError(f"Expected a JSON object: {path}")
        return data

    @staticmethod
    def _archive_rejected_output(path: Path) -> None:
        if path.is_file():
            os.replace(path, path.with_name(f"{path.stem}.rejected{path.suffix}"))

    def template(self, name: str) -> str:
        if name not in TEMPLATE_NAMES:
            raise PromptEvolutionError(f"Unknown prompt-evolution template: {name}")
        return (self.templates_root / f"{name}.md").read_text(encoding="utf-8")

    def save_template(self, name: str, text: str) -> dict[str, str]:
        if name not in TEMPLATE_NAMES or not text.strip():
            raise PromptEvolutionError("A known, non-empty template is required.")
        path = self.templates_root / f"{name}.md"
        path.write_text(text, encoding="utf-8")
        return {"name": name, "text": text}

    def checklist(self) -> dict[str, Any]:
        return self._read_json(self.templates_root / "checklist.json")

    @staticmethod
    def _checklist_sidecar(template_path: Path) -> Path:
        return template_path.with_suffix(".prompt_evolution_checklist.json")

    @staticmethod
    def _validated_checklist_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
        items = payload.get("items")
        if not isinstance(items, list):
            raise PromptEvolutionError("Checklist JSON must contain an items array.")
        validated = []
        for row in items:
            if not isinstance(row, dict):
                raise PromptEvolutionError("Each checklist item must be an object.")
            requirement = str(row.get("requirement") or "").strip()
            question = str(row.get("question") or "").strip()
            correction = str(row.get("correction") or "").strip()
            item_id = str(row.get("id") or "").strip()
            if not item_id or not requirement or not question or not correction:
                raise PromptEvolutionError("Regression checks require id, requirement, question, and correction.")
            validated.append({
                "id": item_id,
                "requirement": requirement,
                "question": question,
                "correction": correction,
            })
        if len({item["id"] for item in validated}) != len(validated):
            raise PromptEvolutionError("Regression check IDs must be unique.")
        return validated

    def _scoped_checklist_path(self, scope: str, character: str, phase: str, costume: str = "") -> Path:
        if scope == "character":
            template = self.app.path_service.character_template_path(character, phase)
        elif scope == "costume" and costume:
            template = self.app.path_service.costume_template_path(character, phase, costume)
        else:
            raise PromptEvolutionError("Checklist scope must be character or costume.")
        if not template.is_file():
            raise PromptEvolutionError(f"Checklist metadata template is unavailable: {template}")
        return self._checklist_sidecar(template)

    def _read_scoped_checklist(self, scope: str, character: str, phase: str, costume: str = "") -> dict[str, Any]:
        path = self._scoped_checklist_path(scope, character, phase, costume)
        if not path.is_file():
            return {"items": []}
        data = self._read_json(path)
        return {"items": self._validated_checklist_items(data)}

    def scoped_checklists(self, character: str, phase: str, costume: str) -> dict[str, Any]:
        global_items = self._validated_checklist_items(self.checklist())
        character_items = self._read_scoped_checklist("character", character, phase)["items"]
        costume_items = self._read_scoped_checklist("costume", character, phase, costume)["items"]
        merged: dict[str, dict[str, Any]] = {}
        for scope, items in (("global", global_items), ("character", character_items), ("costume", costume_items)):
            for row in items:
                merged[row["id"]] = {**row, "scope": scope}
        return {
            "global": {"items": global_items},
            "character": {"items": character_items},
            "costume": {"items": costume_items},
            "merged": {"items": list(merged.values())},
            "paths": {
                "character": str(self._scoped_checklist_path("character", character, phase)),
                "costume": str(self._scoped_checklist_path("costume", character, phase, costume)),
            },
        }

    def save_scoped_checklist(
        self, scope: str, character: str, phase: str, costume: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        if not character or not phase:
            raise PromptEvolutionError("Character and phase are required.")
        items = self._validated_checklist_items(payload)
        path = self._scoped_checklist_path(scope, character, phase, costume)
        self._write_json(path, {
            "version": 3,
            "scope": {"kind": scope, "character": character, "phase": phase, **({"costume": costume} if scope == "costume" else {})},
            "items": items,
        })
        return self.scoped_checklists(character, phase, costume)

    def options(self, character: str, phase: str) -> dict[str, Any]:
        assets = []
        for asset in self.app.list_assets(character, phase):
            if asset.pipeline != "Costume-Dressing" or not asset.costume:
                continue
            try:
                path = self.app.path_service.locked_image_path(asset)
            except ValueError:
                continue
            if path.is_file():
                assets.append({
                    "asset_id": asset.asset_id,
                    "costume": asset.costume,
                    "view": asset.body_view,
                    "image_path": str(path.resolve()),
                })
        profiles_path = self.project_root / "Config" / "Local_Render_Presets.json"
        profiles = self._read_json(profiles_path) if profiles_path.is_file() else {}
        stable_profiles = sorted(name for name, value in profiles.items() if isinstance(value, dict) and value.get("backend") == "stable_matrix")
        return {"assets": assets, "profiles": stable_profiles, "width": CANVAS_WIDTH, "height": CANVAS_HEIGHT}

    def _source_asset(self, character: str, phase: str, costume: str, view: str):
        matches = [
            asset for asset in self.app.list_assets(character, phase)
            if asset.pipeline == "Costume-Dressing"
            and str(asset.costume or "") == costume
            and asset.body_view == view
            and asset.final_image_output
            and self.app.path_service.locked_image_path(asset).is_file()
        ]
        if len(matches) != 1:
            raise PromptEvolutionError(
                f"Expected one locked Costume-Dressing asset for {character}/{phase}/{costume}/{view}; found {len(matches)}."
            )
        return matches[0]

    def reference_preview(self, character: str, phase: str, costume: str, view: str) -> bytes:
        asset = self._source_asset(character, phase, costume, view)
        with tempfile.TemporaryDirectory(prefix="zet_prompt_evolution_preview_") as temp_dir:
            output = Path(temp_dir) / "reference.png"
            self._reference_derivative(self.app.path_service.locked_image_path(asset), output, self._detection_tolerance(character, phase, costume))
            return output.read_bytes()

    def _detection_tolerance(self, character: str, phase: str, costume: str) -> float:
        for row in self.app.turnaround_service.list_rows(character, phase):
            if row.source_pipeline == "Costume-Dressing" and row.costume == costume:
                return float(row.detection_tolerance)
        return DEFAULT_DETECTION_TOLERANCE

    @staticmethod
    def _content_bbox(image: Image.Image) -> tuple[int, int, int, int] | None:
        rgba = image.convert("RGBA")
        if rgba.getextrema()[3][0] < 255:
            bbox = rgba.getchannel("A").getbbox()
            if bbox:
                return bbox
        rgb = rgba.convert("RGB")
        corners = [rgb.getpixel(point) for point in ((0, 0), (rgb.width - 1, 0), (0, rgb.height - 1), (rgb.width - 1, rgb.height - 1))]
        background = tuple(sorted(pixel[channel] for pixel in corners)[len(corners) // 2] for channel in range(3))
        mask = Image.new("L", rgb.size)
        mask.putdata([
            255 if max(abs(pixel[channel] - background[channel]) for channel in range(3)) > 28 else 0
            for pixel in rgb.get_flattened_data()
        ])
        bbox = mask.getbbox()
        if not bbox:
            return None
        area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
        return bbox if area >= image.width * image.height * 0.03 else None

    def _reference_derivative(self, source: Path, destination: Path, tolerance: float = DEFAULT_DETECTION_TOLERANCE) -> dict[str, Any]:
        with Image.open(source) as opened:
            image = opened.convert("RGB")
        try:
            analysis = CharacterGridService().analyze_image(source, CharacterGridOptions(tolerance=tolerance), None)
            bbox = analysis.bbox
        except Exception:
            bbox = self._content_bbox(image)
        target_ratio = CANVAS_WIDTH / CANVAS_HEIGHT
        fallback = bbox is None
        if bbox is None:
            crop_width = min(image.width, int(round(image.height * target_ratio)))
            crop_height = min(image.height, int(round(image.width / target_ratio)))
            if crop_width / crop_height > target_ratio:
                crop_width = int(round(crop_height * target_ratio))
            else:
                crop_height = int(round(crop_width / target_ratio))
            left = max(0, (image.width - crop_width) // 2)
            top = max(0, (image.height - crop_height) // 2)
            crop = (left, top, left + crop_width, top + crop_height)
            derivative = image.crop(crop).resize((CANVAS_WIDTH, CANVAS_HEIGHT), Image.Resampling.LANCZOS)
            placement = [0, 0, CANVAS_WIDTH, CANVAS_HEIGHT]
        else:
            pad_x = max(24, round((bbox[2] - bbox[0]) * REFERENCE_PADDING_RATIO))
            pad_y = max(24, round((bbox[3] - bbox[1]) * REFERENCE_PADDING_RATIO))
            content_left, content_top = max(0, bbox[0] - pad_x), max(0, bbox[1] - pad_y)
            content_right, content_bottom = min(image.width, bbox[2] + pad_x), min(image.height, bbox[3] + pad_y)
            crop = (content_left, content_top, content_right, content_bottom)
            derivative = image.crop(crop)
            derivative.thumbnail((CANVAS_WIDTH, CANVAS_HEIGHT), Image.Resampling.LANCZOS)
            left = (CANVAS_WIDTH - derivative.width) // 2
            top = (CANVAS_HEIGHT - derivative.height) // 2
            placement = [left, top, left + derivative.width, top + derivative.height]
            canvas = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), (128, 128, 128))
            canvas.paste(derivative, (left, top))
            derivative = canvas
        destination.parent.mkdir(parents=True, exist_ok=True)
        derivative.save(destination, "PNG")
        return {
            "source_size": [image.width, image.height], "output_size": [CANVAS_WIDTH, CANVAS_HEIGHT],
            "subject_bounds": list(bbox) if bbox else None, "crop_box": list(crop),
            "crop_method": "center_fallback" if fallback else "turnaround_bbox_padded_contain",
            "detection_tolerance": tolerance, "padding_ratio": REFERENCE_PADDING_RATIO,
            "placement_box": placement,
        }

    def create_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        character, phase = str(payload.get("character") or ""), str(payload.get("phase") or "")
        costume, view = str(payload.get("costume") or ""), str(payload.get("view") or "")
        asset = self._source_asset(character, phase, costume, view)
        batch_size, total_batches = int(payload.get("batch_size", 6)), int(payload.get("total_batches", 5))
        if not 2 <= batch_size <= 10 or not 2 <= total_batches <= 20:
            raise PromptEvolutionError("Batch size must be 2–10 and total batches must be 2–20.")
        fixed_seed_count = int(payload.get("fixed_seed_count", 3))
        if not 1 <= fixed_seed_count < batch_size:
            raise PromptEvolutionError("Fixed seed count must be at least 1 and less than the batch size.")
        cfg_scale, steps = float(payload.get("cfg_scale", 7.0)), int(payload.get("steps", 25))
        if not 0 <= cfg_scale <= 30 or not 1 <= steps <= 150:
            raise PromptEvolutionError("CFG must be 0–30 and steps must be 1–150.")
        if str(self.app.config.local_render_backend).lower() != "stable_matrix":
            raise PromptEvolutionError("Prompt Evolution currently requires the Stable Matrix backend.")
        profile = str(payload.get("profile") or self.app.config.local_render_preset)
        if profile not in self.options(character, phase)["profiles"]:
            raise PromptEvolutionError(f"Unknown Stable Matrix render profile: {profile}")
        templates = {name: self.template(name) for name in TEMPLATE_NAMES}
        checklist = self.scoped_checklists(character, phase, costume)["merged"]
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        root = self.app.path_service.pipeline_path(asset) / "Prompt_Evolution" / run_id
        root.mkdir(parents=True)
        source = self.app.path_service.locked_image_path(asset)
        derivative = root / "reference_768x1024.png"
        crop = self._reference_derivative(source, derivative, self._detection_tolerance(character, phase, costume))
        self._write_json(root / "template_snapshot.json", templates)
        self._write_json(root / "checklist_snapshot.json", checklist)
        generator = random.SystemRandom()
        seeds: list[int] = []
        while len(seeds) < batch_size:
            value = generator.randrange(0, 2**63 - 1)
            if value not in seeds:
                seeds.append(value)
        fixed_seeds, fresh_seeds = seeds[:fixed_seed_count], seeds[fixed_seed_count:]
        created_at = self._now()
        run = {
            "version": RUN_VERSION,
            "run_id": run_id, "root": str(root.resolve()), "asset_id": asset.asset_id,
            "character": character, "phase": phase, "costume": costume, "view": view,
            "source_image": str(source.resolve()), "reference_image": str(derivative.resolve()), "crop": crop,
            "critic_model_a": str(payload.get("critic_model_a") or DEFAULT_VISION_MODEL),
            "critic_model_b": str(payload.get("critic_model_b") or DEFAULT_CHECKLIST_MODEL),
            "analysis_model": str(payload.get("analysis_model") or DEFAULT_VISION_MODEL),
            "check_model": str(payload.get("check_model") or DEFAULT_CHECKLIST_MODEL),
            "checkpoint": str(payload.get("checkpoint") or self.app.config.local_render_checkpoint),
            "profile": profile,
            "cfg_scale": cfg_scale, "steps": steps,
            "width": CANVAS_WIDTH, "height": CANVAS_HEIGHT, "batch_size": batch_size,
            "fixed_seed_count": fixed_seed_count, "total_batches": total_batches,
            "fixed_seeds": fixed_seeds, "fresh_seeds": fresh_seeds, "seeds": seeds,
            "status": "BOOTSTRAPPING", "current_batch": 0,
            "selected_prompt_version": None,
            "created_at": created_at, "updated_at": created_at, "error": "",
            "activity_log": [{
                "at": created_at, "level": "info",
                "message": f"Run created with {batch_size} images per batch and {total_batches} configured batches.",
            }],
        }
        self._write_json(root / "run.json", run)
        positive, negative = str(payload.get("positive_prompt") or "").strip(), str(payload.get("negative_prompt") or "").strip()
        if positive:
            self._start_batch(run, positive, negative)
        else:
            self._queue_bootstrap(run)
        return self.detail(run_id)

    def _queue_ollama(
        self, run: dict[str, Any], *, task: str, prompt: str, output: Path, images: list[Path], model: str | None = None,
        response_schema: dict[str, Any] | None = None, temperature: float | None = None,
    ) -> str:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        queue_order = "01" if task.startswith("critic_") else "02" if task.startswith("check_") else "00"
        ask_id = f"Ask_Prompt_Evolution_{run['run_id']}_{queue_order}_{task}_{stamp}"
        staging = self.proxy.create_staging(ask_id)
        image_names = []
        for index, source in enumerate(images, 1):
            name = f"image_{index}{source.suffix.lower() or '.png'}"
            shutil.copy2(source, staging / name)
            image_names.append(name)
        (staging / "OLLAMA_PROMPT.md").write_text(prompt, encoding="utf-8")
        raw_output_name = f"{output.name}.raw.txt"
        manifest = {
            "version": AI_PROXY_PROTOCOL_VERSION, "ask_id": ask_id, "asset_id": None,
            "character": run["character"], "phase": run["phase"], "pipeline": "Prompt-Evolution",
            "pipeline_stage": task.upper(), "ollama_attempt_id": stamp, "worker_type": "ollama_generate",
            "ollama_model": model or run["analysis_model"], "prompt_file": "OLLAMA_PROMPT.md", "image_files": image_names,
            "json_output": True, "expected_output": raw_output_name, "task_type": f"prompt_evolution_{task}",
            "auxiliary": True, "target_output_dir": str(output.parent.resolve()), "target_output_file": output.name,
            "prompt_evolution_run_id": run["run_id"],
        }
        if response_schema is not None:
            manifest["response_schema"] = response_schema
        if temperature is not None:
            manifest["ollama_temperature"] = temperature
        (staging / "ask_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        self.proxy.publish(staging, ask_id, "ollama_generate")
        selected_model = model or run["analysis_model"]
        batch_number = int(run.get("current_batch", 0)) + 1
        parts = task.split("_")
        if len(parts) >= 3 and parts[0] == "critic":
            message = f"Batch {batch_number} — queued seed {parts[-1]} for Critic {parts[1].upper()} visual comparison ({selected_model})."
        elif len(parts) >= 2 and parts[0] == "check":
            message = f"Batch {batch_number} — queued seed {parts[-1]} for regression checks ({selected_model})."
        elif task == "batch_synthesis":
            message = f"Batch {batch_number} — queued cross-seed analysis ({selected_model})."
        elif task.startswith("prompt_diagnosis"):
            message = f"Batch {batch_number} — queued prompt diagnosis ({selected_model})."
        elif task.startswith("prompt_edit"):
            message = f"Batch {batch_number} — queued conservative prompt edit ({selected_model})."
        elif task == "bootstrap":
            message = f"Queued initial prompt generation ({selected_model})."
        elif task.startswith("repair_"):
            message = f"Queued JSON repair for {task.removeprefix('repair_')} ({selected_model})."
        elif task == "directed_refinement":
            message = f"Queued directed prompt refinement ({selected_model})."
        else:
            message = f"Queued {task.replace('_', ' ')} ({selected_model})."
        self._log(run, message, task=task, ask_id=ask_id, model=selected_model)
        return ask_id

    def _format_template(self, run: dict[str, Any], name: str, values: dict[str, str]) -> str:
        templates = self._read_json(Path(run["root"]) / "template_snapshot.json")
        text = str(templates.get(name) or self.template(name))
        for key, value in values.items():
            text = text.replace("{{" + key + "}}", value)
        return text

    @staticmethod
    def _checklist_questions(checklist: dict[str, Any]) -> str:
        return json.dumps([
            {"id": str(row["id"]), "question": str(row["question"])}
            for row in checklist.get("items", [])
        ], ensure_ascii=False)

    @staticmethod
    def _regression_check_schema(configured_ids: list[str]) -> dict[str, Any]:
        count = len(configured_ids)
        return {
            "type": "object", "required": ["checks"], "properties": {"checks": {
                "type": "array", "minItems": count, "maxItems": count, "uniqueItems": True,
                "items": {
                    "type": "object", "required": ["id", "pass", "confidence", "evidence"],
                    "properties": {
                        "id": {"type": "string", "enum": configured_ids},
                        "pass": {"type": ["boolean", "null"]}, "confidence": {"type": "number"},
                        "evidence": {"type": "string"},
                    },
                },
            }},
        }

    def _queue_bootstrap(self, run: dict[str, Any], prior_error: str = "") -> None:
        root = Path(run["root"])
        prompt = self._format_template(run, "bootstrap", {
            "METADATA": "", "METADATA_WORD_POOL": "",
        })
        if prior_error:
            prompt += f"\n\nThe prior response was rejected: {prior_error}\nReturn only a corrected response that fixes this rejection."
        run["bootstrap_ask_id"] = self._queue_ollama(
            run, task="bootstrap_retry" if prior_error else "bootstrap", prompt=prompt, output=root / "bootstrap.json", images=[Path(run["reference_image"])],
            model=run["analysis_model"], response_schema=BOOTSTRAP_SCHEMA, temperature=0,
        )
        self._save_run(run)

    def _save_run(self, run: dict[str, Any]) -> None:
        run["updated_at"] = self._now()
        self._write_json(Path(run["root"]) / "run.json", run)

    def _llm_json(self, run: dict[str, Any], path: Path) -> dict[str, Any]:
        try:
            return self._read_json(path)
        except json.JSONDecodeError:
            repair_path = path.with_name(f"{path.stem}.repair.json")
            if repair_path.is_file():
                return self._read_json(repair_path)
            marker = path.with_name(f".{path.stem}.repair-queued")
            if not marker.exists():
                self._log(run, f"Rejected malformed JSON in {path.name}; preparing a repair request.", "warning", file=path.name)
                prompt = self._format_template(run, "repair", {
                    "REQUEST": path.stem,
                    "RESPONSE": path.read_text(encoding="utf-8", errors="replace"),
                })
                repair_model = str(run.get("check_model") or DEFAULT_CHECKLIST_MODEL) if path.stem.startswith("regression_check_") else None
                self._queue_ollama(
                    run, task=f"repair_{path.stem}", prompt=prompt, output=repair_path, images=[], model=repair_model,
                )
                marker.write_text(self._now(), encoding="utf-8")
                self._save_run(run)
            raise PromptEvolutionRepairPending(f"Waiting for JSON repair: {path.name}")

    def _prompt_json(self, run: dict[str, Any], path: Path) -> tuple[str, str]:
        data = self._llm_json(run, path)
        positive_terms = self._atomic_terms(data.get("positive_terms"))
        negative_terms = self._atomic_terms(data.get("negative_terms"))
        positive = ", ".join(positive_terms) if positive_terms else self._clean_prompt_terms(data.get("positive_prompt") or data.get("positive_core") or "")
        negative = ", ".join(negative_terms) if negative_terms else self._clean_prompt_terms(data.get("negative_prompt") or data.get("negative_core") or "")
        if not positive:
            retry_prefix = f"{int(run.get('current_batch', 0))}:"
            retry_used = any(
                key.startswith(retry_prefix) and key.rsplit(":", 1)[-1] in {"BOOTSTRAPPING", "DIRECTED_REFINING"}
                for key, count in run.get("validation_retries", {}).items() if int(count) >= 1
            )
            if retry_used:
                positive = "character matching the canonical reference image"
                self._log(run, f"Bootstrap retry still omitted a positive prompt; using a conservative fallback for {path.name}.", "warning")
                self._save_run(run)
                return positive, negative
            raise PromptEvolutionError(f"LLM response omitted positive_prompt: {path}")
        return positive, negative

    @staticmethod
    def _atomic_terms(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        terms = [term.strip() for item in value for term in str(item).split(",") if term.strip()]
        unique: list[str] = []
        seen: set[str] = set()
        for term in terms:
            normalized = " ".join(term.casefold().split())
            if normalized not in seen:
                seen.add(normalized)
                unique.append(term)
        return unique

    @staticmethod
    def _clean_prompt_terms(value: Any) -> str:
        return ", ".join(term for item in str(value).split(",") if (term := item.strip()))

    @staticmethod
    def _compose_prompt(core: str, wrapper: tuple[str, ...]) -> str:
        result: list[str] = []
        seen: set[str] = set()
        for term in [*(item.strip() for item in core.split(",") if item.strip()), *wrapper]:
            key = " ".join(term.casefold().split())
            if key not in seen:
                seen.add(key)
                result.append(term)
        return ", ".join(result)

    def _start_batch(self, run: dict[str, Any], positive: str, negative: str) -> None:
        positive_core = self._clean_prompt_terms(positive)
        negative_core = self._clean_prompt_terms(negative)
        if not positive_core:
            raise PromptEvolutionError("Positive prompt core cannot be empty.")
        positive = self._compose_prompt(positive_core, EVALUATION_POSITIVE_TERMS)
        negative = self._compose_prompt(negative_core, EVALUATION_NEGATIVE_TERMS)
        index = int(run["current_batch"])
        batch = Path(run["root"]) / "batches" / f"{index:03d}"
        batch.mkdir(parents=True, exist_ok=True)
        prompt_path = batch / "Prompt.md"
        prompt_path.write_text(f"Prompt: {positive}\nNegative: {negative}\n", encoding="utf-8")
        asks = []
        manifest = {
            "ask_id": f"PromptEvolution_{run['run_id']}_{index}", "asset_id": run["asset_id"],
            "character": run["character"], "phase": run["phase"], "pipeline": "Prompt-Evolution", "pipeline_stage": "RENDER",
        }
        self._log(run, f"Batch {index + 1} — starting renders for {len(run['seeds'])} seeds.", batch=index + 1)
        for seed in run["seeds"]:
            ask_path = self.app.ai_proxy_service.stage_render_task_local_render_ask(
                manifest, prompt_path, batch, allow_parallel=True, seed=seed, checkpoint=run["checkpoint"],
                render_overrides={"width": CANVAS_WIDTH, "height": CANVAS_HEIGHT, "cfg_scale": run["cfg_scale"], "steps": run["steps"]},
                render_preset=run["profile"],
            )
            ask = self._read_json(ask_path / "ask_manifest.json")
            asks.append({"ask_id": ask["ask_id"], "seed": seed, "file": str(batch / "Local_Test_Renders" / ask["expected_output"])})
            self._log(run, f"Batch {index + 1} — queued render for seed {seed}.", batch=index + 1, seed=seed, ask_id=ask["ask_id"])
        fixed = set(int(seed) for seed in run["fixed_seeds"])
        batch_payload = {
            "version": RUN_VERSION, "index": index, "prompt_version_id": f"prompt-{index:03d}",
            "positive_prompt": positive, "negative_prompt": negative,
            "positive_core": positive_core, "negative_core": negative_core,
            "evaluation_wrapper": {"positive_terms": list(EVALUATION_POSITIVE_TERMS), "negative_terms": list(EVALUATION_NEGATIVE_TERMS)},
            "renders": [{**item, "seed_role": "fixed" if int(item["seed"]) in fixed else "fresh"} for item in asks],
            "status": "RENDERING",
        }
        self._write_json(batch / "batch.json", batch_payload)
        run["status"] = "RENDERING"
        self._save_run(run)

    def advance_run(self, run_id: str) -> dict[str, Any]:
        run = self._find_run(run_id)
        lock = Path(run["root"]) / ".advance.lock"
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(descriptor)
        except FileExistsError:
            if self._now_timestamp() - lock.stat().st_mtime <= 120:
                return self.detail(run_id)
            lock.unlink(missing_ok=True)
            return self.advance_run(run_id)
        try:
            return self._advance_v3_unlocked(run_id)
        finally:
            lock.unlink(missing_ok=True)

    @staticmethod
    def _now_timestamp() -> float:
        return datetime.now().timestamp()

    @staticmethod
    def _array(data: dict[str, Any], name: str) -> list[Any]:
        value = data.get(name)
        if not isinstance(value, list):
            raise PromptEvolutionError(f"LLM response omitted array: {name}")
        return value

    @classmethod
    def _validate_visual_report(
        cls, data: dict[str, Any], *, lenient: bool = False, warnings: list[str] | None = None,
    ) -> dict[str, Any]:
        if lenient:
            for name in ("major_differences", "secondary_differences"):
                value = data.get(name)
                if not isinstance(value, list):
                    (warnings if warnings is not None else []).append(f"Visual critic omitted {name}; assumed an empty list.")
                    value = []
                valid = [item for item in value if isinstance(item, dict) and str(item.get("reference") or "").strip() and str(item.get("candidate") or "").strip()]
                if len(valid) != len(value):
                    (warnings if warnings is not None else []).append(f"Ignored {len(value) - len(valid)} malformed {name} items.")
                data[name] = valid
            value = data.get("stable_matches")
            if not isinstance(value, list):
                (warnings if warnings is not None else []).append("Visual critic omitted stable_matches; assumed an empty list.")
                value = []
            data["stable_matches"] = [item.strip() for item in value if isinstance(item, str) and item.strip()]
            if len(data["stable_matches"]) != len(value):
                (warnings if warnings is not None else []).append("Ignored malformed stable_matches items.")
            return data
        for name in ("major_differences", "secondary_differences"):
            for item in cls._array(data, name):
                if not isinstance(item, dict) or not str(item.get("reference") or "").strip() or not str(item.get("candidate") or "").strip():
                    raise PromptEvolutionError(f"Visual critic returned an invalid {name} item.")
        for item in cls._array(data, "stable_matches"):
            if not isinstance(item, str) or not item.strip():
                raise PromptEvolutionError("Visual critic returned an invalid stable match.")
        return data

    @classmethod
    def _validate_synthesis(
        cls, data: dict[str, Any], *, lenient: bool = False, warnings: list[str] | None = None,
    ) -> dict[str, Any]:
        if lenient:
            warning_list = warnings if warnings is not None else []
            for name in ("recurrent_deviations", "intermittent_deviations", "isolated_deviations"):
                value = data.get(name)
                if not isinstance(value, list):
                    warning_list.append(f"Synthesis omitted {name}; assumed an empty list.")
                    value = []
                valid = []
                for item in value:
                    if not isinstance(item, dict) or not str(item.get("finding") or "").strip():
                        continue
                    valid.append({**item, "seeds": item.get("seeds") if isinstance(item.get("seeds"), list) else [], "observer_agreement": item.get("observer_agreement") if item.get("observer_agreement") in {"single", "dual"} else "single"})
                if len(valid) != len(value):
                    warning_list.append(f"Ignored malformed {name} findings.")
                data[name] = valid
            for name in ("stable_successes", "cross_feature_patterns"):
                value = data.get(name)
                if not isinstance(value, list):
                    warning_list.append(f"Synthesis omitted {name}; assumed an empty list.")
                    value = []
                data[name] = [item.strip() for item in value if isinstance(item, str) and item.strip()]
            value = data.get("next_round_priorities")
            if not isinstance(value, list):
                warning_list.append("Synthesis omitted next_round_priorities; assumed no remaining priorities.")
                value = []
            priorities = []
            for item in value:
                if not isinstance(item, dict) or not str(item.get("problem") or "").strip():
                    continue
                priorities.append({
                    **item,
                    "evidence": str(item.get("evidence") or "No evidence text supplied.").strip(),
                    "seeds": item.get("seeds") if isinstance(item.get("seeds"), list) else [],
                    "observer_agreement": item.get("observer_agreement") if item.get("observer_agreement") in {"single", "dual"} else "single",
                })
            if len(priorities) != len(value):
                warning_list.append("Ignored malformed next-round priorities.")
            if len(priorities) > 3:
                warning_list.append("Synthesis returned more than three priorities; kept the first three.")
            data["next_round_priorities"] = priorities[:3]
            return data
        for name in ("recurrent_deviations", "intermittent_deviations", "isolated_deviations", "stable_successes", "cross_feature_patterns", "next_round_priorities"):
            cls._array(data, name)
        if len(data["next_round_priorities"]) > 3:
            raise PromptEvolutionError("Synthesis returned more than three priorities.")
        for name in ("recurrent_deviations", "intermittent_deviations", "isolated_deviations"):
            for item in data[name]:
                if not isinstance(item, dict) or not str(item.get("finding") or "").strip() or item.get("observer_agreement") not in {"single", "dual"} or not isinstance(item.get("seeds"), list):
                    raise PromptEvolutionError(f"Synthesis returned an invalid {name} finding.")
        for item in data["next_round_priorities"]:
            if not isinstance(item, dict) or not str(item.get("problem") or "").strip() or not str(item.get("evidence") or "").strip() or item.get("observer_agreement") not in {"single", "dual"} or not isinstance(item.get("seeds"), list):
                raise PromptEvolutionError("Synthesis returned an invalid next-round priority.")
        if any(not isinstance(item, str) or not item.strip() for name in ("stable_successes", "cross_feature_patterns") for item in data[name]):
            raise PromptEvolutionError("Synthesis returned an invalid stable success or cross-feature pattern.")
        return data

    @classmethod
    def _validate_checks(
        cls, data: dict[str, Any], configured_ids: set[str], *, lenient: bool = False, warnings: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        if lenient and not isinstance(data.get("checks"), list):
            (warnings if warnings is not None else []).append("Regression-check response omitted checks; assumed all results indeterminate.")
            data["checks"] = []
        checks = cls._array(data, "checks")
        returned: list[str] = []
        for item in checks:
            if not isinstance(item, dict):
                returned.append("")
                continue
            item_id = str(item.get("id") or "").strip()
            if item_id not in configured_ids and item_id.endswith("]") and "[" in item_id:
                bracketed_id = item_id.rsplit("[", 1)[1][:-1].strip()
                if bracketed_id in configured_ids:
                    item_id = bracketed_id
                    item["id"] = item_id
            returned.append(item_id)
        if lenient:
            warning_list = warnings if warnings is not None else []
            by_id: dict[str, dict[str, Any]] = {}
            for item, item_id in zip(checks, returned):
                if not isinstance(item, dict) or item_id not in configured_ids or item_id in by_id:
                    continue
                passed = item.get("pass")
                if passed not in {True, False, None}:
                    passed = None
                    warning_list.append(f"Regression check {item_id} returned an invalid pass value; assumed indeterminate.")
                try:
                    confidence = min(1.0, max(0.0, float(item.get("confidence", 0))))
                except (TypeError, ValueError):
                    confidence = 0.0
                    warning_list.append(f"Regression check {item_id} returned invalid confidence; assumed 0.")
                by_id[item_id] = {**item, "id": item_id, "pass": passed, "confidence": confidence, "evidence": str(item.get("evidence") or "No evidence supplied.")}
            missing = sorted(configured_ids - set(by_id))
            if missing:
                warning_list.append(f"Regression checks omitted IDs {', '.join(missing)}; assumed indeterminate.")
            if len(by_id) != len(checks):
                warning_list.append("Ignored unknown or duplicate regression-check results.")
            return [by_id.get(item_id, {"id": item_id, "pass": None, "confidence": 0.0, "evidence": "No result returned."}) for item_id in sorted(configured_ids)]
        if set(returned) != configured_ids or len(returned) != len(configured_ids):
            expected = ", ".join(sorted(configured_ids)) or "none"
            received = ", ".join(returned) or "none"
            raise PromptEvolutionError(
                f"Regression-check response must return every configured ID exactly once (expected: {expected}; received: {received})."
            )
        for item in checks:
            try:
                valid_confidence = 0 <= float(item.get("confidence", -1)) <= 1
            except (TypeError, ValueError, AttributeError):
                valid_confidence = False
            if not isinstance(item, dict) or item.get("pass") not in {True, False, None} or not valid_confidence:
                raise PromptEvolutionError("Regression-check response returned an invalid result.")
        return checks

    @classmethod
    def _validate_diagnosis(
        cls, data: dict[str, Any], *, lenient: bool = False, warnings: list[str] | None = None,
    ) -> dict[str, Any]:
        if lenient:
            warning_list = warnings if warnings is not None else []
            interventions = data.get("interventions")
            if not isinstance(interventions, list):
                warning_list.append("Diagnosis omitted interventions; assumed no usable interventions.")
                data["interventions"] = []
                return data
            normalized = []
            for index, raw in enumerate(interventions[:3], 1):
                if not isinstance(raw, dict) or not str(raw.get("proposed_wording") or "").strip():
                    warning_list.append(f"Ignored diagnosis intervention {index} because it had no usable proposed wording.")
                    continue
                item = dict(raw)
                item["id"] = str(item.get("id") or f"normalized-{index}").strip()
                item["prompt"] = item.get("prompt") if item.get("prompt") in {"positive", "negative"} else "positive"
                if raw.get("prompt") not in {"positive", "negative"}:
                    warning_list.append(f"Intervention {item['id']} omitted a valid prompt target; assumed positive.")
                item["action"] = item.get("action") if item.get("action") in {"add", "replace", "delete"} else "add"
                if raw.get("action") not in {"add", "replace", "delete"}:
                    warning_list.append(f"Intervention {item['id']} omitted a valid action; assumed add.")
                if item["action"] in {"replace", "delete"} and not str(item.get("relevant_wording") or "").strip():
                    if item["action"] == "replace":
                        item["action"] = "add"
                        warning_list.append(f"Intervention {item['id']} omitted relevant_wording; treated replace as add.")
                    else:
                        warning_list.append(f"Ignored delete intervention {item['id']} because relevant_wording was missing.")
                        continue
                item["relevant_wording"] = str(item.get("relevant_wording") or "")
                for key in ("observed_pattern", "diagnosis", "rationale", "regression_risk"):
                    if not str(item.get(key) or "").strip():
                        item[key] = "Not supplied."
                        warning_list.append(f"Intervention {item['id']} omitted {key}; used a neutral default.")
                if item.get("confidence") not in {"High", "Medium", "Low"}:
                    item["confidence"] = "Low"
                    warning_list.append(f"Intervention {item['id']} omitted valid confidence; assumed Low.")
                normalized.append(item)
            if len(interventions) > 3:
                warning_list.append("Diagnosis returned more than three interventions; kept the first three.")
            data["interventions"] = normalized
            return data
        interventions = cls._array(data, "interventions")
        if len(interventions) > 3:
            raise PromptEvolutionError("Diagnosis returned more than three interventions.")
        allowed = {"add", "replace", "delete"}
        for item in interventions:
            if not isinstance(item, dict) or item.get("confidence") not in {"High", "Medium", "Low"}:
                raise PromptEvolutionError("Diagnosis returned an invalid confidence.")
            if item.get("prompt") not in {"positive", "negative"} or item.get("action") not in allowed:
                raise PromptEvolutionError("Diagnosis returned an invalid prompt intervention.")
            for key in ("id", "observed_pattern", "diagnosis", "proposed_wording", "rationale", "regression_risk"):
                if not str(item.get(key) or "").strip():
                    raise PromptEvolutionError(f"Diagnosis intervention omitted {key}.")
            if item["action"] in {"replace", "delete"} and not str(item.get("relevant_wording") or "").strip():
                raise PromptEvolutionError("Replace/delete interventions require relevant_wording.")
        return data

    @classmethod
    def _validate_edit(
        cls, data: dict[str, Any], positive: str, negative: str, allowed_ids: set[str], *,
        lenient: bool = False, warnings: list[str] | None = None,
    ) -> dict[str, Any]:
        new_positive = cls._clean_prompt_terms(data.get("positive_core") or "")
        new_negative = cls._clean_prompt_terms(data.get("negative_core") or "")
        if lenient:
            warning_list = warnings if warnings is not None else []
            if not new_positive:
                new_positive = cls._clean_prompt_terms(positive)
                warning_list.append("Prompt editor omitted the positive core; retained the prior positive core.")
            if "negative_core" not in data:
                new_negative = cls._clean_prompt_terms(negative)
                warning_list.append("Prompt editor omitted the negative core; retained the prior negative core.")
            changes = data.get("changes")
            if not isinstance(changes, list):
                changes = []
                warning_list.append("Prompt editor omitted its change log; retained the prompt cores it returned.")
            valid_changes = [item for item in changes if isinstance(item, dict) and str(item.get("intervention_id") or "") in allowed_ids][:3]
            if len(valid_changes) != len(changes):
                warning_list.append("Ignored malformed, ineligible, or excess prompt-editor change records.")
            return {**data, "positive_core": new_positive, "negative_core": new_negative, "changes": valid_changes}
        changes = cls._array(data, "changes")
        if not new_positive or (new_positive == cls._clean_prompt_terms(positive) and new_negative == cls._clean_prompt_terms(negative)):
            raise PromptEvolutionError("Prompt editor returned empty or unchanged cores.")
        if not 1 <= len(changes) <= 3:
            raise PromptEvolutionError("Prompt editor must return one to three changes.")
        if any(not isinstance(item, dict) or str(item.get("intervention_id") or "") not in allowed_ids for item in changes):
            raise PromptEvolutionError("Prompt editor used an ineligible intervention.")
        return {**data, "positive_core": new_positive, "negative_core": new_negative}

    @staticmethod
    def _new_fresh_seeds(run: dict[str, Any]) -> list[int]:
        generator = random.SystemRandom()
        used = set(int(seed) for seed in run["fixed_seeds"])
        result = []
        while len(result) < int(run["batch_size"]) - int(run["fixed_seed_count"]):
            seed = generator.randrange(0, 2**63 - 1)
            if seed not in used:
                used.add(seed)
                result.append(seed)
        return result

    def _finish_v3(self, run: dict[str, Any], reason: str) -> None:
        run["stop_reason"] = reason
        run["status"] = "AWAITING_FINAL_REVIEW"
        self._log(run, f"Automatic evolution finished: {reason}")
        self._save_run(run)

    def _log_validation_warnings(self, run: dict[str, Any], warnings: list[str]) -> None:
        batch_number = int(run.get("current_batch", 0)) + 1
        for warning in warnings:
            self._log(run, f"Batch {batch_number} — validation warning: {warning}", "warning", batch=batch_number)

    def _retry_observation_output(
        self, run: dict[str, Any], batch: dict[str, Any], item: dict[str, Any], kind: str, error: str,
    ) -> bool:
        seed = int(item["seed"])
        batch_number = int(run.get("current_batch", 0)) + 1
        retry_key = f"{batch_number - 1}:OBSERVING:{kind}:{seed}"
        retries = run.setdefault("validation_retries", {})
        label = f"Critic {kind[-1].upper()}" if kind.startswith("critic_") else "regression check"
        if int(retries.get(retry_key, 0)) >= 1:
            run["failed_observation"] = {"kind": kind, "seed": seed}
            self._log(run, f"Batch {batch_number} — {label} response for seed {seed} was rejected again: {error}", "error", batch=batch_number, seed=seed)
            return False
        retries[retry_key] = 1
        self._log(run, f"Batch {batch_number} — rejected {label} response for seed {seed}: {error}", "warning", batch=batch_number, seed=seed)
        if kind.startswith("critic_"):
            role = kind.removeprefix("critic_")
            record = item["critics"][role]
            model = run[f"critic_model_{role}"]
            prompt = self._format_template(run, "visual_critic", {"SEED": str(seed), "CRITIC_ROLE": role.upper()})
            task = f"critic_{role}_{seed}"
            schema = VISUAL_REPORT_SCHEMA
        else:
            record = item["check"]
            checklist = self._read_json(Path(run["root"]) / "checklist_snapshot.json")
            configured_ids = [str(row["id"]) for row in checklist.get("items", [])]
            prompt = self._format_template(run, "regression_check", {
                "SEED": str(seed), "CHECKS": self._checklist_questions(checklist),
            })
            model = run["check_model"]
            task = f"check_{seed}"
            schema = self._regression_check_schema(configured_ids)
        output = Path(record["output"])
        self._archive_rejected_output(output)
        prompt += f"\n\nThe prior response was rejected: {error}\nReturn only a corrected response for this request."
        record["ask_id"] = self._queue_ollama(
            run, task=task, prompt=prompt, output=output,
            images=[Path(run["reference_image"]), Path(item["file"])], model=model,
            response_schema=schema, temperature=0,
        )
        record["retry_count"] = int(record.get("retry_count", 0)) + 1
        batch["status"] = "OBSERVING"
        run["status"] = "OBSERVING"
        self._write_json(Path(run["root"]) / "batches" / f"{batch_number - 1:03d}" / "batch.json", batch)
        self._save_run(run)
        return True

    def _retry_v3_validation(self, run: dict[str, Any], stage: str, error: str) -> bool:
        retries = run.setdefault("validation_retries", {})
        key = f"{int(run.get('current_batch', 0))}:{stage}"
        if int(retries.get(key, 0)) >= 1:
            return False
        retries[key] = 1
        root = Path(run["root"])
        if stage == "BOOTSTRAPPING":
            self._archive_rejected_output(root / "bootstrap.json")
            self._log(run, f"Rejected bootstrapping output; queued one corrected retry: {error}", "warning")
            run["last_validation_retry"] = {"stage": stage, "error": error, "at": self._now()}
            self._queue_bootstrap(run, error)
            return True
        if stage == "OBSERVING":
            return False
        if stage == "DIRECTED_REFINING":
            directed = run.get("directed_refinement") or {}
            self._archive_rejected_output(Path(str(directed.get("output") or "")))
            output = root / "directed_refinement.retry.json"
            core = self._read_json(root / "prompt_core.json")
            prompt = self._format_template(run, "directed_refinement", {
                "POSITIVE_PROMPT": str(core["positive_core"]), "NEGATIVE_PROMPT": str(core["negative_core"]),
                "METADATA": "", "METADATA_WORD_POOL": "", "INSTRUCTIONS": str(directed.get("instructions") or ""),
            }) + f"\n\nThe prior response was rejected: {error}\nReturn only a corrected response that fixes this rejection."
            directed.update({"output": str(output), "ask_id": self._queue_ollama(
                run, task="directed_refinement_retry", prompt=prompt, output=output, images=[Path(run["reference_image"])],
                model=run["analysis_model"], response_schema=PROMPT_CORE_SCHEMA, temperature=0,
            )})
            run["directed_refinement"] = directed
            self._log(run, f"Rejected directed refinement output; queued one corrected retry: {error}", "warning")
            run["last_validation_retry"] = {"stage": stage, "error": error, "at": self._now()}
            self._save_run(run)
            return True
        batch_path = root / "batches" / f"{int(run['current_batch']):03d}"
        batch = self._read_json(batch_path / "batch.json")
        if stage == "SYNTHESIZING":
            self._archive_rejected_output(Path(batch["synthesis"]["output"]))
            output = batch_path / "batch_synthesis.retry.json"
            prompt = self._format_template(run, "batch_synthesis", {
                "BATCH_EVIDENCE": json.dumps(batch.get("candidates", []), ensure_ascii=False),
            }) + f"\n\nThe prior response was rejected: {error}\nReturn only a corrected response that fixes this rejection."
            batch["synthesis"] = {"output": str(output), "ask_id": self._queue_ollama(
                run, task="batch_synthesis_retry", prompt=prompt, output=output, images=[], model=run["analysis_model"],
                response_schema=SYNTHESIS_SCHEMA, temperature=0,
            )}
            batch["status"] = "SYNTHESIZING"
            run["status"] = "SYNTHESIZING"
        elif stage == "DIAGNOSING":
            output = batch_path / "prompt_diagnosis.retry.json"
            prompt = self._format_template(run, "prompt_diagnosis", {
                "POSITIVE_CORE": batch["positive_core"], "NEGATIVE_CORE": batch["negative_core"],
                "SYNTHESIS": json.dumps(batch["synthesis"], ensure_ascii=False),
            }) + f"\n\nThe prior response was rejected: {error}"
            batch["diagnosis"] = {"output": str(output), "ask_id": self._queue_ollama(
                run, task="prompt_diagnosis_retry", prompt=prompt, output=output,
                images=[Path(run["reference_image"])], model=run["analysis_model"], response_schema=DIAGNOSIS_SCHEMA, temperature=0,
            )}
            batch["status"] = "DIAGNOSING"
            run["status"] = "DIAGNOSING"
        elif stage == "EDITING":
            eligible = [item for item in batch["diagnosis"]["interventions"] if item["confidence"] == "High"]
            output = batch_path / "prompt_edit.retry.json"
            prompt = self._format_template(run, "prompt_edit", {
                "POSITIVE_CORE": batch["positive_core"], "NEGATIVE_CORE": batch["negative_core"],
                "INTERVENTIONS": json.dumps(eligible, ensure_ascii=False),
                "STABLE_SUCCESSES": json.dumps(batch["synthesis"].get("stable_successes", []), ensure_ascii=False),
            }) + f"\n\nThe prior response was rejected: {error}"
            batch["edit"] = {"output": str(output), "ask_id": self._queue_ollama(
                run, task="prompt_edit_retry", prompt=prompt, output=output, images=[], model=run["analysis_model"],
                response_schema=EDIT_SCHEMA, temperature=0,
            )}
            batch["status"] = "EDITING"
            run["status"] = "EDITING"
        else:
            return False
        self._log(run, f"Batch {int(run.get('current_batch', 0)) + 1} — rejected {stage.lower()} output; queued one automatic retry: {error}", "warning")
        run["last_validation_retry"] = {"stage": stage, "error": error, "at": self._now()}
        self._write_json(batch_path / "batch.json", batch)
        self._save_run(run)
        return True

    def _advance_v3_unlocked(self, run_id: str) -> dict[str, Any]:
        run = self._find_run(run_id)
        if run["status"] in {"COMPLETE", "ABORTED", "FAILED", "AWAITING_PROMPT_REVIEW", "AWAITING_FINAL_REVIEW"}:
            return self.detail(run_id)
        try:
            root = Path(run["root"])
            if run["status"] == "BOOTSTRAPPING" and (root / "bootstrap.json").is_file():
                self._start_batch(run, *self._prompt_json(run, root / "bootstrap.json"))
            elif run["status"] == "RENDERING":
                batch_path = root / "batches" / f"{int(run['current_batch']):03d}"
                batch = self._read_json(batch_path / "batch.json")
                if all(Path(item["file"]).is_file() for item in batch["renders"]):
                    checks = self._read_json(root / "checklist_snapshot.json")
                    questions = self._checklist_questions(checks)
                    configured_ids = [str(row["id"]) for row in checks.get("items", [])]
                    self._log(run, f"Batch {int(run['current_batch']) + 1} — all renders completed; queueing independent visual reviews and regression checks.")
                    observations = []
                    for render in batch["renders"]:
                        item = {"seed": render["seed"], "seed_role": render["seed_role"], "file": render["file"], "critics": {}}
                        for role, model in (("a", run["critic_model_a"]), ("b", run["critic_model_b"])):
                            output = batch_path / f"visual_critic_{role}_{render['seed']}.json"
                            prompt = self._format_template(run, "visual_critic", {"SEED": str(render["seed"]), "CRITIC_ROLE": role.upper()})
                            item["critics"][role] = {"output": str(output), "ask_id": self._queue_ollama(
                                run, task=f"critic_{role}_{render['seed']}", prompt=prompt, output=output,
                                images=[Path(run["reference_image"]), Path(render["file"])], model=model,
                                response_schema=VISUAL_REPORT_SCHEMA, temperature=0,
                            )}
                        if questions:
                            output = batch_path / f"regression_check_{render['seed']}.json"
                            prompt = self._format_template(run, "regression_check", {"SEED": str(render["seed"]), "CHECKS": questions})
                            item["check"] = {"output": str(output), "ask_id": self._queue_ollama(
                                run, task=f"check_{render['seed']}", prompt=prompt, output=output,
                                images=[Path(run["reference_image"]), Path(render["file"])], model=run["check_model"],
                                response_schema=self._regression_check_schema(configured_ids), temperature=0,
                            )}
                        observations.append(item)
                    batch.update({"observations": observations, "status": "OBSERVING"})
                    self._write_json(batch_path / "batch.json", batch)
                    run["status"] = "OBSERVING"
                    self._save_run(run)
            elif run["status"] == "OBSERVING":
                batch_path = root / "batches" / f"{int(run['current_batch']):03d}"
                batch = self._read_json(batch_path / "batch.json")
                outputs = [Path(role["output"]) for item in batch["observations"] for role in item["critics"].values()]
                outputs += [Path(item["check"]["output"]) for item in batch["observations"] if item.get("check")]
                if all(path.is_file() for path in outputs):
                    self._log(run, f"Batch {int(run['current_batch']) + 1} — analyzing critic reports and regression-check responses.")
                    evidence = []
                    for item in batch["observations"]:
                        critics = {}
                        for role, record in item["critics"].items():
                            retry_key = f"{int(run['current_batch'])}:OBSERVING:critic_{role}:{int(item['seed'])}"
                            lenient = int(run.get("validation_retries", {}).get(retry_key, 0)) >= 1
                            warnings: list[str] = []
                            try:
                                critics[role] = self._validate_visual_report(
                                    self._llm_json(run, Path(record["output"])), lenient=lenient, warnings=warnings,
                                )
                            except PromptEvolutionError as exc:
                                if self._retry_observation_output(run, batch, item, f"critic_{role}", str(exc)):
                                    return self.detail(run_id)
                                raise
                            self._log_validation_warnings(run, warnings)
                        check = self._llm_json(run, Path(item["check"]["output"])) if item.get("check") else {"checks": []}
                        configured_ids = {str(row["id"]) for row in self._read_json(root / "checklist_snapshot.json").get("items", [])}
                        retry_key = f"{int(run['current_batch'])}:OBSERVING:check:{int(item['seed'])}"
                        lenient = int(run.get("validation_retries", {}).get(retry_key, 0)) >= 1
                        warnings = []
                        try:
                            checked = self._validate_checks(check, configured_ids, lenient=lenient, warnings=warnings) if item.get("check") else []
                        except PromptEvolutionError as exc:
                            if self._retry_observation_output(run, batch, item, "check", str(exc)):
                                return self.detail(run_id)
                            raise
                        self._log_validation_warnings(run, warnings)
                        row = {"seed": item["seed"], "seed_role": item["seed_role"], "file": item["file"], "critics": critics, "checks": checked}
                        evidence.append(row)
                    self._log(run, f"Batch {int(run['current_batch']) + 1} — all observation responses accepted; queueing cross-seed analysis.")
                    batch["candidates"] = evidence
                    synthesis_output = batch_path / "batch_synthesis.json"
                    synthesis_prompt = self._format_template(run, "batch_synthesis", {"BATCH_EVIDENCE": json.dumps(evidence, ensure_ascii=False)})
                    batch["synthesis"] = {"output": str(synthesis_output), "ask_id": self._queue_ollama(
                        run, task="batch_synthesis", prompt=synthesis_prompt, output=synthesis_output, images=[], model=run["analysis_model"],
                        response_schema=SYNTHESIS_SCHEMA, temperature=0,
                    )}
                    batch["status"] = "SYNTHESIZING"
                    self._write_json(batch_path / "batch.json", batch)
                    run["status"] = "SYNTHESIZING"
                    self._save_run(run)
            elif run["status"] == "SYNTHESIZING":
                batch_path = root / "batches" / f"{int(run['current_batch']):03d}"
                batch = self._read_json(batch_path / "batch.json")
                output = Path(batch["synthesis"]["output"])
                if output.is_file():
                    retry_key = f"{int(run['current_batch'])}:SYNTHESIZING"
                    warnings = []
                    synthesis = self._validate_synthesis(
                        self._llm_json(run, output),
                        lenient=int(run.get("validation_retries", {}).get(retry_key, 0)) >= 1,
                        warnings=warnings,
                    )
                    self._log_validation_warnings(run, warnings)
                    self._log(run, f"Batch {int(run['current_batch']) + 1} — cross-seed analysis accepted.")
                    batch["synthesis"] = synthesis
                    self._write_json(batch_path / "batch.json", batch)
                    if int(run["current_batch"]) + 1 >= int(run["total_batches"]):
                        batch["status"] = "REVIEWED"
                        self._write_json(batch_path / "batch.json", batch)
                        self._finish_v3(run, "Configured batch limit reached.")
                    elif not synthesis["next_round_priorities"]:
                        batch["status"] = "REVIEWED"
                        self._write_json(batch_path / "batch.json", batch)
                        self._finish_v3(run, "No prompt-level priority remained.")
                    else:
                        diagnosis_output = batch_path / "prompt_diagnosis.json"
                        diagnosis_prompt = self._format_template(run, "prompt_diagnosis", {
                            "POSITIVE_CORE": batch["positive_core"], "NEGATIVE_CORE": batch["negative_core"],
                            "SYNTHESIS": json.dumps(synthesis, ensure_ascii=False),
                        })
                        batch["diagnosis"] = {"output": str(diagnosis_output), "ask_id": self._queue_ollama(
                            run, task="prompt_diagnosis", prompt=diagnosis_prompt, output=diagnosis_output,
                            images=[Path(run["reference_image"])], model=run["analysis_model"], response_schema=DIAGNOSIS_SCHEMA, temperature=0,
                        )}
                        batch["status"] = "DIAGNOSING"
                        self._write_json(batch_path / "batch.json", batch)
                        run["status"] = "DIAGNOSING"
                        self._save_run(run)
            elif run["status"] == "DIAGNOSING":
                batch_path = root / "batches" / f"{int(run['current_batch']):03d}"
                batch = self._read_json(batch_path / "batch.json")
                output = Path(batch["diagnosis"]["output"])
                if output.is_file():
                    retry_key = f"{int(run['current_batch'])}:DIAGNOSING"
                    warnings = []
                    diagnosis = self._validate_diagnosis(
                        self._llm_json(run, output),
                        lenient=int(run.get("validation_retries", {}).get(retry_key, 0)) >= 1,
                        warnings=warnings,
                    )
                    self._log_validation_warnings(run, warnings)
                    eligible = [item for item in diagnosis["interventions"] if item["confidence"] == "High"]
                    self._log(run, f"Batch {int(run['current_batch']) + 1} — diagnosis accepted with {len(eligible)} high-confidence interventions.")
                    batch["diagnosis"] = diagnosis
                    self._write_json(batch_path / "batch.json", batch)
                    if not eligible:
                        batch["status"] = "REVIEWED"
                        self._write_json(batch_path / "batch.json", batch)
                        self._finish_v3(run, "No high-confidence intervention was available.")
                    else:
                        edit_output = batch_path / "prompt_edit.json"
                        edit_prompt = self._format_template(run, "prompt_edit", {
                            "POSITIVE_CORE": batch["positive_core"], "NEGATIVE_CORE": batch["negative_core"],
                            "INTERVENTIONS": json.dumps(eligible, ensure_ascii=False),
                            "STABLE_SUCCESSES": json.dumps(batch["synthesis"].get("stable_successes", []), ensure_ascii=False),
                        })
                        batch["edit"] = {"output": str(edit_output), "ask_id": self._queue_ollama(
                            run, task="prompt_edit", prompt=edit_prompt, output=edit_output, images=[], model=run["analysis_model"],
                            response_schema=EDIT_SCHEMA, temperature=0,
                        )}
                        batch["status"] = "EDITING"
                        self._write_json(batch_path / "batch.json", batch)
                        run["status"] = "EDITING"
                        self._save_run(run)
            elif run["status"] == "EDITING":
                batch_path = root / "batches" / f"{int(run['current_batch']):03d}"
                batch = self._read_json(batch_path / "batch.json")
                output = Path(batch["edit"]["output"])
                if output.is_file():
                    eligible_ids = {str(item["id"]) for item in batch["diagnosis"]["interventions"] if item["confidence"] == "High"}
                    retry_key = f"{int(run['current_batch'])}:EDITING"
                    warnings = []
                    edit = self._validate_edit(
                        self._llm_json(run, output), batch["positive_core"], batch["negative_core"], eligible_ids,
                        lenient=int(run.get("validation_retries", {}).get(retry_key, 0)) >= 1,
                        warnings=warnings,
                    )
                    self._log_validation_warnings(run, warnings)
                    self._log(run, f"Batch {int(run['current_batch']) + 1} — proposed prompt edit is ready for review.")
                    batch["edit"] = edit
                    batch["status"] = "AWAITING_PROMPT_REVIEW"
                    self._write_json(batch_path / "batch.json", batch)
                    run["status"] = "AWAITING_PROMPT_REVIEW"
                    self._save_run(run)
            elif run["status"] == "DIRECTED_REFINING":
                directed = run.get("directed_refinement") or {}
                output = Path(str(directed.get("output") or ""))
                if output.is_file():
                    positive, negative = self._prompt_json(run, output)
                    payload = {key: run[key] for key in (
                        "character", "phase", "costume", "view", "critic_model_a", "critic_model_b", "analysis_model", "check_model",
                        "checkpoint", "profile", "cfg_scale", "steps", "batch_size", "fixed_seed_count", "total_batches",
                    )}
                    new_run = self.create_run(payload | {"positive_prompt": positive, "negative_prompt": negative})
                    directed.update({"status": "COMPLETE", "new_run_id": new_run["run_id"]})
                    run["directed_refinement"] = directed
                    run["status"] = "COMPLETE"
                    self._save_run(run)
        except PromptEvolutionRepairPending:
            pass
        except Exception as exc:
            failed_stage = run["status"]
            self._log(run, f"Batch {int(run.get('current_batch', 0)) + 1} — {failed_stage.lower()} error: {exc}", "error")
            if failed_stage == "OBSERVING" or not self._retry_v3_validation(run, failed_stage, str(exc)):
                run["failed_stage"] = failed_stage
                run["status"], run["error"] = "FAILED", str(exc)
                self._save_run(run)
        return self.detail(run_id)

    def abort(self, run_id: str) -> dict[str, Any]:
        run = self._find_run(run_id)
        run["status"] = "ABORTED"
        self._log(run, "Run aborted by the user.", "warning")
        self._save_run(run)
        return self.detail(run_id)

    def accept_prompt_review(self, run_id: str, positive_core: str, negative_core: str) -> dict[str, Any]:
        run = self._find_run(run_id)
        if run["status"] != "AWAITING_PROMPT_REVIEW":
            raise PromptEvolutionError("Run is not awaiting prompt review.")
        positive = self._clean_prompt_terms(positive_core)
        negative = self._clean_prompt_terms(negative_core)
        if not positive:
            raise PromptEvolutionError("Positive prompt core cannot be empty.")
        batch_path = Path(run["root"]) / "batches" / f"{int(run['current_batch']):03d}"
        batch = self._read_json(batch_path / "batch.json")
        proposed = batch.get("edit") or {}
        batch["prompt_review"] = {
            "reviewed_at": self._now(),
            "proposed_positive_core": proposed.get("positive_core", ""),
            "proposed_negative_core": proposed.get("negative_core", ""),
            "accepted_positive_core": positive,
            "accepted_negative_core": negative,
            "manually_edited": positive != proposed.get("positive_core") or negative != proposed.get("negative_core"),
        }
        batch["status"] = "REVIEWED"
        self._write_json(batch_path / "batch.json", batch)
        self._log(run, f"Batch {int(run['current_batch']) + 1} — prompt review accepted; preparing the next batch.")
        run["fresh_seeds"] = self._new_fresh_seeds(run)
        run["seeds"] = [*run["fixed_seeds"], *run["fresh_seeds"]]
        run["current_batch"] = int(run["current_batch"]) + 1
        self._start_batch(run, positive, negative)
        return self.detail(run_id)

    def rename(self, run_id: str, name: str) -> dict[str, Any]:
        run = self._find_run(run_id)
        run["display_name"] = name.strip()[:120]
        self._save_run(run)
        return self.detail(run_id)

    def start_directed_refinement(self, run_id: str, instructions: str) -> dict[str, Any]:
        run = self._find_run(run_id)
        if run["status"] != "COMPLETE" or not run.get("selected_prompt_version"):
            raise PromptEvolutionError("Directed refinement requires a completed run with a selected prompt version.")
        if not instructions.strip():
            raise PromptEvolutionError("Directed refinement instructions are required.")
        root = Path(run["root"])
        output = root / f"directed_refinement_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.json"
        core = self._read_json(root / "prompt_core.json")
        prompt = self._format_template(run, "directed_refinement", {
            "POSITIVE_PROMPT": str(core["positive_core"]),
            "NEGATIVE_PROMPT": str(core["negative_core"]),
            "METADATA": "",
            "METADATA_WORD_POOL": "", "INSTRUCTIONS": instructions.strip(),
        })
        ask_id = self._queue_ollama(
            run, task="directed_refinement", prompt=prompt, output=output, images=[Path(run["reference_image"])],
            model=run["analysis_model"], response_schema=PROMPT_CORE_SCHEMA, temperature=0,
        )
        run["directed_refinement"] = {"status": "QUEUED", "instructions": instructions.strip(), "ask_id": ask_id, "output": str(output)}
        run["status"] = "DIRECTED_REFINING"
        self._save_run(run)
        return self.detail(run_id)

    def delete(self, run_id: str) -> dict[str, Any]:
        run = self._find_run(run_id)
        if run["status"] in {"BOOTSTRAPPING", "RENDERING", "OBSERVING", "SYNTHESIZING", "DIAGNOSING", "EDITING", "DIRECTED_REFINING", "AWAITING_PROMPT_REVIEW", "AWAITING_FINAL_REVIEW"}:
            raise PromptEvolutionError("Abort the active run before deleting it.")
        root = Path(run["root"]).resolve()
        pipeline_root = Path(self.app.config.base_pipeline_path).resolve()
        if not root.is_relative_to(pipeline_root) or root.parent.name != "Prompt_Evolution" or root.name != run_id:
            raise PromptEvolutionError("Refusing to delete an invalid prompt-evolution run path.")
        if root.is_symlink() or (hasattr(root, "is_junction") and root.is_junction()):
            raise PromptEvolutionError("Refusing to delete a linked prompt-evolution run path.")
        shutil.rmtree(root)
        return {"deleted": True, "run_id": run_id}

    @staticmethod
    def _optional_json(path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    def _audit_proxy_records(self, run_id: str) -> list[tuple[str, Path]]:
        paths = AIProxyPathService(self.app.config)
        prefix = f"Ask_Prompt_Evolution_{run_id}_"
        records: list[tuple[str, Path]] = []
        for state, root in (("ask", paths.ask_root()), ("running", paths.running_root()), ("answer", paths.answer_root())):
            if root.is_dir():
                records.extend((state, path) for path in root.iterdir() if path.is_dir() and path.name.startswith(prefix))
        archive = paths.harvested_archive_root()
        if archive.is_dir():
            records.extend(("harvested", path) for path in archive.glob(f"*/{prefix}*") if path.is_dir())
        return sorted(records, key=lambda item: (
            str(self._optional_json(item[1] / "job.json").get("created_at") or ""), item[1].name,
        ))

    def create_audit_bundle(self, run_id: str) -> Path:
        run = self._find_run(run_id)
        root = Path(run["root"]).resolve()
        if not root.is_dir():
            raise FileNotFoundError(f"Prompt-evolution run workspace not found: {root}")
        descriptor, temp_name = tempfile.mkstemp(prefix=f"zet_prompt_evolution_{run_id}_", suffix="_audit.zip")
        os.close(descriptor)
        destination = Path(temp_name)
        inventory: list[dict[str, Any]] = []
        warnings: list[str] = []

        def add_file(bundle: zipfile.ZipFile, source: Path, archive_name: str) -> None:
            if source.is_symlink() or not source.is_file():
                return
            try:
                bundle.write(source, archive_name)
                inventory.append({"path": archive_name, "size": source.stat().st_size})
            except (FileNotFoundError, OSError) as exc:
                warnings.append(f"Could not include {source}: {exc}")

        def add_tree(bundle: zipfile.ZipFile, source_root: Path, archive_root: str) -> None:
            for current, directories, files in os.walk(source_root, followlinks=False):
                current_path = Path(current)
                directories[:] = [name for name in directories if not (current_path / name).is_symlink()]
                for name in sorted(files):
                    source = current_path / name
                    relative = source.relative_to(source_root).as_posix()
                    add_file(bundle, source, f"{archive_root}/{relative}")

        try:
            with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
                add_tree(bundle, root, "run")
                source_image = Path(str(run.get("source_image") or ""))
                if source_image.is_file() and not source_image.is_relative_to(root):
                    add_file(bundle, source_image, f"inputs/locked_source{source_image.suffix.lower()}")
                proxy_records = []
                events = [{"at": run.get("created_at"), "event": "run_created", "status": run.get("status")}]
                for state, record_path in self._audit_proxy_records(run_id):
                    archive_root = f"proxy/{state}/{record_path.name}"
                    add_tree(bundle, record_path, archive_root)
                    ask = self._optional_json(record_path / "ask_manifest.json")
                    job = self._optional_json(record_path / "job.json")
                    answer = self._optional_json(record_path / "answer_manifest.json")
                    harvest = self._optional_json(record_path / "harvest_manifest.json")
                    proxy_records.append({
                        "state": state, "bundle_path": archive_root, "ask_id": ask.get("ask_id") or record_path.name,
                        "task_type": ask.get("task_type"), "model": ask.get("ollama_model"),
                        "created_at": job.get("created_at"), "started_at": answer.get("started_at"),
                        "completed_at": answer.get("completed_at"), "harvested_at": harvest.get("harvested_at"),
                        "status": answer.get("status"), "error_type": answer.get("error_type"),
                        "error_message": answer.get("error_message"),
                    })
                    for timestamp_key, event in (
                        ("created_at", "ask_created"), ("started_at", "ask_started"),
                        ("completed_at", "ask_completed"), ("harvested_at", "answer_harvested"),
                    ):
                        timestamp = proxy_records[-1].get(timestamp_key)
                        if timestamp:
                            events.append({"at": timestamp, "event": event, "ask_id": proxy_records[-1]["ask_id"], "task_type": ask.get("task_type")})
                batches = []
                for batch_path in sorted((root / "batches").glob("*/batch.json")) if (root / "batches").is_dir() else []:
                    batches.append(self._optional_json(batch_path))
                events.sort(key=lambda item: (str(item.get("at") or ""), str(item.get("ask_id") or ""), item["event"]))
                manifest = {
                    "version": 1, "generated_at": self._now(), "run_id": run_id,
                    "description": "Self-contained Prompt Evolution audit bundle. Exact LLM prompts, attachments, responses, and transport manifests are under proxy/.",
                    "run": run, "batches": batches, "proxy_records": proxy_records,
                    "events": events, "files": inventory, "warnings": warnings,
                }
                bundle.writestr("audit_manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        return destination

    def clone_from_batch(self, run_id: str, batch_index: int) -> dict[str, Any]:
        run = self._find_run(run_id)
        batch_path = Path(run["root"]) / "batches" / f"{int(batch_index):03d}" / "batch.json"
        if not batch_path.is_file():
            raise PromptEvolutionError(f"Batch does not exist: {batch_index}")
        batch = self._read_json(batch_path)
        settings = {
            key: run[key] for key in ("character", "phase", "costume", "view", "critic_model_a", "critic_model_b", "analysis_model", "check_model", "checkpoint", "profile", "cfg_scale", "steps", "batch_size", "fixed_seed_count", "total_batches") if key in run
        }
        settings["batch_size"] = max(2, int(settings.get("batch_size", 5)))
        settings["total_batches"] = max(2, int(settings.get("total_batches", 5)))
        return self.create_run(settings | {
            "positive_prompt": batch.get("positive_core", batch["positive_prompt"]),
            "negative_prompt": batch.get("negative_core", batch["negative_prompt"]),
        })

    def restart(self, run_id: str) -> dict[str, Any]:
        run = self._find_run(run_id)
        if run["status"] not in {"COMPLETE", "ABORTED", "FAILED", "AWAITING_FINAL_REVIEW"}:
            raise PromptEvolutionError("Only terminal prompt-evolution runs can be restarted.")
        settings = {
            key: run[key]
            for key in (
                "character", "phase", "costume", "view", "critic_model_a", "critic_model_b", "analysis_model", "check_model", "checkpoint", "profile",
                "cfg_scale", "steps", "batch_size", "fixed_seed_count", "total_batches",
            )
            if key in run
        }
        settings["batch_size"] = max(2, int(settings.get("batch_size", 5)))
        settings["total_batches"] = max(2, int(settings.get("total_batches", 5)))
        restarted = self.create_run(settings)
        fresh = self._find_run(restarted["run_id"])
        fresh["restarted_from_run_id"] = run_id
        if run.get("display_name"):
            fresh["display_name"] = f"{run['display_name']} — restarted"
        self._save_run(fresh)
        return self.detail(fresh["run_id"])

    def retry(self, run_id: str) -> dict[str, Any]:
        run = self._find_run(run_id)
        if run["status"] != "FAILED":
            raise PromptEvolutionError("Only failed runs can be retried.")
        run["error"] = ""
        for path in Path(run["root"]).glob("**/*.repair.json"):
            path.unlink(missing_ok=True)
        for path in Path(run["root"]).glob("**/.*.repair-queued"):
            path.unlink(missing_ok=True)
        failed_stage = str(run.pop("failed_stage", "RENDERING"))
        retry_prefix = f"{int(run.get('current_batch', 0))}:{failed_stage}"
        retry_used = any(key == retry_prefix or key.startswith(f"{retry_prefix}:") for key in run.get("validation_retries", {}))
        message = (
            f"Resuming {failed_stage.lower()} with lenient validation; no additional LLM retry was queued."
            if retry_used else f"Resuming {failed_stage.lower()}; one corrected LLM retry remains available if validation rejects the response."
        )
        self._log(run, message, "warning")
        run["status"] = failed_stage
        run.pop("failed_observation", None)
        self._save_run(run)
        return self.advance_run(run_id)

    def _run_paths(self) -> list[Path]:
        base = Path(self.app.config.base_pipeline_path)
        return sorted(base.glob("**/Prompt_Evolution/*/run.json"), reverse=True) if base.exists() else []

    def _find_run(self, run_id: str) -> dict[str, Any]:
        for path in self._run_paths():
            if path.parent.name == run_id:
                run = self._read_json(path)
                if int(run.get("version", 0)) == RUN_VERSION:
                    return run
                break
        raise FileNotFoundError(f"Prompt-evolution run not found: {run_id}")

    def list_runs(self) -> list[dict[str, Any]]:
        runs = [self._read_json(path) for path in self._run_paths()]
        return [run for run in runs if int(run.get("version", 0)) == RUN_VERSION]

    def detail(self, run_id: str) -> dict[str, Any]:
        run = self._find_run(run_id)
        batches = []
        for path in sorted((Path(run["root"]) / "batches").glob("*/batch.json")) if (Path(run["root"]) / "batches").exists() else []:
            batches.append(self._read_json(path))
        versions = [{
            "prompt_version_id": batch["prompt_version_id"],
            "fixed_renders": [item for item in batch.get("renders", []) if item.get("seed_role") == "fixed"],
            "fresh_renders": [item for item in batch.get("renders", []) if item.get("seed_role") == "fresh"],
        } for batch in batches]
        random.Random(f"{run_id}:prompt-versions").shuffle(versions)
        return {**run, "batches": batches, "prompt_versions": versions}

    def select_prompt_version(self, run_id: str, prompt_version_id: str, selection_reason: str = "") -> dict[str, Any]:
        run = self._find_run(run_id)
        if run["status"] != "AWAITING_FINAL_REVIEW":
            raise PromptEvolutionError("Run is not awaiting final review.")
        batches = [self._read_json(path) for path in sorted((Path(run["root"]) / "batches").glob("*/batch.json"))]
        selected = next((batch for batch in batches if batch.get("prompt_version_id") == prompt_version_id), None)
        if selected is None:
            raise PromptEvolutionError("Unknown prompt version.")
        run["selected_prompt_version"] = prompt_version_id
        run["selection_reason"] = selection_reason.strip()
        run["status"] = "COMPLETE"
        self._log(run, f"Selected {prompt_version_id} as the final prompt version.")
        root = Path(run["root"])
        self._write_json(root / "prompt_core.json", {
            "version": RUN_VERSION, "prompt_version_id": prompt_version_id,
            "positive_core": selected["positive_core"], "negative_core": selected["negative_core"],
            "checkpoint": run.get("checkpoint", ""),
        })
        self._write_json(root / "evaluation_wrapper.json", selected["evaluation_wrapper"])
        self._save_run(run)
        return self.detail(run_id)

    def advance_active_runs(self) -> list[dict[str, Any]]:
        results = []
        for run in self.list_runs():
            if run["status"] not in {"COMPLETE", "ABORTED", "FAILED", "AWAITING_PROMPT_REVIEW", "AWAITING_FINAL_REVIEW"}:
                results.append(self.advance_run(run["run_id"]))
        return results
