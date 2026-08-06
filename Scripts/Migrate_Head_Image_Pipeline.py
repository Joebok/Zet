#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import shutil
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Scripts.Library_Paths import asset_root, character_root, resolve_library_path


VIEWS = ["Front", "Front-Left-3-4", "Front-Right-3-4", "Left-Profile", "Right-Profile", "Back-Left-3-4", "Back-Right-3-4", "Back"]
PHASES = ["Adult", "Youth", "Elder"]

PIPELINE = {
    "stages": ["MANIFEST", "PROMPT", "RENDER", "RENDER_REVIEW"],
    "actor_by_stage": {"MANIFEST": "PYTHON", "PROMPT": "PYTHON", "RENDER": "AI_AGENT", "RENDER_REVIEW": "HUMAN_AGENT"},
    "worker_by_stage": {
        "MANIFEST": "zet.workers.head_image_manifest_worker",
        "PROMPT": "zet.workers.head_image_prompt_worker",
        "RENDER": "zet.workers.noop_worker",
        "RENDER_REVIEW": "zet.workers.noop_worker",
    },
}

RENDERING_RULES = """## Head-Image Rendering Rules

<!-- ZET:BEGIN HEAD_IMAGE_RENDERING_RULES -->

Rendering priorities:

* Render one clear image of the character's head in the requested view.
* Use the Canonical Art Style.
* Head-only, head-and-shoulders, bust, or a small amount of upper torso are all acceptable when they support a natural result.
* Use a simple, unobtrusive background and clear readable lighting.
* Do not impose head-fitment neck geometry, a fixed neck cut, transparency, or shoulder-removal requirements.
* Do not add a narrative scene, prominent props, or unrelated characters.

<!-- ZET:END HEAD_IMAGE_RENDERING_RULES -->"""

GENERIC_REFERENCE_RULES = """## Head-Image Reference Rules

<!-- ZET:BEGIN HEAD_IMAGE_REFERENCE_RULES -->

Optional source-image contract:

* When a source image is supplied, use it as the visual authority for recognizable facial identity, facial proportions, feature relationships, and other identity-defining traits.
* Preserve source identity while rotating the head into the requested target view.
* The target-phase Character.md controls explicitly described phase traits, hair, species features, and intentional changes; it overrides the source only for those changes.
* Preserve every identity-defining source trait that this target phase does not explicitly change.
* Without a source image, construct the character from the factual, identity-preservation, and requested-view sections in this Character.md.
* The requested target view always overrides the source image's camera angle or head orientation.

<!-- ZET:END HEAD_IMAGE_REFERENCE_RULES -->"""

ELDER_REFERENCE_RULES = """## Head-Image Reference Rules

<!-- ZET:BEGIN HEAD_IMAGE_REFERENCE_RULES -->

Optional source-image contract:

* Use the matching Adult Tsaeytte Head-Image as the visual authority for the same person's recognizable facial identity, feature relationships, and elven anatomy.
* Render an older version of that same person, applying the Elder phase descriptions rather than creating a different elderly elf.
* Preserve her heart-shaped facial identity, violet almond eyes, delicate nose and mouth relationships, pointed ears, and characteristic asymmetry unless the Elder template explicitly describes an age-related change.
* Apply restrained elven aging: paler luminous coloring, refined and slightly lengthened facial structure, higher-looking cheekbones, modest sub-cheek hollowing, faint lines, and a more ethereal presence without deep human wrinkles, sagging, sickness, or frailty.
* Replace Adult hair traits with the Elder phase's luminous silver, shoulder-length asymmetrical long bob exactly as described by the target head, hair, and requested-view sections.
* Preserve every identity-defining Adult source trait that the Elder template does not explicitly change.
* Without a source image, construct Elder Tsaeytte from this Character.md with the same identity and aging priorities.
* The requested target view always overrides the source image's camera angle or head orientation.

<!-- ZET:END HEAD_IMAGE_REFERENCE_RULES -->"""


def _backup(path: Path) -> None:
    backup_dir = path.parent / "_backup"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    shutil.copy2(path, backup_dir / f"{path.stem}.backup.{stamp}{path.suffix}")


def _write_json(path: Path, payload: dict) -> None:
    temp = path.with_name(f"{path.name}.head-image.tmp")
    temp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    json.loads(temp.read_text(encoding="utf-8"))
    temp.replace(path)


