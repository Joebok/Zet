"""Local, candidate-based Head-Image generation and review."""
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

from PIL import Image

from Scripts.Run_Head_Image_Jobs import compile_head_image_job
from zet.services.candidate_review_contract import ReviewGate, parse_rejection_verdict, validate_ranking
from zet.services.local_asset_store_service import LocalAssetStoreService
from zet.services.local_render_backend_service import LocalRenderBackendService
from zet.services.workflow_storage import file_lock, supersede_task


class LocalHeadImageError(ValueError):
    pass


FRONT = "FRONT"
VIEWS = ("FRONT", "FRONT_LEFT_3_4", "FRONT_RIGHT_3_4", "LEFT_PROFILE", "RIGHT_PROFILE", "BACK_LEFT_3_4", "BACK_RIGHT_3_4", "BACK")
VIEW_LABELS = {
    "FRONT": "direct front view", "FRONT_LEFT_3_4": "front-left three-quarter view",
    "FRONT_RIGHT_3_4": "front-right three-quarter view", "LEFT_PROFILE": "left profile",
    "RIGHT_PROFILE": "right profile", "BACK_LEFT_3_4": "back-left three-quarter view",
    "BACK_RIGHT_3_4": "back-right three-quarter view", "BACK": "direct back view",
}
VIEW_RULES = {
    "FRONT": "The face points squarely toward camera; show both sides of the face evenly.",
    "FRONT_LEFT_3_4": "Turn the whole head toward the character's anatomical left; show more left cheek and ear, with both eyes visible.",
    "FRONT_RIGHT_3_4": "Turn the whole head toward the character's anatomical right; show more right cheek and ear, with both eyes visible.",
    "LEFT_PROFILE": "Show the character's exact anatomical left profile; keep the nose pointing image-left.",
    "RIGHT_PROFILE": "Show the character's exact anatomical right profile; keep the nose pointing image-right.",
    "BACK_LEFT_3_4": "Show the back of the skull and hair with the anatomical left rear side nearer the camera.",
    "BACK_RIGHT_3_4": "Show the back of the skull and hair with the anatomical right rear side nearer the camera.",
    "BACK": "Show the back of the head squarely; do not reveal the face.",
}


