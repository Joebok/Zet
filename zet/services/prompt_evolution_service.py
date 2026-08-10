from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import random
import re
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
IDENTITY_FLOOR = 6
MINIMUM_SCORE_IMPROVEMENT = 0.1
STRATEGY_VERSION = 2
DEFAULT_VISION_MODEL = "qwen3.5-prompt-evo"
DEFAULT_CHECKLIST_MODEL = "qwen3-VL-prompt-evo"
TEMPLATE_NAMES = ("bootstrap", "evaluation", "checklist_evaluation", "ranking", "repair", "refinement", "directed_refinement")
CHARACTER_SCORE_CATEGORIES = ("face_shape", "eyes", "hair", "species_markers", "body_proportions")
COSTUME_SCORE_CATEGORIES = ("silhouette_layering", "garment_pieces", "colors", "accessories_footwear")
CATEGORY_DISPLAY_NAMES = {
    "face_shape": "Face shape", "eyes": "Eyes", "hair": "Hair", "species_markers": "Species markers",
    "body_proportions": "Body proportions", "silhouette_layering": "Silhouette/layering",
    "garment_pieces": "Garments", "colors": "Colors", "accessories_footwear": "Accessories/footwear",
}
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

    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat(timespec="seconds")

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
        categories = set(CHARACTER_SCORE_CATEGORIES + COSTUME_SCORE_CATEGORIES)
        validated = []
        for row in items:
            if not isinstance(row, dict):
                raise PromptEvolutionError("Each checklist item must be an object.")
            item = str(row.get("item") or row.get("question") or "").strip()
            question = str(row.get("question") or "").strip()
            correction = str(row.get("correction") or "").strip()
            item_id = str(row.get("id") or "").strip()
            category = str(row.get("category") or "").strip()
            try:
                max_rating = float(row.get("max_rating"))
            except (TypeError, ValueError) as exc:
                raise PromptEvolutionError(f"Checklist item '{item or 'unnamed'}' requires a numeric max_rating.") from exc
            if not item or category not in categories or not 0 <= max_rating <= 10:
                raise PromptEvolutionError(
                    "Checklist items require text, a known score category, and a max_rating from 0 to 10."
                )
            validated.append({
                "id": item_id or f"legacy-{len(validated) + 1}",
                "item": item,
                "question": question,
                "correction": correction,
                "category": category,
                "max_rating": int(max_rating) if max_rating.is_integer() else max_rating,
            })
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
                merged[row["item"].casefold()] = {**row, "scope": scope}
        return {
            "global": {"items": global_items},
            "character": {"items": character_items},
            "costume": {"items": costume_items},
            "merged": {"items": list(merged.values())},
            "paths": {
                "character": str(self._scoped_checklist_path("character", character, phase)),
                "costume": str(self._scoped_checklist_path("costume", character, phase, costume)),
            },
            "categories": list(CHARACTER_SCORE_CATEGORIES + COSTUME_SCORE_CATEGORIES),
        }

    def save_scoped_checklist(
        self, scope: str, character: str, phase: str, costume: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        if not character or not phase:
            raise PromptEvolutionError("Character and phase are required.")
        items = self._validated_checklist_items(payload)
        path = self._scoped_checklist_path(scope, character, phase, costume)
        self._write_json(path, {
            "version": 2,
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

    def _metadata(self, character: str, phase: str, costume: str, view: str, mode: str) -> dict[str, Any]:
        labels = {"character": character, "phase": phase, "costume": costume, "view": view}
        if mode == "image_only":
            return {}
        if mode == "labels":
            return labels
        if mode != "curated":
            raise PromptEvolutionError("Metadata mode must be image_only, labels, or curated.")
        view_token = self.app.character_source_service.views.normalize_token(view)
        options = self.app.character_source_service.options(character, phase)
        costume_row = next((item for item in options["costumes"] if item["label"] == costume), None)
        if costume_row is None:
            raise PromptEvolutionError(f"Costume metadata is unavailable: {costume}")
        snapshot = self.app.character_source_service.compile(
            character=character, phase=phase, costume_slug=costume_row["value"], view_token=view_token,
            selected_sections=("identity anchors", "face", "hair", "eyes", "ears", "body proportions", "selected costume", "view/orientation requirements"),
            reference_tags=(),
        )
        source_snapshot = snapshot.get("source_snapshot", {})
        return {
            **labels,
            "selected_sections": source_snapshot.get("selected_sections", {}) if isinstance(source_snapshot, dict) else {},
        }

    def create_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        character, phase = str(payload.get("character") or ""), str(payload.get("phase") or "")
        costume, view = str(payload.get("costume") or ""), str(payload.get("view") or "")
        asset = self._source_asset(character, phase, costume, view)
        batch_size, total_batches = int(payload.get("batch_size", 5)), int(payload.get("total_batches", 5))
        if not 2 <= batch_size <= 10 or not 2 <= total_batches <= 20:
            raise PromptEvolutionError("Batch size must be 2–10 and total batches must be 2–20.")
        cfg_scale, steps = float(payload.get("cfg_scale", 7.0)), int(payload.get("steps", 25))
        mode = str(payload.get("mode") or "auto")
        if not 0 <= cfg_scale <= 30 or not 1 <= steps <= 150:
            raise PromptEvolutionError("CFG must be 0–30 and steps must be 1–150.")
        if mode not in {"auto", "manual"}:
            raise PromptEvolutionError("Run mode must be auto or manual.")
        if str(self.app.config.local_render_backend).lower() != "stable_matrix":
            raise PromptEvolutionError("Prompt Evolution currently requires the Stable Matrix backend.")
        profile = str(payload.get("profile") or self.app.config.local_render_preset)
        if profile not in self.options(character, phase)["profiles"]:
            raise PromptEvolutionError(f"Unknown Stable Matrix render profile: {profile}")
        metadata_snapshot = self._metadata(
            character, phase, costume, view, str(payload.get("metadata_mode") or "curated")
        )
        templates = {name: self.template(name) for name in TEMPLATE_NAMES}
        checklist = self.scoped_checklists(character, phase, costume)["merged"]
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        root = self.app.path_service.pipeline_path(asset) / "Prompt_Evolution" / run_id
        root.mkdir(parents=True)
        source = self.app.path_service.locked_image_path(asset)
        derivative = root / "reference_768x1024.png"
        crop = self._reference_derivative(source, derivative, self._detection_tolerance(character, phase, costume))
        self._write_json(root / "metadata_snapshot.json", metadata_snapshot)
        self._write_json(root / "template_snapshot.json", templates)
        self._write_json(root / "checklist_snapshot.json", checklist)
        generator = random.SystemRandom()
        seeds: list[int] = []
        while len(seeds) < batch_size:
            value = generator.randrange(0, 2**63 - 1)
            if value not in seeds:
                seeds.append(value)
        run = {
            "version": 2, "strategy_version": STRATEGY_VERSION,
            "run_id": run_id, "root": str(root.resolve()), "asset_id": asset.asset_id,
            "character": character, "phase": phase, "costume": costume, "view": view,
            "source_image": str(source.resolve()), "reference_image": str(derivative.resolve()), "crop": crop,
            "model": str(payload.get("model") or DEFAULT_VISION_MODEL),
            "checklist_model": str(payload.get("checklist_model") or DEFAULT_CHECKLIST_MODEL),
            "checkpoint": str(payload.get("checkpoint") or self.app.config.local_render_checkpoint),
            "profile": profile,
            "cfg_scale": cfg_scale, "steps": steps,
            "width": CANVAS_WIDTH, "height": CANVAS_HEIGHT, "batch_size": batch_size,
            "total_batches": total_batches, "mode": mode,
            "metadata_mode": str(payload.get("metadata_mode") or "curated"), "seeds": seeds,
            "status": "BOOTSTRAPPING", "current_batch": 0, "incumbent": None,
            "exploration_incumbent": None, "finalists": [], "rejected_mutations": [],
            "created_at": self._now(), "updated_at": self._now(), "error": "",
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
        queue_order = "01" if task.startswith("evaluate_") else "02" if task.startswith("checklist_") else "00"
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
            "ollama_model": model or run["model"], "prompt_file": "OLLAMA_PROMPT.md", "image_files": image_names,
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
        return ask_id

    def _format_template(self, run: dict[str, Any], name: str, values: dict[str, str]) -> str:
        templates = self._read_json(Path(run["root"]) / "template_snapshot.json")
        text = str(templates.get(name) or self.template(name))
        for key, value in values.items():
            text = text.replace("{{" + key + "}}", value)
        return text

    def _metadata_word_pool(self, run: dict[str, Any]) -> str:
        metadata = self._read_json(Path(run["root"]) / "metadata_snapshot.json")
        if not metadata:
            return ""
        return (
            "OPTIONAL METADATA WORD POOL\n"
            "The canonical image is the source of visual truth. Do not treat this metadata as evidence about what is visible. "
            "Use it only as a vocabulary pool when similar wording helps describe details already visible in the image.\n"
            + json.dumps(metadata, indent=2, ensure_ascii=False)
        )

    @staticmethod
    def _checklist_questions(checklist: dict[str, Any]) -> str:
        questions = []
        auxiliaries = (" is ", " are ", " has ", " have ", " does ", " do ", " can ")
        for index, row in enumerate(checklist.get("items", []), 1):
            explicit = str(row.get("question") or "").strip()
            if explicit:
                questions.append(f"{index} - {explicit}")
                continue
            raw_statement = str(row.get("item") or "").strip()
            statement = raw_statement.rstrip(".?")
            question = statement
            if raw_statement.endswith("?"):
                question = raw_statement
            elif statement:
                lowered = statement.casefold()
                split = next(((lowered.index(auxiliary), auxiliary) for auxiliary in auxiliaries if auxiliary in lowered), None)
                if split:
                    position, auxiliary = split
                    subject = statement[:position].strip()
                    predicate = statement[position + len(auxiliary):].strip()
                    article = "" if subject.casefold().startswith(("the ", "a ", "an ")) else "the "
                    question = f"{auxiliary.strip().capitalize()} {article}{subject.casefold()} {predicate}?"
                elif not statement.endswith("?"):
                    question = f"Is this true: {statement}?"
            questions.append(f"{index} - {question}")
        return "\n".join(questions)

    def _queue_bootstrap(self, run: dict[str, Any]) -> None:
        root = Path(run["root"])
        prompt = self._format_template(run, "bootstrap", {
            "METADATA": "", "METADATA_WORD_POOL": "",
        })
        run["bootstrap_ask_id"] = self._queue_ollama(run, task="bootstrap", prompt=prompt, output=root / "bootstrap.json", images=[Path(run["reference_image"])])
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
                prompt = self._format_template(run, "repair", {
                    "REQUEST": path.stem,
                    "RESPONSE": path.read_text(encoding="utf-8", errors="replace"),
                })
                repair_model = str(run.get("checklist_model") or DEFAULT_CHECKLIST_MODEL) if path.stem.startswith("checklist_evaluation_") else None
                self._queue_ollama(
                    run, task=f"repair_{path.stem}", prompt=prompt, output=repair_path, images=[], model=repair_model,
                )
                marker.write_text(self._now(), encoding="utf-8")
            raise PromptEvolutionRepairPending(f"Waiting for JSON repair: {path.name}")

    def _prompt_json(self, run: dict[str, Any], path: Path) -> tuple[str, str]:
        data = self._llm_json(run, path)
        positive_terms = self._atomic_terms(data.get("positive_terms"))
        negative_terms = self._atomic_terms(data.get("negative_terms"))
        positive = ", ".join(positive_terms) if positive_terms else self._clean_prompt_terms(data.get("positive_prompt") or data.get("positive_core") or "")
        negative = ", ".join(negative_terms) if negative_terms else self._clean_prompt_terms(data.get("negative_prompt") or data.get("negative_core") or "")
        if not positive:
            raise PromptEvolutionError(f"LLM response omitted positive_prompt: {path}")
        return positive, negative

    @staticmethod
    def _atomic_terms(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        terms = [PromptEvolutionService._strip_term_id(str(item)) for item in value if PromptEvolutionService._strip_term_id(str(item))]
        if any("," in term for term in terms):
            raise PromptEvolutionError("Atomic prompt terms must not contain commas.")
        normalized = [" ".join(term.casefold().split()) for term in terms]
        if len(normalized) != len(set(normalized)):
            raise PromptEvolutionError("Atomic prompt terms must be unique.")
        return terms

    @staticmethod
    def _strip_term_id(value: str) -> str:
        return re.sub(r"^[pn]\d{3}:\s*", "", value.strip(), flags=re.IGNORECASE).strip()

    @staticmethod
    def _clean_prompt_terms(value: Any) -> str:
        return ", ".join(
            term for item in str(value).split(",")
            if (term := PromptEvolutionService._strip_term_id(item))
        )

    @staticmethod
    def _term_records(value: str | list[str], prefix: str) -> list[dict[str, str]]:
        raw_terms = value if isinstance(value, list) else value.split(",")
        terms = [term for item in raw_terms if (term := PromptEvolutionService._strip_term_id(str(item)))]
        return [{"id": f"{prefix}{index:03d}", "text": term} for index, term in enumerate(terms, 1)]

    @staticmethod
    def _compose_prompt(core_terms: list[dict[str, str]], wrapper: tuple[str, ...]) -> str:
        result: list[str] = []
        seen: set[str] = set()
        for term in [*(item["text"] for item in core_terms), *wrapper]:
            key = " ".join(term.casefold().split())
            if key not in seen:
                seen.add(key)
                result.append(term)
        return ", ".join(result)

    def _start_batch(self, run: dict[str, Any], positive: str, negative: str) -> None:
        original_positive, original_negative = positive, negative
        strategy_version = int(run.get("strategy_version", 1))
        if strategy_version >= 2:
            positive_terms = run.pop("pending_positive_terms", None) or self._term_records(positive, "p")
            negative_terms = run.pop("pending_negative_terms", None) or self._term_records(negative, "n")
            positive_core = ", ".join(item["text"] for item in positive_terms)
            negative_core = ", ".join(item["text"] for item in negative_terms)
            positive = self._compose_prompt(positive_terms, EVALUATION_POSITIVE_TERMS)
            negative = self._compose_prompt(negative_terms, EVALUATION_NEGATIVE_TERMS)
        elif int(run["current_batch"]) == 0:
            positive, negative = self._initial_prompts(positive, negative)
        if strategy_version < 2:
            positive = self._ensure_gray_background(positive)
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
        for seed in run["seeds"]:
            ask_path = self.app.ai_proxy_service.stage_render_task_local_render_ask(
                manifest, prompt_path, batch, allow_parallel=True, seed=seed, checkpoint=run["checkpoint"],
                render_overrides={"width": CANVAS_WIDTH, "height": CANVAS_HEIGHT, "cfg_scale": run["cfg_scale"], "steps": run["steps"]},
                render_preset=run["profile"],
            )
            ask = self._read_json(ask_path / "ask_manifest.json")
            asks.append({"ask_id": ask["ask_id"], "seed": seed, "file": str(batch / "Local_Test_Renders" / ask["expected_output"])})
        batch_payload = {"index": index, "positive_prompt": positive, "negative_prompt": negative, "renders": asks, "status": "RENDERING"}
        if strategy_version >= 2:
            batch_payload.update({
                "positive_core": positive_core,
                "negative_core": negative_core,
                "positive_core_terms": positive_terms,
                "negative_core_terms": negative_terms,
                "evaluation_wrapper": {
                    "positive_terms": list(EVALUATION_POSITIVE_TERMS),
                    "negative_terms": list(EVALUATION_NEGATIVE_TERMS),
                },
                "batch_slot": int(run.pop("pending_batch_slot", index)),
                "retry_attempt": int(run.pop("pending_batch_retry", 0)),
            })
            parent_finalist_id = str(run.pop("pending_parent_finalist_id", "") or "")
            if parent_finalist_id:
                batch_payload["parent_finalist_id"] = parent_finalist_id
        if index == 0:
            batch_payload.update({"original_positive_prompt": original_positive, "original_negative_prompt": original_negative})
        attempted_mutation = run.pop("pending_mutation", None)
        if attempted_mutation:
            batch_payload["attempted_mutation"] = attempted_mutation
        self._write_json(batch / "batch.json", batch_payload)
        run["status"] = "RENDERING"
        self._save_run(run)

    @staticmethod
    def _initial_prompts(positive: str, negative: str) -> tuple[str, str]:
        def inject(original: str, before: tuple[str, ...], after: tuple[str, ...] = ()) -> str:
            normalized = " ".join(original.casefold().split())
            prefix = [term for term in before if " ".join(term.casefold().split()) not in normalized]
            suffix = [term for term in after if " ".join(term.casefold().split()) not in normalized]
            return ", ".join([*prefix, *([original.strip()] if original.strip() else []), *suffix])
        return inject(positive, INITIAL_POSITIVE_PREFIX, INITIAL_POSITIVE_SUFFIX), inject(negative, INITIAL_NEGATIVE_PREFIX)

    @staticmethod
    def _ensure_gray_background(positive: str) -> str:
        terms = [term.strip() for term in positive.split(",") if term.strip()]
        terms = [GRAY_BACKGROUND_TERM if term.casefold() == LEGACY_GRAY_BACKGROUND_TERM else term for term in terms]
        if not any(term.casefold() == GRAY_BACKGROUND_TERM for term in terms):
            terms.append(GRAY_BACKGROUND_TERM)
        return ", ".join(terms)

    @staticmethod
    def _score(
        data: dict[str, Any], checklist: dict[str, Any] | None = None, checklist_data: dict[str, Any] | None = None,
    ) -> tuple[float, float, float, dict[str, float], dict[str, float], list[dict[str, Any]]]:
        feedback = data.get("category_feedback")
        if isinstance(feedback, dict):
            expected = CHARACTER_SCORE_CATEGORIES + COSTUME_SCORE_CATEGORIES
            if any(not isinstance(feedback.get(name), dict) for name in expected):
                raise PromptEvolutionError("Evaluation omitted structured category feedback.")
            data = {
                **data,
                "character_categories": {name: feedback[name].get("score") for name in CHARACTER_SCORE_CATEGORIES},
                "costume_categories": {name: feedback[name].get("score") for name in COSTUME_SCORE_CATEGORIES},
                "character_evidence": {name: str(feedback[name].get("observation") or "") for name in CHARACTER_SCORE_CATEGORIES},
                "costume_evidence": {name: str(feedback[name].get("observation") or "") for name in COSTUME_SCORE_CATEGORIES},
            }
        def category_scores(key: str, names: tuple[str, ...]) -> dict[str, float]:
            raw = data.get(key)
            if not isinstance(raw, dict):
                return {}
            scores: dict[str, float] = {}
            for name in names:
                if name not in raw or isinstance(raw[name], (dict, list)):
                    raise PromptEvolutionError(f"Evaluation omitted numeric category: {key}.{name}")
                scores[name] = float(raw[name])
            legacy_scale = any(score > 10 for score in scores.values())
            return {name: round(max(0, min(10, score / 10 if legacy_scale else score)), 1) for name, score in scores.items()}

        character_categories = category_scores("character_categories", CHARACTER_SCORE_CATEGORIES)
        costume_categories = category_scores("costume_categories", COSTUME_SCORE_CATEGORIES)
        checklist_effects: list[dict[str, Any]] = []
        if character_categories or costume_categories:
            if not character_categories or not costume_categories:
                raise PromptEvolutionError("Evaluation must include both character and costume category scorecards.")
            character_evidence = data.get("character_evidence") if isinstance(data.get("character_evidence"), dict) else {}
            costume_evidence = data.get("costume_evidence") if isinstance(data.get("costume_evidence"), dict) else {}
            evidence_values = [data.get("evidence"), *character_evidence.values(), *costume_evidence.values()]
            if not any(character_categories.values()) and not any(costume_categories.values()) and not int(data.get("confidence") or 0) and not any(str(value or "").strip() for value in evidence_values):
                raise PromptEvolutionPlaceholderResponse("Evaluation copied empty placeholder values instead of inspecting the images.")
            response_source = checklist_data if checklist_data is not None else data
            responses = {
                str(item.get("item") or ""): item.get("result") is True
                for item in response_source.get("checklist", []) if isinstance(item, dict)
            }
            numbered_responses = {
                int(item["number"]): item.get("result")
                for item in response_source.get("checklist", [])
                if isinstance(item, dict) and str(item.get("number") or "").isdigit()
            }
            if checklist_data is not None:
                supplied = {
                    str(item.get("item") or ""): item.get("result")
                    for item in checklist_data.get("checklist", []) if isinstance(item, dict)
                }
                # Missing or malformed individual answers are indeterminate. A hard
                # constraint must never be applied without an explicit true result.
            for index, item in enumerate((checklist or {}).get("items", []), 1):
                if not isinstance(item, dict) or not (numbered_responses.get(index) is True or responses.get(str(item.get("item") or ""), False)):
                    continue
                category = str(item.get("category") or "").strip().casefold().replace(" ", "_")
                scores = character_categories if category in character_categories else costume_categories
                if category not in scores:
                    continue
                before = scores[category]
                if "max_rating" in item:
                    max_rating = float(item["max_rating"])
                    if max_rating > 10:
                        max_rating /= 10
                    scores[category] = round(min(before, max(0, min(10, max_rating))), 1)
                    checklist_effects.append({"item": str(item["item"]), "category": category, "max_rating": max_rating, "before": before, "after": scores[category]})
                    if item.get("id"):
                        checklist_effects[-1]["id"] = str(item["id"])
                    if item.get("correction"):
                        checklist_effects[-1]["correction"] = str(item["correction"])
                elif "adjustment" in item:
                    adjustment = float(item["adjustment"])
                    if abs(adjustment) > 10:
                        adjustment /= 10
                    scores[category] = round(max(0, min(10, before + adjustment)), 1)
                    checklist_effects.append({
                        "id": str(item.get("id") or ""), "item": str(item["item"]), "category": category,
                        "correction": str(item.get("correction") or ""), "adjustment": adjustment,
                        "before": before, "after": scores[category],
                    })
            character = round(sum(character_categories.values()) / len(character_categories), 1)
            costume = round(sum(costume_categories.values()) / len(costume_categories), 1)
        else:
            def legacy_score(key: str) -> float:
                raw = data.get(key, 0)
                if isinstance(raw, dict):
                    raw = next((raw[name] for name in ("score", "total", "overall", "identity_score") if name in raw), 0)
                score = float(raw)
                return round(max(0, min(10, score / 10 if score > 10 else score)), 1)
            character = legacy_score("character_identity")
            costume = legacy_score("costume_identity")
        return character, costume, round((character + costume) / 2, 1), character_categories, costume_categories, checklist_effects

    @staticmethod
    def _ordered_ranking_seeds(ranking: dict[str, Any]) -> list[int]:
        result: list[int] = []
        for value in ranking.get("ordered_seeds", []) or []:
            raw = value.get("seed") if isinstance(value, dict) else value
            try:
                seed = int(raw)
            except (TypeError, ValueError):
                continue
            if seed not in result:
                result.append(seed)
        return result

    @staticmethod
    def _category_ranking(candidate: dict[str, Any]) -> list[dict[str, Any]]:
        allowed = set(CHARACTER_SCORE_CATEGORIES + COSTUME_SCORE_CATEGORIES)
        categories = {
            name: score for name, score in {**candidate.get("character_categories", {}), **candidate.get("costume_categories", {})}.items()
            if name in allowed
        }
        return [
            {"category": name, "score": score}
            for name, score in sorted(categories.items(), key=lambda item: (-item[1], item[0]))
        ]

    @staticmethod
    def _category_evaluation_summary(candidate: dict[str, Any]) -> str:
        rows = []
        for heading, key, names in (
            ("Character", "character_categories", CHARACTER_SCORE_CATEGORIES),
            ("Costume", "costume_categories", COSTUME_SCORE_CATEGORIES),
        ):
            scores = candidate.get(key) if isinstance(candidate.get(key), dict) else {}
            for order, name in enumerate(names):
                if name not in scores:
                    continue
                score = float(scores[name])
                score = max(0, min(10, score / 10 if score > 10 else score))
                if score < 5:
                    meaning = "This category needs major improvement"
                elif score < 7:
                    meaning = "This category needs improvement"
                elif score < 9:
                    meaning = "This category needs refinement"
                else:
                    meaning = "This category is excellent"
                display_score = str(int(score)) if score.is_integer() else str(round(score, 1))
                rows.append((score, 0 if heading == "Character" else 1, order,
                             f"{heading} {CATEGORY_DISPLAY_NAMES[name]}: Evaluation {display_score}/10 - {meaning}."))
        return "\n".join(row[3] for row in sorted(rows))

    @staticmethod
    def _checklist_directives(candidate: dict[str, Any]) -> str:
        defects = []
        seen = set()
        for effect in candidate.get("checklist_effects") or candidate.get("checklist_adjustments") or []:
            item = str(effect.get("item") or "").strip().rstrip(".")
            if not item or item.casefold() in seen:
                continue
            seen.add(item.casefold())
            statement = item if item.casefold().startswith(("the ", "a ", "an ")) else f"The {item[0].lower()}{item[1:]}"
            defects.append(f"{statement}.")
        if not defects:
            return ""
        noun = "this defect" if len(defects) == 1 else "these defects"
        return f"Additionally you must address {noun} directly: " + " ".join(defects)

    @staticmethod
    def _selected_corrections(candidate: dict[str, Any], limit: int = 2) -> list[dict[str, str]]:
        feedback = candidate.get("evaluation", {}).get("category_feedback", {})
        ranked: list[tuple[float, str, str]] = []
        if isinstance(feedback, dict):
            for category, value in feedback.items():
                if not isinstance(value, dict):
                    continue
                correction = str(value.get("correction") or "").strip()
                if correction:
                    ranked.append((float(value.get("score") or 0), category, correction))
        selected = [
            {"category": category, "correction": correction}
            for _, category, correction in sorted(ranked)[:limit]
        ]
        seen = {(item["category"], item["correction"].casefold()) for item in selected}
        for effect in candidate.get("checklist_effects") or []:
            correction = str(effect.get("correction") or "").strip()
            key = (str(effect.get("category") or ""), correction.casefold())
            if correction and key not in seen:
                selected.append({"category": key[0], "correction": correction})
                seen.add(key)
        return selected

    @staticmethod
    def _terms_for_prompt(records: list[dict[str, str]]) -> str:
        return "\n".join(f"- {item['id']}: {item['text']}" for item in records)

    @staticmethod
    def _term_weight(text: str) -> tuple[str, float | None]:
        match = re.fullmatch(r"\((.+):([0-9]+(?:\.[0-9]+)?)\)", text.strip())
        return (match.group(1).strip(), float(match.group(2))) if match else (text.strip(), None)

    @classmethod
    def _term_key(cls, text: str) -> str:
        base, _ = cls._term_weight(text)
        return " ".join(base.casefold().split())

    @classmethod
    def _strengthened_term(cls, text: str) -> str:
        base, weight = cls._term_weight(text)
        increased = round((weight if weight is not None else 1.0) + 0.2, 2)
        formatted = f"{increased:.2f}".rstrip("0").rstrip(".")
        return f"({base}:{formatted})"

    @staticmethod
    def _refinement_response_schema(
        positive_terms: list[dict[str, str]], negative_terms: list[dict[str, str]], allowed_categories: set[str],
    ) -> dict[str, Any]:
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "positive_core": {"type": "string", "minLength": 1},
                "negative_core": {"type": "string"},
            },
            "required": ["positive_core", "negative_core"],
        }

    @staticmethod
    def _refinement_error(
        code: str, operation_index: int | None, field: str, message: str, *, overrideable: bool = False,
    ) -> dict[str, Any]:
        return {
            "code": code, "operation_index": operation_index, "field": field,
            "message": message, "overrideable": overrideable,
        }

    @classmethod
    def _analyze_term_operations(
        cls,
        positive_terms: list[dict[str, str]],
        negative_terms: list[dict[str, str]],
        data: dict[str, Any],
        allowed_categories: set[str],
        corrections: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        baseline = {
            "positive": [{**item, "text": cls._strip_term_id(item["text"])} for item in positive_terms],
            "negative": [{**item, "text": cls._strip_term_id(item["text"])} for item in negative_terms],
        }
        lists = {key: [dict(item) for item in records] for key, records in baseline.items()}
        operations = data.get("operations")
        errors: list[dict[str, Any]] = []
        applied: list[dict[str, str]] = []
        if not isinstance(operations, list) or not operations:
            errors.append(cls._refinement_error(
                "missing_operations", None, "operations", "Refinement must return at least one term operation.",
            ))
            operations = []
        for index, raw in enumerate(operations):
            if not isinstance(raw, dict):
                errors.append(cls._refinement_error(
                    "invalid_operation", index, "operation", "Operation must be a JSON object.",
                ))
                continue
            operation_errors: list[dict[str, Any]] = []
            target = str(raw.get("target") or "")
            action = str(raw.get("action") or "")
            term_id = str(raw.get("term_id") or "").strip()
            new = cls._strip_term_id(str(raw.get("new") or ""))
            category = str(raw.get("category") or "").strip()
            if target not in lists:
                operation_errors.append(cls._refinement_error(
                    "invalid_target", index, "target", "Target must be positive or negative.",
                ))
            if action not in {"add", "remove", "edit"}:
                operation_errors.append(cls._refinement_error(
                    "invalid_action", index, "action", "Action must be add, edit, or remove.",
                ))
            if not category:
                operation_errors.append(cls._refinement_error(
                    "missing_category", index, "category", "Every operation must include one selected category.",
                    overrideable=True,
                ))
            elif category not in allowed_categories:
                operation_errors.append(cls._refinement_error(
                    "unselected_category", index, "category",
                    f"Category must be one of: {', '.join(sorted(allowed_categories))}.",
                ))
            records = lists.get(target, [])
            match = next((item_index for item_index, item in enumerate(records) if item["id"] == term_id), None)
            if action in {"edit", "remove"} and match is None:
                operation_errors.append(cls._refinement_error(
                    "unknown_term_id", index, "term_id", f"Refinement operation references unknown term ID: {term_id or '(blank)'}.",
                ))
            if action == "add" and term_id:
                operation_errors.append(cls._refinement_error(
                    "add_term_id", index, "term_id", "Add operations must use an empty term_id.",
                ))
            if action in {"add", "edit"} and (not new or any(separator in new for separator in (",", ";"))):
                operation_errors.append(cls._refinement_error(
                    "non_atomic_term", index, "new", "Refinement terms must be non-empty and atomic; commas and semicolons are not allowed.",
                ))
            if action == "remove" and new:
                operation_errors.append(cls._refinement_error(
                    "remove_has_new", index, "new", "Remove operations must use an empty new value.",
                ))
            if action in {"add", "edit"} and any(word in new.casefold().split() for word in ("added", "removed", "present", "absent")):
                operation_errors.append(cls._refinement_error(
                    "editing_narration", index, "new", "Terms must describe visual traits, not editing instructions.",
                ))
            blocking = [item for item in operation_errors if not item["overrideable"]]
            errors.extend(operation_errors)
            if blocking:
                continue
            if action == "add":
                duplicate = next((item for item in records if cls._term_key(item["text"]) == cls._term_key(new)), None)
                if duplicate is not None:
                    term_id = duplicate["id"]
                    new = cls._strengthened_term(duplicate["text"])
                    duplicate["text"] = new
                    action = "strengthen"
                else:
                    indexes = [int(item["id"][1:]) for item in records if item["id"].startswith(target[0]) and item["id"][1:].isdigit()]
                    term_id = f"{target[0]}{max(indexes, default=0) + 1:03d}"
                    records.append({"id": term_id, "text": new})
            elif action == "remove":
                records.pop(match)
            elif action == "edit":
                if records[match]["text"].casefold() == new.casefold():
                    errors.append(cls._refinement_error(
                        "no_op", index, "new", "Refinement attempted a no-op edit.",
                    ))
                    continue
                records[match]["text"] = new
            applied.append({"target": target, "action": action, "term_id": term_id, "new": new, "category": category})
        for target, records in lists.items():
            normalized = [cls._term_key(item["text"]) for item in records]
            duplicates = {value for value in normalized if normalized.count(value) > 1}
            if duplicates:
                errors.append(cls._refinement_error(
                    "duplicate_terms", None, target, f"Refinement produced duplicate {target} terms.",
                ))
        blocking_errors = [item for item in errors if not item["overrideable"]]
        preview_lists = baseline if blocking_errors else lists
        return {
            "strict_valid": not errors,
            "guarded_override_allowed": bool(errors) and not blocking_errors,
            "validation_errors": errors,
            "preview_status": "baseline" if blocking_errors else "complete",
            "positive_terms": preview_lists["positive"],
            "negative_terms": preview_lists["negative"],
            "positive_core": ", ".join(item["text"] for item in preview_lists["positive"]),
            "negative_core": ", ".join(item["text"] for item in preview_lists["negative"]),
            "operations": applied,
        }

    @classmethod
    def _apply_term_operations(
        cls,
        positive_terms: list[dict[str, str]],
        negative_terms: list[dict[str, str]],
        data: dict[str, Any],
        allowed_categories: set[str],
        corrections: list[dict[str, str]] | None = None,
    ) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
        analysis = cls._analyze_term_operations(positive_terms, negative_terms, data, allowed_categories, corrections)
        if not analysis["strict_valid"]:
            raise PromptEvolutionError(analysis["validation_errors"][0]["message"])
        return analysis["positive_terms"], analysis["negative_terms"], analysis["operations"]

    @classmethod
    def _refinement_contract_values(
        cls, incumbent: dict[str, Any], corrections: list[dict[str, str]], evaluation: Any = None,
    ) -> tuple[dict[str, str], dict[str, Any]]:
        positive_terms = incumbent["positive_core_terms"]
        negative_terms = incumbent["negative_core_terms"]
        categories = {str(item["category"]) for item in corrections}
        edit_record = positive_terms[0] if positive_terms else negative_terms[0]
        edit_target = "positive" if positive_terms else "negative"
        remove_record = negative_terms[0] if negative_terms else edit_record
        remove_target = "negative" if negative_terms else edit_target
        category = str(corrections[0]["category"])
        examples = {"operations": [
            {"target": edit_target, "action": "edit", "term_id": edit_record["id"], "new": "specific corrected visual trait", "category": category},
            {"target": "negative", "action": "add", "term_id": "", "new": "specific unwanted visual trait", "category": category},
            {"target": remove_target, "action": "remove", "term_id": remove_record["id"], "new": "", "category": category},
        ]}
        schema = cls._refinement_response_schema(positive_terms, negative_terms, categories)
        return {
            "CORRECTIONS": "\n".join(f"- {item['category']}: {item['correction']}" for item in corrections),
            "POSITIVE_TERMS": cls._terms_for_prompt(positive_terms),
            "NEGATIVE_TERMS": cls._terms_for_prompt(negative_terms),
            "ALLOWED_CATEGORIES": json.dumps(sorted(categories), ensure_ascii=False),
            "OUTPUT_SCHEMA": json.dumps(schema, indent=2, ensure_ascii=False),
            "VALID_EXAMPLES": json.dumps(examples, indent=2, ensure_ascii=False),
            "REJECTED_MUTATIONS": "[]",
            "POSITIVE_PROMPT": incumbent["positive_core"], "NEGATIVE_PROMPT": incumbent["negative_core"],
            "METADATA": "", "METADATA_WORD_POOL": "", "TARGET_CATEGORY": category,
            "EVALUATIONS": json.dumps(evaluation or {}, indent=2, ensure_ascii=False),
            "CATEGORY_EVALUATIONS": "", "REJECTION_CONTEXT": "", "CHECKLIST_DIRECTIVES": "",
        }, schema

    def _record_refinement_attempt(
        self, run: dict[str, Any], batch: dict[str, Any], data: dict[str, Any], output: Path,
    ) -> dict[str, Any]:
        incumbent = run.get("exploration_incumbent") or run["incumbent"]
        corrections = run.get("pending_corrections") or []
        analysis = self._analyze_refinement_response(incumbent, data, corrections)
        number = int(run.get("refinement_attempt_number", 1))
        attempt = {
            "attempt_id": f"ollama-{number:02d}", "number": number,
            "source": "ollama_initial" if number == 1 else "ollama_retry",
            "ask_id": str(run.get("refinement_ask_id") or ""), "output_file": str(output),
            "response": data, "validation_errors": analysis["validation_errors"],
            "strict_valid": analysis["strict_valid"],
            "guarded_override_allowed": analysis["guarded_override_allowed"],
            "preview_status": analysis["preview_status"],
            "positive_core": analysis["positive_core"], "negative_core": analysis["negative_core"],
            "operations": analysis["operations"], "accepted": False, "created_at": self._now(),
        }
        batch.setdefault("refinement_attempts", []).append(attempt)
        return attempt | {"analysis": analysis}

    @staticmethod
    def _refinement_retry_text(base_prompt: str, data: dict[str, Any], errors: list[dict[str, Any]]) -> str:
        reasons = "\n".join(
            f"- Operation {int(item['operation_index']) + 1 if item['operation_index'] is not None else 'response'}, "
            f"field {item['field']}: {item['message']}" for item in errors
        )
        return (
            f"{base_prompt}\n\nPRIOR RESPONSE REJECTED\n{json.dumps(data, indent=2, ensure_ascii=False)}"
            f"\n\nVALIDATION ERRORS\n{reasons}\n\nReturn a corrected response. Fix every listed error and repeat every required field."
        )

    def _apply_operations(self, positive: str, negative: str, data: dict[str, Any]) -> tuple[str, str, list[dict[str, str]]]:
        positive_ops = data.get("positive_operations") or []
        negative_ops = data.get("negative_operations") or []
        if not isinstance(positive_ops, list) or not isinstance(negative_ops, list):
            raise PromptEvolutionError("Refinement operations must be arrays.")
        applied: list[dict[str, str]] = []
        def mutate(text: str, operations: list[Any]) -> str:
            terms = [item.strip() for item in text.split(",") if item.strip()]
            def find_term(value: str) -> int | None:
                normalized = " ".join(value.casefold().split())
                return next((index for index, term in enumerate(terms) if " ".join(term.casefold().split()) == normalized), None)
            for raw in operations:
                if not isinstance(raw, dict) or raw.get("action") not in {"add", "remove", "edit"}:
                    raise PromptEvolutionError("Invalid refinement operation.")
                action, old, new = str(raw["action"]), str(raw.get("old") or "").strip(), str(raw.get("new") or "").strip()
                old_index = find_term(old) if old else None
                new_index = find_term(new) if new else None
                resolved_action = action
                if action == "add" and new:
                    if new_index is None:
                        terms.append(new)
                    else:
                        resolved_action = "noop"
                elif action == "remove" and old:
                    if old_index is not None:
                        terms.pop(old_index)
                    else:
                        resolved_action = "noop"
                elif action == "edit" and new:
                    if old_index is not None:
                        terms[old_index] = new
                    elif new_index is not None:
                        resolved_action = "noop"
                    else:
                        terms.append(new)
                        resolved_action = "add"
                else:
                    raise PromptEvolutionError(f"Could not apply refinement operation: {raw}")
                applied.append({"action": action, "resolved_action": resolved_action, "old": old, "new": new})
            return ", ".join(terms)
        return mutate(positive, positive_ops), mutate(negative, negative_ops), applied

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
            return self._advance_run_unlocked(run_id)
        finally:
            lock.unlink(missing_ok=True)

    @staticmethod
    def _now_timestamp() -> float:
        return datetime.now().timestamp()

    def _advance_run_unlocked(self, run_id: str) -> dict[str, Any]:
        run = self._find_run(run_id)
        if run["status"] in {"COMPLETE", "ABORTED", "FAILED", "AWAITING_USER", "AWAITING_FINALIST", "AWAITING_REFINEMENT_REVIEW"}:
            return self.detail(run_id)
        try:
            root = Path(run["root"])
            if run["status"] == "BOOTSTRAPPING" and (root / "bootstrap.json").is_file():
                self._start_batch(run, *self._prompt_json(run, root / "bootstrap.json"))
            elif run["status"] == "RENDERING":
                batch_path = root / "batches" / f"{int(run['current_batch']):03d}"
                batch = self._read_json(batch_path / "batch.json")
                if all(Path(item["file"]).is_file() for item in batch["renders"]):
                    evaluations = []
                    checklist_path = root / "checklist_snapshot.json"
                    checklist = self._read_json(checklist_path) if checklist_path.is_file() else {"items": []}
                    checklist_questions = self._checklist_questions(checklist)
                    template_snapshot = self._read_json(root / "template_snapshot.json")
                    split_evaluations = "checklist_evaluation" in template_snapshot
                    for item in batch["renders"]:
                        output = batch_path / f"evaluation_{item['seed']}.json"
                        prompt = self._format_template(run, "evaluation", {
                            "METADATA": "", "METADATA_CONTEXT": "", "CHECKLIST": checklist_questions,
                            "CHECKLIST_QUESTIONS": checklist_questions, "SEED": str(item["seed"]),
                        })
                        ask_id = self._queue_ollama(run, task=f"evaluate_{item['seed']}", prompt=prompt, output=output, images=[Path(run["reference_image"]), Path(item["file"])])
                        evaluations.append({"seed": item["seed"], "file": item["file"], "output": str(output), "ask_id": ask_id})
                    for item in evaluations if split_evaluations else []:
                        output = batch_path / f"checklist_evaluation_{item['seed']}.json"
                        prompt = self._format_template(run, "checklist_evaluation", {
                            "METADATA": "", "METADATA_CONTEXT": "", "CHECKLIST": checklist_questions,
                            "CHECKLIST_QUESTIONS": checklist_questions, "SEED": str(item["seed"]),
                        })
                        item["checklist_output"] = str(output)
                        item["checklist_ask_id"] = self._queue_ollama(
                            run, task=f"checklist_{item['seed']}", prompt=prompt, output=output,
                            images=[Path(run["reference_image"]), Path(item["file"])],
                            model=str(run.get("checklist_model") or DEFAULT_CHECKLIST_MODEL),
                        )
                    batch["evaluations"] = evaluations
                    batch["status"] = "EVALUATING"
                    self._write_json(batch_path / "batch.json", batch)
                    run["status"] = "EVALUATING"
                    self._save_run(run)
            elif run["status"] == "EVALUATING":
                batch_path = root / "batches" / f"{int(run['current_batch']):03d}"
                batch = self._read_json(batch_path / "batch.json")
                if all(
                    Path(item["output"]).is_file()
                    and (not item.get("checklist_output") or Path(item["checklist_output"]).is_file())
                    for item in batch["evaluations"]
                ):
                    scored = []
                    retry_queued = False
                    checklist_path = root / "checklist_snapshot.json"
                    checklist = self._read_json(checklist_path) if checklist_path.is_file() else {"items": []}
                    for item in batch["evaluations"]:
                        evaluation_path = Path(item["output"])
                        evaluation = self._llm_json(run, evaluation_path)
                        checklist_evaluation = self._llm_json(run, Path(item["checklist_output"])) if item.get("checklist_output") else None
                        try:
                            score = self._score(evaluation, checklist, checklist_evaluation)
                        except PromptEvolutionPlaceholderResponse:
                            if evaluation_path.stem.endswith(".retry"):
                                raise PromptEvolutionError(f"Evaluation returned empty placeholder scores twice: {evaluation_path.name}")
                            retry_path = evaluation_path.with_name(f"{evaluation_path.stem}.retry.json")
                            prompt = self._format_template(run, "evaluation", {
                                "METADATA": "", "METADATA_CONTEXT": "", "SEED": str(item["seed"]),
                            }) + "\nYour prior response copied empty/default values. Inspect both attached images and return actual scores and evidence."
                            item["ask_id"] = self._queue_ollama(run, task=f"evaluate_{item['seed']}_retry", prompt=prompt, output=retry_path,
                                                                  images=[Path(run["reference_image"]), Path(item["file"])])
                            item["output"] = str(retry_path)
                            retry_queued = True
                            continue
                        character, costume, combined, character_categories, costume_categories, checklist_effects = score
                        scored.append({**item, "character_identity": character, "costume_identity": costume, "combined_score": combined,
                                       "character_categories": character_categories, "costume_categories": costume_categories,
                                       "checklist_effects": checklist_effects, "evaluation": evaluation,
                                       "checklist_evaluation": checklist_evaluation})
                    if retry_queued:
                        self._write_json(batch_path / "batch.json", batch)
                        return self.detail(run_id)
                    scored.sort(key=lambda item: (-item["combined_score"], item["seed"]))
                    first_metadata = Path(scored[0]["file"]).with_suffix(".json")
                    if first_metadata.is_file():
                        settings = self._read_json(first_metadata).get("settings", {})
                        batch["effective_positive_prompt"] = str(settings.get("prompt") or batch["positive_prompt"])
                        batch["effective_negative_prompt"] = str(settings.get("negative_prompt") or batch["negative_prompt"])
                    batch.update({"candidates": scored, "status": "RANKING"})
                    self._write_json(batch_path / "batch.json", batch)
                    ranking_prompt = self._format_template(run, "ranking", {"SCORECARDS": json.dumps(scored, ensure_ascii=False)})
                    run["ranking_ask_id"] = self._queue_ollama(run, task="ranking", prompt=ranking_prompt, output=batch_path / "ranking.json", images=[])
                    run["status"] = "RANKING"
                    self._save_run(run)
            elif run["status"] == "RANKING":
                batch_path = root / "batches" / f"{int(run['current_batch']):03d}"
                ranking_path = batch_path / "ranking.json"
                if ranking_path.is_file():
                    batch = self._read_json(batch_path / "batch.json")
                    ranking = self._llm_json(run, ranking_path)
                    candidates = batch["candidates"]
                    best_score = max(item["combined_score"] for item in candidates)
                    tied = [item for item in candidates if item["combined_score"] == best_score]
                    order = self._ordered_ranking_seeds(ranking)
                    winner = next((item for seed in order for item in tied if int(item["seed"]) == seed), tied[0])
                    batch["category_ranking"] = self._category_ranking(winner)
                    batch["target_category"] = batch["category_ranking"][-1]["category"] if batch["category_ranking"] else None
                    if int(run.get("strategy_version", 1)) >= 2:
                        finalist = {
                            **winner,
                            "finalist_id": f"batch-{int(run['current_batch']):03d}",
                            "positive_prompt": batch["positive_prompt"], "negative_prompt": batch["negative_prompt"],
                            "positive_core": batch["positive_core"], "negative_core": batch["negative_core"],
                            "positive_core_terms": batch["positive_core_terms"], "negative_core_terms": batch["negative_core_terms"],
                            "evaluation_wrapper": batch["evaluation_wrapper"], "batch": run["current_batch"],
                        }
                        if run.get("incumbent") is None:
                            run["incumbent"] = finalist
                        exploration = run.get("exploration_incumbent")
                        improved_exploration = exploration is None or float(winner["combined_score"]) > float(exploration["combined_score"])
                        if improved_exploration:
                            run["exploration_incumbent"] = finalist
                        if not any(item.get("positive_core") == finalist["positive_core"] and item.get("negative_core") == finalist["negative_core"] for item in run.get("finalists", [])):
                            run.setdefault("finalists", []).append(finalist)
                        accepted = None
                        batch.update({"ranking": ranking, "winner_seed": winner["seed"], "shortlisted": True, "improved_exploration": improved_exploration, "accepted": None, "status": "REVIEWED"})
                    else:
                        incumbent = run.get("incumbent")
                        accepted = incumbent is None or (
                            winner["character_identity"] >= IDENTITY_FLOOR and winner["costume_identity"] >= IDENTITY_FLOOR
                            and winner["combined_score"] >= (float(incumbent["combined_score"]) / 10 if float(incumbent["combined_score"]) > 10 else float(incumbent["combined_score"])) + MINIMUM_SCORE_IMPROVEMENT
                        )
                        if accepted:
                            run["incumbent"] = {**winner, "positive_prompt": batch["positive_prompt"], "negative_prompt": batch["negative_prompt"], "batch": run["current_batch"]}
                        batch.update({"ranking": ranking, "winner_seed": winner["seed"], "accepted": accepted, "status": "REVIEWED"})
                    self._write_json(batch_path / "batch.json", batch)
                    if int(run.get("strategy_version", 1)) < 2 and run["mode"] == "manual":
                        run["status"] = "AWAITING_USER"
                        self._save_run(run)
                    else:
                        self._queue_next_or_finish(run, batch)
            elif run["status"] == "REFINING":
                batch_path = root / "batches" / f"{int(run['current_batch']):03d}"
                refinement = Path(str(run.get("refinement_output") or batch_path / "refinement.json"))
                if refinement.is_file():
                    incumbent = run.get("exploration_incumbent") or run["incumbent"]
                    data = self._llm_json(run, refinement)
                    batch = self._read_json(batch_path / "batch.json")
                    if int(run.get("strategy_version", 1)) >= 2:
                        attempt = self._record_refinement_attempt(run, batch, data, refinement)
                        analysis = attempt["analysis"]
                        if not analysis["strict_valid"]:
                            messages = [item["message"] for item in analysis["validation_errors"]]
                            batch["refinement_rejected"] = " ".join(messages)
                            self._write_json(batch_path / "batch.json", batch)
                            attempt_number = int(run.get("refinement_attempt_number", 1))
                            if attempt_number >= 3:
                                run["error"] = ""
                                run["exploration_warning"] = "Ollama produced three rejected refinement attempts. Human review is required."
                                run["status"] = "AWAITING_REFINEMENT_REVIEW"
                                run.pop("refinement_output", None)
                                self._save_run(run)
                                return self.detail(run_id)
                            values, schema = self._refinement_contract_values(incumbent, run.get("pending_corrections") or [])
                            values["REJECTED_MUTATIONS"] = json.dumps(run.get("rejected_mutations", []), ensure_ascii=False)
                            next_number = attempt_number + 1
                            retry = batch_path / f"refinement.attempt-{next_number:02d}.json"
                            retry_prompt = self._refinement_retry_text(
                                str(run.get("last_refinement_prompt") or self._format_template(run, "refinement", values)),
                                data, analysis["validation_errors"],
                            )
                            run["refinement_attempt_number"] = next_number
                            run["refinement_ask_id"] = self._queue_ollama(
                                run, task=f"refinement_retry_{next_number}", prompt=retry_prompt, output=retry,
                                images=[Path(run["reference_image"]), Path(run["pending_candidate_image"])],
                                response_schema=schema, temperature=0,
                            )
                            run["refinement_output"] = str(retry)
                            self._save_run(run)
                            return self.detail(run_id)
                        positive_terms = analysis["positive_terms"]
                        negative_terms = analysis["negative_terms"]
                        operations = analysis["operations"]
                        batch["refinement_attempts"][-1]["accepted"] = True
                        positive = analysis["positive_core"]
                        negative = analysis["negative_core"]
                        run["pending_positive_terms"] = positive_terms
                        run["pending_negative_terms"] = negative_terms
                    else:
                        positive, negative, operations = self._apply_operations(incumbent["positive_prompt"], incumbent["negative_prompt"], data)
                    batch["mutation"] = operations
                    self._write_json(batch_path / "batch.json", batch)
                    run["pending_mutation"] = operations
                    run.pop("refinement_output", None)
                    run.pop("refinement_attempt_number", None)
                    run["current_batch"] = int(run["current_batch"]) + 1
                    self._start_batch(run, positive, negative)
            elif run["status"] == "DIRECTED_REFINING":
                directed = run.get("directed_refinement") or {}
                output = Path(str(directed.get("output") or ""))
                if output.is_file():
                    positive, negative = self._prompt_json(run, output)
                    new_run = self.create_run({
                        key: run[key] for key in ("character", "phase", "costume", "view", "model", "checklist_model", "checkpoint", "profile", "cfg_scale", "steps", "batch_size", "total_batches", "metadata_mode", "mode") if key in run
                    } | {"positive_prompt": positive, "negative_prompt": negative})
                    directed.update({"status": "COMPLETE", "new_run_id": new_run["run_id"], "positive_prompt": positive, "negative_prompt": negative})
                    run["directed_refinement"] = directed
                    run["status"] = "COMPLETE"
                    self._save_run(run)
        except PromptEvolutionRepairPending:
            pass
        except Exception as exc:
            run["failed_stage"] = run["status"]
            run["status"], run["error"] = "FAILED", str(exc)
            self._save_run(run)
        return self.detail(run_id)

    def _finish_exploration(self, run: dict[str, Any]) -> None:
        if int(run.get("strategy_version", 1)) >= 2:
            rejected_ids = set(run.get("rejected_finalist_ids") or [])
            eligible = [item for item in run.get("finalists", []) if item.get("finalist_id") not in rejected_ids]
            finalists = sorted(eligible, key=lambda item: (-float(item.get("combined_score", 0)), int(item.get("batch", 0))))[:3]
            initial = run.get("incumbent")
            if initial and not any(item.get("finalist_id") == initial.get("finalist_id") for item in finalists):
                finalists = [initial, *finalists[:2]]
            generator = random.Random(str(run["run_id"]))
            generator.shuffle(finalists)
            run["finalists"] = finalists
            run["status"] = "AWAITING_FINALIST"
        else:
            run["status"] = "COMPLETE"
        self._save_run(run)

    def _queue_v2_refinement(
        self, run: dict[str, Any], batch: dict[str, Any], selected: dict[str, Any], incumbent: dict[str, Any],
        selection_reason: str = "",
    ) -> None:
        corrections = self._selected_corrections(selected)
        if not corrections:
            run["exploration_stop_reason"] = "No corrective refinement was requested for the selected candidate."
            self._finish_exploration(run)
            return
        values, schema = self._refinement_contract_values(
            incumbent, corrections, selected.get("evaluation", {}).get("category_feedback", {}),
        )
        values["REJECTED_MUTATIONS"] = json.dumps(run.get("rejected_mutations", []), ensure_ascii=False)
        prompt = self._format_template(run, "refinement", values)
        reason = selection_reason.strip()
        if reason:
            prompt = f"{prompt}\n\nAlso take this into consideration: {reason}"
        root = Path(run["root"])
        output = root / "batches" / f"{int(run['current_batch']):03d}" / "refinement.attempt-01.json"
        candidate_image = Path(str(selected["file"]))
        selected_seed = int(selected["seed"])
        generator = random.SystemRandom()
        next_seeds = [selected_seed]
        while len(next_seeds) < int(run["batch_size"]):
            seed = generator.randrange(0, 2**63 - 1)
            if seed not in next_seeds:
                next_seeds.append(seed)
        run["seeds"] = next_seeds
        run["pending_corrections"] = corrections
        run["pending_candidate_image"] = str(candidate_image)
        run["pending_parent_finalist_id"] = str(incumbent.get("finalist_id") or "")
        run["last_refinement_prompt"] = prompt
        run["refinement_output"] = str(output)
        run["refinement_attempt_number"] = 1
        run["refinement_ask_id"] = self._queue_ollama(
            run, task="refinement", prompt=prompt, output=output,
            images=[Path(run["reference_image"]), candidate_image],
            response_schema=schema, temperature=0,
        )
        run["status"] = "REFINING"
        self._save_run(run)

    def _queue_next_or_finish(self, run: dict[str, Any], batch: dict[str, Any]) -> None:
        if int(run["current_batch"]) + 1 >= int(run["total_batches"]):
            self._finish_exploration(run)
            return
        root = Path(run["root"])
        incumbent = run.get("exploration_incumbent") or run["incumbent"]
        selected_seed = int(batch.get("selected_seed", batch["winner_seed"]))
        selected = next((candidate for candidate in batch.get("candidates", []) if int(candidate["seed"]) == selected_seed), {})
        if int(run.get("strategy_version", 1)) >= 2:
            if batch.get("improved_exploration") is False and batch.get("attempted_mutation"):
                run.setdefault("rejected_mutations", []).extend(batch["attempted_mutation"])
            self._queue_v2_refinement(run, batch, selected, incumbent)
            return
        checklist_directives = self._checklist_directives(selected)
        category_evaluations = self._category_evaluation_summary(selected)
        category_ranking = self._category_ranking(selected)
        if category_ranking:
            batch["category_ranking"] = category_ranking
            batch["target_category"] = category_ranking[-1]["category"]
            self._write_json(root / "batches" / f"{int(run['current_batch']):03d}" / "batch.json", batch)
        target_category = str(batch.get("target_category") or "overall identity")
        rejection_context = ""
        if batch.get("accepted") is False:
            attempted_mutation = batch.get("attempted_mutation") or []
            if not attempted_mutation and int(run["current_batch"]) > 0:
                previous_path = root / "batches" / f"{int(run['current_batch']) - 1:03d}" / "batch.json"
                if previous_path.is_file():
                    attempted_mutation = self._read_json(previous_path).get("mutation") or []
            rejection_context = (
                "The last prompt change was tried and had no beneficial effect, so that batch was rejected. "
                f"Ineffective change: {json.dumps(attempted_mutation, ensure_ascii=False)}. "
                "Do not repeat that change; try a different edit for the target category."
            )
        prompt = self._format_template(run, "refinement", {
            "POSITIVE_PROMPT": incumbent["positive_prompt"], "NEGATIVE_PROMPT": incumbent["negative_prompt"],
            "METADATA": "", "TARGET_CATEGORY": target_category,
            "METADATA_WORD_POOL": self._metadata_word_pool(run),
            "EVALUATIONS": category_evaluations, "CATEGORY_EVALUATIONS": category_evaluations,
            "REJECTION_CONTEXT": rejection_context,
            "CHECKLIST_DIRECTIVES": checklist_directives,
        })
        if checklist_directives and checklist_directives not in prompt:
            lead = "Your job is to refine the Stable Diffusion prompt to correct defects and achieve higher evaluations for images generated by the new prompt."
            prompt = prompt.replace(lead, f"{lead} {checklist_directives}", 1) if lead in prompt else f"{checklist_directives}\n\n{prompt}"
        if rejection_context and rejection_context not in prompt:
            prompt = f"{prompt}\n\n{rejection_context}"
        selection_reason = str(batch.get("selection_reason") or "").strip()
        if selection_reason:
            prompt = f"{prompt}\n\nAlso take this into consideration: {selection_reason}"
        output = root / "batches" / f"{int(run['current_batch']):03d}" / "refinement.json"
        winner_seed = selected_seed
        generator = random.SystemRandom()
        next_seeds = [winner_seed]
        while len(next_seeds) < int(run["batch_size"]):
            seed = generator.randrange(0, 2**63 - 1)
            if seed not in next_seeds:
                next_seeds.append(seed)
        run["seeds"] = next_seeds
        run["refinement_ask_id"] = self._queue_ollama(run, task="refinement", prompt=prompt, output=output, images=[Path(run["reference_image"])])
        run["status"] = "REFINING"
        self._save_run(run)

    def select_candidate(self, run_id: str, seed: int, selection_reason: str = "") -> dict[str, Any]:
        run = self._find_run(run_id)
        if run["status"] != "AWAITING_USER":
            raise PromptEvolutionError("Run is not awaiting a manual selection.")
        batch_path = Path(run["root"]) / "batches" / f"{int(run['current_batch']):03d}"
        batch = self._read_json(batch_path / "batch.json")
        selected = next((item for item in batch["candidates"] if int(item["seed"]) == int(seed)), None)
        if selected is None:
            raise PromptEvolutionError(f"Unknown candidate seed: {seed}")
        run["incumbent"] = {**selected, "positive_prompt": batch["positive_prompt"], "negative_prompt": batch["negative_prompt"], "batch": run["current_batch"], "human_override": seed != batch["winner_seed"]}
        batch["ai_accepted"] = batch.get("accepted")
        batch["selected_seed"], batch["human_override"], batch["accepted"] = seed, seed != batch["winner_seed"], True
        if selection_reason.strip():
            batch["selection_reason"] = selection_reason.strip()
        self._write_json(batch_path / "batch.json", batch)
        self._queue_next_or_finish(run, batch)
        return self.detail(run_id)

    def _refinement_review_context(
        self, run_id: str, attempt_id: str,
    ) -> tuple[dict[str, Any], Path, dict[str, Any], dict[str, Any]]:
        run = self._find_run(run_id)
        if run.get("status") != "AWAITING_REFINEMENT_REVIEW":
            raise PromptEvolutionError("Run is not awaiting refinement review.")
        batch_path = Path(run["root"]) / "batches" / f"{int(run['current_batch']):03d}"
        batch = self._read_json(batch_path / "batch.json")
        attempt = next(
            (item for item in batch.get("refinement_attempts", []) if item.get("attempt_id") == attempt_id), None,
        )
        if attempt is None:
            raise PromptEvolutionError(f"Unknown refinement attempt: {attempt_id}")
        return run, batch_path, batch, attempt

    def preview_refinement_review(
        self, run_id: str, attempt_id: str, operations: list[Any] | None = None,
        positive_core: str | None = None, negative_core: str | None = None,
    ) -> dict[str, Any]:
        run, _, _, attempt = self._refinement_review_context(run_id, attempt_id)
        incumbent = run.get("exploration_incumbent") or run["incumbent"]
        corrections = run.get("pending_corrections") or []
        if positive_core is not None or negative_core is not None:
            operations = self._operations_from_prompt_text(
                incumbent, attempt, positive_core or "", negative_core or "", corrections,
            )
        analysis = self._analyze_term_operations(
            incumbent["positive_core_terms"], incumbent["negative_core_terms"], {"operations": operations or []},
            {str(item["category"]) for item in corrections}, corrections,
        )
        return {"attempt_id": attempt_id, "operations_input": operations, **analysis}

    @classmethod
    def _operations_from_prompt_text(
        cls, incumbent: dict[str, Any], attempt: dict[str, Any], positive_core: str,
        negative_core: str, corrections: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        category = str((corrections or [{"category": ""}])[0]["category"])
        allowed_categories = {str(item["category"]) for item in corrections}
        prior_operations = attempt.get("response", {}).get("operations") or []

        def operation_category(target: str, term_id: str = "", new: str = "") -> str:
            for item in prior_operations:
                if not isinstance(item, dict) or str(item.get("target") or "") != target:
                    continue
                if term_id and str(item.get("term_id") or "") == term_id:
                    candidate = str(item.get("category") or category)
                    return candidate if candidate in allowed_categories else category
                if new and cls._term_key(str(item.get("new") or "")) == cls._term_key(new):
                    candidate = str(item.get("category") or category)
                    return candidate if candidate in allowed_categories else category
            return category

        operations: list[dict[str, str]] = []
        for target, text, existing in (
            ("positive", positive_core, incumbent["positive_core_terms"]),
            ("negative", negative_core, incumbent["negative_core_terms"]),
        ):
            revised = cls._term_records(cls._clean_prompt_terms(text), target[0])
            if target == "positive" and not revised:
                raise PromptEvolutionError("The edited positive prompt cannot be empty.")
            revised_keys = [" ".join(item["text"].casefold().split()) for item in revised]
            if len(set(revised_keys)) != len(revised):
                raise PromptEvolutionError(f"The edited {target} prompt contains duplicate terms.")
            common = min(len(existing), len(revised))
            for index in range(common):
                current, replacement = existing[index], revised[index]
                if " ".join(current["text"].casefold().split()) != revised_keys[index]:
                    operations.append({
                        "target": target, "action": "edit", "term_id": current["id"], "new": replacement["text"],
                        "category": operation_category(target, current["id"], replacement["text"]),
                    })
            for item in reversed(existing[common:]):
                operations.append({
                    "target": target, "action": "remove", "term_id": item["id"], "new": "",
                    "category": operation_category(target, item["id"]),
                })
            for item in revised[common:]:
                operations.append({
                    "target": target, "action": "add", "term_id": "", "new": item["text"],
                    "category": operation_category(target, new=item["text"]),
                })
        if not operations:
            raise PromptEvolutionError("The edited prompt is unchanged.")
        return operations

    @classmethod
    def _analyze_refinement_response(
        cls, incumbent: dict[str, Any], data: dict[str, Any], corrections: list[dict[str, str]],
    ) -> dict[str, Any]:
        if "positive_core" not in data and "negative_core" not in data:
            return cls._analyze_term_operations(
                incumbent["positive_core_terms"], incumbent["negative_core_terms"], data,
                {str(item["category"]) for item in corrections}, corrections,
            )
        errors: list[dict[str, Any]] = []
        positive_value = data.get("positive_core")
        negative_value = data.get("negative_core")
        if not isinstance(positive_value, str) or not cls._clean_prompt_terms(positive_value):
            errors.append(cls._refinement_error(
                "missing_positive_core", None, "positive_core", "Refinement must return a non-empty positive_core string.",
            ))
        if not isinstance(negative_value, str):
            errors.append(cls._refinement_error(
                "missing_negative_core", None, "negative_core", "Refinement must return a negative_core string; it may be empty.",
            ))
        positive_core = cls._clean_prompt_terms(positive_value) if isinstance(positive_value, str) else ""
        negative_core = cls._clean_prompt_terms(negative_value) if isinstance(negative_value, str) else ""
        if not errors and (
            positive_core.casefold() == str(incumbent["positive_core"]).casefold()
            and negative_core.casefold() == str(incumbent["negative_core"]).casefold()
        ):
            errors.append(cls._refinement_error(
                "unchanged_prompts", None, "response", "Refinement returned unchanged prompt cores.",
            ))
        if errors:
            positive_terms = [{**item} for item in incumbent["positive_core_terms"]]
            negative_terms = [{**item} for item in incumbent["negative_core_terms"]]
            operations: list[dict[str, str]] = []
        else:
            positive_terms = cls._term_records(positive_core, "p")
            negative_terms = cls._term_records(negative_core, "n")
            try:
                operations = cls._operations_from_prompt_text(
                    incumbent, {"response": data}, positive_core, negative_core, corrections,
                )
            except PromptEvolutionError:
                operations = []
        return {
            "strict_valid": not errors,
            "guarded_override_allowed": False,
            "validation_errors": errors,
            "preview_status": "baseline" if errors else "complete",
            "positive_terms": positive_terms,
            "negative_terms": negative_terms,
            "positive_core": ", ".join(item["text"] for item in positive_terms),
            "negative_core": ", ".join(item["text"] for item in negative_terms),
            "operations": operations,
        }

    def accept_refinement_review(
        self, run_id: str, attempt_id: str, operations: list[Any] | None, confirm_override: bool,
        positive_core: str | None = None, negative_core: str | None = None,
    ) -> dict[str, Any]:
        run, batch_path, batch, attempt = self._refinement_review_context(run_id, attempt_id)
        text_edited = positive_core is not None or negative_core is not None
        edited = operations is not None or text_edited
        if text_edited:
            incumbent = run.get("exploration_incumbent") or run["incumbent"]
            operations = self._operations_from_prompt_text(
                incumbent, attempt, positive_core or "", negative_core or "", run.get("pending_corrections") or [],
            )
        data = {"operations": operations} if edited else attempt.get("response") or {}
        incumbent = run.get("exploration_incumbent") or run["incumbent"]
        corrections = run.get("pending_corrections") or []
        analysis = self._analyze_refinement_response(incumbent, data, corrections)
        if edited and not analysis["strict_valid"]:
            raise PromptEvolutionError("Edited operations remain invalid: " + " ".join(
                item["message"] for item in analysis["validation_errors"]
            ))
        if not edited and not analysis["strict_valid"]:
            if not analysis["guarded_override_allowed"]:
                raise PromptEvolutionError("This rejected attempt has blocking validation errors and must be edited.")
            if not confirm_override:
                raise PromptEvolutionError("Confirm the guarded validation override before using this attempt.")
        selected_attempt = attempt
        if edited:
            selected_attempt = {
                "attempt_id": f"human-{len(batch.get('refinement_attempts', [])) + 1:02d}",
                "number": len(batch.get("refinement_attempts", [])) + 1, "source": "human_edit",
                "ask_id": "", "output_file": "", "response": data,
                "validation_errors": analysis["validation_errors"], "strict_valid": True,
                "guarded_override_allowed": False, "preview_status": "complete",
                "positive_core": analysis["positive_core"], "negative_core": analysis["negative_core"],
                "operations": analysis["operations"], "accepted": True, "created_at": self._now(),
            }
            batch.setdefault("refinement_attempts", []).append(selected_attempt)
        else:
            attempt["accepted"] = True
            attempt["human_override"] = not analysis["strict_valid"]
            attempt["accepted_at"] = self._now()
        batch["mutation"] = analysis["operations"]
        batch["selected_refinement_attempt_id"] = selected_attempt["attempt_id"]
        batch["refinement_human_override"] = not analysis["strict_valid"]
        self._write_json(batch_path / "batch.json", batch)
        run["pending_mutation"] = analysis["operations"]
        run["pending_positive_terms"] = analysis["positive_terms"]
        run["pending_negative_terms"] = analysis["negative_terms"]
        run.pop("exploration_warning", None)
        run.pop("refinement_output", None)
        run.pop("refinement_attempt_number", None)
        run["current_batch"] = int(run["current_batch"]) + 1
        self._start_batch(run, analysis["positive_core"], analysis["negative_core"])
        return self.detail(run_id)

    def select_finalist(self, run_id: str, finalist_id: str, selection_reason: str = "") -> dict[str, Any]:
        run = self._find_run(run_id)
        if run.get("status") != "AWAITING_FINALIST":
            raise PromptEvolutionError("Run is not awaiting a finalist selection.")
        batches = [
            self._read_json(path)
            for path in sorted((Path(run["root"]) / "batches").glob("*/batch.json"))
        ]
        finalists, _ = self._finalist_choices(run, batches)
        finalist = next((item for item in finalists if item.get("finalist_id") == finalist_id), None)
        if finalist is None:
            raise PromptEvolutionError("Unknown prompt-evolution finalist.")
        latest_batch = next(
            (item for item in batches if int(item.get("index", -1)) == int(run.get("current_batch", -2))), None,
        )
        parent_finalist_id = str((latest_batch or {}).get("parent_finalist_id") or "")
        if not parent_finalist_id and int(run.get("current_batch", 0)) == 1:
            parent_finalist_id = str((run.get("incumbent") or {}).get("finalist_id") or "")
        if latest_batch and finalist_id == parent_finalist_id and int(finalist.get("batch", -1)) < int(run["current_batch"]):
            attempted_mutation = latest_batch.get("attempted_mutation") or []
            if attempted_mutation:
                run.setdefault("rejected_mutations", []).extend(attempted_mutation)
            rejected_ids = {
                item.get("finalist_id") for item in finalists
                if int(item.get("batch", -1)) == int(run["current_batch"])
            }
            run.setdefault("rejected_finalist_ids", []).extend(
                item for item in sorted(value for value in rejected_ids if value)
                if item not in run.get("rejected_finalist_ids", [])
            )
            latest_batch.update({
                "accepted": False, "human_rejected": True, "selected_finalist_id": finalist_id,
                "selection_reason": selection_reason.strip(), "status": "REJECTED",
            })
            self._write_json(
                Path(run["root"]) / "batches" / f"{int(run['current_batch']):03d}" / "batch.json", latest_batch,
            )
            run["exploration_incumbent"] = finalist
            run["last_rejected_finalist_selection"] = {
                "finalist_id": finalist_id, "rejected_batch": run["current_batch"],
                "reason": selection_reason.strip(), "at": self._now(),
            }
            run["pending_batch_slot"] = int(latest_batch.get("batch_slot", run["current_batch"]))
            run["pending_batch_retry"] = int(latest_batch.get("retry_attempt", 0)) + 1
            self._queue_v2_refinement(run, latest_batch, finalist, finalist, selection_reason)
            return self.detail(run_id)
        run["incumbent"] = {**finalist, "human_finalist_selection": True}
        run["selected_finalist_id"] = finalist_id
        if selection_reason.strip():
            run["finalist_selection_reason"] = selection_reason.strip()
        run["status"] = "COMPLETE"
        root = Path(run["root"])
        self._write_json(root / "prompt_core.json", {
            "strategy_version": int(run.get("strategy_version", 1)),
            "positive_core": finalist.get("positive_core", finalist.get("positive_prompt", "")),
            "negative_core": finalist.get("negative_core", finalist.get("negative_prompt", "")),
            "positive_terms": finalist.get("positive_core_terms", []),
            "negative_terms": finalist.get("negative_core_terms", []),
            "checkpoint": run.get("checkpoint", ""),
        })
        self._write_json(root / "evaluation_wrapper.json", finalist.get("evaluation_wrapper") or {
            "positive_terms": list(EVALUATION_POSITIVE_TERMS),
            "negative_terms": list(EVALUATION_NEGATIVE_TERMS),
        })
        self._save_run(run)
        return self.detail(run_id)

    def abort(self, run_id: str) -> dict[str, Any]:
        run = self._find_run(run_id)
        run["status"] = "ABORTED"
        self._save_run(run)
        return self.detail(run_id)

    def rename(self, run_id: str, name: str) -> dict[str, Any]:
        run = self._find_run(run_id)
        run["display_name"] = name.strip()[:120]
        self._save_run(run)
        return self.detail(run_id)

    def start_directed_refinement(self, run_id: str, instructions: str) -> dict[str, Any]:
        run = self._find_run(run_id)
        if run["status"] != "COMPLETE" or not run.get("incumbent"):
            raise PromptEvolutionError("Directed refinement requires a completed run with an incumbent image.")
        if not instructions.strip():
            raise PromptEvolutionError("Directed refinement instructions are required.")
        root = Path(run["root"])
        output = root / f"directed_refinement_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.json"
        incumbent = run["incumbent"]
        prompt = self._format_template(run, "directed_refinement", {
            "POSITIVE_PROMPT": str(incumbent.get("positive_core", incumbent["positive_prompt"])),
            "NEGATIVE_PROMPT": str(incumbent.get("negative_core", incumbent["negative_prompt"])),
            "METADATA": "",
            "METADATA_WORD_POOL": "", "INSTRUCTIONS": instructions.strip(),
        })
        ask_id = self._queue_ollama(run, task="directed_refinement", prompt=prompt, output=output, images=[Path(run["reference_image"])])
        run["directed_refinement"] = {"status": "QUEUED", "instructions": instructions.strip(), "ask_id": ask_id, "output": str(output)}
        run["status"] = "DIRECTED_REFINING"
        self._save_run(run)
        return self.detail(run_id)

    def delete(self, run_id: str) -> dict[str, Any]:
        run = self._find_run(run_id)
        if run["status"] in {"BOOTSTRAPPING", "RENDERING", "EVALUATING", "RANKING", "REFINING", "DIRECTED_REFINING", "AWAITING_FINALIST", "AWAITING_REFINEMENT_REVIEW"}:
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

    def start_replay_experiment(self, run_id: str, batch_index: int, seed: int, repeats: int = 3) -> dict[str, Any]:
        if not 1 <= int(repeats) <= 5:
            raise PromptEvolutionError("Replay repeats must be 1–5.")
        run = self._find_run(run_id)
        batch_path = Path(run["root"]) / "batches" / f"{int(batch_index):03d}" / "batch.json"
        if not batch_path.is_file():
            raise PromptEvolutionError("Replay batch does not exist.")
        batch = self._read_json(batch_path)
        candidate = next((item for item in batch.get("candidates", []) if int(item["seed"]) == int(seed)), None)
        if candidate is None:
            raise PromptEvolutionError("Replay candidate does not exist.")
        experiment_id = f"{run_id}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        root = Path(run["root"]).parent.parent / "Prompt_Evolution_Experiments" / experiment_id
        root.mkdir(parents=True)
        experiment_run = {**run, "run_id": experiment_id, "root": str(root)}
        prompt = self.template("evaluation").replace("{{SEED}}", str(seed))
        evaluations = []
        for index in range(1, int(repeats) + 1):
            output = root / f"evaluation_{index}.json"
            ask_id = self._queue_ollama(
                experiment_run, task=f"replay_evaluate_{index}", prompt=prompt, output=output,
                images=[Path(run["reference_image"]), Path(candidate["file"])],
            )
            evaluations.append({"index": index, "ask_id": ask_id, "output": str(output)})
        experiment = {
            "version": 1, "experiment_id": experiment_id, "source_run_id": run_id,
            "source_batch": int(batch_index), "source_seed": int(seed), "root": str(root),
            "reference_image": run["reference_image"], "candidate_image": candidate["file"],
            "checkpoint": run.get("checkpoint"), "profile": run.get("profile"),
            "cfg_scale": run.get("cfg_scale"), "steps": run.get("steps"),
            "positive_core": batch.get("positive_core", batch.get("positive_prompt", "")),
            "negative_core": batch.get("negative_core", batch.get("negative_prompt", "")),
            "positive_core_terms": batch.get("positive_core_terms") or self._term_records(batch.get("positive_prompt", ""), "p"),
            "negative_core_terms": batch.get("negative_core_terms") or self._term_records(batch.get("negative_prompt", ""), "n"),
            "evaluation_prompt": prompt, "evaluations": evaluations, "status": "EVALUATING",
            "created_at": self._now(), "updated_at": self._now(),
        }
        self._write_json(root / "experiment.json", experiment)
        return experiment

    def _find_replay_experiment(self, experiment_id: str) -> dict[str, Any]:
        base = Path(self.app.config.base_pipeline_path)
        matches = list(base.glob(f"**/Prompt_Evolution_Experiments/{experiment_id}/experiment.json"))
        if len(matches) != 1:
            raise FileNotFoundError(f"Prompt-evolution replay experiment not found: {experiment_id}")
        return self._read_json(matches[0])

    def advance_replay_experiment(self, experiment_id: str) -> dict[str, Any]:
        experiment = self._find_replay_experiment(experiment_id)
        if experiment["status"] == "COMPLETE":
            return experiment
        if experiment["status"] == "FAILED":
            if experiment.get("refinements") and all(Path(item["output"]).is_file() for item in experiment["refinements"]):
                experiment["status"] = "REFINING"
                experiment.pop("error", None)
            else:
                return experiment
        root = Path(experiment["root"])
        experiment_run = {
            "run_id": experiment_id, "root": str(root), "character": "Replay", "phase": "Replay",
            "model": DEFAULT_VISION_MODEL,
        }
        try:
            if experiment["status"] == "EVALUATING" and all(Path(item["output"]).is_file() for item in experiment["evaluations"]):
                results = [self._read_json(Path(item["output"])) for item in experiment["evaluations"]]
                for result in results:
                    self._score(result)
                feedback = results[0]["category_feedback"]
                ranges = {
                    category: round(max(float(result["category_feedback"][category]["score"]) for result in results)
                                    - min(float(result["category_feedback"][category]["score"]) for result in results), 2)
                    for category in feedback
                }
                candidate = {"evaluation": results[0], "checklist_effects": []}
                corrections = self._selected_corrections(candidate)
                prompt = self.template("refinement")
                values, schema = self._refinement_contract_values({
                    "positive_core_terms": experiment["positive_core_terms"],
                    "negative_core_terms": experiment["negative_core_terms"],
                    "positive_core": experiment["positive_core"], "negative_core": experiment["negative_core"],
                }, corrections, results[0].get("category_feedback", {}))
                for key, value in values.items():
                    prompt = prompt.replace("{{" + key + "}}", value)
                refinements = []
                text_prompt = prompt.replace(
                    "Image 1 is the sole reference. Image 2 is the rendered candidate to correct.",
                    "No images are attached. Edit only from the supplied current terms and corrective instructions.",
                )
                for variant, variant_prompt, images in (
                    ("corrective_text", text_prompt, []),
                    ("corrective_images", prompt, [Path(experiment["reference_image"]), Path(experiment["candidate_image"])]),
                ):
                    output = root / f"{variant}.json"
                    ask_id = self._queue_ollama(
                        experiment_run, task=f"replay_{variant}", prompt=variant_prompt, output=output, images=images,
                        response_schema=schema, temperature=0,
                    )
                    refinements.append({"variant": variant, "ask_id": ask_id, "output": str(output), "prompt": variant_prompt})
                experiment.update({
                    "evaluation_results": results, "score_ranges": ranges, "corrections": corrections,
                    "refinement_prompt": prompt, "refinements": refinements, "status": "REFINING",
                })
            elif experiment["status"] == "REFINING" and all(Path(item["output"]).is_file() for item in experiment["refinements"]):
                corrections = experiment["corrections"]
                variants = {}
                for item in experiment["refinements"]:
                    data = self._read_json(Path(item["output"]))
                    try:
                        analysis = self._analyze_refinement_response({
                            "positive_core_terms": experiment["positive_core_terms"],
                            "negative_core_terms": experiment["negative_core_terms"],
                            "positive_core": experiment["positive_core"],
                            "negative_core": experiment["negative_core"],
                        }, data, corrections)
                        if not analysis["strict_valid"]:
                            raise PromptEvolutionError(analysis["validation_errors"][0]["message"])
                        variants[item["variant"]] = {
                            "status": "VALID",
                            "positive_core": analysis["positive_core"],
                            "negative_core": analysis["negative_core"],
                            "operations": analysis["operations"],
                        }
                    except PromptEvolutionError as exc:
                        variants[item["variant"]] = {"status": "INVALID", "error": str(exc), "response": data}
                experiment.update({"variants": variants, "status": "COMPLETE"})
        except Exception as exc:
            experiment.update({"status": "FAILED", "error": str(exc)})
        experiment["updated_at"] = self._now()
        self._write_json(root / "experiment.json", experiment)
        return experiment

    def clone_from_batch(self, run_id: str, batch_index: int) -> dict[str, Any]:
        run = self._find_run(run_id)
        batch_path = Path(run["root"]) / "batches" / f"{int(batch_index):03d}" / "batch.json"
        if not batch_path.is_file():
            raise PromptEvolutionError(f"Batch does not exist: {batch_index}")
        batch = self._read_json(batch_path)
        settings = {
            key: run[key] for key in ("character", "phase", "costume", "view", "model", "checklist_model", "checkpoint", "profile", "cfg_scale", "steps", "batch_size", "total_batches", "metadata_mode", "mode") if key in run
        }
        settings["batch_size"] = max(2, int(settings.get("batch_size", 5)))
        settings["total_batches"] = max(2, int(settings.get("total_batches", 5)))
        return self.create_run(settings | {
            "positive_prompt": batch.get("positive_core", batch["positive_prompt"]),
            "negative_prompt": batch.get("negative_core", batch["negative_prompt"]),
        })

    def restart(self, run_id: str) -> dict[str, Any]:
        run = self._find_run(run_id)
        if run["status"] not in {"COMPLETE", "ABORTED", "FAILED", "AWAITING_FINALIST"}:
            raise PromptEvolutionError("Only terminal prompt-evolution runs can be restarted.")
        settings = {
            key: run[key]
            for key in (
                "character", "phase", "costume", "view", "model", "checklist_model", "checkpoint", "profile",
                "cfg_scale", "steps", "batch_size", "total_batches", "metadata_mode", "mode",
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
        if failed_stage == "EVALUATING" and self._retry_invalid_evaluations(run):
            return self.detail(run_id)
        run["status"] = failed_stage
        self._save_run(run)
        return self.advance_run(run_id)

    def _retry_invalid_evaluations(self, run: dict[str, Any]) -> bool:
        root = Path(run["root"])
        batch_path = root / "batches" / f"{int(run['current_batch']):03d}"
        batch = self._read_json(batch_path / "batch.json")
        checklist_path = root / "checklist_snapshot.json"
        checklist = self._read_json(checklist_path) if checklist_path.is_file() else {"items": []}
        queued = False
        for item in batch.get("evaluations", []):
            output = Path(item["output"])
            if not output.is_file():
                continue
            try:
                evaluation = self._llm_json(run, output)
                checklist_evaluation = self._llm_json(run, Path(item["checklist_output"])) if item.get("checklist_output") else None
                self._score(evaluation, checklist, checklist_evaluation)
            except PromptEvolutionError as exc:
                attempt = int(item.get("stage_retry_attempts", 0)) + 1
                retry_path = batch_path / f"evaluation_{item['seed']}.stage-retry-{attempt}.json"
                prompt = self._format_template(run, "evaluation", {
                    "METADATA": "", "METADATA_CONTEXT": "", "SEED": str(item["seed"]),
                }) + f"\n\nYour prior response was rejected: {exc}. Return every required structured category exactly as requested."
                item.update({
                    "output": str(retry_path),
                    "ask_id": self._queue_ollama(
                        run, task=f"evaluate_{item['seed']}_stage_retry_{attempt}", prompt=prompt,
                        output=retry_path, images=[Path(run["reference_image"]), Path(item["file"])],
                    ),
                    "stage_retry_attempts": attempt,
                    "stage_retry_error": str(exc),
                })
                queued = True
        if queued:
            batch["status"] = "EVALUATING"
            self._write_json(batch_path / "batch.json", batch)
            run["status"] = "EVALUATING"
            self._save_run(run)
        return queued

    def recover_missing_evaluations(self, run_id: str) -> dict[str, Any]:
        run = self._find_run(run_id)
        if run["status"] != "EVALUATING":
            raise PromptEvolutionError("Missing evaluations can only be recovered while a run is evaluating.")
        root = Path(run["root"])
        batch_path = root / "batches" / f"{int(run['current_batch']):03d}"
        batch = self._read_json(batch_path / "batch.json")
        snapshot = self.app.queue_snapshot()
        active_ask_ids = {
            str(item.get("ask_id") or item.get("job_id") or "")
            for lane in ("ask", "running", "answer")
            for item in snapshot.get(lane, [])
            if isinstance(item, dict)
        }
        checklist_path = root / "checklist_snapshot.json"
        checklist = self._read_json(checklist_path) if checklist_path.is_file() else {"items": []}
        checklist_questions = self._checklist_questions(checklist)
        recovered = []
        still_active = []
        passes = [
            ("category", "output", "ask_id", "recovery_attempts", "evaluation", "evaluate", None),
            ("checklist", "checklist_output", "checklist_ask_id", "checklist_recovery_attempts", "checklist_evaluation", "checklist", str(run.get("checklist_model") or DEFAULT_CHECKLIST_MODEL)),
        ]
        for kind, output_key, ask_key, attempts_key, template_name, task_name, model in passes:
            for item in batch.get("evaluations", []):
                if output_key not in item or Path(item[output_key]).is_file():
                    continue
                if str(item.get(ask_key) or "") in active_ask_ids:
                    still_active.append(item[ask_key])
                    continue
                attempt = int(item.get(attempts_key, 0)) + 1
                prompt = self._format_template(run, template_name, {
                    "METADATA": "", "METADATA_CONTEXT": "", "CHECKLIST": checklist_questions,
                    "CHECKLIST_QUESTIONS": checklist_questions, "SEED": str(item["seed"]),
                })
                ask_id = self._queue_ollama(
                    run, task=f"{task_name}_{item['seed']}_recovery_{attempt}", prompt=prompt,
                    output=Path(item[output_key]), images=[Path(run["reference_image"]), Path(item["file"])], model=model,
                )
                item.update({ask_key: ask_id, attempts_key: attempt, "recovered_at": self._now()})
                recovered.append({"seed": item["seed"], "kind": kind, "ask_id": ask_id})
        if not recovered:
            if still_active:
                raise PromptEvolutionError(f"Missing evaluation asks are still active: {', '.join(still_active)}")
            raise PromptEvolutionError("No missing evaluation outputs were found to recover.")
        batch["evaluation_recoveries"] = [*batch.get("evaluation_recoveries", []), {"at": self._now(), "items": recovered}]
        self._write_json(batch_path / "batch.json", batch)
        run["error"] = ""
        self._save_run(run)
        return self.detail(run_id)

    def _run_paths(self) -> list[Path]:
        base = Path(self.app.config.base_pipeline_path)
        return sorted(base.glob("**/Prompt_Evolution/*/run.json"), reverse=True) if base.exists() else []

    def _find_run(self, run_id: str) -> dict[str, Any]:
        for path in self._run_paths():
            if path.parent.name == run_id:
                return self._read_json(path)
        raise FileNotFoundError(f"Prompt-evolution run not found: {run_id}")

    def list_runs(self) -> list[dict[str, Any]]:
        return [self._read_json(path) for path in self._run_paths()]

    def detail(self, run_id: str) -> dict[str, Any]:
        run = self._find_run(run_id)
        if run.get("status") == "AWAITING_FINALIST" and run.get("error"):
            run["exploration_warning"] = str(run["error"])
            run["error"] = ""
        batches = []
        for path in sorted((Path(run["root"]) / "batches").glob("*/batch.json")) if (Path(run["root"]) / "batches").exists() else []:
            batches.append(self._read_json(path))
        if run.get("status") == "AWAITING_REFINEMENT_REVIEW":
            incumbent = run.get("exploration_incumbent") or run.get("incumbent") or {}
            corrections = run.get("pending_corrections") or []
            allowed_categories = {str(item["category"]) for item in corrections}
            for batch in batches:
                if int(batch.get("index", -1)) != int(run.get("current_batch", -2)):
                    continue
                for attempt in batch.get("refinement_attempts", []):
                    analysis = self._analyze_refinement_response(incumbent, attempt.get("response") or {}, corrections)
                    attempt.update({
                        "validation_errors": analysis["validation_errors"],
                        "strict_valid": analysis["strict_valid"],
                        "guarded_override_allowed": analysis["guarded_override_allowed"],
                        "preview_status": analysis["preview_status"],
                        "positive_core": analysis["positive_core"], "negative_core": analysis["negative_core"],
                        "operations": analysis["operations"],
                    })
        finalists, finalist_mode = self._finalist_choices(run, batches)
        return {**run, "batches": batches, "finalists": finalists, "finalist_mode": finalist_mode}

    @staticmethod
    def _finalist_choices(run: dict[str, Any], batches: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
        finalists = list(run.get("finalists") or [])
        warning = run.get("exploration_warning") or run.get("error")
        if run.get("status") != "AWAITING_FINALIST" or len(finalists) > 1 or not warning or not batches:
            return finalists, "shortlist"
        batch = batches[-1]
        incumbent_file = str((run.get("incumbent") or {}).get("file") or "")
        choices = []
        for candidate in batch.get("candidates") or []:
            choices.append({
                **candidate,
                "finalist_id": f"batch-{int(batch.get('index', 0)):03d}-seed-{candidate['seed']}",
                "positive_prompt": batch.get("positive_prompt", ""),
                "negative_prompt": batch.get("negative_prompt", ""),
                "positive_core": batch.get("positive_core", batch.get("positive_prompt", "")),
                "negative_core": batch.get("negative_core", batch.get("negative_prompt", "")),
                "positive_core_terms": batch.get("positive_core_terms", []),
                "negative_core_terms": batch.get("negative_core_terms", []),
                "evaluation_wrapper": batch.get("evaluation_wrapper", {}),
                "batch": batch.get("index", 0),
                "is_incumbent": str(candidate.get("file") or "") == incumbent_file,
            })
        if not any(item["is_incumbent"] for item in choices) and run.get("incumbent"):
            choices.append({**run["incumbent"], "is_incumbent": True})
        generator = random.Random(f"{run.get('run_id', '')}:candidate-fallback")
        generator.shuffle(choices)
        return choices or finalists, "candidate_fallback"

    def advance_active_runs(self) -> list[dict[str, Any]]:
        results = []
        for run in self.list_runs():
            if run["status"] not in {"COMPLETE", "ABORTED", "AWAITING_USER", "AWAITING_REFINEMENT_REVIEW"}:
                results.append(self.advance_run(run["run_id"]))
        return results
