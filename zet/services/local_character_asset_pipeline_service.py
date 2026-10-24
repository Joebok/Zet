"""Local candidate workflows for Character-Assembly and Costume-Dressing."""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import random
import re
import shutil
import tempfile
import threading
import time
from typing import Any
from uuid import uuid4

from Scripts.Run_Character_Assembly_Jobs import compile_character_assembly_job
from Scripts.Run_Costume_Dressing_Jobs import compile_costume_dressing_job
from zet.services.local_candidate_review_contract import (
    adjust_candidate_ranking, normalize_human_decision,
)
from zet.services.local_image_ranking_service import rank_images_with_luna, supplied_ranking_references
from zet.services.local_character_progression_service import assembly_front, guard_view, invalidate_assembly_rankings
from zet.services.local_asset_store_service import LocalAssetStoreService
from zet.services.library_reference_service import read_library_json, write_library_json
from zet.services.local_image_pipeline_policy import (
    ACTIVE_RUN_STATUSES, decorate_local_pipeline_detail,
    local_image_pipeline_config,
    mutate_local_run_state, pipeline_page_config, resume_cancelled_autogenerate_state, serialize_local_run_state,
    view_candidate_id,
)
from zet.services.local_render_backend_service import LocalRenderBackendService
from zet.services.render_slot_service import merge_candidates, render_count, slot_maps, frozen_input, verify_input
from zet.services.workflow_storage import runner_lock_active, file_lock, supersede_task


VIEWS = ("FRONT", "FRONT_LEFT_3_4", "FRONT_RIGHT_3_4", "LEFT_PROFILE", "RIGHT_PROFILE",
         "BACK_LEFT_3_4", "BACK_RIGHT_3_4", "BACK")
VIEW_LABELS = {
    "FRONT": "direct front view", "FRONT_LEFT_3_4": "front-left three-quarter view",
    "FRONT_RIGHT_3_4": "front-right three-quarter view", "LEFT_PROFILE": "left profile",
    "RIGHT_PROFILE": "right profile", "BACK_LEFT_3_4": "back-left three-quarter view",
    "BACK_RIGHT_3_4": "back-right three-quarter view", "BACK": "direct back view",
}


class LocalCharacterAssetPipelineError(ValueError):
    pass


