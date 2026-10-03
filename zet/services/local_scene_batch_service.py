"""Persistent scene attempts with dynamic target groups and selection checkpoints."""
from __future__ import annotations

import copy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import hashlib
import json
from pathlib import Path
import random
import re
import shutil
from uuid import uuid4

from zet.models.ai_proxy import AI_PROXY_PROTOCOL_VERSION
from zet.services.atomic_file_service import write_json_atomic
from zet.services.ai_proxy_path_service import AIProxyPathService
from zet.services.local_candidate_review_contract import normalize_human_decision, adjust_candidate_ranking
from zet.services.local_image_ranking_service import rank_images_with_luna
from zet.services.local_render_policy import SCENE_PROFILE, require_qwen_profile
from zet.services.scene_prompt_analysis_service import ScenePromptAnalysisService
from zet.services.scene_prompt_sections import load_final_image_prompt_sections
from zet.services.pipeline_compiler_support import universe_art_style
from zet.services.summary_cache import invalidate_summary_cache
from zet.services.workflow_storage import atomic_copy, file_lock, supersede_task, validate_image


_REVIEWS = ThreadPoolExecutor(max_workers=2, thread_name_prefix="scene-batch-review")
_ACTIVE_REVIEWS: set[str] = set()


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class LocalSceneBatchService:
    def __init__(self, app, project_root: str | Path):
        self.app = app
        self.project_root = Path(project_root)
        self.story = app.story_service
        self.targets = self.story.scene_render_target_service
        self.proxy = AIProxyPathService(app.config)

    def workspace(self, story: str, scene: str) -> Path:
        return self.targets.pipeline_path(self.story.safe_slug(story), self.story.safe_slug(scene), "main") / "Local_Batches"

    def root(self, story: str, scene: str, run_id: str) -> Path:
        if not re.fullmatch(r"[a-f0-9]{32}", run_id):
            raise ValueError("Invalid scene batch ID.")
        root = self.workspace(story, scene) / run_id
        if not (root / "spec.json").is_file():
            raise ValueError("Scene batch not found.")
        return root

    def preview(self, story: str, scene: str, payload: dict) -> dict:
        document = self.story.load_scene_builder_data(story, scene)
        if document.blocked:
            raise ValueError(document.error)
        data = document.data
        self.targets.assert_valid_graph(data)
        graph = self.targets.target_graph(data)
        for item in data.get("subscenes") or []:
            parent = graph["parents"].get(item["id"], "main")
            if item.get("enabled") and parent != "main" and not graph["definitions"][parent].get("enabled"):
                raise ValueError("An enabled target belongs to a disabled subscene: " + item["id"])
        groups = [{"target_id": item["id"], "label": self.targets.target_label(data, item["id"]),
                   "kind": item["kind"]} for item in data.get("subscenes") or [] if item.get("enabled")]
        groups.append({"target_id": "main", "label": "Full Scene", "kind": "main"})
        counts = payload.get("counts") or {}
        if not isinstance(counts, dict):
            raise ValueError("Candidate counts must be keyed by target ID.")
        for group in groups:
            value = counts.get(group["target_id"], payload.get("count", 4))
            if isinstance(value, bool) or not str(value).isdigit() or not 1 <= int(value) <= 16:
                raise ValueError("Choose between 1 and 16 candidates per target.")
            group["count"] = int(value)
            group["dependencies"] = [item["id"] for item in self.targets.direct_dependencies(data, group["target_id"])]
        # Stable topological order, preferring ready backgrounds to unrelated elements.
        pending = sorted(groups, key=lambda item: (item["target_id"] == "main", item["kind"] == "element"))
        ordered = []
        while pending:
            ready = next((item for item in pending if set(item["dependencies"]) <= {g["target_id"] for g in ordered}), None)
            if ready is None:
                raise ValueError("An enabled target depends on a disabled or invalid subscene.")
            ordered.append(ready)
            pending.remove(ready)
        return {"story_slug": document.story.slug, "scene_slug": document.scene.slug,
                "targets": ordered, "candidate_count": sum(item["count"] for item in ordered)}

    def _snapshot(self, story: str, scene: str, root: Path) -> dict:
        root.mkdir(parents=True, exist_ok=True)
        data = copy.deepcopy(self.story.load_scene_builder_data(story, scene).data)
        data.pop("_validation_warnings", None)
        data["scene"]["_story_slug"] = story
        sources = self.story._resolve_scene_element_sources(data)
        settings_path = self.story._library_absolute_path(data["scene"]["story_settings_path"])
        settings = self.story.load_story_settings(settings_path)
        sections_path = self.project_root / "Config/Prompt_Templates/final_image_prompt_tail_v1.md"
        art_style, style_sources = universe_art_style(self.app.config.base_library_path)
        if art_style:
            settings.setdefault("style_defaults", {})["canonical_art_style"] = {"full_prompt_text": art_style}
        refs = self.story.story_reference_service.resolve_scene_references("\n" + json.dumps(data))
        originals = [self.story.scene_builder_json_path(story, scene), settings_path, sections_path]
        originals.extend([self.story._library_absolute_path(self.story.load_scene(story, scene).record.path),
                          self.story._library_absolute_path(self.story.load_story(story).record.story_file_path)])
        originals.extend(self.project_root / "zet/services" / name for name in
                         ["qwen_scene_prompt.py", "scene_render_compiler.py", "scene_render_target_service.py", "story_render_service.py"])
        originals.extend(Path(item["source_path"]) for item in style_sources.values())
        for sections in sources.values():
            originals.extend(self.story._library_absolute_path(value) for key, value in sections.items()
                             if key.endswith("_source") and value)
        frozen = []
        for index, ref in enumerate(refs, 1):
            source = Path(ref["path"])
            destination = root / "inputs" / f"{index:03d}{source.suffix}"
            atomic_copy(source, destination)
            frozen.append({**ref, "path": str(destination), "original_path": str(source), "sha256": _hash(source)})
            originals.append(source)
        compiler_sources = {}
        for index, source in enumerate(dict.fromkeys(originals), 1):
            if source.is_file():
                destination = root / "source_files" / f"{index:03d}_{source.name}"
                atomic_copy(source, destination)
                compiler_sources[str(destination)] = _hash(source)
        snapshot = {"scene": data, "settings": settings, "sections": load_final_image_prompt_sections(sections_path),
                    "resolved_material_hash": hashlib.sha256(json.dumps(sources, sort_keys=True).encode("utf-8")).hexdigest(),
                    "references": frozen, "compiler_sources": compiler_sources,
                    "sources": {str(path): _hash(path) for path in originals if path.is_file()}}
        write_json_atomic(root / "snapshot.json", snapshot)
        return snapshot

    def create(self, story: str, scene: str, payload: dict) -> dict:
        plan = self.preview(story, scene, payload)
        story, scene = plan["story_slug"], plan["scene_slug"]
        run_id = uuid4().hex
        root = self.workspace(story, scene) / run_id
        root.mkdir(parents=True, exist_ok=False)
        snapshot_root = root / "snapshots" / uuid4().hex
        self._snapshot(story, scene, snapshot_root)
        atomic_copy(snapshot_root / "snapshot.json", root / "snapshot.json")
        spec = {"schema_version": 1, "kind": "scene", "run_id": run_id, "story_slug": story,
                "scene_slug": scene, "batch_name": str(payload.get("batch_name") or "").strip(),
                "created_at": _now(), "views": [item["target_id"] for item in plan["targets"]], **plan}
        write_json_atomic(root / "spec.json", spec)
        write_json_atomic(root / "state.json", {"status": "QUEUED", "stop_requested": False,
                          "groups": {item["target_id"]: {"status": "PENDING", "candidates": [], "attempts": []}
                                     for item in plan["targets"]}, "selected_views": {}, "rankings": {},
                          "view_reviews": {}, "prompt_improvement_migrated": True})
        return self.detail(story, scene, run_id)

    def list_runs(self, story: str, scene: str) -> list[dict]:
        rows = []
        for path in self.workspace(story, scene).glob("*/spec.json"):
            spec = _read(path)
            state = _read(path.parent / "state.json")
            rows.append({**spec, "status": state["status"]})
        return sorted(rows, key=lambda item: item["created_at"], reverse=True)

    def delete(self, story: str, scene: str, run_id: str) -> None:
        """Remove an inactive batch and its run-owned files."""
        root = self.root(story, scene, run_id)
        self.detail(story, scene, run_id)
        with file_lock(root / "state.lock"):
            state = _read(root / "state.json")
            if any(candidate["status"] in {"SUBMITTING", "QUEUED", "RUNNING"}
                   for group in state["groups"].values() for candidate in group["candidates"]):
                raise ValueError("Stop active render work and wait before deleting this batch.")
            if any(group.get("analysis", {}).get("status") in {"QUEUED", "RUNNING"}
                   for group in state["groups"].values()):
                raise ValueError("Wait for prompt analysis to finish before deleting this batch.")
            if any(ranking.get("status") == "RUNNING" for ranking in state["rankings"].values()):
                raise ValueError("Wait for candidate rating to finish before deleting this batch.")
            # Move it out of the discoverable workspace while holding the run lock,
            # so a render action cannot race with deletion.
            deleted = root.with_name(f".{run_id}.deleting-{uuid4().hex}")
            root.rename(deleted)
        shutil.rmtree(deleted)

    def linked_batch(self, story: str, scene: str, target: str = "main", ask_id: str = "") -> str:
        if not self.targets._safe_target_id(target):
            raise ValueError("Invalid scene target.")
        story, scene = self.story.safe_slug(story), self.story.safe_slug(scene)
        if ask_id:
            for batch in self.list_runs(story, scene):
                state = _read(self.root(story, scene, batch["run_id"]) / "state.json")
                for group in state["groups"].values():
                    for attempt in [group, *group["attempts"]]:
                        if any(job.get("ask_id") == ask_id for candidate in attempt["candidates"]
                               for job in candidate.get("render_attempts", [])):
                            return batch["run_id"]
            return ""
        metadata = self.targets.review_paths(story, scene, target)["metadata"]
        run_id = _read(metadata).get("batch_id", "") if metadata.is_file() else ""
        return run_id if any(batch["run_id"] == run_id for batch in self.list_runs(story, scene)) else ""

    def summaries(self) -> list[dict]:
        rows = []
        for story in self.story.list_stories():
            for scene in self.story.list_scenes(story.slug):
                for summary in self.list_runs(story.slug, scene.slug):
                    run = self.detail(story.slug, scene.slug, summary["run_id"])
                    target = next((key for key, group in run["groups"].items()
                                   if any(item["status"] in {"QUEUED", "RUNNING"} for item in group["candidates"])),
                                  next(iter(run["ready_targets"]), "main"))
                    rows.append({**summary, "status": run["status"], "render_target_id": target,
                                 "target_label": self.targets.target_label(_read(Path(run["root"]) / "snapshot.json")["scene"], target)})
        return rows

    def _selected(self, state: dict) -> dict:
        selected = {}
        for target, candidate_id in state["selected_views"].items():
            group = state["groups"][target]
            candidate = next((item for item in group["candidates"] if item["candidate_id"] == candidate_id), {})
            path = Path(candidate.get("image_path") or "")
            if group.get("stale_reason") or not path.is_file() or candidate.get("sha256") != _hash(path):
                continue
            selected[target] = {"path": str(path), "sha256": _hash(path), "candidate_id": candidate_id}
        return selected

    def _compile(self, root: Path, state: dict, target: str) -> dict:
        snapshot = _read(root / "snapshot.json")
        for reference in snapshot["references"]:
            if not Path(reference["path"]).is_file() or _hash(Path(reference["path"])) != reference["sha256"]:
                raise ValueError("A frozen batch reference is missing or altered. Create a new batch.")
        try:
            compiled = self.story.story_render_service.compile_batch_target(
                snapshot["scene"], snapshot["settings"], snapshot["sections"], snapshot["references"], target,
                self._selected(state))
        except Exception as exc:
            raise ValueError(str(exc)) from exc
        group = state["groups"][target]
        generation = uuid4().hex
        output = root / "targets" / target / generation
        output.mkdir(parents=True, exist_ok=False)
        prompt_path = output / "Qwen_Image_2_1_Prompt.md"
        prompt_path.write_text(compiled["prompt"], encoding="utf-8")
        write_json_atomic(output / "Scene_Render_IR.json", compiled["ir"])
        compiled["references"] = [{**item, "sha256": _hash(Path(item["path"]))} for item in compiled["references"]]
        write_json_atomic(output / "references.json", compiled["references"])
        group.update(attempt_id=generation, prompt_path=str(prompt_path), ir_path=str(output / "Scene_Render_IR.json"),
                     reference_images=compiled["references"], prompt_sha256=_hash(prompt_path),
                     ir_sha256=_hash(output / "Scene_Render_IR.json"),
                     subject_count=len({
                         str(item.get("id") or "") for item in compiled["ir"].get("elements", [])
                         if item.get("element_type", "Character") in {"Character", "Monster"}
                         and str(item.get("id") or "") in {str(place.get("scene_element_id") or "") for place in compiled["ir"].get("placements", [])}
                     }),
                     subject_labels=list(dict.fromkeys(
                         str(item.get("display_name") or item.get("id") or "")
                         for item in compiled["ir"].get("elements", [])
                         if item.get("element_type", "Character") in {"Character", "Monster"}
                         if str(item.get("id") or "") in {str(place.get("scene_element_id") or "") for place in compiled["ir"].get("placements", [])}
                     )),
                     reference_assignments=[{
                         "label": item.get("label", ""), "role": item.get("prompt_role", ""),
                         "applies_to": item.get("applies_to", ""),
                     } for item in compiled["ir"].get("image_inputs", [])],
                     render_input_hash=compiled["render_input_hash"], source_selections=self._selected(state),
                     status="COMPILED", stale_reason="", candidates=[])
        # Shared improvement packages read current per-target compiler artifacts.
        directory = root / "prompts" / target
        atomic_copy(prompt_path, directory / "Final_Image_Prompt.md")
        write_json_atomic(directory / "dependency_manifest.json", {"resources": compiled["references"]})
        write_json_atomic(directory / "Prompt_Source_Hashes.json", snapshot["compiler_sources"])
        write_json_atomic(directory / "Prompt_Source_Map.json", {"fragments": [{"source_path": path} for path in snapshot["compiler_sources"]]})
        return group

    def _refresh_snapshot_for_render(self, story: str, scene: str, root: Path, spec: dict) -> None:
        """Refresh scene and reference inputs before compiling a new render attempt."""
        plan = self.preview(story, scene, {})
        current_targets = [(item["target_id"], item["dependencies"]) for item in plan["targets"]]
        batch_targets = [(item["target_id"], item["dependencies"]) for item in spec["targets"]]
        if current_targets != batch_targets:
            raise ValueError("Target structure changed. Create a new batch for this scene.")
        snapshot_root = root / "snapshots" / uuid4().hex
        self._snapshot(story, scene, snapshot_root)
        atomic_copy(snapshot_root / "snapshot.json", root / "snapshot.json")

    def _archive(self, state: dict, target: str, reason: str) -> None:
        group = state["groups"][target]
        if group.get("attempt_id"):
            archived = {key: copy.deepcopy(value) for key, value in group.items() if key != "attempts"}
            archived.update(stale_reason=reason, ranking=copy.deepcopy(state["rankings"].get(target, {})),
                            selected_candidate_id=state["selected_views"].get(target, ""),
                            view_review=copy.deepcopy(state["view_reviews"].get(target, {})))
            group.setdefault("attempts", []).append(archived)
        group.update(candidates=[], status="PENDING", stale_reason=reason)
        for key in ("attempt_id", "prompt_path", "ir_path", "reference_images", "source_selections", "analysis", "analysis_history"):
            group.pop(key, None)
        state["selected_views"].pop(target, None)
        state["rankings"].pop(target, None)
        state.setdefault("view_reviews", {}).pop(target, None)

    def _invalidate_dependents(self, spec: dict, state: dict, target: str) -> None:
        affected = {target}
        for item in spec["targets"]:
            key = item["target_id"]
            if key != target and affected.intersection(item["dependencies"]):
                affected.add(key)
                self._withdraw(state["groups"][key])
                self._archive(state, key, f"The selected {target} image changed.")
        state.pop("publication", None)

    def _withdraw(self, group: dict) -> None:
        for item in group["candidates"]:
            if item.get("ask_id"):
                for task in self.proxy.task_paths("ask", "running", "answer"):
                    if task.name == item["ask_id"]:
                        supersede_task(Path(self.app.config.base_ai_queue_path), task, "Scene batch attempt superseded or stopped")

    def _harvest(self, group: dict) -> None:
        for candidate in group["candidates"]:
            if candidate["status"] == "SUBMITTING":
                # Recover the queue publication/state-write boundary after a restart.
                match = next((path for path in self.proxy.task_paths("ask", "running", "answer")
                              if (path / "ask_manifest.json").is_file() and _read(path / "ask_manifest.json").get("source_ask_id") == candidate["source_ask_id"]), None)
                if match:
                    candidate.update(status="QUEUED", ask_id=match.name)
                    candidate["render_attempts"][-1]["ask_id"] = match.name
                else:
                    candidate.update(status="FAILED", error="Submission was interrupted before queue publication. Retry this candidate.")
                    self._record_render_attempt(candidate)
            if candidate["status"] not in {"QUEUED", "RUNNING"}:
                continue
            ask_id = candidate["ask_id"]
            folder = self.proxy.answer_root() / ask_id
            if not (folder / "answer_manifest.json").is_file():
                if (self.proxy.running_root() / ask_id).is_dir():
                    candidate["status"] = "RUNNING"
                    self._record_render_attempt(candidate)
                continue
            try:
                ask, answer = _read(folder / "ask_manifest.json"), _read(folder / "answer_manifest.json")
                if (ask.get("source_ask_id") != candidate["source_ask_id"] or ask.get("ask_id") != ask_id
                        or answer.get("ask_id") != ask_id or ask.get("consumer") != "zet-scene-batches"):
                    raise ValueError("AI Proxy answer does not belong to this scene batch attempt.")
                if answer.get("status") in {"ERROR", "RETRY_LATER"}:
                    raise ValueError(answer.get("error_message") or "Local render failed.")
                if answer.get("status") != "SUCCESS":
                    continue
                name = answer.get("expected_output")
                if not name or Path(name).name != name:
                    raise ValueError("Invalid render output filename.")
                source = folder / name
                validate_image(source.read_bytes())
                atomic_copy(source, Path(candidate["image_path"]))
                candidate.update(status="COMPLETE", sha256=_hash(Path(candidate["image_path"])))
                write_json_atomic(folder / "harvest_manifest.json", {"consumer": "zet-scene-batches", "harvested_at": _now()})
            except Exception as exc:
                candidate.update(status="FAILED", error=str(exc))
            self._record_render_attempt(candidate)

    @staticmethod
    def _record_render_attempt(candidate):
        if candidate.get("render_attempts"):
            candidate["render_attempts"][-1].update(
                {key: candidate[key] for key in ("status", "error", "ask_id", "image_path", "sha256") if key in candidate},
                updated_at=_now())

    def detail(self, story: str, scene: str, run_id: str) -> dict:
        root = self.root(story, scene, run_id)
        with file_lock(root / "state.lock"):
            spec, state = _read(root / "spec.json"), _read(root / "state.json")
            selected = self._selected(state)
            for target, candidate_id in list(state["selected_views"].items()):
                if target not in selected:
                    state["selected_views"].pop(target)
                    state["groups"][target]["stale_reason"] = "Selected image is missing or altered."
                    self._invalidate_dependents(spec, state, target)
            for target, group in state["groups"].items():
                self._harvest(group)
                self._harvest_analysis(group)
                candidates = group["candidates"]
                if candidates and all(item["status"] in {"COMPLETE", "FAILED", "STOPPED"} for item in candidates):
                    if any(item["status"] == "COMPLETE" for item in candidates):
                        ranking = state["rankings"].get(target) or {}
                        if ranking.get("status") == "RUNNING" and ranking.get("job_id") not in _ACTIVE_REVIEWS:
                            ranking.update(status="FAILED", error="Rating was interrupted; re-evaluate this group.")
                        if not ranking:
                            job_id = uuid4().hex
                            state["rankings"][target] = {"status": "RUNNING", "job_id": job_id}
                            _ACTIVE_REVIEWS.add(job_id)
                            _REVIEWS.submit(self._rate, story, scene, run_id, target, group["attempt_id"], job_id)
                        group["status"] = ("SELECTED" if target in self._selected(state) else "AWAITING_HUMAN_SELECTION")
                        if state.get("publication", {}).get("status") == "COMPLETE" and target in self._selected(state):
                            group["status"] = "PUBLISHED"
                    else:
                        group["status"] = "FAILED"
            if state["stop_requested"]:
                state["status"] = "STOPPED"
            elif len(self._selected(state)) == len(spec["targets"]):
                state["status"] = "COMPLETE" if state.get("publication", {}).get("status") == "COMPLETE" else "READY_TO_PUBLISH"
            elif any(item["status"] in {"QUEUED", "RUNNING"} for group in state["groups"].values() for item in group["candidates"]):
                state["status"] = "RUNNING"
            elif any(group["status"] == "FAILED" for group in state["groups"].values()):
                state["status"] = "FAILED"
            else:
                state["status"] = "AWAITING_HUMAN_SELECTION" if any(g["candidates"] for g in state["groups"].values()) else "QUEUED"
            state["updated_at"] = _now()
            write_json_atomic(root / "state.json", state)
            result = {**spec, **state, "root": str(root)}
            result["candidates"] = [{**item, "view": target, "reference_images": group.get("reference_images", []),
                                     "prompt_path": group.get("prompt_path", "")}
                                    for target, group in state["groups"].items() for item in group["candidates"]]
            result["ready_targets"] = [item["target_id"] for item in spec["targets"]
                                       if set(item["dependencies"]) <= set(self._selected(state))
                                       and item["target_id"] not in state["selected_views"]]
            return result

    def _rate(self, story, scene, run_id, target, attempt, job_id):
        root = self.root(story, scene, run_id)
        try:
            with file_lock(root / "state.lock"):
                state = _read(root / "state.json")
                group = state["groups"][target]
                if group.get("attempt_id") != attempt:
                    raise ValueError("This rating attempt was superseded.")
                candidates = [item for item in group["candidates"] if item["status"] == "COMPLETE"]
            hashes = {item["candidate_id"]: _hash(Path(item["image_path"])) for item in candidates}
            if len(candidates) == 1:
                entries, model = [{"candidate_id": candidates[0]["candidate_id"], "reason": "Only completed image."}], "single-survivor"
            else:
                prompt = ("Rank every supplied scene candidate for prompt adherence, composition, visual continuity, "
                          "reference preservation and image quality. Explicitly check the exact required character count and identity of each character; "
                          "penalize duplicated or missing characters and unrequested background structures. Check each character's gaze direction and verify "
                          "that every dialogue line appears exactly as written, with a visible panel and pointer aimed at its speaker. State these checks in each reason. "
                          "References precede candidates. Human decisions are independent advice. "
                          f"Candidate IDs: {list(hashes)}\nExact submitted prompt:\n" + Path(group["prompt_path"]).read_text(encoding="utf-8"))
                entries, model = rank_images_with_luna(
                    project_root=self.project_root, model=self.app.config.codex_default_model, prompt=prompt,
                    candidate_ids=list(hashes), image_paths=[item["image_path"] for item in candidates],
                    reference_image_paths=[item["path"] for item in group.get("reference_images", [])],
                    executable=shutil.which("codex") or "codex")
            ranking = {"status": "COMPLETE", "entries": entries, "ordered_candidate_ids": [item["candidate_id"] for item in entries],
                       "luna_ordered_candidate_ids": [item["candidate_id"] for item in entries], "input_hashes": hashes, "model": model}
        except Exception as exc:
            ranking = {"status": "FAILED", "error": str(exc)}
        with file_lock(root / "state.lock"):
            state = _read(root / "state.json")
            if state["groups"][target].get("attempt_id") == attempt and state["rankings"].get(target, {}).get("job_id") == job_id:
                state["rankings"][target] = ranking
                write_json_atomic(root / "state.json", state)
        _ACTIVE_REVIEWS.discard(job_id)

    def action(self, story: str, scene: str, run_id: str, name: str, payload: dict) -> dict:
        root = self.root(story, scene, run_id)
        self.detail(story, scene, run_id)
        with file_lock(root / "state.lock"):
            spec, state = _read(root / "spec.json"), _read(root / "state.json")
            target = str(payload.get("target_id") or "main")
            if target not in state["groups"]:
                raise ValueError("Unknown scene target.")
            group = state["groups"][target]
            if name == "rename":
                spec["batch_name"] = str(payload.get("batch_name") or "").strip()
                write_json_atomic(root / "spec.json", spec)
            elif name == "stop":
                state["stop_requested"] = True
                for value in state["groups"].values():
                    self._withdraw(value)
                    for item in value["candidates"]:
                        if item["status"] in {"QUEUED", "RUNNING"}:
                            item["status"] = "STOPPED"
                            self._record_render_attempt(item)
            elif name in {"start", "resume", "render", "retry", "rerender", "compile", "recompile"}:
                state["stop_requested"] = False
                if name in {"start", "resume"}:
                    ready = [item["target_id"] for item in spec["targets"]
                             if set(item["dependencies"]) <= set(self._selected(state)) and item["target_id"] not in state["selected_views"]]
                    if not ready:
                        if len(self._selected(state)) == len(spec["views"]):
                            write_json_atomic(root / "state.json", state)
                            return self.detail(story, scene, run_id)
                        raise ValueError("Select prerequisite candidates before continuing.")
                    target, group = ready[0], state["groups"][ready[0]]
                if any(item["status"] in {"QUEUED", "RUNNING"} for item in group["candidates"]):
                    raise ValueError("This target is already rendering. Stop it before rerendering.")
                if name in {"start", "render"} and any(item["status"] == "COMPLETE" for item in group["candidates"]):
                    raise ValueError("Select a rated candidate before continuing, or rerender this group.")
                if name == "recompile":
                    plan = self.preview(story, scene, {})
                    if [(item["target_id"], item["dependencies"]) for item in plan["targets"]] != [(item["target_id"], item["dependencies"]) for item in spec["targets"]]:
                        raise ValueError("Target structure changed. Create a new batch for this scene.")
                    if any(item["status"] in {"QUEUED", "RUNNING"} for g in state["groups"].values() for item in g["candidates"]):
                        raise ValueError("Stop this batch before refreshing its source inputs.")
                    snapshot_root = root / "snapshots" / uuid4().hex
                    self._snapshot(story, scene, snapshot_root)
                    atomic_copy(snapshot_root / "snapshot.json", root / "snapshot.json")
                    for key in spec["views"]:
                        self._archive(state, key, "Scene inputs explicitly refreshed.")
                    state.pop("publication", None)
                    # Refresh resets selections; compile the first dependency-free target.
                    target = spec["views"][0]
                    group = state["groups"][target]
                    write_json_atomic(root / "state.json", state)
                elif name in {"start", "resume", "render", "rerender", "compile"}:
                    # Each newly compiled prompt must use the current Scene Builder data,
                    # story settings, prompt sections, and resolved reference images.
                    self._refresh_snapshot_for_render(story, scene, root, spec)
                if name in {"start", "resume", "render"} and group.get("attempt_id"):
                    self._archive(state, target, "Render started from current scene inputs.")
                    self._invalidate_dependents(spec, state, target)
                if name == "rerender":
                    self._withdraw(group)
                    self._archive(state, target, "Target rerendered.")
                    self._invalidate_dependents(spec, state, target)
                if name == "compile" and group.get("attempt_id"):
                    self._archive(state, target, "Prompt recompiled from saved batch inputs.")
                    self._invalidate_dependents(spec, state, target)
                if not group.get("attempt_id"):
                    self._compile(root, state, target)
                if name not in {"compile", "recompile"}:
                    self._queue(root, spec, state, target, retry=name in {"retry", "resume"},
                                candidate_id=str(payload.get("candidate_id") or "") if name == "retry" else "")
            elif name in {"select", "review", "move-rank"}:
                candidate_id = str(payload.get("candidate_id") or "")
                candidate = next((item for item in group["candidates"] if item["candidate_id"] == candidate_id), None)
                if name == "select" and not candidate_id:
                    state["selected_views"].pop(target, None)
                    self._invalidate_dependents(spec, state, target)
                elif not candidate:
                    raise ValueError("Choose a candidate from this target.")
                elif name == "review":
                    candidate["human_review"] = {"decision": normalize_human_decision(payload.get("decision"))}
                    if candidate["human_review"]["decision"] == "reject" and state["selected_views"].get(target) == candidate_id:
                        state["selected_views"].pop(target)
                        self._invalidate_dependents(spec, state, target)
                elif name == "move-rank":
                    state["rankings"][target] = adjust_candidate_ranking(state["rankings"].get(target, {}), candidate_id,
                                                                        payload.get("direction"), timestamp=_now())
                else:
                    ranking = state["rankings"].get(target, {})
                    if candidate["status"] != "COMPLETE" or not Path(candidate.get("image_path") or "").is_file() or ranking.get("status") != "COMPLETE" or ranking.get("input_hashes", {}).get(candidate_id) != _hash(Path(candidate["image_path"])):
                        raise ValueError("Wait for a current rating before selecting this image.")
                    if candidate.get("human_review", {}).get("decision") == "reject":
                        raise ValueError("A rejected candidate cannot be selected.")
                    if state["selected_views"].get(target) != candidate_id:
                        self._invalidate_dependents(spec, state, target)
                    state["selected_views"][target] = candidate_id
                    group["stale_reason"] = ""
            elif name == "reevaluate":
                state["rankings"].pop(target, None)
            elif name == "publish":
                self._publish(root, spec, state)
            else:
                raise ValueError("Unknown scene batch action.")
            write_json_atomic(root / "state.json", state)
        return self.detail(story, scene, run_id)

    def _queue(self, root, spec, state, target, retry=False, candidate_id=""):
        group = state["groups"][target]
        profile = require_qwen_profile(self.project_root, SCENE_PROFILE)
        definition = next(item for item in spec["targets"] if item["target_id"] == target)
        if candidate_id and not any(item["candidate_id"] == candidate_id and item["status"] in {"FAILED", "STOPPED"} for item in group["candidates"]):
            raise ValueError("Choose a failed or stopped candidate to retry.")
        self._validate_attempt_inputs(group)
        if not group["candidates"]:
            for ordinal in range(1, definition["count"] + 1):
                group["candidates"].append({"candidate_id": f"{target}-{ordinal:03d}", "seed": random.SystemRandom().randrange(2**63),
                                            "status": "PENDING", "human_review": {"decision": "undecided"}, "render_attempts": []})
        state["rankings"].pop(target, None)
        for item in group["candidates"]:
            if candidate_id and item["candidate_id"] != candidate_id:
                continue
            if item["status"] == "COMPLETE" or (item["status"] in {"FAILED", "STOPPED"} and not retry):
                continue
            attempt = uuid4().hex
            source_id = f"SceneBatch_{spec['run_id']}_{target}_{item['candidate_id']}_{attempt}"
            output = Path(group["prompt_path"]).parent / item["candidate_id"] / attempt
            item.update(status="SUBMITTING", source_ask_id=source_id, ask_id="", image_path=str(output / "candidate.png"), error="")
            item["render_attempts"].append({"source_ask_id": source_id, "seed": item["seed"], "created_at": _now()})
            self._record_render_attempt(item)
            write_json_atomic(root / "state.json", state)
            try:
                ask_path = self.app.ai_proxy_service.stage_render_task_local_render_ask(
                    {"ask_id": source_id, "pipeline": "Local-Scene", "pipeline_stage": "SCENE_BATCH_RENDER"},
                    Path(group["prompt_path"]), output, scene_render_ir_path=Path(group["ir_path"]),
                    allow_parallel=True, seed=item["seed"], checkpoint=profile["diffusion_model"],
                    render_preset=SCENE_PROFILE, image_generation="comfyui", reference_files=group["reference_images"],
                    consumer="zet-scene-batches")
                item.update(status="QUEUED", ask_id=ask_path.name, source_ask_id=source_id,
                            image_path=str(output / "candidate.png"), error="")
                item["render_attempts"][-1]["ask_id"] = ask_path.name
            except Exception as exc:
                item.update(status="FAILED", error=str(exc))
            self._record_render_attempt(item)
            write_json_atomic(root / "state.json", state)
        group["status"] = "RUNNING"

    def _publish(self, root, spec, state):
        selected = self._selected(state)
        if set(selected) != set(spec["views"]):
            raise ValueError("Select a current rated image for every target before publishing.")
        if any(state["rankings"].get(target, {}).get("status") != "COMPLETE"
               or state["rankings"][target].get("input_hashes", {}).get(value["candidate_id"]) != value["sha256"]
               for target, value in selected.items()):
            raise ValueError("Complete current ratings before publishing.")
        for target in spec["views"]:
            self._validate_attempt_inputs(state["groups"][target])
        snapshot = _read(root / "snapshot.json")
        changed = [path for path, digest in snapshot["sources"].items() if not Path(path).is_file() or _hash(Path(path)) != digest]
        current_scene = copy.deepcopy(self.story.load_scene_builder_data(spec["story_slug"], spec["scene_slug"]).data)
        current_sources = self.story._resolve_scene_element_sources(current_scene)
        if hashlib.sha256(json.dumps(current_sources, sort_keys=True).encode("utf-8")).hexdigest() != snapshot["resolved_material_hash"]:
            changed.append("Resolved element identity or source descriptions")
        if changed:
            raise ValueError("Source inputs changed. Create a new batch before publishing: " + ", ".join(changed))
        publication = state.setdefault("publication", {"status": "PUBLISHING", "targets": {}})
        with file_lock(self.targets.pipeline_path(spec["story_slug"], spec["scene_slug"], "main") / "Scene_Review.lock"):
            for target in spec["views"]:
                paths = self.targets.review_paths(spec["story_slug"], spec["scene_slug"], target)
                selection = selected[target]
                if publication["targets"].get(target) == selection["sha256"] and paths["locked"].is_file() and _hash(paths["locked"]) == selection["sha256"]:
                    continue
                atomic_copy(Path(selection["path"]), paths["candidate"])
                write_json_atomic(paths["candidate"].with_suffix(".render.json"), {
                    "image_sha256": selection["sha256"], "batch_id": spec["run_id"], "candidate_id": selection["candidate_id"],
                    "story_slug": spec["story_slug"], "scene_slug": spec["scene_slug"], "render_target_id": target,
                    "attempt_id": state["groups"][target]["attempt_id"],
                    "batch_render_input_hash": state["groups"][target]["render_input_hash"],
                    "prompt_sha256": state["groups"][target]["prompt_sha256"],
                    "render_input_hash": state["groups"][target]["render_input_hash"]})
                self.app.scene_image_review_service.promote(spec["story_slug"], spec["scene_slug"], target)
                publication["targets"][target] = selection["sha256"]
                write_json_atomic(root / "state.json", state)
        publication.update(status="COMPLETE", published_at=_now())
        invalidate_summary_cache()

    @staticmethod
    def _validate_attempt_inputs(group):
        artifacts = [(group["prompt_path"], group["prompt_sha256"]), (group["ir_path"], group["ir_sha256"])]
        artifacts.extend((reference["path"], reference["sha256"]) for reference in group["reference_images"])
        if any(not Path(path).is_file() or _hash(Path(path)) != digest for path, digest in artifacts):
            raise ValueError("Saved prompt, IR or reference images changed. Explicitly recompile before rendering or publishing.")

    def artifact(self, story, scene, run_id, target, kind, index="", attempt_id="") -> Path:
        root = self.root(story, scene, run_id)
        state = _read(root / "state.json")
        group = state["groups"].get(target)
        if group is None:
            raise ValueError("Unknown scene target.")
        if attempt_id and attempt_id != group.get("attempt_id"):
            group = next((item for item in group["attempts"] if item["attempt_id"] == attempt_id), None)
            if group is None:
                raise ValueError("Unknown scene attempt.")
        if kind == "prompt":
            path = Path(group.get("prompt_path") or "")
        elif kind == "reference":
            if not 0 <= int(index) < len(group["reference_images"]):
                raise ValueError("Unknown reference image.")
            path = Path(group["reference_images"][int(index)]["path"])
        elif kind == "image":
            path = Path(next(item for item in group["candidates"] if item["candidate_id"] == index)["image_path"])
        elif kind == "analysis":
            path = Path(group["analysis"]["result_path"])
        else:
            raise ValueError("Unknown batch artifact.")
        if not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("Batch artifact is unavailable.")
        return path

    def analyze_prompt(self, story, scene, run_id, target, second_opinion=False):
        root = self.root(story, scene, run_id)
        with file_lock(root / "state.lock"):
            state = _read(root / "state.json")
            group = state["groups"][target]
            if not group.get("prompt_path"):
                self._compile(root, state, target)
            self._validate_attempt_inputs(group)
            previous = group.get("analysis") or {}
            if previous.get("status") in {"QUEUED", "RUNNING"}:
                raise ValueError("Prompt analysis is already running.")
            if second_opinion and previous.get("status") != "COMPLETE":
                raise ValueError("Complete the primary analysis before requesting a second opinion.")
            ask_id = f"SceneBatchAnalysis_{run_id}_{target}_{uuid4().hex}"
            folder = self.proxy.file_proxy_client.create_staging(ask_id)
            result = Path(group["prompt_path"]).parent / f"{ask_id}.md"
            manifest = {"version": AI_PROXY_PROTOCOL_VERSION, "ask_id": ask_id, "worker_type": "ollama_generate",
                        "ollama_model": ScenePromptAnalysisService._alternate_model(self.app.config.ai_prompt_analysis_model)
                        if second_opinion else self.app.config.ai_prompt_analysis_model,
                        "prompt_file": "OLLAMA_PROMPT.md", "expected_output": "Analysis.md", "task_type": "scene_batch_prompt_analysis",
                        "consumer": "zet-scene-batches", "source_prompt_sha256": group["prompt_sha256"],
                        "batch_id": run_id, "render_target_id": target, "attempt_id": group["attempt_id"], "auxiliary": True}
            instructions = (self.project_root / self.app.config.ai_prompt_analysis_instructions_file).read_text(encoding="utf-8")
            prompt = Path(group["prompt_path"]).read_text(encoding="utf-8")
            request = (instructions.replace("{{FINAL_IMAGE_PROMPT}}", prompt) if "{{FINAL_IMAGE_PROMPT}}" in instructions
                       else instructions + "\n\nExact submitted Qwen image prompt:\n" + prompt)
            if second_opinion:
                request += "\n\nProvide an independent second opinion on this prior analysis:\n" + Path(previous["result_path"]).read_text(encoding="utf-8")
            (folder / "OLLAMA_PROMPT.md").write_text(request, encoding="utf-8")
            write_json_atomic(folder / "ask_manifest.json", manifest)
            group.setdefault("analysis_history", []).extend([previous] if previous else [])
            group["analysis"] = {"ask_id": ask_id, "prompt_sha256": group["prompt_sha256"], "attempt_id": group["attempt_id"],
                                 "batch_id": run_id, "render_target_id": target,
                                 "result_path": str(result), "status": "SUBMITTING", "second_opinion": second_opinion}
            write_json_atomic(root / "state.json", state)
            try:
                self.proxy.file_proxy_client.publish(folder, ask_id, "ollama_generate")
                group["analysis"]["status"] = "QUEUED"
            except Exception as exc:
                group["analysis"].update(status="FAILED", error=str(exc))
            write_json_atomic(root / "state.json", state)
        return self.detail(story, scene, run_id)

    def _harvest_analysis(self, group):
        record = group.get("analysis") or {}
        if record.get("status") == "SUBMITTING":
            published = any((folder / record["ask_id"]).is_dir() for folder in
                            (self.proxy.ask_root(), self.proxy.running_root(), self.proxy.answer_root()))
            if published:
                record["status"] = "QUEUED"
            else:
                record.update(status="FAILED", error="Prompt analysis submission was interrupted. Request analysis again.")
        if record.get("status") not in {"QUEUED", "RUNNING"}:
            return
        folder = self.proxy.answer_root() / record["ask_id"]
        if not (folder / "answer_manifest.json").is_file():
            return
        try:
            ask, answer = _read(folder / "ask_manifest.json"), _read(folder / "answer_manifest.json")
            if (answer.get("ask_id") != record["ask_id"] or ask.get("ask_id") != record["ask_id"]
                    or ask.get("batch_id") != record["batch_id"] or ask.get("render_target_id") != record["render_target_id"]
                    or ask.get("consumer") != "zet-scene-batches" or ask.get("source_prompt_sha256") != group["prompt_sha256"]
                    or ask.get("attempt_id") != group["attempt_id"]):
                raise ValueError("Prompt analysis belongs to a different attempt.")
            if answer.get("status") != "SUCCESS":
                raise ValueError(answer.get("error_message") or "Prompt analysis failed.")
            name = answer.get("expected_output")
            if not name or Path(name).name != name:
                raise ValueError("Invalid analysis filename.")
            atomic_copy(folder / name, Path(record["result_path"]))
            record["status"] = "COMPLETE"
            write_json_atomic(folder / "harvest_manifest.json", {"consumer": "zet-scene-batches"})
        except Exception as exc:
            record.update(status="FAILED", error=str(exc))

    def improvement(self, story, scene):
        from zet.services.local_prompt_improvement_service import LocalPromptImprovementService
        return LocalPromptImprovementService(SceneBatchAdapter(self, story, scene), "scene", self.project_root)


class SceneBatchAdapter:
    """Supply the existing observations/package workflow with dynamic scene views."""
    def __init__(self, service, story, scene):
        self.service, self.story, self.scene, self.app = service, story, scene, service.app

    def detail(self, run_id):
        return self.service.detail(self.story, self.scene, run_id)
