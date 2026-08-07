#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import shutil
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if __package__ in {None, ""} and str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from zet.services.ai_proxy_path_service import AIProxyPathService
from zet.services.config_service import ConfigService
from zet.services.path_service import PathService


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _move(source: Path, destination: Path) -> bool:
    if not source.exists():
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        return False
    shutil.move(str(source), str(destination))
    return True


def _retire_character_markdown(path: Path) -> bool:
    if not path.is_file():
        return False
    original = path.read_text(encoding="utf-8")
    text = original
    for marker in ("HEAD_FITMENT_RENDERING_RULES", "COMPILER_BUNDLE_HEAD_FITMENT"):
        pattern = re.compile(
            rf"(?ms)^##[^\n]*\n\n(?=<!-- ZET:BEGIN {marker} -->).*?<!-- ZET:END {marker} -->\s*"
            if marker == "HEAD_FITMENT_RENDERING_RULES"
            else rf"(?ms)^<!-- ZET:BEGIN {marker} -->.*?<!-- ZET:END {marker} -->\s*"
        )
        text = pattern.sub("", text)
    text = text.replace(
        "* Head-only, head-and-shoulders, bust, or a small amount of upper torso are all acceptable when they support a natural result.",
        "* Use natural head-and-shoulders or limited-bust framing with the complete head, hair silhouette, jaw, chin, neck, and enough upper-shoulder context for assembly.",
    )
    text = re.sub(
        r"(?m)^\* Use a simple, unobtrusive background and clear readable lighting\.$",
        "* Render on a transparent background with clear readable lighting; do not add a backdrop or environment.",
        text,
    )
    text = re.sub(
        r"(?m)^\* Do not impose head-fitment neck geometry, a fixed neck cut, transparency, or shoulder-removal requirements\.$",
        "* The visible shoulders, upper torso, and clothing are contextual only and do not define the final assembled body.",
        text,
    )
    text = "\n".join(
        line for line in text.splitlines()
        if "head-fitment" not in line.casefold() and "head fitment" not in line.casefold() and "HEAD_FITMENT" not in line
    ).rstrip() + "\n"
    if text == original:
        return False
    path.write_text(text, encoding="utf-8")
    return True


def _archive_proxy_jobs(paths: PathService, stamp: str) -> list[str]:
    proxy_paths = AIProxyPathService(paths.config)
    moved: list[str] = []
    destination_root = proxy_paths.archive_root() / "Retired_Head_Fitment" / stamp
    for state in ("ask", "running", "answer"):
        for job_path in proxy_paths.task_paths(state):
            manifest_path = job_path / "ask_manifest.json"
            if not manifest_path.is_file():
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if manifest.get("pipeline") != "Head-Fitment" and manifest.get("task_type") not in {
                "head_fitment_inpaint",
                "head_fitment_mask_generate",
            }:
                continue
            if state == "answer" and (job_path / "harvest_manifest.json").exists():
                continue
            destination = destination_root / state / job_path.name
            if _move(job_path, destination):
                moved.append(str(destination))
    return moved


