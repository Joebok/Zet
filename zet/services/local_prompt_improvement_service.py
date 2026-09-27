"""Per-view prompt improvement observations and portable review packages."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
from typing import Any
from uuid import uuid4
import zipfile

from zet.services.atomic_file_service import write_json_atomic
from zet.services.local_image_pipeline_policy import mutate_local_run_state
from zet.services.local_candidate_review_contract import view_review_defaults
from zet.services.workflow_storage import file_lock


_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="zet-prompt-improvement")
_ACTIVE_LOCK = threading.Lock()
_ACTIVE_JOBS: set[str] = set()


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_paths(source_map: Path) -> list[Path]:
    if not source_map.is_file():
        return []
    try:
        data = json.loads(source_map.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    paths = []
    for fragment in data.get("fragments") or []:
        value = fragment.get("source_path")
        if value and Path(str(value)).suffix.lower() in {".md", ".json", ".yaml", ".yml"}:
            path = Path(str(value))
            if path.is_file() and path not in paths:
                paths.append(path)
    return paths


def record_compiler_sources(output_dir: Path) -> None:
    """Capture source hashes alongside the prompt at local compilation time."""
    sources = {str(path.resolve()): _hash(path) for path in _source_paths(output_dir / "Prompt_Source_Map.json")}
    write_json_atomic(output_dir / "Prompt_Source_Hashes.json", sources)


def ensure_view_reviews(root: Path, spec: dict[str, Any], state: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Move historical candidate notes into view observations exactly once."""
    def has_notes(source: dict[str, Any], updates: dict[str, Any]) -> bool:
        return any(str((human if isinstance(human, dict) else {}).get("notes") or "").strip()
                   for item in source.get("candidates") or []
                   for human in (item.get("human_review"),
                                 (updates.get(item.get("candidate_id")) or {}).get("human_review")))

    if state.get("prompt_improvement_migrated") and not has_notes(spec, state.get("candidates") or {}):
        return spec, state
    with file_lock(root / "state.lock"):
        spec = json.loads((root / "spec.json").read_text(encoding="utf-8"))
        state = json.loads((root / "state.json").read_text(encoding="utf-8"))
        if state.get("prompt_improvement_migrated") and not has_notes(spec, state.get("candidates") or {}):
            return spec, state
        reviews = state.setdefault("view_reviews", {})
        for view in spec.get("views") or []:
            record = reviews.setdefault(str(view), {})
            defaults = view_review_defaults()
            record.setdefault("observations", defaults["observations"])
            record.setdefault("ai_observations", defaults["ai_observations"])
        updates = state.setdefault("candidates", {})
        for candidate in spec.get("candidates") or []:
            candidate_id = str(candidate.get("candidate_id") or "")
            view = str(candidate.get("view") or "")
            update = updates.get(candidate_id) or {}
            notes = list(dict.fromkeys(str((human if isinstance(human, dict) else {}).get("notes") or "").strip()
                                       for human in (candidate.get("human_review"), update.get("human_review"))))
            notes = [note for note in notes if note]
            if notes and view:
                record = reviews.setdefault(view, {})
                prior = str(record.get("observations") or "").strip()
                added = "\n\n".join(f"{candidate_id}: {note}" for note in notes)
                record["observations"] = f"{prior}\n\n{added}".strip()
            for item in (candidate, update):
                human = item.get("human_review")
                if isinstance(human, dict):
                    human.pop("notes", None)
        state["prompt_improvement_migrated"] = True
        write_json_atomic(root / "state.json", state)
        write_json_atomic(root / "spec.json", spec)
        return spec, state