def _update_character(path: Path, phase: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if "ZET:BEGIN HEAD_IMAGE_REFERENCE_RULES" in text and "ZET:BEGIN HEAD_IMAGE_RENDERING_RULES" in text:
        return False
    marker = "## Body Reference Rendering Rules"
    if marker not in text:
        raise ValueError(f"Body Reference Rendering Rules marker not found: {path}")
    rules = ELDER_REFERENCE_RULES if phase == "Elder" else GENERIC_REFERENCE_RULES
    replacement = f"{rules}\n\n{RENDERING_RULES}\n\n{marker}"
    _backup(path)
    path.write_text(text.replace(marker, replacement, 1), encoding="utf-8")
    return True


def _update_pipelines(path: Path) -> bool:
    payload = json.loads(path.read_text(encoding="utf-8"))
    pipelines = payload["pipelines"]
    if "Head-Image" in pipelines:
        return False
    ordered = {}
    for name, value in pipelines.items():
        ordered[name] = value
        if name == "Body-Reference":
            ordered["Head-Image"] = PIPELINE
    payload["pipelines"] = ordered
    _backup(path)
    _write_json(path, payload)
    return True


def _reference_path(record: dict, role: str) -> str:
    return next((str(item.get("path") or "") for item in record.get("reference_files", []) if isinstance(item, dict) and item.get("role") == role), "")


def _migrate_phase(character: str, phase: str, adult_head_images: dict[str, tuple[int, Path]] | None = None) -> dict[str, tuple[int, Path]]:
    phase_root = character_root(PROJECT_ROOT) / character / phase
    assets_path = phase_root / "Assets.json"
    output_root = asset_root(PROJECT_ROOT) / character / phase
    output_root.mkdir(parents=True, exist_ok=True)
    payload = json.loads(assets_path.read_text(encoding="utf-8"))
    records = payload["assets"]
    next_id = int(payload.get("next_asset_id") or 1)
    by_view = {str(item.get("body_view") or ""): item for item in records if item.get("pipeline") == "Head-Image"}
    fitments = {str(item.get("body_view") or ""): item for item in records if item.get("pipeline") == "Head-Fitment"}
    changed = False
    result: dict[str, tuple[int, Path]] = {}

    for view in VIEWS:
        record = by_view.get(view)
        if record is None:
            record = {
                "asset_id": next_id,
                "character": character,
                "phase": phase,
                "pipeline": "Head-Image",
                "body_view": view,
                "head_view": view,
                "asset_state": "NEW",
                "pipeline_stage": "MANIFEST",
                "actor": "PYTHON",
                "final_image_output": f"Head-Image_{view}.png",
                "reference_files": [],
                "assembly_style_mode": "MATCHED_STYLE",
            }
            records.append(record)
            by_view[view] = record
            next_id += 1
            changed = True
        canonical = output_root / str(record.get("final_image_output") or f"Head-Image_{view}.png")
        if phase in {"Adult", "Youth"}:
            fitment = fitments.get(view, {})
            legacy_raw = _reference_path(fitment, "headshot") or _reference_path(fitment, "head_image")
            legacy = resolve_library_path(PROJECT_ROOT, legacy_raw) if legacy_raw else Path()
            if not canonical.exists():
                if not legacy.is_file():
                    raise ValueError(f"Legacy headshot missing for {character}/{phase}/{view}: {legacy_raw}")
                shutil.copy2(legacy, canonical)
            if record.get("asset_state") != "LOCKED" or record.get("pipeline_stage") != "LOCKED":
                record.update({"asset_state": "LOCKED", "pipeline_stage": "LOCKED", "actor": "HUMAN_AGENT", "error_code": None, "error_message": None})
                changed = True
            result[view] = (int(record["asset_id"]), canonical)
            if fitment:
                body_refs = [item for item in fitment.get("reference_files", []) if isinstance(item, dict) and item.get("role") == "body_reference"]
                desired = [*body_refs, {"role": "head_image", "label": "Locked Head-Image", "path": str(canonical), "source_asset_id": record["asset_id"], "source_phase": phase, "head_view": view}]
                if fitment.get("reference_files") != desired:
                    fitment["reference_files"] = desired
                    changed = True
        elif adult_head_images and record.get("pipeline_stage") == "MANIFEST" and not record.get("reference_files"):
            source_id, source_path = adult_head_images[view]
            record["reference_files"] = [{
                "role": "head_image_source",
                "label": "Adult Head-Image source",
                "path": str(source_path),
                "source_asset_id": source_id,
                "source_character": character,
                "source_phase": "Adult",
                "head_view": view,
            }]
            changed = True
        if canonical.is_file() and record.get("asset_state") == "LOCKED":
            result[view] = (int(record["asset_id"]), canonical)

    if changed:
        _backup(assets_path)
        payload["next_asset_id"] = next_id
        _write_json(assets_path, payload)
    return result


def migrate(character: str = "Tsaeytte") -> None:
    for phase in PHASES:
        phase_root = character_root(PROJECT_ROOT) / character / phase
        _update_character(phase_root / "Character.md", phase)
        _update_pipelines(phase_root / "Pipelines.json")
    adult = _migrate_phase(character, "Adult")
    _migrate_phase(character, "Youth")
    _migrate_phase(character, "Elder", adult)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Migrate Tsaeytte phases to the Head-Image pipeline.")
    parser.add_argument("--character", default="Tsaeytte")
    args = parser.parse_args(argv)
    migrate(args.character)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
