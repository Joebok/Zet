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
import subprocess
import tempfile
import threading
import time
from typing import Any
from uuid import uuid4

from Scripts.Run_Character_Assembly_Jobs import compile_character_assembly_job
from Scripts.Run_Costume_Dressing_Jobs import compile_costume_dressing_job
from zet.services.candidate_review_contract import ReviewGate
from zet.services.local_candidate_review_contract import (
    adjust_candidate_ranking, normalize_human_decision,
)
from zet.services.local_image_ranking_service import rank_images_with_luna
from zet.services.local_asset_store_service import LocalAssetStoreService
from zet.services.local_image_pipeline_policy import (
    ACTIVE_RUN_STATUSES, decorate_local_pipeline_detail, gate_result_is_current,
    local_image_pipeline_config,
    mutate_local_run_state, pipeline_page_config, resume_cancelled_autogenerate_state, serialize_local_run_state,
    upgrade_legacy_review_v1, view_candidate_id,
)
from zet.services.local_render_backend_service import LocalRenderBackendService
from zet.services.workflow_storage import file_lock, supersede_task


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
            "gate_key": "local-character-assembly", "preset": "comfyui-qwen-local-character-edit",
        },
        "costume-dressing": {
            "key": "costume-dressing", "label": "Local Costume-Dressing", "workspace": "Costume-Dressing",
            "asset_pipeline": "Costume-Dressing", "task": "costume-dressing", "qualifies": True,
            "gate_key": "local-costume-dressing", "preset": "comfyui-qwen-local-character-edit",
        },
    }

    GATES = {
        "character-assembly": (
            ReviewGate("framing", "Does the candidate preserve the full requested character framing without material cropping? Return TRUE only for a clear defect; otherwise FALSE."),
            ReviewGate("orientation", "Does the candidate clearly show the requested " + "{view}" + " view without mirroring? Return TRUE only for a clear defect; otherwise FALSE."),
            ReviewGate("body_preservation", "Compare Image 1, the Body-Reference, with Image 2, the assembled candidate. Is there a clear change to body proportions, pose, stance, or framing? Return TRUE only for a clear change; otherwise FALSE.", input_roles=("body_reference",)),
            ReviewGate("head_identity", "Compare Image 1, the Head-Image, with Image 2, the assembled candidate. Is there a clear mismatch in face, hair, species traits, or gaze? Return TRUE only for a clear mismatch; otherwise FALSE.", input_roles=("head_image",)),
        ),
        "costume-dressing": (
            ReviewGate("framing", "Does the candidate preserve the complete requested full-body framing? Return TRUE only for a clear defect; otherwise FALSE."),
            ReviewGate("orientation", "Does the candidate clearly preserve the requested " + "{view}" + " body and head orientation without mirroring? Return TRUE only for a clear defect; otherwise FALSE."),
            ReviewGate("costume_fidelity", "Does the candidate clearly omit or materially redesign specified costume pieces? Return TRUE only for a clear defect; otherwise FALSE."),
            ReviewGate("character_preservation", "Compare Image 1, the assembled character, with Image 2, the candidate. Is there a clear change to character identity, anatomy, pose, or body proportions? Return TRUE only for a clear defect; otherwise FALSE.", input_roles=("character_assembly",)),
        ),
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
        for path in self.root.glob(pattern):
            if (path / "spec.json").is_file():
                spec = self._read(path / "spec.json")
                if spec.get("kind") == self.pipeline and (not costume or spec.get("costume") == costume):
                    return path
        raise LocalCharacterAssetPipelineError(f"Local {self.definition['label']} run not found: {run_id}")

    @staticmethod
    def _read(path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise LocalCharacterAssetPipelineError(f"Could not read local pipeline state: {path}") from exc
        if not isinstance(value, dict):
            raise LocalCharacterAssetPipelineError(f"Invalid local pipeline state: {path}")
        return value

    @staticmethod
    def _write(path: Path, value: dict[str, Any]) -> None:
        from zet.services.atomic_file_service import write_json_atomic
        write_json_atomic(path, value)

    def _costume_path(self, character: str, phase: str, costume: str) -> Path:
        name = re.sub(r"[^A-Za-z0-9_-]+", "-", costume).strip("-") or "Costume"
        return self.character_root / character / phase / f"Costume_{name.replace('-', '_')}.md"

    def _locked(self, character: str, phase: str, pipeline: str, view: str, qualifier: str = "") -> dict[str, Any]:
        key = self.asset_store.key(pipeline, view, qualifier)
        record = self.asset_store.detail(character, phase)["assets"].get(key) or {}
        if not record.get("locked") or record.get("stale"):
            raise LocalCharacterAssetPipelineError(f"A current locked {pipeline} image is required for {view}.")
        path = Path(str(record.get("locked_image_path") or "")).resolve()
        if not path.is_file() or self._hash(path) != record.get("image_sha256"):
            raise LocalCharacterAssetPipelineError(f"The locked {pipeline} image for {view} is missing or changed.")
        return {**record, "key": key, "image_path": str(path)}

    def _requirements(self) -> tuple[tuple[str, str], ...]:
        source_pipeline = {
            "body_reference": "Body-Reference",
            "head_image": "Head-Image",
            "character_assembly": "Character-Assembly",
        }
        return tuple((role, source_pipeline[role])
                     for role in local_image_pipeline_config(self.pipeline).reference_roles
                     if role in source_pipeline)

    def _source_adapter(self, pipeline: str):
        if pipeline == "Body-Reference":
            from zet.services.local_body_reference_service import LocalBodyReferenceService
            return LocalBodyReferenceService(self.app, self.project_root)
        if pipeline == "Head-Image":
            from zet.services.local_head_image_service import LocalHeadImageService
            return LocalHeadImageService(self.app, self.project_root)
        return LocalCharacterAssetPipelineService(self.app, self.project_root, "character-assembly")

    @staticmethod
    def _batch_label(run: dict[str, Any]) -> str:
        name = str(run.get("batch_name") or "Unnamed batch").strip()
        created = str(run.get("created_at") or "")
        return f"{name} · {created.replace('T', ' ')}" if created else name

    def _source_batch_options(self, character: str, phase: str, costume: str) -> dict[str, list[dict[str, Any]]]:
        options: dict[str, list[dict[str, Any]]] = {}
        for role, pipeline in self._requirements():
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
                             source_batches: dict[str, str]) -> dict[str, dict[str, Any]]:
        result = {}
        for role, pipeline in self._requirements():
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
        front_count, other_count = int(payload.get("front_count") or 8), int(payload.get("other_count") or 4)
        total = front_count + 7 * other_count
        if front_count < 1 or other_count < 1 or total > 256:
            raise LocalCharacterAssetPipelineError("Candidate counts must be positive and the run cannot exceed 256 candidates.")
        inputs, blocking_reasons = {}, []
        source_batches = payload.get("source_batches") or {}
        if not isinstance(source_batches, dict):
            raise LocalCharacterAssetPipelineError("Source batch choices must be an object keyed by source role.")
        requested_views = ("FRONT",) if payload.get("front_only") else VIEWS
        for view in requested_views:
            resolved = {}
            try:
                resolved = self._resolve_view_inputs(character, phase, costume, view, source_batches)
            except LocalCharacterAssetPipelineError as exc:
                blocking_reasons.append(str(exc))
            if len(resolved) == len(self._requirements()):
                inputs[view] = resolved
        costume_path = self._costume_path(character, phase, costume) if costume else None
        if costume_path and not costume_path.is_file():
            blocking_reasons.append(f"Costume template not found: {costume_path}")
        return {"pipeline": self.pipeline, "pipeline_config": pipeline_page_config(self.pipeline),
                "character": character, "phase": phase, "costume": costume,
                "views": list(VIEWS), "front_count": front_count, "other_count": other_count,
                "candidate_count": total, "inputs": inputs, "front_only": bool(payload.get("front_only")),
                "use_front_anchor": bool(payload.get("use_front_anchor", True)),
                "front_anchor_required_for_other_views": bool(payload.get("use_front_anchor", True)),
                "source_batches": {role: str(source_batches.get(role) or "locked") for role, _ in self._requirements()},
                "source_batch_options": self._source_batch_options(character, phase, costume),
                "can_create": not blocking_reasons, "blocking_reasons": list(dict.fromkeys(blocking_reasons))}

    def _requires_front_anchor(self, run: dict[str, Any]) -> bool:
        return bool(run.get("use_front_anchor", True))

    def _snapshot_inputs(self, root: Path, plan: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], str]:
        snapshot = {}
        input_root = root / "inputs"
        for view, refs in plan["inputs"].items():
            snapshot[view] = {}
            for role, record in refs.items():
                source = Path(record["image_path"])
                expected_hash = str(record.get("sha256") or record.get("image_sha256") or "")
                if not source.is_file() or not expected_hash or self._hash(source) != expected_hash:
                    raise LocalCharacterAssetPipelineError(f"Selected {role.replace('_', ' ')} source for {view} changed after preview.")
                destination = input_root / view / f"{role}{source.suffix.lower()}"
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
                snapshot[view][role] = {**record, "image_path": str(destination), "sha256": self._hash(destination)}
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
        for view in VIEWS:
            for ordinal in range(1, (plan["front_count"] if view == "FRONT" else plan["other_count"]) + 1):
                index += 1
                candidates.append({"candidate_id": view_candidate_id(view, ordinal), "view": view, "ordinal": ordinal,
                                  "seed": seeds[index - 1], "status": "PENDING", "image_path": "",
                                  "gates": {}, "human_review": {"decision": "undecided"}, "retry_count": 0})
        spec = {"schema_version": 1, "review_version": 2, "kind": self.pipeline, "run_id": run_id,
                "universe_id": str(getattr(self.app.config, "universe_id", "Moonsea")),
                "created_at": self._now(), "status": "QUEUED", "character": plan["character"], "phase": plan["phase"],
                "costume": plan["costume"], "views": list(VIEWS), "front_count": plan["front_count"],
                "other_count": plan["other_count"], "candidate_count": count, "sources": sources,
                "source_batches": plan.get("source_batches") or {},
                "use_front_anchor": plan["use_front_anchor"],
                "costume_path": costume_path, "costume_sha256": self._hash(Path(costume_path)) if costume_path else "",
                "candidates": candidates, "front_anchor": None, "selected_views": {}, "rankings": {}}
        self._write(root / "spec.json", spec)
        self._write(root / "state.json", {"run_id": run_id, "status": "QUEUED", "updated_at": self._now(),
                                           "stop_requested": False, "front_anchor": None, "views_started": False,
                                           "candidates": {}, "selected_views": {}, "rankings": {}})
        return self.detail(run_id, plan["costume"])

    def detail(self, run_id: str, costume: str = "", *, upgrade_legacy: bool = False) -> dict[str, Any]:
        root = self._run_root(run_id, costume)
        spec, state = self._read(root / "spec.json"), self._read(root / "state.json")
        with self._active_lock:
            active = self._is_active(run_id)
        if upgrade_legacy and upgrade_legacy_review_v1(root, spec, state, active=active):
            spec, state = self._read(root / "spec.json"), self._read(root / "state.json")
        from zet.services.local_prompt_improvement_service import ensure_view_reviews
        spec, state = ensure_view_reviews(root, spec, state)
        candidates = {item["candidate_id"]: dict(item) for item in spec.get("candidates", [])}
        for cid, update in (state.get("candidates") or {}).items():
            if cid in candidates:
                candidates[cid].update(update)
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
        for candidate in result["candidates"]:
            candidate["image_filled"] = Path(str(candidate.get("image_path") or "")).is_file()
        if state.get("status") in ACTIVE_RUN_STATUSES:
            with self._active_lock:
                result["interrupted"] = not self._is_active(run_id)
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
                     or ranking.get("input_hashes", {}).get(candidate_id) != self._hash(image)
                     or not self._candidate_gates_current(result, candidate)
                     or bool(candidate.get("legacy_review_stale"))
                     or bool(local_asset.get("locked") and local_asset.get("candidate_id") != candidate_id))
            if stale:
                result["stale_selections"].append(view)
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
                        interrupted = not self._is_active(run_id)
                    if interrupted:
                        status = "INTERRUPTED"
                result.append({
                    "run_id": run_id, "batch_name": spec.get("batch_name", ""),
                    "character": spec.get("character", ""), "phase": spec.get("phase", ""),
                    "costume": spec.get("costume", ""), "created_at": spec.get("created_at", ""),
                    "status": status, "candidate_count": int(spec.get("candidate_count") or len(spec.get("candidates") or [])),
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
                                         view, run.get("source_batches") or {})

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
                source_hash = str(source.get("sha256") or source.get("image_sha256") or "")
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
                current_valid = (current_path.is_file() and current.get("image_sha256")
                                 and self._hash(current_path) == current.get("image_sha256"))
                if not current.get("locked") or current.get("stale") or not current_valid:
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
                                or self._hash(selected_path) != source_hash):
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
                            "image_sha256": self._hash(destination)}
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
            if not path.is_file() or not digest or self._hash(path) != digest:
                raise LocalCharacterAssetPipelineError(f"Chosen {role.replace('_', ' ')} reference for {view} is missing or changed.")
        return self._snapshot_view_inputs(run, view, source)

    def _verify_snapshot_view(self, run: dict[str, Any], view: str) -> dict[str, dict[str, Any]]:
        sources = (run.get("sources") or {}).get(view) or {}
        if len(sources) != len(self._requirements()):
            raise LocalCharacterAssetPipelineError(f"No complete original reference snapshot exists for {view}.")
        for role, record in sources.items():
            path = Path(str(record.get("image_path") or ""))
            if not path.is_file() or self._hash(path) != record.get("sha256"):
                raise LocalCharacterAssetPipelineError(f"Original {role.replace('_', ' ')} snapshot for {view} is missing or changed.")
        return sources

    def _references(self, run: dict[str, Any], view: str) -> list[dict[str, Any]]:
        inputs = run.get("sources", {}).get(view)
        if inputs is None:
            inputs = self._snapshot_view_inputs(run, view, self._locked_view_inputs(run, view))
        if self.pipeline == "character-assembly":
            roles = (("body_reference", "head_image") if view == "FRONT" or not self._requires_front_anchor(run)
                     else ("body_reference", "head_image", "front_assembly"))
        else:
            roles = ("character_assembly",) if view == "FRONT" or not self._requires_front_anchor(run) else ("character_assembly", "front_costume")
        refs = []
        for role in roles:
            if role in {"front_assembly", "front_costume"}:
                anchor = next((item for item in run["candidates"] if item["candidate_id"] == run.get("front_anchor")), None)
                path = Path(str((anchor or {}).get("image_path") or ""))
                if not anchor or not path.is_file():
                    raise LocalCharacterAssetPipelineError("Select a reviewed FRONT candidate before generating other views.")
                refs.append({"role": role, "path": str(path), "view": "FRONT", "character": run["character"], "phase": run["phase"]})
            else:
                source = inputs[role]
                refs.append({"role": role, "path": source["image_path"], "view": view,
                             "body_view": view, "head_view": view, "character": run["character"], "phase": run["phase"]})
        return refs

    def _compile(self, run: dict[str, Any], view: str, refs: list[dict[str, Any]]) -> dict[str, Any]:
        root = Path(run["root"])
        output = root / "prompts" / view
        template = self.character_root / run["character"] / run["phase"] / "Character.md"
        job = {"Job": f"Local_{self.pipeline}_{run['run_id']}_{view}", "Task": self.definition["task"],
               "Character": run["character"], "Phase": run["phase"], "Output Directory": str(output),
               "Template Path": str(template), "Reference Files": refs}
        if self.pipeline == "character-assembly":
            job.update({"Body View": view, "Head View": view,
                        "use_front_anchor": self._requires_front_anchor(run)})
            result = compile_character_assembly_job(
                job, self.project_root, pipeline_mode="local",
                universe_root=self.app.config.base_library_path,
            )
        else:
            job.update({"Body View": view, "Head View": view, "Costume": run["costume"],
                        "Costume Path": run["costume_path"]})
            result = compile_costume_dressing_job(
                job, self.project_root, pipeline_mode="local",
                universe_root=self.app.config.base_library_path,
            )
        from zet.services.local_prompt_improvement_service import record_compiler_sources
        record_compiler_sources(output)
        return result

    def queue_render_candidate(self, run_id: str, candidate_id: str, costume: str = "") -> dict[str, Any]:
        run = self.detail(run_id, costume)
        candidate = next((item for item in run["candidates"] if item["candidate_id"] == candidate_id), None)
        if not candidate:
            raise LocalCharacterAssetPipelineError(f"Unknown candidate: {candidate_id}")
        if candidate["view"] != "FRONT" and self._requires_front_anchor(run) and not run.get("front_anchor"):
            raise LocalCharacterAssetPipelineError("Select a FRONT candidate before generating other views.")
        refs = self._references(run, candidate["view"])
        compiled = self._compile(run, candidate["view"], refs)
        root = Path(run["root"])
        candidate_root = root / "renders" / candidate_id
        render_root = candidate_root / "Local_Test_Renders"
        target = render_root / f"{self.pipeline.replace('-', '')}_{candidate_id}_{candidate.get('retry_count', 0)}.png"
        prompt_path = Path(compiled["final_prompt"])
        prompt_copy = candidate_root / "Qwen_Local_Character_Prompt.md"
        prompt_copy.parent.mkdir(parents=True, exist_ok=True)
        prompt_copy.write_text("Positive Prompt:\n" + prompt_path.read_text(encoding="utf-8") + "\n\nNegative Prompt:\n", encoding="utf-8")
        preset_name = self.definition["preset"]
        profile = LocalRenderBackendService(self.project_root / "Config" / "Local_Render_Presets.json").preset(preset_name)
        ask_id = f"LocalCharacterAsset_{run_id}_{candidate_id}_{candidate.get('retry_count', 0)}"
        manifest = {"ask_id": ask_id, "character": run["character"], "phase": run["phase"],
                    "pipeline": f"Local-{self.definition['label'].removeprefix('Local ')}", "pipeline_stage": "LOCAL_CHARACTER_RENDER"}
        render_references = compiled.get("reference_files") or refs
        ask_path = self.app.ai_proxy_service.stage_render_task_local_render_ask(
            manifest, prompt_copy, candidate_root, allow_parallel=True, seed=int(candidate["seed"]),
            checkpoint=str(profile.get("diffusion_model") or ""), render_preset=preset_name,
            image_generation="comfyui", reference_files=render_references,
        )
        ask = self._read(ask_path / "ask_manifest.json")
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
        paths = self.app.ai_proxy_service.ai_proxy_path_service
        receipt = paths.lifecycle.read_receipt(ask_id)
        if receipt:
            return "HARVESTED", {"ask_id": ask_id, "status": receipt.get("answer_status", receipt.get("status", "")),
                                  "error_message": receipt.get("error_message", "")}
        for status, folder in (("QUEUED", paths.ask_root()), ("RUNNING", paths.running_root()), ("ANSWERED", paths.answer_root())):
            path = folder / ask_id
            if path.is_dir():
                try:
                    return status, self._read(path / "answer_manifest.json")
                except LocalCharacterAssetPipelineError:
                    return status, {}
        return "UNKNOWN", {}

    def _harvest_render(self, run: dict[str, Any], candidate: dict[str, Any]) -> None:
        paths = self.app.ai_proxy_service.ai_proxy_path_service
        ask_id = str(candidate.get("ask_id") or "")
        answer_dir = paths.answer_root() / ask_id
        if not answer_dir.is_dir() or not (answer_dir / "answer_manifest.json").is_file():
            return
        ask, answer = self._read(answer_dir / "ask_manifest.json"), self._read(answer_dir / "answer_manifest.json")
        expected_pipeline = f"Local-{self.definition['label'].removeprefix('Local ')}"
        if (ask.get("ask_id") != ask_id or answer.get("ask_id") != ask_id
                or ask.get("pipeline") != expected_pipeline or not self._ask_belongs_to_run(ask, run)):
            raise LocalCharacterAssetPipelineError("AI Proxy answer does not belong to this candidate.")
        if answer.get("status") in {"ERROR", "RETRY_LATER"}:
            raise LocalCharacterAssetPipelineError(str(answer.get("error_message") or "Local render failed."))
        if answer.get("status") != "SUCCESS" or Path(str(answer.get("expected_output") or "")).name != answer.get("expected_output"):
            return
        source = answer_dir / str(answer["expected_output"])
        target = Path(str(candidate.get("image_path") or ""))
        if not source.is_file() or not target.resolve().is_relative_to(Path(run["root"]).resolve()):
            raise LocalCharacterAssetPipelineError("AI Proxy returned an invalid candidate image.")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
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
        candidate = next(item for item in self.detail(run_id, costume)["candidates"] if item["candidate_id"] == candidate_id)
        target = Path(str(candidate.get("image_path") or ""))
        deadline = time.monotonic() + 1860
        while not target.is_file():
            run = self.detail(run_id, costume)
            if run.get("stop_requested"):
                return False
            self._harvest_render(run, candidate)
            if target.is_file():
                break
            _, answer = self._proxy_answer(str(candidate.get("ask_id") or ""))
            if answer.get("status") in {"ERROR", "RETRY_LATER"}:
                raise LocalCharacterAssetPipelineError(str(answer.get("error_message") or "Local render failed."))
            if time.monotonic() >= deadline:
                raise LocalCharacterAssetPipelineError("Timed out waiting for the local render.")
            time.sleep(max(.5, float(self.app.config.comfyui_poll_seconds)))
        self._update(run_id, candidate_id, costume, status="WAITING_FOR_GATES", image_sha256=self._hash(target), rendered_at=self._now())
        return True

    @classmethod
    def review_gates(cls, pipeline: str, view: str) -> list[ReviewGate]:
        if pipeline not in cls.GATES or view not in VIEWS:
            raise LocalCharacterAssetPipelineError("Unknown pipeline or view.")
        return [ReviewGate(gate.key, gate.prompt.format(view=VIEW_LABELS[view]), gate.uses_anchor,
                           gate.crop_head, gate.uses_source, gate.input_roles) for gate in cls.GATES[pipeline]]

    def _gate_policy(self, gate: str) -> str:
        from zet.services.local_gate_registry_service import LocalGateRegistryService
        return LocalGateRegistryService(self.app, self.project_root).status(self.definition["gate_key"], gate)

    def _candidate_gates_current(self, run: dict[str, Any], candidate: dict[str, Any]) -> bool:
        image = Path(str(candidate.get("image_path") or ""))
        if not image.is_file():
            return False
        for source in (run.get("sources", {}).get(candidate["view"]) or {}).values():
            source_path = Path(str(source.get("image_path") or ""))
            if not source_path.is_file() or self._hash(source_path) != source.get("sha256"):
                return False
        if self.pipeline == "costume-dressing":
            costume_path = Path(str(run.get("costume_path") or ""))
            if (not costume_path.is_file() or not run.get("costume_sha256")
                    or self._hash(costume_path) != run["costume_sha256"]):
                return False
        expected = {"candidate": self._hash(image)}
        if candidate["view"] != "FRONT" and self._requires_front_anchor(run):
            anchor = next((item for item in run["candidates"] if item["candidate_id"] == run.get("front_anchor")), None)
            anchor_path = Path(str((anchor or {}).get("image_path") or ""))
            if not anchor_path.is_file():
                return False
            anchor_role = "front_costume" if self.pipeline == "costume-dressing" else "front_assembly"
            expected[anchor_role] = self._hash(anchor_path)
        for gate in self.review_gates(self.pipeline, candidate["view"]):
            saved = (candidate.get("gates") or {}).get(gate.key) or {}
            input_hashes = dict(expected)
            for role in gate.input_roles:
                input_hashes[role] = run["sources"][candidate["view"]][role]["sha256"]
            prompt_hash = hashlib.sha256(gate.prompt.encode()).hexdigest()
            if not gate_result_is_current(saved, input_hashes=input_hashes, prompt_sha256=prompt_hash,
                                          policy_status=self._gate_policy(gate.key)):
                return False
        return True

    def _stage_candidate_gates(self, run_id: str, candidate_id: str, costume: str = "") -> bool:
        run = self.detail(run_id, costume)
        candidate = next((item for item in run["candidates"] if item["candidate_id"] == candidate_id), None)
        image = Path(str((candidate or {}).get("image_path") or ""))
        if not candidate or not image.is_file():
            raise LocalCharacterAssetPipelineError("Candidate image is missing.")
        gates = dict(candidate.get("gates") or {})
        for definition in self.review_gates(self.pipeline, candidate["view"]):
            policy = self._gate_policy(definition.key)
            hashes = {"candidate": self._hash(image)}
            for role in definition.input_roles:
                hashes[role] = run["sources"][candidate["view"]][role]["sha256"]
            if candidate["view"] != "FRONT" and self._requires_front_anchor(run):
                anchor = next(item for item in run["candidates"] if item["candidate_id"] == run["front_anchor"])
                anchor_role = "front_costume" if self.pipeline == "costume-dressing" else "front_assembly"
                hashes[anchor_role] = self._hash(Path(anchor["image_path"]))
            prompt_hash = hashlib.sha256(definition.prompt.encode()).hexdigest()
            if policy == "Disabled":
                gates[definition.key] = {"status": "DISABLED", "policy_status": policy,
                                         "input_hashes": hashes, "prompt_sha256": prompt_hash, "completed_at": self._now()}
                self._update(run_id, candidate_id, costume, gates=gates)
                continue
            if (record.get("status") == "COMPLETE" and record.get("policy_status") == policy
                    and record.get("input_hashes") == hashes and record.get("prompt_sha256") == prompt_hash):
                record["evaluation_id"] = str((run.get("evaluations") or {}).get(candidate["view"], {}).get("evaluation_id") or "")
                gates[definition.key] = record
                self._update(run_id, candidate_id, costume, gates=gates)
                continue
            if (record.get("status") in {"QUEUED", "RUNNING"} and record.get("policy_status") == policy
                    and record.get("input_hashes") == hashes and record.get("prompt_sha256") == prompt_hash):
                record["evaluation_id"] = str((run.get("evaluations") or {}).get(candidate["view"], {}).get("evaluation_id") or "")
                gates[definition.key] = record
                self._update(run_id, candidate_id, costume, gates=gates)
                continue
            try:
                record = self._queue_gate(run, candidate, definition, hashes)
                record.update(policy_status=policy, prompt_sha256=prompt_hash,
                              evaluation_id=str((run.get("evaluations") or {}).get(candidate["view"], {}).get("evaluation_id") or ""))
                gates[definition.key] = record
                self._update(run_id, candidate_id, costume, status="WAITING_FOR_GATES", gates=gates)
            except Exception as exc:
                gates[definition.key] = {"status": "FAILED", "policy_status": policy, "input_hashes": hashes,
                                         "prompt_sha256": prompt_hash, "error": str(exc)}
                self._update(run_id, candidate_id, costume, gates=gates)
        return True

    def _collect_candidate_gates(self, run_id: str, candidate_id: str, costume: str = "",
                                 evaluation_id: str = "") -> bool:
        run = self.detail(run_id, costume)
        candidate = next((item for item in run["candidates"] if item["candidate_id"] == candidate_id), None)
        if not candidate:
            return False
        if evaluation_id:
            evaluation = (run.get("evaluations") or {}).get(str(candidate.get("view") or ""), {})
            if evaluation.get("evaluation_id") != evaluation_id or evaluation.get("status") not in {"RUNNING", "STAGING"}:
                return False
            image = Path(str(candidate.get("image_path") or ""))
            if not image.is_file() or evaluation.get("input_hashes", {}).get(candidate_id) != self._hash(image):
                return False
        gates = dict(candidate.get("gates") or {})
        for definition in self.review_gates(self.pipeline, candidate["view"]):
            record = dict(gates.get(definition.key) or {})
            if record.get("status") in {"COMPLETE", "DISABLED", "FAILED"} or not record.get("ask_id"):
                continue
            if self.detail(run_id, costume).get("stop_requested"):
                return False
            try:
                verdict, reason = self._wait_gate(run_id, candidate_id, definition.key, costume)
                record.update(status="COMPLETE", verdict=verdict, reason=reason, completed_at=self._now())
            except Exception as exc:
                record.update(status="FAILED", error=str(exc), failed_at=self._now())
            if evaluation_id:
                latest_run = self.detail(run_id, costume)
                active = (latest_run.get("evaluations") or {}).get(candidate["view"], {})
                if active.get("evaluation_id") != evaluation_id or active.get("status") not in {"RUNNING", "STAGING"}:
                    return False
                latest_candidate = next(item for item in latest_run["candidates"] if item["candidate_id"] == candidate_id)
                gates = dict(latest_candidate.get("gates") or {})
            gates[definition.key] = record
            self._update(run_id, candidate_id, costume, gates=gates)
        if evaluation_id:
            latest_run = self.detail(run_id, costume)
            active = (latest_run.get("evaluations") or {}).get(candidate["view"], {})
            if active.get("evaluation_id") != evaluation_id or active.get("status") not in {"RUNNING", "STAGING"}:
                return False
        latest = next(item for item in self.detail(run_id, costume)["candidates"] if item["candidate_id"] == candidate_id)
        rejection = next((gate.key for gate in self.review_gates(self.pipeline, candidate["view"])
                          if (latest.get("gates") or {}).get(gate.key, {}).get("verdict") == "TRUE"
                          and (latest.get("gates") or {}).get(gate.key, {}).get("policy_status") == "Active"), "")
        self._update(run_id, candidate_id, costume,
                     status="GATE_REJECTED" if rejection else "WAITING_FOR_HUMAN_REVIEW",
                     rejection_gate=rejection, review_error="")
        return True

    def run_candidate_gates(self, run_id: str, candidate_id: str, costume: str = "") -> bool:
        """Synchronous compatibility entry point; queue the full gate set first."""
        self._stage_candidate_gates(run_id, candidate_id, costume)
        return self._collect_candidate_gates(run_id, candidate_id, costume)

    def stage_view_evaluation(self, run_id: str, view: str, costume: str = "", *,
                              candidate_ids: set[str] | None = None) -> dict[str, Any]:
        from zet.services.local_image_evaluation_service import local_image_evaluation_service
        view = str(view or "").upper()
        run = self.detail(run_id, costume)
        candidates = [item for item in run.get("candidates") or [] if item.get("view") == view
                      and (candidate_ids is None or item["candidate_id"] in candidate_ids)
                      and Path(str(item.get("image_path") or "")).is_file()]
        evaluation_id = uuid4().hex
        hashes = {item["candidate_id"]: self._hash(Path(item["image_path"])) for item in candidates}
        previous = (run.get("evaluations") or {}).get(view) or {}
        if previous.get("status") in {"STAGING", "RUNNING"} and previous.get("input_hashes") == hashes:
            self.reconcile_review_jobs(run_id, costume)
            return previous
        from zet.services.local_image_evaluation_service import update_view_evaluation
        update_view_evaluation(self._run_root(run_id, costume), view, {
            "evaluation_id": evaluation_id, "status": "STAGING", "input_hashes": hashes,
            "started_at": self._now(),
        })

        def stage() -> None:
            for item in candidates:
                if self.detail(run_id, costume).get("stop_requested"):
                    return
                try:
                    self._stage_candidate_gates(run_id, item["candidate_id"], costume)
                except Exception as exc:
                    self._update(run_id, item["candidate_id"], costume, review_error=str(exc))

        def collect() -> None:
            current = self.detail(run_id, costume)
            if (current.get("evaluations") or {}).get(view, {}).get("evaluation_id") == evaluation_id and \
                    current["evaluations"][view].get("gates_status") == "COMPLETE":
                return
            for item in candidates:
                if self.detail(run_id, costume).get("stop_requested"):
                    return
                self._collect_candidate_gates(run_id, item["candidate_id"], costume, evaluation_id)
            current = self.detail(run_id, costume)
            if (current.get("evaluations") or {}).get(view, {}).get("evaluation_id") == evaluation_id:
                evaluation = dict(current["evaluations"][view])
                evaluation["status"] = "COMPLETE" if evaluation.get("ranking_status") in {"COMPLETE", "FAILED", "EMPTY"} else "RUNNING"
                update_view_evaluation(self._run_root(run_id, costume), view,
                    {**evaluation, "gates_status": "COMPLETE", "updated_at": self._now()},
                    evaluation_id=evaluation_id)

        def rank() -> None:
            if self.detail(run_id, costume).get("stop_requested"):
                return
            current = self.detail(run_id, costume)
            evaluation = (current.get("evaluations") or {}).get(view) or {}
            if evaluation.get("evaluation_id") == evaluation_id and evaluation.get("ranking_status") in {"COMPLETE", "FAILED", "EMPTY"}:
                return
            self.rank_view(run_id, view, costume, evaluation_id=evaluation_id)
            current = self.detail(run_id, costume)
            evaluation = dict((current.get("evaluations") or {}).get(view) or {})
            if evaluation.get("evaluation_id") == evaluation_id and evaluation.get("gates_status") == "COMPLETE":
                evaluation["status"] = "COMPLETE"
                update_view_evaluation(self._run_root(run_id, costume), view, evaluation, evaluation_id=evaluation_id)

        service = local_image_evaluation_service()
        return service.stage_view_evaluation(run_id, view, evaluation_id, stage_gates=stage,
            collect_gates=collect, rank=rank,
            save_evaluation=lambda record: update_view_evaluation(self._run_root(run_id, costume), view, record,
                evaluation_id=evaluation_id), input_hashes=hashes)

    def reconcile_review_jobs(self, run_id: str, costume: str = "") -> dict[str, Any]:
        from zet.services.local_image_evaluation_service import local_image_evaluation_service
        run = self.detail(run_id, costume)
        for view, evaluation in (run.get("evaluations") or {}).items():
            if evaluation.get("status") not in {"RUNNING", "STAGING"}:
                continue
            evaluation_id = str(evaluation.get("evaluation_id") or "")
            if not evaluation_id:
                continue
            candidates = [item for item in run.get("candidates") or [] if item.get("view") == view
                          and item["candidate_id"] in (evaluation.get("input_hashes") or {})]
            local_image_evaluation_service().reconcile_review_jobs(run_id, view, evaluation_id,
                stage_gates=lambda: [self._stage_candidate_gates(run_id, item["candidate_id"], costume)
                                     for item in candidates],
                collect_gates=lambda: [self._collect_candidate_gates(run_id, item["candidate_id"], costume, evaluation_id)
                                       for item in candidates],
                rank=lambda: self.rank_view(run_id, view, costume, evaluation_id=evaluation_id))
        return self.detail(run_id, costume)

    def _queue_gate(self, run: dict[str, Any], candidate: dict[str, Any], gate: ReviewGate,
                    hashes: dict[str, str]) -> dict[str, Any]:
        root = Path(run["root"])
        candidate_path = Path(candidate["image_path"])
        images = []
        for role in gate.input_roles:
            images.append((f"{role}.png", Path(run["sources"][candidate["view"]][role]["image_path"])))
        images.append(("candidate.png", candidate_path))
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        output = root / "analyses" / candidate["candidate_id"] / f"gate_{gate.key}_{timestamp}.txt"
        ask_id = f"Ask_LocalCharacterAsset_{run['run_id']}_{candidate['candidate_id']}_{gate.key}_{timestamp}"
        proxy = self.app.ai_proxy_service.ai_proxy_path_service.file_proxy_client
        staging = proxy.create_staging(ask_id)
        for name, path in images:
            shutil.copy2(path, staging / name)
        (staging / "OLLAMA_PROMPT.md").write_text(gate.prompt, encoding="utf-8")
        manifest = {"version": 1, "ask_id": ask_id, "character": run["character"], "phase": run["phase"],
                    "universe_id": str(run.get("universe_id") or getattr(self.app.config, "universe_id", "Moonsea")),
                    "pipeline": f"Local-{self.definition['label'].removeprefix('Local ')}",
                    "pipeline_stage": f"LOCAL_{self.pipeline.upper().replace('-', '_')}_{gate.key.upper()}_GATE",
                    "worker_type": "ollama_generate", "ollama_model": str(getattr(self.app.config, "local_body_reference_face_gate_model", "image-analysis-alt:latest")),
                    "ollama_think": False, "prompt_file": "OLLAMA_PROMPT.md", "image_files": [name for name, _ in images],
                    "json_output": False, "expected_output": output.name, "task_type": "local_character_asset_gate",
                    "auxiliary": True, "target_output_dir": str(output.parent), "target_output_file": output.name,
                    "local_character_asset_run_id": run["run_id"], "candidate_id": candidate["candidate_id"],
                    "gate": gate.key, "input_hashes": hashes, "prompt_sha256": hashlib.sha256(gate.prompt.encode()).hexdigest()}
        (staging / "ask_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        proxy.publish(staging, ask_id, "ollama_generate")
        return {"status": "QUEUED", "ask_id": ask_id, "output_path": str(output), "input_hashes": hashes,
                "prompt_sha256": manifest["prompt_sha256"], "policy_status": self._gate_policy(gate.key)}

    def _wait_gate(self, run_id: str, candidate_id: str, gate: str, costume: str = "") -> tuple[str, str]:
        candidate = next(item for item in self.detail(run_id, costume)["candidates"] if item["candidate_id"] == candidate_id)
        record = dict((candidate.get("gates") or {}).get(gate) or {})
        output = Path(record["output_path"])
        deadline = time.monotonic() + 1800
        while not output.is_file():
            if self.detail(run_id, costume).get("stop_requested"):
                raise LocalCharacterAssetPipelineError("Review stopped by user.")
            folder = self.app.ai_proxy_service.ai_proxy_path_service.answer_root() / str(record.get("ask_id") or "")
            if folder.is_dir() and (folder / "answer_manifest.json").is_file():
                ask = self._read(folder / "ask_manifest.json")
                answer = self._read(folder / "answer_manifest.json")
                if (ask.get("ask_id") != record.get("ask_id") or answer.get("ask_id") != record.get("ask_id")
                        or not self._ask_belongs_to_run(ask, run)
                        or ask.get("local_character_asset_run_id") != run_id
                        or ask.get("candidate_id") != candidate_id or ask.get("task_type") != "local_character_asset_gate"):
                    raise LocalCharacterAssetPipelineError("AI Proxy gate answer does not match this local candidate.")
                if answer.get("status") in {"ERROR", "RETRY_LATER"}:
                    raise LocalCharacterAssetPipelineError(str(answer.get("error_message") or "Gate failed."))
                if answer.get("status") == "SUCCESS":
                    expected_name = str(ask.get("target_output_file") or "")
                    source_name = str(answer.get("expected_output") or "")
                    source = folder / source_name
                    expected_output = Path(str(record.get("output_path") or "")).resolve()
                    if expected_output != (Path(self.detail(run_id, costume)["root"]) / "analyses" / candidate_id / expected_name).resolve():
                        raise LocalCharacterAssetPipelineError("AI Proxy gate output path does not match its local candidate.")
                    if source.is_file() and Path(source_name).name == source_name and source_name == expected_name:
                        output.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(source, output)
            if output.is_file():
                break
            if time.monotonic() >= deadline:
                raise LocalCharacterAssetPipelineError(f"Timed out waiting for the {gate} gate.")
            time.sleep(1)
        answer = output.read_text(encoding="utf-8").strip()
        match = re.fullmatch(r"(TRUE|FALSE)(?::\s*(.*))?", answer, re.IGNORECASE)
        if not match:
            raise LocalCharacterAssetPipelineError(f"{gate} gate returned an invalid verdict.")
        return match.group(1).upper(), (match.group(2) or "").strip()

    def execute_run(self, run_id: str, *, views: set[str] | None = None, costume: str = "",
                    candidate_ids: set[str] | None = None, render_only: bool = False) -> None:
        root = self._run_root(run_id, costume)
        try:
            with file_lock(root / "runner.lock", timeout=0):
                with self._active_lock:
                    self._active.add(self._active_key(run_id))
                run = self.detail(run_id, costume)
                if views is None:
                    views = set(VIEWS) if run.get("front_anchor") or not self._requires_front_anchor(run) else {"FRONT"}
                if any(view != "FRONT" for view in views) and self._requires_front_anchor(run) and not run.get("front_anchor"):
                    self._run_update(run_id, costume, status="AWAITING_FRONT_ANCHOR",
                                     error="Select a FRONT candidate before generating other views.")
                    return
                self._run_update(run_id, costume, status="RUNNING", error="")
                for view in [item for item in VIEWS if item in views]:
                    pending = [item for item in self.detail(run_id, costume)["candidates"] if item["view"] == view
                               and (candidate_ids is None or item["candidate_id"] in candidate_ids)
                               and not Path(str(item.get("image_path") or "")).is_file()]
                    for item in pending:
                        if self.detail(run_id, costume).get("stop_requested"):
                            break
                        current = next(x for x in self.detail(run_id, costume)["candidates"] if x["candidate_id"] == item["candidate_id"])
                        if Path(str(current.get("image_path") or "")).is_file():
                            continue
                        try:
                            ask_id = str(current.get("ask_id") or "")
                            queue_status, _ = self._proxy_answer(ask_id) if ask_id else ("UNKNOWN", {})
                            if queue_status in {"QUEUED", "RUNNING", "ANSWERED"}:
                                self._update(run_id, item["candidate_id"], costume,
                                             status="QUEUED" if queue_status == "QUEUED" else "RUNNING")
                                continue
                            if current.get("ask_id") or current.get("status") == "RUNNING":
                                self.retry_candidate(run_id, item["candidate_id"], costume)
                            self.queue_render_candidate(run_id, item["candidate_id"], costume)
                            self._update(run_id, item["candidate_id"], costume, status="RUNNING")
                        except Exception as exc:
                            self._update(run_id, item["candidate_id"], costume, status="FAILED", render_error=str(exc))
                    for item in pending:
                        if self.detail(run_id, costume).get("stop_requested"):
                            break
                        current = next(x for x in self.detail(run_id, costume)["candidates"] if x["candidate_id"] == item["candidate_id"])
                        if not Path(str(current.get("image_path") or "")).is_file() and current.get("status") in {"QUEUED", "RUNNING"}:
                            try:
                                self._wait_render(run_id, item["candidate_id"], costume)
                            except Exception as exc:
                                self._update(run_id, item["candidate_id"], costume, status="FAILED", render_error=str(exc))
                    if not render_only and not self.detail(run_id, costume).get("stop_requested"):
                        pending = [item for item in self.detail(run_id, costume)["candidates"] if item["view"] == view
                                   and (candidate_ids is None or item["candidate_id"] in candidate_ids)
                                   and Path(str(item.get("image_path") or "")).is_file()]
                        if pending and not self.detail(run_id, costume).get("stop_requested"):
                            self.stage_view_evaluation(run_id, view, costume,
                                candidate_ids={item["candidate_id"] for item in pending})
                latest = self.detail(run_id, costume)
                selected = latest.get("selected_views") or {}
                complete = all(selected.get(view) for view in VIEWS)
                status = "CANCELLED" if latest.get("stop_requested") else "COMPLETE" if complete else "AWAITING_FRONT_ANCHOR" if self._requires_front_anchor(latest) and not latest.get("front_anchor") else "AWAITING_HUMAN_SELECTION"
                self._run_update(run_id, costume, status=status, target_views=[])
        except TimeoutError:
            return
        except Exception as exc:
            self._run_update(run_id, costume, status="ERROR", error=str(exc), target_views=[])
        finally:
            with self._active_lock:
                self._active.discard(self._active_key(run_id))

    def _rank(self, run: dict[str, Any], view: str) -> dict[str, Any]:
        survivors = [item for item in run["candidates"] if item["view"] == view
                     and Path(str(item.get("image_path") or "")).is_file()]
        hashes = {item["candidate_id"]: self._hash(Path(item["image_path"])) for item in survivors}
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
                      "Gates and human reviews are independent advice; assess every image on its visual merits. "
                      "Compare view accuracy, source preservation, identity, and usefulness as a reference. "
                      "Candidate IDs: " + ", ".join(hashes))
            reference_image_paths = []
            if view != "FRONT" and self._requires_front_anchor(run):
                anchor = next(item for item in run["candidates"] if item["candidate_id"] == run["front_anchor"])
                guide = "costume appearance" if self.pipeline == "costume-dressing" else "assembled-character proportion and appearance"
                prompt += f". The first image is the selected FRONT {guide} guide; rank candidates for consistency with it."
                reference_image_paths.append(str(anchor["image_path"]))
            image_paths = [str(item["image_path"]) for item in survivors]
            try:
                executable = shutil.which("codex") or "codex"
                entries, model = rank_images_with_luna(
                    project_root=self.project_root,
                    model=str(getattr(self.app.config, "codex_default_model", "gpt-6-luna")),
                    prompt=prompt,
                    candidate_ids=list(hashes),
                    image_paths=image_paths,
                    executable=executable,
                    reference_image_paths=reference_image_paths,
                    runner=subprocess.run,
                )
            except Exception as exc:
                raise LocalCharacterAssetPipelineError(str(exc)) from exc
            ranking = {"status": "COMPLETE", "ordered_candidate_ids": [entry["candidate_id"] for entry in entries],
                       "luna_ordered_candidate_ids": [entry["candidate_id"] for entry in entries],
                           "entries": entries, "input_hashes": hashes,
                           "model": model, "recorded_at": self._now()}
        return ranking

    def rank_view(self, run_id: str, view: str, costume: str = "", *, evaluation_id: str = "") -> dict[str, Any]:
        run = self.detail(run_id, costume)
        view = view.upper()
        if view not in VIEWS:
            raise LocalCharacterAssetPipelineError(f"Unknown view: {view}")
        if view != "FRONT" and self._requires_front_anchor(run) and not run.get("front_anchor"):
            raise LocalCharacterAssetPipelineError("Select a FRONT candidate before ranking other views.")
        root, state = self._state(run_id, costume)
        current_evaluation = (run.get("evaluations") or {}).get(view) or {}
        evaluation_id = evaluation_id or str(current_evaluation.get("evaluation_id") or "")
        if evaluation_id and (current_evaluation.get("evaluation_id") != evaluation_id
                              or current_evaluation.get("status") not in {"RUNNING", "STAGING"}):
            return run
        hashes_before = {item["candidate_id"]: self._hash(Path(item["image_path"]))
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
            ranking = {"status": "FAILED", "error": str(exc), "recorded_at": self._now()}
        def save(current: dict[str, Any]) -> None:
            active = (current.get("evaluations") or {}).get(view) or {}
            if evaluation_id and (active.get("evaluation_id") != evaluation_id or active.get("status") not in {"RUNNING", "STAGING"}):
                return
            hashes_now = {item["candidate_id"]: self._hash(Path(str(item["image_path"])))
                          for item in self.detail(run_id, costume)["candidates"] if item.get("view") == view
                          and Path(str(item.get("image_path") or "")).is_file()}
            if hashes_now != hashes_before:
                return
            ranking["evaluation_id"] = evaluation_id
            current.setdefault("rankings", {})[view] = ranking
            if evaluation_id:
                active.update(ranking_status=ranking.get("status"), ranking_updated_at=self._now())
                current.setdefault("evaluations", {})[view] = active
        mutate_local_run_state(root, save)
        from zet.services.local_prompt_improvement_service import after_initial_ranking
        after_initial_ranking(self, self.pipeline, self.project_root, run_id, view, costume)
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
        if view not in VIEWS:
            raise LocalCharacterAssetPipelineError(f"Unknown view: {view}")
        if view != "FRONT" and self._requires_front_anchor(run) and not run.get("front_anchor"):
            raise LocalCharacterAssetPipelineError("Select a FRONT candidate before rerunning failed candidates in other views.")
        self.asset_store.assert_batch_change_allowed(run["character"], run["phase"], self.definition["asset_pipeline"], view, self._qualifier(costume))
        root, state = self._state(run_id, costume)
        failed = [item for item in run["candidates"] if item["view"] == view and
                  (item.get("status") in {"FAILED", "GATE_REJECTED"} or item.get("human_review", {}).get("decision") == "reject")]
        from zet.services.local_image_pipeline_policy import clear_candidate_artifacts
        for candidate in failed:
            clear_candidate_artifacts(root, candidate["candidate_id"], candidate.get("image_path"))
            state.setdefault("candidates", {})[candidate["candidate_id"]] = {
                "status": "PENDING", "image_path": "", "ask_id": "", "gates": {}, "rejection_gate": "",
                "human_review": {"decision": "undecided"},
                "retry_count": int(candidate.get("retry_count") or 0) + 1,
            }
        state.setdefault("rankings", {}).pop(view, None)
        from zet.services.local_image_evaluation_service import supersede_evaluations
        supersede_evaluations(state, {view}, "Candidates in this view are being re-run.")
        state.update(status="QUEUED", stop_requested=False)
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
                    status="WAITING_FOR_GATES", gates={}, rejection_gate="", failed_gate="")
        for current in views:
            state.setdefault("rankings", {}).pop(current, None)
        state["status"] = "QUEUED"
        state["stop_requested"] = False
        self._write(root / "state.json", state)
        return self.detail(run_id, costume)

    @serialize_local_run_state
    def select_view(self, run_id: str, view: str, candidate_id: str, costume: str = "", *, autogenerate: bool = False) -> dict[str, Any]:
        run, view = self.detail(run_id, costume), view.upper()
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
        if auto_approved and not self._candidate_gates_current(run, candidate):
            raise LocalCharacterAssetPipelineError("Re-evaluate and pass the FRONT gates before autoselecting this candidate.")
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
                            item_state.update(gates={key: {**value, "status": "STALE", "stale_reason": "FRONT anchor changed."}
                                                     for key, value in (item.get("gates") or {}).items()},
                                              stale_selection=bool(state.get("selected_views", {}).get(other)))
        update = {"selected_at": self._now()}
        if auto_approved:
            update["autogenerate_approval"] = {"approved_at": self._now(), "reason": "Current #1 Luna FRONT candidate passed local gates."}
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
                        update["gates"] = {key: {**value, "status": "STALE", "stale_reason": "FRONT anchor changed."}
                                           for key, value in (candidate.get("gates") or {}).items()}
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

        if pipeline in {"Body-Reference", "Head-Image"} and view != "FRONT":
            front_id = str(run.get("front_anchor") or "")
            if not front_id or str((run.get("selected_views") or {}).get("FRONT") or "") != front_id:
                raise LocalCharacterAssetPipelineError(f"A selected FRONT {pipeline} anchor is required before promoting {view}.")
            self._collect_promotion_selection(run, pipeline, "FRONT", qualifier, records, visiting)
            front = next(item for item in run["candidates"] if item.get("candidate_id") == front_id)
            dependencies.append({"key": self.asset_store.key(pipeline, "FRONT", qualifier),
                                 "image_sha256": self._hash(Path(str(front["image_path"])))})

        if pipeline in {"Character-Assembly", "Costume-Dressing"} and view != "FRONT" and self._requires_front_anchor(run):
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
                        "image_path": str(image), "image_sha256": digest, "dependencies": dependencies}
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
        digest = str(source.get("sha256") or source.get("image_sha256") or "")
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
        if pipeline in {"Character-Assembly", "Costume-Dressing", "Body-Reference", "Head-Image"}:
            self._collect_promotion_selection(source_run, pipeline, view, qualifier, records, visiting)
        else:
            candidate = next((item for item in source_run.get("candidates", [])
                              if item.get("candidate_id") == source_candidate_id), None)
            image = Path(str((candidate or {}).get("image_path") or "")).resolve()
            if not image.is_file() or self._hash(image) != digest:
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
            state["updated_at"] = self._now()
        mutate_local_run_state(root, apply)
        return self.detail(run_id, costume)

    def retry_candidate(self, run_id: str, candidate_id: str, costume: str = "") -> dict[str, Any]:
        run = self.detail(run_id, costume)
        candidate = next((item for item in run["candidates"] if item["candidate_id"] == candidate_id), None)
        if not candidate:
            raise LocalCharacterAssetPipelineError(f"Unknown candidate: {candidate_id}")
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
        self._update(run_id, candidate_id, costume, status="PENDING", image_path="", ask_id="", gates={},
                     rejection_gate="", failed_gate="", render_error="", review_error="",
                     retry_count=int(candidate.get("retry_count") or 0) + 1,
                     human_review={"decision": "undecided"})
        return self.detail(run_id, costume)

    def rerun_view(self, run_id: str, view: str, costume: str = "", *, refresh_sources: bool = True,
                   recompile: bool = False) -> dict[str, Any]:
        refresh_sources = refresh_sources or recompile
        run, view = self.detail(run_id, costume), view.upper()
        if view not in VIEWS:
            raise LocalCharacterAssetPipelineError(f"Unknown view: {view}")
        self.asset_store.assert_batch_change_allowed(run["character"], run["phase"], self.definition["asset_pipeline"], view, self._qualifier(costume))
        state = self._read(Path(run["root"]) / "state.json")
        if view == "FRONT" and self._requires_front_anchor(run) and any(
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
                "status": "PENDING", "image_path": "", "ask_id": "", "gates": {},
                "rejection_gate": "", "human_review": {"decision": "undecided"},
                "retry_count": int(candidate.get("retry_count") or 0) + 1,
            }
        state.setdefault("rankings", {}).pop(view, None)
        selected_id = state.setdefault("selected_views", {}).pop(view, None)
        if selected_id:
            self.asset_store.clear_batch_selection(run["character"], run["phase"], self.definition["asset_pipeline"], view, run_id, self._qualifier(costume))
        if view == "FRONT":
            state["front_anchor"] = None
            state["views_started"] = False
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
                    digest = str(source.get("sha256") or source.get("image_sha256") or "")
                    if not path.is_file() or not digest or self._hash(path) != digest:
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
                     candidates={item["candidate_id"]: {"status": "PENDING", "image_path": "", "ask_id": "", "gates": {},
                         "rejection_gate": "", "retry_count": int(item.get("retry_count") or 0) + 1,
                         "human_review": {"decision": "undecided"}} for item in run["candidates"]})
        self._write(root / "state.json", state)
        return self.detail(run_id, costume)

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
        requires_front_anchor = self._requires_front_anchor(run)
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
                        if not path.is_file() or self._hash(path) != record.get("sha256"):
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
            update.update(error="", render_error="", review_error="", failed_gate="")
            if candidate["candidate_id"] in missing_ids:
                clear_candidate_artifacts(state_root, candidate["candidate_id"], candidate.get("image_path"))
                update.update(status="QUEUED" if candidate["view"] in target_views else "PENDING",
                              image_path="", ask_id="", gates={}, rejection_gate="",
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
        run = self.detail(run_id, costume)
        item = next((candidate for candidate in run["candidates"] if candidate["candidate_id"] == candidate_id), None)
        path = Path(str((item or {}).get("image_path") or "")).resolve()
        if not path.is_file() or not path.is_relative_to(Path(run["root"]).resolve()):
            raise LocalCharacterAssetPipelineError("Candidate image is unavailable.")
        return path

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

    def review_specification(self, run_id: str, view: str, costume: str = "") -> str:
        run = self.detail(run_id, costume)
        view = str(view or "").upper()
        if view not in run.get("views", []):
            raise LocalCharacterAssetPipelineError(f"Unknown view: {view}")
        gates = self.review_gates(self.pipeline, view)
        sections = [f"{self.definition['label']} review specification — {view}"]
        sections.extend(f"{gate.key.replace('_', ' ').title()} gate:\n{gate.prompt}" for gate in gates)
        return "\n\n".join(sections)

    def gate_prompt(self, run_id: str, view: str, gate: str, costume: str = "") -> str:
        definition = next((item for item in self.review_gates(self.pipeline, view.upper()) if item.key == gate), None)
        if not definition:
            raise LocalCharacterAssetPipelineError(f"Unknown gate for view: {gate}")
        return definition.prompt

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
            for gate in (candidate.get("gates") or {}).values():
                if gate.get("ask_id"):
                    ask_ids.add(str(gate["ask_id"]))
        if not ask_ids:
            return
        queue_root = Path(paths.config.base_ai_queue_path)
        for task in paths.task_paths("ask"):
            if task.name in ask_ids:
                supersede_task(queue_root, task, "The local character pipeline work was stopped, deleted, or retried.")

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
