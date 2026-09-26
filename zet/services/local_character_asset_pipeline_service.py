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
from zet.services.candidate_review_contract import ReviewGate, validate_ranking
from zet.services.local_asset_store_service import LocalAssetStoreService
from zet.services.local_image_pipeline_policy import (
    ACTIVE_RUN_STATUSES, decorate_local_pipeline_detail, gate_result_is_current, pipeline_page_config, upgrade_legacy_review_v1,
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

    def __init__(self, app: Any, project_root: str | Path, pipeline: str):
        if pipeline not in self.PIPELINES:
            raise LocalCharacterAssetPipelineError(f"Unsupported local pipeline: {pipeline}")
        self.app = app
        self.project_root = Path(project_root).resolve()
        self.definition = self.PIPELINES[pipeline]
        self.pipeline = pipeline
        self.library_root = Path(app.config.base_library_path).resolve()
        self.character_root = Path(app.config.base_character_path).resolve()
        self.root = self.library_root / "Experiments" / "Character-Pipeline"
        self.asset_store = LocalAssetStoreService(self.library_root)

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

    def preview(self, payload: dict[str, Any]) -> dict[str, Any]:
        character, phase = str(payload.get("character") or "").strip(), str(payload.get("phase") or "").strip()
        costume = str(payload.get("costume") or "").strip()
        if not character or not phase or (self.definition["qualifies"] and not costume):
            raise LocalCharacterAssetPipelineError("Character and phase are required; Costume-Dressing also requires a costume.")
        front_count, other_count = int(payload.get("front_count") or 8), int(payload.get("other_count") or 4)
        total = front_count + 7 * other_count
        if front_count < 1 or other_count < 1 or total > 256:
            raise LocalCharacterAssetPipelineError("Candidate counts must be positive and the run cannot exceed 256 candidates.")
        inputs, blocking_reasons = {}, []
        requested_views = ("FRONT",) if payload.get("front_only") else VIEWS
        for view in requested_views:
            requirements = (("body_reference", "Body-Reference"), ("head_image", "Head-Image")) \
                if self.pipeline == "character-assembly" else (("character_assembly", "Character-Assembly"),)
            resolved = {}
            for role, pipeline in requirements:
                try:
                    resolved[role] = self._locked(character, phase, pipeline, view)
                except LocalCharacterAssetPipelineError as exc:
                    blocking_reasons.append(str(exc))
            if len(resolved) == len(requirements):
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
                candidates.append({"candidate_id": f"c{index:03d}", "view": view, "ordinal": ordinal,
                                  "seed": seeds[index - 1], "status": "PENDING", "image_path": "",
                                  "gates": {}, "human_review": {"decision": "undecided", "notes": ""}, "retry_count": 0})
        spec = {"schema_version": 1, "review_version": 2, "kind": self.pipeline, "run_id": run_id,
                "created_at": self._now(), "status": "QUEUED", "character": plan["character"], "phase": plan["phase"],
                "costume": plan["costume"], "views": list(VIEWS), "front_count": plan["front_count"],
                "other_count": plan["other_count"], "candidate_count": count, "sources": sources,
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
            active = run_id in self._active
        if upgrade_legacy and upgrade_legacy_review_v1(root, spec, state, active=active):
            spec, state = self._read(root / "spec.json"), self._read(root / "state.json")
        candidates = {item["candidate_id"]: dict(item) for item in spec.get("candidates", [])}
        for cid, update in (state.get("candidates") or {}).items():
            if cid in candidates:
                candidates[cid].update(update)
        result = {**spec, **state, "candidates": list(candidates.values()), "root": str(root),
                  "selected_views": state.get("selected_views") or {}, "rankings": state.get("rankings") or {},
                  "stop_requested": bool(state.get("stop_requested")), "interrupted": False}
        if state.get("status") in ACTIVE_RUN_STATUSES:
            with self._active_lock:
                result["interrupted"] = run_id not in self._active
                if result["interrupted"]:
                    result["status"] = "INTERRUPTED"
        result["local_assets"] = self.asset_store.detail(result["character"], result["phase"])["assets"]
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
        if result["stale_selections"] and result["status"] not in ACTIVE_RUN_STATUSES | {"ERROR", "CANCELLED", "INTERRUPTED"}:
            result["status"] = "REVIEW_REQUIRED"
        return decorate_local_pipeline_detail(result, self.pipeline)

    def list_runs(self, character: str = "", phase: str = "", costume: str = "") -> list[dict[str, Any]]:
        if costume and self.definition["qualifies"]:
            base = self._workspace(character, phase, costume)
            paths = base.glob("*/spec.json")
        else:
            base = self.root / (self._safe(character) if character else "*") / (self._safe(phase) if phase else "*") / self.definition["workspace"]
            paths = base.glob("**/spec.json")
        result = []
        for path in paths:
            spec = self._read(path)
            if spec.get("kind") == self.pipeline:
                try:
                    result.append(self.detail(spec["run_id"], str(spec.get("costume") or "")))
                except LocalCharacterAssetPipelineError:
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

    def _references(self, run: dict[str, Any], view: str) -> list[dict[str, Any]]:
        inputs = run.get("sources", {}).get(view)
        if inputs is None:
            inputs = {}
            required = (("body_reference", "Body-Reference"), ("head_image", "Head-Image")) if self.pipeline == "character-assembly" else (("character_assembly", "Character-Assembly"),)
            qualifier = self._qualifier(run.get("costume") or "") if self.pipeline == "costume-dressing" else ""
            for role, pipeline in required:
                record = self._locked(run["character"], run["phase"], pipeline, view, qualifier)
                source = Path(record["image_path"])
                destination = Path(run["root"]) / "inputs" / view / f"{role}{source.suffix.lower()}"
                destination.parent.mkdir(parents=True, exist_ok=True)
                if not destination.exists():
                    shutil.copy2(source, destination)
                inputs[role] = {**record, "image_path": str(destination), "sha256": self._hash(destination)}
            spec_path = Path(run["root"]) / "spec.json"
            spec = self._read(spec_path)
            spec.setdefault("sources", {})[view] = inputs
            self._write(spec_path, spec)
            run.setdefault("sources", {})[view] = inputs
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
            job.update({"Body View": view, "Head View": view})
            result = compile_character_assembly_job(job, self.project_root, pipeline_mode="local")
        else:
            job.update({"Body View": view, "Head View": view, "Costume": run["costume"],
                        "Costume Path": run["costume_path"]})
            result = compile_costume_dressing_job(job, self.project_root, pipeline_mode="local")
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
        ask_path = self.app.ai_proxy_service.stage_render_task_local_render_ask(
            manifest, prompt_copy, candidate_root, allow_parallel=True, seed=int(candidate["seed"]),
            checkpoint=str(profile.get("diffusion_model") or ""), render_preset=preset_name,
            image_generation="comfyui", reference_files=refs,
        )
        ask = self._read(ask_path / "ask_manifest.json")
        ref_hashes = {str(ref["role"]): self._hash(Path(ref["path"])) for ref in refs}
        self._update(run_id, candidate_id, costume=costume, status="QUEUED", ask_id=ask["ask_id"],
                     image_path=str(target), prompt_path=str(prompt_path), prompt_sha256=self._hash(prompt_path),
                     reference_images=[{"role": ref["role"], "path": ref["path"], "sha256": ref_hashes[ref["role"]]} for ref in refs],
                     input_hashes=ref_hashes, workflow_kind=str(ask.get("workflow_kind") or profile.get("workflow_kind") or ""),
                     render_preset=preset_name, queued_at=self._now())
        return self.detail(run_id, costume)

    def _state(self, run_id: str, costume: str = "") -> tuple[Path, dict[str, Any]]:
        root = self._run_root(run_id, costume)
        return root, self._read(root / "state.json")

    def _update(self, run_id: str, candidate_id: str, costume: str = "", **changes: Any) -> None:
        root, state = self._state(run_id, costume)
        state.setdefault("candidates", {}).setdefault(candidate_id, {}).update(changes)
        state["updated_at"] = self._now()
        self._write(root / "state.json", state)

    def _run_update(self, run_id: str, costume: str = "", **changes: Any) -> None:
        root, state = self._state(run_id, costume)
        state.update(changes, updated_at=self._now())
        self._write(root / "state.json", state)

    def _proxy_answer(self, ask_id: str) -> tuple[str, dict[str, Any]]:
        paths = self.app.ai_proxy_service.ai_proxy_path_service
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
                or ask.get("pipeline") != expected_pipeline):
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
        current_assets = self.asset_store.detail(run["character"], run["phase"])["assets"]
        for source in (run.get("sources", {}).get(candidate["view"]) or {}).values():
            current = current_assets.get(source.get("key"), {})
            source_path = Path(str(current.get("locked_image_path") or ""))
            if (not current.get("locked") or current.get("stale") or not source_path.is_file()
                    or current.get("image_sha256") != source.get("sha256")
                    or self._hash(source_path) != source.get("sha256")):
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

    def run_candidate_gates(self, run_id: str, candidate_id: str, costume: str = "") -> bool:
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
            try:
                record = self._queue_gate(run, candidate, definition, hashes)
                self._update(run_id, candidate_id, costume, status="WAITING_FOR_GATES", gates={**gates, definition.key: record})
                verdict, reason = self._wait_gate(run_id, candidate_id, definition.key, costume)
                gates[definition.key] = {**record, "status": "COMPLETE", "policy_status": policy,
                                         "verdict": verdict, "reason": reason, "input_hashes": hashes,
                                         "prompt_sha256": prompt_hash, "completed_at": self._now()}
                self._update(run_id, candidate_id, costume, gates=gates)
                if verdict == "TRUE" and policy == "Active":
                    self._update(run_id, candidate_id, costume, status="GATE_REJECTED", rejection_gate=definition.key)
                    return True
            except Exception as exc:
                gates[definition.key] = {"status": "FAILED", "policy_status": policy, "input_hashes": hashes,
                                         "prompt_sha256": prompt_hash, "error": str(exc)}
                self._update(run_id, candidate_id, costume, gates=gates)
                if policy != "Warning":
                    self._update(run_id, candidate_id, costume, status="FAILED", failed_gate=definition.key)
                    return False
        self._update(run_id, candidate_id, costume, status="WAITING_FOR_HUMAN_REVIEW", gates=gates)
        return True

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

    def execute_run(self, run_id: str, *, views: set[str] | None = None, costume: str = "") -> None:
        root = self._run_root(run_id, costume)
        try:
            with file_lock(root / "runner.lock", timeout=0):
                with self._active_lock:
                    self._active.add(run_id)
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
                               and item.get("status") in {"PENDING", "FAILED", "QUEUED", "RUNNING", "WAITING_FOR_GATES"}]
                    for item in pending:
                        if self.detail(run_id, costume).get("stop_requested"):
                            break
                        current = next(x for x in self.detail(run_id, costume)["candidates"] if x["candidate_id"] == item["candidate_id"])
                        if Path(str(current.get("image_path") or "")).is_file():
                            continue
                        try:
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
                    for item in pending:
                        if self.detail(run_id, costume).get("stop_requested"):
                            break
                        current = next(x for x in self.detail(run_id, costume)["candidates"] if x["candidate_id"] == item["candidate_id"])
                        if Path(str(current.get("image_path") or "")).is_file() and current.get("status") not in {"GATE_REJECTED"}:
                            try:
                                self.run_candidate_gates(run_id, item["candidate_id"], costume)
                            except Exception as exc:
                                self._update(run_id, item["candidate_id"], costume, status="FAILED", review_error=str(exc))
                    if not self.detail(run_id, costume).get("stop_requested"):
                        self.rank_view(run_id, view, costume)
                latest = self.detail(run_id, costume)
                selected = latest.get("selected_views") or {}
                complete = all(selected.get(view) for view in VIEWS)
                status = "CANCELLED" if latest.get("stop_requested") else "COMPLETE" if complete else "AWAITING_FRONT_ANCHOR" if self._requires_front_anchor(latest) and not latest.get("front_anchor") else "AWAITING_HUMAN_SELECTION"
                self._run_update(run_id, costume, status=status)
        except TimeoutError:
            return
        except Exception as exc:
            self._run_update(run_id, costume, status="ERROR", error=str(exc))
        finally:
            with self._active_lock:
                self._active.discard(run_id)

    def _rank(self, run: dict[str, Any], view: str) -> dict[str, Any]:
        survivors = [item for item in run["candidates"] if item["view"] == view
                     and item.get("status") in {"WAITING_FOR_HUMAN_REVIEW", "COMPLETE"}
                     and (not item.get("rejection_gate") or item.get("human_review", {}).get("decision") == "keep")
                     and item.get("human_review", {}).get("decision") != "reject"
                     and Path(str(item.get("image_path") or "")).is_file()
                     and (item.get("human_review", {}).get("decision") == "keep" or self._candidate_gates_current(run, item))]
        hashes = {item["candidate_id"]: self._hash(Path(item["image_path"])) for item in survivors}
        if not survivors:
            ranking = {"status": "EMPTY", "ordered_candidate_ids": [], "luna_ordered_candidate_ids": [], "entries": [], "input_hashes": {}, "recorded_at": self._now()}
        elif len(survivors) == 1:
            item = survivors[0]
            ranking = {"status": "COMPLETE", "ordered_candidate_ids": [item["candidate_id"]],
                       "luna_ordered_candidate_ids": [item["candidate_id"]],
                       "entries": [{"candidate_id": item["candidate_id"], "reason": "Only candidate survived the gates."}],
                       "input_hashes": hashes, "model": "deterministic-single-survivor", "recorded_at": self._now()}
        else:
            schema = {"type": "object", "properties": {"ranking": {"type": "array", "items": {
                "type": "object", "properties": {"candidate_id": {"type": "string"}, "reason": {"type": "string"}},
                "required": ["candidate_id", "reason"], "additionalProperties": False}}}, "required": ["ranking"], "additionalProperties": False}
            with tempfile.TemporaryDirectory(prefix="zet_local_character_rank_") as temp:
                schema_path, output_path = Path(temp) / "schema.json", Path(temp) / "ranking.json"
                schema_path.write_text(json.dumps(schema), encoding="utf-8")
                prompt = f"Rank these {self.definition['label']} candidates for {view}. Compare view accuracy, source preservation, identity, and usefulness as a reference. Candidate IDs: " + ", ".join(hashes)
                command = [shutil.which("codex") or "codex", "-a", "never", "-s", "read-only", "-m",
                           str(getattr(self.app.config, "codex_default_model", "gpt-6-luna")),
                           "-c", 'model_reasoning_effort="high"', "-C", str(self.project_root), "exec",
                           "--ignore-user-config", "--skip-git-repo-check", "--ephemeral", "--output-schema",
                           str(schema_path), "--output-last-message", str(output_path)]
                if view != "FRONT" and self._requires_front_anchor(run):
                    anchor = next(item for item in run["candidates"] if item["candidate_id"] == run["front_anchor"])
                    guide = "costume appearance" if self.pipeline == "costume-dressing" else "assembled-character proportion and appearance"
                    prompt += f". The first image is the selected FRONT {guide} guide; rank candidates for consistency with it."
                    command.extend(["--image", str(anchor["image_path"])])
                for item in survivors:
                    command.extend(["--image", str(item["image_path"])])
                result = subprocess.run(command, input=prompt, capture_output=True, text=True, timeout=1800, check=False)
                if result.returncode:
                    raise LocalCharacterAssetPipelineError((result.stderr or result.stdout or "Luna ranking failed")[-2000:])
                entries = validate_ranking(json.loads(output_path.read_text(encoding="utf-8")), list(hashes))
            ranking = {"status": "COMPLETE", "ordered_candidate_ids": [entry["candidate_id"] for entry in entries],
                       "luna_ordered_candidate_ids": [entry["candidate_id"] for entry in entries],
                           "entries": entries, "input_hashes": hashes,
                           "model": str(getattr(self.app.config, "codex_default_model", "gpt-6-luna")), "recorded_at": self._now()}
        return ranking

    def rank_view(self, run_id: str, view: str, costume: str = "") -> dict[str, Any]:
        run = self.detail(run_id, costume)
        view = view.upper()
        if view not in VIEWS:
            raise LocalCharacterAssetPipelineError(f"Unknown view: {view}")
        if view != "FRONT" and self._requires_front_anchor(run) and not run.get("front_anchor"):
            raise LocalCharacterAssetPipelineError("Select a FRONT candidate before ranking other views.")
        root, state = self._state(run_id, costume)
        state.setdefault("rankings", {})[view] = {"status": "RUNNING", "started_at": self._now()}
        self._write(root / "state.json", state)
        try:
            ranking = self._rank(run, view)
        except Exception as exc:
            ranking = {"status": "FAILED", "error": str(exc), "recorded_at": self._now()}
        root, state = self._state(run_id, costume)
        state.setdefault("rankings", {})[view] = ranking
        self._write(root / "state.json", state)
        return self.detail(run_id, costume)

    def move_rank(self, run_id: str, view: str, candidate_id: str, direction: str, costume: str = "") -> dict[str, Any]:
        run = self.detail(run_id, costume)
        view = view.upper()
        ranking = dict((run.get("rankings") or {}).get(view) or {})
        ordered = list(ranking.get("ordered_candidate_ids") or [])
        if direction not in {"up", "down"} or candidate_id not in ordered:
            raise LocalCharacterAssetPipelineError("Candidate is not in the current ranking.")
        index = ordered.index(candidate_id)
        target = index - 1 if direction == "up" else index + 1
        if target < 0 or target >= len(ordered):
            return run
        ranking.setdefault("luna_ordered_candidate_ids", list(ordered))
        ordered[index], ordered[target] = ordered[target], ordered[index]
        entries = {entry["candidate_id"]: entry for entry in ranking.get("entries", [])}
        ranking["ordered_candidate_ids"] = ordered
        ranking["entries"] = [entries[cid] for cid in ordered if cid in entries]
        ranking["recorded_at"] = self._now()
        root, state = self._state(run_id, costume)
        state.setdefault("rankings", {})[view] = ranking
        self._write(root / "state.json", state)
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
                "human_review": {"decision": "undecided", "notes": ""},
                "retry_count": int(candidate.get("retry_count") or 0) + 1,
            }
        state.setdefault("rankings", {}).pop(view, None)
        state["status"] = "QUEUED"
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

    def select_view(self, run_id: str, view: str, candidate_id: str, costume: str = "", *, autogenerate: bool = False) -> dict[str, Any]:
        run, view = self.detail(run_id, costume), view.upper()
        if view not in VIEWS:
            raise LocalCharacterAssetPipelineError(f"Unknown view: {view}")
        if not candidate_id:
            return self.unselect_view(run_id, view, costume)
        if view != "FRONT" and self._requires_front_anchor(run) and not run.get("front_anchor"):
            raise LocalCharacterAssetPipelineError("Select a FRONT candidate before selecting other views.")
        qualifier = self._qualifier(costume)
        candidate = next((item for item in run["candidates"] if item["candidate_id"] == candidate_id), None)
        human_pass = bool(candidate and candidate.get("human_review", {}).get("decision") == "keep")
        if not candidate or candidate["view"] != view or (candidate.get("rejection_gate") and not human_pass):
            raise LocalCharacterAssetPipelineError("Choose a gate surviving or human-passed candidate from this view.")
        if candidate.get("human_review", {}).get("decision") == "reject":
            raise LocalCharacterAssetPipelineError("A human-rejected candidate cannot be selected.")
        auto_approved = bool(autogenerate and view == "FRONT")
        if auto_approved and candidate.get("human_review", {}).get("decision") == "reject":
            raise LocalCharacterAssetPipelineError("A human-rejected candidate cannot be autoselected.")
        if view == "FRONT" and candidate.get("human_review", {}).get("decision") != "keep" and not auto_approved:
            raise LocalCharacterAssetPipelineError("Review and pass a FRONT candidate before selecting it as the anchor.")
        ranking = (run.get("rankings") or {}).get(view) or {}
        image = Path(str(candidate.get("image_path") or ""))
        if ranking.get("status") != "COMPLETE" or candidate_id not in ranking.get("ordered_candidate_ids", []) or not image.is_file() or ranking.get("input_hashes", {}).get(candidate_id) != self._hash(image):
            raise LocalCharacterAssetPipelineError("Candidate needs a current gate review and ranking before selection.")
        if not human_pass and not self._candidate_gates_current(run, candidate):
            raise LocalCharacterAssetPipelineError("Candidate has missing or stale gates; re-evaluate and rank this view.")
        luna_order = list(ranking.get("luna_ordered_candidate_ids") or [])
        if not luna_order and len(ranking.get("ordered_candidate_ids") or []) == 1:
            luna_order = list(ranking["ordered_candidate_ids"])
        if auto_approved and (not luna_order or luna_order[0] != candidate_id):
            raise LocalCharacterAssetPipelineError("Autogenerate can select only the original #1 Luna candidate.")
        key = self.asset_store.key(self.definition["asset_pipeline"], view, qualifier)
        existing = run["local_assets"].get(key) or {}
        self.asset_store.assert_batch_change_allowed(run["character"], run["phase"], self.definition["asset_pipeline"], view, qualifier)
        dependencies = []
        if self.pipeline == "character-assembly":
            for pipeline in ("Body-Reference", "Head-Image"):
                source = run["sources"][view]["body_reference" if pipeline == "Body-Reference" else "head_image"]
                dependencies.append({"key": source["key"], "image_sha256": source["sha256"]})
        if view != "FRONT" and self._requires_front_anchor(run):
            front = next(item for item in run["candidates"] if item["candidate_id"] == run.get("front_anchor"))
            dependencies.append({"key": self.asset_store.key(self.definition["asset_pipeline"], "FRONT", qualifier),
                                 "image_sha256": self._hash(Path(front["image_path"]))})
        self.asset_store.record_batch_selection(run["character"], run["phase"], self.definition["asset_pipeline"], view,
                                          candidate_id=candidate_id, image_path=image, batch_id=run_id,
                                          dependencies=dependencies, qualifier=qualifier)
        root, state = self._state(run_id, costume)
        state.setdefault("selected_views", {})[view] = candidate_id
        if view == "FRONT":
            old_anchor = state.get("front_anchor")
            state["front_anchor"] = candidate_id
            if old_anchor != candidate_id and self._requires_front_anchor(run):
                state["views_started"] = False
                for other in VIEWS[1:]:
                    state.setdefault("rankings", {}).pop(other, None)
                    old_selected = state.setdefault("selected_views", {}).pop(other, None)
                    old_key = self.asset_store.key(self.definition["asset_pipeline"], other, qualifier)
                    selected_asset = self.asset_store.detail(run["character"], run["phase"])["assets"].get(old_key) or {}
                    if old_selected and selected_asset.get("batch_id") == run_id and not selected_asset.get("locked"):
                        self.asset_store.clear_selection(
                            run["character"], run["phase"], self.definition["asset_pipeline"], other, qualifier
                        )
                    for item in run["candidates"]:
                        if item["view"] == other:
                            item_state = state.setdefault("candidates", {}).setdefault(item["candidate_id"], {})
                            item_state.update(gates={key: {**value, "status": "STALE", "stale_reason": "FRONT anchor changed."}
                                                     for key, value in (item.get("gates") or {}).items()},
                                              rejection_gate="")
        update = {"status": "COMPLETE", "selected_at": self._now()}
        if auto_approved:
            update["autogenerate_approval"] = {"approved_at": self._now(), "reason": "Current #1 Luna FRONT candidate passed local gates."}
        state.setdefault("candidates", {}).setdefault(candidate_id, {}).update(update)
        state["status"] = "COMPLETE" if all(state.get("selected_views", {}).get(target) for target in VIEWS) else "AWAITING_HUMAN_SELECTION"
        self._write(root / "state.json", state)
        return self.detail(run_id, costume)

    def unselect_view(self, run_id: str, view: str, costume: str = "") -> dict[str, Any]:
        run, view = self.detail(run_id, costume), str(view or "").upper()
        if view not in VIEWS:
            raise LocalCharacterAssetPipelineError(f"Unknown view: {view}")
        targets = VIEWS if view == "FRONT" and self._requires_front_anchor(run) else (view,)
        qualifier = self._qualifier(costume)
        for target in targets:
            self.asset_store.assert_batch_change_allowed(run["character"], run["phase"],
                                                         self.definition["asset_pipeline"], target, qualifier)
        root, state = self._state(run_id, costume)
        for target in targets:
            state.setdefault("selected_views", {}).pop(target, None)
            self.asset_store.clear_batch_selection(run["character"], run["phase"],
                self.definition["asset_pipeline"], target, run_id, qualifier)
            if target != "FRONT":
                state.setdefault("rankings", {}).pop(target, None)
        if view == "FRONT":
            state["front_anchor"] = None
            state["views_started"] = False
        state["status"] = "AWAITING_FRONT_ANCHOR" if view == "FRONT" and self._requires_front_anchor(run) else "AWAITING_HUMAN_SELECTION"
        self._write(root / "state.json", state)
        return self.detail(run_id, costume)

    def lock_selected_view(self, run_id: str, view: str, costume: str = "") -> dict[str, Any]:
        run = self.detail(run_id, costume)
        view = view.upper()
        candidate_id = (run.get("selected_views") or {}).get(view)
        if not candidate_id:
            raise LocalCharacterAssetPipelineError("Select a reviewed candidate before locking it.")
        candidate = next((item for item in run["candidates"] if item["candidate_id"] == candidate_id), None)
        ranking = (run.get("rankings") or {}).get(view) or {}
        image = Path(str((candidate or {}).get("image_path") or ""))
        if (not candidate or not image.is_file() or ranking.get("status") != "COMPLETE"
                or ranking.get("input_hashes", {}).get(candidate_id) != self._hash(image)
                or not self._candidate_gates_current(run, candidate)
                or candidate.get("human_review", {}).get("decision") == "reject"):
            raise LocalCharacterAssetPipelineError("Selected candidate needs current gates, ranking, and human review before locking.")
        if view.upper() != "FRONT" and self._requires_front_anchor(run):
            key = self.asset_store.key(self.definition["asset_pipeline"], "FRONT", self._qualifier(costume))
            front = (run.get("local_assets") or {}).get(key) or {}
            anchor = next((item for item in run["candidates"] if item["candidate_id"] == run.get("front_anchor")), None)
            anchor_image = Path(str((anchor or {}).get("image_path") or ""))
            if self._requires_front_anchor(run) and (not front.get("locked") or not anchor_image.is_file() or front.get("image_sha256") != self._hash(anchor_image)):
                raise LocalCharacterAssetPipelineError("Lock the selected FRONT image before locking later views.")
        dependencies = []
        if self.pipeline == "character-assembly":
            for pipeline, role in (("Body-Reference", "body_reference"), ("Head-Image", "head_image")):
                source = run["sources"][view][role]
                dependencies.append({"key": source["key"], "image_sha256": source["sha256"]})
        if view != "FRONT" and self._requires_front_anchor(run):
            dependencies.append({"key": self.asset_store.key(self.definition["asset_pipeline"], "FRONT", self._qualifier(costume)),
                                 "image_sha256": self._hash(anchor_image)})
        return self.asset_store.lock_batch_selection(
            run["character"], run["phase"], self.definition["asset_pipeline"], view,
            candidate_id=candidate_id, image_path=image, batch_id=run_id,
            dependencies=dependencies, qualifier=self._qualifier(costume),
        )

    def unlock_view(self, character: str, phase: str, view: str, costume: str = "") -> dict[str, Any]:
        return self.asset_store.unlock(character, phase, self.definition["asset_pipeline"], view.upper(), self._qualifier(costume))

    def update_candidate(self, run_id: str, candidate_id: str, payload: dict[str, Any], costume: str = "") -> dict[str, Any]:
        run = self.detail(run_id, costume)
        candidate = next((item for item in run["candidates"] if item["candidate_id"] == candidate_id), None)
        decision = str(payload.get("decision") or "undecided")
        if not candidate or decision not in {"keep", "reject", "undecided"}:
            raise LocalCharacterAssetPipelineError("Invalid candidate or human decision.")
        if not Path(str(candidate.get("image_path") or "")).is_file():
            raise LocalCharacterAssetPipelineError("Candidate image must be complete before human review.")
        root, state = self._state(run_id, costume)
        if decision == "reject" and (run.get("selected_views") or {}).get(candidate["view"]) == candidate_id:
            if candidate["view"] == "FRONT" and self._requires_front_anchor(run) and any(
                (run.get("selected_views") or {}).get(view) for view in VIEWS[1:]
            ):
                raise LocalCharacterAssetPipelineError("Clear downstream selections before rejecting the FRONT anchor.")
            qualifier = self._qualifier(costume)
            self.asset_store.clear_batch_selection(run["character"], run["phase"], self.definition["asset_pipeline"], candidate["view"], run_id, qualifier)
            state.setdefault("selected_views", {}).pop(candidate["view"], None)
            if candidate["view"] == "FRONT":
                state["front_anchor"] = None
                state["views_started"] = False
        previous_decision = str((candidate.get("human_review") or {}).get("decision") or "undecided")
        if previous_decision != decision and (
            previous_decision == "reject" or decision == "reject" or candidate.get("rejection_gate")
        ):
            ranking = state.setdefault("rankings", {}).get(candidate["view"])
            if ranking and ranking.get("status") == "COMPLETE":
                ranking = dict(ranking)
                ranking["status"] = "STALE"
                ranking["stale_reason"] = "Human review changed the ranked survivor set. Re-rank this view."
                state["rankings"][candidate["view"]] = ranking
        self._write(root / "state.json", state)
        self._update(run_id, candidate_id, costume,
                     human_review={"decision": decision, "notes": str(payload.get("notes") or "")},
                     status="WAITING_FOR_HUMAN_REVIEW" if decision == "reject" else "COMPLETE" if decision == "keep" else candidate.get("status"))
        return self.detail(run_id, costume)

    def retry_candidate(self, run_id: str, candidate_id: str, costume: str = "") -> dict[str, Any]:
        run = self.detail(run_id, costume)
        candidate = next((item for item in run["candidates"] if item["candidate_id"] == candidate_id), None)
        if not candidate:
            raise LocalCharacterAssetPipelineError(f"Unknown candidate: {candidate_id}")
        if candidate["view"] != "FRONT" and self._requires_front_anchor(run) and not run.get("front_anchor"):
            raise LocalCharacterAssetPipelineError("Select a FRONT candidate before retrying other views.")
        self.asset_store.assert_batch_change_allowed(run["character"], run["phase"], self.definition["asset_pipeline"], candidate["view"], self._qualifier(costume))
        from zet.services.local_image_pipeline_policy import clear_candidate_artifacts
        root = Path(run["root"])
        clear_candidate_artifacts(root, candidate_id, candidate.get("image_path"))
        self._update(run_id, candidate_id, costume, status="PENDING", image_path="", ask_id="", gates={},
                     rejection_gate="", failed_gate="", render_error="", review_error="",
                     retry_count=int(candidate.get("retry_count") or 0) + 1,
                     human_review={"decision": "undecided", "notes": ""})
        return self.detail(run_id, costume)

    def rerun_view(self, run_id: str, view: str, costume: str = "") -> dict[str, Any]:
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
        root, state = self._state(run_id, costume)
        for candidate in [item for item in run["candidates"] if item["view"] == view]:
            from zet.services.local_image_pipeline_policy import clear_candidate_artifacts
            clear_candidate_artifacts(root, candidate["candidate_id"], candidate.get("image_path"))
            state.setdefault("candidates", {})[candidate["candidate_id"]] = {
                "status": "PENDING", "image_path": "", "ask_id": "", "gates": {},
                "rejection_gate": "", "human_review": {"decision": "undecided", "notes": ""},
                "retry_count": int(candidate.get("retry_count") or 0) + 1,
            }
        state.setdefault("rankings", {}).pop(view, None)
        selected_id = state.setdefault("selected_views", {}).pop(view, None)
        if selected_id:
            self.asset_store.clear_batch_selection(run["character"], run["phase"], self.definition["asset_pipeline"], view, run_id, self._qualifier(costume))
        if view == "FRONT":
            state["front_anchor"] = None
            state["views_started"] = False
        state["status"] = "QUEUED"
        self._write(root / "state.json", state)
        return self.detail(run_id, costume)

    def rerun(self, run_id: str, costume: str = "") -> dict[str, Any]:
        run = self.detail(run_id, costume)
        for view in VIEWS:
            self.asset_store.assert_batch_change_allowed(run["character"], run["phase"], self.definition["asset_pipeline"], view, self._qualifier(costume))
        root, state = self._state(run_id, costume)
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
                         "human_review": {"decision": "undecided", "notes": ""}} for item in run["candidates"]})
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

    def proceed(self, run_id: str, costume: str = "") -> dict[str, Any]:
        run = self.detail(run_id, costume)
        candidate_id = (run.get("selected_views") or {}).get("FRONT")
        if not candidate_id:
            raise LocalCharacterAssetPipelineError("Select the FRONT candidate before continuing.")
        anchor = next((item for item in run["candidates"] if item["candidate_id"] == candidate_id), None)
        if not anchor or anchor.get("human_review", {}).get("decision") != "keep":
            raise LocalCharacterAssetPipelineError("Review and pass the FRONT candidate before continuing.")
        anchor_image = Path(str(anchor.get("image_path") or ""))
        front_ranking = (run.get("rankings") or {}).get("FRONT") or {}
        if (not anchor_image.is_file() or front_ranking.get("status") != "COMPLETE"
                or candidate_id not in (front_ranking.get("ordered_candidate_ids") or [])
                or front_ranking.get("input_hashes", {}).get(candidate_id) != self._hash(anchor_image)
                or not self._candidate_gates_current(run, anchor)):
            raise LocalCharacterAssetPipelineError("Re-evaluate and rank FRONT before continuing with other views.")
        if run.get("front_anchor") != candidate_id:
            raise LocalCharacterAssetPipelineError("The selected FRONT candidate is not the current anchor.")
        if run.get("status") in ACTIVE_RUN_STATUSES:
            raise LocalCharacterAssetPipelineError("Wait for active batch work to finish before starting other views.")
        candidates_by_view = {
            view: [item for item in run["candidates"] if item["view"] == view]
            for view in VIEWS[1:]
        }
        target_views = {
            view for view, candidates in candidates_by_view.items()
            if candidates and all(item.get("status") == "PENDING" and not item.get("image_path") for item in candidates)
        }
        if not target_views:
            return {**run, "target_views": []}
        state_root, state = self._state(run_id, costume)
        state["front_anchor"] = candidate_id
        state["status"] = "READY_FOR_VIEWS"
        state["views_started"] = True
        # Claim these views before returning so a second request cannot queue them twice.
        for candidate in run["candidates"]:
            if candidate["view"] in target_views:
                state.setdefault("candidates", {}).setdefault(candidate["candidate_id"], {})["status"] = "QUEUED"
        self._write(state_root / "state.json", state)
        return {**self.detail(run_id, costume), "target_views": [view for view in VIEWS[1:] if view in target_views]}

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
        self._run_update(run_id, costume, status="CANCELLED", stop_requested=True)
        self._withdraw_queued_asks(run_id, costume)
        return self.detail(run_id, costume)

    def _withdraw_queued_asks(self, run_id: str, costume: str = "") -> None:
        run = self.detail(run_id, costume)
        paths = getattr(self.app, "ai_proxy_service", None)
        paths = getattr(paths, "ai_proxy_path_service", None)
        if paths is None:
            return
        ask_ids = set()
        for candidate in run.get("candidates", []):
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
                supersede_task(queue_root, task, "The local character pipeline run was stopped or deleted.")

    def resume(self, run_id: str, costume: str = "") -> dict[str, Any]:
        run = self.detail(run_id, costume)
        if run.get("status") != "INTERRUPTED":
            raise LocalCharacterAssetPipelineError("Only an interrupted run can be resumed.")
        self._run_update(run_id, costume, stop_requested=False, status="QUEUED")
        return self.detail(run_id, costume)