class LocalHeadImageService:
    """Manage one local Head-Image workspace per character and phase."""

    _active: set[str] = set()
    _active_lock = threading.Lock()
    _runner_lock = threading.Lock()

    GATES = {
        "background": "Is the background similar in color or tone to the hair or skin of the subject? Return TRUE when the background similar in color or tone to the hair or skin of the subject. A genuinely transparent background passes. Return FALSE otherwise.",
        "framing": "Does the image show the complete head and hairstyle silhouette without material cropping, distortion, or extra subjects? Return TRUE only for a clear defect; otherwise return FALSE.",
        "orientation": "Does the visible head match the requested view: {view}. {view_rule} Return TRUE only for a clear wrong view or mirrored anatomy; otherwise return FALSE.",
        "identity": "Compare Image 1, the selected FRONT anchor, with Image 2, the candidate. Could both images plausibly depict the same character's head, face, hair, and species traits from different angles? Return TRUE only for a clear identity mismatch; otherwise return FALSE.",
        "source_identity": "Compare the supplied reference image with the generated FRONT candidate. Is there a clear character identity mismatch? Return TRUE only for a clear mismatch; otherwise return FALSE.",
    }

    def __init__(self, app: Any, project_root: str | Path):
        self.app = app
        self.project_root = Path(project_root).resolve()
        self.library_root = Path(app.config.base_library_path).resolve()
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
            raise LocalHeadImageError("Character and phase are required.")
        return token

    def _workspace(self, character: str, phase: str) -> Path:
        return self.root / self._safe(character) / self._safe(phase) / "Head-Image"

    def _run_root(self, run_id: str) -> Path:
        if not re.fullmatch(r"\d{8}_\d{6}_\d{6}", str(run_id or "")):
            raise LocalHeadImageError("Invalid Local Head-Image batch ID.")
        for path in self.root.glob(f"*/ */Head-Image/{run_id}".replace(" ", "")):
            if (path / "spec.json").is_file():
                return path
        for path in self.root.glob(f"*/ */Head-Image/{run_id}".replace(" ", "")):
            if (path / "spec.json").is_file():
                return path
        for path in self.root.glob(f"*/*/Head-Image/{run_id}"):
            if (path / "spec.json").is_file():
                return path
        raise LocalHeadImageError(f"Local Head-Image batch not found: {run_id}")

    def preview(self, payload: dict[str, Any]) -> dict[str, Any]:
        character, phase = str(payload.get("character") or "").strip(), str(payload.get("phase") or "").strip()
        if not character or not phase:
            raise LocalHeadImageError("Character and phase are required.")
        front_count, other_count = int(payload.get("front_count") or 8), int(payload.get("other_count") or 4)
        if front_count < 1 or other_count < 1 or front_count + 7 * other_count > 256:
            raise LocalHeadImageError("Candidate counts must be positive and the run cannot exceed 256 candidates.")
        return {"character": character, "phase": phase, "views": list(VIEWS), "front_count": front_count,
                "other_count": other_count, "candidate_count": front_count + 7 * other_count,
                "front_source_optional": True, "front_anchor_required_for_other_views": True}

    def upload_source(self, character: str, phase: str, filename: str, contents: bytes) -> dict[str, str]:
        if not contents or len(contents) > 32 * 1024 * 1024:
            raise LocalHeadImageError("Choose an image under 32 MB.")
        suffix = Path(filename or "reference.png").suffix.lower()
        if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
            raise LocalHeadImageError("Supported image types are PNG, JPEG, and WebP.")
        try:
            import io
            with Image.open(io.BytesIO(contents)) as image:
                image.verify()
        except Exception as exc:
            raise LocalHeadImageError("The uploaded reference is not a readable image.") from exc
        target_dir = self._workspace(character, phase) / "inputs"
        target_dir.mkdir(parents=True, exist_ok=True)
        safe_name = self._safe(Path(filename or "reference.png").stem) + suffix
        target = target_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{safe_name}"
        target.write_bytes(contents)
        return {"path": str(target), "name": target.name}

    def _compile(self, run_root: Path, character: str, phase: str, view: str, references: list[dict]) -> dict[str, Any]:
        output_dir = run_root / "prompts" / view
        template_path = Path(self.app.config.base_character_path) / character / phase / "Character.md"
        job = {"Job": f"LocalHeadImage_{run_root.name}_{view}", "Task": "head-image", "Character": character,
               "Phase": phase, "Head View": view, "Template Path": str(template_path),
               "Output Directory": str(output_dir), "Reference Files": references}
        try:
            return compile_head_image_job(job, self.project_root, pipeline_mode="local")
        except Exception as exc:
            raise LocalHeadImageError(f"Could not compile the local {view} prompt: {exc}") from exc

    def create_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        plan = self.preview(payload)
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        root = self._workspace(plan["character"], plan["phase"]) / run_id
        root.mkdir(parents=True, exist_ok=False)
        source_path = str(payload.get("front_source_path") or "").strip()
        source_snapshot = ""
        if source_path:
            source = Path(source_path).resolve()
            if not source.is_file():
                raise LocalHeadImageError(f"Front reference image not found: {source}")
            destination = root / "inputs" / ("front_source" + source.suffix.lower())
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            source_snapshot = str(destination)
        seeds = payload.get("seeds")
        total = int(plan["candidate_count"])
        if not isinstance(seeds, list):
            rng = random.SystemRandom()
            seeds = [rng.randrange(0, 2**63 - 1) for _ in range(total)]
        if len(seeds) != total:
            raise LocalHeadImageError("Explicit seed count must match the candidate plan.")
        try:
            seeds = [str(int(item)) for item in seeds]
        except (TypeError, ValueError) as exc:
            raise LocalHeadImageError("Every seed must be an integer.") from exc
        candidates = []
        index = 0
        for view in VIEWS:
            count = plan["front_count"] if view == FRONT else plan["other_count"]
            for ordinal in range(1, count + 1):
                index += 1
                candidates.append({"candidate_id": f"c{index:03d}", "view": view, "ordinal": ordinal,
                                   "seed": seeds[index - 1], "status": "PENDING", "image_path": "",
                                   "gates": {}, "human_review": {"decision": "undecided", "notes": ""},
                                   "retry_count": 0})
        front_prompt = self._compile(root, plan["character"], plan["phase"], FRONT,
                                     ([{"role": "head_image_source", "path": source_snapshot}] if source_snapshot else []))
        spec = {"schema_version": 1, "review_version": 2, "kind": "local_head_image", "run_id": run_id,
                "created_at": self._now(), "status": "RUNNING", "character": plan["character"], "phase": plan["phase"],
                "views": list(VIEWS), "front_count": plan["front_count"], "other_count": plan["other_count"],
                "candidate_count": total, "front_source": source_snapshot,
                "front_source_sha256": self._hash(Path(source_snapshot)) if source_snapshot else "",
                "front_prompt_path": front_prompt["final_prompt"], "front_prompt_sha256": self._hash(Path(front_prompt["final_prompt"])),
                "candidates": candidates, "front_anchor": None, "selected_views": {}, "rankings": {}, "created_by": "zet"}
        self._write(root / "spec.json", spec)
        self._write(root / "state.json", {"run_id": run_id, "status": "QUEUED", "updated_at": self._now(),
                                            "stop_requested": False, "candidates": {}, "selected_views": {}, "rankings": {}})
        return self.detail(run_id)

    @staticmethod
    def _write(path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        temporary.replace(path)

    def detail(self, run_id: str) -> dict[str, Any]:
        root = self._run_root(run_id)
        spec = json.loads((root / "spec.json").read_text(encoding="utf-8"))
        state = json.loads((root / "state.json").read_text(encoding="utf-8"))
        candidates = {item["candidate_id"]: dict(item) for item in spec.get("candidates", [])}
        for candidate_id, update in (state.get("candidates") or {}).items():
            if candidate_id in candidates:
                candidates[candidate_id].update(update)
        value = {**spec, **state, "candidates": list(candidates.values()), "root": str(root),
                 "stop_requested": bool(state.get("stop_requested"))}
        active = state.get("status") in {"RUNNING", "STOPPING", "REEVALUATING"}
        if active:
            with self._active_lock:
                value["interrupted"] = run_id not in self._active
                if value["interrupted"]:
                    value["status"] = "INTERRUPTED"
        else:
            value["interrupted"] = False
        value["selected_views"] = state.get("selected_views") or {}
        value["rankings"] = state.get("rankings") or {}
        value["front_anchor"] = state.get("front_anchor") or spec.get("front_anchor")
        value["local_assets"] = self.asset_store.detail(value["character"], value["phase"]).get("assets", {})
        stale = []
        anchor = next((c for c in value["candidates"] if c["candidate_id"] == value.get("front_anchor")), None)
        anchor_path = Path(str((anchor or {}).get("image_path") or ""))
        anchor_hash = self._hash(anchor_path) if anchor_path.is_file() else ""
        for view, ranking in value["rankings"].items():
            if view == FRONT:
                continue
            if ranking.get("status") in {"COMPLETE", "STALE"} and ranking.get("anchor_hash") != anchor_hash:
                ranking.update(status="STALE", stale_reason="The selected FRONT anchor changed.")
                stale.append(view)
        for candidate in value["candidates"]:
            if candidate.get("view") == FRONT:
                continue
            gate = (candidate.get("gates") or {}).get("identity") or {}
            if gate and gate.get("input_hashes", {}).get("front_anchor") != anchor_hash:
                gate["status"] = "STALE"
                candidate.setdefault("stale_gates", []).append("identity")
                if candidate["view"] not in stale:
                    stale.append(candidate["view"])
        value["stale_views"] = sorted(set(stale))
        value["stale_selections"] = stale
        return value

    def front_source_path(self, run_id: str) -> Path:
        root = self._run_root(run_id).resolve()
        spec = json.loads((root / "spec.json").read_text(encoding="utf-8"))
        source = Path(str(spec.get("front_source") or "")).resolve()
        if not source.is_file() or not source.is_relative_to(root):
            raise LocalHeadImageError(f"Front reference image not found for batch: {run_id}")
        return source

    def list_runs(self, character: str = "", phase: str = "") -> list[dict[str, Any]]:
        result = []
        for path in self.root.glob("*/*/Head-Image/*/spec.json"):
            try:
                spec = json.loads(path.read_text(encoding="utf-8"))
                if spec.get("kind") != "local_head_image":
                    continue
                if character and spec.get("character") != character or phase and spec.get("phase") != phase:
                    continue
                run = self.detail(str(spec["run_id"]))
                result.append({"run_id": run["run_id"], "character": run["character"], "phase": run["phase"],
                               "created_at": run["created_at"], "status": run["status"],
                               "candidate_count": run["candidate_count"],
                               "complete_count": sum(1 for item in run["candidates"] if item.get("image_path")),
                               "front_anchor": run.get("front_anchor")})
            except (OSError, ValueError, KeyError, json.JSONDecodeError):
                continue
        return sorted(result, key=lambda item: item["run_id"], reverse=True)

    def _state(self, run_id: str) -> tuple[Path, dict[str, Any]]:
        root = self._run_root(run_id)
        return root, json.loads((root / "state.json").read_text(encoding="utf-8"))

    def _update(self, run_id: str, candidate_id: str, **changes: Any) -> None:
        root, state = self._state(run_id)
        state.setdefault("candidates", {}).setdefault(candidate_id, {}).update(changes)
        state["updated_at"] = self._now()
        self._write(root / "state.json", state)

    def _run_update(self, run_id: str, **changes: Any) -> None:
        root, state = self._state(run_id)
        state.update(changes, updated_at=self._now())
        self._write(root / "state.json", state)

    def queue_render_candidate(self, run_id: str, candidate_id: str) -> dict[str, Any]:
        run = self.detail(run_id)
        candidate = next((item for item in run["candidates"] if item["candidate_id"] == candidate_id), None)
        if not candidate:
            raise LocalHeadImageError(f"Unknown candidate: {candidate_id}")
        if candidate["view"] != FRONT and not run.get("front_anchor"):
            raise LocalHeadImageError("Select a FRONT anchor before generating other views.")
        if candidate.get("status") in {"QUEUED", "RUNNING"}:
            return candidate
        root = Path(run["root"])
        references = []
        if candidate["view"] == FRONT:
            source = str(run.get("front_source") or "")
            if source:
                references = [{"role": "head_image_source", "label": "Uploaded front reference", "path": source}]
        else:
            anchor = next((item for item in run["candidates"] if item["candidate_id"] == run["front_anchor"]), None)
            anchor_path = Path(str((anchor or {}).get("image_path") or ""))
            if not anchor_path.is_file():
                raise LocalHeadImageError("Selected FRONT anchor image is missing.")
            references = [{"role": "head_image_source", "label": "Selected local FRONT anchor", "path": str(anchor_path)}]
        compiled = self._compile(root, run["character"], run["phase"], candidate["view"], references)
        prompt_path = Path(compiled["final_prompt"])
        candidate_dir = root / "renders" / candidate_id
        candidate_dir.mkdir(parents=True, exist_ok=True)
        output_name = f"HeadImage_{candidate_id}_{int(candidate.get('retry_count') or 0)}.png"
        render_dir = candidate_dir / "Local_Test_Renders"
        output_path = render_dir / output_name
        prompt_copy = candidate_dir / "Qwen_Head_Image_Prompt.md"
        prompt_copy.write_text("Positive Prompt:\n" + prompt_path.read_text(encoding="utf-8") + "\n\nNegative Prompt:\n", encoding="utf-8")
        preset_name = "comfyui-qwen-head-image-edit" if references else "comfyui-qwen-head-image-text"
        profile = LocalRenderBackendService(self.project_root / "Config" / "Local_Render_Presets.json").preset(preset_name)
        ask_id = f"LocalHeadImage_{run_id}_{candidate_id}_{int(candidate.get('retry_count') or 0)}"
        manifest = {"ask_id": ask_id, "character": run["character"], "phase": run["phase"],
                    "pipeline": "Local-Head-Image", "pipeline_stage": "HEAD_IMAGE_RENDER"}
        ask_path = self.app.ai_proxy_service.stage_render_task_local_render_ask(
            manifest, prompt_copy, candidate_dir, allow_parallel=True, seed=int(candidate["seed"]),
            checkpoint=str(profile.get("diffusion_model") or ""), render_preset=preset_name,
            image_generation="comfyui", reference_files=references,
        )
        ask = json.loads((ask_path / "ask_manifest.json").read_text(encoding="utf-8"))
        reference_images = [{"role": str(reference.get("role") or ""),
                             "path": str(reference.get("path") or ""),
                             "sha256": self._hash(Path(reference["path"]))}
                            for reference in references]
        self._update(run_id, candidate_id, status="QUEUED", ask_id=ask["ask_id"], image_path=str(output_path),
                     prompt_path=str(prompt_path), prompt_sha256=self._hash(prompt_path),
                     source_image_hash=self._hash(Path(references[0]["path"])) if references else "",
                     reference_images=reference_images,
                     input_hashes={item["role"]: item["sha256"] for item in reference_images},
                     workflow_kind=str(ask.get("workflow_kind") or profile.get("workflow_kind") or ""),
                     render_preset=preset_name, queued_at=self._now())
        return self.detail(run_id)

    def _proxy_answer(self, ask_id: str) -> tuple[str, dict[str, Any]]:
        paths = self.app.ai_proxy_service.ai_proxy_path_service
        for status, folder in (("QUEUED", paths.ask_root()), ("RUNNING", paths.running_root()), ("ANSWERED", paths.answer_root())):
            path = folder / ask_id
            if path.is_dir():
                try:
                    return status, json.loads((path / "answer_manifest.json").read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    return status, {}
        return "UNKNOWN", {}

    def _harvest(self, run_id: str, candidate: dict[str, Any]) -> None:
        paths = self.app.ai_proxy_service.ai_proxy_path_service
        ask_id = str(candidate.get("ask_id") or "")
        answer_dir = paths.answer_root() / ask_id
        if not answer_dir.is_dir() or not (answer_dir / "answer_manifest.json").is_file():
            return
        ask = json.loads((answer_dir / "ask_manifest.json").read_text(encoding="utf-8"))
        answer = json.loads((answer_dir / "answer_manifest.json").read_text(encoding="utf-8"))
        if ask.get("ask_id") != ask_id or answer.get("ask_id") != ask_id or ask.get("pipeline") != "Local-Head-Image":
            raise LocalHeadImageError("AI Proxy answer does not belong to this Local Head-Image candidate.")
        if answer.get("status") in {"ERROR", "RETRY_LATER"}:
            raise LocalHeadImageError(str(answer.get("error_message") or "AI Proxy render failed."))
        if answer.get("status") != "SUCCESS" or Path(str(answer.get("expected_output") or "")).name != answer.get("expected_output"):
            return
        source = answer_dir / str(answer["expected_output"])
        target = Path(str(candidate.get("image_path") or ""))
        if not source.is_file() or not target.resolve().is_relative_to(self._run_root(run_id).resolve()):
            raise LocalHeadImageError("AI Proxy returned an invalid candidate image.")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    def _wait_render(self, run_id: str, candidate_id: str) -> bool:
        candidate = next(item for item in self.detail(run_id)["candidates"] if item["candidate_id"] == candidate_id)
        target = Path(str(candidate.get("image_path") or ""))
        deadline = time.monotonic() + 1860
        while not target.is_file():
            run = self.detail(run_id)
            if run.get("stop_requested"):
                return False
            self._harvest(run_id, candidate)
            if target.is_file():
                break
            _, answer = self._proxy_answer(str(candidate.get("ask_id") or ""))
            if answer.get("status") in {"ERROR", "RETRY_LATER"}:
                raise LocalHeadImageError(str(answer.get("error_message") or "ComfyUI render failed."))
            if time.monotonic() >= deadline:
                raise LocalHeadImageError("Timed out waiting for the ComfyUI render.")
            time.sleep(max(.5, float(self.app.config.comfyui_poll_seconds)))
        self._update(run_id, candidate_id, status="WAITING_FOR_GATES", image_sha256=self._hash(target), rendered_at=self._now())
        return True

    @classmethod
    def review_gates(cls, view: str, *, has_front_source: bool = False) -> list[ReviewGate]:
        gates = [ReviewGate("background", cls.GATES["background"]),
                 ReviewGate("framing", cls.GATES["framing"]),
                 ReviewGate("orientation", cls.GATES["orientation"].format(view=VIEW_LABELS.get(view, view), view_rule=VIEW_RULES.get(view, "")))]
        if view == FRONT and has_front_source:
            gates.append(ReviewGate("source_identity", cls.GATES["source_identity"]))
        elif view != FRONT:
            gates.append(ReviewGate("identity", cls.GATES["identity"], uses_anchor=True))
        return gates

    def _queue_gate(self, run_id: str, candidate: dict[str, Any], definition: ReviewGate) -> dict[str, Any]:
        run = self.detail(run_id)
        root = self._run_root(run_id)
        image = Path(str(candidate.get("image_path") or ""))
        if not image.is_file():
            raise LocalHeadImageError("Candidate image is missing.")
        view = candidate["view"]
        input_images = [("candidate.png", image)]
        hashes = {"candidate": self._hash(image), "front_anchor": ""}
        if definition.uses_anchor:
            anchor = next((item for item in run["candidates"] if item["candidate_id"] == run["front_anchor"]), None)
            anchor_path = Path(str((anchor or {}).get("image_path") or ""))
            if not anchor_path.is_file():
                raise LocalHeadImageError("Selected FRONT anchor image is missing.")
            input_images.insert(0, ("front_anchor.png", anchor_path))
            hashes["front_anchor"] = self._hash(anchor_path)
        if definition.key == "source_identity":
            input_images.insert(0, ("front_source.png", Path(run["front_source"])))
            hashes["front_source"] = run.get("front_source_sha256", "")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        output = root / "analyses" / candidate["candidate_id"] / f"gate_{definition.key}_{timestamp}.txt"
        ask_id = f"Ask_LocalHeadImage_{run_id}_{candidate['candidate_id']}_{definition.key}_{timestamp}"
        proxy = self.app.ai_proxy_service.ai_proxy_path_service.file_proxy_client
        staging = proxy.create_staging(ask_id)
        for name, path in input_images:
            shutil.copy2(path, staging / name)
        (staging / "OLLAMA_PROMPT.md").write_text(definition.prompt, encoding="utf-8")
        manifest = {"version": 1, "ask_id": ask_id, "character": run["character"], "phase": run["phase"],
                    "pipeline": "Local-Head-Image", "pipeline_stage": f"HEAD_IMAGE_{definition.key.upper()}_GATE",
                    "worker_type": "ollama_generate", "ollama_model": str(getattr(self.app.config, "local_body_reference_face_gate_model", "image-analysis-alt:latest")),
                    "ollama_think": False, "prompt_file": "OLLAMA_PROMPT.md", "image_files": [name for name, _ in input_images],
                    "json_output": False, "expected_output": output.name, "task_type": "local_head_image_gate",
                    "auxiliary": True, "target_output_dir": str(output.parent), "target_output_file": output.name,
                    "local_head_image_run_id": run_id, "candidate_id": candidate["candidate_id"],
                    "gate": definition.key, "input_hashes": hashes,
                    "prompt_sha256": hashlib.sha256(definition.prompt.encode()).hexdigest()}
        (staging / "ask_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        proxy.publish(staging, ask_id, "ollama_generate")
        return {"status": "QUEUED", "ask_id": ask_id, "output_path": str(output), "input_hashes": hashes,
                "prompt_sha256": manifest["prompt_sha256"]}

    def _harvest_gate(self, run_id: str, candidate_id: str, record: dict[str, Any]) -> None:
        ask_id = str(record.get("ask_id") or "")
        paths = self.app.ai_proxy_service.ai_proxy_path_service
        folder = paths.answer_root() / ask_id
        if not folder.is_dir() or not (folder / "answer_manifest.json").is_file():
            return
        ask = json.loads((folder / "ask_manifest.json").read_text(encoding="utf-8"))
        answer = json.loads((folder / "answer_manifest.json").read_text(encoding="utf-8"))
        if (ask.get("ask_id") != ask_id or ask.get("local_head_image_run_id") != run_id
                or ask.get("candidate_id") != candidate_id or ask.get("task_type") != "local_head_image_gate"):
            raise LocalHeadImageError("AI Proxy gate answer does not match its Local Head-Image candidate.")
        if answer.get("status") in {"ERROR", "RETRY_LATER"}:
            raise LocalHeadImageError(str(answer.get("error_message") or "Head gate failed."))
        if answer.get("status") != "SUCCESS":
            return
        filename = str(ask.get("target_output_file") or "")
        expected = self._run_root(run_id) / "analyses" / candidate_id / filename
        target = Path(str(record.get("output_path") or ""))
        source = folder / str(answer.get("expected_output") or "")
        if (expected.resolve() != target.resolve() or not target.resolve().is_relative_to(self._run_root(run_id).resolve())
                or not source.is_file() or Path(str(answer.get("expected_output") or "")).name != answer.get("expected_output")):
            raise LocalHeadImageError("AI Proxy gate output path is invalid.")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    def _wait_gate(self, run_id: str, candidate_id: str, gate_key: str) -> tuple[str, str]:
        candidate = next(item for item in self.detail(run_id)["candidates"] if item["candidate_id"] == candidate_id)
        record = dict((candidate.get("gates") or {}).get(gate_key) or {})
        output = Path(str(record.get("output_path") or ""))
        deadline = time.monotonic() + 1800
        while not output.is_file():
            if self.detail(run_id).get("stop_requested"):
                raise LocalHeadImageError("Review stopped by user.")
            self._harvest_gate(run_id, candidate_id, record)
            if output.is_file():
                break
            _, answer = self._proxy_answer(str(record.get("ask_id") or ""))
            if answer.get("status") in {"ERROR", "RETRY_LATER"}:
                raise LocalHeadImageError(str(answer.get("error_message") or f"{gate_key} gate failed."))
            if time.monotonic() >= deadline:
                raise LocalHeadImageError(f"Timed out waiting for the {gate_key} gate.")
            time.sleep(1)
        response = output.read_text(encoding="utf-8").strip()
        match = re.fullmatch(r"(TRUE|FALSE)(?::\s*(.*))?", response, re.IGNORECASE)
        if not match:
            raise LocalHeadImageError(f"{gate_key} gate returned an invalid verdict.")
        return match.group(1).upper(), (match.group(2) or "").strip()

    def run_candidate_gates(self, run_id: str, candidate_id: str) -> bool:
        run = self.detail(run_id)
        candidate = next(item for item in run["candidates"] if item["candidate_id"] == candidate_id)
        image = Path(str(candidate.get("image_path") or ""))
        if not image.is_file():
            raise LocalHeadImageError("Candidate image is missing.")
        gates = dict(candidate.get("gates") or {})
        definitions = self.review_gates(candidate["view"], has_front_source=bool(run.get("front_source")))
        for definition in definitions:
            current = dict(gates.get(definition.key) or {})
            anchor = next((item for item in run["candidates"] if item["candidate_id"] == run.get("front_anchor")), None)
            hashes = {"candidate": self._hash(image), "front_anchor": ""}
            if definition.uses_anchor:
                anchor_path = Path(str((anchor or {}).get("image_path") or ""))
                hashes["front_anchor"] = self._hash(anchor_path) if anchor_path.is_file() else ""
            if definition.key == "source_identity":
                hashes["front_source"] = run.get("front_source_sha256", "")
            prompt_hash = hashlib.sha256(definition.prompt.encode()).hexdigest()
            if (current.get("status") == "COMPLETE" and current.get("input_hashes") == hashes
                    and current.get("prompt_sha256") == prompt_hash):
                verdict, reason = current["verdict"], current.get("reason", "")
            else:
                try:
                    current = self._queue_gate(run_id, candidate, definition)
                    gates[definition.key] = current
                    self._update(run_id, candidate_id, status="WAITING_FOR_GATES", gates=gates)
                    verdict, reason = self._wait_gate(run_id, candidate_id, definition.key)
                    current.update(status="COMPLETE", verdict=verdict, reason=reason, completed_at=self._now())
                    gates[definition.key] = current
                    self._update(run_id, candidate_id, gates=gates)
                except Exception as exc:
                    current.update(status="FAILED", error=str(exc))
                    gates[definition.key] = current
                    self._update(run_id, candidate_id, status="FAILED", failed_gate=definition.key, gates=gates)
                    return False
            if verdict == "TRUE":
                self._update(run_id, candidate_id, status="GATE_REJECTED", rejection_gate=definition.key,
                             gates=gates, completed_at=self._now())
                return True
        self._update(run_id, candidate_id, status="WAITING_FOR_HUMAN_REVIEW", gates=gates,
                     image_sha256=self._hash(image))
        return True

    def execute_run(self, run_id: str, *, views: set[str] | None = None, candidate_ids: set[str] | None = None) -> None:
        root = self._run_root(run_id)
        try:
            with file_lock(root / "runner.lock", timeout=0):
                with self._active_lock:
                    self._active.add(run_id)
                run = self.detail(run_id)
                if views is None:
                    views = {FRONT} if not run.get("front_anchor") else {view for view in VIEWS if view != FRONT}
                self._run_update(run_id, status="RUNNING", error="")
                selected_views = [view for view in VIEWS if view in views]
                for view in selected_views:
                    view_candidates = [item for item in self.detail(run_id)["candidates"]
                                       if item["view"] == view
                                       and (candidate_ids is None or item["candidate_id"] in candidate_ids)
                                       and item.get("status") in {"PENDING", "FAILED", "QUEUED", "RUNNING", "WAITING_FOR_GATES"}]

                    # Queue the whole view first so ComfyUI can render its candidates
                    # as a batch before any candidate is sent through review gates.
                    for candidate in view_candidates:
                        if self.detail(run_id).get("stop_requested"):
                            break
                        candidate_id = candidate["candidate_id"]
                        current = next(item for item in self.detail(run_id)["candidates"]
                                       if item["candidate_id"] == candidate_id)
                        if Path(str(current.get("image_path") or "")).is_file():
                            continue
                        try:
                            self.queue_render_candidate(run_id, candidate_id)
                            self._update(run_id, candidate_id, status="RUNNING")
                        except Exception as exc:
                            self._update(run_id, candidate_id, status="FAILED", render_error=str(exc))

                    if self.detail(run_id).get("stop_requested"):
                        break

                    # Wait until every queued render for this view has finished (or
                    # failed) before starting any gates for the view.
                    for candidate in view_candidates:
                        if self.detail(run_id).get("stop_requested"):
                            break
                        candidate_id = candidate["candidate_id"]
                        current = next(item for item in self.detail(run_id)["candidates"]
                                       if item["candidate_id"] == candidate_id)
                        if Path(str(current.get("image_path") or "")).is_file():
                            continue
                        if current.get("status") not in {"QUEUED", "RUNNING"}:
                            continue
                        try:
                            if not self._wait_render(run_id, candidate_id):
                                break
                        except Exception as exc:
                            self._update(run_id, candidate_id, status="FAILED", render_error=str(exc))

                    if self.detail(run_id).get("stop_requested"):
                        break

                    # Gate every rendered candidate, then rank the view's survivors.
                    for candidate in view_candidates:
                        if self.detail(run_id).get("stop_requested"):
                            break
                        candidate_id = candidate["candidate_id"]
                        current = next(item for item in self.detail(run_id)["candidates"]
                                       if item["candidate_id"] == candidate_id)
                        if (current.get("status") not in {"PENDING", "FAILED", "QUEUED", "RUNNING", "WAITING_FOR_GATES",
                                                          "WAITING_FOR_HUMAN_REVIEW", "COMPLETE"}
                                or not Path(str(current.get("image_path") or "")).is_file()):
                            continue
                        try:
                            self.run_candidate_gates(run_id, candidate_id)
                        except Exception as exc:
                            self._update(run_id, candidate_id, status="FAILED", render_error=str(exc))

                    if self.detail(run_id).get("stop_requested"):
                        break
                    self.rank_view(run_id, view)
                latest = self.detail(run_id)
                waiting_anchor = not latest.get("front_anchor")
                pending = any(item["status"] in {"PENDING", "FAILED", "QUEUED", "RUNNING", "WAITING_FOR_GATES"}
                              for item in latest["candidates"])
                self._run_update(run_id, status=("STOPPED" if latest.get("stop_requested") else
                                                  "AWAITING_FRONT_ANCHOR" if waiting_anchor else
                                                  "AWAITING_HUMAN_SELECTION" if pending else "COMPLETE"))
        except TimeoutError:
            return
        except Exception as exc:
            self._run_update(run_id, status="ERROR", error=str(exc))
        finally:
            with self._active_lock:
                self._active.discard(run_id)

    def gate_prompt(self, run_id: str, view: str, gate: str) -> str:
        if view not in VIEWS:
            raise LocalHeadImageError(f"Unknown view: {view}")
        if gate == "background":
            return self.GATES[gate]
        if gate == "framing":
            return self.GATES[gate]
        if gate == "orientation":
            return self.GATES[gate].format(view=VIEW_LABELS[view], view_rule=VIEW_RULES[view])
        if gate == "identity":
            return self.GATES[gate]
        if gate == "source_identity":
            return self.GATES[gate]
        raise LocalHeadImageError(f"Unknown gate: {gate}")

    def review_prompt(self, run_id: str, view: str) -> str:
        run = self.detail(run_id)
        view = str(view or "").upper()
        if view not in VIEWS:
            raise LocalHeadImageError(f"Unknown view: {view}")
        candidate = next((item for item in run["candidates"] if item["view"] == view and item.get("prompt_path")), None)
        path = Path(str((candidate or {}).get("prompt_path") or (run.get("front_prompt_path") if view == FRONT else "")))
        if not path.is_file():
            references = []
            if view == FRONT and run.get("front_source"):
                references = [{"role": "head_image_source", "path": run["front_source"]}]
            elif view != FRONT:
                anchor = next((item for item in run["candidates"] if item["candidate_id"] == run.get("front_anchor")), None)
                anchor_path = Path(str((anchor or {}).get("image_path") or ""))
                if not anchor_path.is_file():
                    raise LocalHeadImageError("Select a FRONT anchor before viewing this view's prompt.")
                references = [{"role": "head_image_source", "label": "Selected local FRONT anchor", "path": str(anchor_path)}]
            compiled = self._compile(Path(run["root"]), run["character"], run["phase"], view, references)
            path = Path(compiled["final_prompt"])
        return path.read_text(encoding="utf-8")

    def image_prompt(self, run_id: str, view: str) -> str:
        """Return the image-generation prompt saved for a view."""
        return self.review_prompt(run_id, view)

    def review_specification(self, run_id: str, view: str) -> str:
        run = self.detail(run_id)
        view = str(view or "").upper()
        if view not in VIEWS:
            raise LocalHeadImageError(f"Unknown view: {view}")
        sections = [
            f"Local Head-Image review specification — {view}",
            "Background gate:\n" + self.gate_prompt(run_id, view, "background"),
            "Framing gate:\n" + self.gate_prompt(run_id, view, "framing"),
            "Orientation gate:\n" + self.gate_prompt(run_id, view, "orientation"),
        ]
        if view == FRONT and run.get("front_source"):
            sections.append("Source identity gate:\n" + self.gate_prompt(run_id, view, "source_identity"))
        elif view != FRONT:
            sections.append("Identity gate:\n" + self.gate_prompt(run_id, view, "identity"))
        return "\n\n".join(sections)

    def queue_view_ranking(self, run_id: str, view: str) -> dict[str, Any]:
        run = self.detail(run_id)
        view = str(view or "").upper()
        if view not in VIEWS:
            raise LocalHeadImageError(f"Unknown view: {view}")
        self.asset_store.assert_change_allowed(run["character"], run["phase"], "Head-Image", view)
        root, state = self._state(run_id)
        state.setdefault("rankings", {})[view] = {"status": "QUEUED", "queued_at": self._now()}
        self._write(root / "state.json", state)
        return self.detail(run_id)

    def rank_view(self, run_id: str, view: str) -> dict[str, Any]:
        try:
            return self._rank_view(run_id, view)
        except Exception as exc:
            root, state = self._state(run_id)
            state.setdefault("rankings", {})[str(view or "").upper()] = {
                "status": "FAILED", "error": str(exc), "recorded_at": self._now(),
            }
            self._write(root / "state.json", state)
            return self.detail(run_id)

    def _rank_view(self, run_id: str, view: str) -> dict[str, Any]:
        run = self.detail(run_id)
        if view not in VIEWS:
            raise LocalHeadImageError(f"Unknown view: {view}")
        self.asset_store.assert_change_allowed(run["character"], run["phase"], "Head-Image", view)
        anchor = next((item for item in run["candidates"] if item["candidate_id"] == run.get("front_anchor")), None)
        anchor_path = Path(str((anchor or {}).get("image_path") or ""))
        if view != FRONT and not anchor_path.is_file():
            raise LocalHeadImageError("Select a FRONT anchor before ranking other views.")
        survivors = [item for item in run["candidates"] if item["view"] == view
                     and item.get("status") in {"WAITING_FOR_HUMAN_REVIEW", "COMPLETE"}
                     and not item.get("rejection_gate") and item.get("human_review", {}).get("decision") != "reject"
                     and Path(str(item.get("image_path") or "")).is_file()]
        if not survivors:
            raise LocalHeadImageError("No gate-surviving candidates are available to rank.")
        hashes = {item["candidate_id"]: self._hash(Path(item["image_path"])) for item in survivors}
        anchor_hash = self._hash(anchor_path) if view != FRONT else ""
        for candidate in survivors:
            expected = {"candidate": hashes[candidate["candidate_id"]], "front_anchor": ""}
            definitions = self.review_gates(candidate["view"], has_front_source=bool(run.get("front_source")))
            for definition in definitions:
                if definition.uses_anchor:
                    expected["front_anchor"] = anchor_hash
                if definition.key == "source_identity":
                    expected["front_source"] = run.get("front_source_sha256", "")
                gate = (candidate.get("gates") or {}).get(definition.key) or {}
                if gate.get("status") != "COMPLETE" or gate.get("verdict") != "FALSE" or gate.get("input_hashes") != expected:
                    raise LocalHeadImageError(f"{candidate['candidate_id']} has missing or stale {definition.key} gates; re-evaluate this view.")
        if len(survivors) == 1:
            entries = [{"candidate_id": survivors[0]["candidate_id"], "reason": "Only candidate survived the gates."}]
            model = "deterministic-single-survivor"
        else:
            schema = {"type": "object", "properties": {"ranking": {"type": "array", "items": {
                "type": "object", "properties": {"candidate_id": {"type": "string"}, "reason": {"type": "string"}},
                "required": ["candidate_id", "reason"], "additionalProperties": False}}}, "required": ["ranking"], "additionalProperties": False}
            schema_fd, schema_name = tempfile.mkstemp(prefix="zet_local_head_rank_schema_", suffix=".json")
            output_fd, output_name = tempfile.mkstemp(prefix="zet_local_head_rank_", suffix=".json")
            os.close(schema_fd)
            os.close(output_fd)
            schema_file, output_file = Path(schema_name), Path(output_name)
            schema_file.write_text(json.dumps(schema), encoding="utf-8")
            prompt = (f"Rank these head-image candidates for {view}. Compare orientation, clear identity, complete head and hair silhouette, "
                      "character details, and usefulness as a reference. All supplied candidates passed narrow rejection gates. "
                      "Return each candidate once with a concise reason. Candidate IDs: "
                      + ", ".join(item["candidate_id"] for item in survivors))
            executable = shutil.which("codex")
            if not executable and os.name == "nt" and os.environ.get("LOCALAPPDATA"):
                installs = list((Path(os.environ["LOCALAPPDATA"]) / "OpenAI" / "Codex" / "bin").glob("*/codex.exe"))
                if installs:
                    executable = str(max(installs, key=lambda p: p.stat().st_mtime_ns))
            if not executable:
                raise LocalHeadImageError("Codex CLI is unavailable for Luna ranking.")
            command = [executable, "-a", "never", "-s", "read-only", "-m",
                       str(getattr(self.app.config, "codex_default_model", "gpt-6-luna")), "-C", str(self.project_root),
                       "exec", "--ignore-user-config", "--skip-git-repo-check", "--ephemeral", "--output-schema",
                       str(schema_file), "--output-last-message", str(output_file)]
            if view != FRONT:
                command.extend(["--image", str(anchor_path)])
            for item in survivors:
                command.extend(["--image", str(item["image_path"])])
            try:
                result = subprocess.run(command, input=prompt, capture_output=True, text=True, timeout=1800, check=False)
                if result.returncode:
                    raise LocalHeadImageError((result.stderr or result.stdout or "Luna ranking failed")[-2000:])
                entries = validate_ranking(json.loads(output_file.read_text(encoding="utf-8")), [item["candidate_id"] for item in survivors])
                model = str(getattr(self.app.config, "codex_default_model", "gpt-6-luna"))
            finally:
                schema_file.unlink(missing_ok=True)
                output_file.unlink(missing_ok=True)
        root, state = self._state(run_id)
        state.setdefault("rankings", {})[view] = {"status": "COMPLETE",
            "ordered_candidate_ids": [item["candidate_id"] for item in entries], "entries": entries,
            "input_hashes": hashes, "anchor_hash": anchor_hash, "model": model, "recorded_at": self._now()}
        self._write(root / "state.json", state)
        return self.detail(run_id)

    def select_view(self, run_id: str, view: str, candidate_id: str) -> dict[str, Any]:
        run = self.detail(run_id)
        view = str(view or "").upper()
        selected = run.get("selected_views") or {}
        if not candidate_id:
            asset_key = self.asset_store.key("Head-Image", view)
            record = self.asset_store.detail(run["character"], run["phase"])["assets"].get(asset_key) or {}
            if record.get("batch_id") == run_id and record.get("candidate_id") == selected.get(view):
                self.asset_store.clear_selection(run["character"], run["phase"], "Head-Image", view)
            root, state = self._state(run_id)
            state.setdefault("selected_views", {}).pop(view, None)
            if view == FRONT:
                state["front_anchor"] = None
                for downstream in VIEWS:
                    if downstream != FRONT:
                        state.setdefault("selected_views", {}).pop(downstream, None)
                        ranking = state.setdefault("rankings", {}).get(downstream)
                        if ranking:
                            ranking.update(status="STALE", stale_reason="The selected FRONT anchor was cleared.")
                for other in VIEWS:
                    if other != FRONT:
                        state.setdefault("selected_views", {}).pop(other, None)
            self._write(root / "state.json", state)
            return self.detail(run_id)
        candidate = next((item for item in run["candidates"] if item["candidate_id"] == candidate_id), None)
        if not candidate or candidate["view"] != view or candidate.get("rejection_gate"):
            raise LocalHeadImageError("Choose a gate-surviving candidate from this view.")
        ranking = (run.get("rankings") or {}).get(view) or {}
        image = Path(str(candidate.get("image_path") or ""))
        if (ranking.get("status") != "COMPLETE" or candidate_id not in ranking.get("ordered_candidate_ids", [])
                or not image.is_file() or ranking.get("input_hashes", {}).get(candidate_id) != self._hash(image)):
            raise LocalHeadImageError("The candidate needs a current gate review and ranking before selection.")
        if selected.get(view) != candidate_id:
            self.asset_store.assert_change_allowed(run["character"], run["phase"], "Head-Image", view)
        dependencies = []
        if view != FRONT:
            anchor = next(item for item in run["candidates"] if item["candidate_id"] == run["front_anchor"])
            anchor_hash = self._hash(Path(anchor["image_path"]))
            if ranking.get("anchor_hash") != anchor_hash:
                raise LocalHeadImageError("The FRONT anchor changed after ranking; rerun review for this view.")
            dependencies = [{"key": self.asset_store.key("Head-Image", FRONT), "image_sha256": anchor_hash}]
        root, state = self._state(run_id)
        state.setdefault("selected_views", {})[view] = candidate_id
        if view == FRONT:
            state["front_anchor"] = candidate_id
            for other_view in VIEWS:
                if other_view != FRONT:
                    state.setdefault("selected_views", {}).pop(other_view, None)
            state.setdefault("rankings", {})
            for other_view in VIEWS:
                if other_view != FRONT:
                    state["rankings"].pop(other_view, None)
        self.asset_store.record_selection(run["character"], run["phase"], "Head-Image", view,
                                          candidate_id=candidate_id, image_path=image, batch_id=run_id,
                                          dependencies=dependencies)
        self._write(root / "state.json", state)
        return self.detail(run_id)

    def update_candidate(self, run_id: str, candidate_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        run = self.detail(run_id)
        candidate = next((item for item in run["candidates"] if item["candidate_id"] == candidate_id), None)
        decision = str(payload.get("decision") or "undecided")
        if not candidate or decision not in {"keep", "reject", "undecided"}:
            raise LocalHeadImageError("Invalid candidate or human decision.")
        self.asset_store.assert_change_allowed(run["character"], run["phase"], "Head-Image", candidate["view"])
        if candidate.get("rejection_gate"):
            raise LocalHeadImageError("Gate-rejected candidates cannot be selected for human review.")
        if candidate.get("status") not in {"WAITING_FOR_HUMAN_REVIEW", "COMPLETE"}:
            raise LocalHeadImageError("Candidate must pass current gates before human review.")
        self._update(run_id, candidate_id, human_review={"decision": decision, "notes": str(payload.get("notes") or "")})
        return self.detail(run_id)

    def lock_selected_view(self, run_id: str, view: str) -> dict[str, Any]:
        run = self.detail(run_id)
        candidate_id = (run.get("selected_views") or {}).get(view)
        candidate = next((item for item in run["candidates"] if item["candidate_id"] == candidate_id), None)
        ranking = (run.get("rankings") or {}).get(view) or {}
        image = Path(str((candidate or {}).get("image_path") or ""))
        local_asset = (run.get("local_assets") or {}).get(self.asset_store.key("Head-Image", view)) or {}
        if local_asset.get("candidate_id") != candidate_id or local_asset.get("batch_id") != run_id:
            raise LocalHeadImageError("Select this candidate as the current local asset before locking it.")
        if (not candidate or not image.is_file() or ranking.get("status") != "COMPLETE"
                or ranking.get("input_hashes", {}).get(candidate_id) != self._hash(image)):
            raise LocalHeadImageError("Select a candidate with current gates and ranking before locking it.")
        if candidate.get("human_review", {}).get("decision") == "reject":
            raise LocalHeadImageError("A human-rejected candidate cannot be locked.")
        definitions = self.review_gates(view, has_front_source=bool(run.get("front_source")))
        for gate in definitions:
            record = (candidate.get("gates") or {}).get(gate.key) or {}
            expected = {"candidate": self._hash(image), "front_anchor": ""}
            if gate.uses_anchor:
                anchor = next((item for item in run["candidates"] if item["candidate_id"] == run.get("front_anchor")), None)
                anchor_path = Path(str((anchor or {}).get("image_path") or ""))
                expected["front_anchor"] = self._hash(anchor_path) if anchor_path.is_file() else ""
            if gate.key == "source_identity":
                expected["front_source"] = run.get("front_source_sha256", "")
            if (record.get("status") != "COMPLETE" or record.get("verdict") != "FALSE"
                    or record.get("input_hashes") != expected):
                raise LocalHeadImageError(f"The selected candidate has a missing or stale {gate.key} gate.")
        return self.asset_store.lock(run["character"], run["phase"], "Head-Image", view)

    def unlock_view(self, character: str, phase: str, view: str) -> dict[str, Any]:
        return self.asset_store.unlock(character, phase, "Head-Image", view)

    def proceed(self, run_id: str) -> dict[str, Any]:
        run = self.detail(run_id)
        if not run.get("front_anchor"):
            raise LocalHeadImageError("Select a reviewed FRONT candidate before generating other views.")
        pending_views = {view for view in VIEWS if view != FRONT and any(
            item["view"] == view and item["status"] in {"PENDING", "FAILED"} for item in run["candidates"])}
        self._run_update(run_id, status="RUNNING", stop_requested=False)
        return {**self.detail(run_id), "target_views": sorted(pending_views)}

    def rerun_view(self, run_id: str, view: str) -> dict[str, Any]:
        run = self.detail(run_id)
        view = str(view or "").upper()
        if view not in VIEWS:
            raise LocalHeadImageError(f"Unknown view: {view}")
        self.asset_store.assert_change_allowed(run["character"], run["phase"], "Head-Image", view)
        root, state = self._state(run_id)
        for item in run["candidates"]:
            if item["view"] == view:
                state.setdefault("candidates", {}).setdefault(item["candidate_id"], {}).update(
                    status="PENDING", image_path="", ask_id="", gates={}, rejection_gate="", render_error="",
                    retry_count=int(item.get("retry_count") or 0) + 1,
                    seed=str(random.SystemRandom().randrange(0, 2**63 - 1)))
        state.setdefault("rankings", {}).pop(view, None)
        state.setdefault("selected_views", {}).pop(view, None)
        if view == FRONT:
            state["front_anchor"] = None
            for other_view in VIEWS:
                if other_view != FRONT:
                    state.setdefault("selected_views", {}).pop(other_view, None)
                    ranking = state.setdefault("rankings", {}).get(other_view)
                    if ranking:
                        ranking.update(status="STALE", stale_reason="The selected FRONT anchor changed.")
        state.update(status="RUNNING", stop_requested=False, error="")
        self._write(root / "state.json", state)
        return self.detail(run_id)

    def rerun_failed_view(self, run_id: str, view: str) -> dict[str, Any]:
        run = self.detail(run_id)
        self.asset_store.assert_change_allowed(run["character"], run["phase"], "Head-Image", view)
        root, state = self._state(run_id)
        for item in run["candidates"]:
            if item["view"] == view and (item.get("status") in {"FAILED", "GATE_REJECTED"} or item.get("human_review", {}).get("decision") == "reject"):
                state.setdefault("candidates", {}).setdefault(item["candidate_id"], {}).update(
                    status="PENDING", image_path="", ask_id="", gates={}, rejection_gate="", render_error="",
                    human_review={"decision": "undecided", "notes": ""}, retry_count=int(item.get("retry_count") or 0) + 1)
        self._write(root / "state.json", state)
        return self.detail(run_id)

    def reevaluate(self, run_id: str, view: str | None = None) -> dict[str, Any]:
        run = self.detail(run_id)
        targets = {view.upper()} if view else set(VIEWS)
        for target in targets:
            if target not in VIEWS:
                raise LocalHeadImageError(f"Unknown view: {target}")
            self.asset_store.assert_change_allowed(run["character"], run["phase"], "Head-Image", target)
        root, state = self._state(run_id)
        for item in run["candidates"]:
            if item["view"] in targets and Path(str(item.get("image_path") or "")).is_file():
                state.setdefault("candidates", {}).setdefault(item["candidate_id"], {}).update(
                    status="WAITING_FOR_GATES", gates={}, rejection_gate="", render_error="")
        state["status"] = "REEVALUATING"
        self._write(root / "state.json", state)
        return self.detail(run_id)

    def retry_candidate(self, run_id: str, candidate_id: str) -> dict[str, Any]:
        candidate = next((item for item in self.detail(run_id)["candidates"] if item["candidate_id"] == candidate_id), None)
        if not candidate:
            raise LocalHeadImageError(f"Unknown candidate: {candidate_id}")
        self.asset_store.assert_change_allowed(self.detail(run_id)["character"], self.detail(run_id)["phase"], "Head-Image", candidate["view"])
        self._update(run_id, candidate_id, status="PENDING", image_path="", ask_id="", gates={}, rejection_gate="",
                     render_error="", retry_count=int(candidate.get("retry_count") or 0) + 1)
        return self.detail(run_id)

    def move_candidate_rank(self, run_id: str, view: str, candidate_id: str, direction: str) -> dict[str, Any]:
        run = self.detail(run_id)
        self.asset_store.assert_change_allowed(run["character"], run["phase"], "Head-Image", view)
        ranking = (run.get("rankings") or {}).get(view) or {}
        order = list(ranking.get("ordered_candidate_ids") or [])
        if ranking.get("status") != "COMPLETE" or candidate_id not in order or direction not in {"up", "down"}:
            raise LocalHeadImageError("A current ranking and valid direction are required.")
        index = order.index(candidate_id); other = index + (-1 if direction == "up" else 1)
        if not 0 <= other < len(order): return run
        order[index], order[other] = order[other], order[index]
        root, state = self._state(run_id); ranking = state["rankings"][view]
        ranking.setdefault("luna_ordered_candidate_ids", ranking["ordered_candidate_ids"])
        ranking["ordered_candidate_ids"] = order
        by_id = {item["candidate_id"]: item for item in ranking["entries"]}
        ranking["entries"] = [by_id[item] for item in order]
        ranking["adjusted_at"] = self._now(); self._write(root / "state.json", state)
        return self.detail(run_id)

    def request_stop(self, run_id: str) -> dict[str, Any]:
        self._run_update(run_id, stop_requested=True, status="STOPPING")
        self._withdraw_queued_asks(run_id)
        return self.detail(run_id)

    def _withdraw_queued_asks(self, run_id: str) -> None:
        paths = self.app.ai_proxy_service.ai_proxy_path_service
        queue_root = Path(self.app.config.base_ai_queue_path)
        prefixes = (f"LocalHeadImage_{run_id}_", f"Ask_LocalHeadImage_{run_id}_")
        for task in paths.task_paths("ask"):
            if task.name.startswith(prefixes):
                supersede_task(queue_root, task, "Local Head-Image run was cancelled.")

    def resume(self, run_id: str) -> dict[str, Any]:
        self._run_update(run_id, stop_requested=False, status="RUNNING")
        return self.detail(run_id)

    def delete_run(self, run_id: str) -> dict[str, Any]:
        root = self._run_root(run_id)
        run = self.detail(run_id)
        if any(record.get("selected") and record.get("batch_id") == run_id and not record.get("locked")
               for record in run["local_assets"].values()):
            raise LocalHeadImageError("Lock or unselect this batch's local assets before deleting it.")
        if run.get("status") in {"RUNNING", "STOPPING", "REEVALUATING"} and not run.get("interrupted"):
            raise LocalHeadImageError("Stop the batch and wait before deleting it.")
        self._withdraw_queued_asks(run_id)
        shutil.rmtree(root)
        return {"deleted": True, "run_id": run_id}

    def image_path(self, run_id: str, candidate_id: str) -> Path:
        run = self.detail(run_id)
        candidate = next((item for item in run["candidates"] if item["candidate_id"] == candidate_id), None)
        path = Path(str((candidate or {}).get("image_path") or "")).resolve()
        if not path.is_file() or not path.is_relative_to(Path(run["root"]).resolve()):
            raise LocalHeadImageError("Candidate image is unavailable.")
        return path
