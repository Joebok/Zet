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

from Scripts.Run_Body_Reference_Jobs import compile_body_reference_job
from zet.services.local_render_backend_service import LocalRenderBackendService
from zet.services.workflow_storage import file_lock


class BodyReferenceExperimentError(ValueError):
    """Raised when a Body-Reference experiment cannot be planned safely."""


DEFAULT_VIEWS = (
    "FRONT", "FRONT_LEFT_3_4", "FRONT_RIGHT_3_4", "LEFT_PROFILE",
    "RIGHT_PROFILE", "BACK_LEFT_3_4", "BACK_RIGHT_3_4", "BACK",
)
FRONT_VIEW = "FRONT"
METHOD_TEXT_FIRST = "text_first"
METHOD_FRONT_CONDITIONED = "front_conditioned"
PILOT_FRONT_COUNT = 16
PILOT_OTHER_COUNT = 4


class BodyReferenceExperimentService:
    """Plan and persist a non-canonical Qwen Body-Reference experiment.

    The experiment owns its prompt snapshots, candidate slots, and decisions. It
    deliberately does not mutate canonical Assets or pipeline state.
    """

    _runner_lock = threading.Lock()
    _active_runs: set[str] = set()
    _active_runs_lock = threading.Lock()

    def __init__(self, app: Any, project_root: str | Path):
        self.app = app
        self.project_root = Path(project_root).resolve()
        self.library_root = Path(app.config.base_library_path).resolve()
        self.experiments_root = self.library_root / "Experiments" / "Character-Pipeline"

    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat(timespec="seconds")

    @staticmethod
    def _hash(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def _write(path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        temp.replace(path)

    @staticmethod
    def _safe(value: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip())
        return cleaned.strip("._") or "unknown"

    def _runner_is_active(self, run_id: str) -> bool:
        """Return whether a live process still owns this run's durable lock."""
        with self._active_runs_lock:
            if run_id in self._active_runs:
                return True
        try:
            with file_lock(self._root(run_id) / "runner.lock", timeout=0):
                return False
        except TimeoutError:
            return True
    def _views(self) -> list[str]:
        path = self.project_root / "Config" / "Prompt_View_Text.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
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
            raise BodyReferenceExperimentError("Character and phase are required.")
        views = self._views()
        if len(views) != 8:
            raise BodyReferenceExperimentError(f"Expected eight configured Body-Reference views; found {len(views)}.")
        front_count = int(payload.get("front_count") or PILOT_FRONT_COUNT)
        other_count = int(payload.get("other_count") or PILOT_OTHER_COUNT)
        if front_count < 1 or other_count < 1:
            raise BodyReferenceExperimentError("Candidate counts must be positive.")
        candidate_count = front_count + (len(views) - 1) * other_count * 2
        if candidate_count > 256:
            raise BodyReferenceExperimentError("Body-Reference experiment cannot exceed 256 candidates.")
        return {
            "character": character,
            "phase": phase,
            "views": views,
            "front_count": front_count,
            "other_count": other_count,
            "candidate_count": candidate_count,
            "methods": [METHOD_TEXT_FIRST, METHOD_FRONT_CONDITIONED],
            "front_anchor_required": True,
        }

    def _compile_view(self, root: Path, character: str, phase: str, view: str, index: int) -> dict[str, Any]:
        output = root / "prompts" / view
        job = {
            "Job": f"BodyReferenceExperiment_{root.name}_{view}",
            "Task": "body-reference",
            "Character": character,
            "Phase": phase,
            "Body View": view,
            "Output Directory": str(output),
        }
        try:
            result = compile_body_reference_job(job, self.project_root)
            analysis = self._compile_analysis_view(root, character, phase, view)
        except Exception as exc:
            raise BodyReferenceExperimentError(f"Could not compile Body-Reference prompt for {view}: {exc}") from exc
        final_prompt = Path(str(result["final_prompt"]))
        if not final_prompt.is_file():
            raise BodyReferenceExperimentError(f"Compiled prompt is missing for {view}: {final_prompt}")
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
            "Job": f"BodyReferenceExperiment_{root.name}_{view}",
            "Task": "body-reference",
            "Character": character,
            "Phase": phase,
            "Body View": view,
            "Output Directory": str(output),
        }
        result = compile_body_reference_job(job, self.project_root, prompt_variant="analysis")
        prompt_path = Path(str(result["final_prompt"]))
        if not prompt_path.is_file():
            raise BodyReferenceExperimentError(f"Compiled analysis prompt is missing for {view}: {prompt_path}")
        template_path = self.project_root / "Config" / "Prompt_Templates" / "body_reference_v2.md"
        return {
            "analysis_specification": prompt_path.read_text(encoding="utf-8"),
            "analysis_prompt_path": str(prompt_path),
            "analysis_template_sha256": self._hash(template_path),
        }

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
        return f"{instruction} Character facts: {body[:5000]}"

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
            raise BodyReferenceExperimentError("Qwen workflow requires prompt, diffusion model, text encoder, and VAE.")
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
        root = self.experiments_root / self._safe(plan["character"]) / self._safe(plan["phase"]) / run_id
        root.mkdir(parents=True, exist_ok=False)
        prompts = [self._compile_view(root, plan["character"], plan["phase"], view, index)
                   for index, view in enumerate(plan["views"], start=1)]
        seeds = payload.get("seeds")
        if not isinstance(seeds, list):
            generator = random.SystemRandom()
            seeds = [generator.randrange(0, 2**63 - 1) for _ in range(plan["candidate_count"])]
        if len(seeds) != plan["candidate_count"]:
            raise BodyReferenceExperimentError("Explicit seed count must match the candidate plan.")
        try:
            seeds = [str(int(seed)) for seed in seeds]
        except (TypeError, ValueError) as exc:
            raise BodyReferenceExperimentError("Every seed must be an integer.") from exc
        candidates: list[dict[str, Any]] = []
        seed_index = 0
        for view_index, prompt in enumerate(prompts):
            count_methods = ["shared_front"] if prompt["view"] == FRONT_VIEW else [METHOD_TEXT_FIRST, METHOD_FRONT_CONDITIONED]
            count = plan["front_count"] if prompt["view"] == FRONT_VIEW else plan["other_count"]
            for method in count_methods:
                for ordinal in range(count):
                    candidate_id = f"c{len(candidates) + 1:03d}"
                    candidate_prompt = prompt["qwen_prompt"]
                    if method == METHOD_FRONT_CONDITIONED:
                        candidate_prompt = self._qwen_prompt(prompt["manual_prompt"], prompt["view"], anchor=True)
                    candidates.append({
                        "candidate_id": candidate_id, "view": prompt["view"], "view_index": view_index + 1,
                        "method": method, "ordinal": ordinal + 1, "seed": str(seeds[seed_index]),
                        "prompt": candidate_prompt, "prompt_sha256": hashlib.sha256(candidate_prompt.encode()).hexdigest(),
                        "status": "PENDING", "image_path": "", "render_error": "",
                        "analyses": {}, "disposition": "pending", "human_review": {"decision": "undecided", "notes": ""},
                    })
                    seed_index += 1
        spec = {
            "schema_version": 1, "kind": "body_reference_qwen_experiment", "run_id": run_id,
            "created_at": self._now(), "status": "AWAITING_FRONT_ANCHOR", "character": plan["character"],
            "phase": plan["phase"], "views": plan["views"], "front_view": FRONT_VIEW,
            "front_count": plan["front_count"], "other_count": plan["other_count"],
            "candidate_count": len(candidates), "methods": plan["methods"], "seeds": [str(seed) for seed in seeds],
            "prompt_snapshots": prompts, "candidates": candidates,
            "source_snapshot_sha256": hashlib.sha256(json.dumps(prompts, sort_keys=True).encode()).hexdigest(),
            "front_anchor": None, "lineups": {}, "created_by": "zet",
        }
        self._write(root / "spec.json", spec)
        self._write(root / "state.json", {"run_id": run_id, "status": spec["status"], "updated_at": self._now(),
                                            "stop_requested": False, "candidates": {}})
        return {**spec, "root": str(root)}

    def _root(self, run_id: str) -> Path:
        if not re.fullmatch(r"\d{8}_\d{6}_\d{6}", str(run_id or "")):
            raise BodyReferenceExperimentError("Invalid Body-Reference experiment id.")
        matches = list(self.experiments_root.glob(f"*/ */{run_id}".replace(" ", "")))
        if matches:
            return matches[0]
        for path in self.experiments_root.glob(f"*/*/{run_id}"):
            if (path / "spec.json").is_file():
                return path
        raise BodyReferenceExperimentError(f"Body-Reference experiment not found: {run_id}")

    def detail(self, run_id: str) -> dict[str, Any]:
        root = self._root(run_id)
        value = json.loads((root / "spec.json").read_text(encoding="utf-8"))
        state = json.loads((root / "state.json").read_text(encoding="utf-8")) if (root / "state.json").is_file() else {}
        candidates = {item["candidate_id"]: dict(item) for item in value.get("candidates", [])}
        for candidate_id, update in (state.get("candidates") or {}).items():
            if candidate_id in candidates:
                candidates[candidate_id].update(update)
        stored_status = state.get("status") or value.get("status")
        interrupted = stored_status in {"PREFLIGHT", "RUNNING", "STOPPING", "REEVALUATING"} and not self._runner_is_active(run_id)
        value["status"] = "INTERRUPTED" if interrupted else stored_status
        value["interrupted"] = interrupted
        value["stop_requested"] = bool(state.get("stop_requested", False))
        value["review_only"] = bool(state.get("review_only", False))
        value["post_review_status"] = state.get("post_review_status") or ""
        value["error"] = state.get("error") or ("The experiment runner stopped before this batch finished." if interrupted else "")
        value["front_anchor"] = state.get("front_anchor") or value.get("front_anchor")
        value["lineups"] = state.get("lineups") or value.get("lineups") or {}
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
        value["root"] = str(root)
        return value

    def list_runs(self, character: str = "", phase: str = "") -> list[dict[str, Any]]:
        """Return selectable experiment batches, newest first."""
        wanted_character = str(character or "").strip()
        wanted_phase = str(phase or "").strip()
        runs: list[dict[str, Any]] = []
        for spec_path in self.experiments_root.glob("*/*/*/spec.json"):
            try:
                spec = json.loads(spec_path.read_text(encoding="utf-8"))
                if wanted_character and spec.get("character") != wanted_character:
                    continue
                if wanted_phase and spec.get("phase") != wanted_phase:
                    continue
                run = self.detail(str(spec.get("run_id") or spec_path.parent.name))
            except (OSError, ValueError, json.JSONDecodeError, BodyReferenceExperimentError):
                continue
            counts: dict[str, int] = {}
            for candidate in run.get("candidates") or []:
                status = str(candidate.get("status") or "UNKNOWN")
                counts[status] = counts.get(status, 0) + 1
            runs.append({
                "run_id": run["run_id"], "character": run.get("character", ""),
                "phase": run.get("phase", ""), "created_at": run.get("created_at", ""),
                "status": run.get("status", ""), "candidate_count": len(run.get("candidates") or []),
                "complete_count": counts.get("COMPLETE", 0), "front_anchor": run.get("front_anchor"),
                "source_run_id": run.get("source_run_id", ""),
            })
        return sorted(runs, key=lambda item: str(item.get("created_at") or item["run_id"]), reverse=True)

    def list_codex_jobs(self) -> list[dict[str, Any]]:
        """Summarize Codex/Luna reviews across experiment batches."""
        jobs = []
        for summary in self.list_runs():
            run = self.detail(summary["run_id"])
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
                               ("Waiting for candidate image" if candidate.get("status") != "COMPLETE"
                                and status == "PENDING" else ""),
                })
        return jobs

    def rerun(self, run_id: str) -> dict[str, Any]:
        """Create a fresh batch using the selected run's character and counts."""
        source = self.detail(run_id)
        fresh = self.create_run({
            "character": source["character"], "phase": source["phase"],
            "front_count": source.get("front_count", PILOT_FRONT_COUNT),
            "other_count": source.get("other_count", PILOT_OTHER_COUNT),
        })
        root = self._root(fresh["run_id"])
        spec = json.loads((root / "spec.json").read_text(encoding="utf-8"))
        spec["source_run_id"] = run_id
        self._write(root / "spec.json", spec)
        fresh["source_run_id"] = run_id
        return fresh

    def rerun_view(self, run_id: str, view: str) -> dict[str, Any]:
        """Replace the selected view's images and reviews in the existing batch."""
        run = self.detail(run_id)
        view = str(view or "").upper()
        if view not in run.get("views", []):
            raise BodyReferenceExperimentError(f"Unknown experiment view: {view}")
        if run["status"] in {"PREFLIGHT", "RUNNING", "STOPPING", "REEVALUATING"}:
            raise BodyReferenceExperimentError("Stop the active batch before re-running a view.")
        if self._runner_lock.locked():
            raise BodyReferenceExperimentError("Another experiment batch is running; try again when it finishes.")
        candidates = [item for item in run["candidates"] if item.get("view") == view]
        if not candidates:
            raise BodyReferenceExperimentError(f"This batch has no candidates for view {view}.")

        root = self._root(run_id).resolve()
        state = json.loads((root / "state.json").read_text(encoding="utf-8"))
        stamp = self._now()
        for candidate in candidates:
            old_analyses = candidate.get("analyses") or {}
            update = state.setdefault("candidates", {}).setdefault(candidate["candidate_id"], {})
            if old_analyses:
                history = list(candidate.get("analysis_history") or [])
                history.append({"archived_at": stamp, "analyses": old_analyses})
                update["analysis_history"] = history
            image_text = str(candidate.get("image_path") or "")
            if image_text:
                try:
                    image_path = Path(image_text).resolve()
                    if image_path.is_relative_to(root):
                        image_path.unlink(missing_ok=True)
                except (OSError, RuntimeError):
                    pass
            update.update(
                status="PENDING", seed=str(random.SystemRandom().randrange(0, 2**63 - 1)),
                image_path="", image_sha256="", ask_id="", queued_at="",
                completed_at="", render_error="", analyses={}, local_job={}, luna_status="",
                luna_error="", disposition="pending", human_review={"decision": "undecided", "notes": ""},
                retry_count=int(candidate.get("retry_count") or 0) + 1,
            )

        if view == FRONT_VIEW:
            state["front_anchor"] = None
            state["lineups"] = {}
            state["set_report"] = {}
        else:
            for selections in (state.get("lineups") or {}).values():
                selections.pop(view, None)
            state["set_report"] = {}
        state.update(
            status="RUNNING", review_only=False, target_views=[view], stop_requested=False,
            error="", updated_at=stamp,
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
                raise BodyReferenceExperimentError(f"Unknown experiment view: {normalized_view}")
            target_views = [normalized_view]
        if run["status"] in {"PREFLIGHT", "RUNNING", "STOPPING", "REEVALUATING"}:
            raise BodyReferenceExperimentError("Stop the active batch before re-evaluating it.")
        if self._runner_lock.locked():
            raise BodyReferenceExperimentError("Another experiment batch is running; try again when it finishes.")
        completed = [item for item in run["candidates"] if item.get("status") == "COMPLETE"
                     and item.get("view") in target_views
                     and Path(str(item.get("image_path") or "")).is_file()]
        if not completed:
            scope = f" for view {target_views[0]}" if view is not None else ""
            raise BodyReferenceExperimentError(f"This batch has no completed images to re-evaluate{scope}.")
        for target_view in target_views:
            if view is None or any(item.get("view") == target_view for item in completed):
                self._review_facts(run, target_view)
        state = json.loads((self._root(run_id) / "state.json").read_text(encoding="utf-8"))
        stamp = self._now()
        for candidate in completed:
            update = state.setdefault("candidates", {}).setdefault(candidate["candidate_id"], {})
            old = candidate.get("analyses") or {}
            if old:
                history = list(candidate.get("analysis_history") or [])
                history.append({"archived_at": stamp, "analyses": old})
                update["analysis_history"] = history
            decision = (candidate.get("human_review") or {}).get("decision")
            update.update(analyses={}, local_job={}, luna_status="PENDING", luna_error="",
                          disposition="human_keep" if decision == "keep" else
                          "human_reject" if decision == "reject" else "pending")
        state.update(status="REEVALUATING", review_only=True, target_views=target_views,
                     stop_requested=False, post_review_status=run["status"], error="", updated_at=stamp)
        self._save_state(run_id, state)
        result = self.detail(run_id)
        result.update(status="REEVALUATING", interrupted=False, error="")
        return result
    def delete_run(self, run_id: str) -> dict[str, Any]:
        root = self._root(run_id).resolve()
        experiments_root = self.experiments_root.resolve()
        if (root.parent.parent.parent != experiments_root or root.name != run_id
                or not root.is_relative_to(experiments_root)):
            raise BodyReferenceExperimentError("Invalid experiment batch location.")
        state_path = root / "state.json"
        if state_path.is_file():
            try:
                state = json.loads(state_path.read_text(encoding="utf-8"))
            except (OSError, ValueError, json.JSONDecodeError):
                state = {}
            if state.get("status") in {"PREFLIGHT", "RUNNING", "STOPPING", "REEVALUATING"}:
                raise BodyReferenceExperimentError("Stop the batch and wait for it to finish before deleting it.")
        shutil.rmtree(root)
        return {"deleted": True, "run_id": run_id}

    def _save_state(self, run_id: str, state: dict[str, Any]) -> None:
        self._write(self._root(run_id) / "state.json", state)

    def select_front_anchor(self, run_id: str, candidate_id: str) -> dict[str, Any]:
        run = self.detail(run_id)
        candidate = next((item for item in run["candidates"] if item["candidate_id"] == candidate_id), None)
        if not candidate or candidate["view"] != FRONT_VIEW:
            raise BodyReferenceExperimentError("Only a front-view candidate can become the anchor.")
        if candidate.get("status") != "COMPLETE":
            raise BodyReferenceExperimentError("The front anchor must have a completed render.")
        if candidate.get("human_review", {}).get("decision") != "keep":
            raise BodyReferenceExperimentError("A human must keep the front anchor after both analyses.")
        if not all(candidate.get("analyses", {}).get(provider) for provider in ("local", "luna")):
            raise BodyReferenceExperimentError("Both image analyses must finish before selecting the front anchor.")
        image_hash = self._hash(Path(candidate["image_path"]))
        if any(candidate["analyses"][provider].get("input_hashes", {}).get("candidate") != image_hash
               for provider in ("local", "luna")):
            raise BodyReferenceExperimentError("Front-anchor analysis is stale; rerun both analyses.")
        state = json.loads((self._root(run_id) / "state.json").read_text(encoding="utf-8"))
        state.update({"status": "READY_FOR_VIEWS", "updated_at": self._now(),
                      "front_anchor": candidate_id, "stop_requested": False})
        self._save_state(run_id, state)
        return self.detail(run_id)

    def update_candidate(self, run_id: str, candidate_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        run = self.detail(run_id)
        candidate = next((item for item in run["candidates"] if item["candidate_id"] == candidate_id), None)
        if candidate is None:
            raise BodyReferenceExperimentError(f"Unknown candidate: {candidate_id}")
        update = {"human_review": {"decision": str(payload.get("decision") or "undecided"),
                                   "notes": str(payload.get("notes") or "")}}
        if update["human_review"]["decision"] not in {"keep", "reject", "undecided"}:
            raise BodyReferenceExperimentError("Human decision must be keep, reject, or undecided.")
        if candidate.get("status") != "COMPLETE" or not all(candidate.get("analyses", {}).get(provider)
                                                            for provider in ("local", "luna")):
            raise BodyReferenceExperimentError("Both image analyses must finish before human review.")
        if update["human_review"]["decision"] == "keep":
            update["disposition"] = "human_keep"
        elif update["human_review"]["decision"] == "reject":
            update["disposition"] = "human_reject"
        state = json.loads((self._root(run_id) / "state.json").read_text(encoding="utf-8"))
        state.setdefault("candidates", {}).setdefault(candidate_id, {}).update(update)
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
            raise BodyReferenceExperimentError("Analysis provider must be local or luna.")
        if not isinstance(result, dict) or not isinstance(input_hashes, dict):
            raise BodyReferenceExperimentError("Analysis result and input hashes must be objects.")
        if "pass" not in result or not isinstance(result.get("pass"), bool):
            raise BodyReferenceExperimentError("Analysis result must include a boolean pass field.")
        if (not isinstance(result.get("uncertain"), bool)
                or not isinstance(result.get("criteria"), dict)
                or not isinstance(result.get("failure_categories"), list)
                or not isinstance(result.get("evidence"), str)
                or not isinstance(result.get("failure_reason"), str)):
            raise BodyReferenceExperimentError("Analysis result is missing structured rubric fields.")
        run = self.detail(run_id)
        candidate = next((item for item in run["candidates"] if item["candidate_id"] == candidate_id), None)
        if candidate is None:
            raise BodyReferenceExperimentError(f"Unknown candidate: {candidate_id}")
        image = Path(str(candidate.get("image_path") or ""))
        if candidate.get("status") != "COMPLETE" or not image.is_file():
            raise BodyReferenceExperimentError("Analysis requires a completed candidate image.")
        if input_hashes.get("candidate") != self._hash(image):
            raise BodyReferenceExperimentError("Analysis input hash does not match the candidate image.")
        if candidate["view"] != FRONT_VIEW:
            anchor = next((item for item in run["candidates"] if item["candidate_id"] == run.get("front_anchor")), None)
            anchor_image = Path(str(anchor.get("image_path") or "")) if anchor else None
            if anchor_image is None or not anchor_image.is_file() or input_hashes.get("front_anchor") != self._hash(anchor_image):
                raise BodyReferenceExperimentError("Analysis front-anchor hash is missing or stale.")
        analysis = {**result, "provider": provider, "input_hashes": dict(input_hashes), "recorded_at": self._now()}
        state = json.loads((self._root(run_id) / "state.json").read_text(encoding="utf-8"))
        updates = state.setdefault("candidates", {}).setdefault(candidate_id, {})
        analyses = dict(updates.get("analyses") or candidate.get("analyses") or {})
        analyses[provider] = analysis
        updates["analyses"] = analyses
        if "local" in analyses and "luna" in analyses:
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
            "\n\nRequested view: " + str(candidate.get("view") or "")
            + "\n\nAuthoritative Body-Reference specification:\n" + facts
        )

    def _review_facts(self, run: dict[str, Any], view: str) -> str:
        prompt = next((item for item in run.get("prompt_snapshots", []) if item.get("view") == view), {})
        template_path = self.project_root / "Config" / "Prompt_Templates" / "body_reference_v2.md"
        if not template_path.is_file():
            return str(prompt.get("analysis_specification") or prompt.get("manual_prompt") or "")
        template_hash = self._hash(template_path)
        if prompt.get("analysis_template_sha256") == template_hash and prompt.get("analysis_specification"):
            return str(prompt["analysis_specification"])

        root = Path(str(run["root"]))
        spec_path = root / "spec.json"
        with file_lock(root / "analysis_prompt.lock"):
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            snapshot = next((item for item in spec.get("prompt_snapshots", []) if item.get("view") == view), None)
            if snapshot is None:
                raise BodyReferenceExperimentError(f"No saved prompt for view {view}.")
            if snapshot.get("analysis_template_sha256") != template_hash or not snapshot.get("analysis_specification"):
                try:
                    snapshot.update(self._compile_analysis_view(root, spec["character"], spec["phase"], view))
                except Exception as exc:
                    raise BodyReferenceExperimentError(f"Could not refresh analysis prompt for {view}: {exc}") from exc
                spec["source_snapshot_sha256"] = hashlib.sha256(
                    json.dumps(spec["prompt_snapshots"], sort_keys=True).encode()
                ).hexdigest()
                self._write(spec_path, spec)
            return str(snapshot["analysis_specification"])

    def review_prompt(self, run_id: str, view: str) -> str:
        """Return the shared local/Codex review prompt for one experiment view."""
        run = self.detail(run_id)
        if view not in run.get("views", []):
            raise BodyReferenceExperimentError(f"Unknown experiment view: {view}")
        candidate = {"view": view}
        return self.analysis_prompt(
            candidate,
            anchor=view != FRONT_VIEW,
            facts=self._review_facts(run, view),
        )

    def queue_local_analysis(self, run_id: str, candidate_id: str, model: str = "") -> dict[str, Any]:
        run = self.detail(run_id)
        candidate = next((item for item in run["candidates"] if item["candidate_id"] == candidate_id), None)
        if not candidate or not Path(str(candidate.get("image_path") or "")).is_file():
            raise BodyReferenceExperimentError("A completed candidate image is required for local analysis.")
        image = Path(candidate["image_path"])
        anchor_id = run.get("front_anchor")
        anchor = next((item for item in run["candidates"] if item["candidate_id"] == anchor_id), None)
        anchor_image = Path(str(anchor.get("image_path") or "")) if anchor else None
        if candidate["view"] != FRONT_VIEW and (anchor_image is None or not anchor_image.is_file()):
            raise BodyReferenceExperimentError("Select a completed front anchor before reviewing other views.")
        proxy = self.app.ai_proxy_service.ai_proxy_path_service.file_proxy_client
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        ask_id = f"Ask_BodyReference_{run_id}_{candidate_id}_LOCAL_{stamp}"
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
            "pipeline": "Character-Pipeline-Experiment", "pipeline_stage": "BODY_REFERENCE_ANALYSIS",
            "worker_type": "ollama_generate", "ollama_model": model or getattr(self.app.config, "ai_prompt_evolution_vision_model", "image-analysis:latest"),
            "prompt_file": "OLLAMA_PROMPT.md", "image_files": [name for name, _ in files], "json_output": True,
            "response_schema": self.analysis_schema(), "expected_output": "response.json", "task_type": "body_reference_analysis",
            "auxiliary": True, "target_output_dir": str(output.parent), "target_output_file": output.name,
            "body_reference_run_id": run_id, "candidate_id": candidate_id,
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
        state = json.loads((self._root(run_id) / "state.json").read_text(encoding="utf-8"))
        state.setdefault("candidates", {}).setdefault(candidate_id, {}).update(update)
        state["updated_at"] = self._now()
        self._save_state(run_id, state)

    def _run_update(self, run_id: str, **update: Any) -> None:
        state = json.loads((self._root(run_id) / "state.json").read_text(encoding="utf-8"))
        state.update(update, updated_at=self._now())
        self._save_state(run_id, state)

    def _proxy_answer(self, ask_id: str) -> tuple[str, dict[str, Any]]:
        paths = self.app.ai_proxy_service.ai_proxy_path_service
        roots = (("QUEUED", paths.ask_root()), ("RUNNING", paths.running_root()),
                 ("ANSWERED", paths.answer_root()))
        for status, root in roots:
            record = root / ask_id
            if record.is_dir():
                try:
                    answer = json.loads((record / "answer_manifest.json").read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    answer = {}
                return status, answer
        for record in paths.harvested_archive_root().glob(f"*/{ask_id}"):
            try:
                answer = json.loads((record / "answer_manifest.json").read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                answer = {}
            return "HARVESTED", answer
        return "UNKNOWN", {}

    def _harvest_experiment_answer(self, run_id: str, candidate_id: str, ask_id: str, target: Path) -> None:
        paths = self.app.ai_proxy_service.ai_proxy_path_service
        answer_path = paths.answer_root() / ask_id
        if not answer_path.is_dir():
            return
        if not (answer_path / "answer_manifest.json").is_file():
            return
        try:
            ask = json.loads((answer_path / "ask_manifest.json").read_text(encoding="utf-8"))
            answer = json.loads((answer_path / "answer_manifest.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise BodyReferenceExperimentError(f"Invalid AI Proxy answer {ask_id}: {exc}") from exc
        if ask.get("ask_id") != ask_id or answer.get("ask_id") != ask_id:
            raise BodyReferenceExperimentError("AI Proxy answer ID does not match the queued job.")
        source_id = str(ask.get("source_ask_id") or "")
        render_source = re.fullmatch(rf"BodyReference_{re.escape(run_id)}_{re.escape(candidate_id)}_\d+", source_id)
        if (ask.get("body_reference_run_id") != run_id or ask.get("candidate_id") != candidate_id) and not render_source:
            raise BodyReferenceExperimentError("AI Proxy answer does not belong to this experiment candidate.")
        status = str(answer.get("status") or "").upper()
        if status in {"ERROR", "RETRY_LATER"}:
            raise BodyReferenceExperimentError(str(answer.get("error_message") or "AI Proxy job failed."))
        if status != "SUCCESS":
            return
        expected = str(ask.get("expected_output") or "")
        if not expected or Path(expected).name != expected or answer.get("expected_output") != expected:
            raise BodyReferenceExperimentError("AI Proxy answer output filename is invalid.")
        if ask.get("task_type") == "body_reference_analysis":
            filename = str(ask.get("target_output_file") or "")
            if not re.fullmatch(r"local(?:_\d{8}_\d{6}_\d{6})?\.json", filename):
                raise BodyReferenceExperimentError("AI Proxy analysis output filename is invalid.")
            expected_target = self._root(run_id) / "analyses" / candidate_id / filename
            if ask.get("target_output_file") != target.name:
                raise BodyReferenceExperimentError("AI Proxy analysis output filename is invalid.")
        else:
            expected_target = self._root(run_id) / "renders" / candidate_id / "Local_Test_Renders" / expected
            if ask.get("task_type") != "local_test_render" or ask.get("target_output_file") != expected:
                raise BodyReferenceExperimentError("AI Proxy render output filename is invalid.")
        if expected_target.resolve() != target.resolve() or not target.resolve().is_relative_to(self._root(run_id).resolve()):
            raise BodyReferenceExperimentError("AI Proxy answer target does not match the experiment slot.")
        source = answer_path / expected
        if not source.is_file() or source.stat().st_size == 0:
            raise BodyReferenceExperimentError("AI Proxy answer is missing its output file.")
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + f".{os.getpid()}.tmp")
        shutil.copy2(source, temporary)
        temporary.replace(target)

    def _preflight(self) -> None:
        backend = LocalRenderBackendService(self.project_root / "Config" / "Local_Render_Presets.json")
        inventory = backend.comfyui_options(self.app.config.comfyui_server_url)
        for name in ("comfyui-qwen-body-reference-text", "comfyui-qwen-body-reference-edit"):
            profile = backend.preset(name)
            if not profile:
                raise BodyReferenceExperimentError(f"Missing render preset: {name}")
            for key, available, label in (
                ("diffusion_model", inventory["diffusion_models"], "diffusion model"),
                ("text_encoder", inventory["text_encoders"], "text encoder"),
                ("vae", inventory["vaes"], "VAE"),
            ):
                if profile.get(key) not in available:
                    raise BodyReferenceExperimentError(f"ComfyUI is missing the {label}: {profile.get(key)}")
        required = {"UNETLoader", "CLIPLoader", "VAELoader", "TextEncodeQwenImage21",
                    "EmptyLatentImage", "KSampler", "VAEDecode", "SaveImage", "LoadImage"}
        missing = required - set(inventory["node_types"])
        if missing:
            raise BodyReferenceExperimentError("ComfyUI is missing nodes: " + ", ".join(sorted(missing)))

    def _render_view_candidates(self, run_id: str, view: str) -> bool:
        """Queue and finish every candidate image for one view before review work."""
        run = self.detail(run_id)
        candidates = [item for item in run["candidates"] if item.get("view") == view]

        # Publish the whole view's render batch before waiting on any one image.
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
            current = next(
                item for item in self.detail(run_id)["candidates"]
                if item["candidate_id"] == candidate["candidate_id"]
            )
            if current.get("status") not in {"QUEUED", "RUNNING"}:
                continue
            try:
                if not self._wait_for_render(run_id, current["candidate_id"]):
                    return False
            except Exception as exc:
                self._candidate_update(run_id, current["candidate_id"], {
                    "status": "FAILED", "render_error": str(exc),
                })
        return True

    def _review_view_candidates(self, run_id: str, view: str) -> bool:
        """Run all pending analyses for one view after its images are available."""
        candidates = [item for item in self.detail(run_id)["candidates"] if item.get("view") == view]
        for candidate in candidates:
            if self.detail(run_id)["stop_requested"]:
                return False
            current = next(
                item for item in self.detail(run_id)["candidates"]
                if item["candidate_id"] == candidate["candidate_id"]
            )
            if current.get("status") != "COMPLETE":
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
        candidate = next(item for item in self.detail(run_id)["candidates"] if item["candidate_id"] == candidate_id)
        image = Path(str(candidate.get("image_path") or ""))
        deadline = time.monotonic() + 1860
        while not image.is_file():
            if self.detail(run_id)["stop_requested"]:
                return False
            self._harvest_experiment_answer(run_id, candidate_id, str(candidate.get("ask_id") or ""), image)
            proxy_status, answer = self._proxy_answer(str(candidate.get("ask_id") or ""))
            if str(answer.get("status") or "").upper() in {"ERROR", "RETRY_LATER"}:
                raise BodyReferenceExperimentError(str(answer.get("error_message") or "AI Proxy render failed"))
            if proxy_status == "RUNNING" and candidate.get("status") != "RUNNING":
                self._candidate_update(run_id, candidate_id, {"status": "RUNNING"})
                candidate["status"] = "RUNNING"
            if time.monotonic() >= deadline:
                raise BodyReferenceExperimentError("Timed out waiting for the render; use Retry after checking AI Proxy.")
            time.sleep(max(0.5, float(self.app.config.comfyui_poll_seconds)))
        self._candidate_update(run_id, candidate_id, {"status": "COMPLETE", "completed_at": self._now(),
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
            self._harvest_experiment_answer(run_id, candidate_id, job["ask_id"], output)
            proxy_status, answer = self._proxy_answer(job["ask_id"])
            if str(answer.get("status") or "").upper() in {"ERROR", "RETRY_LATER"}:
                raise BodyReferenceExperimentError(str(answer.get("error_message") or "Local image analysis failed"))
            if proxy_status == "RUNNING" and job["status"] != "RUNNING":
                job["status"] = "RUNNING"
                self._candidate_update(run_id, candidate_id, {"local_job": job})
            if time.monotonic() >= deadline:
                raise BodyReferenceExperimentError("Timed out waiting for local image analysis.")
            time.sleep(2)
        try:
            result = json.loads(output.read_text(encoding="utf-8"))
            self.record_analysis(run_id, candidate_id, "local", result, job["input_hashes"])
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise BodyReferenceExperimentError(f"Invalid local image analysis: {exc}") from exc
        job["status"] = "COMPLETE"
        self._candidate_update(run_id, candidate_id, {"local_job": job})
        return True

    def execute_run(self, run_id: str) -> None:
        try:
            with file_lock(self._root(run_id) / "runner.lock", timeout=0):
                self._execute_run_locked(run_id)
        except TimeoutError:
            return

    def _execute_run_locked(self, run_id: str) -> None:
        if not self._runner_lock.acquire(blocking=False):
            return
        with self._active_runs_lock:
            self._active_runs.add(run_id)
        try:
            initial_state = json.loads((self._root(run_id) / "state.json").read_text(encoding="utf-8"))
            review_only = bool(initial_state.get("review_only"))
            target_views = list(initial_state.get("target_views") or [])
            if not review_only:
                self._run_update(run_id, status="PREFLIGHT", error="")
                self._preflight()
            self._run_update(run_id, status="REEVALUATING" if review_only else "RUNNING")
            run = self.detail(run_id)
            views = target_views or (list(run.get("views") or []) if review_only else (
                [FRONT_VIEW] if not run.get("front_anchor") else
                [view for view in run.get("views") or [] if view != FRONT_VIEW]
            ))
            for view in views:
                if self.detail(run_id)["stop_requested"]:
                    self._run_update(run_id, status="STOPPED")
                    return
                if not review_only and not self._render_view_candidates(run_id, view):
                    self._run_update(run_id, status="STOPPED")
                    return
                if not self._review_view_candidates(run_id, view):
                    self._run_update(run_id, status="STOPPED")
                    return
                if not self.detail(run_id).get("front_anchor"):
                    self._run_update(run_id, status="AWAITING_FRONT_ANCHOR", review_only=False, target_views=[])
                    return
            status = (run.get("post_review_status") or "AWAITING_FRONT_ANCHOR") if review_only else (
                "AWAITING_FRONT_ANCHOR" if not self.detail(run_id).get("front_anchor") else "COMPLETE"
            )
            self._run_update(run_id, status=status, review_only=False, target_views=[])
            return
        except Exception as exc:
            self._run_update(run_id, status="ERROR", review_only=False, error=str(exc))
        finally:
            with self._active_runs_lock:
                self._active_runs.discard(run_id)
            self._runner_lock.release()
    def queue_render_candidate(self, run_id: str, candidate_id: str) -> dict[str, Any]:
        run = self.detail(run_id)
        candidate = next((item for item in run["candidates"] if item["candidate_id"] == candidate_id), None)
        if not candidate:
            raise BodyReferenceExperimentError(f"Unknown candidate: {candidate_id}")
        if candidate.get("status") in {"QUEUED", "RUNNING", "COMPLETE"}:
            return candidate
        if candidate.get("view") != FRONT_VIEW and not run.get("front_anchor"):
            raise BodyReferenceExperimentError("Complete front analysis and select an anchor before rendering other views.")
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
                raise BodyReferenceExperimentError("Front-conditioned rendering requires a completed front anchor image.")
            references = [{"role": "body_reference_front_anchor", "path": str(anchor_path)}]
        root = self._root(run_id)
        candidate_dir = root / "renders" / candidate_id
        candidate_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = candidate_dir / "Qwen_Body_Reference_Prompt.md"
        prompt_path.write_text(f"Positive Prompt:\n{candidate['prompt']}\n\nNegative Prompt:\n", encoding="utf-8")
        profile = LocalRenderBackendService(self.project_root / "Config" / "Local_Render_Presets.json").preset(preset_name)
        checkpoint = str(profile.get("diffusion_model") or "").strip()
        manifest = {"ask_id": f"BodyReference_{run_id}_{candidate_id}_{int(candidate.get('retry_count') or 0)}", "character": run["character"],
                    "phase": run["phase"], "pipeline": "Character-Pipeline-Experiment", "pipeline_stage": "BODY_REFERENCE_RENDER"}
        ask_path = self.app.ai_proxy_service.stage_render_task_local_render_ask(
            manifest, prompt_path, candidate_dir, allow_parallel=True, seed=int(candidate["seed"]),
            checkpoint=checkpoint, render_preset=preset_name, image_generation="comfyui",
            reference_files=references,
        )
        ask = json.loads((ask_path / "ask_manifest.json").read_text(encoding="utf-8"))
        update = {"status": "QUEUED", "ask_id": ask["ask_id"], "queued_at": self._now(),
                  "image_path": str(candidate_dir / "Local_Test_Renders" / ask["expected_output"])}
        state = json.loads((root / "state.json").read_text(encoding="utf-8"))
        state.setdefault("candidates", {}).setdefault(candidate_id, {}).update(update)
        state["updated_at"] = self._now()
        self._save_state(run_id, state)
        return self.detail(run_id)

    def queue_next_render(self, run_id: str) -> dict[str, Any]:
        run = self.detail(run_id)
        state = json.loads((self._root(run_id) / "state.json").read_text(encoding="utf-8"))
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
        state = json.loads((self._root(run_id) / "state.json").read_text(encoding="utf-8"))
        state["stop_requested"] = True
        state["status"] = "STOPPING"
        state["updated_at"] = self._now()
        self._save_state(run_id, state)
        return self.detail(run_id)

    def resume(self, run_id: str) -> dict[str, Any]:
        state = json.loads((self._root(run_id) / "state.json").read_text(encoding="utf-8"))
        state["stop_requested"] = False
        state["status"] = "READY_FOR_VIEWS" if state.get("front_anchor") else "AWAITING_FRONT_ANCHOR"
        state["updated_at"] = self._now()
        self._save_state(run_id, state)
        return self.detail(run_id)

    def retry_candidate(self, run_id: str, candidate_id: str) -> dict[str, Any]:
        run = self.detail(run_id)
        candidate = next((item for item in run["candidates"] if item["candidate_id"] == candidate_id), None)
        if candidate is None:
            raise BodyReferenceExperimentError(f"Unknown candidate: {candidate_id}")
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
        elif candidate["status"] == "COMPLETE":
            if not (candidate.get("luna_status") == "FAILED" or
                    (candidate.get("local_job") or {}).get("status") == "FAILED"):
                raise BodyReferenceExperimentError("This candidate has no failed analysis to retry.")
            self._candidate_update(run_id, candidate_id, {
                "luna_status": "PENDING" if candidate.get("luna_status") == "FAILED" else candidate.get("luna_status"),
                "local_job": {} if (candidate.get("local_job") or {}).get("status") == "FAILED" else candidate.get("local_job"),
            })
        else:
            raise BodyReferenceExperimentError("Only a failed render or analysis can be retried.")
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
            if candidate["status"] != "COMPLETE":
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
            raise BodyReferenceExperimentError(f"Unknown candidate: {candidate_id}")
        image = Path(str(candidate.get("image_path") or ""))
        if not image.is_file():
            raise BodyReferenceExperimentError("A completed candidate image is required for Luna analysis.")
        anchor = next((item for item in run["candidates"] if item["candidate_id"] == run.get("front_anchor")), None)
        images = [image]
        if candidate["view"] != FRONT_VIEW:
            anchor_image = Path(str(anchor.get("image_path") or "")) if anchor else None
            if anchor_image is None or not anchor_image.is_file():
                raise BodyReferenceExperimentError("Select a completed front anchor before reviewing other views.")
            images = [anchor_image, image]
        schema_fd, schema_name = tempfile.mkstemp(prefix="zet_body_reference_schema_", suffix=".json")
        output_fd, output_name = tempfile.mkstemp(prefix="zet_body_reference_luna_", suffix=".json")
        os.close(schema_fd)
        os.close(output_fd)
        schema_file = Path(schema_name)
        output_file = Path(output_name)
        schema_file.write_text(json.dumps(self.analysis_schema()), encoding="utf-8")
        codex_executable = None
        if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
            installs = list((Path(os.environ["LOCALAPPDATA"]) / "OpenAI" / "Codex" / "bin").glob("*/codex.exe"))
            if installs:
                codex_executable = str(max(installs, key=lambda path: path.stat().st_mtime_ns))
        codex_executable = codex_executable or shutil.which("codex")
        if not codex_executable:
            raise BodyReferenceExperimentError("Codex CLI is unavailable for Luna analysis.")
        command = [codex_executable, "-a", "never", "-s", "read-only", "-m", self.app.config.codex_default_model,
                   "-c", 'model_reasoning_effort="high"', "-C", str(self.project_root), "exec",
                   "--ignore-user-config", "--skip-git-repo-check", "--ephemeral", "--output-schema", str(schema_file),
                   "--output-last-message", str(output_file)]
        for path in images:
            command.extend(["--image", str(path)])
        prompt = self.analysis_prompt(candidate, anchor=candidate["view"] != FRONT_VIEW,
                                      facts=self._review_facts(run, candidate["view"]))
        started = time.perf_counter()
        try:
            completed = subprocess.run(command, input=prompt, capture_output=True, text=True, timeout=1800,
                                       check=False, env=self._luna_environment())
            if completed.returncode != 0:
                raise BodyReferenceExperimentError((completed.stderr or completed.stdout or "Luna analysis failed")[-2000:])
            result = json.loads(output_file.read_text(encoding="utf-8"))
            if not isinstance(result, dict):
                raise BodyReferenceExperimentError("Luna analysis output must be a JSON object.")
            hashes = {"candidate": self._hash(image), "front_anchor": self._hash(images[0]) if len(images) == 2 else ""}
            self.record_analysis(run_id, candidate_id, "luna", result, hashes)
            return {"provider": "luna", "status": "COMPLETE", "elapsed_seconds": round(time.perf_counter() - started, 3), "result": result}
        except (OSError, json.JSONDecodeError) as exc:
            raise BodyReferenceExperimentError(f"Luna analysis output was invalid: {exc}") from exc
        finally:
            schema_file.unlink(missing_ok=True)
            output_file.unlink(missing_ok=True)

    def set_lineup(self, run_id: str, method: str, selections: dict[str, str]) -> dict[str, Any]:
        if method not in {METHOD_TEXT_FIRST, METHOD_FRONT_CONDITIONED}:
            raise BodyReferenceExperimentError("Unknown Body-Reference experiment method.")
        run = self.detail(run_id)
        allowed_views = set(run.get("views") or [])
        if set(selections) - allowed_views:
            raise BodyReferenceExperimentError("Lineup contains an unknown view.")
        by_id = {item["candidate_id"]: item for item in run.get("candidates") or []}
        for view, candidate_id in selections.items():
            candidate = by_id.get(str(candidate_id))
            if not candidate or candidate.get("view") != view:
                raise BodyReferenceExperimentError(f"Candidate {candidate_id} does not belong to view {view}.")
            if view != FRONT_VIEW and candidate.get("method") != method:
                raise BodyReferenceExperimentError("Lineup candidate uses the wrong generation method.")
            if candidate.get("disposition") not in {"joint_pass", "human_keep"}:
                raise BodyReferenceExperimentError("Only jointly passed or human-kept candidates can enter a lineup.")
        state = json.loads((self._root(run_id) / "state.json").read_text(encoding="utf-8"))
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