def retire_phase(paths: PathService, character: str, phase: str, stamp: str) -> dict:
    phase_path = paths.character_path(character, phase)
    assets_path = phase_path / "Assets.json"
    pipelines_path = phase_path / "Pipelines.json"
    if not assets_path.is_file() or not pipelines_path.is_file():
        return {"character": character, "phase": phase, "changed": False, "reason": "missing foundation files"}

    assets_payload = json.loads(assets_path.read_text(encoding="utf-8"))
    pipelines_payload = json.loads(pipelines_path.read_text(encoding="utf-8"))
    records = list(assets_payload.get("assets") or [])
    retired = [record for record in records if record.get("pipeline") == "Head-Fitment"]
    retired_ids = {int(record["asset_id"]) for record in retired}
    reserved_ids = {int(asset_id) for asset_id in assets_payload.get("reserved_asset_ids", [])}
    pipeline_present = "Head-Fitment" in (pipelines_payload.get("pipelines") or {})
    changed = bool(retired or pipeline_present or not retired_ids.issubset(reserved_ids) or assets_payload.get("schema_version") != 2)
    if not changed:
        return {"character": character, "phase": phase, "changed": False, "reserved_asset_ids": sorted(reserved_ids)}

    backup_root = phase_path / "_backup" / "HeadFitmentRetirement" / stamp
    backup_root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(assets_path, backup_root / "Assets.json")
    shutil.copy2(pipelines_path, backup_root / "Pipelines.json")
    character_path = phase_path / "Character.md"
    if character_path.is_file():
        shutil.copy2(character_path, backup_root / "Character.md")

    archive_root = phase_path / "_archive" / "Head-Fitment"
    archive_root.mkdir(parents=True, exist_ok=True)
    retired_manifest_path = archive_root / "RetiredAssets.json"
    archived_payload = {"schema_version": 1, "retired_at": stamp, "pipeline": "Head-Fitment", "assets": retired}
    if retired_manifest_path.is_file():
        previous = json.loads(retired_manifest_path.read_text(encoding="utf-8"))
        by_id = {int(record["asset_id"]): record for record in previous.get("assets", [])}
        by_id.update({int(record["asset_id"]): record for record in retired})
        archived_payload["assets"] = [by_id[asset_id] for asset_id in sorted(by_id)]
    _write_json(retired_manifest_path, archived_payload)

    archived_paths: dict[int, str] = {}
    for record in retired:
        asset_id = int(record["asset_id"])
        output_name = str(record.get("final_image_output") or "").strip()
        if output_name:
            source = paths.character_asset_path(character, phase) / output_name
            destination = archive_root / "Assets" / output_name
            _move(source, destination)
            if destination.is_file():
                archived_paths[asset_id] = str(destination)

    _move(paths.pipeline_base_path(character, phase) / "Head-Fitment", archive_root / "Pipeline")

    active_records = [record for record in records if record.get("pipeline") != "Head-Fitment"]
    for record in active_records:
        if record.get("pipeline") != "Character-Assembly" or record.get("asset_state") != "LOCKED":
            continue
        for reference in record.get("reference_files") or []:
            source_id = reference.get("source_asset_id")
            if reference.get("role") != "head_fitment" or source_id not in retired_ids:
                continue
            reference["historical_only"] = True
            reference["archived"] = True
            if int(source_id) in archived_paths:
                reference["path"] = archived_paths[int(source_id)]

    assets_payload["schema_version"] = 2
    assets_payload["reserved_asset_ids"] = sorted(reserved_ids | retired_ids)
    assets_payload["assets"] = active_records
    pipelines_payload.setdefault("pipelines", {}).pop("Head-Fitment", None)
    _write_json(assets_path, assets_payload)
    _write_json(pipelines_path, pipelines_payload)
    _retire_character_markdown(character_path)
    return {
        "character": character,
        "phase": phase,
        "changed": True,
        "retired_asset_ids": sorted(retired_ids),
        "archive_root": str(archive_root),
        "backup_root": str(backup_root),
    }


def retire_library(config_path: str | Path, character: str = "") -> dict:
    config = ConfigService.load(config_path)
    paths = PathService(config, PROJECT_ROOT)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    character_root = Path(config.base_character_path)
    characters = [character_root / character] if character else sorted(path for path in character_root.iterdir() if path.is_dir())
    results = []
    for character_path in characters:
        if not character_path.is_dir():
            continue
        for phase_path in sorted(path for path in character_path.iterdir() if path.is_dir() and not path.name.startswith("_")):
            results.append(retire_phase(paths, character_path.name, phase_path.name, stamp))
    return {"stamp": stamp, "phases": results, "archived_proxy_jobs": _archive_proxy_jobs(paths, stamp)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Permanently retire active Head-Fitment assets and pipeline definitions.")
    parser.add_argument("--config", default=str(PROJECT_ROOT / "config.toml"))
    parser.add_argument("--character", default="")
    args = parser.parse_args()
    print(json.dumps(retire_library(args.config, args.character), indent=2))


if __name__ == "__main__":
    main()