class LocalCharacterAssetPipelineService:
    """Run one local Assembly or costume-specific Dressing candidate pipeline."""

    _active: set[str] = set()
    _active_lock = threading.Lock()
    _runner_lock = threading.Lock()

    PIPELINES = {
        "character-assembly": {
            "key": "character-assembly", "label": "Local Character-Assembly", "workspace": "Character-Assembly",
            "asset_pipeline": "Character-Assembly", "task": "character-assembly", "qualifies": False,
            "preset": "comfyui-qwen-local-character-edit",
        },
        "costume-dressing": {
            "key": "costume-dressing", "label": "Local Costume-Dressing", "workspace": "Costume-Dressing",
            "asset_pipeline": "Costume-Dressing", "task": "costume-dressing", "qualifies": True,
            "preset": "comfyui-qwen-local-character-edit",
        },
    }


    def __init__(self, app: Any, project_root: str | Path, pipeline: str, *, runs_root: str | Path | None = None):
        if pipeline not in self.PIPELINES:
            raise LocalCharacterAssetPipelineError(f"Unsupported local pipeline: {pipeline}")
        self.app = app
        self.project_root = Path(project_root).resolve()
        self.definition = self.PIPELINES[pipeline]
        self.pipeline = pipeline
        self.library_root = Path(app.config.base_library_path).resolve()
        self.character_root = Path(app.config.base_character_path).resolve()
        self.root = Path(runs_root).resolve() if runs_root else self.library_root / "PipelineCandidates" / "Character-Pipeline"
        self.asset_store = LocalAssetStoreService(self.library_root)
        self._runner_lock = threading.Lock()

    @staticmethod
    def prompt_packet_constraints(run: dict[str, Any], view: str) -> list[str]:
        if view not in {"BACK_LEFT_3_4", "BACK_RIGHT_3_4", "BACK"}:
            return []
        return [
            "Replace only the generic fitment clothing, jewelry, equipment, and footwear controlled by the costume.",
            "Preserve identity, anatomy, body proportions, pose, body and head orientation, camera, and crop from Image 1.",
            "The costume conforms to the existing body; the body does not change to fit the costume.",
            "Do not leave generic fitment clothing visible.",
            "Do not add unlisted garments, jewelry, equipment, weapons, or props.",
        ]

    def _ask_belongs_to_run(self, ask: dict[str, Any], run: dict[str, Any]) -> bool:
        configured = str(getattr(self.app.config, "universe_id", "Moonsea"))
        owner = str(ask.get("universe_id") or "").strip()
        if not owner and bool(getattr(self.app.config, "universe_is_legacy", True)):
            owner = "Moonsea"
        run_owner = str(run.get("universe_id") or "").strip()
        if not run_owner and bool(getattr(self.app.config, "universe_is_legacy", True)):
            run_owner = "Moonsea"
        return bool(owner) and owner == configured and run_owner == owner

    def _active_key(self, run_id: str) -> str:
        return f"{self.library_root}::{self.pipeline}::{run_id}"

    def _is_active(self, run_id: str) -> bool:
        key = self._active_key(run_id)
        return key in self._active or (not hasattr(self.app.config, "universe_id") and run_id in self._active)

    @staticmethod
    def _now() -> str:
        return datetime.now().astimezone().isoformat(timespec="seconds")

    @staticmethod
    def _hash(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def _safe(value: str) -> str:
        token = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value or "").strip()).strip("_")
        if not token or token in {".", ".."}:
            raise LocalCharacterAssetPipelineError("Character, phase, and costume are required.")
        return token

    def _qualifier(self, costume: str = "") -> str:
        return self._safe(costume) if self.definition["qualifies"] else ""

    def _workspace(self, character: str, phase: str, costume: str = "") -> Path:
        root = self.root / self._safe(character) / self._safe(phase) / self.definition["workspace"]
        if self.definition["qualifies"]:
            root /= self._qualifier(costume)
        return root

    def _run_root(self, run_id: str, costume: str = "") -> Path:
        if not re.fullmatch(r"[0-9a-f]{32}", str(run_id or "")):
            raise LocalCharacterAssetPipelineError("Invalid local pipeline run ID.")
        # Glob only below this pipeline workspace. The requested costume narrows Dressing lookup.
        pattern = f"*/*/{self.definition['workspace']}/*/{run_id}" if self.definition["qualifies"] else f"*/*/{self.definition['workspace']}/{run_id}"
        requested_costume = self._qualifier(costume) if costume and self.definition["qualifies"] else costume
        for path in self.root.glob(pattern):
            if (path / "spec.json").is_file():
                spec = self._read(path / "spec.json")
                stored_costume = spec.get("costume")
                if stored_costume and self.definition["qualifies"]:
                    stored_costume = self._qualifier(stored_costume)
                if spec.get("kind") == self.pipeline and (not costume or stored_costume == requested_costume):
                    return path
        raise LocalCharacterAssetPipelineError(f"Local {self.definition['label']} run not found: {run_id}")

    def _read(self, path: Path) -> dict[str, Any]:
        try:
            value = read_library_json(path, self.library_root)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise LocalCharacterAssetPipelineError(f"Could not read local pipeline state: {path}") from exc
        if not isinstance(value, dict):
            raise LocalCharacterAssetPipelineError(f"Invalid local pipeline state: {path}")
        return value

    def _write(self, path: Path, value: dict[str, Any]) -> None:
        write_library_json(path, value, self.library_root)

    def _costume_path(self, character: str, phase: str, costume: str) -> Path:
        name = re.sub(r"[^A-Za-z0-9_-]+", "-", costume).strip("-") or "Costume"
        return self.character_root / character / phase / f"Costume_{name.replace('-', '_')}.md"

    def _locked(self, character: str, phase: str, pipeline: str, view: str, qualifier: str = "") -> dict[str, Any]:
        key = self.asset_store.key(pipeline, view, qualifier)
        records = self.asset_store.locked_assets(character, phase, pipeline=pipeline, qualifier=qualifier)
        record = next((item for item in records if item["key"] == key), None)
        if record is None:
            raise LocalCharacterAssetPipelineError(f"A locked {pipeline} file is required for {view}.")
        return record

    def _requirements(self, head_pipeline: str = "head-image") -> tuple[tuple[str, str], ...]:
        source_pipeline = {
            "body_reference": "Body-Reference",
            "head_image": "Head-Image-Edit" if head_pipeline == "head-image-edit" else "Head-Image",
            "character_assembly": "Character-Assembly",
        }
        return tuple((role, source_pipeline[role])
                     for role in local_image_pipeline_config(self.pipeline).reference_roles
                     if role in source_pipeline)

    def _source_adapter(self, pipeline: str):
        if pipeline == "Body-Reference":
            from zet.services.local_body_reference_service import LocalBodyReferenceService
            return LocalBodyReferenceService(self.app, self.project_root)
        if pipeline == "Head-Image-Edit":
            from zet.services.local_head_image_edit_service import LocalHeadImageEditService
            return LocalHeadImageEditService(self.app, self.project_root)
        if pipeline == "Head-Image":
            from zet.services.local_head_image_service import LocalHeadImageService
            return LocalHeadImageService(self.app, self.project_root)
        return LocalCharacterAssetPipelineService(self.app, self.project_root, "character-assembly")

    @staticmethod
    def _batch_label(run: dict[str, Any]) -> str:
        name = str(run.get("batch_name") or "Unnamed batch").strip()
        created = str(run.get("created_at") or "")
        return f"{name} · {created.replace('T', ' ')}" if created else name

    def _source_batch_options(self, character: str, phase: str, costume: str, head_pipeline: str = "head-image") -> dict[str, list[dict[str, Any]]]:
        options: dict[str, list[dict[str, Any]]] = {}
        for role, pipeline in self._requirements(head_pipeline):
            adapter = self._source_adapter(pipeline)
            runs = adapter.list_run_summaries(character, phase)
            values = []
            for item in runs:
                selected = item.get("selected_views") or {}
                if not selected:
                    continue
                values.append({"run_id": item["run_id"], "batch_name": self._batch_label(item),
                               "selected_views": sorted(selected)})
            options[role] = values
        return options

    def _selected_batch_input(self, character: str, phase: str, pipeline: str, run_id: str,
                              view: str, costume: str) -> dict[str, Any]:
        adapter = self._source_adapter(pipeline)
        run = adapter.detail(run_id)
        candidate_id = (run.get("selected_views") or {}).get(view)
        candidate = next((item for item in run.get("candidates", [])
                          if item.get("candidate_id") == candidate_id and item.get("view") == view), None)
        image = Path(str((candidate or {}).get("image_path") or "")).resolve()
        source_root = Path(str(run.get("root") or "")).resolve()
        if (not candidate_id or not candidate or not image.is_file()
                or not image.is_relative_to(source_root)):
            raise LocalCharacterAssetPipelineError(
                f"Selected {pipeline} image for {view} is missing from batch {self._batch_label(run)}.")
        digest = self._hash(image)
        if candidate.get("image_sha256") and candidate["image_sha256"] != digest:
            raise LocalCharacterAssetPipelineError(f"Selected {pipeline} image for {view} has changed.")
        local_pipeline = "Character-Assembly" if pipeline == "Character-Assembly" else pipeline
        key = self.asset_store.key(local_pipeline, view)
        selected_asset = (run.get("local_assets") or {}).get(key) or {}
        if (selected_asset.get("batch_id") == run_id and selected_asset.get("candidate_id") == candidate_id
                and selected_asset.get("image_sha256") and selected_asset["image_sha256"] != digest):
            raise LocalCharacterAssetPipelineError(f"Selected {pipeline} image for {view} has changed since selection.")
        return {"pipeline": local_pipeline, "view": view, "qualifier": "", "key": key,
                "candidate_id": candidate_id, "batch_id": run_id, "batch_name": self._batch_label(run),
                "image_path": str(image), "image_sha256": digest, "sha256": digest,
                "selected": True, "locked": bool(candidate.get("locked"))}

    def _resolve_view_inputs(self, character: str, phase: str, costume: str, view: str,
                             source_batches: dict[str, str], head_pipeline: str = "head-image") -> dict[str, dict[str, Any]]:
        result = {}
        for role, pipeline in self._requirements(head_pipeline):
            selected_batch = str(source_batches.get(role) or "").strip()
            if selected_batch and selected_batch != "locked":
                result[role] = {**self._selected_batch_input(character, phase, pipeline, selected_batch, view, costume),
                                "source_mode": "batch"}
            else:
                record = self._locked(character, phase, pipeline, view)
                result[role] = {**record, "pipeline": pipeline, "view": view,
                                "qualifier": "", "image_sha256": record["image_sha256"],
                                "sha256": record["image_sha256"], "source_mode": "locked"}
        return result

    def preview(self, payload: dict[str, Any]) -> dict[str, Any]:
        character, phase = str(payload.get("character") or "").strip(), str(payload.get("phase") or "").strip()
        costume = str(payload.get("costume") or "").strip()
        if not character or not phase or (self.definition["qualifies"] and not costume):
            raise LocalCharacterAssetPipelineError("Character and phase are required; Costume-Dressing also requires a costume.")
        status_loader = getattr(self.app, "character_onboarding_status", None)
        if callable(status_loader):
            status = status_loader(character, phase)
            if not status.template_ready:
                raise LocalCharacterAssetPipelineError("A valid Character.md is required before local production: " + "; ".join(status.validation_errors))
        if self.definition["qualifies"]:
            costume_status_loader = getattr(self.app, "costume_template_status", None)
            if callable(costume_status_loader):
                costume_status = costume_status_loader(character, phase, costume)
                if isinstance(costume_status, dict):
                    template_ready = bool(costume_status.get("template_ready"))
                    validation_errors = costume_status.get("validation_errors") or []
                else:
                    template_ready = bool(getattr(costume_status, "template_ready", False))
                    validation_errors = getattr(costume_status, "validation_errors", []) or []
                if not template_ready:
                    details = "; ".join(str(error) for error in validation_errors)
                    raise LocalCharacterAssetPipelineError(
                        "A valid costume template is required before local Costume-Dressing can run"
                        + (f": {details}" if details else ".")
                    )
        front_count, other_count = render_count(payload.get("front_count"), 8), render_count(payload.get("other_count"), 4)
        from zet.services.local_character_progression_service import planned_views
        requested_views = planned_views(payload)
        total = front_count + (len(requested_views) - 1) * other_count
        if front_count < 1 or other_count < 1 or total > 256:
            raise LocalCharacterAssetPipelineError("Candidate counts must be positive and the run cannot exceed 256 candidates.")
        inputs, blocking_reasons = {}, []
        head_pipeline = str(payload.get("head_pipeline") or "head-image")
        if head_pipeline not in {"head-image", "head-image-edit"}:
            raise LocalCharacterAssetPipelineError("Choose Head-Image or Head-Image Edit as the head pipeline.")
        source_batches = payload.get("source_batches") or {}
        if not isinstance(source_batches, dict):
            raise LocalCharacterAssetPipelineError("Source batch choices must be an object keyed by source role.")
        for view in requested_views:
            resolved = {}
            try:
                resolved = self._resolve_view_inputs(character, phase, costume, view, source_batches, head_pipeline)
            except LocalCharacterAssetPipelineError as exc:
                blocking_reasons.append(str(exc))
            if len(resolved) == len(self._requirements(head_pipeline)):
                inputs[view] = resolved
        costume_path = self._costume_path(character, phase, costume) if costume else None
        if costume_path and not costume_path.is_file():
            blocking_reasons.append(f"Costume template not found: {costume_path}")
        return {"pipeline": self.pipeline, "pipeline_config": pipeline_page_config(self.pipeline),
                "character": character, "phase": phase, "costume": costume,
                "views": requested_views, "front_count": front_count, "other_count": other_count,
                "candidate_count": total, "inputs": inputs, "front_only": bool(payload.get("front_only")),
                "use_front_anchor": self.pipeline != "character-assembly" and bool(payload.get("use_front_anchor", True)),
                "front_anchor_required_for_other_views": self.pipeline != "character-assembly" and bool(payload.get("use_front_anchor", True)),
                "source_batches": {role: str(source_batches.get(role) or "locked") for role, _ in self._requirements(head_pipeline)},
                "head_pipeline": head_pipeline,
                "source_batch_options": self._source_batch_options(character, phase, costume, head_pipeline),
                "can_create": not blocking_reasons, "blocking_reasons": list(dict.fromkeys(blocking_reasons))}

    def _requires_front_anchor(self, run: dict[str, Any]) -> bool:
        return self.pipeline != "character-assembly" and bool(run.get("use_front_anchor", True))

    def _snapshot_inputs(self, root: Path, plan: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], str]:
        snapshot = {}
        input_root = root / "inputs"
        for view, refs in plan["inputs"].items():
            snapshot[view] = {}
            for role, record in refs.items():
                source = Path(record["image_path"])
                expected_hash = str(record.get("sha256") or record.get("image_sha256") or "")
                if not source.is_file():
                    raise LocalCharacterAssetPipelineError(f"Selected {role.replace('_', ' ')} source for {view} changed after preview.")
                destination = input_root / view / f"{role}{source.suffix.lower()}"
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
                snapshot[view][role] = {**record, "image_path": str(destination), "sha256": self._hash(destination),
                                        "managed_checksum": record.get("image_sha256", "")}
        costume_snapshot = ""
        if plan.get("costume"):
            source = self._costume_path(plan["character"], plan["phase"], plan["costume"])
            destination = input_root / (source.name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            costume_snapshot = str(destination)
        return snapshot, costume_snapshot

    def _refresh_costume_snapshot(self, run: dict[str, Any]) -> None:
        if self.pipeline != "costume-dressing":
            return
        source = self._costume_path(run["character"], run["phase"], run["costume"])
        if not source.is_file():
            raise LocalCharacterAssetPipelineError(f"Costume template not found: {source}")
        root = Path(run["root"])
        destination = root / "inputs" / source.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        spec = self._read(root / "spec.json")
        spec["costume_path"] = str(destination)
        spec["costume_sha256"] = self._hash(destination)
        self._write(root / "spec.json", spec)

    def create_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        plan = self.preview(payload)
        if not plan["can_create"]:
            raise LocalCharacterAssetPipelineError("Cannot create this batch: " + " ".join(plan["blocking_reasons"]))
        run_id = uuid4().hex
        root = self._workspace(plan["character"], plan["phase"], plan["costume"]) / run_id
        root.mkdir(parents=True, exist_ok=False)
        sources, costume_path = self._snapshot_inputs(root, plan)
        count = plan["candidate_count"]
        seeds = payload.get("seeds")
        if not isinstance(seeds, list):
            rng = random.SystemRandom()
            seeds = [rng.randrange(0, 2**63 - 1) for _ in range(count)]
        if len(seeds) != count:
            raise LocalCharacterAssetPipelineError("Explicit seed count must match the candidate plan.")
        try:
            seeds = [str(int(seed)) for seed in seeds]
        except (TypeError, ValueError) as exc:
            raise LocalCharacterAssetPipelineError("Every seed must be an integer.") from exc
        candidates, index = [], 0
        for view in plan["views"]:
            for ordinal in range(1, (plan["front_count"] if view == "FRONT" else plan["other_count"]) + 1):
                index += 1
                candidates.append({"candidate_id": view_candidate_id(view, ordinal), "view": view, "ordinal": ordinal,
                                  "seed": seeds[index - 1], "status": "PENDING", "image_path": "",
                                  "human_review": {"decision": "undecided"}, "retry_count": 0})
        spec = {"schema_version": 1, "review_version": 3, "kind": self.pipeline, "run_id": run_id,
                "universe_id": str(getattr(self.app.config, "universe_id", "Moonsea")),
                "created_at": self._now(), "status": "QUEUED", "character": plan["character"], "phase": plan["phase"],
                "costume": plan["costume"], "views": plan["views"], "front_count": plan["front_count"],
                "other_count": plan["other_count"], "candidate_count": count, "sources": sources,
                "source_batches": plan.get("source_batches") or {},
                "head_pipeline": plan.get("head_pipeline", "head-image"),
                "use_front_anchor": plan["use_front_anchor"],
                "costume_path": costume_path, "costume_sha256": self._hash(Path(costume_path)) if costume_path else "",
                "candidates": candidates, "front_anchor": None, "selected_views": {}, "rankings": {}}
        spec["slots_by_view"] = slot_maps(spec)
        self._write(root / "spec.json", spec)
        self._write(root / "state.json", {"run_id": run_id, "status": "QUEUED", "updated_at": self._now(),
                                           "stop_requested": False, "front_anchor": None, "views_started": False,
                                           "candidates": {}, "selected_views": {}, "rankings": {}})
        from zet.services.local_character_progression_service import enroll
        enroll(root, plan["views"])
        return self.detail(run_id, plan["costume"])

    def _all_selected_views_locked(self, run: dict[str, Any]) -> bool:
        return self.asset_store.all_selected_views_locked(
            run, self.definition["asset_pipeline"],
            qualifier=self._qualifier(str(run.get("costume") or "")),
            require_front_anchor=self._requires_front_anchor(run),
        )

    def detail(self, run_id: str, costume: str = "") -> dict[str, Any]:
        root = self._run_root(run_id, costume)
        spec, state = self._read(root / "spec.json"), self._read(root / "state.json")
        from zet.services.local_prompt_improvement_service import ensure_view_reviews
        spec, state = ensure_view_reviews(root, spec, state)
        candidates = merge_candidates(spec, state)
        if self.pipeline == "costume-dressing":
            references_by_view = {}
            for candidate in candidates.values():
                view = str(candidate.get("view") or "")
                if view not in references_by_view:
                    manifest_path = root / "prompts" / view / "dependency_manifest.json"
                    try:
                        manifest = self._read(manifest_path)
                    except LocalCharacterAssetPipelineError:
                        manifest = {}
                    resources = manifest.get("resources") if isinstance(manifest, dict) else None
                    references_by_view[view] = (
                        [dict(item) for item in resources if isinstance(item, dict)]
                        if isinstance(resources, list) else []
                    )
                if references_by_view[view]:
                    candidate["reference_images"] = references_by_view[view]
        result = {**spec, **state, "candidates": list(candidates.values()), "root": str(root),
                  "selected_views": state.get("selected_views") or {}, "rankings": state.get("rankings") or {},
                  "stop_requested": bool(state.get("stop_requested")), "interrupted": False}
        if self.pipeline == "character-assembly":
            result["use_front_anchor"] = False
            front = assembly_front(result)
            front_hash = self._hash(Path(front["image_path"])) if front else ""
            for view, ranking in result["rankings"].items():
                if (view != "FRONT" and ranking.get("status") == "COMPLETE"
                        and len(ranking.get("ordered_candidate_ids") or []) > 1
                        and not any(ref.get("candidate_id") == (front or {}).get("candidate_id")
                                    and ref.get("sha256") == front_hash
                                    for ref in ranking.get("comparison_references") or [])):
                    ranking.update(status="STALE", stale_reason="Re-evaluate against the selected FRONT's proportions and identity.")
        for candidate in result["candidates"]:
            candidate["image_filled"] = Path(str(candidate.get("image_path") or "")).is_file()
        if state.get("status") in ACTIVE_RUN_STATUSES:
            with self._active_lock:
                result["interrupted"] = not self._is_active(run_id) and not runner_lock_active(root)
                if result["interrupted"]:
                    result["status"] = "INTERRUPTED"
        result["local_assets"] = self.asset_store.detail(result["character"], result["phase"])["assets"]
        result["lineage_warnings"] = self._lineage_warnings(result)
        by_id = {item["candidate_id"]: item for item in result["candidates"]}
        result["stale_selections"] = []
        for view, candidate_id in result["selected_views"].items():
            candidate = by_id.get(candidate_id) or {}
            image = Path(str(candidate.get("image_path") or ""))
            ranking = (result.get("rankings", {}).get(view) or {})
            key = self.asset_store.key(self.definition["asset_pipeline"], view, self._qualifier(str(result.get("costume") or "")))
            local_asset = result["local_assets"].get(key) or {}
            stale = (not candidate or not image.is_file() or ranking.get("status") != "COMPLETE"
                     or candidate_id not in (ranking.get("ordered_candidate_ids") or [])
                     or ranking.get("input_hashes", {}).get(candidate_id) != str(candidate.get("image_sha256") or "")
                     or bool(local_asset.get("locked") and local_asset.get("candidate_id") != candidate_id))
            if stale:
                result["stale_selections"].append(view)
        if (result["status"] in {"AWAITING_HUMAN_SELECTION", "REVIEW_REQUIRED", "COMPLETE"}
                and self._all_selected_views_locked(result)):
            result["status"] = "COMPLETE"
            result["stale_selections"] = []
        return decorate_local_pipeline_detail(result, self.pipeline)

    def list_runs(self, character: str = "", phase: str = "", costume: str = "") -> list[dict[str, Any]]:
        character_path = self._safe(character) if character else "*"
        phase_path = self._safe(phase) if phase else "*"
        if costume and self.definition["qualifies"]:
            pattern = (f"{character_path}/{phase_path}/{self.definition['workspace']}/"
                       f"{self._qualifier(costume)}/*/spec.json")
        else:
            pattern = (f"{character_path}/{phase_path}/{self.definition['workspace']}/**/spec.json")
        paths = self.root.glob(pattern)
        result = []
        for path in paths:
            spec = self._read(path)
            if spec.get("kind") == self.pipeline:
                try:
                    result.append(self.detail(spec["run_id"], str(spec.get("costume") or "")))
                except LocalCharacterAssetPipelineError:
                    continue
        return sorted(result, key=lambda item: item.get("created_at", ""), reverse=True)

    def list_run_summaries(self, character: str = "", phase: str = "", costume: str = "") -> list[dict[str, Any]]:
        """List batches without building full details or checking image lineage."""
        character_path = self._safe(character) if character else "*"
        phase_path = self._safe(phase) if phase else "*"
        if costume and self.definition["qualifies"]:
            pattern = (f"{character_path}/{phase_path}/{self.definition['workspace']}/"
                       f"{self._qualifier(costume)}/*/spec.json")
        else:
            pattern = (f"{character_path}/{phase_path}/{self.definition['workspace']}/**/spec.json")
        paths = self.root.glob(pattern)
        result = []
        for path in paths:
            try:
                spec = self._read(path)
                if spec.get("kind") != self.pipeline:
                    continue
                state = self._read(path.with_name("state.json"))
                run_id = str(spec.get("run_id") or path.parent.name)
                status = str(state.get("status") or spec.get("status") or "UNKNOWN")
                interrupted = False
                if status in ACTIVE_RUN_STATUSES:
                    with self._active_lock:
                        interrupted = not self._is_active(run_id) and not runner_lock_active(path.parent)
                    if interrupted:
                        status = "INTERRUPTED"
                if status in {"AWAITING_HUMAN_SELECTION", "REVIEW_REQUIRED"} and self._all_selected_views_locked({
                    **spec, **state, "run_id": run_id,
                    "candidates": list(merge_candidates(spec, state).values()),
                }):
                    status = "COMPLETE"
                result.append({
                    "character_progression": state.get("character_progression"),
                    "run_id": run_id, "batch_name": spec.get("batch_name", ""),
                    "character": spec.get("character", ""), "phase": spec.get("phase", ""),
                    "costume": spec.get("costume", ""), "created_at": spec.get("created_at", ""),
                    "status": status, "candidate_count": len(merge_candidates(spec, state)),
                    "selected_views": state.get("selected_views") or {},
                })
            except (OSError, LocalCharacterAssetPipelineError, ValueError):
                continue
        return sorted(result, key=lambda item: item.get("created_at", ""), reverse=True)

    def rename_run(self, run_id: str, batch_name: str, costume: str = "") -> dict[str, Any]:
        name = str(batch_name or "").strip()
        if len(name) > 120:
            raise LocalCharacterAssetPipelineError("Batch name cannot exceed 120 characters.")
        root = self._run_root(run_id, costume)
        spec_path = root / "spec.json"
        spec = self._read(spec_path)
        spec["batch_name"] = name
        self._write(spec_path, spec)
        return self.detail(run_id, costume)

    def _locked_view_inputs(self, run: dict[str, Any], view: str) -> dict[str, dict[str, Any]]:
        return self._resolve_view_inputs(run["character"], run["phase"], str(run.get("costume") or ""),
                                         view, run.get("source_batches") or {}, run.get("head_pipeline", "head-image"))

    def _lineage_warnings(self, run: dict[str, Any]) -> dict[str, list[str]]:
        warnings: dict[str, list[str]] = {}
        source_runs: dict[tuple[str, str], dict[str, Any]] = {}
        for view, sources in (run.get("sources") or {}).items():
            entries = []
            for role, source in sources.items():
                if role.startswith("front_"):
                    continue
                pipeline = str(source.get("pipeline") or {
                    "body_reference": "Body-Reference", "head_image": "Head-Image",
                    "character_assembly": "Character-Assembly",
                }.get(role, ""))
                qualifier = str(source.get("qualifier") or "")
                key = str(source.get("key") or self.asset_store.key(pipeline, view, qualifier))
                current = (run.get("local_assets") or {}).get(key) or {}
                source_hash = str(source.get("managed_checksum") or source.get("image_sha256") or source.get("sha256") or "")
                source_batch = str(source.get("batch_id") or "")
                source_candidate = str(source.get("candidate_id") or "")
                source_label = str(source.get("batch_name") or "")
                if not source_label and source_batch:
                    try:
                        source_key = (pipeline, source_batch)
                        if source_key not in source_runs:
                            source_runs[source_key] = self._source_adapter(pipeline).detail(source_batch)
                        source_label = self._batch_label(source_runs[source_key])
                    except Exception:
                        source_label = "a previous batch"
                source_label = source_label or "a previous batch"
                current_path = Path(str(current.get("locked_image_path") or ""))
                current_valid = current_path.is_file()
                if not current.get("locked") or not current_valid:
                    entries.append(f"{role.replace('_', ' ')} came from {source_label}; no current locked image exists.")
                elif current.get("image_sha256") != source_hash:
                    entries.append(f"{role.replace('_', ' ')} came from {source_label}, not the current locked image.")
                source_mode = str(source.get("source_mode") or
                                  (run.get("source_batches") or {}).get(role) or "locked")
                if source_mode != "locked" and source_batch and source_candidate:
                    try:
                        source_key = (pipeline, source_batch)
                        if source_key not in source_runs:
                            source_runs[source_key] = self._source_adapter(pipeline).detail(source_batch)
                        source_run = source_runs[source_key]
                        selected = str((source_run.get("selected_views") or {}).get(view) or "")
                        candidate = next((item for item in source_run.get("candidates", [])
                                          if item.get("candidate_id") == source_candidate), None)
                        selected_path = Path(str((candidate or {}).get("image_path") or ""))
                        if (selected != source_candidate or not selected_path.is_file()
                                or (candidate or {}).get("image_sha256", "") != source_hash):
                            entries.append(f"The {role.replace('_', ' ')} image is no longer the selected {view} image in its source batch.")
                        if pipeline == "Character-Assembly":
                            for ancestor_view, messages in (source_run.get("lineage_warnings") or {}).items():
                                if ancestor_view == view:
                                    entries.extend(f"Character-Assembly lineage: {message}" for message in messages)
                    except Exception:
                        entries.append(f"The {role.replace('_', ' ')} source batch is unavailable for lineage verification.")
            if entries:
                warnings[view] = list(dict.fromkeys(entries))
        return warnings

    def _snapshot_view_inputs(self, run: dict[str, Any], view: str,
                              locked: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        inputs = {}
        for role, record in locked.items():
            source = Path(record["image_path"])
            destination = Path(run["root"]) / "inputs" / view / f"{role}{source.suffix.lower()}"
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            inputs[role] = {**record, "image_path": str(destination), "sha256": self._hash(destination),
                            "managed_checksum": record.get("image_sha256", "")}
        spec_path = Path(run["root"]) / "spec.json"
        spec = self._read(spec_path)
        spec.setdefault("sources", {})[view] = inputs
        self._write(spec_path, spec)
        run.setdefault("sources", {})[view] = inputs
        return inputs

    def _refresh_view_inputs(self, run: dict[str, Any], view: str) -> dict[str, dict[str, Any]]:
        source = self._locked_view_inputs(run, view)
        for role, record in source.items():
            path = Path(str(record.get("image_path") or ""))
            digest = str(record.get("sha256") or record.get("image_sha256") or "")
            if not path.is_file():
                raise LocalCharacterAssetPipelineError(f"Chosen {role.replace('_', ' ')} reference for {view} is missing or changed.")
        return self._snapshot_view_inputs(run, view, source)

    def _verify_snapshot_view(self, run: dict[str, Any], view: str) -> dict[str, dict[str, Any]]:
        sources = (run.get("sources") or {}).get(view) or {}
        if len(sources) != len(self._requirements()):
            raise LocalCharacterAssetPipelineError(f"No complete original reference snapshot exists for {view}.")
        for role, record in sources.items():
            path = Path(str(record.get("image_path") or ""))
            if not path.is_file():
                raise LocalCharacterAssetPipelineError(f"Original {role.replace('_', ' ')} snapshot for {view} is missing or changed.")
        return sources

    def _references(self, run: dict[str, Any], view: str, *, use_recipe: bool = False) -> list[dict[str, Any]]:
        from zet.services.local_view_reference_service import custom_references, reference_recipes
        inputs = run.get("sources", {}).get(view)
        if inputs is None:
            inputs = self._snapshot_view_inputs(run, view, self._locked_view_inputs(run, view))
        if self.pipeline == "character-assembly":
            roles = (("body_reference", "head_image") if view == "FRONT" or not self._requires_front_anchor(run)
                     else ("body_reference", "head_image", "front_assembly"))
        else:
            roles = ("character_assembly",) if view == "FRONT" or not self._requires_front_anchor(run) else ("character_assembly", "front_costume")
        refs = []
        custom = use_recipe and (reference_recipes(Path(run["root"])).get(view) or {}).get("mode", "default") != "default"
        for role in roles:
            if role in {"front_assembly", "front_costume"}:
                if custom:
                    continue
                anchor = next((item for item in run["candidates"] if item["candidate_id"] == run.get("front_anchor")), None)
                path = Path(str((anchor or {}).get("image_path") or ""))
                if not anchor or not path.is_file():
                    raise LocalCharacterAssetPipelineError("Select a reviewed FRONT candidate before generating other views.")
                refs.append({"role": role, "path": str(path), "view": "FRONT", "character": run["character"], "phase": run["phase"]})
            else:
                source = inputs[role]
                refs.append({"role": role, "path": source["image_path"], "view": view,
                             "body_view": view, "head_view": view, "character": run["character"], "phase": run["phase"]})
        return custom_references(run, view, self.pipeline, refs) if use_recipe and self.pipeline != "character-assembly" else refs

    def _compile(self, run: dict[str, Any], view: str, refs: list[dict[str, Any]], *, output_dir: Path | None = None, use_reference_recipe: bool = False) -> dict[str, Any]:
        from zet.services.template_source_service import compile_with_revision
        root = Path(run["root"])
        output = output_dir or root / "prompts" / view
        template = self.character_root / run["character"] / run["phase"] / "Character.md"
        job = {"Job": f"Local_{self.pipeline}_{run['run_id']}_{view}", "Task": self.definition["task"],
               "Character": run["character"], "Phase": run["phase"], "Output Directory": str(output),
               "Template Path": str(template), "Reference Files": refs}
        if self.pipeline == "character-assembly":
            job.update({"Body View": view, "Head View": view, "use_front_anchor": False})
            result = compile_with_revision(root, compile_character_assembly_job,
                job, self.project_root, pipeline_mode="local",
                universe_root=self.app.config.base_library_path,
            )
        else:
            job.update({"Body View": view, "Head View": view, "Costume": run["costume"],
                        "Costume Path": run["costume_path"]})
            result = compile_with_revision(root, compile_costume_dressing_job,
                job, self.project_root, pipeline_mode="local",
                universe_root=self.app.config.base_library_path,
            )
        return result

    def queue_render_candidate(self, run_id: str, candidate_id: str, costume: str = "") -> dict[str, Any]:
        run = self.detail(run_id, costume)
        candidate = next((item for item in run["candidates"] if item["candidate_id"] == candidate_id), None)
        if not candidate:
            raise LocalCharacterAssetPipelineError(f"Unknown candidate: {candidate_id}")
        if self.pipeline == "character-assembly":
            guard_view(run, candidate["view"])
        from zet.services.local_character_progression_service import prepare_candidate
        if run.get("character_progression"):
            from zet.services.local_image_workflow_service import LocalImagePipelineWorkflowService
            candidate = prepare_candidate(LocalImagePipelineWorkflowService(self.app, self.project_root, self.pipeline), run, candidate)

        if not candidate.get("render_input") and candidate["view"] != "FRONT" and self._requires_front_anchor(run) and not run.get("front_anchor"):
            raise LocalCharacterAssetPipelineError("Select a FRONT candidate before generating other views.")
        root = Path(run["root"])
        candidate_root = root / "renders" / candidate_id
        candidate_root.mkdir(parents=True, exist_ok=True)
        saved_input = candidate.get("render_input")
        if saved_input:
            verify_input(saved_input)
        else:
            refs = self._references(run, candidate["view"])
            compiled = self._compile(run, candidate["view"], refs)
            saved_input = frozen_input(candidate_root / "inputs", Path(compiled["final_prompt"]).read_text(encoding="utf-8"),
                                       compiled.get("reference_files") or refs, self.definition["preset"])
            saved_input["template_revision_id"] = compiled.get("template_revision_id", "")
        self._update(run_id, candidate_id, costume=costume, render_input=saved_input)
        render_root = candidate_root / "Local_Test_Renders"
        target = render_root / f"{self.pipeline.replace('-', '')}_{candidate_id}_{candidate.get('retry_count', 0)}.png"
        prompt_path = candidate_root / "Final_Prompt.md"
        prompt_path.write_text(saved_input["prompt"], encoding="utf-8")
        prompt_copy = candidate_root / "Qwen_Local_Character_Prompt.md"
        prompt_copy.write_text("Positive Prompt:\n" + saved_input["prompt"] + "\n\nNegative Prompt:\n", encoding="utf-8")
        preset_name = saved_input["preset"]
        profile = LocalRenderBackendService(self.app.config.state_file(self.project_root, "Local_Render_Presets.json"), config=self.app.config).preset(preset_name)
        ask_id = f"LocalCharacterAsset_{run_id}_{candidate_id}_{candidate.get('retry_count', 0)}"
        manifest = {"ask_id": ask_id, "character": run["character"], "phase": run["phase"],
                    "pipeline": f"Local-{self.definition['label'].removeprefix('Local ')}", "pipeline_stage": "LOCAL_CHARACTER_RENDER"}
        render_references = saved_input["references"]
        ask_path = self.app.ai_proxy_service.stage_render_task_local_render_ask(
            manifest, prompt_copy, candidate_root, allow_parallel=True, seed=int(candidate["seed"]),
            checkpoint=str(profile.get("diffusion_model") or ""), render_preset=preset_name,
            image_generation="comfyui", reference_files=render_references,
        )
        ask = self._read(ask_path / "ask_manifest.json")
        target = render_root / str(ask.get("target_output_file") or target.name)
        ref_hashes = {
            str(ref.get("image_index") or index + 1): self._hash(Path(ref["path"]))
            for index, ref in enumerate(render_references)
        }
        self._update(run_id, candidate_id, costume=costume, status="QUEUED", ask_id=ask["ask_id"],
                     image_path=str(target), prompt_path=str(prompt_path), prompt_sha256=self._hash(prompt_path),
                     reference_images=[{**ref, "role": str(ref.get("role") or "reference"),
                                        "label": ref.get("label", ""), "path": ref["path"],
                                        "sha256": self._hash(Path(ref["path"]))}
                                       for ref in render_references],
                     input_hashes=ref_hashes, workflow_kind=str(ask.get("workflow_kind") or profile.get("workflow_kind") or ""),
                     render_preset=preset_name, queued_at=self._now())
        return self.detail(run_id, costume)

    def _state(self, run_id: str, costume: str = "") -> tuple[Path, dict[str, Any]]:
        root = self._run_root(run_id, costume)
        return root, self._read(root / "state.json")

    def _update(self, run_id: str, candidate_id: str, costume: str = "", **changes: Any) -> None:
        root = self._run_root(run_id, costume)
        def apply(state: dict[str, Any]) -> None:
            state.setdefault("candidates", {}).setdefault(candidate_id, {}).update(changes)
            state["updated_at"] = self._now()
        mutate_local_run_state(root, apply)

    def _run_update(self, run_id: str, costume: str = "", **changes: Any) -> None:
        root = self._run_root(run_id, costume)
        def apply(state: dict[str, Any]) -> None:
            state.update(changes, updated_at=self._now())
        mutate_local_run_state(root, apply)

    def _proxy_answer(self, ask_id: str) -> tuple[str, dict[str, Any]]:
        return self.app.ai_proxy_service.ai_proxy_path_service.jobs.execution_status(ask_id)

    def _harvest_render(self, run: dict[str, Any], candidate: dict[str, Any]) -> None:
        paths = self.app.ai_proxy_service.ai_proxy_path_service
        ask_id = str(candidate.get("ask_id") or "")
        answer_dir = paths.answer_path(ask_id)
        if not answer_dir.is_dir() or not (answer_dir / "answer_manifest.json").is_file():
            return
        ask, answer = self._read(answer_dir / "ask_manifest.json"), self._read(answer_dir / "answer_manifest.json")
        expected_pipeline = f"Local-{self.definition['label'].removeprefix('Local ')}"
        if (ask.get("ask_id") != ask_id or answer.get("ask_id") != ask_id
                or ask.get("pipeline") != expected_pipeline or not self._ask_belongs_to_run(ask, run)):
            raise LocalCharacterAssetPipelineError("AI Proxy answer does not belong to this candidate.")
        if answer.get("status") in {"ERROR", "RETRY_LATER", "FAILED"}:
            raise LocalCharacterAssetPipelineError(str(answer.get("error_message") or "Local render failed."))
        if answer.get("status") != "SUCCESS" or Path(str(answer.get("expected_output") or "")).name != answer.get("expected_output"):
            return
        source = answer_dir / str(answer["expected_output"])
        target = Path(str(candidate.get("image_path") or ""))
        if not source.is_file() or not target.resolve().is_relative_to(Path(run["root"]).resolve()):
            raise LocalCharacterAssetPipelineError("AI Proxy returned an invalid candidate image.")
        paths.jobs.copy_result(ask_id, target, image=True)
        elapsed_seconds = answer.get("elapsed_seconds")
        if elapsed_seconds is None:
            try:
                started = datetime.fromisoformat(str(answer.get("started_at") or ""))
                completed = datetime.fromisoformat(str(answer.get("completed_at") or ""))
                elapsed_seconds = max(0.0, (completed - started).total_seconds())
            except (TypeError, ValueError):
                elapsed_seconds = None
        try:
            elapsed_seconds = max(0.0, float(elapsed_seconds)) if elapsed_seconds is not None else None
        except (TypeError, ValueError):
            elapsed_seconds = None
        if elapsed_seconds is not None:
            self._update(run["run_id"], candidate["candidate_id"],
                         costume=str(run.get("costume") or ""), elapsed_seconds=elapsed_seconds)

    def _wait_render(self, run_id: str, candidate_id: str, costume: str = "") -> bool:
        candidate = next((item for item in self.detail(run_id, costume)["candidates"] if item["candidate_id"] == candidate_id), None)
        if candidate is None:
            return True
        target = Path(str(candidate.get("image_path") or ""))
        deadline = time.monotonic() + 1860
        while not self.app.ai_proxy_service.ai_proxy_path_service.jobs.image_harvest_ready(str(candidate.get("ask_id") or ""), target):
            if not any(c["candidate_id"] == candidate_id for c in self.detail(run_id, costume)["candidates"]):
                return True
            run = self.detail(run_id, costume)
            if run.get("stop_requested"):
                return False
            self._harvest_render(run, candidate)
            if self.app.ai_proxy_service.ai_proxy_path_service.jobs.image_harvest_ready(str(candidate.get("ask_id") or ""), target):
                break
            _, answer = self._proxy_answer(str(candidate.get("ask_id") or ""))
            if answer.get("status") in {"ERROR", "RETRY_LATER", "FAILED"}:
                raise LocalCharacterAssetPipelineError(str(answer.get("error_message") or "Local render failed."))
            if time.monotonic() >= deadline and not self.app.ai_proxy_service.ai_proxy_path_service.jobs.is_pending(str(candidate.get("ask_id") or "")):
                raise LocalCharacterAssetPipelineError("Timed out waiting for the local render.")
            time.sleep(max(.5, float(self.app.config.comfyui_poll_seconds)))
        self._update(run_id, candidate_id, costume, status="WAITING_FOR_HUMAN_REVIEW", image_sha256=self._hash(target), rendered_at=self._now())
        return True







    def stage_view_evaluation(self, run_id: str, view: str, costume: str = "", *, candidate_ids: set[str] | None = None) -> dict[str, Any]:
        from zet.services.local_image_evaluation_service import finish_evaluation, local_image_evaluation_service, update_view_evaluation
        view = str(view or "").upper()
        run = self.detail(run_id, costume)
        if self.pipeline == "character-assembly" and view != "FRONT" and not assembly_front(run):
            raise LocalCharacterAssetPipelineError("Select an available FRONT image before ranking remaining views.")
        candidates = [item for item in run.get("candidates") or [] if item.get("view") == view
                      and (candidate_ids is None or item["candidate_id"] in candidate_ids)
                      and Path(str(item.get("image_path") or "")).is_file()]
        hashes = {item["candidate_id"]: str(item.get("image_sha256") or "") for item in candidates}
        previous = (run.get("evaluations") or {}).get(view) or {}
        if previous.get("status") == "RUNNING" and previous.get("input_hashes") == hashes:
            self.reconcile_review_jobs(run_id, costume)
            return previous
        evaluation_id = uuid4().hex
        def rank():
            if self.detail(run_id, costume).get("stop_requested"):
                return
            self.rank_view(run_id, view, costume, evaluation_id=evaluation_id)
            current = dict((self.detail(run_id, costume).get("evaluations") or {}).get(view) or {})
            if current.get("evaluation_id") == evaluation_id:
                current["status"] = "COMPLETE"
                update_view_evaluation(self._run_root(run_id, costume), view, current, evaluation_id=evaluation_id)
        return local_image_evaluation_service().stage_view_evaluation(
            run_id, view, evaluation_id, rank=rank,
            finish=lambda: finish_evaluation(self._run_root(run_id, costume), view, evaluation_id),
            save_evaluation=lambda record: update_view_evaluation(self._run_root(run_id, costume), view, record, evaluation_id=evaluation_id, replace=True),
            input_hashes=hashes)

    def reconcile_review_jobs(self, run_id: str, costume: str = "") -> dict[str, Any]:
        from zet.services.local_image_evaluation_service import finish_evaluation, local_image_evaluation_service
        run = self.detail(run_id, costume)
        for view, evaluation in (run.get("evaluations") or {}).items():
            if evaluation.get("status") != "RUNNING":
                continue
            evaluation_id = str(evaluation.get("evaluation_id") or "")
            if evaluation_id:
                local_image_evaluation_service().reconcile_review_jobs(
                    run_id, view, evaluation_id,
                    finish=lambda view=view, evaluation_id=evaluation_id: finish_evaluation(self._run_root(run_id, costume), view, evaluation_id),
                    rank=lambda view=view, evaluation_id=evaluation_id: self.rank_view(run_id, view, costume, evaluation_id=evaluation_id))
        return self.detail(run_id, costume)




    def execute_run(self, run_id: str, *, views: set[str] | None = None, costume: str = "",
                    candidate_ids: set[str] | None = None, render_only: bool = False) -> None:
        from zet.services.local_character_progression_service import execution_views
        staged = self.detail(run_id, costume)
        if staged.get("character_progression") or self.pipeline == "character-assembly":
            views = execution_views(staged, views)
            if not views:
                return
        root = self._run_root(run_id, costume)
        try:
            with file_lock(root / "runner.lock", timeout=0):
                with self._active_lock:
                    self._active.add(self._active_key(run_id))
                run = self.detail(run_id, costume)
                if candidate_ids is None and run.get("target_candidate_ids"):
                    candidate_ids = set(run["target_candidate_ids"])
                if views is None and run.get("target_views"):
                    views = set(run["target_views"])
                if views is None:
                    views = set(VIEWS) if run.get("front_anchor") or not self._requires_front_anchor(run) else {"FRONT"}
                if any(view != "FRONT" for view in views) and ((self.pipeline == "character-assembly" and not assembly_front(run))
                        or (self._requires_front_anchor(run) and not run.get("front_anchor"))):
                    self._run_update(run_id, costume, status="AWAITING_FRONT_ANCHOR",
                                     error="Select a FRONT candidate before generating other views.")
                    return
                self._run_update(run_id, costume, status="RUNNING", error="", slot_work_pending=False,
                                 target_views=sorted(views), target_candidate_ids=sorted(candidate_ids or []), recovery_render_only=render_only)
                for view in [item for item in VIEWS if item in views]:
                    pending = [item for item in self.detail(run_id, costume)["candidates"] if item["view"] == view
                               and (candidate_ids is not None or not item.get("slot_managed"))
                               and (candidate_ids is None or item["candidate_id"] in candidate_ids)
                               and not Path(str(item.get("image_path") or "")).is_file()]
                    for item in pending:
                        if self.detail(run_id, costume).get("stop_requested"):
                            break
                        current = next((x for x in self.detail(run_id, costume)["candidates"] if x["candidate_id"] == item["candidate_id"]), None)
                        if current is None:
                            continue
                        if Path(str(current.get("image_path") or "")).is_file():
                            continue
                        try:
                            ask_id = str(current.get("ask_id") or "")
                            queue_status, _ = self._proxy_answer(ask_id) if ask_id else ("UNKNOWN", {})
                            if queue_status in {"QUEUED", "RUNNING", "ANSWERED", "RECOVERING", "PAUSED_STORAGE", "HELD"}:
                                self._update(run_id, item["candidate_id"], costume,
                                             status="QUEUED" if queue_status == "QUEUED" else "RUNNING")
                                continue
                            if current.get("ask_id") or current.get("status") == "RUNNING":
                                self.retry_candidate(run_id, item["candidate_id"], costume)
                            self.queue_render_candidate(run_id, item["candidate_id"], costume)
                            self._update(run_id, item["candidate_id"], costume, status="RUNNING")
                        except Exception as exc:
                            from zet.services.storage_health_service import pause_on_storage_error
                            pause_on_storage_error(self.app.config, exc)
                            self._update(run_id, item["candidate_id"], costume, status="FAILED", render_error=str(exc))
                    for item in pending:
                        if self.detail(run_id, costume).get("stop_requested"):
                            break
                        current = next((x for x in self.detail(run_id, costume)["candidates"] if x["candidate_id"] == item["candidate_id"]), None)
                        if current is None:
                            continue
                        if not Path(str(current.get("image_path") or "")).is_file() and current.get("status") in {"QUEUED", "RUNNING"}:
                            try:
                                self._wait_render(run_id, item["candidate_id"], costume)
                            except Exception as exc:
                                from zet.services.storage_health_service import pause_on_storage_error
                                pause_on_storage_error(self.app.config, exc)
                                self._update(run_id, item["candidate_id"], costume, status="FAILED", render_error=str(exc))
                    if not render_only and not self.detail(run_id, costume).get("stop_requested"):
                        pending = [item for item in self.detail(run_id, costume)["candidates"] if item["view"] == view
                                   and (candidate_ids is not None or not item.get("slot_managed"))
                                   and (candidate_ids is None or item["candidate_id"] in candidate_ids)
                                   and Path(str(item.get("image_path") or "")).is_file()]
                        if pending and not self.detail(run_id, costume).get("stop_requested"):
                            self.stage_view_evaluation(run_id, view, costume)
                latest = self.detail(run_id, costume)
                selected = latest.get("selected_views") or {}
                complete = all(selected.get(view) for view in VIEWS)
                status = "CANCELLED" if latest.get("stop_requested") else "COMPLETE" if complete else "AWAITING_FRONT_ANCHOR" if self._requires_front_anchor(latest) and not latest.get("front_anchor") else "AWAITING_HUMAN_SELECTION"
                self._run_update(run_id, costume, status=status, target_views=[], target_candidate_ids=[])
        except TimeoutError:
            return
        except Exception as exc:
            from zet.services.storage_health_service import pause_on_storage_error
            pause_on_storage_error(self.app.config, exc)
            from zet.services.storage_health_service import storage_health
            if not storage_health(self.app.config).check_error(exc):
                self._run_update(run_id, costume, status="ERROR", error=str(exc))
        finally:
            with self._active_lock:
                self._active.discard(self._active_key(run_id))

    def _rank(self, run: dict[str, Any], view: str) -> dict[str, Any]:
        survivors = [item for item in run["candidates"] if item["view"] == view
                     and Path(str(item.get("image_path") or "")).is_file()]
        from zet.services.image_harvest_service import candidate_admission, require_candidate_harvest
        for survivor in survivors:
            require_candidate_harvest(self.app, run, survivor)
        hashes = {item["candidate_id"]: str(item.get("image_sha256") or "") for item in survivors}
        comparisons = []
        if self.pipeline == "character-assembly" and view != "FRONT":
            front = assembly_front(run)
            if not front:
                raise LocalCharacterAssetPipelineError("Select an available FRONT image before ranking remaining views.")
            image = Path(front["image_path"])
            comparisons.append({"candidate_id": front["candidate_id"], "view": "FRONT",
                                "path": str(image), "sha256": self._hash(image)})
        if not survivors:
            ranking = {"status": "EMPTY", "ordered_candidate_ids": [], "luna_ordered_candidate_ids": [], "entries": [], "input_hashes": {}, "recorded_at": self._now()}
        elif len(survivors) == 1:
            item = survivors[0]
            ranking = {"status": "COMPLETE", "ordered_candidate_ids": [item["candidate_id"]],
                       "luna_ordered_candidate_ids": [item["candidate_id"]],
                       "entries": [{"candidate_id": item["candidate_id"], "reason": "Only completed image in this view."}],
                       "input_hashes": hashes, "model": "deterministic-single-survivor", "recorded_at": self._now()}
        else:
            prompt = (f"Rank all rendered {self.definition['label']} images for {view}. "
                      "Human review is an independent advice signal; assess every image on its visual merits. "
                      "Compare view accuracy, source preservation, identity, and usefulness as a reference. "
                      "Candidate IDs: " + ", ".join(hashes))
            image_paths = [str(item["image_path"]) for item in survivors]
            try:
                reference_image_paths, reference_guidance = supplied_ranking_references(
                    survivors, lambda: self._references(run, view, use_recipe=True), comparisons=comparisons,
                    source_roles=("body_reference", "head_image") if self.pipeline == "character-assembly" else None)
                entries, model = rank_images_with_luna(
                    project_root=self.project_root,
                    model=str(getattr(self.app.config, "codex_default_model", "gpt-6-luna")),
                    prompt=prompt + "\n\n" + reference_guidance,
                    candidate_ids=list(hashes),
                    image_paths=image_paths,
                    paths=self.app.ai_proxy_service.ai_proxy_path_service,
                    admission=lambda: candidate_admission(self.app, lambda: self.detail(run["run_id"], str(run.get("costume") or "")), run, survivors),
                    owner={"run_id": run["run_id"], "view": view, "pipeline": self.pipeline, "evaluation_id": str((run.get("evaluations") or {}).get(view, {}).get("evaluation_id") or "")},
                    reference_image_paths=reference_image_paths,
                )
            except Exception as exc:
                from zet.services.storage_health_service import pause_on_storage_error
                pause_on_storage_error(self.app.config, exc)
                raise LocalCharacterAssetPipelineError(str(exc)) from exc
            ranking = {"status": "COMPLETE", "ordered_candidate_ids": [entry["candidate_id"] for entry in entries],
                       "luna_ordered_candidate_ids": [entry["candidate_id"] for entry in entries],
                           "entries": entries, "input_hashes": hashes,
                           "model": model, "recorded_at": self._now()}
        if self.pipeline == "character-assembly":
            ranking["comparison_references"] = comparisons if len(survivors) > 1 else []
        return ranking

    def rank_view(self, run_id: str, view: str, costume: str = "", *, evaluation_id: str = "") -> dict[str, Any]:
        run = self.detail(run_id, costume)
        view = view.upper()
        if view not in VIEWS:
            raise LocalCharacterAssetPipelineError(f"Unknown view: {view}")
        if self.pipeline == "character-assembly" and view != "FRONT" and not assembly_front(run):
            raise LocalCharacterAssetPipelineError("Select an available FRONT image before ranking remaining views.")
        comparison_before = assembly_front(run) if self.pipeline == "character-assembly" and view != "FRONT" else None
        comparison_hash = self._hash(Path(comparison_before["image_path"])) if comparison_before else ""
        if view != "FRONT" and self._requires_front_anchor(run) and not run.get("front_anchor"):
            raise LocalCharacterAssetPipelineError("Select a FRONT candidate before ranking other views.")
        root, state = self._state(run_id, costume)
        current_evaluation = (run.get("evaluations") or {}).get(view) or {}
        evaluation_id = evaluation_id or str(current_evaluation.get("evaluation_id") or "")
        if evaluation_id and (current_evaluation.get("evaluation_id") != evaluation_id
                              or current_evaluation.get("status") not in {"RUNNING", "STAGING"}):
            return run
        hashes_before = {item["candidate_id"]: str(item.get("image_sha256") or "")
                         for item in run["candidates"] if item.get("view") == view
                         and Path(str(item.get("image_path") or "")).is_file()}
        can_start = []
        def mark_running(current: dict[str, Any]) -> None:
            active = (current.get("evaluations") or {}).get(view) or {}
            if evaluation_id and (active.get("evaluation_id") != evaluation_id
                                  or active.get("status") not in {"RUNNING", "STAGING"}):
                can_start.append(False)
                return
            current.setdefault("rankings", {}).update({
                view: {"status": "RUNNING", "started_at": self._now(), "evaluation_id": evaluation_id,
                       "input_hashes": hashes_before}
            })
            can_start.append(True)
        mutate_local_run_state(root, mark_running)
        if can_start and not can_start[-1]:
            return run
        try:
            ranking = self._rank(run, view)
        except Exception as exc:
            from zet.services.storage_health_service import pause_on_storage_error
            pause_on_storage_error(self.app.config, exc)
            ranking = {"status": "FAILED", "error": str(exc), "recorded_at": self._now()}
        def save(current: dict[str, Any]) -> None:
            active = (current.get("evaluations") or {}).get(view) or {}
            if evaluation_id and (active.get("evaluation_id") != evaluation_id or active.get("status") not in {"RUNNING", "STAGING"}):
                return
            if comparison_before:
                front_now = assembly_front(self.detail(run_id, costume))
                if (not front_now or front_now["candidate_id"] != comparison_before["candidate_id"]
                        or self._hash(Path(front_now["image_path"])) != comparison_hash):
                    return
            hashes_now = {item["candidate_id"]: str(item.get("image_sha256") or "")
                          for item in self.detail(run_id, costume)["candidates"] if item.get("view") == view
                          and Path(str(item.get("image_path") or "")).is_file()}
            if hashes_now != hashes_before:
                return
            ranking["evaluation_id"] = evaluation_id
            current.setdefault("rankings", {})[view] = ranking
            if evaluation_id:
                ranking_status = ranking.get("status")
                active.update(ranking_status=ranking_status, ranking_updated_at=self._now())
                if ranking_status in {"COMPLETE", "FAILED", "EMPTY", "SKIPPED"}:
                    active["status"] = "COMPLETE"
                current.setdefault("evaluations", {})[view] = active
        mutate_local_run_state(root, save)
        return self.detail(run_id, costume)

    def move_rank(self, run_id: str, view: str, candidate_id: str, direction: str, costume: str = "") -> dict[str, Any]:
        run = self.detail(run_id, costume)
        root = Path(run["root"])
        view = view.upper()
        ranking = dict((run.get("rankings") or {}).get(view) or {})
        try:
            adjusted = adjust_candidate_ranking(ranking, candidate_id, direction, timestamp=self._now())
        except ValueError as exc:
            raise LocalCharacterAssetPipelineError(str(exc)) from exc
        if adjusted == ranking:
            return run
        def save_ranking(current: dict[str, Any]) -> None:
            rankings = current.setdefault("rankings", {})
            previous = rankings.get(view)
            if previous and previous.get("status") not in {"RUNNING", "QUEUED"}:
                current.setdefault("ranking_history", {}).setdefault(view, []).append(
                    {"archived_at": self._now(), "ranking": previous}
                )
            rankings[view] = adjusted
        mutate_local_run_state(root, save_ranking)
        return self.detail(run_id, costume)

    def rerun_failed_view(self, run_id: str, view: str, costume: str = "") -> dict[str, Any]:
        run, view = self.detail(run_id, costume), view.upper()
        if self.pipeline == "character-assembly":
            guard_view(run, view)
        if view not in VIEWS:
            raise LocalCharacterAssetPipelineError(f"Unknown view: {view}")
        if view != "FRONT" and self._requires_front_anchor(run) and not run.get("front_anchor"):
            raise LocalCharacterAssetPipelineError("Select a FRONT candidate before rerunning failed candidates in other views.")
        self.asset_store.assert_batch_change_allowed(run["character"], run["phase"], self.definition["asset_pipeline"], view, self._qualifier(costume))
        root, state = self._state(run_id, costume)
        failed = [item for item in run["candidates"] if item["view"] == view and
                  (item.get("status") == "FAILED" or item.get("human_review", {}).get("decision") == "reject")]
        from zet.services.local_image_pipeline_policy import clear_candidate_artifacts
        for candidate in failed:
            clear_candidate_artifacts(root, candidate["candidate_id"], candidate.get("image_path"))
            state.setdefault("candidates", {})[candidate["candidate_id"]] = {
                "status": "PENDING", "image_path": "", "ask_id": "",
                "human_review": {"decision": "undecided"},
                "retry_count": int(candidate.get("retry_count") or 0) + 1,
            }
        state.setdefault("rankings", {}).pop(view, None)
        from zet.services.local_image_evaluation_service import supersede_evaluations
        supersede_evaluations(state, {view}, "Candidates in this view are being re-run.")
        state.update(status="QUEUED", stop_requested=False, target_views=[view],
                     target_candidate_ids=[item["candidate_id"] for item in run["candidates"]
                                           if item["view"] == view])
        self._write(root / "state.json", state)
        return self.detail(run_id, costume)

    def reevaluate(self, run_id: str, view: str | None = None, costume: str = "") -> dict[str, Any]:
        run = self.detail(run_id, costume)
        views = {view.upper()} if view else set(VIEWS)
        if not views.issubset(set(VIEWS)):
            raise LocalCharacterAssetPipelineError(f"Unknown view: {view}")
        if any(current != "FRONT" for current in views) and self._requires_front_anchor(run) and not run.get("front_anchor"):
            raise LocalCharacterAssetPipelineError("Select a FRONT candidate before re-evaluating other views.")
        root, state = self._state(run_id, costume)
        from zet.services.local_image_evaluation_service import supersede_evaluations
        supersede_evaluations(state, views, "The view is being re-evaluated.")
        for candidate in run["candidates"]:
            if candidate["view"] in views and Path(str(candidate.get("image_path") or "")).is_file():
                state.setdefault("candidates", {}).setdefault(candidate["candidate_id"], {}).update(
                    status="WAITING_FOR_HUMAN_REVIEW")
        for current in views:
            state.setdefault("rankings", {}).pop(current, None)
        state["status"] = "QUEUED"
        state["stop_requested"] = False
        self._write(root / "state.json", state)
        return self.detail(run_id, costume)

    @serialize_local_run_state
    def select_view(self, run_id: str, view: str, candidate_id: str, costume: str = "", *, autogenerate: bool = False) -> dict[str, Any]:
        run, view = self.detail(run_id, costume), view.upper()
        if run.get("character_progression"):
            from zet.services.local_character_progression_service import select
            from zet.services.local_image_workflow_service import LocalImagePipelineWorkflowService
            return select(LocalImagePipelineWorkflowService(self.app, self.project_root, self.pipeline), run, view, candidate_id)

        if view not in VIEWS:
            raise LocalCharacterAssetPipelineError(f"Unknown view: {view}")
        if not candidate_id:
            return self.unselect_view(run_id, view, costume)
        qualifier = self._qualifier(costume)
        candidate = next((item for item in run["candidates"] if item["candidate_id"] == candidate_id), None)
        if not candidate or candidate["view"] != view:
            raise LocalCharacterAssetPipelineError("Choose a candidate from this view.")
        auto_approved = bool(autogenerate and view == "FRONT")
        if auto_approved and candidate.get("human_review", {}).get("decision") == "reject":
            raise LocalCharacterAssetPipelineError("A human-rejected candidate cannot be autoselected.")
        ranking = (run.get("rankings") or {}).get(view) or {}
        image = Path(str(candidate.get("image_path") or ""))
        if not image.is_file():
            raise LocalCharacterAssetPipelineError("The candidate image is missing.")
        luna_order = list(ranking.get("luna_ordered_candidate_ids") or [])
        if not luna_order and len(ranking.get("ordered_candidate_ids") or []) == 1:
            luna_order = list(ranking["ordered_candidate_ids"])
        if auto_approved and (not luna_order or luna_order[0] != candidate_id):
            raise LocalCharacterAssetPipelineError("Autogenerate can select only the original #1 Luna candidate.")
        if auto_approved and ranking.get("status") != "COMPLETE":
            raise LocalCharacterAssetPipelineError("Autogenerate requires a completed Luna ranking.")
        key = self.asset_store.key(self.definition["asset_pipeline"], view, qualifier)
        existing = run["local_assets"].get(key) or {}
        self.asset_store.assert_batch_change_allowed(run["character"], run["phase"], self.definition["asset_pipeline"], view, qualifier)
        dependencies = []
        if self.pipeline == "character-assembly":
            for pipeline in ("Body-Reference", "Head-Image"):
                source = run["sources"][view]["body_reference" if pipeline == "Body-Reference" else "head_image"]
                dependencies.append({"key": source["key"], "image_sha256": source["sha256"]})
        else:
            source = run["sources"][view]["character_assembly"]
            dependencies.append({"key": source["key"], "image_sha256": source["sha256"]})
        if view != "FRONT" and self._requires_front_anchor(run) and run.get("front_anchor"):
            front = next((item for item in run["candidates"] if item["candidate_id"] == run.get("front_anchor")), None)
            front_image = Path(str((front or {}).get("image_path") or ""))
            if front_image.is_file():
                dependencies.append({"key": self.asset_store.key(self.definition["asset_pipeline"], "FRONT", qualifier),
                                     "image_sha256": self._hash(front_image)})
        self.asset_store.record_batch_selection(run["character"], run["phase"], self.definition["asset_pipeline"], view,
                                          candidate_id=candidate_id, image_path=image, batch_id=run_id,
                                          dependencies=dependencies, qualifier=qualifier)
        root, state = self._state(run_id, costume)
        state.setdefault("selected_views", {})[view] = candidate_id
        if view == "FRONT":
            old_anchor = state.get("front_anchor")
            state["front_anchor"] = candidate_id
            if old_anchor != candidate_id and self.pipeline == "character-assembly":
                invalidate_assembly_rankings(state)
            if old_anchor != candidate_id and self._requires_front_anchor(run):
                from zet.services.local_image_evaluation_service import supersede_evaluations
                supersede_evaluations(state, set(VIEWS[1:]), "The selected FRONT anchor changed.")
                state["views_started"] = True
                for other in VIEWS[1:]:
                    ranking = state.setdefault("rankings", {}).get(other)
                    if ranking:
                        ranking.update(status="STALE", stale_reason="FRONT anchor changed.")
                    for item in run["candidates"]:
                        if item["view"] == other:
                            item_state = state.setdefault("candidates", {}).setdefault(item["candidate_id"], {})
                            item_state.update(stale_selection=bool(state.get("selected_views", {}).get(other)))
        update = {"selected_at": self._now()}
        if auto_approved:
            update["autogenerate_approval"] = {"approved_at": self._now(), "reason": "Current #1 Luna FRONT candidate has a valid image and ranking."}
        state.setdefault("candidates", {}).setdefault(candidate_id, {}).update(update)
        if state.get("status") not in ACTIVE_RUN_STATUSES:
            state["status"] = "COMPLETE" if all(state.get("selected_views", {}).get(target) for target in VIEWS) else "AWAITING_HUMAN_SELECTION"
        self._write(root / "state.json", state)
        return self.detail(run_id, costume)

    @serialize_local_run_state
    def unselect_view(self, run_id: str, view: str, costume: str = "") -> dict[str, Any]:
        run, view = self.detail(run_id, costume), str(view or "").upper()
        if view not in VIEWS:
            raise LocalCharacterAssetPipelineError(f"Unknown view: {view}")
        targets = (view,)
        qualifier = self._qualifier(costume)
        for target in targets:
            self.asset_store.assert_batch_change_allowed(run["character"], run["phase"],
                                                         self.definition["asset_pipeline"], target, qualifier)
        root, state = self._state(run_id, costume)
        for target in targets:
            state.setdefault("selected_views", {}).pop(target, None)
            self.asset_store.clear_batch_selection(run["character"], run["phase"],
                self.definition["asset_pipeline"], target, run_id, qualifier)
        if view == "FRONT":
            state["front_anchor"] = None
            if self.pipeline == "character-assembly":
                invalidate_assembly_rankings(state)
            if self._requires_front_anchor(run):
                from zet.services.local_image_evaluation_service import supersede_evaluations
                supersede_evaluations(state, set(VIEWS[1:]), "The selected FRONT anchor changed.")
            for other in VIEWS[1:]:
                ranking = state.setdefault("rankings", {}).get(other)
                if ranking:
                    ranking.update(status="STALE", stale_reason="The selected FRONT anchor changed.")
                for candidate in run.get("candidates") or []:
                    if candidate.get("view") == other:
                        update = state.setdefault("candidates", {}).setdefault(candidate["candidate_id"], {})
                        if state.get("selected_views", {}).get(other) == candidate.get("candidate_id"):
                            update["stale_selection"] = True
        if state.get("status") not in ACTIVE_RUN_STATUSES:
            state["status"] = "AWAITING_FRONT_ANCHOR" if view == "FRONT" and self._requires_front_anchor(run) else "AWAITING_HUMAN_SELECTION"
        self._write(root / "state.json", state)
        return self.detail(run_id, costume)

    def _collect_promotion_selection(self, run: dict[str, Any], pipeline: str, view: str,
                                     qualifier: str, records: dict[str, dict[str, Any]],
                                     visiting: set[tuple[str, str, str]]) -> None:
        marker = (pipeline, qualifier, view)
        if marker in visiting:
            return
        visiting.add(marker)
        candidate_id = str((run.get("selected_views") or {}).get(view) or "")
        candidate = next((item for item in run.get("candidates", [])
                          if item.get("candidate_id") == candidate_id and item.get("view") == view), None)
        image = Path(str((candidate or {}).get("image_path") or "")).resolve()
        if not candidate_id or not candidate or not image.is_file():
            raise LocalCharacterAssetPipelineError(f"Select a readable {pipeline} image for {view} before promoting its lineage.")
        prompt_pilot = bool(candidate.get("prompt_generator"))
        # Locking captures the selected image; review freshness is tracked separately.
        digest = self._hash(image)

        dependencies = []
        if pipeline == "Character-Assembly":
            for role, source in (run.get("sources", {}).get(view) or {}).items():
                if role in {"body_reference", "head_image"}:
                    self._collect_promotion_source(run, view, source, records, visiting)
                    dependencies.append({"key": source["key"], "image_sha256": source["sha256"]})
        elif pipeline == "Costume-Dressing":
            source = (run.get("sources", {}).get(view) or {}).get("character_assembly")
            if source:
                self._collect_promotion_source(run, view, source, records, visiting)
                dependencies.append({"key": source["key"], "image_sha256": source["sha256"]})

        if pipeline in {"Body-Reference", "Head-Image", "Head-Image-Edit"} and view != "FRONT" and not prompt_pilot:
            front_id = str(run.get("front_anchor") or "")
            if not front_id or str((run.get("selected_views") or {}).get("FRONT") or "") != front_id:
                raise LocalCharacterAssetPipelineError(f"A selected FRONT {pipeline} anchor is required before promoting {view}.")
            self._collect_promotion_selection(run, pipeline, "FRONT", qualifier, records, visiting)
            front = next(item for item in run["candidates"] if item.get("candidate_id") == front_id)
            dependencies.append({"key": self.asset_store.key(pipeline, "FRONT", qualifier),
                                 "image_sha256": self._hash(Path(str(front["image_path"])))})

        if pipeline == "Head-Image-Edit" and not prompt_pilot:
            refs = (candidate.get("render_input") or {}).get("references") or (candidate.get("refinement") or {}).get("reference_inputs", [])
            for ref in refs:
                source_view = ref.get("view")
                if ref.get("candidate_id") and source_view and source_view != view:
                    source_candidate = next((c for c in run["candidates"] if c["candidate_id"] == (run.get("selected_views") or {}).get(source_view)), {})
                    source_image = Path(str(source_candidate.get("image_path") or ""))
                    if ((run.get("selected_views") or {}).get(source_view) != ref["candidate_id"] or not source_image.is_file()
                            or (source_candidate.get("human_review") or {}).get("decision") == "reject"
                            or (ref.get("sha256") and self._hash(source_image) != ref["sha256"])):
                        raise LocalCharacterAssetPipelineError("The head finishing guide selection changed; refine again before promotion.")
                    if source_view == "FRONT":
                        continue
                    self._collect_promotion_selection(run, pipeline, source_view, qualifier, records, visiting)
                    dependencies.append({"key": self.asset_store.key(pipeline, source_view), "image_sha256": ref.get("sha256", "")})

        if pipeline in {"Character-Assembly", "Costume-Dressing"} and view != "FRONT" and self._requires_front_anchor(run) and not prompt_pilot:
            front_id = str(run.get("front_anchor") or "")
            if not front_id:
                raise LocalCharacterAssetPipelineError(f"A selected FRONT {pipeline} anchor is required before promotion of {view}.")
            self._collect_promotion_selection(run, pipeline, "FRONT", qualifier, records, visiting)
            front = next(item for item in run["candidates"] if item.get("candidate_id") == front_id)
            front_hash = self._hash(Path(str(front["image_path"])))
            front_key = self.asset_store.key(pipeline, "FRONT", qualifier)
            dependencies.append({"key": front_key, "image_sha256": front_hash})

        key = self.asset_store.key(pipeline, view, qualifier)
        records[key] = {"pipeline": pipeline, "view": view, "qualifier": qualifier,
                        "candidate_id": candidate_id, "batch_id": run["run_id"],
                        "batch_name": self._batch_label(run),
                        "image_path": str(image), "image_sha256": digest, "dependencies": dependencies,
                        **({"prompt_generator": deepcopy(candidate["prompt_generator"])} if prompt_pilot else {})}
        visiting.remove(marker)

    def _collect_promotion_source(self, owner: dict[str, Any], view: str, source: dict[str, Any],
                                  records: dict[str, dict[str, Any]],
                                  visiting: set[tuple[str, str, str]]) -> None:
        key = str(source.get("key") or "")
        pipeline = str(source.get("pipeline") or "")
        if not pipeline:
            pipeline = {"body_reference": "Body-Reference", "head_image": "Head-Image",
                        "character_assembly": "Character-Assembly"}.get(key.split(":", 1)[0], "")
        if not pipeline:
            raise LocalCharacterAssetPipelineError(f"Cannot identify the source pipeline for {view}.")
        qualifier = str(source.get("qualifier") or "")
        digest = str(source.get("managed_checksum") or source.get("image_sha256") or source.get("sha256") or "")
        current = (owner.get("local_assets") or {}).get(key) or {}
        if current.get("locked") and current.get("image_sha256") == digest:
            return
        source_run_id = str(source.get("batch_id") or "")
        source_candidate_id = str(source.get("candidate_id") or "")
        if not source_run_id or not source_candidate_id:
            raise LocalCharacterAssetPipelineError(f"The {pipeline} source for {view} is no longer locked or selected in a source batch.")
        adapter = self._source_adapter(pipeline)
        source_run = adapter.detail(source_run_id)
        if str((source_run.get("selected_views") or {}).get(view) or "") != source_candidate_id:
            raise LocalCharacterAssetPipelineError(f"The {pipeline} source for {view} is no longer selected in its source batch.")
        if pipeline in {"Character-Assembly", "Costume-Dressing", "Body-Reference", "Head-Image", "Head-Image-Edit"}:
            self._collect_promotion_selection(source_run, pipeline, view, qualifier, records, visiting)
        else:
            candidate = next((item for item in source_run.get("candidates", [])
                              if item.get("candidate_id") == source_candidate_id), None)
            image = Path(str((candidate or {}).get("image_path") or "")).resolve()
            if not image.is_file():
                raise LocalCharacterAssetPipelineError(f"The selected {pipeline} image for {view} is missing or changed.")
            records[key] = {"pipeline": pipeline, "view": view, "qualifier": qualifier,
                            "candidate_id": source_candidate_id, "batch_id": source_run_id,
                            "batch_name": self._batch_label(source_run),
                            "image_path": str(image), "image_sha256": digest, "dependencies": []}

    def lock_preview(self, run_id: str, view: str, costume: str = "") -> dict[str, Any]:
        run = self.detail(run_id, costume)
        view = str(view or "").upper()
        if view not in VIEWS:
            raise LocalCharacterAssetPipelineError(f"Unknown view: {view}")
        records: dict[str, dict[str, Any]] = {}
        self._collect_promotion_selection(run, self.definition["asset_pipeline"], view,
                                          self._qualifier(costume), records, set())
        existing = run.get("local_assets") or {}
        changes = []
        for key, item in records.items():
            old = existing.get(key) or {}
            if old.get("locked") and old.get("image_sha256") == item["image_sha256"]:
                continue
            changes.append({"key": key, "pipeline": item["pipeline"], "view": item["view"],
                            "batch_name": item.get("batch_name", ""),
                            "replacing_batch": old.get("batch_name", "")})
        return {"run_id": run_id, "view": view, "changes": changes, "record_count": len(records)}

    def lock_selected_view(self, run_id: str, view: str, costume: str = "") -> dict[str, Any]:
        run = self.detail(run_id, costume)
        view = view.upper()
        self.lock_preview(run_id, view, costume)
        records: dict[str, dict[str, Any]] = {}
        self._collect_promotion_selection(run, self.definition["asset_pipeline"], view,
                                          self._qualifier(costume), records, set())
        return self.asset_store.promote_chain(run["character"], run["phase"], list(records.values()))[-1]

    def unlock_view(self, character: str, phase: str, view: str, costume: str = "") -> dict[str, Any]:
        return self.asset_store.unlock(character, phase, self.definition["asset_pipeline"], view.upper(), self._qualifier(costume))

    def update_candidate(self, run_id: str, candidate_id: str, payload: dict[str, Any], costume: str = "") -> dict[str, Any]:
        run = self.detail(run_id, costume)
        candidate = next((item for item in run["candidates"] if item["candidate_id"] == candidate_id), None)
        if not candidate:
            raise LocalCharacterAssetPipelineError(f"Unknown candidate: {candidate_id}")
        try:
            decision = normalize_human_decision(payload.get("decision"))
        except ValueError as exc:
            raise LocalCharacterAssetPipelineError(str(exc)) from exc
        if not Path(str(candidate.get("image_path") or "")).is_file():
            raise LocalCharacterAssetPipelineError("Candidate image must be complete before human review.")
        root = Path(run["root"])
        def apply(state: dict[str, Any]) -> None:
            state.setdefault("candidates", {}).setdefault(candidate_id, {}).update(
                human_review={"decision": decision},
                status=candidate.get("status"),
            )
            if (self.pipeline == "character-assembly" and decision == "reject"
                    and (state.get("selected_views") or {}).get("FRONT") == candidate_id):
                invalidate_assembly_rankings(state)
            state["updated_at"] = self._now()
        mutate_local_run_state(root, apply)
        return self.detail(run_id, costume)

    def retry_candidate(self, run_id: str, candidate_id: str, costume: str = "") -> dict[str, Any]:
        run = self.detail(run_id, costume)
        candidate = next((item for item in run["candidates"] if item["candidate_id"] == candidate_id), None)
        if not candidate:
            raise LocalCharacterAssetPipelineError(f"Unknown candidate: {candidate_id}")
        if self.pipeline == "character-assembly":
            guard_view(run, candidate["view"])
        if candidate["view"] != "FRONT" and self._requires_front_anchor(run) and not run.get("front_anchor"):
            raise LocalCharacterAssetPipelineError("Select a FRONT candidate before retrying other views.")
        self.asset_store.assert_batch_change_allowed(run["character"], run["phase"], self.definition["asset_pipeline"], candidate["view"], self._qualifier(costume))
        root, state = self._state(run_id, costume)
        from zet.services.local_image_evaluation_service import supersede_evaluations
        supersede_evaluations(state, {str(candidate["view"])}, "A candidate in this view is being retried.")
        self._write(root / "state.json", state)
        from zet.services.local_image_pipeline_policy import clear_candidate_artifacts
        root = Path(run["root"])
        clear_candidate_artifacts(root, candidate_id, candidate.get("image_path"))
        self._update(run_id, candidate_id, costume, status="PENDING", image_path="", ask_id="",
                     render_error="", review_error="",
                     retry_count=int(candidate.get("retry_count") or 0) + 1,
                     human_review={"decision": "undecided"})
        return self.detail(run_id, costume)

    def rerun_view(self, run_id: str, view: str, costume: str = "", *, refresh_sources: bool = True,
                   recompile: bool = False) -> dict[str, Any]:
        refresh_sources = refresh_sources or recompile
        run, view = self.detail(run_id, costume), view.upper()
        if self.pipeline == "character-assembly":
            guard_view(run, view)
        if view not in VIEWS:
            raise LocalCharacterAssetPipelineError(f"Unknown view: {view}")
        self.asset_store.assert_batch_change_allowed(run["character"], run["phase"], self.definition["asset_pipeline"], view, self._qualifier(costume))
        state = self._read(Path(run["root"]) / "state.json")
        if view == "FRONT" and not run.get("character_progression") and self._requires_front_anchor(run) and any(
            (state.get("selected_views") or {}).get(target) for target in VIEWS[1:]
        ):
            raise LocalCharacterAssetPipelineError("Clear or unlock downstream selections before rerunning FRONT.")
        if view != "FRONT" and self._requires_front_anchor(run) and not run.get("front_anchor"):
            raise LocalCharacterAssetPipelineError("Select a FRONT candidate before rerunning other views.")
        if refresh_sources:
            self._refresh_view_inputs(run, view)
        else:
            self._verify_snapshot_view(run, view)
        if recompile:
            self._refresh_costume_snapshot(run)
            self._compile(run, view, self._references(run, view))
        root, state = self._state(run_id, costume)
        from zet.services.local_image_evaluation_service import supersede_evaluations
        supersede_evaluations(state, {view}, "A view or its inputs are being re-run.")
        for candidate in [item for item in run["candidates"] if item["view"] == view]:
            from zet.services.local_image_pipeline_policy import clear_candidate_artifacts
            clear_candidate_artifacts(root, candidate["candidate_id"], candidate.get("image_path"))
            state.setdefault("candidates", {})[candidate["candidate_id"]] = {
                "status": "PENDING", "image_path": "", "ask_id": "",
                "human_review": {"decision": "undecided"},
                "retry_count": int(candidate.get("retry_count") or 0) + 1,
            }
        state.setdefault("rankings", {}).pop(view, None)
        selected_id = state.setdefault("selected_views", {}).pop(view, None)
        if selected_id:
            self.asset_store.clear_batch_selection(run["character"], run["phase"], self.definition["asset_pipeline"], view, run_id, self._qualifier(costume))
        if view == "FRONT":
            state["front_anchor"] = None
            state["views_started"] = False
            if self.pipeline == "character-assembly":
                invalidate_assembly_rankings(state)
        state.update(status="QUEUED", stop_requested=False)
        self._write(root / "state.json", state)
        return self.detail(run_id, costume)

    def rerun(self, run_id: str, costume: str = "", *, refresh_sources: bool = True,
              recompile: bool = False) -> dict[str, Any]:
        refresh_sources = refresh_sources or recompile
        run = self.detail(run_id, costume)
        for view in VIEWS:
            self.asset_store.assert_batch_change_allowed(run["character"], run["phase"], self.definition["asset_pipeline"], view, self._qualifier(costume))
        if refresh_sources:
            fresh_sources = {view: self._locked_view_inputs(run, view) for view in VIEWS}
            for view, sources in fresh_sources.items():
                for role, source in sources.items():
                    path = Path(str(source.get("image_path") or ""))
                    digest = str(source.get("managed_checksum") or source.get("image_sha256") or source.get("sha256") or "")
                    if not path.is_file():
                        raise LocalCharacterAssetPipelineError(f"Chosen {role.replace('_', ' ')} reference for {view} is missing or changed.")
        else:
            for view in VIEWS:
                if view in (run.get("sources") or {}):
                    self._verify_snapshot_view(run, view)
        if recompile:
            self._refresh_costume_snapshot(run)
            run = self.detail(run_id, costume)
        root, state = self._state(run_id, costume)
        from zet.services.local_image_evaluation_service import supersede_evaluations
        supersede_evaluations(state, set(VIEWS), "The run is being restarted.")
        if refresh_sources:
            for view, sources in fresh_sources.items():
                self._snapshot_view_inputs(run, view, sources)
        if recompile:
            run = self.detail(run_id, costume)
            views_to_compile = VIEWS if not self._requires_front_anchor(run) else ("FRONT",)
            for view in views_to_compile:
                self._compile(run, view, self._references(run, view))
        from zet.services.local_image_pipeline_policy import clear_candidate_artifacts
        for candidate in run["candidates"]:
            clear_candidate_artifacts(root, candidate["candidate_id"], candidate.get("image_path"))
        for view in VIEWS:
            selected = (state.get("selected_views") or {}).get(view)
            if selected:
                self.asset_store.clear_batch_selection(run["character"], run["phase"], self.definition["asset_pipeline"], view, run_id, self._qualifier(costume))
        state.update(status="QUEUED", stop_requested=False, front_anchor=None, views_started=False,
                     selected_views={}, rankings={},
                     candidates={item["candidate_id"]: {"status": "PENDING", "image_path": "", "ask_id": "",
                         "retry_count": int(item.get("retry_count") or 0) + 1,
                         "human_review": {"decision": "undecided"}} for item in run["candidates"]})
        self._write(root / "state.json", state)
        return self.detail(run_id, costume)

    @serialize_local_run_state
    def delete_run(self, run_id: str, costume: str = "") -> dict[str, Any]:
        run = self.detail(run_id, costume)
        if run.get("status") in {"RUNNING", "STOPPING", "REEVALUATING"} and not run.get("interrupted"):
            raise LocalCharacterAssetPipelineError("Stop the run and wait before deleting it.")
        for view in VIEWS:
            key = self.asset_store.key(self.definition["asset_pipeline"], view, self._qualifier(costume))
            record = run["local_assets"].get(key) or {}
            if record.get("selected") and record.get("batch_id") == run_id and record.get("locked"):
                raise LocalCharacterAssetPipelineError(f"Unlock {key} before deleting its batch.")
        for view in VIEWS:
            key = self.asset_store.key(self.definition["asset_pipeline"], view, self._qualifier(costume))
            record = run["local_assets"].get(key) or {}
            if record.get("selected") and record.get("batch_id") == run_id:
                self.asset_store.clear_selection(run["character"], run["phase"], self.definition["asset_pipeline"], view, self._qualifier(costume))
        self._withdraw_queued_asks(run_id, costume)
        root = Path(run["root"]).resolve()
        if not root.is_relative_to(self.root.resolve()) or root.name != run_id:
            raise LocalCharacterAssetPipelineError("Run path escaped its local workspace.")
        shutil.rmtree(root)
        return {"deleted": True, "run_id": run_id}

    @serialize_local_run_state
    def proceed(self, run_id: str, costume: str = "") -> dict[str, Any]:
        run = self.detail(run_id, costume)
        with self._active_lock:
            if self._is_active(run_id):
                raise LocalCharacterAssetPipelineError("Wait for active batch work to finish before running remaining images.")
        candidate_id = (run.get("selected_views") or {}).get("FRONT")
        requires_front_anchor = self.pipeline == "character-assembly" or self._requires_front_anchor(run)
        if self.pipeline == "character-assembly" and candidate_id and not assembly_front(run):
            raise LocalCharacterAssetPipelineError("Select an available FRONT image before running remaining views.")
        missing = [item for item in run["candidates"]
                   if not Path(str(item.get("image_path") or "")).is_file()]
        if requires_front_anchor and not candidate_id and not any(item["view"] == "FRONT" for item in missing):
            raise LocalCharacterAssetPipelineError("A FRONT selection is required for other views.")
        if candidate_id:
            anchor = next((item for item in run["candidates"] if item["candidate_id"] == candidate_id), None)
            if not anchor or not Path(str(anchor.get("image_path") or "")).is_file():
                raise LocalCharacterAssetPipelineError("The selected FRONT image is unavailable.")
            if run.get("front_anchor") != candidate_id:
                raise LocalCharacterAssetPipelineError("The selected FRONT candidate is not the current anchor.")
        if run.get("status") in ACTIVE_RUN_STATUSES:
            raise LocalCharacterAssetPipelineError("Wait for active batch work to finish before starting other views.")
        if run.get("status") == "READY_FOR_VIEWS" and run.get("target_views"):
            return {**run, "target_views": [], "blocked_views": {}}
        candidates_by_view = {
            view: [item for item in run["candidates"] if item["view"] == view]
            for view in VIEWS
        }
        target_views = set()
        blocked_views = {}
        for view, candidates in candidates_by_view.items():
            if not candidates or not any(not Path(str(item.get("image_path") or "")).is_file()
                                         for item in candidates):
                continue
            if view != "FRONT" and requires_front_anchor and not candidate_id:
                blocked_views[view] = "Select a FRONT candidate before generating other views."
                continue
            try:
                sources = (run.get("sources") or {}).get(view)
                if sources:
                    for role, record in sources.items():
                        path = Path(str(record.get("image_path") or ""))
                        if not path.is_file():
                            raise LocalCharacterAssetPipelineError(f"Recorded {role.replace('_', ' ')} input for {view} is missing or changed.")
                else:
                    self._refresh_view_inputs(run, view)
            except LocalCharacterAssetPipelineError as exc:
                blocked_views[view] = str(exc)
                continue
            target_views.add(view)
        state_root, state = self._state(run_id, costume)
        from zet.services.local_image_evaluation_service import supersede_evaluations
        from zet.services.local_image_pipeline_policy import clear_candidate_artifacts
        supersede_evaluations(state, {item["view"] for item in missing}, "Missing images are being retried.")
        self._withdraw_queued_asks(run_id, costume, candidate_ids={item["candidate_id"] for item in missing})
        missing_ids = {item["candidate_id"] for item in missing}
        for candidate in run["candidates"]:
            update = state.setdefault("candidates", {}).setdefault(candidate["candidate_id"], {})
            update.update(error="", render_error="", review_error="")
            if candidate["candidate_id"] in missing_ids:
                clear_candidate_artifacts(state_root, candidate["candidate_id"], candidate.get("image_path"))
                update.update(status="QUEUED" if candidate["view"] in target_views else "PENDING",
                              image_path="", ask_id="",
                              retry_count=int(candidate.get("retry_count") or 0) + 1,
                              human_review={"decision": "undecided"})
        state["front_anchor"] = candidate_id
        state.update(status="READY_FOR_VIEWS" if target_views else "AWAITING_HUMAN_SELECTION",
                     stop_requested=False, error="", target_candidate_ids=[])
        state["views_started"] = bool(target_views - {"FRONT"}) or bool(state.get("views_started"))
        state["target_views"] = [view for view in VIEWS if view in target_views]
        # Claim these views before returning so a second request cannot queue them twice.
        self._write(state_root / "state.json", state)
        return {**self.detail(run_id, costume), "target_views": [view for view in VIEWS if view in target_views],
                "blocked_views": blocked_views}

    def image_path(self, run_id: str, candidate_id: str, costume: str = "") -> Path:
        from zet.services.local_candidate_image_service import candidate_image_path
        try:
            return candidate_image_path(self._run_root(run_id, costume), candidate_id, self.library_root)
        except ValueError as exc:
            raise LocalCharacterAssetPipelineError("Candidate image is unavailable.") from exc

    def source_path(self, run_id: str, view: str, role: str, costume: str = "") -> Path:
        run = self.detail(run_id, costume)
        view, role = view.upper(), str(role or "")
        if view not in VIEWS:
            raise LocalCharacterAssetPipelineError(f"Unknown view: {view}")
        source = (run.get("sources", {}).get(view) or {}).get(role)
        if source:
            path = Path(str(source.get("image_path") or "")).resolve()
        elif role in {"front_assembly", "front_costume"}:
            expected_role = "front_costume" if self.pipeline == "costume-dressing" else "front_assembly"
            if role != expected_role:
                raise LocalCharacterAssetPipelineError(f"No {role} source is available for {view}.")
            anchor = next((item for item in run["candidates"] if item["candidate_id"] == run.get("front_anchor")), None)
            path = Path(str((anchor or {}).get("image_path") or "")).resolve()
        else:
            raise LocalCharacterAssetPipelineError(f"No {role} source is available for {view}.")
        if not path.is_file() or not path.is_relative_to(Path(run["root"]).resolve()):
            raise LocalCharacterAssetPipelineError(f"The {role} source for {view} is unavailable.")
        return path

    def image_prompt(self, run_id: str, view: str, costume: str = "") -> str:
        run = self.detail(run_id, costume)
        path = Path(run["root"]) / "prompts" / view.upper() / "Final_Image_Prompt.md"
        if not path.is_file():
            refs = self._references(run, view.upper())
            compiled = self._compile(run, view.upper(), refs)
            path = Path(compiled["final_prompt"])
        return path.read_text(encoding="utf-8")



    def request_stop(self, run_id: str, costume: str = "") -> dict[str, Any]:
        root, state = self._state(run_id, costume)
        from zet.services.local_image_evaluation_service import supersede_evaluations
        supersede_evaluations(state, set(state.get("evaluations") or {}), "The run was stopped.")
        state.update(status="CANCELLED", stop_requested=True)
        self._write(root / "state.json", state)
        self._withdraw_queued_asks(run_id, costume)
        return self.detail(run_id, costume)

    def _withdraw_queued_asks(self, run_id: str, costume: str = "", *,
                              candidate_ids: set[str] | None = None) -> None:
        run = self.detail(run_id, costume)
        paths = getattr(self.app, "ai_proxy_service", None)
        paths = getattr(paths, "ai_proxy_path_service", None)
        if paths is None:
            return
        ask_ids = set()
        for candidate in run.get("candidates", []):
            if candidate_ids is not None and candidate["candidate_id"] not in candidate_ids:
                continue
            if candidate.get("ask_id"):
                ask_ids.add(str(candidate["ask_id"]))
        if not ask_ids:
            return
        queue_root = Path(paths.config.base_ai_queue_path)
        for task in paths.task_paths("ask"):
            if task.name in ask_ids:
                supersede_task(queue_root, task, "The local character pipeline work was stopped, deleted, or retried.", state_root=self.app.ai_proxy_service.ai_proxy_path_service.lifecycle.storage_root)

    def resume(self, run_id: str, costume: str = "") -> dict[str, Any]:
        run = self.detail(run_id, costume)
        if run.get("status") == "CANCELLED" and run.get("created_by_autogenerate"):
            with self._active_lock:
                if self._is_active(run_id):
                    raise LocalCharacterAssetPipelineError("Wait for the stopped batch runner to finish before resuming.")
            root, state = self._state(run_id, costume)
            resume_cancelled_autogenerate_state(run, state, ready_status="AWAITING_HUMAN_SELECTION")
            self._write(root / "state.json", state)
            return self.detail(run_id, costume)
        if run.get("status") != "INTERRUPTED":
            raise LocalCharacterAssetPipelineError("Only an interrupted run can be resumed.")
        self._run_update(run_id, costume, stop_requested=False, status="QUEUED")
        return self.detail(run_id, costume)
