from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import random
import re
import shutil
import threading
import time
from typing import Any
from uuid import uuid4

from PIL import Image

from Scripts.Run_Body_Reference_Jobs import compile_body_reference_job

from zet.services.local_candidate_review_contract import adjust_candidate_ranking, normalize_human_decision
from zet.services.local_image_ranking_service import rank_images_with_luna
from zet.services.local_render_backend_service import LocalRenderBackendService
from zet.services.local_asset_store_service import LocalAssetStoreService
from zet.services.library_reference_service import read_library_json, write_library_json
from zet.services.atomic_file_service import write_json_atomic
from zet.services.local_image_pipeline_policy import (
    ACTIVE_RUN_STATUSES, clear_candidate_artifacts, decorate_local_pipeline_detail, pipeline_page_config,
    mutate_local_run_state, resume_cancelled_autogenerate_state, serialize_local_run_state,
    view_candidate_id,
)
from zet.services.render_slot_service import merge_candidates, render_count, slot_maps, frozen_input, verify_input
from zet.services.workflow_storage import file_lock, supersede_task


class LocalBodyReferenceError(ValueError):
    """Raised when a Local Body-Reference cannot be planned safely."""


DEFAULT_VIEWS = (
    "FRONT", "FRONT_LEFT_3_4", "FRONT_RIGHT_3_4", "LEFT_PROFILE",
    "RIGHT_PROFILE", "BACK_LEFT_3_4", "BACK_RIGHT_3_4", "BACK",
)
CANONICAL_VIEW_DEFINITIONS = {
    "FRONT": "Direct frontal view. Subject faces the camera squarely; both sides are approximately symmetrical.",
    "FRONT_LEFT_3_4": "Frontal three-quarter view. The near side appears on IMAGE_RIGHT, and the face points toward IMAGE_LEFT.",
    "FRONT_RIGHT_3_4": "Frontal three-quarter view. The near side appears on IMAGE_LEFT, and the face points toward IMAGE_RIGHT.",
    "LEFT_PROFILE": "Exact profile showing the near side. Nose/face points toward IMAGE_LEFT.",
    "RIGHT_PROFILE": "Exact profile showing the near side. Nose/face points toward IMAGE_RIGHT.",
    "BACK_LEFT_3_4": "Rear three-quarter view. The near side appears on IMAGE_LEFT; head and body point away and toward IMAGE_LEFT.",
    "BACK_RIGHT_3_4": "Rear three-quarter view. The near side appears on IMAGE_RIGHT; head and body point away and toward IMAGE_RIGHT.",
    "BACK": "Direct rear view. Subject faces directly away from the camera; both sides are approximately symmetrical.",
}
ORIENTATION_VIEW_DEFINITIONS = {
    "FRONT": (
        "- This is a direct frontal view.\n"
        "- The face and torso point straight toward the camera.\n"
        "- Both sides of the front of the torso are visible and approximately symmetrical.\n"
        "- It must not be essentially a three-quarter view, profile, or rear view."
    ),
    "FRONT_LEFT_3_4": (
        "- This is a frontal three-quarter view.\n"
        "- The face and torso point diagonally toward IMAGE_LEFT.\n"
        "- The near side of the body appears on IMAGE_RIGHT.\n"
        "- The near side appears on IMAGE_RIGHT; the far side appears on IMAGE_LEFT.\n"
        "- Both the front and side of the torso are clearly visible.\n"
        "- It must not be essentially FRONT or LEFT PROFILE."
    ),
    "FRONT_RIGHT_3_4": (
        "- This is a frontal three-quarter view.\n"
        "- The face and torso point diagonally toward IMAGE_RIGHT.\n"
        "- The near side of the body appears on IMAGE_LEFT.\n"
        "- The near side appears on IMAGE_LEFT; the far side appears on IMAGE_RIGHT.\n"
        "- Both the front and side of the torso are clearly visible.\n"
        "- It must not be essentially FRONT or RIGHT PROFILE."
    ),
    "LEFT_PROFILE": (
        "- This is an exact side profile.\n"
        "- The face and torso point toward IMAGE_LEFT.\n"
        "- Show the near side in profile.\n"
        "- The front and back of the torso are not clearly visible.\n"
        "- It must not be essentially FRONT_LEFT_3_4 or BACK_LEFT_3_4."
    ),
    "RIGHT_PROFILE": (
        "- This is an exact side profile.\n"
        "- The face and torso point toward IMAGE_RIGHT.\n"
        "- Show the near side in profile.\n"
        "- The front and back of the torso are not clearly visible.\n"
        "- It must not be essentially FRONT_RIGHT_3_4 or BACK_RIGHT_3_4."
    ),
    "BACK_LEFT_3_4": (
        "- This is a rear three-quarter view.\n"
        "- The head and torso point away from the camera and diagonally toward IMAGE_LEFT.\n"
        "- The near side of the body appears on IMAGE_LEFT.\n"
        "- The near side appears on IMAGE_LEFT; the far side appears on IMAGE_RIGHT.\n"
        "- Both the back and side of the torso are clearly visible.\n"
        "- It must not be essentially BACK or LEFT PROFILE."
    ),
    "BACK_RIGHT_3_4": (
        "- This is a rear three-quarter view.\n"
        "- The head and torso point away from the camera and diagonally toward IMAGE_RIGHT.\n"
        "- The near side of the body appears on IMAGE_RIGHT.\n"
        "- The near side appears on IMAGE_RIGHT; the far side appears on IMAGE_LEFT.\n"
        "- Both the back and side of the torso are clearly visible.\n"
        "- It must not be essentially BACK or RIGHT PROFILE."
    ),
    "BACK": (
        "- This is a direct rear view.\n"
        "- The head and torso point straight away from the camera.\n"
        "- Both sides of the back of the torso are visible and approximately symmetrical.\n"
        "- It must not be essentially a three-quarter view, profile, or frontal view."
    ),
}


FRONT_VIEW = "FRONT"
METHOD_TEXT_FIRST = "text_first"
METHOD_FRONT_CONDITIONED = "front_conditioned"
PILOT_FRONT_COUNT = 8
PILOT_OTHER_COUNT = 4


