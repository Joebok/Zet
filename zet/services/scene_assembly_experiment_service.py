"""Isolated FirstDay prompt-versus-layer scene assembly experiment."""
from __future__ import annotations

from datetime import datetime, timezone
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import time
import uuid
from typing import Any

import cv2
import numpy as np
import PIL
from PIL import Image, ImageChops, ImageDraw, ImageFont

from zet.services.comfyui_render_service import (
    compile_ir_to_comfyui_workflow,
    list_comfyui_node_types,
    run_comfyui_workflow,
)
from zet.services.config_service import ConfigService
from zet.services.local_render_policy import require_qwen_profile


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LIBRARY_ROOT = Path(r"C:\Users\Joe\Projects\Zet_Library_v5")
STORY_ROOT = LIBRARY_ROOT / "Moonsea" / "Stories" / "FirstDay"
BATCH_ROOT = LIBRARY_ROOT / "Moonsea" / "PipelineCandidates" / "Stories" / "FirstDay"
OUTPUT_ROOT = PROJECT_ROOT / "output" / "scene-assembly-comparison"
PROFILE_NAME = "comfyui-qwen-image-2-1-scene"
ARMS = ("A_original", "B_corrected", "C_layers")
SEEDS = tuple(range(1101, 1109))
CONFIG_PATH = PROJECT_ROOT / "config.toml"
PRESETS_PATH = PROJECT_ROOT / "Config" / "Local_Render_Presets.json"

_SCENES = {
    "Chapter-01-Standing-in-Wonder": {
        "batch": "a1ed3b000f824a14892001cf69d4bbec",
        "selected": {
            "group_target": "Schoolboys_440071c5_subscene",
            "group": "Schoolboys_440071c5_subscene-002",
            "main": "main-001-cc90dcd0",
            "main_attempt": "cc90dcd049cc40aa8af4a185acb9084e",
        },
        "output_size": (832, 1248),
        "members": ["Tsaeytte", "Schoolboy 1", "Schoolboy 2", "Kaeldor"],
        "layers": [
            {"key": "group", "label": "Schoolboys and Kaeldor", "box": (0.22, 0.50, 0.29, 0.24), "depth": 1},
            {"key": "Tsaeytte", "label": "Tsaeytte", "box": (0.54, 0.30, 0.30, 0.68), "depth": 3},
        ],
        "requirements": [
            "Tsaeytte stands at right in a back three-quarter view and looks up at the arch inscription while holding her books.",
            "A small, complete group of exactly three students is visible beyond the arch on the left.",
            'Tsaeytte speaks the exact words "Potential is nothing without discipline" in a readable balloon.',
        ],
        "dialogue": [{"text": "Potential is nothing without discipline", "speaker": "Tsaeytte", "lines": 2}],
        "speaker_locations": {"Tsaeytte": (0.68, 0.36)},
        "contact_points": {"group": [(0.18, 0.96), (0.50, 0.96), (0.82, 0.96)], "Tsaeytte": [(0.50, 0.99)]},
        "extract": {"Tsaeytte": (420, 344, 282, 870)},
        "dialogue_extract": [(558, 272, 205, 104)],
        "dialogue_box": (0.68, 0.20, 0.25, 0.10),
        "anchors": {"Tsaeytte": (575, 360, 0.5, 0.18)},
    },
    "Chapter-02-At-the-Arch": {
        "batch": "bc5874ca8480481da4d73e63bcd8ceea",
        "selected": {
            "group_target": "Schoolboys_and_Kaeldor_1791131636182_subscene",
            "group": "Schoolboys_and_Kaeldor_1791131636182_subscene-003-eda1bd68",
            "main": "main-006-690f8267",
            "main_attempt": "690f82677e3a42dcb0955bcdee439274",
        },
        "output_size": (1376, 768),
        "members": ["Valindia", "Schoolboy 1", "Schoolboy 2", "Kaeldor", "Tsaeytte"],
        "layers": [
            {"key": "Valindia", "label": "Valindia", "box": (0.18, 0.06, 0.25, 0.91), "depth": 3},
            {"key": "group", "label": "Schoolboys and Kaeldor", "box": (0.40, 0.19, 0.31, 0.77), "depth": 2},
            {"key": "Tsaeytte", "label": "Tsaeytte", "box": (0.65, 0.08, 0.28, 0.89), "depth": 3},
        ],
        "requirements": [
            "Valindia walks away at left and turns only her head toward Tsaeytte.",
            "Tsaeytte walks away at right, carrying her books, and turns only her head toward Valindia.",
            "The three boys roughhouse together in the middle distance beneath the arch.",
            'Valindia says the exact words "country girl" in a readable balloon.',
        ],
        "dialogue": [{"text": "country girl", "speaker": "Valindia", "lines": 1}],
        "speaker_locations": {"Valindia": (0.29, 0.16)},
        "contact_points": {"Valindia": [(0.50, 0.99)], "group": [(0.19, 0.96), (0.50, 0.98), (0.82, 0.96)],
                           "Tsaeytte": [(0.50, 0.99)]},
        "extract": {"Valindia": (250, 42, 365, 710), "Tsaeytte": (915, 42, 360, 710)},
        "dialogue_extract": [(366, 0, 180, 72)],
        "dialogue_box": (0.27, 0.01, 0.16, 0.10),
        "anchors": {"Valindia": (365, 84, 0.5, 0.18), "Tsaeytte": (1070, 100, 0.5, 0.18)},
    },
    "Chapter-03-Collision": {
        "batch": "b0eb6b5b168e49c9bfaf64ec4ac9fd36",
        "selected": {
            "group_target": "Kaeldor_and_the_Schoolboys_1791152906199_subscene",
            "pair_target": "Tsaeytte_and_Valindia_1791243031945_subscene",
            "group": "Kaeldor_and_the_Schoolboys_1791152906199_subscene-008-1b4658ec",
            "pair": "Tsaeytte_and_Valindia_1791243031945_subscene-001-f5e8bd76",
            "background": "background-004",
            "main": "main-001-99151f9f",
            "main_attempt": "99151f9f91304f2e850801db2588c666",
        },
        "output_size": (928, 1152),
        "members": ["Kaeldor", "Schoolboy 1", "Schoolboy 2", "Tsaeytte", "Valindia"],
        "layers": [
            {"key": "group", "label": "Kaeldor and the Schoolboys", "box": (0.01, 0.30, 0.48, 0.70), "depth": 3},
            {"key": "pair", "label": "Tsaeytte and Valindia", "box": (0.44, 0.40, 0.55, 0.57), "depth": 2},
        ],
        "requirements": [
            "Exactly five characters appear: Kaeldor, two schoolboys, Tsaeytte, and Valindia.",
            "Tsaeytte remains seated on the ground with her hands behind her supporting her, on the right with Valindia standing behind her.",
            "Retain all five books visible in the accepted source; separately record that the authored scene asks for four.",
            "The three boys occupy the left foreground as a single intact group; record whether Kaeldor reads as walking.",
            'Kaeldor has one small, readable speech balloon containing exactly "sorry".',
        ],
        "dialogue": [{"text": "sorry", "speaker": "Kaeldor", "lines": 1}],
        "speaker_locations": {"Kaeldor": (0.38, 0.43)},
        "contact_points": {"group": [(0.12, 0.98), (0.51, 0.98), (0.87, 0.98)],
                           "pair": [(0.14, 0.95), (0.76, 0.95)]},
        "extract": {},
        "dialogue_extract": [],
        "dialogue_box": None,
        "anchors": {},
    },
}


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _source_record(scene_slug: str, target: str, candidate_id: str | None = None,
                   attempt_id: str | None = None) -> dict[str, Any]:
    batch_root = BATCH_ROOT / scene_slug / "Local_Batches" / _SCENES[scene_slug]["batch"]
    state = _json(batch_root / "state.json")
    group = state["groups"][target]
    candidate_id = candidate_id or state["selected_views"].get(target)
    candidate = next((item for item in group["candidates"] if item["candidate_id"] == candidate_id), None)
    if candidate is None or not candidate.get("image_path"):
        raise ValueError(f"Selected source {scene_slug}/{target}/{candidate_id} is missing")
    path = Path(candidate["image_path"])
    if not path.is_file():
        raise ValueError(f"Selected image does not exist: {path}")
    attempt_id = attempt_id or candidate.get("attempt_id") or group.get("attempt_id")
    attempt = group.get("attempts", {}).get(attempt_id, group)
    return {"target": target, "candidate_id": candidate_id, "attempt_id": attempt_id,
            "image_path": str(path.resolve()), "sha256": _hash(path), "prompt_path": attempt.get("prompt_path"),
            "dimensions": list(_load_image(path).size),
            "ir_path": attempt.get("ir_path"), "snapshot_path": attempt.get("snapshot_path"),
            "references": attempt.get("reference_images", [])}


def _load_image(path: Path) -> Image.Image:
    with Image.open(path) as image:
        return image.convert("RGBA")