class LocalPromptImprovementService:
    def __init__(self, adapter: Any, pipeline: str, project_root: str | Path):
        self.adapter = adapter
        self.pipeline = pipeline
        self.project_root = Path(project_root).resolve()

    def _run(self, run_id: str, costume: str = "", *, upgrade_legacy: bool = False) -> dict[str, Any]:
        if self.pipeline in {"character-assembly", "costume-dressing"}:
            return self.adapter.detail(run_id, costume, upgrade_legacy=upgrade_legacy)
        if self.pipeline == "body-reference":
            return self.adapter.detail(run_id, upgrade_legacy=upgrade_legacy)
        return self.adapter.detail(run_id)

    @staticmethod
    def _root(run: dict[str, Any]) -> Path:
        return Path(run["root"]).resolve()

    @staticmethod
    def _view(run: dict[str, Any], view: str) -> str:
        view = str(view or "").upper()
        if view not in (run.get("views") or []):
            raise ValueError(f"Unknown local batch view: {view}")
        return view

    @staticmethod
    def _images(run: dict[str, Any], view: str) -> tuple[list[tuple[dict[str, Any], Path]], list[dict[str, str]]]:
        images, missing = [], []
        for candidate in (item for item in run.get("candidates") or [] if item.get("view") == view):
            path = Path(str(candidate.get("image_path") or ""))
            if path.is_file():
                images.append((candidate, path))
            else:
                missing.append({"candidate_id": str(candidate["candidate_id"]),
                                "status": str(candidate.get("render_status") or candidate.get("status") or "UNKNOWN"),
                                "reason": str(candidate.get("render_error") or candidate.get("error") or "Image unavailable")})
        return images, missing

    def detail(self, run_id: str, costume: str = "", *, upgrade_legacy: bool = False) -> dict[str, Any]:
        run = self._run(run_id, costume, upgrade_legacy=upgrade_legacy)
        root = self._root(run)
        spec = json.loads((root / "spec.json").read_text(encoding="utf-8"))
        state = json.loads((root / "state.json").read_text(encoding="utf-8"))
        if not state.get("prompt_improvement_migrated"):
            ensure_view_reviews(root, spec, state)
            run = self._run(run_id, costume)
        interrupted = []
        for view, record in (run.get("view_reviews") or {}).items():
            ai = record.get("ai_observations") or {}
            if ai.get("status") in {"QUEUED", "RUNNING"}:
                with _ACTIVE_LOCK:
                    active = ai.get("job_id") in _ACTIVE_JOBS
                if not active:
                    interrupted.append(view)
        if interrupted:
            def mark_interrupted(state: dict[str, Any]) -> None:
                for view in interrupted:
                    ai = state.setdefault("view_reviews", {}).setdefault(view, {}).setdefault("ai_observations", {})
                    with _ACTIVE_LOCK:
                        active = ai.get("job_id") in _ACTIVE_JOBS
                    if ai.get("status") in {"QUEUED", "RUNNING"} and not active:
                        ai.update(status="FAILED", error="Analysis was interrupted; use Re-analyze.", completed_at=_now())
            mutate_local_run_state(root, mark_interrupted)
            run = self._run(run_id, costume)
        for candidate in run.get("candidates") or []:
            (candidate.get("human_review") or {}).pop("notes", None)
        for view, record in (run.get("view_reviews") or {}).items():
            ai = record.get("ai_observations") or {}
            if ai.get("status") != "COMPLETE":
                continue
            images, _ = self._images(run, view)
            hashes = {item["candidate_id"]: _hash(path) for item, path in images}
            if hashes != ai.get("input_hashes"):
                ai["status"] = "STALE"
                ai["stale_reason"] = "View images changed after analysis."
        return run

    def save_observations(self, run_id: str, view: str, observations: str, costume: str = "") -> dict[str, Any]:
        run = self.detail(run_id, costume)
        view = self._view(run, view)
        if not isinstance(observations, str):
            raise ValueError("Observations must be text.")
        def save(state: dict[str, Any]) -> None:
            state.setdefault("view_reviews", {}).setdefault(view, {})["observations"] = observations
            state["updated_at"] = _now()
        mutate_local_run_state(self._root(run), save)
        return self.detail(run_id, costume)

    def reset_after_rerender(self, run_id: str, views: set[str], costume: str = "") -> None:
        run = self.detail(run_id, costume)
        def reset(state: dict[str, Any]) -> None:
            for view in views:
                record = state.setdefault("view_reviews", {}).setdefault(view, {})
                record["ai_observations"] = {"status": "PENDING", "text": "", "auto_started": False}
        mutate_local_run_state(self._root(run), reset)

    def start(self, run_id: str, view: str, costume: str = "", *, automatic: bool = False) -> dict[str, Any]:
        run = self.detail(run_id, costume)
        view = self._view(run, view)
        images, missing = self._images(run, view)
        if not images:
            if automatic:
                return run
            raise ValueError("No rendered images are available for this view.")
        hashes = {item["candidate_id"]: _hash(path) for item, path in images}
        job_id = uuid4().hex
        with _ACTIVE_LOCK:
            _ACTIVE_JOBS.add(job_id)
        accepted: list[bool] = []
        def claim(state: dict[str, Any]) -> None:
            record = state.setdefault("view_reviews", {}).setdefault(view, {})
            previous = record.get("ai_observations") or {}
            if previous.get("status") in {"QUEUED", "RUNNING"}:
                accepted.append(False)
                return
            ranking = (state.get("rankings", {}).get(view) or {})
            if automatic and (previous.get("auto_started") or ranking.get("status") != "COMPLETE"
                              or (ranking.get("input_hashes") and ranking["input_hashes"] != hashes)):
                accepted.append(False)
                return
            record["ai_observations"] = {"status": "QUEUED", "text": str(previous.get("text") or ""),
                "auto_started": bool(automatic or previous.get("auto_started")), "job_id": job_id,
                "input_hashes": hashes, "missing_candidates": missing, "queued_at": _now(), "error": ""}
            accepted.append(True)
        mutate_local_run_state(self._root(run), claim)
        if accepted and accepted[-1]:
            try:
                _POOL.submit(self._analyze, run_id, view, costume, job_id, hashes, missing)
            except Exception as exc:
                self._save_ai(run, view, job_id, {"status": "FAILED", "error": str(exc), "completed_at": _now()})
                with _ACTIVE_LOCK:
                    _ACTIVE_JOBS.discard(job_id)
        else:
            with _ACTIVE_LOCK:
                _ACTIVE_JOBS.discard(job_id)
        return self.detail(run_id, costume)

    def _analyze(self, run_id: str, view: str, costume: str, job_id: str,
                 hashes: dict[str, str], missing: list[dict[str, str]]) -> None:
        try:
            run = self.detail(run_id, costume)
            images, _ = self._images(run, view)
            images = [(item, path) for item, path in images if item["candidate_id"] in hashes]
            if {item["candidate_id"]: _hash(path) for item, path in images} != hashes:
                raise ValueError("View images changed before analysis started.")
            self._save_ai(run, view, job_id, {"status": "RUNNING", "started_at": _now()})
            executable = shutil.which("codex")
            if not executable and os.name == "nt" and os.environ.get("LOCALAPPDATA"):
                installs = list((Path(os.environ["LOCALAPPDATA"]) / "OpenAI" / "Codex" / "bin").glob("*/codex.exe"))
                if installs:
                    executable = str(max(installs, key=lambda path: path.stat().st_mtime_ns))
            if not executable:
                raise ValueError("Codex CLI is unavailable for Luna observations.")
            prompt = self._analysis_prompt(run, view, images, missing)
            schema = {"type": "object", "properties": {"observations": {"type": "string"}},
                      "required": ["observations"], "additionalProperties": False}
            with tempfile.TemporaryDirectory(prefix="zet_prompt_improvement_") as temp:
                schema_path, output_path = Path(temp) / "schema.json", Path(temp) / "answer.json"
                schema_path.write_text(json.dumps(schema), encoding="utf-8")
                command = [executable, "-a", "never", "-s", "read-only", "-m",
                           str(getattr(self.adapter.app.config, "codex_default_model", "gpt-6-luna")),
                           "-c", 'model_reasoning_effort="high"', "-C", str(self.project_root), "exec",
                           "--ignore-user-config", "--skip-git-repo-check", "--ephemeral", "--output-schema",
                           str(schema_path), "--output-last-message", str(output_path)]
                for _, path in images:
                    command.extend(["--image", str(path)])
                completed = subprocess.run(command, input=prompt, capture_output=True, text=True,
                                           encoding="utf-8", errors="replace", timeout=1800, check=False)
                if completed.returncode:
                    raise ValueError((completed.stderr or completed.stdout or "Luna observations failed")[-2000:])
                answer = json.loads(output_path.read_text(encoding="utf-8"))
                observations = str(answer.get("observations") or "").strip()
                if not observations:
                    raise ValueError("Luna returned empty observations.")
            latest = self.detail(run_id, costume)
            current, _ = self._images(latest, view)
            current_hashes = {item["candidate_id"]: _hash(path) for item, path in current}
            self._save_ai(latest, view, job_id, {"status": "COMPLETE" if current_hashes == hashes else "STALE",
                "text": observations, "input_hashes": hashes, "missing_candidates": missing,
                "model": str(getattr(self.adapter.app.config, "codex_default_model", "gpt-6-luna")),
                "completed_at": _now(), "error": ""})
        except Exception as exc:
            try:
                self._save_ai(self._run(run_id, costume), view, job_id,
                              {"status": "FAILED", "error": str(exc), "completed_at": _now()})
            except Exception:
                pass
        finally:
            with _ACTIVE_LOCK:
                _ACTIVE_JOBS.discard(job_id)

    def _save_ai(self, run: dict[str, Any], view: str, job_id: str, changes: dict[str, Any]) -> None:
        def save(state: dict[str, Any]) -> None:
            ai = state.setdefault("view_reviews", {}).setdefault(view, {}).setdefault("ai_observations", {})
            if ai.get("job_id") == job_id:
                ai.update(changes)
        mutate_local_run_state(self._root(run), save)

    def _saved_prompt(self, run: dict[str, Any], view: str) -> str:
        path = self._root(run) / "prompts" / view / "Final_Image_Prompt.md"
        if path.is_file():
            return path.read_text(encoding="utf-8")
        snapshot = next((item for item in run.get("prompt_snapshots") or [] if item.get("view") == view), {})
        return str(snapshot.get("manual_prompt") or "")

    def _analysis_prompt(self, run: dict[str, Any], view: str,
                         images: list[tuple[dict[str, Any], Path]], missing: list[dict[str, str]]) -> str:
        mapping = "\n".join(f"Image {index}: {item['candidate_id']} (status {item.get('status') or 'UNKNOWN'})"
                            for index, (item, _) in enumerate(images, 1))
        return (f"Review every supplied image from the {self.pipeline} batch's {view} view.\n"
                "Report noticeable structural discrepancies and variations between images that a clearer prompt or template could mitigate. "
                "Focus on silhouette, garment size and shape, head/body proportions, hair length and form, and equipment or weapon placement. "
                "Use candidate IDs as evidence and distinguish a recurring variation from an isolated defect. "
                "Do not focus on minor decorative differences such as embroidery motifs. Do not rank, reject, or skip gate-failed images. "
                "For one image, compare major structures against the saved prompt and state that cross-image variation cannot be assessed. "
                "Do not claim to inspect missing images. Return concise observations, not rewritten prompts.\n\n"
                f"Image mapping:\n{mapping}\n\nMissing images and reasons:\n{json.dumps(missing, indent=2)}\n\n"
                f"Saved image prompt:\n{self._saved_prompt(run, view)}")

    def create_package(self, run_id: str, costume: str = "") -> Path:
        run = self.detail(run_id, costume)
        root = self._root(run)
        handle, name = tempfile.mkstemp(prefix="zet_prompt_improvement_", suffix=".zip")
        os.close(handle)
        target = Path(name)
        manifest: dict[str, Any] = {"pipeline": self.pipeline, "run_id": run_id,
            "character": run.get("character"), "phase": run.get("phase"), "costume": run.get("costume"),
            "created_at": _now(), "files": [], "missing": [], "source_changes": [], "unverified_sources": []}
        included: set[Path] = set()
        archive_names: set[str] = set()
        known_source_hashes: dict[str, str] = {}
        try:
            with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                def add_text(label: str, value: str) -> None:
                    data = value.encode("utf-8")
                    archive.writestr(label, data)
                    manifest["files"].append({"name": label, "sha256": hashlib.sha256(data).hexdigest()})

                def add(path: Path, label: str, expected_hash: str = "") -> None:
                    path = path.resolve()
                    if not path.is_file():
                        manifest["missing"].append({"label": label, "path": str(path)})
                        return
                    if path in included and label.startswith("sources/"):
                        current_hash = _hash(path) if expected_hash else ""
                        if expected_hash and current_hash != expected_hash:
                            manifest["source_changes"].append({"label": label, "expected_sha256": expected_hash,
                                                                "current_sha256": current_hash})
                        return
                    digest = _hash(path)
                    if expected_hash and digest != expected_hash:
                        manifest["source_changes"].append({"label": label, "expected_sha256": expected_hash,
                                                            "current_sha256": digest})
                    elif label.startswith("sources/") and not expected_hash:
                        manifest["unverified_sources"].append(label)
                    included.add(path)
                    archive_name = label.replace("\\", "/")
                    if archive_name in archive_names:
                        archive_name = f"sources/{hashlib.sha256(str(path).encode()).hexdigest()[:8]}_{path.name}"
                    archive_names.add(archive_name)
                    archive.write(path, archive_name)
                    manifest["files"].append({"name": archive_name, "sha256": digest,
                                              "expected_sha256": expected_hash, "original_path": str(path) if label.startswith("sources/") else ""})

                reviews = run.get("view_reviews") or {}
                for view in run.get("views") or []:
                    images, missing = self._images(run, view)
                    for item, path in images:
                        add(path, f"images/{view}/{item['candidate_id']}{path.suffix.lower()}")
                    manifest["missing"].extend({"label": f"images/{view}/{item['candidate_id']}", **item} for item in missing)
                    prompt_dir = root / "prompts" / view
                    for filename in ("Final_Image_Prompt.md", "Prompt_Source_Map.json", "dependency_manifest.json", "Compiled_Sections.md", "Prompt_Source_Hashes.json"):
                        path = prompt_dir / filename
                        if path.is_file():
                            add(path, f"prompts/{view}/{filename}")
                    if not (prompt_dir / "Final_Image_Prompt.md").is_file():
                        prompt = self._saved_prompt(run, view)
                        if prompt:
                            add_text(f"prompts/{view}/Final_Image_Prompt.md", prompt)
                    hash_path = prompt_dir / "Prompt_Source_Hashes.json"
                    source_hashes = json.loads(hash_path.read_text(encoding="utf-8")) if hash_path.is_file() else {}
                    known_source_hashes.update(source_hashes)
                    for source in _source_paths(prompt_dir / "Prompt_Source_Map.json"):
                        add(source, f"sources/{source.name}", source_hashes.get(str(source.resolve()), ""))
                    for source_name, expected in source_hashes.items():
                        if not Path(source_name).is_file():
                            manifest["source_changes"].append({"label": source_name,
                                "expected_sha256": expected, "current_sha256": "", "reason": "Source missing"})
                    snapshot = next((item for item in run.get("prompt_snapshots") or [] if item.get("view") == view), {})
                    render_prompt = str(snapshot.get("qwen_prompt") or "")
                    if render_prompt:
                        add_text(f"prompts/{view}/Render_Prompt.md", render_prompt)
                    for candidate in (item for item in run.get("candidates") or [] if item.get("view") == view):
                        prompt = str(candidate.get("prompt") or "")
                        if prompt and prompt != render_prompt:
                            add_text(f"prompts/{view}/candidates/{candidate['candidate_id']}.md", prompt)
                    for key in ("source_map", "dependency_manifest"):
                        path_value = snapshot.get(key)
                        if path_value:
                            path = Path(str(path_value))
                            add(path, f"prompts/{view}/{path.name}")
                character = Path(self.adapter.app.config.base_character_path) / str(run.get("character") or "") / str(run.get("phase") or "") / "Character.md"
                add(character, "sources/Character.md", known_source_hashes.get(str(character.resolve()), ""))
                costume_path = run.get("costume_path")
                if costume_path:
                    path = Path(str(costume_path))
                    add(path, "sources/Costume.md", known_source_hashes.get(str(path.resolve()), ""))
                for path in (self.project_root / "Config" / "Prompt_Templates").glob("*.md"):
                    if path.stem in {"body_reference_v2", "head_image_v2", "character_assembly_v2", "costume_dressing_v2",
                                     "final_image_prompt_tail_v1"} and (path.stem.startswith(self.pipeline.replace("-", "_")) or path.stem == "final_image_prompt_tail_v1"):
                        add(path, f"sources/{path.name}", known_source_hashes.get(str(path.resolve()), ""))
                guide = self.project_root / "Docs" / "Prompt_Compiler_Guide.md"
                add(guide, "Prompt_Compiler_Guide.md")
                for view in run.get("views") or []:
                    roles = {"character-assembly": ("body_reference", "head_image"),
                             "costume-dressing": ("character_assembly",)}.get(self.pipeline, ())
                    if view != "FRONT" or (self.pipeline == "head-image" and run.get("front_source")):
                        roles = (*roles, "front_reference")
                    for role in roles:
                        try:
                            source = self._reference_path(run, view, role, costume)
                        except Exception:
                            source = None
                        if source:
                            add(source, f"references/{view}/{role}{source.suffix.lower()}")
                        else:
                            manifest["missing"].append({"label": f"references/{view}/{role}", "reason": "Reference unavailable"})
                add_text("Observations.json", json.dumps(reviews, indent=2, ensure_ascii=False))
                add_text("ChatGPT_Review_Request.md", self._package_request(run))
                archive.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
            return target
        except Exception:
            target.unlink(missing_ok=True)
            raise

    def _reference_path(self, run: dict[str, Any], view: str, role: str, costume: str) -> Path | None:
        if role == "front_reference" and self.pipeline == "head-image" and view == "FRONT" and run.get("front_source"):
            return Path(str(run["front_source"]))
        if self.pipeline in {"character-assembly", "costume-dressing"} and role != "front_reference":
            try:
                return self.adapter.source_path(run["run_id"], view, role, costume)
            except Exception:
                return None
        if view != "FRONT" and role == "front_reference":
            candidate = next((item for item in run.get("candidates") or [] if item["candidate_id"] == run.get("front_anchor")), None)
            if candidate and candidate.get("image_path"):
                return Path(str(candidate["image_path"]))
        return None

    def _package_request(self, run: dict[str, Any]) -> str:
        return (f"# Prompt Improvement Review\n\nReview the {self.pipeline} batch for {run.get('character')}/{run.get('phase')}. "
                "Use Observations.json, all available images, saved compiled prompts, the relevant source templates, "
                "source maps, dependency manifests, and Prompt_Compiler_Guide.md. Identify major structural variation "
                "that clearer prompt or template wording could reduce. Give evidence by view and candidate ID. "
                "Distinguish prompt ambiguity from model inconsistency and missing images. "
                "For every source template you recommend changing, return the complete proposed replacement template, ready for review, "
                "with only minimal, targeted changes. Identify the exact source sections changed and explain how each change compiles "
                "into the final prompt. Preserve all required tags and compiler contracts. "
                "Identify issues that template edits alone cannot adequately address. Where evidence supports it, recommend specific "
                "improvements to compilation, review, image selection, or other parts of the process, and keep these recommendations "
                "separate from the proposed templates. Do not edit files or treat any suggested change as approved.\n")


def after_initial_ranking(adapter: Any, pipeline: str, project_root: Path,
                          run_id: str, view: str, costume: str = "") -> None:
    """Called after a ranking commit; state prevents repeats on later rankings."""
    try:
        LocalPromptImprovementService(adapter, pipeline, project_root).start(run_id, view, costume, automatic=True)
    except Exception:
        # Ranking is advisory and must remain independent of prompt improvement.
        pass