class LocalBodyReferenceService:
    """Plan and persist a non-canonical Qwen Local Body-Reference.

    Each run owns its prompt snapshots, candidate slots, and decisions. It
    deliberately does not mutate canonical Assets or pipeline state.
    """

    RANKING_SCHEMA = {
        "type": "object",
        "properties": {"ranking": {"type": "array", "items": {
            "type": "object", "properties": {
                "candidate_id": {"type": "string"}, "reason": {"type": "string"},
            }, "required": ["candidate_id", "reason"], "additionalProperties": False,
        }}},
        "required": ["ranking"], "additionalProperties": False,
    }

    _active_runs: set[str] = set()
    _active_runs_lock = threading.Lock()

    def __init__(self, app: Any, project_root: str | Path):
        self.app = app
        self.project_root = Path(project_root).resolve()
        self.library_root = Path(app.config.base_library_path).resolve()
        self.runs_root = self.library_root / "PipelineCandidates" / "Character-Pipeline"
        self.asset_store = LocalAssetStoreService(self.library_root)
        self._runner_lock = threading.Lock()
        self._migrate_legacy_runs()

    def _active_key(self, run_id: str) -> str:
        return f"{self.library_root}::{run_id}"

    def _is_active(self, run_id: str) -> bool:
        key = self._active_key(run_id)
        return key in self._active_runs or (not hasattr(self.app.config, "universe_id") and run_id in self._active_runs)

    def _ask_belongs_to_run(self, ask: dict[str, Any], run: dict[str, Any]) -> bool:
        configured = str(getattr(self.app.config, "universe_id", "Moonsea"))
        legacy = bool(getattr(self.app.config, "universe_is_legacy", True))
        owner = str(ask.get("universe_id") or ("Moonsea" if legacy else "")).strip()
        run_owner = str(run.get("universe_id") or ("Moonsea" if legacy else "")).strip()
        return bool(owner) and owner == configured and run_owner == owner

    def _migrate_legacy_runs(self) -> None:
        """Upgrade stored run and queued-job identifiers to Local Body-Reference."""
        marker = self.runs_root / ".local_body_reference_migration_v1"
        if marker.exists():
            return
        identifier_replacements = {
            "BodyReferenceExperiment_": "LocalBodyReference_",
            "Character-Pipeline-Experiment": "Local-Body-Reference",
        }
        exact_replacements = {
            "body_reference_qwen_experiment": "local_body_reference",
            "body_reference_analysis": "local_body_reference_analysis",
        }
        key_replacements = {
            "body_reference_experiment_run_id": "local_body_reference_run_id",
            "body_reference_run_id": "local_body_reference_run_id",
        }

        def upgrade(value: Any) -> Any:
            if isinstance(value, dict):
                result = {}
                for key, item in value.items():
                    new_key = key_replacements.get(key, key) if isinstance(key, str) else key
                    if isinstance(new_key, str):
                        for old, new in identifier_replacements.items():
                            new_key = new_key.replace(old, new)
                    result[new_key] = upgrade(item)
                return result
            if isinstance(value, list):
                return [upgrade(item) for item in value]
            if isinstance(value, str):
                value = exact_replacements.get(value, value)
                for old, new in identifier_replacements.items():
                    value = value.replace(old, new)
            return value

        queue_root = Path(getattr(self.app.config, "base_ai_queue_path", self.library_root / "AI_Queue")).resolve()
        roots = [(self.runs_root, False), (queue_root, True)]
        for root, is_queue_root in roots:
            if not root.exists():
                continue
            for path in root.rglob("*.json"):
                if path == marker or path.name.endswith(".tmp"):
                    continue
                try:
                    original = self._read_json(path)
                except (OSError, json.JSONDecodeError):
                    continue
                upgraded = upgrade(original)
                if upgraded != original:
                    try:
                        self._write(path, upgraded)
                    except OSError:
                        # Queue bundles may be read-only or temporarily locked by
                        # Dropbox while answers are syncing. A legacy queue
                        # manifest should not prevent Zet from starting or
                        # rendering scenes; leave that queue file untouched.
                        if not is_queue_root:
                            raise
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(self._now() + "\n", encoding="utf-8")

    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat(timespec="seconds")

    @staticmethod
    def _hash(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _read_json(self, path: Path) -> dict[str, Any]:
        return read_library_json(path, self.library_root)

    def _write(self, path: Path, value: dict[str, Any]) -> None:
        if path.resolve().is_relative_to(self.runs_root.resolve()):
            write_library_json(path, value, self.library_root)
        else:
            write_json_atomic(path, value)

    @staticmethod
    def _safe(value: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip())
        return cleaned.strip("._") or "unknown"

    def _runner_is_active(self, run_id: str) -> bool:
        """Return whether a live process still owns this run's durable lock."""
        with self._active_runs_lock:
            if self._is_active(run_id):
                return True
        try:
            with file_lock(self._root(run_id) / "runner.lock", timeout=0):
                return False
        except TimeoutError:
            return True
    def _views(self) -> list[str]:
        path = self.project_root / "Config" / "Prompt_View_Text.json"
        try:
            payload = self._read_json(path)
            configured = payload.get("views", payload) if isinstance(payload, dict) else {}
            keys = [str(key).upper() for key in configured if str(key).strip()]
        except (OSError, json.JSONDecodeError):
            keys = []
        ordered = [view for view in DEFAULT_VIEWS if view in keys]
        return ordered + [view for view in keys if view not in ordered]

    def preview(self, payload: dict[str, Any]) -> dict[str, Any]:
        character = str(payload.get("character") or "").strip()
        phase = str(payload.get("phase") or "").strip()
        if not character or not phase:
            raise LocalBodyReferenceError("Character and phase are required.")
        status_loader = getattr(self.app, "character_onboarding_status", None)
        status = status_loader(character, phase) if callable(status_loader) else None
        if status is not None and not status.template_ready:
            raise LocalBodyReferenceError("A valid Character.md is required before local Body-Reference can run: " + "; ".join(status.validation_errors))
        views = self._views()
        if len(views) != 8:
            raise LocalBodyReferenceError(f"Expected eight configured Body-Reference views; found {len(views)}.")
        front_count = render_count(payload.get("front_count"), PILOT_FRONT_COUNT)
        other_count = render_count(payload.get("other_count"), PILOT_OTHER_COUNT)
        if front_count < 1 or other_count < 1:
            raise LocalBodyReferenceError("Candidate counts must be positive.")
        candidate_count = front_count + (len(views) - 1) * other_count
        if candidate_count > 256:
            raise LocalBodyReferenceError("Local Body-Reference cannot exceed 256 candidates.")
        return {
            "character": character,
            "phase": phase,
            "views": views,
            "front_count": front_count,
            "other_count": other_count,
            "candidate_count": candidate_count,
            "methods": [METHOD_FRONT_CONDITIONED],
            "front_anchor_required": True,
            "pipeline": "body-reference",
            "pipeline_config": pipeline_page_config("body-reference"),
            "can_create": True,
            "blocking_reasons": [],
        }

    def _compile_view(self, root: Path, character: str, phase: str, view: str, index: int) -> dict[str, Any]:
        output = root / "prompts" / view
        job = {
            "Job": f"LocalBodyReference_{root.name}_{view}",
            "Task": "body-reference",
            "Character": character,
            "Phase": phase,
            "Body View": view,
            "Output Directory": str(output),
        }
        try:
            result = compile_body_reference_job(
                job, self.project_root, pipeline_mode="local",
                universe_root=self.app.config.base_library_path,
            )
            analysis = self._compile_analysis_view(root, character, phase, view)
        except Exception as exc:
            raise LocalBodyReferenceError(f"Could not compile Body-Reference prompt for {view}: {exc}") from exc
        final_prompt = Path(str(result["final_prompt"]))
        if not final_prompt.is_file():
            raise LocalBodyReferenceError(f"Compiled prompt is missing for {view}: {final_prompt}")
        from zet.services.local_prompt_improvement_service import record_compiler_sources
        record_compiler_sources(output)
        text = final_prompt.read_text(encoding="utf-8")
        qwen_prompt = self._qwen_prompt(text, view)
        return {
            "view": view,
            "view_index": index,
            "manual_prompt": text,
            **analysis,
            "qwen_prompt": qwen_prompt,
            "prompt_path": str(final_prompt),
            "prompt_sha256": self._hash(final_prompt),
            "source_map": str(result.get("source_map") or ""),
            "dependency_manifest": str(result.get("dependency_manifest") or ""),
        }

    def _compile_analysis_view(self, root: Path, character: str, phase: str, view: str) -> dict[str, str]:
        output = root / "prompts" / view / "analysis"
        job = {
            "Job": f"LocalBodyReference_{root.name}_{view}",
            "Task": "body-reference",
            "Character": character,
            "Phase": phase,
            "Body View": view,
            "Output Directory": str(output),
        }
        result = compile_body_reference_job(
            job, self.project_root, prompt_variant="analysis", pipeline_mode="local",
            universe_root=self.app.config.base_library_path,
        )
        prompt_path = Path(str(result["final_prompt"]))
        if not prompt_path.is_file():
            raise LocalBodyReferenceError(f"Compiled analysis prompt is missing for {view}: {prompt_path}")
        template_path = self.project_root / "Config" / "Prompt_Templates" / "body_reference_v2.md"
        return {
            "analysis_specification": prompt_path.read_text(encoding="utf-8"),
            "analysis_prompt_path": str(prompt_path),
            "analysis_template_sha256": self._hash(template_path),
            "analysis_character_sha256": self._character_template_hash(character, phase),
        }

    def _character_template_hash(self, character: str, phase: str) -> str:
        base_path = getattr(self.app.config, "base_character_path", self.project_root / "Characters")
        path = Path(base_path) / character / phase / "Character.md"
        return self._hash(path) if path.is_file() else ""

    @staticmethod
    def _qwen_prompt(manual_prompt: str, view: str, anchor: bool = False) -> str:
        body = re.sub(r"\{\{[^}]+\}\}", "", manual_prompt)
        body = re.sub(r"^#+\s*", "", body, flags=re.MULTILINE)
        body = re.sub(r"\s+", " ", body).strip()
        instruction = (
            f"Create one full-body technical Body-Reference image in the exact {view.replace('_', ' ').lower()} view. "
            "Show the entire body from head to both soles, with a neutral standing pose, readable anatomy, "
            "the configured neutral fitment shell, a simplified neutral mannequin head, and a plain neutral studio background. "
            "Keep body proportions, species morphology, head-to-body scale, shoulder and hip structure, limb lengths, "
            "and fitment clothing consistent with the supplied character facts. Keep the mannequin head in scale with "
            "the body rather than enlarging it for portrait-style anime expression; do not add facial features or hair. "
            "Do not add costume details, props, weapons, "
            "dramatic action, cropping, text, shadows, or extra subjects."
        )
        if anchor:
            instruction = (
                "Use <image1> as the accepted front-view Qwen identity and proportion anchor. "
                + instruction.replace("Create one", "Edit the supplied identity anchor into one", 1)
                + " Preserve the anchor's body proportions while changing only the requested view."
            )
        return f"{instruction} Character facts: {body}"

    @staticmethod
    def compile_qwen_workflow(
        prompt: str,
        *,
        checkpoint: str,
        text_encoder: str,
        vae: str,
        seed: int,
        width: int = 832,
        height: int = 1216,
        steps: int = 40,
        anchor_path: str = "",
    ) -> dict[str, Any]:
        if not prompt.strip() or not checkpoint.strip() or not text_encoder.strip() or not vae.strip():
            raise LocalBodyReferenceError("Qwen workflow requires prompt, diffusion model, text encoder, and VAE.")
        workflow: dict[str, Any] = {
            "1": {"class_type": "UNETLoader", "inputs": {"unet_name": checkpoint, "weight_dtype": "default"}},
            "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": text_encoder, "type": "qwen_image"}},
            "3": {"class_type": "VAELoader", "inputs": {"vae_name": vae}},
        }
        encode: dict[str, Any] = {
            "clip": ["2", 0], "vae": ["3", 0], "prompt": prompt,
            "negative_prompt": "", "resolution": max(width, height),
        }
        if anchor_path:
            workflow["10"] = {"class_type": "LoadImage", "inputs": {"image": Path(anchor_path).name}}
            encode["images.image_1"] = ["10", 0]
        workflow["4"] = {"class_type": "TextEncodeQwenImage21", "inputs": encode}
        workflow["5"] = {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}}
        workflow["6"] = {"class_type": "KSampler", "inputs": {
            "seed": seed, "steps": steps, "cfg": 1.0, "sampler_name": "euler",
            "scheduler": "simple", "denoise": 1.0, "model": ["1", 0],
            "positive": ["4", 0], "negative": ["4", 1], "latent_image": ["5", 0],
        }}
        workflow["7"] = {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["3", 0]}}
        workflow["8"] = {"class_type": "SaveImage", "inputs": {"filename_prefix": "Zet_BodyReference", "images": ["7", 0]}}
        return workflow

    def create_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        plan = self.preview(payload)
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        root = self.runs_root / self._safe(plan["character"]) / self._safe(plan["phase"]) / run_id
        root.mkdir(parents=True, exist_ok=False)
        prompts = [self._compile_view(root, plan["character"], plan["phase"], view, index)
                   for index, view in enumerate(plan["views"], start=1)]
        seeds = payload.get("seeds")
        if not isinstance(seeds, list):
            generator = random.SystemRandom()
            seeds = [generator.randrange(0, 2**63 - 1) for _ in range(plan["candidate_count"])]
        if len(seeds) != plan["candidate_count"]:
            raise LocalBodyReferenceError("Explicit seed count must match the candidate plan.")
        try:
            seeds = [str(int(seed)) for seed in seeds]
        except (TypeError, ValueError) as exc:
            raise LocalBodyReferenceError("Every seed must be an integer.") from exc
        candidates: list[dict[str, Any]] = []
        seed_index = 0
        for view_index, prompt in enumerate(prompts):
            count_methods = ["shared_front"] if prompt["view"] == FRONT_VIEW else [METHOD_FRONT_CONDITIONED]
            count = plan["front_count"] if prompt["view"] == FRONT_VIEW else plan["other_count"]
            for method in count_methods:
                for ordinal in range(count):
                    candidate_id = view_candidate_id(prompt["view"], ordinal + 1)
                    candidate_prompt = prompt["qwen_prompt"]
                    if method == METHOD_FRONT_CONDITIONED:
                        candidate_prompt = self._qwen_prompt(prompt["manual_prompt"], prompt["view"], anchor=True)
                    candidates.append({
                        "candidate_id": candidate_id, "view": prompt["view"], "view_index": view_index + 1,
                        "method": method, "ordinal": ordinal + 1, "seed": str(seeds[seed_index]),
                        "prompt": candidate_prompt, "prompt_sha256": hashlib.sha256(candidate_prompt.encode()).hexdigest(),
                        "status": "PENDING", "image_path": "", "render_error": "",
                        "analyses": {}, "disposition": "pending", "human_review": {"decision": "undecided"},
                    })
                    seed_index += 1
        spec = {
            "schema_version": 2, "review_version": 3, "kind": "local_body_reference", "run_id": run_id,
            "universe_id": str(getattr(self.app.config, "universe_id", "Moonsea")),
            "batch_name": "",
            "created_at": self._now(), "status": "QUEUED", "character": plan["character"],
            "phase": plan["phase"], "views": plan["views"], "front_view": FRONT_VIEW,
            "front_count": plan["front_count"], "other_count": plan["other_count"],
            "candidate_count": len(candidates), "methods": plan["methods"], "seeds": [str(seed) for seed in seeds],
            "prompt_snapshots": prompts, "candidates": candidates,
            "source_snapshot_sha256": hashlib.sha256(json.dumps(prompts, sort_keys=True).encode()).hexdigest(),
            "front_anchor": None, "lineups": {}, "selected_views": {}, "rankings": {}, "created_by": "zet",
        }
        spec["slots_by_view"] = slot_maps(spec)
        self._write(root / "spec.json", spec)
        self._write(root / "state.json", {"run_id": run_id, "status": spec["status"], "updated_at": self._now(),
                                            "stop_requested": False, "candidates": {}, "rankings": {},
                                            "selected_views": {}})
        return {**spec, "root": str(root)}

    def _root(self, run_id: str) -> Path:
        if not re.fullmatch(r"\d{8}_\d{6}_\d{6}", str(run_id or "")):
            raise LocalBodyReferenceError("Invalid Local Body-Reference id.")
        matches = list(self.runs_root.glob(f"*/ */{run_id}".replace(" ", "")))
        if matches:
            return matches[0]
        for path in self.runs_root.glob(f"*/*/{run_id}"):
            if (path / "spec.json").is_file():
                return path
        raise LocalBodyReferenceError(f"Local Body-Reference not found: {run_id}")

    def detail(self, run_id: str) -> dict[str, Any]:
        root = self._root(run_id)
        value = self._read_json((root / "spec.json"))
        with file_lock(root / "state.lock"):
            state = self._read_json((root / "state.json")) if (root / "state.json").is_file() else {}
        from zet.services.local_prompt_improvement_service import ensure_view_reviews
        value, state = ensure_view_reviews(root, value, state)
        candidates = merge_candidates(value, state)
        stored_status = state.get("status") or value.get("status")
        interrupted = stored_status in {"PREFLIGHT", "RUNNING", "STOPPING", "REEVALUATING"} and not self._runner_is_active(run_id)
        value["status"] = "INTERRUPTED" if interrupted else stored_status
        value["review_version"] = int(value.get("review_version") or 1)
        value["interrupted"] = interrupted
        value["stop_requested"] = bool(state.get("stop_requested", False))
        value["review_only"] = bool(state.get("review_only", False))
        value["post_review_status"] = state.get("post_review_status") or ""
        value["error"] = state.get("error") or ("The Local Body-Reference runner stopped before this batch finished." if interrupted else "")
        value["front_anchor"] = state.get("front_anchor") or value.get("front_anchor")
        value["lineups"] = state.get("lineups") or value.get("lineups") or {}
        value["selected_views"] = state.get("selected_views") or value.get("selected_views") or {}
        value["rankings"] = state.get("rankings") or value.get("rankings") or {}
        value["view_reviews"] = state.get("view_reviews") or {}
        value["evaluations"] = state.get("evaluations") or value.get("evaluations") or {}
        value["slots_by_view"] = state.get("slots_by_view", value.get("slots_by_view", {}))
        value["slot_version"] = state.get("slot_version", 0)
        value["slot_work_pending"] = bool(state.get("slot_work_pending"))
        value["slot_render_ids"] = state.get("slot_render_ids") or []
        value["slot_review_views"] = state.get("slot_review_views") or []
        value["slot_collection_error"] = state.get("slot_collection_error", "")
        value["target_candidate_ids"] = state.get("target_candidate_ids") or []
        value["target_views"] = state.get("target_views") or []
        value["set_report"] = state.get("set_report") or {}
        if interrupted:
            for candidate in candidates.values():
                job = candidate.get("local_job") or {}
                if job.get("status") in {"QUEUED", "RUNNING"}:
                    job["status"] = "INTERRUPTED"
                    candidate["local_job"] = job
                if candidate.get("luna_status") in {"QUEUED", "RUNNING"}:
                    candidate["luna_status"] = "INTERRUPTED"
        value["candidates"] = list(candidates.values())
        stale_selections: list[str] = []
        by_id = {item["candidate_id"]: item for item in value["candidates"]}
        for view, ranking in (value.get("rankings") or {}).items():
            if view not in value.get("views", []):
                continue
            anchor = next((item for item in by_id.values() if item.get("candidate_id") == value.get("front_anchor")), None)
            anchor_image = Path(str(anchor.get("image_path") or "")) if anchor else None
            anchor_hash = self._hash(anchor_image) if view != FRONT_VIEW and anchor_image and anchor_image.is_file() else ""
            candidates_for_view = [item for item in by_id.values() if item.get("view") == view
                                   and item.get("human_review", {}).get("decision") != "reject"
                                   and Path(str(item.get("image_path") or "")).is_file()]
            current_hashes = {item["candidate_id"]: self._hash(Path(str(item["image_path"]))) for item in candidates_for_view}
            if ranking.get("status") in {"COMPLETE", "EMPTY"} and (
                    ranking.get("input_hashes") != current_hashes or ranking.get("anchor_hash", "") != anchor_hash):
                ranking.update(status="STALE", stale_reason="Candidate set or FRONT anchor changed after ranking.")
            selected_id = (value.get("selected_views") or {}).get(view)
            selected = by_id.get(selected_id)
            image = Path(str((selected or {}).get("image_path") or ""))
            if selected_id and (not selected or not image.is_file() or ranking.get("status") != "COMPLETE"
                                or selected_id not in (ranking.get("ordered_candidate_ids") or [])
                                or ranking.get("input_hashes", {}).get(selected_id) != self._hash(image)):
                stale_selections.append(view)
        value["stale_selections"] = stale_selections
        if stale_selections and value["status"] not in {"PREFLIGHT", "RUNNING", "STOPPING", "REEVALUATING", "ERROR"}:
            value["status"] = "REVIEW_REQUIRED"
        value["root"] = str(root)
        value["local_assets"] = self.asset_store.detail(
            str(value.get("character") or ""), str(value.get("phase") or "")
        ).get("assets", {})
        # Adopt legacy selected candidates into the local asset index without
        # moving their images or changing their selection/review state.
        for selected_view, selected_id in (value.get("selected_views") or {}).items():
            asset_key = self.asset_store.key("Body-Reference", selected_view)
            if asset_key in value["local_assets"]:
                continue
            selected_candidate = next((item for item in value.get("candidates", [])
                                       if item.get("candidate_id") == selected_id), None)
            selected_image = Path(str((selected_candidate or {}).get("image_path") or ""))
            if selected_candidate and selected_image.is_file():
                dependencies = []
                if selected_view != FRONT_VIEW:
                    anchor = next((item for item in value.get("candidates", [])
                                   if item.get("candidate_id") == value.get("front_anchor")), None)
                    anchor_image = Path(str((anchor or {}).get("image_path") or ""))
                    if anchor_image.is_file():
                        dependencies.append({
                            "key": self.asset_store.key("Body-Reference", FRONT_VIEW),
                            "image_sha256": self._hash(anchor_image),
                        })
                self.asset_store.record_batch_selection(
                    str(value["character"]), str(value["phase"]), "Body-Reference", selected_view,
                    candidate_id=str(selected_id), image_path=selected_image, batch_id=run_id,
                    dependencies=dependencies,
                )
        value["local_assets"] = self.asset_store.detail(
            str(value.get("character") or ""), str(value.get("phase") or "")
        ).get("assets", {})
        return decorate_local_pipeline_detail(value, "body-reference")

    def image_path(self, run_id: str, candidate_id: str) -> Path:
        run = self.detail(run_id)
        candidate = next((item for item in run["candidates"] if item["candidate_id"] == candidate_id), None)
        path = Path(str((candidate or {}).get("image_path") or "")).resolve()
        if not path.is_file() or not path.is_relative_to(Path(run["root"]).resolve()):
            raise LocalBodyReferenceError("Candidate image is unavailable.")
        return path

    def rename_run(self, run_id: str, batch_name: str) -> dict[str, Any]:
        name = str(batch_name or "").strip()
        if len(name) > 120:
            raise LocalBodyReferenceError("Batch name cannot exceed 120 characters.")
        root = self._root(run_id)
        spec_path = root / "spec.json"
        spec = self._read_json(spec_path)
        spec["batch_name"] = name
        self._write(spec_path, spec)
        return self.detail(run_id)

    def list_runs(self, character: str = "", phase: str = "") -> list[dict[str, Any]]:
        """Return selectable Local Body-Reference batches, newest first."""
        wanted_character = str(character or "").strip()
        wanted_phase = str(phase or "").strip()
        runs: list[dict[str, Any]] = []
        for spec_path in self.runs_root.glob("*/*/*/spec.json"):
            try:
                spec = self._read_json(spec_path)
                if wanted_character and spec.get("character") != wanted_character:
                    continue
                if wanted_phase and spec.get("phase") != wanted_phase:
                    continue
                run = self.detail(str(spec.get("run_id") or spec_path.parent.name))
            except (OSError, ValueError, json.JSONDecodeError, LocalBodyReferenceError):
                continue
            counts: dict[str, int] = {}
            for candidate in run.get("candidates") or []:
                status = str(candidate.get("status") or "UNKNOWN")
                counts[status] = counts.get(status, 0) + 1
            complete_count = (len(run.get("selected_views") or {}) if run.get("review_version", 1) >= 2
                              else counts.get("COMPLETE", 0))
            runs.append({
                "run_id": run["run_id"], "batch_name": run.get("batch_name", ""),
                "character": run.get("character", ""),
                "phase": run.get("phase", ""), "created_at": run.get("created_at", ""),
                "status": run.get("status", ""), "candidate_count": len(run.get("candidates") or []),
                "complete_count": complete_count, "front_anchor": run.get("front_anchor"),
                "source_run_id": run.get("source_run_id", ""),
            })
        return sorted(runs, key=lambda item: str(item.get("created_at") or item["run_id"]), reverse=True)

    def list_run_summaries(self, character: str = "", phase: str = "") -> list[dict[str, Any]]:
        """List batches without recalculating rankings or hashing candidate images."""
        wanted_character = str(character or "").strip()
        wanted_phase = str(phase or "").strip()
        runs: list[dict[str, Any]] = []
        for spec_path in self.runs_root.glob("*/*/*/spec.json"):
            try:
                spec = self._read_json(spec_path)
                if wanted_character and spec.get("character") != wanted_character:
                    continue
                if wanted_phase and spec.get("phase") != wanted_phase:
                    continue
                state_path = spec_path.with_name("state.json")
                state = self._read_json(state_path) if state_path.is_file() else {}
                run_id = str(spec.get("run_id") or spec_path.parent.name)
                status = str(state.get("status") or spec.get("status") or "UNKNOWN")
                if status in {"PREFLIGHT", "RUNNING", "STOPPING", "REEVALUATING"} and not self._runner_is_active(run_id):
                    status = "INTERRUPTED"
                candidates = merge_candidates(spec, state)
                selected = state.get("selected_views") or spec.get("selected_views") or {}
                counts: dict[str, int] = {}
                for candidate in candidates.values():
                    candidate_status = str(candidate.get("status") or "UNKNOWN")
                    counts[candidate_status] = counts.get(candidate_status, 0) + 1
                try:
                    review_version = int(spec.get("review_version") or 1)
                except (TypeError, ValueError):
                    review_version = 1
                runs.append({
                    "run_id": run_id, "batch_name": spec.get("batch_name", ""),
                    "character": spec.get("character", ""), "phase": spec.get("phase", ""),
                    "created_at": spec.get("created_at", ""), "status": status,
                    "candidate_count": len(candidates),
                    "complete_count": len(selected) if review_version >= 2 else counts.get("COMPLETE", 0),
                    "front_anchor": state.get("front_anchor") or spec.get("front_anchor"),
                    "source_run_id": spec.get("source_run_id", ""),
                    "selected_views": selected,
                })
            except (OSError, ValueError, json.JSONDecodeError, LocalBodyReferenceError):
                continue
        return sorted(runs, key=lambda item: str(item.get("created_at") or item["run_id"]), reverse=True)

    def list_codex_jobs(self) -> list[dict[str, Any]]:
        """Summarize Codex/Luna reviews across Local Body-Reference batches."""
        jobs = []
        for summary in self.list_runs():
            run = self.detail(summary["run_id"])
            if run.get("review_version", 1) >= 2:
                for view in run.get("views") or []:
                    ranking = (run.get("rankings") or {}).get(view) or {}
                    status = str(ranking.get("status") or "PENDING").upper()
                    jobs.append({
                        "run_id": run["run_id"], "candidate_id": "", "view": view,
                        "character": run.get("character", ""), "phase": run.get("phase", ""),
                        "status": status,
                        "details": str(ranking.get("error") or (
                            "Waiting for rendered candidates" if status == "PENDING" else ""
                        )),
                    })
                continue
            for candidate in run.get("candidates") or []:
                status = str(candidate.get("luna_status") or "").upper()
                if "luna" in (candidate.get("analyses") or {}):
                    status = "COMPLETE"
                elif status not in {"RUNNING", "FAILED"}:
                    status = "PENDING"
                jobs.append({
                    "run_id": run["run_id"], "candidate_id": candidate["candidate_id"],
                    "character": run.get("character", ""), "phase": run.get("phase", ""),
                    "view": candidate.get("view", ""), "status": status,
                    "details": (candidate.get("luna_error") or "") if status == "FAILED" else
                               ("Waiting for candidate image" if not Path(str(candidate.get("image_path") or "")).is_file()
                                and status == "PENDING" else ""),
                })
        return jobs

    def _refresh_compiled_prompts(self, run_id: str, views: set[str]) -> None:
        root = self._root(run_id).resolve()
        spec_path = root / "spec.json"
        spec = self._read_json(spec_path)
        snapshots = {str(item.get("view") or ""): item for item in spec.get("prompt_snapshots") or []}
        for index, view in enumerate(spec.get("views") or [], start=1):
            if view not in views:
                continue
            snapshot = snapshots.get(view)
            if snapshot is None:
                raise LocalBodyReferenceError(f"No saved prompt for view {view}.")
            refreshed = self._compile_view(root, str(spec["character"]), str(spec["phase"]), view, index)
            snapshot.update(refreshed)
            for candidate in spec.get("candidates") or []:
                if candidate.get("view") != view:
                    continue
                prompt = refreshed["qwen_prompt"]
                if candidate.get("method") == METHOD_FRONT_CONDITIONED:
                    prompt = self._qwen_prompt(refreshed["manual_prompt"], view, anchor=True)
                candidate["prompt"] = prompt
                candidate["prompt_sha256"] = hashlib.sha256(prompt.encode()).hexdigest()
        spec["source_snapshot_sha256"] = hashlib.sha256(
            json.dumps(spec["prompt_snapshots"], sort_keys=True).encode()
        ).hexdigest()
        self._write(spec_path, spec)
        def update_added(state):
            for candidate in (state.get("added_candidates") or {}).values():
                if candidate["candidate_id"] in (state.get("detached_candidates") or []):
                    continue
                view = candidate["view"]
                if view not in views:
                    continue
                refreshed = snapshots[view]
                prompt = refreshed["qwen_prompt"]
                if candidate.get("method") == METHOD_FRONT_CONDITIONED:
                    prompt = self._qwen_prompt(refreshed["manual_prompt"], view, anchor=True)
                candidate.update(prompt=prompt, prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest())
                state.setdefault("candidates", {}).setdefault(candidate["candidate_id"], {}).update(prompt=prompt, prompt_sha256=candidate["prompt_sha256"])
        mutate_local_run_state(root, update_added)

    def rerun(self, run_id: str, *, recompile: bool = False) -> dict[str, Any]:
        """Clear the current batch's generated candidates and reviews, then restart FRONT."""
        run = self.detail(run_id)
        if run.get("status") in ACTIVE_RUN_STATUSES or run.get("interrupted"):
            raise LocalBodyReferenceError("Wait for the current batch to finish or recover it before starting a fresh batch.")
        if self._runner_is_active(run_id):
            raise LocalBodyReferenceError("Wait for this batch to finish before starting a fresh run.")
        views = set(run.get("views", []))
        if recompile:
            self._refresh_compiled_prompts(run_id, views)
        for view in views:
            self.asset_store.assert_batch_change_allowed(
                run["character"], run["phase"], "Body-Reference", view
            )
        root = self._root(run_id).resolve()
        self._withdraw_queued_asks(run_id)
        for view in views:
            self._clear_owned_selection(run, view)
        state_path = root / "state.json"
        state = self._read_json(state_path)
        for candidate in run.get("candidates", []):
            clear_candidate_artifacts(root, candidate["candidate_id"], candidate.get("image_path"))
            state.setdefault("candidates", {}).setdefault(candidate["candidate_id"], {}).update(
                status="PENDING", render_input=None, seed=str(random.SystemRandom().randrange(0, 2**63 - 1)),
                image_path="", image_sha256="", ask_id="", queued_at="", completed_at="",
                render_error="", analyses={},
                disposition="pending",
                human_review={"decision": "undecided"}, local_job={},
                luna_status="PENDING", luna_error="", review_history=[], analysis_history=[],
                retry_count=int(candidate.get("retry_count") or 0) + 1,
            )
        state.update(
            status="RUNNING", front_anchor=None, target_views=[], target_candidate_ids=[],
            review_only=False, stop_requested=False, error="", lineups={}, set_report={},
            selected_views={}, rankings={}, ranking_history={}, updated_at=self._now(),
        )
        (root / "cancelled.json").unlink(missing_ok=True)
        self._save_state(run_id, state)
        result = self.detail(run_id)
        result.update(status="RUNNING", interrupted=False, error="")
        return result

    def rerun_view(self, run_id: str, view: str, *, recompile: bool = False) -> dict[str, Any]:
        """Replace the selected view's images and reviews in the existing batch."""
        run = self.detail(run_id)
        if int(run.get("review_version") or 1) < 2:
            raise LocalBodyReferenceError("View reruns require a version 2 Local Body-Reference batch.")
        view = str(view or "").upper()
        if view not in run.get("views", []):
            raise LocalBodyReferenceError(f"Unknown Local Body-Reference view: {view}")
        if run["status"] in {"PREFLIGHT", "RUNNING", "STOPPING", "REEVALUATING", "WAITING_FOR_ANALYSIS"}:
            raise LocalBodyReferenceError("Stop the active batch before re-running a view.")
        if self._runner_is_active(run_id):
            raise LocalBodyReferenceError("This Local Body-Reference batch is running; try again when it finishes.")
        candidates = [item for item in run["candidates"] if item.get("view") == view]
        if not candidates:
            raise LocalBodyReferenceError(f"This batch has no candidates for view {view}.")

        root = self._root(run_id).resolve()
        affected_views = (set(run.get("views", []))
                          if view == FRONT_VIEW and int(run.get("review_version") or 1) >= 2 else {view})
        if recompile:
            self._refresh_compiled_prompts(run_id, affected_views)
        for affected_view in affected_views:
            self.asset_store.assert_batch_change_allowed(run["character"], run["phase"], "Body-Reference", affected_view)
        state = self._read_json((root / "state.json"))
        stamp = self._now()
        from zet.services.local_image_evaluation_service import supersede_evaluations
        supersede_evaluations(state, affected_views, "A view or its inputs are being re-run.")
        self._withdraw_queued_asks(run_id, affected_views=affected_views)
        for affected_view in affected_views:
            self._clear_owned_selection(run, affected_view)
        affected_candidates = [item for item in run["candidates"] if item.get("view") in affected_views]
        for affected in affected_candidates:
            clear_candidate_artifacts(root, affected["candidate_id"], affected.get("image_path"))
            state.setdefault("candidates", {}).setdefault(affected["candidate_id"], {}).update(
                status="PENDING", render_input=None, seed=str(random.SystemRandom().randrange(0, 2**63 - 1)),
                image_path="", image_sha256="", ask_id="", queued_at="", completed_at="",
                render_error="", analyses={},
                disposition="pending", human_review={"decision": "undecided"},
                retry_count=int(affected.get("retry_count") or 0) + 1,
            )
        if int(run.get("review_version") or 1) >= 2:
            for affected_view in affected_views:
                state.setdefault("rankings", {}).pop(affected_view, None)
                state.setdefault("selected_views", {}).pop(affected_view, None)
        if view != FRONT_VIEW:
            for selections in (state.get("lineups") or {}).values():
                selections.pop(view, None)
        state["lineups"] = {}
        state["set_report"] = {}

        if view == FRONT_VIEW:
            state["front_anchor"] = None
            state["ranking_history"] = {}
        (root / "cancelled.json").unlink(missing_ok=True)
        state.update(
            status="RUNNING", review_only=False, target_views=[view],
            target_candidate_ids=[item["candidate_id"] for item in candidates], stop_requested=False,
            error="", updated_at=stamp,
        )
        self._save_state(run_id, state)
        result = self.detail(run_id)
        result.update(status="RUNNING", interrupted=False, error="")
        return result
    def rerun_failed_view(self, run_id: str, view: str) -> dict[str, Any]:
        """Regenerate failed candidates in one view and clear their reviews."""
        run = self.detail(run_id)
        view = str(view or "").upper()
        if view not in run.get("views", []):
            raise LocalBodyReferenceError(f"Unknown Local Body-Reference view: {view}")
        self.asset_store.assert_batch_change_allowed(run["character"], run["phase"], "Body-Reference", view)
        if run["status"] in {"PREFLIGHT", "RUNNING", "STOPPING", "REEVALUATING", "WAITING_FOR_ANALYSIS"}:
            raise LocalBodyReferenceError("Stop the active batch before re-running a view.")
        if self._runner_is_active(run_id):
            raise LocalBodyReferenceError("This Local Body-Reference batch is running; try again when it finishes.")

        def is_failed_candidate(candidate: dict[str, Any]) -> bool:
            if candidate.get("view") != view:
                return False
            if int(run.get("review_version") or 1) >= 2:
                return (candidate.get("status") in {"FAILED"}
                        or candidate.get("human_review", {}).get("decision") == "reject")
            if not Path(str(candidate.get("image_path") or "")).is_file():
                return False
            if candidate.get("status") != "COMPLETE":
                return False
            human_decision = (candidate.get("human_review") or {}).get("decision", "undecided")
            if human_decision == "reject":
                return True
            analyses = candidate.get("analyses") or {}
            local, luna = analyses.get("local") or {}, analyses.get("luna") or {}
            return (
                human_decision == "undecided"
                and local.get("pass") is False and not local.get("uncertain", False)
                and luna.get("pass") is False and not luna.get("uncertain", False)
            )

        candidates = [item for item in run["candidates"] if is_failed_candidate(item)]
        if not candidates:
            raise LocalBodyReferenceError(f"This batch has no failed images to re-run for view {view}.")

        root = self._root(run_id).resolve()
        self.asset_store.assert_batch_change_allowed(run["character"], run["phase"], "Body-Reference", view)
        state = self._read_json((root / "state.json"))
        from zet.services.local_image_evaluation_service import supersede_evaluations
        supersede_evaluations(state, {view}, "Candidates in this view are being re-run.")
        stamp = self._now()
        self._withdraw_queued_asks(run_id, candidate_ids={item["candidate_id"] for item in candidates})
        self._clear_owned_selection(run, view)
        candidate_ids = [item["candidate_id"] for item in candidates]
        if int(run.get("review_version") or 1) >= 2:
            state.setdefault("selected_views", {}).pop(view, None)
            state.setdefault("rankings", {}).pop(view, None)
        for candidate in candidates:
            clear_candidate_artifacts(root, candidate["candidate_id"], candidate.get("image_path"))
            update = state.setdefault("candidates", {}).setdefault(candidate["candidate_id"], {})
            update.update(
                status="PENDING", render_input=None, seed=str(random.SystemRandom().randrange(0, 2**63 - 1)),
                image_path="", image_sha256="", ask_id="", queued_at="",
                completed_at="", render_error="", analyses={}, analysis_history=[], review_history=[],
                ranking_history=[], local_job={}, luna_status="",
                luna_error="", disposition="pending", human_review={"decision": "undecided"},
                retry_count=int(candidate.get("retry_count") or 0) + 1,
            )

        if view == FRONT_VIEW and state.get("front_anchor") in candidate_ids:
            state["front_anchor"] = None
            state["lineups"] = {}
            state["set_report"] = {}
            if int(run.get("review_version") or 1) >= 2:
                state.setdefault("selected_views", {}).pop(FRONT_VIEW, None)
                old_rank = state.setdefault("rankings", {}).pop(FRONT_VIEW, None)
                if old_rank:
                    state.setdefault("ranking_history", {}).setdefault(FRONT_VIEW, []).append(
                        {"archived_at": stamp, "ranking": old_rank}
                    )
                self._invalidate_views_after_anchor_change(run_id, state)
        else:
            if int(run.get("review_version") or 1) >= 2:
                state.setdefault("selected_views", {}).pop(view, None)
                old_rank = state.setdefault("rankings", {}).pop(view, None)
                if old_rank:
                    state.setdefault("ranking_history", {}).setdefault(view, []).append(
                        {"archived_at": stamp, "ranking": old_rank}
                    )
            for selections in (state.get("lineups") or {}).values():
                selections.pop(view, None)
            state["set_report"] = {}
        (root / "cancelled.json").unlink(missing_ok=True)
        state.update(
            status="RUNNING", review_only=False, target_views=[view],
            target_candidate_ids=candidate_ids, stop_requested=False, error="", updated_at=stamp,
        )
        self._save_state(run_id, state)
        result = self.detail(run_id)
        result.update(status="RUNNING", interrupted=False, error="")
        return result

    def reevaluate(self, run_id: str, view: str | None = None) -> dict[str, Any]:
        """Re-run visual reviewers on completed images in the existing batch."""
        run = self.detail(run_id)
        target_views = list(run.get("views", []))
        if view is not None:
            normalized_view = str(view or "").upper()
            if normalized_view not in target_views:
                raise LocalBodyReferenceError(f"Unknown Local Body-Reference view: {normalized_view}")
            target_views = [normalized_view]
        for target_view in target_views:
            self.asset_store.assert_batch_change_allowed(run["character"], run["phase"], "Body-Reference", target_view)
        if run["status"] in {"PREFLIGHT", "RUNNING", "STOPPING", "REEVALUATING", "WAITING_FOR_ANALYSIS"}:
            raise LocalBodyReferenceError("Stop the active batch before re-evaluating it.")
        if self._runner_is_active(run_id):
            raise LocalBodyReferenceError("This Local Body-Reference batch is running; try again when it finishes.")
        if int(run.get("review_version") or 1) >= 2:
            completed = [item for item in run["candidates"] if item.get("view") in target_views
                         and item.get("status") in {"COMPLETE", "WAITING_FOR_HUMAN_REVIEW", "FAILED"}
                         and Path(str(item.get("image_path") or "")).is_file()]
        else:
            completed = [item for item in run["candidates"]
                         if (item.get("status") == "COMPLETE" or
                             (run.get("interrupted") and item.get("status") == "WAITING_FOR_ANALYSIS"))
                         and item.get("view") in target_views
                         and Path(str(item.get("image_path") or "")).is_file()]
        if not completed:
            scope = f" for view {target_views[0]}" if view is not None else ""
            raise LocalBodyReferenceError(f"This batch has no completed images to re-evaluate{scope}.")
        for target_view in target_views:
            self._review_facts(run, target_view)
        if int(run.get("review_version") or 1) >= 2:
            state = self._read_json((self._root(run_id) / "state.json"))
            stamp = self._now()
            from zet.services.local_image_evaluation_service import supersede_evaluations
            supersede_evaluations(state, set(target_views), "The view is being re-evaluated.")
            for target_view in target_views:
                old_ranking = state.setdefault("rankings", {}).pop(target_view, None)
                if old_ranking:
                    state.setdefault("ranking_history", {}).setdefault(target_view, []).append(
                        {"archived_at": stamp, "ranking": old_ranking}
                    )
            for candidate in completed:
                update = state.setdefault("candidates", {}).setdefault(candidate["candidate_id"], {})
                update.update(status="WAITING_FOR_HUMAN_REVIEW",
                              render_error="", completed_at="")
            (self._root(run_id) / "cancelled.json").unlink(missing_ok=True)
            state.update(status="REEVALUATING", review_only=True, target_views=target_views,
                         target_candidate_ids=[item["candidate_id"] for item in completed],
                         stop_requested=False, post_review_status=run["status"], error="", updated_at=stamp)
            self._save_state(run_id, state)
            result = self.detail(run_id)
            result.update(status="REEVALUATING", interrupted=False, error="")
            return result
        state = self._read_json((self._root(run_id) / "state.json"))
        stamp = self._now()
        from zet.services.local_image_evaluation_service import supersede_evaluations
        supersede_evaluations(state, set(target_views), "The view is being re-evaluated.")
        for candidate in completed:
            update = state.setdefault("candidates", {}).setdefault(candidate["candidate_id"], {})
            old = candidate.get("analyses") or {}
            if old:
                history = list(candidate.get("analysis_history") or [])
                history.append({"archived_at": stamp, "analyses": old})
                update["analysis_history"] = history
            decision = (candidate.get("human_review") or {}).get("decision")
            update.update(status="WAITING_FOR_ANALYSIS", completed_at="", analyses={}, local_job={}, luna_status="PENDING", luna_error="",
                          disposition="human_keep" if decision == "keep" else
                          "human_reject" if decision == "reject" else "pending")
        (self._root(run_id) / "cancelled.json").unlink(missing_ok=True)
        state.update(status="REEVALUATING", review_only=True, target_views=target_views,
                     target_candidate_ids=[item["candidate_id"] for item in completed],
                     stop_requested=False, post_review_status=run["status"], error="", updated_at=stamp)
        self._save_state(run_id, state)
        result = self.detail(run_id)
        result.update(status="REEVALUATING", interrupted=False, error="")
        return result
    def delete_run(self, run_id: str) -> dict[str, Any]:
        root = self._root(run_id).resolve()
        runs_root = self.runs_root.resolve()
        if (root.parent.parent.parent != runs_root or root.name != run_id
                or not root.is_relative_to(runs_root)):
            raise LocalBodyReferenceError("Invalid Local Body-Reference batch location.")
        run = self.detail(run_id)
        candidates = {item["candidate_id"]: item for item in run.get("candidates", [])}
        active_selections = {
            view: candidate_id
            for view, candidate_id in (run.get("selected_views") or {}).items()
            if (candidate := candidates.get(candidate_id))
            and candidate.get("view") == view
            and Path(str(candidate.get("image_path") or "")).is_file()
        }
        # Older selection flows could clear state.json but leave an unlocked
        # batch-owned record in local_assets.json. Reconcile those invisible
        # records before applying the delete guard.
        for record in run.get("local_assets", {}).values():
            if (record.get("selected") and record.get("batch_id") == run_id
                    and not record.get("locked")
                    and active_selections.get(record.get("view")) != record.get("candidate_id")):
                self.asset_store.clear_batch_selection(
                    run["character"], run["phase"], "Body-Reference", record["view"], run_id,
                    str(record.get("qualifier") or ""),
                )
        run = self.detail(run_id)
        if any(record.get("selected") and record.get("batch_id") == run_id and not record.get("locked")
               for record in run.get("local_assets", {}).values()):
            raise LocalBodyReferenceError("Lock or unselect this batch's local assets before deleting it.")
        if self._runner_is_active(run_id):
            raise LocalBodyReferenceError("Wait for the batch runner to finish before deleting it.")
        self._withdraw_queued_asks(run_id)
        shutil.rmtree(root)
        return {"deleted": True, "run_id": run_id}

    def _save_state(self, run_id: str, state: dict[str, Any]) -> None:
        root = self._root(run_id)
        if (root / "cancelled.json").is_file():
            state.update(status="CANCELLED", stop_requested=True, error="Cancelled by user.")
        self._write(root / "state.json", state)

    def _clear_owned_selection(self, run: dict[str, Any], view: str) -> None:
        self.asset_store.clear_batch_selection(
            run["character"], run["phase"], "Body-Reference", view, run["run_id"]
        )

    def _withdraw_queued_asks(self, run_id: str, *, affected_views: set[str] | None = None,
                              candidate_ids: set[str] | None = None) -> None:
        paths = getattr(getattr(self.app, "ai_proxy_service", None), "ai_proxy_path_service", None)
        if paths is None:
            return
        queue_root = Path(self.app.config.base_ai_queue_path)
        prefixes = (f"BodyReference_{run_id}_", f"Ask_LocalBodyReference_{run_id}_")
        for task in paths.task_paths("ask"):
            if not task.name.startswith(prefixes):
                continue
            matched = next((item for item in self.detail(run_id)["candidates"]
                            if f"_{item['candidate_id']}_" in task.name), None)
            if matched and (affected_views is None or matched["view"] in affected_views) and \
                    (candidate_ids is None or matched["candidate_id"] in candidate_ids):
                supersede_task(queue_root, task, "Local Body-Reference candidate is being replaced.", state_root=self.app.ai_proxy_service.ai_proxy_path_service.lifecycle.storage_root)

    def select_front_anchor(self, run_id: str, candidate_id: str) -> dict[str, Any]:
        run = self.detail(run_id)
        if run.get("review_version", 1) >= 2:
            return self.select_view(run_id, FRONT_VIEW, candidate_id)
        candidate = next((item for item in run["candidates"] if item["candidate_id"] == candidate_id), None)
        if not candidate or candidate["view"] != FRONT_VIEW:
            raise LocalBodyReferenceError("Only a front-view candidate can become the anchor.")
        if candidate.get("status") != "COMPLETE":
            raise LocalBodyReferenceError("The front anchor must have a completed render.")
        if candidate.get("human_review", {}).get("decision") != "keep":
            raise LocalBodyReferenceError("A human must keep the front anchor after both analyses.")
        if not all(candidate.get("analyses", {}).get(provider) for provider in ("local", "luna")):
            raise LocalBodyReferenceError("Both image analyses must finish before selecting the front anchor.")
        image_hash = self._hash(Path(candidate["image_path"]))
        if any(candidate["analyses"][provider].get("input_hashes", {}).get("candidate") != image_hash
               for provider in ("local", "luna")):
            raise LocalBodyReferenceError("Front-anchor analysis is stale; rerun both analyses.")
        state = self._read_json((self._root(run_id) / "state.json"))
        state.update({"status": "READY_FOR_VIEWS", "updated_at": self._now(),
                      "front_anchor": candidate_id, "stop_requested": False,
                      "target_views": [], "target_candidate_ids": []})
        self._save_state(run_id, state)
        return self.detail(run_id)

    def update_candidate(self, run_id: str, candidate_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        run = self.detail(run_id)
        candidate = next((item for item in run["candidates"] if item["candidate_id"] == candidate_id), None)
        if candidate is None:
            raise LocalBodyReferenceError(f"Unknown candidate: {candidate_id}")
        self.asset_store.assert_batch_change_allowed(run["character"], run["phase"], "Body-Reference", candidate["view"])
        if run.get("review_version", 1) >= 2:
            try:
                decision = normalize_human_decision(payload.get("decision"))
            except ValueError as exc:
                raise LocalBodyReferenceError(str(exc)) from exc
            image = Path(str(candidate.get("image_path") or ""))
            if not image.is_file():
                raise LocalBodyReferenceError("The candidate must have a completed image before human review.")
            root = self._root(run_id)
            disposition = "human_keep" if decision == "keep" else "human_reject" if decision == "reject" else "pending"
            def apply(state: dict[str, Any]) -> None:
                state.setdefault("candidates", {}).setdefault(candidate_id, {}).update(
                    human_review={"decision": decision}, disposition=disposition,
                    status=candidate.get("status"),
                )
                state["updated_at"] = self._now()
            mutate_local_run_state(root, apply)
            return self.detail(run_id)
        try:
            decision = normalize_human_decision(payload.get("decision"))
        except ValueError as exc:
            raise LocalBodyReferenceError(str(exc)) from exc
        update = {"human_review": {"decision": decision}}
        if candidate.get("status") not in {"WAITING_FOR_HUMAN_REVIEW", "COMPLETE"} or not all(
            candidate.get("analyses", {}).get(provider) for provider in ("local", "luna")
        ):
            raise LocalBodyReferenceError("Both image analyses must finish before human review.")
        decision = update["human_review"]["decision"]
        if decision == "keep":
            update.update(disposition="human_keep", status="COMPLETE", completed_at=self._now())
        elif decision == "reject":
            update.update(disposition="human_reject", status="COMPLETE", completed_at=self._now())
        else:
            update.update(status="WAITING_FOR_HUMAN_REVIEW", completed_at="")
        state = self._read_json((self._root(run_id) / "state.json"))
        state.setdefault("candidates", {}).setdefault(candidate_id, {}).update(update)
        merged_statuses = {item["candidate_id"]: item.get("status") for item in run.get("candidates") or []}
        merged_statuses[candidate_id] = update.get("status", candidate.get("status"))
        if state.get("front_anchor") and merged_statuses and all(status == "COMPLETE" for status in merged_statuses.values()):
            state.update(status="COMPLETE", target_views=[], target_candidate_ids=[], review_only=False)
        state["updated_at"] = self._now()
        self._save_state(run_id, state)
        return self.detail(run_id)

    def record_analysis(
        self,
        run_id: str,
        candidate_id: str,
        provider: str,
        result: dict[str, Any],
        input_hashes: dict[str, str],
    ) -> dict[str, Any]:
        if provider not in {"local", "luna"}:
            raise LocalBodyReferenceError("Analysis provider must be local or luna.")
        if not isinstance(result, dict) or not isinstance(input_hashes, dict):
            raise LocalBodyReferenceError("Analysis result and input hashes must be objects.")
        if "pass" not in result or not isinstance(result.get("pass"), bool):
            raise LocalBodyReferenceError("Analysis result must include a boolean pass field.")
        if (not isinstance(result.get("uncertain"), bool)
                or not isinstance(result.get("criteria"), dict)
                or not isinstance(result.get("failure_categories"), list)
                or not isinstance(result.get("evidence"), str)
                or not isinstance(result.get("failure_reason"), str)):
            raise LocalBodyReferenceError("Analysis result is missing structured rubric fields.")
        run = self.detail(run_id)
        candidate = next((item for item in run["candidates"] if item["candidate_id"] == candidate_id), None)
        if candidate is None:
            raise LocalBodyReferenceError(f"Unknown candidate: {candidate_id}")
        image = Path(str(candidate.get("image_path") or ""))
        if candidate.get("status") not in {"WAITING_FOR_ANALYSIS", "WAITING_FOR_HUMAN_REVIEW", "COMPLETE"} or not image.is_file():
            raise LocalBodyReferenceError("Analysis requires a rendered candidate image.")
        if input_hashes.get("candidate") != self._hash(image):
            raise LocalBodyReferenceError("Analysis input hash does not match the candidate image.")
        if candidate["view"] != FRONT_VIEW:
            anchor = next((item for item in run["candidates"] if item["candidate_id"] == run.get("front_anchor")), None)
            anchor_image = Path(str(anchor.get("image_path") or "")) if anchor else None
            if anchor_image is None or not anchor_image.is_file() or input_hashes.get("front_anchor") != self._hash(anchor_image):
                raise LocalBodyReferenceError("Analysis front-anchor hash is missing or stale.")
        analysis = {**result, "provider": provider, "input_hashes": dict(input_hashes), "recorded_at": self._now()}
        state = self._read_json((self._root(run_id) / "state.json"))
        updates = state.setdefault("candidates", {}).setdefault(candidate_id, {})
        analyses = dict(updates.get("analyses") or candidate.get("analyses") or {})
        analyses[provider] = analysis
        updates["analyses"] = analyses
        if "local" in analyses and "luna" in analyses:
            updates["status"] = "WAITING_FOR_HUMAN_REVIEW"
            decision = (candidate.get("human_review") or {}).get("decision")
            updates["disposition"] = ("human_keep" if decision == "keep" else
                                      "human_reject" if decision == "reject" else
                                      self.disposition(analyses["local"], analyses["luna"]))
        state["updated_at"] = self._now()
        self._save_state(run_id, state)
        return self.detail(run_id)

    @staticmethod
    def analysis_schema() -> dict[str, Any]:
        criterion = {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["pass", "fail", "uncertain"]},
                "evidence": {"type": "string"},
            },
            "required": ["status", "evidence"],
            "additionalProperties": False,
        }
        names = (
            "view", "head_body_alignment", "full_body_crop", "stance", "anatomy",
            "fitment", "background", "body_facts", "head_body_scale",
            "torso_leg_balance", "limb_lengths", "shoulder_hip_structure",
            "body_mass", "species_morphology",
        )
        return {
            "type": "object",
            "properties": {
                "pass": {"type": "boolean"},
                "uncertain": {"type": "boolean"},
                "criteria": {"type": "object", "properties": {name: criterion for name in names},
                             "required": list(names), "additionalProperties": False},
                "failure_categories": {"type": "array", "items": {"type": "string"}},
                "failure_reason": {"type": "string", "description": "A short reason when pass is false; empty when pass is true."},
                "evidence": {"type": "string"},
                "proportion_notes": {"type": "string"},
            },
            "required": ["pass", "uncertain", "criteria", "failure_categories", "failure_reason", "evidence", "proportion_notes"],
            "additionalProperties": False,
        }
    @staticmethod
    def analysis_prompt(candidate: dict[str, Any], *, anchor: bool = False, facts: str = "") -> str:
        view = str(candidate.get("view") or "")
        view_definition = CANONICAL_VIEW_DEFINITIONS.get(view, "")
        reference_directive = (
            "Image 1 is the accepted front anchor; Image 2 is the candidate. "
            "Compare the candidate with the front anchor for consistent body proportions, species morphology, "
            "and fitment clothing while judging the requested orientation from the candidate. "
            if anchor else "Judge the candidate image against the requested view and written specification. "
        )
        return (
            "You are a Body-Reference visual QA reviewer. Determine whether the candidate is a usable technical "
            "body reference that materially satisfies the supplied specification. Judge only visible evidence. "
            + reference_directive
            + "The specification includes essential requirements and generation guidance; do not treat every "
            "sentence as an equally weighted pass/fail criterion. Assess each primary property independently "
            "without presuming a defect exists. PRIMARY requirements are believable head-to-body and overall "
            "anatomical proportions, neck attachment, torso-to-leg balance, limb lengths, body mass, shoulder/hip "
            "structure, exact requested body and head orientation, complete framing, neutral readable stance, "
            "required species morphology, and mannequin-head requirements. A clear violation of a PRIMARY "
            "requirement is a failure. SECONDARY requirements include fitment-clothing details, studio background, "
            "lighting, minor color variation, seams, and presentation details. Fail a SECONDARY deviation only "
            "when it materially interferes with silhouette, anatomical readability, pose evaluation, or usefulness "
            "as a technical body reference. Incidental differences alone are not failures: faint diffuse floor "
            "or contact shadows, subtle background gradients, minor seams, and small color deviations are acceptable. "
            "Fail shadowing only if it obscures anatomy, confuses the feet or silhouette, or substantially disrupts "
            "a neutral technical presentation. For head-to-body scale, evaluate the cranial or mannequin head mass, "
            "not species appendages or external extensions. For an elf, exclude pointed ears and ear-tip span from "
            "head-width estimates; compare the skull or face oval with the shoulders, torso, and total body height. "
            "A wide ear-tip span is not evidence of an oversized head. Distinguish apparent width from perspective, "
            "pose, hair, clothing, headgear, horns, or other protrusions from underlying anatomical proportion. "
            "Before failing, ask whether correction of the visible defect would materially improve usefulness as "
            "a technical body reference. If not, it is insufficient for failure. Simple fitment clothing specified "
            "below, including a tube top and compression shorts when requested, is not costume. Variation in its "
            "cut or seams is low priority; fail fitment only if it obscures the body silhouette or adds substantial "
            "unrequested garments. When a featureless mannequin head is specified, facial features, hair, or "
            "character likeness are material failures. Use uncertain only when an important PRIMARY visual trait "
            "truly cannot be judged. A clear visual pass must have pass=true and uncertain=false. If uncertain=true, "
            "set pass=false and explain the unresolved primary trait. Return pass=false only for a visible PRIMARY "
            "violation or a SECONDARY defect severe enough to materially compromise the body reference. When "
            "failing, identify the single most consequential material defect in failure_reason and cite its visible "
            "evidence. Do not fail solely because a minor deviation can be detected. Return only the requested JSON object."
            "\n\nRequested view: " + view
            + "\n\nView labels refer to the SUBJECT'S ANATOMICAL side. IMAGE_LEFT and IMAGE_RIGHT refer to directions on the rendered image. These definitions override any alternate naming convention."
            + "\n\nCanonical " + view + " Definition: " + view_definition
            + "\n\nAuthoritative Body-Reference specification:\n" + facts
        )

    def _review_facts(self, run: dict[str, Any], view: str) -> str:
        prompt = next((item for item in run.get("prompt_snapshots", []) if item.get("view") == view), {})
        template_path = self.project_root / "Config" / "Prompt_Templates" / "body_reference_v2.md"
        if not template_path.is_file():
            return str(prompt.get("analysis_specification") or prompt.get("manual_prompt") or "")
        template_hash = self._hash(template_path)
        character_hash = self._character_template_hash(str(run["character"]), str(run["phase"]))
        if (prompt.get("analysis_template_sha256") == template_hash
                and prompt.get("analysis_character_sha256", "") == character_hash
                and prompt.get("analysis_specification")):
            return str(prompt["analysis_specification"])

        root = Path(str(run["root"]))
        spec_path = root / "spec.json"
        with file_lock(root / "analysis_prompt.lock"):
            spec = self._read_json(spec_path)
            snapshot = next((item for item in spec.get("prompt_snapshots", []) if item.get("view") == view), None)
            if snapshot is None:
                raise LocalBodyReferenceError(f"No saved prompt for view {view}.")
            if (snapshot.get("analysis_template_sha256") != template_hash
                    or snapshot.get("analysis_character_sha256", "") != character_hash
                    or not snapshot.get("analysis_specification")):
                try:
                    snapshot.update(self._compile_analysis_view(root, spec["character"], spec["phase"], view))
                except Exception as exc:
                    raise LocalBodyReferenceError(f"Could not refresh analysis prompt for {view}: {exc}") from exc
                spec["source_snapshot_sha256"] = hashlib.sha256(
                    json.dumps(spec["prompt_snapshots"], sort_keys=True).encode()
                ).hexdigest()
                self._write(spec_path, spec)
            return str(snapshot["analysis_specification"])

    def review_prompt(self, run_id: str, view: str) -> str:
        """Return the shared local/Codex review prompt for one Local Body-Reference view."""
        run = self.detail(run_id)
        if view not in run.get("views", []):
            raise LocalBodyReferenceError(f"Unknown Local Body-Reference view: {view}")
        candidate = {"view": view}
        return self.analysis_prompt(
            candidate,
            anchor=view != FRONT_VIEW,
            facts=self._review_facts(run, view),
        )

    def image_prompt(self, run_id: str, view: str) -> str:
        run = self.detail(run_id)
        if view not in run.get("views", []):
            raise LocalBodyReferenceError(f"Unknown Local Body-Reference view: {view}")
        snapshot = next((item for item in run.get("prompt_snapshots") or [] if item["view"] == view), None)
        path = Path(str((snapshot or {}).get("prompt_path") or ""))
        if not path.is_file():
            raise LocalBodyReferenceError(f"No current image prompt is saved for view {view}.")
        return self._qwen_prompt(path.read_text(encoding="utf-8"), view, anchor=view != FRONT_VIEW)

    @serialize_local_run_state
    def queue_local_analysis(self, run_id: str, candidate_id: str, model: str = "") -> dict[str, Any]:
        run = self.detail(run_id)
        candidate = next((item for item in run["candidates"] if item["candidate_id"] == candidate_id), None)
        if (not candidate or candidate.get("status") not in {"WAITING_FOR_ANALYSIS", "WAITING_FOR_HUMAN_REVIEW", "COMPLETE"}
                or not Path(str(candidate.get("image_path") or "")).is_file()):
            raise LocalBodyReferenceError("A rendered candidate image is required for local analysis.")
        from zet.services.image_harvest_service import candidate_admission, require_candidate_harvest
        require_candidate_harvest(self.app, run, candidate)
        image = Path(candidate["image_path"])
        anchor_id = run.get("front_anchor")
        anchor = next((item for item in run["candidates"] if item["candidate_id"] == anchor_id), None)
        anchor_image = Path(str(anchor.get("image_path") or "")) if anchor else None
        if candidate["view"] != FRONT_VIEW and (anchor_image is None or not anchor_image.is_file()):
            raise LocalBodyReferenceError("Select a completed front anchor before reviewing other views.")
        proxy = self.app.ai_proxy_service.ai_proxy_path_service.file_proxy_client
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        ask_id = f"Ask_LocalBodyReference_{run_id}_{candidate_id}_LOCAL_{stamp}"
        staging = proxy.create_staging(ask_id)
        files = [("candidate.png", image)]
        if anchor_image and candidate["view"] != FRONT_VIEW:
            files.insert(0, ("front_anchor.png", anchor_image))
        for name, source in files:
            shutil.copy2(source, staging / name)
        prompt = self.analysis_prompt(candidate, anchor=candidate["view"] != FRONT_VIEW,
                                      facts=self._review_facts(run, candidate["view"]))
        (staging / "OLLAMA_PROMPT.md").write_text(prompt, encoding="utf-8")
        output = self._root(run_id) / "analyses" / candidate_id / f"local_{stamp}.json"
        manifest = {
            "version": 1, "ask_id": ask_id, "character": run["character"], "phase": run["phase"],
            "universe_id": str(run.get("universe_id") or getattr(self.app.config, "universe_id", "Moonsea")),
            "pipeline": "Local-Body-Reference", "pipeline_stage": "BODY_REFERENCE_ANALYSIS",
            "worker_type": "ollama_generate", "ollama_model": model or str(
                getattr(self.app.config, "local_body_reference_review_model", "image-analysis:latest")
                or "image-analysis:latest"
            ),
            "prompt_file": "OLLAMA_PROMPT.md", "image_files": [name for name, _ in files], "json_output": True,
            "response_schema": self.analysis_schema(), "expected_output": "response.json", "task_type": "local_body_reference_analysis",
            "auxiliary": True, "target_output_dir": str(output.parent), "target_output_file": output.name,
            "local_body_reference_run_id": run_id, "candidate_id": candidate_id,
            "input_hashes": {"candidate": self._hash(image), "front_anchor": self._hash(anchor_image) if anchor_image and anchor_image.is_file() else ""},
        }
        (staging / "ask_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        proxy.publish(staging, ask_id, "ollama_generate")
        self._candidate_update(run_id, candidate_id, {"local_job": {
            "ask_id": ask_id, "status": "QUEUED", "output_path": str(output),
            "input_hashes": manifest["input_hashes"], "model": manifest["ollama_model"],
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        }})
        return {"provider": "local", "ask_id": ask_id, "status": "QUEUED", "output_path": str(output), "input_hashes": manifest["input_hashes"]}

    def _candidate_update(self, run_id: str, candidate_id: str, update: dict[str, Any]) -> None:
        root = self._root(run_id)
        def apply(state: dict[str, Any]) -> None:
            state.setdefault("candidates", {}).setdefault(candidate_id, {}).update(update)
            state["updated_at"] = self._now()
            if (root / "cancelled.json").is_file():
                state.update(status="CANCELLED", stop_requested=True, error="Cancelled by user.")
        mutate_local_run_state(root, apply)

    def _run_update(self, run_id: str, **update: Any) -> None:
        root = self._root(run_id)
        def apply(state: dict[str, Any]) -> None:
            changes = dict(update)
            if state.get("status") == "CANCELLED" and changes.get("status") != "CANCELLED":
                changes.pop("status", None)
                changes.pop("error", None)
            state.update(changes, updated_at=self._now())
            if (root / "cancelled.json").is_file():
                state.update(status="CANCELLED", stop_requested=True, error="Cancelled by user.")
        mutate_local_run_state(root, apply)

    def _proxy_answer(self, ask_id: str) -> tuple[str, dict[str, Any]]:
        return self.app.ai_proxy_service.ai_proxy_path_service.jobs.execution_status(ask_id)

    def _harvest_local_body_reference_answer(self, run_id: str, candidate_id: str, ask_id: str, target: Path) -> None:
        paths = self.app.ai_proxy_service.ai_proxy_path_service
        answer_path = paths.answer_path(ask_id)
        if not answer_path.is_dir():
            return
        if not (answer_path / "answer_manifest.json").is_file():
            return
        try:
            ask = self._read_json((answer_path / "ask_manifest.json"))
            answer = self._read_json((answer_path / "answer_manifest.json"))
        except (OSError, json.JSONDecodeError) as exc:
            raise LocalBodyReferenceError(f"Invalid AI Proxy answer {ask_id}: {exc}") from exc
        if (ask.get("ask_id") != ask_id or answer.get("ask_id") != ask_id
                or not self._ask_belongs_to_run(ask, self.detail(run_id))):
            raise LocalBodyReferenceError("AI Proxy answer ID does not match the queued job.")
        source_id = str(ask.get("source_ask_id") or "")
        render_source = re.fullmatch(rf"(?:Local)?BodyReference_{re.escape(run_id)}_{re.escape(candidate_id)}_\d+", source_id)
        if (ask.get("local_body_reference_run_id") != run_id or ask.get("candidate_id") != candidate_id) and not render_source:
            raise LocalBodyReferenceError("AI Proxy answer does not belong to this Local Body-Reference candidate.")
        status = str(answer.get("status") or "").upper()
        if status in {"ERROR", "RETRY_LATER", "FAILED"}:
            raise LocalBodyReferenceError(str(answer.get("error_message") or "AI Proxy job failed."))
        if status != "SUCCESS":
            return
        expected = str(ask.get("expected_output") or "")
        if not expected or Path(expected).name != expected or answer.get("expected_output") != expected:
            raise LocalBodyReferenceError("AI Proxy answer output filename is invalid.")
        if ask.get("task_type") in {"local_body_reference_analysis", "body_reference_analysis"}:
            filename = str(ask.get("target_output_file") or "")
            if ask.get("task_type") in {"local_body_reference_analysis", "body_reference_analysis"}:
                if not re.fullmatch(r"local(?:_\d{8}_\d{6}_\d{6})?\.json", filename):
                    raise LocalBodyReferenceError("AI Proxy analysis output filename is invalid.")
            expected_target = self._root(run_id) / "analyses" / candidate_id / filename
            if ask.get("target_output_file") != target.name:
                raise LocalBodyReferenceError("AI Proxy analysis output filename is invalid.")
        else:
            expected_target = self._root(run_id) / "renders" / candidate_id / "Local_Test_Renders" / expected
            if ask.get("task_type") != "local_test_render" or ask.get("target_output_file") != expected:
                raise LocalBodyReferenceError("AI Proxy render output filename is invalid.")
        if expected_target.resolve() != target.resolve() or not target.resolve().is_relative_to(self._root(run_id).resolve()):
            raise LocalBodyReferenceError("AI Proxy answer target does not match the Local Body-Reference slot.")
        source = answer_path / expected
        if not source.is_file() or source.stat().st_size == 0:
            raise LocalBodyReferenceError("AI Proxy answer is missing its output file.")
        paths.jobs.copy_result(ask_id, target, image=target.suffix.lower() in {".png", ".jpg", ".webp"})

    def _preflight(self) -> None:
        backend = LocalRenderBackendService(self.app.config.state_file(self.project_root, "Local_Render_Presets.json"), config=self.app.config)
        for name in ("comfyui-qwen-body-reference-text", "comfyui-qwen-body-reference-edit"):
            profile = backend.preset(name)
            if not profile:
                raise LocalBodyReferenceError(f"Missing render preset: {name}")
            for key in ("diffusion_model", "text_encoder", "vae"):
                if not str(profile.get(key) or "").strip():
                    raise LocalBodyReferenceError(f"Render preset {name} is missing {key}.")

    def _render_view_candidates(self, run_id: str, view: str, candidate_ids: set[str] | None = None) -> bool:
        """Render candidate images without blocking on AI Proxy."""
        run = self.detail(run_id)
        candidates = [item for item in run["candidates"] if item.get("view") == view
                      and (candidate_ids is not None or not item.get("slot_managed"))
                      and (candidate_ids is None or item["candidate_id"] in candidate_ids)]

        for candidate in candidates:
            if self.detail(run_id)["stop_requested"]:
                return False
            if candidate.get("status") != "PENDING":
                continue
            try:
                self.queue_render_candidate(run_id, candidate["candidate_id"])
            except Exception as exc:
                self._candidate_update(run_id, candidate["candidate_id"], {
                    "status": "FAILED", "render_error": str(exc),
                })

        for candidate in candidates:
            current = next((item for item in self.detail(run_id)["candidates"]
                           if item["candidate_id"] == candidate["candidate_id"]), None)
            if current is None:
                continue
            candidate_id = current["candidate_id"]
            if current.get("status") in {"QUEUED", "RUNNING"}:
                try:
                    if not self._wait_for_render(run_id, candidate_id):
                        return False
                    current = next((item for item in self.detail(run_id)["candidates"]
                                   if item["candidate_id"] == candidate_id), None)
                except Exception as exc:
                    self._candidate_update(run_id, candidate_id, {"status": "FAILED", "render_error": str(exc)})
                    continue
        return True

    @staticmethod
    def _crop_head(image_path: Path, crop_path: Path) -> None:
        """Crop the centered head area from the full-body reference render."""
        with Image.open(image_path) as source:
            image = source.convert("RGB")
            width, height = image.size
            image.crop((int(width * 0.25), 0, int(width * 0.75), int(height * 0.32))).save(crop_path, format="PNG")




    def move_candidate_rank(self, run_id: str, view: str, candidate_id: str, direction: str) -> dict[str, Any]:
        """Move one reviewed candidate one place in the saved ranking."""
        run = self.detail(run_id)
        view = str(view or "").upper()
        self.asset_store.assert_batch_change_allowed(run["character"], run["phase"], "Body-Reference", view)
        if view not in run.get("views", []):
            raise LocalBodyReferenceError(f"Unknown or unsupported Local Body-Reference view: {view}")
        if run.get("status") in {"PREFLIGHT", "RUNNING", "STOPPING", "REEVALUATING"}:
            raise LocalBodyReferenceError("Wait for the current operation to finish before changing rank.")
        ranking = (run.get("rankings") or {}).get(view) or {}
        try:
            adjusted = adjust_candidate_ranking(ranking, candidate_id, direction, timestamp=self._now())
        except ValueError as exc:
            raise LocalBodyReferenceError(str(exc)) from exc
        if adjusted is ranking:
            return run
        state = self._read_json((self._root(run_id) / "state.json"))
        state.setdefault("rankings", {})[view] = adjusted
        state["updated_at"] = self._now()
        self._save_state(run_id, state)
        return self.detail(run_id)







    def _execute_after_current_run(self, run_id: str) -> None:
        """Resume after another serialized batch operation releases the runner lock."""
        while self._runner_is_active(run_id):
            time.sleep(1)
        self.execute_run(run_id)

    def stage_view_evaluation(self, run_id: str, view: str, *, candidate_ids: set[str] | None = None) -> dict[str, Any]:
        from zet.services.local_image_evaluation_service import finish_evaluation, local_image_evaluation_service, update_view_evaluation
        view = str(view or "").upper()
        run = self.detail(run_id)
        candidates = [item for item in run.get("candidates") or [] if item.get("view") == view
                      and (candidate_ids is None or item["candidate_id"] in candidate_ids)
                      and Path(str(item.get("image_path") or "")).is_file()]
        hashes = {item["candidate_id"]: self._hash(Path(item["image_path"])) for item in candidates}
        previous = (run.get("evaluations") or {}).get(view) or {}
        if previous.get("status") == "RUNNING" and previous.get("input_hashes") == hashes:
            self.reconcile_review_jobs(run_id)
            return previous
        evaluation_id = uuid4().hex
        def rank():
            if self.detail(run_id).get("stop_requested"):
                return
            self.rank_view(run_id, view, evaluation_id=evaluation_id)
            current = dict((self.detail(run_id).get("evaluations") or {}).get(view) or {})
            if current.get("evaluation_id") == evaluation_id:
                current["status"] = "COMPLETE"
                update_view_evaluation(self._root(run_id), view, current, evaluation_id=evaluation_id)
        return local_image_evaluation_service().stage_view_evaluation(
            run_id, view, evaluation_id, rank=rank,
            finish=lambda: finish_evaluation(self._root(run_id), view, evaluation_id),
            save_evaluation=lambda record: update_view_evaluation(self._root(run_id), view, record, evaluation_id=evaluation_id),
            input_hashes=hashes)

    def reconcile_review_jobs(self, run_id: str) -> dict[str, Any]:
        from zet.services.local_image_evaluation_service import finish_evaluation, local_image_evaluation_service
        run = self.detail(run_id)
        for view, evaluation in (run.get("evaluations") or {}).items():
            evaluation_id = str(evaluation.get("evaluation_id") or "")
            if evaluation.get("status") == "RUNNING" and evaluation_id:
                local_image_evaluation_service().reconcile_review_jobs(
                    run_id, view, evaluation_id,
                    finish=lambda view=view, evaluation_id=evaluation_id: finish_evaluation(self._root(run_id), view, evaluation_id),
                    rank=lambda view=view, evaluation_id=evaluation_id: self.rank_view(run_id, view, evaluation_id=evaluation_id))
        return self.detail(run_id)

    def _review_view_candidates_v2(self, run_id: str, view: str, candidate_ids: set[str] | None = None) -> bool:
        run = self.detail(run_id)
        candidates = [item for item in run["candidates"] if item.get("view") == view
                      and (candidate_ids is None or item["candidate_id"] in candidate_ids)
                      and Path(str(item.get("image_path") or "")).is_file()]
        if run.get("stop_requested"):
            return False
        try:
            self.rank_view(run_id, view)
        except Exception:
            return True
        return not self.detail(run_id).get("stop_requested")

    def queue_view_ranking(self, run_id: str, view: str) -> dict[str, Any]:
        """Queue rendered candidates for comparative Luna ranking."""
        run = self.detail(run_id)
        view = str(view or "").upper()
        self.asset_store.assert_batch_change_allowed(run["character"], run["phase"], "Body-Reference", view)
        if view not in run.get("views", []):
            raise LocalBodyReferenceError(f"Unknown or unsupported Local Body-Reference view: {view}")
        if run.get("status") in {"PREFLIGHT", "RUNNING", "STOPPING", "REEVALUATING"}:
            raise LocalBodyReferenceError("Wait for the current Local Body-Reference operation to finish before ranking.")
        survivors = [item for item in run["candidates"] if item.get("view") == view
                     and (item.get("status") in {"WAITING_FOR_HUMAN_REVIEW", "COMPLETE"}
                          or item.get("human_review", {}).get("decision") == "keep")
                     and item.get("human_review", {}).get("decision") != "reject"]
        if not survivors:
            raise LocalBodyReferenceError("No rendered candidates are available to rank.")
        root = self._root(run_id)
        state = self._read_json((root / "state.json"))
        rankings = state.setdefault("rankings", {})
        previous = rankings.get(view)
        if previous:
            state.setdefault("ranking_history", {}).setdefault(view, []).append(
                {"archived_at": self._now(), "ranking": previous}
            )
        rankings[view] = {"status": "QUEUED", "ordered_candidate_ids": [],
                          "entries": [], "queued_at": self._now()}
        state["updated_at"] = self._now()
        self._save_state(run_id, state)
        return self.detail(run_id)

    def rank_view(self, run_id: str, view: str, *, evaluation_id: str = "") -> dict[str, Any]:
        """Rank every completed version 2 image in one canonical view."""
        run = self.detail(run_id)
        view = str(view or "").upper()
        self.asset_store.assert_batch_change_allowed(run["character"], run["phase"], "Body-Reference", view)
        if view not in run.get("views", []):
            raise LocalBodyReferenceError(f"Unknown Local Body-Reference view: {view}")
        active_evaluation = (run.get("evaluations") or {}).get(view) or {}
        if evaluation_id and (active_evaluation.get("evaluation_id") != evaluation_id
                              or active_evaluation.get("status") not in {"RUNNING", "STAGING"}):
            return run
        if not evaluation_id and active_evaluation.get("status") in {"RUNNING", "STAGING"}:
            evaluation_id = str(active_evaluation.get("evaluation_id") or "")
        anchor = next((item for item in run["candidates"] if item["candidate_id"] == run.get("front_anchor")), None)
        anchor_image = Path(str(anchor.get("image_path") or "")) if anchor else None
        if view != FRONT_VIEW and (anchor_image is None or not anchor_image.is_file()):
            raise LocalBodyReferenceError("Select a completed front anchor before ranking other views.")
        survivors = [item for item in run["candidates"] if item.get("view") == view
                     and item.get("human_review", {}).get("decision") != "reject"
                     and Path(str(item.get("image_path") or "")).is_file()]
        from zet.services.image_harvest_service import candidate_admission, require_candidate_harvest
        for survivor in survivors:
            require_candidate_harvest(self.app, run, survivor)
        root = self._root(run_id)
        state = self._read_json((root / "state.json"))
        previous = dict((state.get("rankings") or {}).get(view) or {})
        if previous.get("status") == "COMPLETE" and not evaluation_id:
            current_hashes = {item["candidate_id"]: self._hash(Path(str(item["image_path"]))) for item in survivors}
            current_anchor_hash = self._hash(anchor_image) if view != FRONT_VIEW and anchor_image else ""
            if previous.get("input_hashes") == current_hashes and previous.get("anchor_hash", "") == current_anchor_hash:
                return run
        current_hashes = {item["candidate_id"]: self._hash(Path(str(item["image_path"]))) for item in survivors}
        current_anchor_hash = self._hash(anchor_image) if view != FRONT_VIEW and anchor_image else ""
        if not survivors:
            ranking = {"status": "EMPTY", "ordered_candidate_ids": [], "luna_ordered_candidate_ids": [], "entries": [],
                       "input_hashes": {}, "anchor_hash": current_anchor_hash,
                       "model": "", "recorded_at": self._now()}
        elif len(survivors) == 1:
            only = survivors[0]
            ranking = {"status": "COMPLETE", "ordered_candidate_ids": [only["candidate_id"]],
                       "luna_ordered_candidate_ids": [only["candidate_id"]],
                       "entries": [{"candidate_id": only["candidate_id"], "reason": "Only completed image in this view."}],
                       "input_hashes": current_hashes, "anchor_hash": current_anchor_hash,
                       "model": "deterministic-single-survivor", "recorded_at": self._now()}
        else:
            try:
                image_labels: list[str] = []
                reference_images = []
                if view != FRONT_VIEW and anchor_image:
                    reference_images.append(anchor_image)
                    image_labels.append("Image 1: accepted FRONT anchor")
                for index, candidate in enumerate(survivors, start=1):
                    image_labels.append(f"Candidate {candidate['candidate_id']}: image {index + (1 if view != FRONT_VIEW else 0)}")
                prompt = (
                    "Rank all rendered body-reference candidates from best to worst. Human review is an independent advice signal; assess every image on its visual merits. Compare them against one another; do not turn minor "
                    "imperfections into automatic failures. Favor the requested canonical view, complete readable "
                    "silhouette, believable anatomy, proportions, mannequin head, and technical reference usefulness. "
                    + ("Use the FRONT anchor to judge body consistency. " if view != FRONT_VIEW else "")
                    + "Return every candidate exactly once with a concise comparative reason.\n\n"
                    + "Requested view: " + view + "\n"
                    + "View definition: " + CANONICAL_VIEW_DEFINITIONS.get(view, "") + "\n"
                    + "Image mapping:\n" + "\n".join(image_labels) + "\n\n"
                    + "Body-Reference specification:\n" + self._review_facts(run, view)
                )
                model = str(getattr(self.app.config, "codex_default_model", "gpt-6-luna"))
                entries, model = rank_images_with_luna(
                    project_root=self.project_root,
                    model=model,
                    prompt=prompt,
                    candidate_ids=[item["candidate_id"] for item in survivors],
                    image_paths=[item["image_path"] for item in survivors],
                    reference_image_paths=reference_images,
                    paths=self.app.ai_proxy_service.ai_proxy_path_service,
                    admission=lambda: candidate_admission(self.app, lambda: self.detail(run_id), run, survivors),
                    owner={"run_id": run_id, "view": view, "pipeline": 'Body-Reference', "evaluation_id": evaluation_id},
                )
                ranking = {"status": "COMPLETE", "evaluation_id": evaluation_id,
                           "ordered_candidate_ids": [item["candidate_id"] for item in entries],
                           "luna_ordered_candidate_ids": [item["candidate_id"] for item in entries],
                           "entries": entries, "input_hashes": current_hashes, "anchor_hash": current_anchor_hash,
                           "model": str(getattr(self.app.config, "codex_default_model", "gpt-6-luna")),
                           "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(), "recorded_at": self._now()}
            except Exception as exc:
                ranking = {"status": "FAILED", "ordered_candidate_ids": [], "entries": [],
                           "input_hashes": current_hashes, "anchor_hash": current_anchor_hash,
                           "error": str(exc), "recorded_at": self._now()}
                self._save_ranking_result(run_id, view, evaluation_id, current_hashes, ranking)
                raise LocalBodyReferenceError(f"Luna ranking failed for {view}: {exc}") from exc
        def save_ranking(current: dict[str, Any]) -> None:
            active = (current.get("evaluations") or {}).get(view) or {}
            if evaluation_id and (active.get("evaluation_id") != evaluation_id or active.get("status") not in {"RUNNING", "STAGING"}):
                return
            latest = self.detail(run_id)
            ranked_candidate_ids = set(current_hashes)
            hashes_now = {item["candidate_id"]: self._hash(Path(str(item["image_path"])))
                          for item in latest["candidates"] if item.get("view") == view
                          and item["candidate_id"] in ranked_candidate_ids
                          and Path(str(item.get("image_path") or "")).is_file()}
            if hashes_now != current_hashes:
                return
            ranking["evaluation_id"] = evaluation_id
            current_rankings = current.setdefault("rankings", {})
            previous = current_rankings.get(view)
            if previous and previous != ranking and previous.get("status") not in {"QUEUED", "RUNNING"}:
                current.setdefault("ranking_history", {}).setdefault(view, []).append(
                    {"archived_at": self._now(), "ranking": previous}
                )
            current_rankings[view] = ranking
            if evaluation_id:
                ranking_status = ranking.get("status")
                active.update(ranking_status=ranking_status, ranking_updated_at=self._now())
                if ranking_status in {"COMPLETE", "FAILED", "EMPTY", "SKIPPED"}:
                    active["status"] = "COMPLETE"
                current.setdefault("evaluations", {})[view] = active
            current["updated_at"] = self._now()
        mutate_local_run_state(root, save_ranking)
        from zet.services.local_prompt_improvement_service import after_initial_ranking
        after_initial_ranking(self, "body-reference", self.project_root, run_id, view)
        return self.detail(run_id)

    def _save_ranking_result(self, run_id: str, view: str, evaluation_id: str,
                             input_hashes: dict[str, str], ranking: dict[str, Any]) -> None:
        def save(state: dict[str, Any]) -> None:
            active = (state.get("evaluations") or {}).get(view) or {}
            if evaluation_id and (active.get("evaluation_id") != evaluation_id or active.get("status") not in {"RUNNING", "STAGING"}):
                return
            run = self.detail(run_id)
            ranked_candidate_ids = set(input_hashes)
            current = {item["candidate_id"]: self._hash(Path(str(item["image_path"])))
                       for item in run["candidates"] if item.get("view") == view
                       and item["candidate_id"] in ranked_candidate_ids
                       and Path(str(item.get("image_path") or "")).is_file()}
            if current != input_hashes:
                return
            ranking["evaluation_id"] = evaluation_id
            state.setdefault("rankings", {})[view] = ranking
            if evaluation_id:
                ranking_status = ranking.get("status")
                active.update(ranking_status=ranking_status, ranking_updated_at=self._now())
                if ranking_status in {"COMPLETE", "FAILED", "EMPTY", "SKIPPED"}:
                    active["status"] = "COMPLETE"
                state.setdefault("evaluations", {})[view] = active
        mutate_local_run_state(self._root(run_id), save)

    def _invalidate_views_after_anchor_change(self, run_id: str, state: dict[str, Any]) -> None:
        """Clear downstream selections and review state when FRONT identity changes."""
        run = self.detail(run_id)
        for view in (run.get("views") or []):
            if view != FRONT_VIEW:
                self.asset_store.assert_batch_change_allowed(run["character"], run["phase"], "Body-Reference", view)
        root = self._root(run_id).resolve()
        downstream_views = {view for view in (run.get("views") or []) if view != FRONT_VIEW}
        self._withdraw_queued_asks(run_id, affected_views=downstream_views)
        selected = state.setdefault("selected_views", {})
        rankings = state.setdefault("rankings", {})
        for view in (run.get("views") or []):
            if view == FRONT_VIEW:
                continue
            selected.pop(view, None)
            rankings.pop(view, None)
            self._clear_owned_selection(run, view)
        for candidate in run.get("candidates") or []:
            if candidate.get("view") == FRONT_VIEW:
                continue
            image_path = str(candidate.get("image_path") or "")
            clear_candidate_artifacts(root, candidate["candidate_id"], candidate.get("image_path"))
            update = state.setdefault("candidates", {}).setdefault(candidate["candidate_id"], {})
            update.update({
                "status": "PENDING", "image_path": "", "image_sha256": "", "ask_id": "",
                "render_error": "",
                "analyses": {}, "analysis_history": [], "review_history": [],
                "human_review": {"decision": "undecided"},
                "retry_count": int(candidate.get("retry_count") or 0) + (1 if image_path else 0),
            })

    def _mark_downstream_review_stale(self, run: dict[str, Any], state: dict[str, Any]) -> None:
        """Keep rendered work and selections when a human changes the FRONT choice."""
        from zet.services.local_image_evaluation_service import supersede_evaluations
        supersede_evaluations(state, set(run.get("views") or []) - {FRONT_VIEW},
                              "The selected FRONT anchor changed.")
        for view in run.get("views") or []:
            if view == FRONT_VIEW:
                continue
            ranking = state.setdefault("rankings", {}).get(view)
            if ranking:
                ranking.update(status="STALE", stale_reason="The selected FRONT anchor changed.")
            for candidate in run.get("candidates") or []:
                if candidate.get("view") != view:
                    continue
                if state.get("selected_views", {}).get(view) == candidate.get("candidate_id"):
                    state["candidates"][candidate["candidate_id"]]["stale_selection"] = True


    @serialize_local_run_state
    def select_view(self, run_id: str, view: str, candidate_id: str, *, autogenerate: bool = False) -> dict[str, Any]:
        """Select the human-approved candidate for one version 2 view."""
        run = self.detail(run_id)
        view = str(view or "").upper()
        if run.get("review_version", 1) < 2:
            raise LocalBodyReferenceError("View selection is available for version 2 runs.")
        if view not in run.get("views", []):
            raise LocalBodyReferenceError(f"Unknown Local Body-Reference view: {view}")
        root = self._root(run_id)
        state = self._read_json((root / "state.json"))
        selected = state.setdefault("selected_views", {})
        if not candidate_id:
            if view == FRONT_VIEW:
                for downstream_view in run.get("views", []):
                    if downstream_view != FRONT_VIEW:
                        self.asset_store.assert_batch_change_allowed(run["character"], run["phase"], "Body-Reference", downstream_view)
            removed_id = selected.pop(view, None)
            if not removed_id and view == FRONT_VIEW:
                removed_id = state.get("front_anchor")
            self.asset_store.clear_batch_selection(
                run["character"], run["phase"], "Body-Reference", view, run_id
            )
            if not removed_id:
                return self.detail(run_id)
            state.setdefault("candidates", {}).setdefault(removed_id, {}).update(selected_at="")
            if view == FRONT_VIEW:
                if state.get("front_anchor") == removed_id:
                    state["front_anchor"] = None
                self._mark_downstream_review_stale(run, state)
            if state.get("status") not in ACTIVE_RUN_STATUSES and view != FRONT_VIEW:
                state["status"] = "AWAITING_HUMAN_SELECTION" if state.get("front_anchor") else "AWAITING_FRONT_ANCHOR"
            elif state.get("status") not in ACTIVE_RUN_STATUSES:
                state["status"] = "AWAITING_FRONT_ANCHOR"
            state["updated_at"] = self._now()
            self._save_state(run_id, state)
            return self.detail(run_id)
        candidate = next((item for item in run["candidates"] if item["candidate_id"] == candidate_id), None)
        if not candidate or candidate.get("view") != view:
            raise LocalBodyReferenceError(f"Candidate {candidate_id} does not belong to view {view}.")
        auto_approved = bool(autogenerate and view == FRONT_VIEW)
        if auto_approved and candidate.get("human_review", {}).get("decision") == "reject":
            raise LocalBodyReferenceError("A human-rejected candidate cannot be autoselected.")
        ranking = (run.get("rankings") or {}).get(view) or {}
        if view != FRONT_VIEW and run.get("front_anchor"):
            anchor = next((item for item in run["candidates"] if item["candidate_id"] == run.get("front_anchor")), None)
            anchor_image = Path(str(anchor.get("image_path") or "")) if anchor else None
        luna_order = list(ranking.get("luna_ordered_candidate_ids") or [])
        if not luna_order and len(ranking.get("ordered_candidate_ids") or []) == 1:
            luna_order = list(ranking["ordered_candidate_ids"])
        if auto_approved and (not luna_order or luna_order[0] != candidate_id):
            raise LocalBodyReferenceError("Autogenerate can select only the original #1 Luna candidate.")
        image = Path(str(candidate.get("image_path") or ""))
        if not image.is_file():
            raise LocalBodyReferenceError("The candidate image is missing.")
        if auto_approved and (ranking.get("status") != "COMPLETE"
                              or ranking.get("input_hashes", {}).get(candidate_id) != self._hash(image)):
            raise LocalBodyReferenceError("Autogenerate requires a current FRONT ranking.")
        previous_id = selected.get(view)
        if previous_id != candidate_id:
            self.asset_store.assert_batch_change_allowed(run["character"], run["phase"], "Body-Reference", view)
        old_anchor_id = state.get("front_anchor")
        if view == FRONT_VIEW and old_anchor_id != candidate_id:
            for downstream_view in run.get("views", []):
                if downstream_view != FRONT_VIEW:
                    self.asset_store.assert_batch_change_allowed(run["character"], run["phase"], "Body-Reference", downstream_view)
        selected[view] = candidate_id
        update = {"selected_at": self._now()}
        if auto_approved:
            update["autogenerate_approval"] = {"approved_at": self._now(), "reason": "Current #1 Luna FRONT candidate has a valid image and ranking."}
        state.setdefault("candidates", {}).setdefault(candidate_id, {}).update(update)
        if view == FRONT_VIEW:
            state["front_anchor"] = candidate_id
            if old_anchor_id != candidate_id:
                self._mark_downstream_review_stale(run, state)
                if state.get("status") not in ACTIVE_RUN_STATUSES:
                    state.update(status="READY_FOR_VIEWS", target_views=[], target_candidate_ids=[])
        image_hash = self._hash(image)
        dependencies = []
        if view != FRONT_VIEW:
            anchor = next((item for item in run["candidates"]
                           if item.get("candidate_id") == run.get("front_anchor")), None)
            anchor_image = Path(str((anchor or {}).get("image_path") or ""))
            if anchor_image and anchor_image.is_file():
                dependencies.append({
                    "key": self.asset_store.key("Body-Reference", FRONT_VIEW),
                    "image_sha256": self._hash(anchor_image),
                })
        self.asset_store.record_batch_selection(
            run["character"], run["phase"], "Body-Reference", view,
            candidate_id=candidate_id, image_path=image, batch_id=run_id,
            dependencies=dependencies,
        )

        all_selected = all(view_name in selected for view_name in run.get("views") or [])
        if all_selected and state.get("front_anchor") == selected.get(FRONT_VIEW) and not self.detail(run_id).get("stale_selections") and state.get("status") not in ACTIVE_RUN_STATUSES:
            state.update(status="COMPLETE", target_views=[], target_candidate_ids=[], review_only=False)
        elif state.get("status") in ACTIVE_RUN_STATUSES:
            pass
        elif state.get("front_anchor"):
            state.setdefault("status", "AWAITING_HUMAN_SELECTION")
            if state.get("status") not in {"READY_FOR_VIEWS", "RUNNING", "PREFLIGHT"}:
                state["status"] = "AWAITING_HUMAN_SELECTION"
        else:
            state["status"] = "AWAITING_FRONT_ANCHOR"
        state["updated_at"] = self._now()
        self._save_state(run_id, state)
        return self.detail(run_id)

    def lock_selected_view(self, run_id: str, view: str) -> dict[str, Any]:
        run = self.detail(run_id)
        view = str(view or "").upper()
        candidate_id = (run.get("selected_views") or {}).get(view)
        if not candidate_id:
            raise LocalBodyReferenceError(f"Select a reviewed {view} candidate before locking it.")
        candidate = next((item for item in run.get("candidates", [])
                          if item.get("candidate_id") == candidate_id), None)
        image = Path(str((candidate or {}).get("image_path") or ""))
        if not candidate or not image.is_file():
            raise LocalBodyReferenceError("The selected candidate image is missing.")
        try:
            dependencies = []
            if view != FRONT_VIEW:
                anchor = next((item for item in run["candidates"]
                               if item["candidate_id"] == run.get("front_anchor")), None)
                anchor_image = Path(str((anchor or {}).get("image_path") or ""))
                if anchor_image.is_file():
                    dependencies.append({"key": self.asset_store.key("Body-Reference", FRONT_VIEW),
                                         "image_sha256": self._hash(anchor_image)})
            return self.asset_store.lock_batch_selection(
                run["character"], run["phase"], "Body-Reference", view,
                candidate_id=candidate_id, image_path=image, batch_id=run_id,
                dependencies=dependencies,
            )
        except Exception as exc:
            raise LocalBodyReferenceError(str(exc)) from exc

    def unlock_view(self, character: str, phase: str, view: str) -> dict[str, Any]:
        try:
            return self.asset_store.unlock(character, phase, "Body-Reference", view)
        except Exception as exc:
            raise LocalBodyReferenceError(str(exc)) from exc

    def _review_view_candidates(self, run_id: str, view: str, candidate_ids: set[str] | None = None) -> bool:
        """Run all pending analyses for one view after its images are available."""
        candidates = [item for item in self.detail(run_id)["candidates"] if item.get("view") == view and (candidate_ids is None or item["candidate_id"] in candidate_ids)]
        for candidate in candidates:
            if self.detail(run_id)["stop_requested"]:
                return False
            current = next(
                item for item in self.detail(run_id)["candidates"]
                if item["candidate_id"] == candidate["candidate_id"]
            )
            if current.get("status") not in {"WAITING_FOR_ANALYSIS", "COMPLETE"}:
                continue
            candidate_id = current["candidate_id"]
            try:
                if "local" not in current.get("analyses", {}):
                    if not current.get("local_job"):
                        self.queue_local_analysis(run_id, candidate_id)
                current = next(
                    item for item in self.detail(run_id)["candidates"]
                    if item["candidate_id"] == candidate_id
                )
                if "luna" not in current.get("analyses", {}) and current.get("luna_status") != "FAILED":
                    self._candidate_update(run_id, candidate_id, {"luna_status": "RUNNING"})
                    try:
                        self.run_luna_analysis(run_id, candidate_id)
                        self._candidate_update(run_id, candidate_id, {"luna_status": "COMPLETE"})
                    except Exception as exc:
                        self._candidate_update(run_id, candidate_id, {
                            "luna_status": "FAILED", "luna_error": str(exc),
                        })
                current = next(
                    item for item in self.detail(run_id)["candidates"]
                    if item["candidate_id"] == candidate_id
                )
                if "local" not in current.get("analyses", {}):
                    try:
                        self._wait_for_local(run_id, candidate_id)
                    except Exception as exc:
                        job = current.get("local_job") or {}
                        job.update(status="FAILED", error=str(exc))
                        self._candidate_update(run_id, candidate_id, {"local_job": job})
            except Exception as exc:
                # Preserve the existing behavior for an unexpected candidate-level
                # review failure while allowing the rest of the view to proceed.
                self._candidate_update(run_id, candidate_id, {
                    "status": "FAILED", "render_error": str(exc),
                })
        return True

    def _wait_for_render(self, run_id: str, candidate_id: str) -> bool:
        candidate = next((item for item in self.detail(run_id)["candidates"] if item["candidate_id"] == candidate_id), None)
        if candidate is None:
            return True
        image = Path(str(candidate.get("image_path") or ""))
        deadline = time.monotonic() + 1860
        while not self.app.ai_proxy_service.ai_proxy_path_service.jobs.image_harvest_ready(str(candidate.get("ask_id") or ""), image):
            if not any(c["candidate_id"] == candidate_id for c in self.detail(run_id)["candidates"]):
                return True
            if self.detail(run_id)["stop_requested"]:
                return False
            self._harvest_local_body_reference_answer(run_id, candidate_id, str(candidate.get("ask_id") or ""), image)
            proxy_status, answer = self._proxy_answer(str(candidate.get("ask_id") or ""))
            if str(answer.get("status") or "").upper() in {"ERROR", "RETRY_LATER", "FAILED"}:
                raise LocalBodyReferenceError(str(answer.get("error_message") or "AI Proxy render failed"))
            if proxy_status == "RUNNING" and candidate.get("status") != "RUNNING":
                self._candidate_update(run_id, candidate_id, {"status": "RUNNING"})
                candidate["status"] = "RUNNING"
            if time.monotonic() >= deadline and not self.app.ai_proxy_service.ai_proxy_path_service.jobs.is_pending(str(candidate.get("ask_id") or "")):
                raise LocalBodyReferenceError("Timed out waiting for the render; use Retry after checking AI Proxy.")
            time.sleep(max(0.5, float(self.app.config.comfyui_poll_seconds)))
        self._candidate_update(run_id, candidate_id, {"status": "WAITING_FOR_HUMAN_REVIEW", "completed_at": "",
                                                    "image_sha256": self._hash(image), "render_error": ""})
        return True

    def _wait_for_local(self, run_id: str, candidate_id: str) -> bool:
        candidate = next(item for item in self.detail(run_id)["candidates"] if item["candidate_id"] == candidate_id)
        job = candidate["local_job"]
        output = Path(job["output_path"])
        deadline = time.monotonic() + 1800
        while not output.is_file():
            if self.detail(run_id)["stop_requested"]:
                return False
            self._harvest_local_body_reference_answer(run_id, candidate_id, job["ask_id"], output)
            proxy_status, answer = self._proxy_answer(job["ask_id"])
            if str(answer.get("status") or "").upper() in {"ERROR", "RETRY_LATER", "FAILED"}:
                raise LocalBodyReferenceError(str(answer.get("error_message") or "Local image analysis failed"))
            if proxy_status == "RUNNING" and job["status"] != "RUNNING":
                job["status"] = "RUNNING"
                self._candidate_update(run_id, candidate_id, {"local_job": job})
            if time.monotonic() >= deadline and not self.app.ai_proxy_service.ai_proxy_path_service.jobs.is_pending(str(job.get("ask_id") or "")):
                raise LocalBodyReferenceError("Timed out waiting for local image analysis.")
            time.sleep(2)
        try:
            result = self._read_json(output)
            self.record_analysis(run_id, candidate_id, "local", result, job["input_hashes"])
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise LocalBodyReferenceError(f"Invalid local image analysis: {exc}") from exc
        job["status"] = "COMPLETE"
        self._candidate_update(run_id, candidate_id, {"local_job": job})
        return True

    def execute_run(self, run_id: str, *, views: set[str] | None = None,
                    candidate_ids: set[str] | None = None, render_only: bool = False) -> None:
        try:
            with file_lock(self._root(run_id) / "runner.lock", timeout=0):
                self._execute_run_locked(run_id, views=views, candidate_ids=candidate_ids, render_only=render_only)
        except TimeoutError:
            return

    def _execute_run_locked(self, run_id: str, *, views: set[str] | None = None,
                            candidate_ids: set[str] | None = None, render_only: bool = False) -> None:
        with self._active_runs_lock:
            self._active_runs.add(self._active_key(run_id))
        try:
            initial_state = self._read_json((self._root(run_id) / "state.json"))
            if initial_state.get("status") == "CANCELLED" or initial_state.get("stop_requested"):
                self._withdraw_queued_asks(run_id)
                self._run_update(run_id, status="CANCELLED", stop_requested=True)
                return
            review_only = bool(initial_state.get("review_only"))
            target_views = list(initial_state.get("target_views") or [])
            saved_candidate_ids = set(initial_state.get("target_candidate_ids") or [])
            target_candidate_ids = saved_candidate_ids | candidate_ids if candidate_ids is not None else (
                saved_candidate_ids or None
            )
            if not review_only:
                self._run_update(run_id, status="PREFLIGHT", error="", slot_work_pending=False)
                self._preflight()
            self._run_update(run_id, status="REEVALUATING" if review_only else "RUNNING")
            run = self.detail(run_id)
            views = target_views or list(views or []) or (list(run.get("views") or []) if review_only else (
                [FRONT_VIEW] if not run.get("front_anchor") else
                [view for view in run.get("views") or [] if view != FRONT_VIEW]
            ))
            for view in views:
                if self.detail(run_id)["stop_requested"]:
                    self._withdraw_queued_asks(run_id)
                    self._run_update(run_id, status="CANCELLED", stop_requested=True)
                    return
                if not review_only and not self._render_view_candidates(run_id, view, target_candidate_ids):
                    self._withdraw_queued_asks(run_id)
                    self._run_update(run_id, status="CANCELLED", stop_requested=True)
                    return
                if review_only and not render_only and not self.detail(run_id)["stop_requested"]:
                    current = self.detail(run_id)
                    review = (self._review_view_candidates_v2 if int(current.get("review_version") or 1) >= 2
                              else self._review_view_candidates)
                    if not review(run_id, view, target_candidate_ids):
                        self._withdraw_queued_asks(run_id)
                        self._run_update(run_id, status="CANCELLED", stop_requested=True)
                        return
                if not render_only and not review_only and not self.detail(run_id)["stop_requested"]:
                    try:
                        self.stage_view_evaluation(run_id, view)
                    except Exception as exc:
                        current = self.detail(run_id).get("review_errors") or {}
                        current[view] = str(exc)
                        self._run_update(run_id, review_errors=current)
            if render_only:
                latest = self.detail(run_id)
                status = "CANCELLED" if latest.get("stop_requested") else (
                    "AWAITING_FRONT_ANCHOR" if not latest.get("front_anchor") else "AWAITING_HUMAN_SELECTION")
                self._run_update(run_id, status=status, review_only=False, target_views=[], target_candidate_ids=[])
                return
            for view in views:
                latest = self.detail(run_id)
                if latest.get("stop_requested"):
                    self._withdraw_queued_asks(run_id)
                    self._run_update(run_id, status="CANCELLED", stop_requested=True)
                    return
                view_candidates = [item for item in latest["candidates"] if item.get("view") == view
                                   and (target_candidate_ids is None or item["candidate_id"] in target_candidate_ids)]
                waiting_status = next((status for status in ("WAITING_FOR_ANALYSIS", "WAITING_FOR_HUMAN_REVIEW")
                                       if any(item.get("status") == status for item in view_candidates)), None)
                if waiting_status and not latest.get("front_anchor"):
                    waiting_candidates = [item for item in view_candidates
                                          if item.get("status") in {"WAITING_FOR_ANALYSIS", "WAITING_FOR_HUMAN_REVIEW"}]
                    self._run_update(run_id, status=("AWAITING_FRONT_ANCHOR" if latest.get("review_version", 1) >= 2 else waiting_status), review_only=False,
                                     target_views=[view], target_candidate_ids=[item["candidate_id"] for item in waiting_candidates])
                    return
                if not latest.get("front_anchor"):
                    self._run_update(run_id, status="AWAITING_FRONT_ANCHOR", review_only=False, target_views=[])
                    return
            latest = self.detail(run_id)
            if latest.get("stop_requested"):
                self._withdraw_queued_asks(run_id)
                self._run_update(run_id, status="CANCELLED", stop_requested=True)
                return
            scoped_candidates = [item for item in latest.get("candidates") or []
                                 if target_candidate_ids is None or item["candidate_id"] in target_candidate_ids]
            waiting_candidates = [item for item in scoped_candidates if item.get("status") in {
                "WAITING_FOR_ANALYSIS", "WAITING_FOR_HUMAN_REVIEW"
            }]
            if waiting_candidates:
                waiting_status = next(status for status in ("WAITING_FOR_ANALYSIS", "WAITING_FOR_HUMAN_REVIEW")
                                      if any(item.get("status") == status for item in waiting_candidates))
                all_selected = all((latest.get("selected_views") or {}).get(target) for target in latest.get("views") or [])
                run_status = ("COMPLETE" if all_selected else "AWAITING_HUMAN_SELECTION") if latest.get("review_version", 1) >= 2 else waiting_status
                self._run_update(run_id, status=run_status, review_only=False,
                                 target_views=sorted({item["view"] for item in waiting_candidates}),
                                 target_candidate_ids=[item["candidate_id"] for item in waiting_candidates])
                return
            selected = latest.get("selected_views") or {}
            complete = all(selected.get(view) and any(
                item["candidate_id"] == selected[view] and item["view"] == view
                and Path(str(item.get("image_path") or "")).is_file() for item in latest["candidates"]
            ) for view in latest.get("views", []))
            if review_only:
                status = run.get("post_review_status") or "AWAITING_FRONT_ANCHOR"
            elif int(latest.get("review_version") or 1) < 2:
                status = "AWAITING_FRONT_ANCHOR" if not latest.get("front_anchor") else "COMPLETE"
            else:
                status = ("AWAITING_FRONT_ANCHOR" if not latest.get("front_anchor") else
                          "COMPLETE" if complete else "AWAITING_HUMAN_SELECTION")
            self._run_update(run_id, status=status, review_only=False, target_views=[], target_candidate_ids=[])
            return
        except Exception as exc:
            self._run_update(run_id, status="ERROR", review_only=False, error=str(exc))
        finally:
            with self._active_runs_lock:
                self._active_runs.discard(self._active_key(run_id))
    def queue_render_candidate(self, run_id: str, candidate_id: str) -> dict[str, Any]:
        run = self.detail(run_id)
        candidate = next((item for item in run["candidates"] if item["candidate_id"] == candidate_id), None)
        if not candidate:
            raise LocalBodyReferenceError(f"Unknown candidate: {candidate_id}")
        if candidate.get("status") in {"QUEUED", "RUNNING", "COMPLETE"}:
            return candidate
        if candidate.get("view") != FRONT_VIEW and not run.get("front_anchor"):
            raise LocalBodyReferenceError("Complete front analysis and select an anchor before rendering other views.")
        method = candidate.get("method")
        if method == "shared_front":
            preset_name = "comfyui-qwen-body-reference-text"
            references = []
        elif method == METHOD_TEXT_FIRST:
            preset_name = "comfyui-qwen-body-reference-text"
            references = []
        else:
            preset_name = "comfyui-qwen-body-reference-edit"
            anchor = next((item for item in run["candidates"] if item["candidate_id"] == run.get("front_anchor")), None)
            anchor_path = Path(str(anchor.get("image_path") or "")) if anchor else None
            if anchor_path is None or not anchor_path.is_file():
                raise LocalBodyReferenceError("Front-conditioned rendering requires a completed front anchor image.")
            references = [{"role": "body_reference_front_anchor", "path": str(anchor_path)}]
        root = self._root(run_id)
        candidate_dir = root / "renders" / candidate_id
        saved_input = candidate.get("render_input")
        if saved_input:
            verify_input(saved_input)
            references = saved_input["references"]
            preset_name = saved_input["preset"]
        else:
            saved_input = frozen_input(candidate_dir / "inputs", candidate["prompt"], references, preset_name)
        references = saved_input["references"]
        self._candidate_update(run_id, candidate_id, {"render_input": saved_input})
        candidate_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = candidate_dir / "Qwen_Body_Reference_Prompt.md"
        prompt_path.write_text(f"Positive Prompt:\n{saved_input['prompt']}\n\nNegative Prompt:\n", encoding="utf-8")
        profile = LocalRenderBackendService(self.app.config.state_file(self.project_root, "Local_Render_Presets.json"), config=self.app.config).preset(preset_name)
        checkpoint = str(profile.get("diffusion_model") or "").strip()
        manifest = {"ask_id": f"LocalBodyReference_{run_id}_{candidate_id}_{int(candidate.get('retry_count') or 0)}", "character": run["character"],
                    "phase": run["phase"], "pipeline": "Local-Body-Reference", "pipeline_stage": "BODY_REFERENCE_RENDER"}
        ask_path = self.app.ai_proxy_service.stage_render_task_local_render_ask(
            manifest, prompt_path, candidate_dir, allow_parallel=True, seed=int(candidate["seed"]),
            checkpoint=checkpoint, render_preset=preset_name, image_generation="comfyui",
            reference_files=references,
        )
        ask = self._read_json((ask_path / "ask_manifest.json"))
        update = {"status": "QUEUED", "ask_id": ask["ask_id"], "queued_at": self._now(),
                  "reference_images": [{"role": str(item.get("role") or ""),
                                        "label": str(item.get("label") or ""),
                                        "path": str(item.get("path") or ""),
                                        "sha256": self._hash(Path(str(item.get("path") or "")))}
                                       for item in references],
                  "image_path": str(candidate_dir / "Local_Test_Renders" / ask["expected_output"])}
        state = self._read_json((root / "state.json"))
        state.setdefault("candidates", {}).setdefault(candidate_id, {}).update(update)
        state["updated_at"] = self._now()
        self._save_state(run_id, state)
        return self.detail(run_id)

    def queue_next_render(self, run_id: str) -> dict[str, Any]:
        run = self.detail(run_id)
        state = self._read_json((self._root(run_id) / "state.json"))
        if state.get("stop_requested"):
            return {"status": "STOPPED", "run_id": run_id, "candidate_id": None}
        pending = [item for item in run.get("candidates") or [] if item.get("status") == "PENDING"]
        if not pending:
            return {"status": run.get("status") or "COMPLETE", "run_id": run_id, "candidate_id": None}
        candidate = pending[0]
        if candidate.get("view") != FRONT_VIEW and not run.get("front_anchor"):
            return {"status": "AWAITING_FRONT_ANCHOR", "run_id": run_id, "candidate_id": None}
        self.queue_render_candidate(run_id, candidate["candidate_id"])
        return {"status": "QUEUED", "run_id": run_id, "candidate_id": candidate["candidate_id"]}

    def request_stop(self, run_id: str) -> dict[str, Any]:
        root = self._root(run_id)
        state = self._read_json((root / "state.json"))
        if state.get("status") == "CANCELLED":
            self._withdraw_queued_asks(run_id)
            return self.detail(run_id)
        active = {"PREFLIGHT", "RUNNING", "STOPPING", "REEVALUATING",
                  "WAITING_FOR_ANALYSIS", "WAITING_FOR_HUMAN_REVIEW"}
        if state.get("status") not in active:
            run = self.detail(run_id)
            if not run.get("interrupted"):
                raise LocalBodyReferenceError("This batch is not running.")
        stamp = self._now()
        self._write(root / "cancelled.json", {"run_id": run_id, "cancelled_at": stamp})
        state["stop_requested"] = True
        state["status"] = "CANCELLED"
        from zet.services.local_image_evaluation_service import supersede_evaluations
        supersede_evaluations(state, set(state.get("evaluations") or {}), "The run was stopped.")
        state["cancelled_at"] = stamp
        state["error"] = "Cancelled by user."
        state["updated_at"] = stamp
        self._save_state(run_id, state)
        self._withdraw_queued_asks(run_id)
        return self.detail(run_id)

    def resume(self, run_id: str) -> dict[str, Any]:
        run = self.detail(run_id)
        if run.get("status") == "CANCELLED" and run.get("created_by_autogenerate"):
            if self._runner_is_active(run_id):
                raise LocalBodyReferenceError("Wait for the stopped batch runner to finish before resuming.")
            root = self._root(run_id)
            state = self._read_json((root / "state.json"))
            resume_cancelled_autogenerate_state(run, state, ready_status="READY_FOR_VIEWS")
            state["updated_at"] = self._now()
            (root / "cancelled.json").unlink(missing_ok=True)
            self._save_state(run_id, state)
            return self.detail(run_id)
        if run.get("status") != "INTERRUPTED":
            raise LocalBodyReferenceError("Only an interrupted batch can be resumed; cancelled batches are terminal.")
        state = self._read_json((self._root(run_id) / "state.json"))
        state["stop_requested"] = False
        state["status"] = "QUEUED"
        state["updated_at"] = self._now()
        self._save_state(run_id, state)
        return self.detail(run_id)

    def proceed(self, run_id: str) -> dict[str, Any]:
        run = self.detail(run_id)
        if not run.get("front_anchor"):
            raise LocalBodyReferenceError("Select a FRONT anchor before generating other views.")
        if run.get("status") in ACTIVE_RUN_STATUSES:
            raise LocalBodyReferenceError("Wait for the current batch operation to finish before proceeding.")
        state = self._read_json((self._root(run_id) / "state.json"))
        if run.get("review_version", 1) >= 2:
            anchor = next((item for item in run["candidates"] if item.get("candidate_id") == run["front_anchor"]), None)
            image = Path(str((anchor or {}).get("image_path") or ""))
            if not anchor or not image.is_file():
                raise LocalBodyReferenceError("Select a FRONT anchor with an available image before proceeding.")
            claimed = set(state.get("target_views") or [])
            target_views = [view for view in run.get("views", []) if view != FRONT_VIEW and view not in claimed and
                            (candidates := [item for item in run["candidates"] if item.get("view") == view]) and
                            all(item.get("status") == "PENDING" and not item.get("image_path") for item in candidates)]
        else:
            target_views = [view for view in run.get("views", []) if view != FRONT_VIEW]
        if run.get("review_version", 1) >= 2 and not target_views:
            return {**run, "target_views": []}
        state.update(status="READY_FOR_VIEWS", stop_requested=False, updated_at=self._now(), target_views=target_views)
        self._save_state(run_id, state)
        return {**self.detail(run_id), "target_views": target_views}

    def retry_candidate(self, run_id: str, candidate_id: str) -> dict[str, Any]:
        run = self.detail(run_id)
        candidate = next((item for item in run["candidates"] if item["candidate_id"] == candidate_id), None)
        if candidate is None:
            raise LocalBodyReferenceError(f"Unknown candidate: {candidate_id}")
        self.asset_store.assert_batch_change_allowed(run["character"], run["phase"], "Body-Reference", candidate["view"])
        root, state = self._state(run_id)
        from zet.services.local_image_evaluation_service import supersede_evaluations
        supersede_evaluations(state, {str(candidate["view"])}, "A candidate in this view is being retried.")
        self._save_state(run_id, state)
        if candidate["status"] == "FAILED":
            ask_id = str(candidate.get("ask_id") or "")
            proxy_status, answer = self._proxy_answer(ask_id) if ask_id else ("UNKNOWN", {})
            if ask_id and (proxy_status in {"QUEUED", "RUNNING"} or str(answer.get("status") or "").upper() == "SUCCESS"):
                self._candidate_update(run_id, candidate_id, {"status": "QUEUED", "render_error": ""})
            else:
                self._candidate_update(run_id, candidate_id, {
                    "status": "PENDING", "render_error": "", "ask_id": "", "image_path": "",
                    "retry_count": int(candidate.get("retry_count") or 0) + 1,
                })
        elif candidate["status"] in {"COMPLETE", "WAITING_FOR_HUMAN_REVIEW", "WAITING_FOR_ANALYSIS"}:
            if not (candidate.get("luna_status") == "FAILED" or
                    (candidate.get("local_job") or {}).get("status") == "FAILED"):
                raise LocalBodyReferenceError("This candidate has no failed analysis to retry.")
            self._candidate_update(run_id, candidate_id, {
                "status": "WAITING_FOR_ANALYSIS",
                "luna_status": "PENDING" if candidate.get("luna_status") == "FAILED" else candidate.get("luna_status"),
                "local_job": {} if (candidate.get("local_job") or {}).get("status") == "FAILED" else candidate.get("local_job"),
            })
        else:
            raise LocalBodyReferenceError("Only a failed render or analysis can be retried.")
        return self.resume(run_id)

    def recover_failed_batch(self, run_id: str) -> dict[str, Any]:
        run = self.detail(run_id)
        for candidate in run["candidates"]:
            if candidate["status"] != "FAILED":
                continue
            ask_id = str(candidate.get("ask_id") or "")
            proxy_status, answer = self._proxy_answer(ask_id) if ask_id else ("UNKNOWN", {})
            if ask_id and (proxy_status in {"QUEUED", "RUNNING"} or str(answer.get("status") or "").upper() == "SUCCESS"):
                self._candidate_update(run_id, candidate["candidate_id"],
                                       {"status": "QUEUED", "render_error": ""})
            else:
                self._candidate_update(run_id, candidate["candidate_id"], {
                    "status": "PENDING", "render_error": "", "ask_id": "", "image_path": "",
                    "retry_count": int(candidate.get("retry_count") or 0) + 1,
                })
        return self.resume(run_id)

    def retry_failed_analyses(self, run_id: str) -> dict[str, Any]:
        run = self.detail(run_id)
        for candidate in run["candidates"]:
            if candidate["status"] not in {"COMPLETE", "WAITING_FOR_HUMAN_REVIEW", "WAITING_FOR_ANALYSIS"}:
                continue
            update: dict[str, Any] = {}
            job = candidate.get("local_job") or {}
            if job.get("status") == "FAILED":
                job["status"] = "QUEUED"
                job.pop("error", None)
                update["local_job"] = job
            if candidate.get("luna_status") == "FAILED":
                update.update(luna_status="PENDING", luna_error="")
            if update:
                update["status"] = "WAITING_FOR_ANALYSIS"
                self._candidate_update(run_id, candidate["candidate_id"], update)
        return self.resume(run_id)
    @staticmethod
    def _luna_environment() -> dict[str, str]:
        """Keep authentication while removing the desktop task's live tool context."""
        return {key: value for key, value in os.environ.items()
                if key == "CODEX_HOME" or not key.startswith(("CODEX_", "NODE_REPL_", "CUA_", "BROWSER_"))}

    def run_luna_analysis(self, run_id: str, candidate_id: str) -> dict[str, Any]:
        run = self.detail(run_id)
        candidate = next((item for item in run["candidates"] if item["candidate_id"] == candidate_id), None)
        if not candidate:
            raise LocalBodyReferenceError(f"Unknown candidate: {candidate_id}")
        image = Path(str(candidate.get("image_path") or ""))
        if not image.is_file():
            raise LocalBodyReferenceError("A completed candidate image is required for Luna analysis.")
        anchor = next((item for item in run["candidates"] if item["candidate_id"] == run.get("front_anchor")), None)
        images = [image]
        if candidate["view"] != FRONT_VIEW:
            anchor_image = Path(str(anchor.get("image_path") or "")) if anchor else None
            if anchor_image is None or not anchor_image.is_file():
                raise LocalBodyReferenceError("Select a completed front anchor before reviewing other views.")
            images = [anchor_image, image]
        prompt = self.analysis_prompt(candidate, anchor=candidate["view"] != FRONT_VIEW,
                                      facts=self._review_facts(run, candidate["view"]))
        started = time.perf_counter()
        result, _ = self.app.ai_proxy_service.ai_proxy_path_service.jobs.generate_json(
            "codex:" + self.app.config.codex_default_model.removeprefix("codex:"), "", prompt,
            self.analysis_schema(), images, task_type="local_body_reference_review",
            owner={"run_id": run_id, "candidate_id": candidate_id})
        hashes = {"candidate": self._hash(image), "front_anchor": self._hash(images[0]) if len(images) == 2 else ""}
        self.record_analysis(run_id, candidate_id, "luna", result, hashes)
        return {"provider": "luna", "status": "COMPLETE", "elapsed_seconds": round(time.perf_counter() - started, 3), "result": result}

    def set_lineup(self, run_id: str, method: str, selections: dict[str, str]) -> dict[str, Any]:
        if method != METHOD_FRONT_CONDITIONED:
            raise LocalBodyReferenceError("Unknown Local Body-Reference method.")
        run = self.detail(run_id)
        allowed_views = set(run.get("views") or [])
        if set(selections) - allowed_views:
            raise LocalBodyReferenceError("Lineup contains an unknown view.")
        by_id = {item["candidate_id"]: item for item in run.get("candidates") or []}
        for view, candidate_id in selections.items():
            candidate = by_id.get(str(candidate_id))
            if not candidate or candidate.get("view") != view:
                raise LocalBodyReferenceError(f"Candidate {candidate_id} does not belong to view {view}.")
            if view != FRONT_VIEW and candidate.get("method") != method:
                raise LocalBodyReferenceError("Lineup candidate uses the wrong generation method.")
            if candidate.get("disposition") not in {"joint_pass", "human_keep"}:
                raise LocalBodyReferenceError("Only jointly passed or human-kept candidates can enter a lineup.")
        state = self._read_json((self._root(run_id) / "state.json"))
        state.setdefault("lineups", {})[method] = dict(selections)
        state["set_report"] = self.compare_lineups(run, state["lineups"])
        state["updated_at"] = self._now()
        self._save_state(run_id, state)
        return self.detail(run_id)

    @staticmethod
    def disposition(local: dict[str, Any], luna: dict[str, Any]) -> str:
        if not local or not luna:
            return "pending"
        local_pass = local.get("pass") is True and not local.get("uncertain", False)
        luna_pass = luna.get("pass") is True and not luna.get("uncertain", False)
        if local_pass and luna_pass:
            return "joint_pass"
        local_fail = local.get("pass") is False and not local.get("uncertain", False)
        luna_fail = luna.get("pass") is False and not luna.get("uncertain", False)
        if local_fail and luna_fail:
            return "joint_fail"
        return "human_triage"

    @staticmethod
    def compare_lineups(run: dict[str, Any], selections: dict[str, dict[str, str]]) -> dict[str, Any]:
        by_id = {item.get("candidate_id"): item for item in run.get("candidates") or []}
        report: dict[str, Any] = {"views": {}, "methods": {}, "coherent": {}}
        for method in (METHOD_TEXT_FIRST, METHOD_FRONT_CONDITIONED):
            chosen = selections.get(method) or {}
            rows = [by_id.get(candidate_id) for candidate_id in chosen.values()]
            rows = [row for row in rows if row]
            failures: dict[str, int] = {}
            proportion_notes: list[str] = []
            for row in rows:
                for analysis in (row.get("analyses") or {}).values():
                    for reason in analysis.get("failure_categories") or []:
                        failures[str(reason)] = failures.get(str(reason), 0) + 1
                    note = str(analysis.get("proportion_notes") or "").strip()
                    if note:
                        proportion_notes.append(note)
            report["methods"][method] = {
                "view_count": len(chosen), "complete": len(chosen) == len(run.get("views") or []),
                "usable_count": sum(row.get("disposition") in {"joint_pass", "human_keep"} for row in rows),
                "failure_distribution": failures, "proportion_notes": proportion_notes,
            }
            report["coherent"][method] = len(chosen) == len(run.get("views") or [])
        for view in run.get("views") or []:
            report["views"][view] = {}
            for method in (METHOD_TEXT_FIRST, METHOD_FRONT_CONDITIONED):
                candidate_id = (selections.get(method) or {}).get(view)
                row = by_id.get(candidate_id) if candidate_id else None
                analyses = (row or {}).get("analyses") or {}
                report["views"][view][method] = {
                    "candidate_id": candidate_id,
                    "disposition": (row or {}).get("disposition", "missing"),
                    "proportion_notes": [str(item.get("proportion_notes") or "") for item in analyses.values()
                                         if str(item.get("proportion_notes") or "").strip()],
                    "failure_categories": sorted({str(reason) for item in analyses.values()
                                                   for reason in item.get("failure_categories") or []}),
                }
        return report