def _grabcut(image: Image.Image, roi: tuple[int, int, int, int]) -> Image.Image:
    """Create a human-reviewable full-resolution GrabCut mask from an authored ROI."""
    rgba = np.asarray(image.convert("RGBA"))
    h, w = rgba.shape[:2]
    x, y, rw, rh = roi
    x, y = max(0, x), max(0, y)
    rw, rh = min(rw, w - x), min(rh, h - y)
    if rw < 8 or rh < 8:
        raise ValueError(f"Extraction rectangle falls outside {w}x{h}: {roi}")
    bgr = cv2.cvtColor(rgba[:, :, :3], cv2.COLOR_RGB2BGR)
    labels = np.full((h, w), cv2.GC_BGD, np.uint8)
    inset = max(2, min(rw, rh) // 90)
    labels[y + inset:y + rh - inset, x + inset:x + rw - inset] = cv2.GC_PR_FGD
    labels[y + rh // 3:y + 2 * rh // 3, x + rw // 3:x + 2 * rw // 3] = cv2.GC_FGD
    bg_model, fg_model = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(bgr, labels, None, bg_model, fg_model, 6, cv2.GC_INIT_WITH_MASK)
    mask = np.isin(labels, (cv2.GC_FGD, cv2.GC_PR_FGD))
    # GrabCut is the foreground classifier. A global color flood is deliberately
    # avoided: scene backgrounds often share colors with hair, skin, books, and cloth.
    mask[:y, :] = False
    mask[y + rh:, :] = False
    mask[:, :x] = False
    mask[:, x + rw:] = False
    # Keep all connected components, including books, loose hair, ears and balloon tails.
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_CLOSE, kernel, iterations=1) > 0
    alpha = Image.fromarray(mask.astype(np.uint8) * 255, "L")
    cut = image.copy()
    cut.putalpha(alpha)
    bbox = alpha.getbbox()
    if bbox is None:
        raise ValueError(f"Empty extraction mask for {roi}")
    return cut.crop(bbox)


def _isolated_source_cutout(image: Image.Image, *, tolerance: int = 48) -> Image.Image:
    """Remove edge-connected near-white paper from accepted subscene artwork."""
    rgba = np.asarray(image.convert("RGBA"))
    rgb = rgba[:, :, :3].astype(np.int16)
    near_paper = (rgb.min(axis=2) >= 188) & ((rgb.max(axis=2) - rgb.min(axis=2)) <= tolerance)
    count, components = cv2.connectedComponents(near_paper.astype(np.uint8), connectivity=4)
    edge_components = set(components[0, :]) | set(components[-1, :]) | set(components[:, 0]) | set(components[:, -1])
    edge_components.discard(0)
    paper = np.isin(components, list(edge_components)) if count else np.zeros(near_paper.shape, bool)
    mask = ~paper
    # Keep edge antialiasing without shrinking detached books, hair or balloon tails.
    mask = cv2.dilate(mask.astype(np.uint8), np.ones((3, 3), np.uint8), iterations=1) > 0
    cut = image.copy()
    cut.putalpha(Image.fromarray(mask.astype(np.uint8) * 255, "L"))
    bbox = Image.fromarray(mask.astype(np.uint8) * 255, "L").getbbox()
    if bbox is None:
        raise ValueError("Uniform-background extraction removed the entire accepted source")
    return cut.crop(bbox)


def _fit(layer: Image.Image, box: tuple[float, float, float, float], canvas: tuple[int, int]) -> tuple[Image.Image, tuple[int, int]]:
    width, height = canvas
    x, y, bw, bh = box
    max_w, max_h = max(1, round(bw * width)), max(1, round(bh * height))
    factor = min(max_w / layer.width, max_h / layer.height)
    size = max(1, round(layer.width * factor)), max(1, round(layer.height * factor))
    scaled = layer.resize(size, Image.Resampling.LANCZOS)
    position = round((x + bw / 2) * width - size[0] / 2), round((y + bh) * height - size[1])
    return scaled, position


class SceneAssemblyExperimentService:
    """Freeze, prepare, compile, render and review a non-production scene experiment."""

    def __init__(self, run_id: str):
        self.run_id = str(run_id)
        self.root = (OUTPUT_ROOT / self.run_id).resolve()
        if not self.root.is_relative_to(OUTPUT_ROOT.resolve()):
            raise ValueError("Experiment output must stay within the configured output root")
        self.config = ConfigService.load(CONFIG_PATH)

    def _scene_dir(self, slug: str) -> Path:
        if slug not in _SCENES:
            raise ValueError(f"Unsupported scene: {slug}")
        return self.root / slug

    def freeze(self) -> dict[str, Any]:
        manifest_path = self.root / "manifest.json"
        if manifest_path.exists():
            raise ValueError("Inputs are already frozen; start a new run to change sources")
        self.root.mkdir(parents=True, exist_ok=False)
        manifest: dict[str, Any] = {
            "schema_version": 1, "run_id": self.run_id, "created_at": datetime.now(timezone.utc).isoformat(),
            "profile": PROFILE_NAME, "profile_settings": self._profile(), "seeds": list(SEEDS),
            "arms": list(ARMS), "scenes": {},
            "checkpoint": self.config.comfyui_checkpoint, "server_url": self.config.comfyui_server_url,
            "seed_arm_schedule": {str(seed): list(ARMS[SEEDS.index(seed) % len(ARMS):]) +
                                  list(ARMS[:SEEDS.index(seed) % len(ARMS)]) for seed in SEEDS},
            "environment": {"python": __import__("sys").version, "pillow": PIL.__version__,
                            "numpy": np.__version__, "opencv": cv2.__version__},
        }
        for slug, spec in _SCENES.items():
            scene_dir = self._scene_dir(slug)
            target_map = {"group": spec["selected"]["group_target"], "main": "main"}
            if "pair" in spec["selected"]:
                target_map["pair"] = spec["selected"]["pair_target"]
            if "background" in spec["selected"]:
                target_map["background"] = "background"
            if "main" in spec["selected"]:
                target_map["main"] = "main"
            sources = {key: _source_record(slug, target_map[key], spec["selected"].get(key),
                                           spec["selected"].get("main_attempt") if key == "main" else None)
                       for key in target_map if key == "main" or key in spec["selected"]}
            if "main" not in sources:
                sources["main"] = _source_record(slug, "main", attempt_id=spec["selected"]["main_attempt"])
            for name, record in sources.items():
                source_dir = scene_dir / "frozen" / "source_images"
                source_dir.mkdir(parents=True, exist_ok=True)
                source = Path(record["image_path"])
                destination = source_dir / f"{name}{source.suffix or '.png'}"
                shutil.copy2(source, destination)
                record["frozen_path"] = str(destination)
                for path_key in ("prompt_path", "ir_path", "snapshot_path"):
                    source_file = Path(record[path_key]) if record.get(path_key) else None
                    if source_file and source_file.is_file():
                        dest = scene_dir / "frozen" / f"{name}_{source_file.name}"
                        shutil.copy2(source_file, dest)
                        record[f"frozen_{path_key}"] = str(dest)
                record["source_sha256_verified"] = _hash(destination) == record["sha256"]
            # Freeze every shared main-scene reference in its existing order.
            shared_refs = []
            for ref in sources["main"].get("references", []):
                source = Path(str(ref.get("path") or ""))
                if not source.is_file():
                    raise ValueError(f"Missing main-scene reference: {source}")
                try:
                    with Image.open(source) as source_image:
                        extension = source.suffix or f".{str(source_image.format or 'png').lower()}"
                except Exception as exc:
                    raise ValueError(f"Main-scene reference is not a readable image: {source}") from exc
                dest = scene_dir / "frozen" / "references" / f"{len(shared_refs)+1:02d}_{source.stem}{extension}"
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, dest)
                shared_refs.append({**ref, "path": str(dest), "source_path": str(source.resolve()),
                                    "sha256": _hash(source)})
            manifest["scenes"][slug] = {
                "sources": sources, "shared_references": shared_refs,
                "output_size": list(spec["output_size"]), "members": spec["members"],
                "profile_settings": self._profile(slug),
                "requirements": spec["requirements"], "dialogue": spec["dialogue"],
                "inherited_defects": (["Accepted group contains five books although authored requirement is four.",
                                       "Accepted Kaeldor stride may read as standing rather than walking."]
                                      if slug == "Chapter-03-Collision" else []),
                "arm_status": {arm: {str(seed): "PENDING" for seed in SEEDS} for arm in ARMS},
            }
        _write_json(manifest_path, manifest)
        return manifest

    def _manifest(self) -> dict[str, Any]:
        path = self.root / "manifest.json"
        if not path.is_file():
            raise ValueError("Run freeze before using this command")
        return _json(path)

    def prepare(self) -> dict[str, Any]:
        manifest = self._manifest()
        for slug, spec in _SCENES.items():
            state = manifest["scenes"][slug]
            state["profile_settings"] = self._profile(slug)
            scene_dir = self._scene_dir(slug)
            for name, source_record in state["sources"].items():
                frozen_source = Path(source_record["frozen_path"])
                if not frozen_source.is_file() or _hash(frozen_source) != source_record["sha256"]:
                    raise ValueError(f"{slug}/{name}: frozen source image changed or is missing")
            for ref in state["shared_references"]:
                ref_path = Path(ref["path"])
                original_hash = ref["sha256"]
                source_ref = Path(ref.get("source_path") or "")
                if source_ref.is_file() and _hash(source_ref) != original_hash:
                    raise ValueError(f"{slug}: selected reference source changed: {source_ref}")
                if not ref_path.is_file() or _hash(ref_path) != original_hash:
                    raise ValueError(f"{slug}: frozen reference changed or is missing: {ref_path}")
            for ref in state["shared_references"]:
                ref_path = Path(ref["path"])
                if not ref_path.suffix:
                    with Image.open(ref_path) as source_image:
                        suffix = f".{str(source_image.format or 'png').lower()}"
                    typed_path = ref_path.with_suffix(suffix)
                    if not typed_path.exists():
                        shutil.copy2(ref_path, typed_path)
                    if _hash(typed_path) != ref["sha256"]:
                        raise ValueError(f"Frozen reference hash changed: {ref_path}")
                    ref["path"] = str(typed_path)
            shots: dict[str, Any] = {"canvas": spec["output_size"], "layers": [], "dialogue": spec["dialogue"],
                                     "requirements": spec["requirements"],
                                     "speaker_locations": spec["speaker_locations"]}
            for item in spec["layers"]:
                if item["key"] == "group":
                    source = Path(state["sources"]["group"]["frozen_path"])
                    source_image = _load_image(source)
                    layer = _isolated_source_cutout(source_image)
                elif item["key"] == "pair":
                    source_image = _load_image(Path(state["sources"]["pair"]["frozen_path"]))
                    layer = _isolated_source_cutout(source_image)
                else:
                    source = Path(state["sources"]["main"]["frozen_path"])
                    layer = _grabcut(_load_image(source), spec["extract"][item["key"]])
                layer_path = scene_dir / "prepared" / f"{item['key']}.png"
                layer_path.parent.mkdir(parents=True, exist_ok=True)
                layer.save(layer_path)
                shots["layers"].append({**item, "path": str(layer_path), "sha256": _hash(layer_path),
                                        "bbox": layer.getbbox(), "source_pixels": layer.width * layer.height})
            # Keep original control dialogue as its own exact raster layer. Chapter 03's
            # balloon remains attached to the accepted boys' source group.
            dialogue_layers: list[Path] = []
            for dialogue_index, roi in enumerate(spec.get("dialogue_extract", []), 1):
                source_image = _load_image(Path(state["sources"]["main"]["frozen_path"]))
                layer = _grabcut(source_image, roi)
                layer_path = scene_dir / "prepared" / f"dialogue-{dialogue_index:02d}.png"
                layer.save(layer_path)
                dialogue_layers.append(layer_path)
                shots["layers"].append({"key": f"dialogue-{dialogue_index:02d}",
                                        "label": "Original dialogue balloon", "box": spec["dialogue_box"],
                                        "depth": 5, "path": str(layer_path), "sha256": _hash(layer_path),
                                        "bbox": layer.getbbox(), "source_pixels": layer.width * layer.height,
                                        "dialogue_layer": True})
            # Control identity slots carry the matching foreground and its dialogue
            # as one shared reference raster; the balloon remains a separate scene layer.
            if slug != "Chapter-03-Collision" and dialogue_layers:
                speaker = spec["dialogue"][0]["speaker"]
                person = _load_image(scene_dir / "prepared" / f"{speaker}.png")
                bubble = _load_image(dialogue_layers[0])
                reference = Image.new("RGBA", (512, 768), "white")
                person.thumbnail((390, 740), Image.Resampling.LANCZOS)
                bubble.thumbnail((210, 150), Image.Resampling.LANCZOS)
                reference.alpha_composite(person, (8, 768 - person.height - 8))
                reference.alpha_composite(bubble, (512 - bubble.width - 8, 8))
                reference_path = scene_dir / "prepared" / f"reference_{speaker}_with_dialogue.png"
                reference.convert("RGB").save(reference_path)
                shots["dialogue_reference"] = str(reference_path)
            if slug != "Chapter-03-Collision":
                main_refs = state["shared_references"]
                background = next((Path(item["path"]) for item in main_refs
                                   if "arch" in str(item.get("label") or "").casefold()), None)
            else:
                background = Path(state["sources"]["background"]["frozen_path"])
            if not background or not background.is_file():
                raise ValueError(f"No frozen background image for {slug}")
            source_bg = _load_image(background)
            target_w, target_h = tuple(spec["output_size"])
            factor = max(target_w / source_bg.width, target_h / source_bg.height)
            bg_size = max(target_w, round(source_bg.width * factor)), max(target_h, round(source_bg.height * factor))
            bg = source_bg.resize(bg_size, Image.Resampling.LANCZOS)
            left, top = (bg.width - target_w) // 2, (bg.height - target_h) // 2
            bg = bg.crop((left, top, left + target_w, top + target_h))
            bg_path = scene_dir / "prepared" / "background.png"
            bg_path.parent.mkdir(parents=True, exist_ok=True)
            bg.save(bg_path)
            shots["background"] = {"path": str(bg_path), "source_path": str(background), "sha256": _hash(bg_path)}
            # Save inspectable cutout previews and the deterministic layer composite.
            canvas = bg.copy()
            masks: list[Image.Image] = []
            ordered = sorted(shots["layers"], key=lambda x: x["depth"])
            for item in ordered:
                layer = _load_image(Path(item["path"]))
                scaled, position = _fit(layer, item["box"], tuple(spec["output_size"]))
                canvas.alpha_composite(scaled, position)
                full_mask = Image.new("L", tuple(spec["output_size"]), 0)
                full_mask.paste(scaled.getchannel("A"), position)
                masks.append(full_mask)
                item["placed_size"] = scaled.size
                item["position"] = position
                local_points = spec["contact_points"].get(item["key"], [])
                item["contact_points"] = [[round(position[0] + px * scaled.width),
                                            round(position[1] + py * scaled.height)] for px, py in local_points]
            comp_dir = scene_dir / "prepared"
            canvas.save(comp_dir / "layout-preview.png")
            _write_json(comp_dir / "shot.json", shots)
            # Opaque overlay, with a 16 px exterior seam band and 48 px ground contacts.
            h, w = spec["output_size"][1], spec["output_size"][0]
            union = np.maximum.reduce([np.asarray(mask) for mask in masks]) if masks else np.zeros((h, w), np.uint8)
            binary = (union > 0).astype(np.uint8)
            Image.fromarray(binary * 255, "L").save(comp_dir / "protected-foreground-mask.png")
            radius = max(1, round(16 * min(w, h) / 1024))
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * radius + 1, 2 * radius + 1))
            dilated = cv2.dilate(binary, kernel)
            edit_mask = ((dilated > 0) & (binary == 0)).astype(np.uint8) * 255
            for item in shots["layers"]:
                if item.get("dialogue_layer"):
                    continue
                contact_radius = max(1, round(48 * min(w, h) / 1024))
                for cx, cy in item.get("contact_points", []):
                    center = (min(w-1, max(0, cx)), min(h-1, max(0, cy)))
                    cv2.circle(edit_mask, center, contact_radius, 255, -1)
            edit_mask[binary > 0] = 0
            Image.fromarray(edit_mask, "L").save(comp_dir / "qwen-edit-mask.png")
            canvas.save(comp_dir / "layer-composite.png")
            for arm in ARMS:
                for seed in SEEDS:
                    arm_dir = scene_dir / "renders" / arm / str(seed)
                    arm_dir.mkdir(parents=True, exist_ok=True)
                    state["arm_status"][arm][str(seed)] = "PREPARED"
            state["shot"] = shots
            state["prepared_hashes"] = {p.name: _hash(p) for p in comp_dir.iterdir() if p.is_file()}
            state["prep_status"] = "REVIEW_REQUIRED"
        _write_json(self.root / "manifest.json", manifest)
        return manifest

    def _compile_workflow(self, slug: str, arm: str, seed: int) -> tuple[dict[str, Any], str, list[dict[str, Any]]]:
        manifest = self._manifest()
        scene = manifest["scenes"][slug]
        spec = _SCENES[slug]
        size = tuple(scene["output_size"])
        shared = self._shared_experiment_references(slug, scene)
        main_prompt = Path(scene["sources"]["main"]["frozen_prompt_path"]).read_text(encoding="utf-8")
        if arm == "A_original":
            prompt = main_prompt
            references = shared
        elif arm == "B_corrected":
            prompt = self._corrected_prompt(slug, scene, shared)
            references = shared
        else:
            prompt = self._layer_prompt(slug, scene)
            composite = self._scene_dir(slug) / "prepared" / "layer-composite.png"
            references = [{"path": str(composite), "label": "Canvas image", "tag": "<image1>", "image_index": 1}]
            references.extend(shared)
        refs_for_comfy = []
        for index, ref in enumerate(references, 1):
            path = Path(str(ref.get("path") or ""))
            if not path.is_file():
                raise ValueError(f"Frozen render reference is missing: {path}")
            refs_for_comfy.append({**ref, "path": str(path), "image_index": index,
                                   "comfyui_input_name": f"ZetExperiment/{slug}/{arm}/{index:02d}_{path.name}"})
        ir = {
            "schema_version": 4, "prompt_schema_version": 1,
            "source": {},
            "scene": {"slug": slug, "story_beat": ""},
            "canvas": {"orientation": "portrait" if size[1] > size[0] else "landscape",
                       "aspect_ratio": f"{size[0]}:{size[1]}"},
            "style": {"canonical_art_style": "Painterly semi-realistic fantasy illustration with anime-influenced facial stylization and refined linework."},
            "environment": {"location": "", "lighting": "Morning sunlight", "weather_or_atmosphere": "Clear", "mood": ""},
            "composition": {"focal_point": "Tsaeytte"},
            "elements": [], "placements": [], "image_inputs": [
                {"index": i, "tag": f"<image{i}>", "label": ref["label"],
                 "role": ("edit_base" if arm == "C_layers" and i == 1 else
                          "background_reference" if any(token in str(ref["label"]).casefold() for token in ("background", "archway")) else
                          "group_reference"),
                 "applies_to": ref["label"], "preserve": [], "change": [], "ignore": []}
                for i, ref in enumerate(refs_for_comfy, 1)
            ],
            "references": refs_for_comfy, "resolved_sources": {}, "dialogue": [], "render_mode": "composite",
        }
        workflow = compile_ir_to_comfyui_workflow(
            ir, self._profile(slug), checkpoint=self.config.comfyui_checkpoint,
            positive_prompt_globals="", negative_prompt_globals="", seed=seed,
            output_prefix=f"ZetExperiment/{self.run_id}/{slug}/{arm}/{seed}",
            reference_files=refs_for_comfy, available_node_types=set(list_comfyui_node_types(self.config.comfyui_server_url)),
            scene_prompt_override=prompt,
        )
        if (workflow.width, workflow.height) != size:
            raise ValueError(f"{slug}: compiled output size {(workflow.width, workflow.height)} differs from frozen {size}")
        return workflow.workflow, prompt, workflow.debug.get("references_used", refs_for_comfy)

    def _profile(self, scene_slug: str | None = None) -> dict[str, Any]:
        profile = _json(PRESETS_PATH)[PROFILE_NAME]
        profile = dict(profile)
        profile["width"], profile["height"] = 1024, 1024
        # Scene dimensions are multiples of 32 and define the exact frozen output canvas.
        profile["pixel_budget"] = (math.prod(_SCENES[scene_slug]["output_size"])
                                    if scene_slug else 1048576)
        return profile

    def _shared_experiment_references(self, slug: str, scene: dict[str, Any]) -> list[dict[str, Any]]:
        """Replace foreground slots for controls while retaining original slot order."""
        refs = [dict(item) for item in scene["shared_references"]]
        if slug == "Chapter-03-Collision":
            return refs
        shot = scene["shot"]
        for slot, ref in enumerate(refs, 1):
            label = str(ref.get("label") or "")
            replacement: Path | None = None
            if "Schoolboys" in label:
                replacement = self._scene_dir(slug) / "prepared" / "group.png"
            elif any(name in label for name in ("Tsaeytte", "Valindia")):
                speaker = scene["dialogue"][0]["speaker"]
                dialogue_ref = shot.get("dialogue_reference") if speaker in label else None
                character = "Tsaeytte" if "Tsaeytte" in label else "Valindia"
                replacement = Path(dialogue_ref) if dialogue_ref else self._scene_dir(slug) / "prepared" / f"{character}.png"
            elif "Valindia" in label:
                replacement = self._scene_dir(slug) / "prepared" / "Valindia.png"
            if replacement:
                reference_image = _load_image(replacement)
                if reference_image.getchannel("A").getextrema() != (255, 255):
                    flattened = Image.new("RGB", reference_image.size, "white")
                    flattened.paste(reference_image.convert("RGB"), mask=reference_image.getchannel("A"))
                    flattened_path = self._scene_dir(slug) / "prepared" / f"reference-slot-{slot}-{replacement.stem}.jpg"
                    flattened.save(flattened_path, quality=94)
                    replacement = flattened_path
                ref["path"] = str(replacement)
                ref["label"] = label
                ref["source_role"] = "extracted foreground replacing accepted reference slot"
        return refs

    @staticmethod
    def _corrected_prompt(slug: str, scene: dict[str, Any], refs: list[dict[str, Any]]) -> str:
        tags = [f"<image{i}>" for i in range(1, len(refs) + 1)]
        background_name = "the background scene image" if slug == "Chapter-03-Collision" else "the archway image"
        lines = ["Create one finished illustrated story frame by composing the supplied references.",
                 f"Use {background_name} as the background canvas. Place the source groups as complete cutouts; do not invent extra people."]
        for tag, ref in zip(tags, refs):
            label = str(ref.get("label") or "visual reference")
            role = "the accepted character pose and clothing" if "Tsaeytte" in label or "Valindia" in label else "the accepted group appearance and internal arrangement" if "Schoolboys" in label or "Kaeldor" in label else "the archway architecture and inscription"
            lines.append(f"{tag} supplies {role} for {label}.")
        if slug == "Chapter-01-Standing-in-Wonder":
            lines.extend(["Place the three-student group small in the distant left arch opening. Place the single woman prominently in the right foreground, about three times the group's height.",
                          "Keep her back three-quarter pose and upward gaze; keep her books against her left side. Leave clear space above and to her left for her balloon."])
        elif slug == "Chapter-02-At-the-Arch":
            lines.extend(["Place the boys as a compact middle-distance group beneath the central arch. Put the tall red-haired woman at left and the petite dark-haired woman at right in the foreground, at matching full-body scale.",
                          "Keep each woman's accepted walking pose and head turn. Leave a small clear balloon area above the left woman."])
        else:
            lines.extend(["Place <image2>'s intact three-boy group in the left foreground, occupying roughly the left half of the frame. Place <image3>'s intact two-woman group at center-right behind them, at about four-fifths of the boys' height.",
                          "Tsaeytte stays seated with both supporting hands on the ground and remains visually prominent; Valindia stands immediately behind her. Preserve the source overlap and all five books."])
        lines.extend(["Place each source exactly once. Preserve pose, body proportions, expression, costume, group membership, and every visible prop shown in that source.",
                      "Maintain natural depth and overlap, keep visible feet in contact with the path, and preserve each group's internal arrangement."])
        lines.extend(scene["requirements"])
        lines.append("Keep the arch inscription readable and consistent with its reference. Use painterly semi-realistic fantasy illustration with refined anime-influenced facial stylization.")
        lines.extend(f"Draw one dialogue balloon for {d['speaker']} containing exactly \"{d['text']}\" on no more than {d['lines']} line(s); point it to that speaker and keep it clear of faces." for d in scene["dialogue"])
        return " ".join(lines)

    @staticmethod
    def _requirement_trace(scene: dict[str, Any], prompt: str) -> dict[str, str]:
        trace = {}
        for requirement in scene["requirements"]:
            keywords = [word for word in requirement.split() if len(word) > 5]
            matching = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", prompt)
                        if sum(word.casefold() in sentence.casefold() for word in keywords) >= 2]
            trace[requirement] = " ".join(matching) if matching else "UNRESOLVED"
        return trace

    @staticmethod
    def _layer_prompt(slug: str, scene: dict[str, Any]) -> str:
        return ("Edit <image1>, the assembled canvas. Preserve all people, their pose, identity, proportions, costumes, props, the arch, and all readable text exactly as shown. "
                "Blend only the narrow joins between the placed cutouts and the background, and add believable contact shadows beneath visible feet. Do not move, resize, rotate, redraw, add, or remove any figure or prop. "
                "Use <image2> and later images only to confirm identity and group appearance. Preserve each reference group's internal arrangement. "
                + " ".join(scene["requirements"]))

    def compile(self) -> dict[str, Any]:
        manifest = self._manifest()
        for slug, scene in manifest["scenes"].items():
            if scene.get("prep_status") != "APPROVED":
                raise ValueError(f"{slug}: inspect layout-preview.png and run approve-layouts before compiling")
            for filename, digest in scene.get("prepared_hashes", {}).items():
                path = self._scene_dir(slug) / "prepared" / filename
                if not path.is_file() or _hash(path) != digest:
                    raise ValueError(f"{slug}: prepared render input changed after layout approval: {filename}")
            for arm in ARMS:
                for seed in SEEDS:
                    workflow, prompt, references = self._compile_workflow(slug, arm, seed)
                    target = self._scene_dir(slug) / "renders" / arm / str(seed)
                    target.mkdir(parents=True, exist_ok=True)
                    _write_json(target / "workflow.json", workflow)
                    (target / "prompt.txt").write_text(prompt, encoding="utf-8")
                    _write_json(target / "references.json", references)
                    if arm == "B_corrected":
                        _write_json(target / "requirement-trace.json", self._requirement_trace(scene, prompt))
                    scene["arm_status"][arm][str(seed)] = "COMPILED"
        _write_json(self.root / "manifest.json", manifest)
        return manifest

    def approve_layouts(self) -> dict[str, Any]:
        manifest = self._manifest()
        for slug, scene in manifest["scenes"].items():
            preview = self._scene_dir(slug) / "prepared" / "layout-preview.png"
            if not preview.is_file():
                raise ValueError(f"{slug}: prepare assets before approving layouts")
            for name, digest in scene.get("prepared_hashes", {}).items():
                path = preview.parent / name
                if not path.is_file() or _hash(path) != digest:
                    raise ValueError(f"{slug}: prepared artifact changed after review: {name}")
            scene["prep_status"] = "APPROVED"
            scene["layout_approved_at"] = datetime.now(timezone.utc).isoformat()
        _write_json(self.root / "manifest.json", manifest)
        return manifest

    def _compose_result(self, slug: str, arm: str, proposal: Path, dest: Path) -> Path:
        if arm != "C_layers":
            shutil.copy2(proposal, dest)
            return dest
        scene_dir = self._scene_dir(slug)
        canvas = _load_image(scene_dir / "prepared" / "layer-composite.png")
        generated = _load_image(proposal).resize(canvas.size, Image.Resampling.LANCZOS)
        mask = _load_image(scene_dir / "prepared" / "qwen-edit-mask.png").getchannel("R")
        # Verify no protected character/dialogue pixels overlap the Qwen integration mask.
        protected_path = scene_dir / "prepared" / "protected-foreground-mask.png"
        protected = np.asarray(_load_image(protected_path).getchannel("R")) > 0
        edit = np.asarray(mask) > 0
        if np.any(protected & edit):
            raise ValueError("Qwen integration mask overlaps protected foreground pixels")
        merged = Image.composite(generated, canvas, mask)
        merged_pixels = np.asarray(merged)
        base_pixels = np.asarray(canvas)
        outside_changed = int(np.count_nonzero(np.any(merged_pixels[~edit] != base_pixels[~edit], axis=1)))
        if outside_changed:
            raise AssertionError("Protected composite pixels changed during layer integration")
        merged.save(dest)
        diff = ImageChops.difference(merged.convert("RGB"), canvas.convert("RGB"))
        diff_pixels = np.asarray(diff).copy()
        diff_pixels[~edit] = 0
        Image.fromarray(diff_pixels, "RGB").save(dest.parent / "pixel-difference.png")
        _write_json(dest.parent / "pixel-difference-verification.json", {
            "outside_edit_pixels_changed": outside_changed,
            "inside_edit_pixels_changed": int(np.count_nonzero(np.any(merged_pixels[edit] != base_pixels[edit], axis=1))),
            "protected_pixel_count": int(np.count_nonzero(protected)),
            "edit_mask_pixel_count": int(np.count_nonzero(edit)),
            "verified": True,
        })
        return dest

    def render(self, *, limit: int | None = None, only_smoke: bool = False) -> dict[str, Any]:
        manifest = self._manifest()
        require_qwen_profile(PROJECT_ROOT, PROFILE_NAME, checkpoint=self.config.comfyui_checkpoint)
        launched = 0
        profile = self._profile()
        for seed_index, seed in enumerate(SEEDS):
            arms = list(ARMS)
            shift = seed_index % len(arms)
            arms = arms[shift:] + arms[:shift]
            for slug, scene in manifest["scenes"].items():
                for arm in arms:
                    if only_smoke and launched:
                        return manifest
                    if limit is not None and launched >= limit:
                        _write_json(self.root / "manifest.json", manifest)
                        return manifest
                    status = scene["arm_status"][arm][str(seed)]
                    if status == "COMPLETE":
                        continue
                    if status not in {"COMPILED", "FAILED", "SUBMITTING"}:
                        raise ValueError(f"{slug}/{arm}/{seed}: run compile before rendering")
                    target = self._scene_dir(slug) / "renders" / arm / str(seed)
                    workflow_path = target / "workflow.json"
                    prompt_path = target / "prompt.txt"
                    if not workflow_path.is_file() or not prompt_path.is_file():
                        raise ValueError(f"{slug}/{arm}/{seed}: frozen compile artifacts are missing")
                    workflow = _json(workflow_path)
                    started = time.monotonic()
                    scene["arm_status"][arm][str(seed)] = "SUBMITTING"
                    _write_json(self.root / "manifest.json", manifest)
                    try:
                        result = run_comfyui_workflow(workflow, server_url=self.config.comfyui_server_url,
                                                      output_dir=target / "comfyui", reference_files=_json(target / "references.json"),
                                                      poll_seconds=self.config.comfyui_poll_seconds,
                                                      timeout_seconds=self.config.comfyui_timeout_seconds)
                        proposal = result.image_paths[0]
                        final_path = self._compose_result(slug, arm, proposal, target / "candidate.png")
                        _write_json(target / "result.json", {
                            "status": "COMPLETE", "seed": seed, "prompt_sha256": _hash(prompt_path),
                            "workflow_sha256": _hash(workflow_path), "output_sha256": _hash(final_path),
                            "proposal": str(proposal), "output": str(final_path), "prompt_id": result.prompt_id,
                            "elapsed_seconds": round(time.monotonic() - started, 2),
                            "dimensions": list(_load_image(final_path).size),
                        })
                        scene["arm_status"][arm][str(seed)] = "COMPLETE"
                    except Exception as exc:
                        scene["arm_status"][arm][str(seed)] = "FAILED"
                        journal_path = target / "comfyui" / "ComfyUI_Submission.json"
                        journal = _json(journal_path) if journal_path.is_file() else {}
                        _write_json(target / "result.json", {"status": "FAILED", "seed": seed, "error": str(exc),
                                                              "prompt_id": journal.get("prompt_id"),
                                                              "submission_status": journal.get("status"),
                                                              "submission_journal": str(journal_path),
                                                              "elapsed_seconds": round(time.monotonic() - started, 2)})
                        raise
                    _write_json(self.root / "manifest.json", manifest)
                    launched += 1
        return manifest

    def sheets(self) -> dict[str, str]:
        manifest = self._manifest()
        complete = sum(status == "COMPLETE" for scene in manifest["scenes"].values()
                       for arms in scene["arm_status"].values() for status in arms.values())
        if complete != len(_SCENES) * len(ARMS) * len(SEEDS):
            raise ValueError(f"Blinded evaluation requires all 72 scheduled outputs; currently complete: {complete}")
        manifest["seed_arm_schedule"] = {
            str(seed): list(ARMS[SEEDS.index(seed) % len(ARMS):]) +
            list(ARMS[:SEEDS.index(seed) % len(ARMS)]) for seed in SEEDS
        }
        manifest["render_completed_at"] = datetime.now(timezone.utc).isoformat()
        manifest["environment"]["pillow"] = PIL.__version__
        manifest["source_inventory"] = {}
        for slug, scene in manifest["scenes"].items():
            scene["profile_settings"] = self._profile(slug)
            manifest["source_inventory"][slug] = {"sources": {}, "references": []}
            for name, record in scene["sources"].items():
                frozen = Path(record["frozen_path"])
                if not frozen.is_file() or _hash(frozen) != record["sha256"]:
                    raise ValueError(f"{slug}/{name}: frozen source changed after render")
                with Image.open(frozen) as image:
                    record["dimensions"] = list(image.size)
                    record["format"] = image.format
                manifest["source_inventory"][slug]["sources"][name] = {
                    key: record.get(key) for key in ("target", "candidate_id", "attempt_id", "sha256", "dimensions", "format", "frozen_path")
                }
            for ref in scene["shared_references"]:
                ref_path = Path(ref["path"])
                if not ref_path.is_file() or _hash(ref_path) != ref["sha256"]:
                    raise ValueError(f"{slug}: shared frozen reference changed after render: {ref_path}")
                with Image.open(ref_path) as image:
                    size, image_format = image.size, image.format
                manifest["source_inventory"][slug]["references"].append({
                    "label": ref.get("label"), "path": str(ref_path), "sha256": ref["sha256"],
                    "dimensions": list(size), "format": image_format,
                })
        _write_json(self.root / "manifest.json", manifest)
        path = self.root / "evaluation.json"
        evaluation = _json(path) if path.exists() else {"schema_version": 1, "run_id": self.run_id, "items": {}}
        blinded_ids = {}
        for slug in manifest["scenes"]:
            for seed in SEEDS:
                order = sorted(ARMS, key=lambda arm: hashlib.sha256(
                    f"{self.run_id}:{slug}:{seed}:{arm}:order".encode()).hexdigest())
                panels, mapping = [], {}
                for arm in order:
                    result = _json(self._scene_dir(slug) / "renders" / arm / str(seed) / "result.json")
                    if result.get("status") != "COMPLETE":
                        continue
                    token = hashlib.sha256(f"{self.run_id}:{slug}:{seed}:{arm}:review".encode()).hexdigest()[:8]
                    mapping[token] = arm
                    image = _load_image(Path(result["output"]))
                    image.thumbnail((384, 480), Image.Resampling.LANCZOS)
                    panels.append((token, image))
                    evaluation["items"].setdefault(token, {
                        "scene": slug, "seed": seed,
                        "criteria": {name: {"result": "unreviewed", "reason": ""} for name in self._criteria(slug)},
                        "lettered_criteria": {
                            **{name: {"result": "unreviewed", "reason": ""}
                               for name in self._criteria(slug) if name != "native_dialogue"},
                            "lettered_dialogue": {"result": "unreviewed", "reason": ""},
                        },
                        "blinded_token": token,
                        "lettering_review": {"action": "pending", "balloon_box": None,
                                             "speaker_anchor": None, "reason": ""},
                    })
                sheet = Image.new("RGB", (len(panels) * 400, 530), "#e8e8e8")
                draw = ImageDraw.Draw(sheet)
                for i, (token, image) in enumerate(panels):
                    x = 8 + i * 400
                    sheet.paste(image.convert("RGB"), (x, 36))
                    draw.text((x, 10), token, fill="#111111")
                out = self._scene_dir(slug) / "blind-sheets" / f"seed-{seed}.jpg"
                out.parent.mkdir(parents=True, exist_ok=True)
                sheet.save(out, quality=92)
                blinded_ids[f"{slug}/{seed}"] = mapping
        _write_json(path, evaluation)
        _write_json(self.root / "unblinding-key.json", blinded_ids)
        self.export_review_csv()
        (self.root / "review-guide.md").write_text(self._review_guide(), encoding="utf-8")
        return {slug: str(self._scene_dir(slug) / "blind-sheets") for slug in manifest["scenes"]}

    def letter_sheets(self) -> dict[str, str]:
        manifest = self._manifest()
        blind_map = _json(self.root / "unblinding-key.json")
        for slug in manifest["scenes"]:
            for seed in SEEDS:
                mapping = blind_map.get(f"{slug}/{seed}", {})
                tokens = sorted(mapping, key=lambda token: hashlib.sha256(
                    f"{self.run_id}:{slug}:{seed}:{token}:lettered".encode()).hexdigest())
                panels = []
                for token in tokens:
                    arm = mapping[token]
                    path = self._scene_dir(slug) / "renders" / arm / str(seed) / "lettered" / "candidate.png"
                    if not path.is_file():
                        continue
                    image = _load_image(path)
                    image.thumbnail((384, 480), Image.Resampling.LANCZOS)
                    panels.append((token, image))
                if len(panels) != len(ARMS):
                    raise ValueError(f"{slug}/{seed}: all three lettered variants must exist before scoring")
                sheet = Image.new("RGB", (len(panels) * 400, 530), "#e8e8e8")
                draw = ImageDraw.Draw(sheet)
                for index, (token, image) in enumerate(panels):
                    x = 8 + index * 400
                    sheet.paste(image.convert("RGB"), (x, 36))
                    draw.text((x, 10), token, fill="#111111")
                out = self._scene_dir(slug) / "lettered-blind-sheets" / f"seed-{seed}.jpg"
                out.parent.mkdir(parents=True, exist_ok=True)
                sheet.save(out, quality=92)
        self.export_review_csv()
        return {slug: str(self._scene_dir(slug) / "lettered-blind-sheets") for slug in manifest["scenes"]}

    @staticmethod
    def _criteria(slug: str) -> list[str]:
        return ["cast_and_identity", "pose_and_expression", "props_and_source_retention", "facing_and_gaze",
                "scale_depth_and_grounding", "background_continuity", "native_dialogue", "integration_quality",
                "narrative_readability", "authored_requirements"]

    @staticmethod
    def review_criterion_info() -> dict[str, dict[str, str]]:
        return {
            "cast_and_identity": {"label": "Cast and identity", "question": "Are the required four or five people visible and recognizable in the accepted identities and costumes?"},
            "pose_and_expression": {"label": "Pose and expression", "question": "Are the accepted poses, expressions, and internal group arrangement preserved?"},
            "props_and_source_retention": {"label": "Props and source retention", "question": "Are source props retained? Five books pass source retention even though Chapter 03 asks for four."},
            "facing_and_gaze": {"label": "Facing and gaze", "question": "Do facing and gaze relationships match the intended interaction?"},
            "scale_depth_and_grounding": {"label": "Scale, depth, and grounding", "question": "Are relative sizes, foreground/background order, cropping, contact, and overlaps readable?"},
            "background_continuity": {"label": "Background continuity", "question": "Is the arch/background coherent, with inscriptions retained and no distracting holes or duplicated structures?"},
            "native_dialogue": {"label": "Native dialogue", "question": "Is the exact dialogue present once, legible, attached to the correct speaker, and safely placed?"},
            "integration_quality": {"label": "Integration quality", "question": "Are seams, halos, contact shadows, lighting, and pasted appearance acceptable?"},
            "narrative_readability": {"label": "Narrative readability", "question": "Does the scene read as intended, including departure motion or Chapter 03's aftermath?"},
            "authored_requirements": {"label": "Authored requirements", "question": "Does it meet the authored requirements separately from inherited source defects? Chapter 03 asks for four books and readable walking."},
        }

    def review_catalog(self) -> dict[str, Any]:
        """Return blinded candidate metadata for the local visual-review page."""
        manifest = self._manifest()
        evaluation = _json(self.root / "evaluation.json")
        blind_map = _json(self.root / "unblinding-key.json")
        items = evaluation.get("items", {})
        scenes = []
        for slug, scene in manifest["scenes"].items():
            candidates = []
            for seed in SEEDS:
                for token, item in items.items():
                    if item.get("scene") != slug or int(item.get("seed", -1)) != seed:
                        continue
                    arm = blind_map.get(f"{slug}/{seed}", {}).get(token)
                    if arm not in ARMS:
                        raise ValueError(f"Missing blinded arm assignment for {slug}/{seed}/{token}")
                    native = self._scene_dir(slug) / "renders" / arm / str(seed) / "candidate.png"
                    lettered = native.parent / "lettered" / "candidate.png"
                    if not native.is_file():
                        raise ValueError(f"Missing rendered image for blinded candidate {token}")
                    lettering_review = dict(item.get("lettering_review", {}))
                    if (lettering_review.get("action", "pending") in {"pending", ""}
                            and item.get("criteria", {}).get("native_dialogue", {}).get("result") == "pass"):
                        lettering_review["action"] = "reuse"
                    candidates.append({
                        "token": token,
                        "seed": seed,
                        "native": {key: dict(value) for key, value in item.get("criteria", {}).items()},
                        "lettered": {key: dict(value) for key, value in item.get("lettered_criteria", {}).items()},
                        "lettered_available": lettered.is_file(),
                        "lettering_review": lettering_review,
                    })
            scenes.append({"slug": slug, "candidates": candidates})
        return {"run_id": self.run_id, "scenes": scenes, "criteria": self.review_criterion_info()}

    def review_image_path(self, token: str, variant: str) -> Path:
        if variant not in {"native", "lettered"}:
            raise ValueError("Review variant must be native or lettered")
        manifest = self._manifest()
        items = _json(self.root / "evaluation.json").get("items", {})
        item = items.get(token)
        if item is None:
            raise ValueError("Unknown blinded candidate")
        scene, seed = item["scene"], int(item["seed"])
        arm = _json(self.root / "unblinding-key.json").get(f"{scene}/{seed}", {}).get(token)
        if scene not in manifest["scenes"] or arm not in ARMS:
            raise ValueError("Candidate does not belong to this experiment")
        path = self._scene_dir(scene) / "renders" / arm / str(seed) / "candidate.png"
        if variant == "lettered":
            path = path.parent / "lettered" / "candidate.png"
        if not path.is_file():
            raise FileNotFoundError(f"The {variant} image is not available yet")
        return path

    def save_candidate_review(self, token: str, variant: str, payload: dict[str, Any]) -> None:
        if variant not in {"native", "lettered"}:
            raise ValueError("Review variant must be native or lettered")
        evaluation_path = self.root / "evaluation.json"
        evaluation = _json(evaluation_path)
        item = evaluation.get("items", {}).get(token)
        if item is None:
            raise ValueError("Unknown blinded candidate")
        self.review_image_path(token, variant)
        field = "criteria" if variant == "native" else "lettered_criteria"
        available = item.get(field, {})
        changes = payload.get("criteria", {})
        if not isinstance(changes, dict):
            raise ValueError("Criteria review must be an object")
        for criterion, review in changes.items():
            if criterion not in available or not isinstance(review, dict):
                raise ValueError(f"Unknown review criterion: {criterion}")
            result = str(review.get("result", "unreviewed"))
            if result not in {"pass", "fail", "unassessable", "unreviewed"}:
                raise ValueError(f"Invalid review value for {criterion}: {result}")
            available[criterion] = {"result": result, "reason": str(review.get("reason", ""))[:2000]}
        lettering = payload.get("lettering_review")
        if lettering is not None:
            if not isinstance(lettering, dict):
                raise ValueError("Lettering review must be an object")
            action = str(lettering.get("action", "pending"))
            if action not in {"reuse", "replace", "add", "unsafe", "pending"}:
                raise ValueError(f"Invalid lettering action: {action}")
            box = lettering.get("balloon_box")
            anchor = lettering.get("speaker_anchor")
            if box is not None or anchor is not None:
                valid_box = isinstance(box, list) and len(box) == 4
                valid_anchor = isinstance(anchor, list) and len(anchor) == 2
                if not (valid_box and valid_anchor):
                    raise ValueError("Balloon area and speaker point must both be provided")
                values = [float(value) for value in [*box, *anchor]]
                if (any(value < 0 or value > 1 for value in values) or box[2] <= 0 or box[3] <= 0
                        or box[0] + box[2] > 1 or box[1] + box[3] > 1):
                    raise ValueError("Balloon box and speaker point must use normalized image coordinates")
            item["lettering_review"] = {"action": action, "balloon_box": box, "speaker_anchor": anchor,
                                        "reason": str(lettering.get("reason", ""))[:1000]}
        _write_json(evaluation_path, evaluation)
        self.export_review_csv()

    @staticmethod
    def _inherit_non_dialogue_ratings(item: dict[str, Any]) -> None:
        lettered = item.setdefault("lettered_criteria", {})
        for criterion, review in item.get("criteria", {}).items():
            if criterion != "native_dialogue":
                lettered[criterion] = {"result": review.get("result", "unreviewed"),
                                      "reason": review.get("reason", ""),
                                      "inherited_from": "native"}
        lettered.setdefault("lettered_dialogue", {"result": "unreviewed", "reason": ""})

    def generate_lettered_stage(self) -> dict[str, Any]:
        """Reuse dialogue already rated correct and apply reviewed repairs to the rest."""
        evaluation = _json(self.root / "evaluation.json")
        for token, item in evaluation.get("items", {}).items():
            self._inherit_non_dialogue_ratings(item)
            native_dialogue = item.get("criteria", {}).get("native_dialogue", {}).get("result")
            review = item.get("lettering_review", {})
            action = review.get("action", "pending")
            if action in {"pending", ""} and native_dialogue == "pass":
                action = "reuse"
            if action in {"pending", ""}:
                raise ValueError(f"Choose a dialogue repair for blinded candidate {token} before generation")
            if action in {"add", "replace"} and not (review.get("balloon_box") and review.get("speaker_anchor")):
                raise ValueError(f"Mark balloon placement and speaker point for blinded candidate {token}")
            review["action"] = action
            item["lettering_review"] = review
        _write_json(self.root / "evaluation.json", evaluation)
        counts = self.letter_variants()
        if counts["pending"]:
            raise ValueError(f"{counts['pending']} lettered versions still need repair instructions")
        sheets = self.letter_sheets()
        return {"counts": counts, "sheets": sheets}

    @staticmethod
    def _review_guide() -> str:
        return """# Blinded visual review

Open the image-and-score interface by running this from the Zet project folder:

```powershell
.\\.venv\\Scripts\\python.exe -m zet.scripts.scene_assembly_comparison review <run-id>
```

The browser page displays each candidate, saves ratings and reasons directly into this run, and links to the
blinded three-image comparison sheet for the same seed. Keep the review server terminal open while using it.
The page shows native renders first; lettered renders become available after the dialogue-repair stage.

Score every token independently within its scene and seed, before opening `unblinding-key.json`.
Use `pass`, `fail`, or `unassessable`, and give a short reason for each rating. Score native and
lettered variants separately. A pass requires the criterion to be clearly satisfied in the image.

| Criterion | Review question |
|---|---|
| `cast_and_identity` | Are the required four/five people visible and recognizable in the accepted identities and costumes? |
| `pose_and_expression` | Are the accepted poses, expressions, and internal group arrangement preserved? |
| `props_and_source_retention` | Are source props retained? In Chapter 03, five books pass source retention even though five violates the authored requirement. |
| `facing_and_gaze` | Do facing and gaze relationships match the intended interaction? |
| `scale_depth_and_grounding` | Are relative sizes, foreground/background order, cropping, contact, and overlaps readable? |
| `background_continuity` | Is the arch/background coherent, with inscriptions retained and no distracting holes or duplicated structures? |
| `native_dialogue` / `lettered_dialogue` | Is the exact dialogue present once, legible, attached to the correct speaker, and safely placed? |
| `integration_quality` | Are seams, halos, contact shadows, lighting, and pasted appearance acceptable? |
| `narrative_readability` | Does the scene read as intended, including departure motion or Chapter 03's aftermath? |
| `authored_requirements` | Does it satisfy authored requirements separately from inherited source defects? Chapter 03 calls for four books and readable walking. |

User shorthand for recurring failure notes: **A**, duplicate/overlaid Kaeldor-and-schoolboys group; **B**, missing boots on Tsaeytte or Valindia; **C**, merged Valindia and Tsaeytte; **D**, reversed depth order (boys foreground, pair midground); **E** (Chapter 01), duplicate/floating boys group plus missing/transparent Tsaeytte hair and marks around her shoes.

For the lettering stage, use `reuse` when the native balloon is correct, `replace` when a usable
balloon needs new lettering, `add` when a balloon is missing, and `unsafe` when a repair would overlap
or repaint a character. `balloon_box` and `speaker_anchor` use normalized canvas coordinates.
"""

    def report(self) -> dict[str, Any]:
        manifest = self._manifest()
        evaluation_path = self.root / "evaluation.json"
        evaluation = _json(evaluation_path) if evaluation_path.exists() else {"items": {}}
        key_path = self.root / "unblinding-key.json"
        blind_map = _json(key_path) if key_path.is_file() else {}
        report: dict[str, Any] = {"run_id": self.run_id, "generated_at": datetime.now(timezone.utc).isoformat(),
                                  "scenes": {}, "recommendation": "Awaiting blinded native-render review and dialogue-lettering instructions."}
        for slug, scene in manifest["scenes"].items():
            variant_criteria = {"native": self._criteria(slug),
                                "lettered": [name for name in self._criteria(slug) if name != "native_dialogue"] + ["lettered_dialogue"]}
            outcomes = {variant: {arm: {criterion: {"pass": 0, "fail": 0, "unassessable": 0, "unreviewed": 0}
                                         for criterion in variant_criteria[variant]} for arm in ARMS}
                        for variant in ("native", "lettered")}
            elapsed = {arm: [] for arm in ARMS}
            for arm in ARMS:
                for seed in SEEDS:
                    result_path = self._scene_dir(slug) / "renders" / arm / str(seed) / "result.json"
                    if not result_path.is_file():
                        continue
                    result = _json(result_path)
                    if result.get("status") == "COMPLETE":
                        elapsed[arm].append(result.get("elapsed_seconds", 0))
                    token = next((token for token, mapped_arm in blind_map.get(f"{slug}/{seed}", {}).items()
                                  if mapped_arm == arm), None)
                    item = evaluation.get("items", {}).get(token, {}) if token else {}
                    for variant, field in (("native", "criteria"), ("lettered", "lettered_criteria")):
                        for criterion, review in item.get(field, {}).items():
                            value = review.get("result", "unreviewed")
                            if criterion in outcomes[variant][arm]:
                                outcomes[variant][arm][criterion][value if value in outcomes[variant][arm][criterion] else "unreviewed"] += 1
            essential = ["cast_and_identity", "pose_and_expression", "props_and_source_retention",
                         "facing_and_gaze", "scale_depth_and_grounding", "background_continuity",
                         "integration_quality", "narrative_readability", "authored_requirements"]
            success = {}
            for arm in ARMS:
                native_pass = finished_pass = lettered_pass = 0
                reviewed_native = reviewed_lettered = 0
                for seed in SEEDS:
                    token = next((token for token, mapped_arm in blind_map.get(f"{slug}/{seed}", {}).items()
                                  if mapped_arm == arm), None)
                    item = evaluation.get("items", {}).get(token, {}) if token else {}
                    native = item.get("criteria", {})
                    lettered = item.get("lettered_criteria", {})
                    if native and all(native.get(name, {}).get("result") in {"pass", "fail", "unassessable"} for name in essential):
                        reviewed_native += 1
                        native_pass += native.get("native_dialogue", {}).get("result") == "pass"
                        finished_pass += all(native.get(name, {}).get("result") == "pass" for name in essential)
                    if lettered and all(lettered.get(name, {}).get("result") in {"pass", "fail", "unassessable"}
                                        for name in [*essential, "lettered_dialogue"]):
                        reviewed_lettered += 1
                        lettered_pass += all(lettered.get(name, {}).get("result") == "pass"
                                             for name in [*essential, "lettered_dialogue"])
                success[arm] = {"native_dialogue_success": f"{native_pass}/{reviewed_native}",
                                "native_finished_scene_success": f"{finished_pass}/{reviewed_native}",
                                "lettered_finished_scene_success": f"{lettered_pass}/{reviewed_lettered}"}
            disagreements = {}
            for left, right in (("A_original", "B_corrected"), ("B_corrected", "C_layers"), ("A_original", "C_layers")):
                pair_counts = {}
                for criterion in self._criteria(slug):
                    n = 0
                    for seed in SEEDS:
                        left_token = next((token for token, arm in blind_map.get(f"{slug}/{seed}", {}).items() if arm == left), None)
                        right_token = next((token for token, arm in blind_map.get(f"{slug}/{seed}", {}).items() if arm == right), None)
                        left_item = evaluation.get("items", {}).get(left_token, {}).get("criteria", {}).get(criterion, {}).get("result")
                        right_item = evaluation.get("items", {}).get(right_token, {}).get("criteria", {}).get(criterion, {}).get("result")
                        n += left_item in {"pass", "fail"} and right_item in {"pass", "fail"} and left_item != right_item
                    pair_counts[criterion] = n
                disagreements[f"{left} vs {right}"] = pair_counts
            report["scenes"][slug] = {"arm_counts": scene["arm_status"], "native_ratings": outcomes["native"],
                                      "lettered_ratings": outcomes["lettered"], "paired_disagreements": disagreements,
                                      "success_counts": success,
                                      "mean_render_seconds": {arm: round(sum(v)/len(v), 2) if v else None
                                                               for arm, v in elapsed.items()}}
        primary_slug = "Chapter-03-Collision"
        if primary_slug in report["scenes"]:
            primary = report["scenes"][primary_slug]["native_ratings"]
            metrics = {arm: {criterion: values["pass"] for criterion, values in by_criterion.items()}
                       for arm, by_criterion in primary.items()}
            reviewed = all(primary[arm][criterion]["unreviewed"] == 0
                           for arm in ARMS for criterion in self._criteria(primary_slug))
            if reviewed:
                b_prompt_delta = sum(metrics["B_corrected"][criterion] - metrics["A_original"][criterion]
                                     for criterion in ("cast_and_identity", "pose_and_expression", "scale_depth_and_grounding",
                                                       "native_dialogue", "authored_requirements"))
                pose_delta = metrics["C_layers"]["pose_and_expression"] - metrics["B_corrected"]["pose_and_expression"]
                scale_delta = metrics["C_layers"]["scale_depth_and_grounding"] - metrics["B_corrected"]["scale_depth_and_grounding"]
                integration = metrics["C_layers"]["integration_quality"]
                if pose_delta >= 2 and integration >= 4:
                    report["recommendation"] = (
                        f"Chapter 03 favors a bounded explicit-layer follow-up: C passed pose preservation "
                        f"{metrics['C_layers']['pose_and_expression']}/8 versus B {metrics['B_corrected']['pose_and_expression']}/8, "
                        f"and integration quality passed {integration}/8. Scale pass counts were C "
                        f"{metrics['C_layers']['scale_depth_and_grounding']}/8 versus B "
                        f"{metrics['B_corrected']['scale_depth_and_grounding']}/8. This remains exploratory evidence."
                    )
                elif b_prompt_delta >= 2:
                    report["recommendation"] = (
                        f"Corrected deterministic prompts show a useful Chapter 03 signal: their net criterion-pass-count "
                        f"change versus the original prompt across identity, pose, scale, native dialogue, and authored "
                        f"requirements is +{b_prompt_delta}. Keep testing prompt/compiler corrections before considering a migration."
                    )
                elif all(metrics[arm]["pose_and_expression"] <= 2 for arm in ARMS):
                    report["recommendation"] = (
                        "All three arms struggled to preserve Chapter 03 pose and expression. Revisit the shared accepted "
                        "sources, extraction, and frozen layout before attributing the result to prompt wording or Qwen."
                    )
                else:
                    report["recommendation"] = (
                        "Chapter 03 results are mixed across pose, scale, dialogue, and integration. Use the criterion-level "
                        "paired disagreements and Chapters 01–02 controls to define one further bounded experiment; do not roll out automatically."
                    )
            else:
                report["recommendation"] = "Awaiting complete human review of the blinded native renders."
            if reviewed:
                lettered_ratings = report["scenes"][primary_slug]["lettered_ratings"]
                lettered_reviewed = all(
                    lettered_ratings[arm][criterion]["unreviewed"] == 0
                    for arm in ARMS for criterion in lettered_ratings[arm]
                )
                if not lettered_reviewed:
                    report["recommendation"] += " Deterministic-lettering results remain unscored."
        _write_json(self.root / "report.json", report)
        (self.root / "report.md").write_text(self._render_report(report), encoding="utf-8")
        return report

    def letter_variants(self) -> dict[str, int]:
        """Apply human-directed, deterministic dialogue repairs without repainting figures."""
        manifest = self._manifest()
        evaluation_path = self.root / "evaluation.json"
        if not evaluation_path.is_file():
            raise ValueError("Generate blinded sheets and complete native dialogue review first")
        evaluation = _json(evaluation_path)
        blind_map = _json(self.root / "unblinding-key.json")
        counts = {"reused": 0, "lettered": 0, "unsafe": 0, "pending": 0}
        for slug, scene in manifest["scenes"].items():
            width, height = scene["output_size"]
            dialogue = scene["dialogue"][0]
            for arm in ARMS:
                for seed in SEEDS:
                    token = next((token for token, mapped_arm in blind_map.get(f"{slug}/{seed}", {}).items()
                                  if mapped_arm == arm), None)
                    item = evaluation.get("items", {}).get(token) if token else None
                    key = f"{slug}/{seed}/{arm}"
                    if not item:
                        continue
                    review = item.get("lettering_review", {})
                    action = review.get("action", "pending")
                    native = self._scene_dir(slug) / "renders" / arm / str(seed) / "candidate.png"
                    if not native.is_file():
                        continue
                    out_dir = self._scene_dir(slug) / "renders" / arm / str(seed) / "lettered"
                    out_dir.mkdir(parents=True, exist_ok=True)
                    output = out_dir / "candidate.png"
                    if action in {"reuse", "unsafe"}:
                        shutil.copy2(native, output)
                        counts["reused" if action == "reuse" else "unsafe"] += 1
                        continue
                    if action not in {"add", "replace"}:
                        counts["pending"] += 1
                        continue
                    box = review.get("balloon_box")
                    anchor = review.get("speaker_anchor")
                    if not (isinstance(box, list) and len(box) == 4 and isinstance(anchor, list) and len(anchor) == 2):
                        counts["pending"] += 1
                        continue
                    x, y, bw, bh = (int(round(float(box[i]) * (width if i % 2 == 0 else height))) for i in range(4))
                    ax, ay = int(round(float(anchor[0]) * width)), int(round(float(anchor[1]) * height))
                    if x < 0 or y < 0 or bw < 24 or bh < 24 or x+bw > width or y+bh > height or not (0 <= ax < width and 0 <= ay < height):
                        raise ValueError(f"{key}: lettering geometry lies outside its canvas")
                    canvas = _load_image(native)
                    draw = ImageDraw.Draw(canvas)
                    font_size = max(14, min(42, int(bh * 0.42)))
                    font_path = Path(r"C:\Windows\Fonts\arial.ttf")
                    text = str(dialogue["text"])
                    words = text.split()
                    line_limit = int(dialogue["lines"])
                    lines: list[str] = []
                    while font_size >= 12:
                        font = ImageFont.truetype(str(font_path), font_size) if font_path.is_file() else ImageFont.load_default(size=font_size)
                        lines, current = [], ""
                        for word in words:
                            trial = f"{current} {word}".strip()
                            if current and draw.textbbox((0, 0), trial, font=font)[2] > bw * 0.82:
                                lines.append(current)
                                current = word
                            else:
                                current = trial
                        if current:
                            lines.append(current)
                        if len(lines) <= line_limit:
                            break
                        font_size -= 2
                    if len(lines) > line_limit:
                        raise ValueError(f"{key}: exact dialogue does not fit the configured line limit")
                    tail = (min(max(ax, x + 14), x + bw - 14), y + bh) if ay >= y + bh else (min(max(ax, x + 14), x + bw - 14), y)
                    tip = (ax, ay)
                    draw.polygon([tail, (tail[0]-12, tail[1]), tip, (tail[0]+12, tail[1])], fill="white", outline="#211f20")
                    draw.rounded_rectangle((x, y, x+bw, y+bh), radius=min(18, bh//5), fill="white", outline="#211f20", width=max(2, width//500))
                    line_heights = [draw.textbbox((0, 0), line, font=font)[3] for line in lines]
                    total_h = sum(line_heights) + max(0, len(lines)-1) * 3
                    cy = y + (bh-total_h)//2
                    for line, line_h in zip(lines, line_heights):
                        bb = draw.textbbox((0, 0), line, font=font)
                        tx = x + (bw-(bb[2]-bb[0]))//2
                        draw.text((tx, cy), line, font=font, fill="#171515")
                        cy += line_h + 3
                    canvas.save(output)
                    _write_json(out_dir / "lettering.json", {"action": action, "text": text,
                                                                "speaker": dialogue["speaker"],
                                                                "box": box, "speaker_anchor": anchor,
                                                                "policy": "Pillow raster balloon; applied only to the reviewed safe box"})
                    counts["lettered"] += 1
        return counts

    @staticmethod
    def _render_report(report: dict[str, Any]) -> str:
        lines = [f"# Scene assembly comparison {report['run_id']}", "",
                 f"**Recommendation:** {report['recommendation']}", "",
                 "Native scenes were scored blind. Lettered variants inherit native ratings for all non-dialogue criteria; only the new or retained balloon is scored again.", ""]
        for slug, scene in report["scenes"].items():
            lines.extend([f"## {slug}", "", "| Arm | Rendered | Mean seconds | Native dialogue pass | Native finished scenes | Lettered finished scenes |",
                          "|---|---:|---:|---:|---:|---:|"])
            for arm in ARMS:
                complete = sum(value == "COMPLETE" for value in scene["arm_counts"][arm].values())
                metrics = scene["success_counts"][arm]
                lines.append(f"| {arm} | {complete}/8 | {scene['mean_render_seconds'][arm]} | {metrics['native_dialogue_success']} | "
                             f"{metrics['native_finished_scene_success']} | {metrics['lettered_finished_scene_success']} |")
            lines.extend(["", "### Native criterion ratings", "",
                          "Counts are shown as pass / fail / unassessable / unreviewed.", "",
                          "| Criterion | Original prompt | Corrected prompt | Layer composition |",
                          "|---|---:|---:|---:|"])
            for criterion in scene["native_ratings"][ARMS[0]]:
                cells = []
                for arm in ARMS:
                    counts = scene["native_ratings"][arm][criterion]
                    cells.append(" / ".join(str(counts[name]) for name in ("pass", "fail", "unassessable", "unreviewed")))
                lines.append(f"| {criterion} | " + " | ".join(cells) + " |")
            lines.extend(["", "### Lettered balloon review", "",
                          "Only the balloon and lettering were rescored; all other visual ratings carry forward from the native render. Counts are pass / fail / unassessable / unreviewed.", "",
                          "| Criterion | Original prompt | Corrected prompt | Layer composition |",
                          "|---|---:|---:|---:|"])
            cells = []
            for arm in ARMS:
                counts = scene["lettered_ratings"][arm]["lettered_dialogue"]
                cells.append(" / ".join(str(counts[name]) for name in ("pass", "fail", "unassessable", "unreviewed")))
            lines.append("| Balloon and lettering | " + " | ".join(cells) + " |")
            lines.extend(["", "### Paired disagreements", "",
                          "For each seed, this counts criteria where both arms were rated pass/fail and disagreed.", "",
                          "| Comparison | " + " | ".join(scene["paired_disagreements"][next(iter(scene["paired_disagreements"]))]) + " |",
                          "|---|" + "---:|" * len(scene["paired_disagreements"][next(iter(scene["paired_disagreements"]))])])
            for comparison, criteria in scene["paired_disagreements"].items():
                lines.append(f"| {comparison} | " + " | ".join(str(value) for value in criteria.values()) + " |")
            lines.append("")
        return "\n".join(lines)

    def review_help(self) -> str:
        return ("After sheets, fill review-scorecard.csv: set each result to pass, fail, or unassessable and enter a concise reason. "
                "Keep candidate tokens blinded while scoring. Then run import-review to update evaluation.json. "
                "Keep unblinding-key.json closed until you finish scoring all three tokens for a seed. "
                "In the native_dialogue row, set lettering_action to reuse, replace, add, or unsafe. For replace/add, "
                "provide balloon_box and speaker_anchor as normalized [x,y,width,height] and [x,y] canvas coordinates. "
                "After import-review, run letter and letter-sheets; lettered rows inherit native non-dialogue ratings, so score only lettered_dialogue, "
                "then import again before report.")

    def export_review_csv(self) -> Path:
        evaluation_path = self.root / "evaluation.json"
        if not evaluation_path.is_file():
            raise ValueError("Generate blinded sheets before exporting a scorecard")
        evaluation = _json(evaluation_path)
        output = self.root / "review-scorecard.csv"
        native_criteria = self._criteria("Chapter-01-Standing-in-Wonder")
        lettered_criteria = [name for name in native_criteria if name != "native_dialogue"] + ["lettered_dialogue"]
        fields = ["token", "scene", "seed"]
        for variant, criteria in (("native", native_criteria), ("lettered", lettered_criteria)):
            for criterion in criteria:
                fields.extend((f"{variant}_{criterion}", f"{variant}_reason_{criterion}"))
        fields.extend(("lettering_action", "balloon_box", "speaker_anchor", "lettering_reason"))
        with output.open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for token, item in sorted(evaluation.get("items", {}).items()):
                row: dict[str, Any] = {"token": token, "scene": item.get("scene"), "seed": item.get("seed")}
                for variant, field in (("native", "criteria"), ("lettered", "lettered_criteria")):
                    for criterion, review in item.get(field, {}).items():
                        row[f"{variant}_{criterion}"] = review.get("result", "unreviewed")
                        row[f"{variant}_reason_{criterion}"] = review.get("reason", "")
                lettering = item.get("lettering_review", {})
                row.update({"lettering_action": lettering.get("action", "pending"),
                            "balloon_box": json.dumps(lettering.get("balloon_box")) if lettering.get("balloon_box") else "",
                            "speaker_anchor": json.dumps(lettering.get("speaker_anchor")) if lettering.get("speaker_anchor") else "",
                            "lettering_reason": lettering.get("reason", "")})
                writer.writerow(row)
        return output

    def import_review_csv(self) -> int:
        scorecard = self.root / "review-scorecard.csv"
        evaluation_path = self.root / "evaluation.json"
        if not scorecard.is_file() or not evaluation_path.is_file():
            raise ValueError("Export review-scorecard.csv and evaluation.json before importing scores")
        evaluation = _json(evaluation_path)
        updated = 0
        with scorecard.open("r", newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            if "variant" in (reader.fieldnames or []):
                raise ValueError("This scorecard uses the obsolete long format; export a fresh scorecard before rating")
            for row in reader:
                token = row.get("token", "")
                item = evaluation.get("items", {}).get(token)
                if item is None or row.get("scene") != item.get("scene") or str(row.get("seed")) != str(item.get("seed")):
                    raise ValueError(f"Review row does not match blinded token {token}")
                for variant, field in (("native", "criteria"), ("lettered", "lettered_criteria")):
                    for criterion, review in item[field].items():
                        result = row.get(f"{variant}_{criterion}", "unreviewed").strip() or "unreviewed"
                        if result not in {"pass", "fail", "unassessable", "unreviewed"}:
                            raise ValueError(f"Invalid review value for {token}/{variant}/{criterion}: {result}")
                        review["result"] = result
                        review["reason"] = row.get(f"{variant}_reason_{criterion}", "")
                        updated += 1
                lettering = item.setdefault("lettering_review", {})
                action = row.get("lettering_action", "pending").strip() or "pending"
                if action not in {"reuse", "replace", "add", "unsafe", "pending"}:
                    raise ValueError(f"Invalid lettering action for token {token}: {action}")
                lettering["action"] = action
                for source_key in ("balloon_box", "speaker_anchor"):
                    raw = row.get(source_key, "").strip()
                    if raw:
                        lettering[source_key] = json.loads(raw)
                    else:
                        lettering[source_key] = None
                lettering["reason"] = row.get("lettering_reason", "")
        _write_json(evaluation_path, evaluation)
        return updated

