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
from tempfile import TemporaryDirectory
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
SLOT_COUNT = 8
INITIAL_SLOT_COUNT = 4


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
        for group in groups:
            group["count"] = SLOT_COUNT
            group["initial_count"] = INITIAL_SLOT_COUNT
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
                "targets": ordered, "slot_count": SLOT_COUNT,
                "initial_render_count": INITIAL_SLOT_COUNT}

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
        existing = self.list_runs(story, scene)
        if existing:
            return self.detail(story, scene, existing[0]["run_id"])
        plan = self.preview(story, scene, payload)
        story, scene = plan["story_slug"], plan["scene_slug"]
        run_id = uuid4().hex
        root = self.workspace(story, scene) / run_id
        root.mkdir(parents=True, exist_ok=False)
        snapshot_root = root / "snapshots" / uuid4().hex
        self._snapshot(story, scene, snapshot_root)
        atomic_copy(snapshot_root / "snapshot.json", root / "snapshot.json")
        spec = {"schema_version": 3, "kind": "scene", "run_id": run_id, "story_slug": story,
                "scene_slug": scene,
                "created_at": _now(), "views": [item["target_id"] for item in plan["targets"]], **plan}
        write_json_atomic(root / "spec.json", spec)
        write_json_atomic(root / "state.json", {"status": "QUEUED", "stop_requested": False,
                          "groups": {item["target_id"]: self._empty_group(item["target_id"])
                                     for item in plan["targets"]}, "selected_views": {}, "rankings": {}})
        return self.detail(story, scene, run_id)

    def list_runs(self, story: str, scene: str) -> list[dict]:
        workspace = self.workspace(story, scene)
        workspace.mkdir(parents=True, exist_ok=True)
        specs = list(workspace.glob("*/spec.json"))
        if not specs:
            return []
        # Reconcile the newest legacy batch in place while preserving older runs.
        specs.sort(key=lambda path: _read(path).get("created_at", ""), reverse=True)
        current = specs[0].parent
        spec, state = _read(current / "spec.json"), _read(current / "state.json")
        if int(spec.get("schema_version", 0) or 0) < 3:
            self._upgrade_legacy(story, scene, current, specs[1:])
        elif len(specs) > 1:
            # Keep older batch artifacts available for image selection and recovery.
            pass
        rows = []
        for path in workspace.glob("*/spec.json"):
            spec = _read(path)
            state = _read(path.parent / "state.json")
            rows.append({**spec, "status": state["status"]})
        return sorted(rows, key=lambda item: item["created_at"], reverse=True)[:1]

    def _upgrade_legacy(self, story: str, scene: str, root: Path, old_specs: list[Path]) -> None:
        spec_path, state_path = root / "spec.json", root / "state.json"
        with file_lock(root / "state.lock"):
            spec, state = _read(spec_path), _read(state_path)
            if spec.get("schema_version", 0) >= 3:
                return
            plan = self.preview(story, scene, {})
            for target, group in state.setdefault("groups", {}).items():
                attempts = group.get("attempts")
                if not isinstance(attempts, dict):
                    group["legacy_attempts"] = attempts or []
                    group["attempts"] = {}
                candidates = group.setdefault("candidates", [])
                slots = {}
                for ordinal, candidate in enumerate(candidates, 1):
                    candidate.setdefault("slot", min(ordinal, SLOT_COUNT))
                    candidate.setdefault("attempt_id", group.get("attempt_id", ""))
                    slots[str(candidate["slot"])] = candidate["candidate_id"]
                for ordinal in range(1, SLOT_COUNT + 1):
                    key = str(ordinal)
                    if key not in slots:
                        candidate_id = f"{target}-{ordinal:03d}"
                        if any(item.get("candidate_id") == candidate_id for item in candidates):
                            candidate_id = f"{candidate_id}-{uuid4().hex[:8]}"
                        candidate = {"candidate_id": candidate_id, "slot": ordinal,
                                     "seed": random.SystemRandom().randrange(2**63), "status": "EMPTY",
                                     "human_review": {"decision": "undecided"}}
                        candidates.append(candidate)
                        slots[key] = candidate_id
                group["active_slot_ids"] = slots
                group.setdefault("active", False)
                if group.get("attempt_id") and group.get("prompt_path") and group.get("ir_path"):
                    group["attempts"].setdefault(group["attempt_id"], {
                        key: group.get(key) for key in ("attempt_id", "prompt_path", "prompt_sha256", "ir_path",
                            "ir_sha256", "reference_images", "render_input_hash", "source_selections")
                    })
            self._reconcile_targets(spec, state, plan)
            spec["schema_version"] = 3
            write_json_atomic(state_path, state)
            write_json_atomic(spec_path, spec)
        # Prior candidate files, snapshots, prompts and older batches remain in place.

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
                    if any(candidate.get("ask_id") == ask_id for candidate in group["candidates"]):
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

    def _selected(self, state: dict, *, verify: bool = False) -> dict:
        selected = {}
        for target, candidate_id in state["selected_views"].items():
            group = state["groups"][target]
            candidate = next((item for item in group["candidates"] if item["candidate_id"] == candidate_id), {})
            path = Path(candidate.get("image_path") or "")
            if candidate.get("status") != "COMPLETE" or not path.is_file():
                continue
            expected_hash = str(candidate.get("sha256") or "")
            digest = _hash(path) if verify or not expected_hash else expected_hash
            if verify and expected_hash and digest != expected_hash:
                raise ValueError("A selected scene render image was changed after review.")
            selected[target] = {"path": str(path), "sha256": digest, "candidate_id": candidate_id}
        return selected

    def _compile(self, root: Path, state: dict, target: str) -> dict:
        """Compile a new immutable attempt from the currently saved scene inputs."""
        spec = _read(root / "spec.json")
        generation = uuid4().hex
        snapshot_root = root / "snapshots" / generation
        snapshot = self._snapshot(spec["story_slug"], spec["scene_slug"], snapshot_root)
        for reference in snapshot["references"]:
            if not Path(reference["path"]).is_file() or _hash(Path(reference["path"])) != reference["sha256"]:
                raise ValueError("A current scene reference is missing or altered.")
        selections = self._selected(state, verify=True)
        selections.pop(target, None)
        try:
            compiled = self.story.story_render_service.compile_batch_target(
                snapshot["scene"], snapshot["settings"], snapshot["sections"], snapshot["references"], target,
                selections)
        except Exception as exc:
            raise ValueError(str(exc)) from exc
        group = state["groups"][target]
        output = root / "targets" / target / generation
        output.mkdir(parents=True, exist_ok=False)
        prompt_path = output / "Qwen_Image_2_1_Prompt.md"
        prompt_path.write_text(compiled["prompt"], encoding="utf-8")
        write_json_atomic(output / "Scene_Render_IR.json", compiled["ir"])
        compiled["references"] = [{**item, "sha256": _hash(Path(item["path"]))} for item in compiled["references"]]
        write_json_atomic(output / "references.json", compiled["references"])
        attempt = {"attempt_id": generation, "prompt_path": str(prompt_path),
                   "ir_path": str(output / "Scene_Render_IR.json"),
                   "snapshot_path": str(snapshot_root / "snapshot.json"),
                   "reference_images": compiled["references"],
                   "prompt_sha256": _hash(prompt_path),
                   "ir_sha256": _hash(output / "Scene_Render_IR.json"),
                   "render_input_hash": compiled["render_input_hash"],
                   "source_selections": selections}
        group.setdefault("attempts", {})[generation] = attempt
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
                     render_input_hash=compiled["render_input_hash"], source_selections=selections,
                     status="COMPILED", stale_reason="")
        return group

    def preview_prompt(self, story: str, scene: str, run_id: str, target: str) -> str:
        """Compile the next prompt from saved scene inputs without changing a render attempt."""
        root = self.root(story, scene, run_id)
        with file_lock(root / "state.lock"):
            spec, state = _read(root / "spec.json"), _read(root / "state.json")
            plan = self.preview(story, scene, {})
            definition = next((item for item in plan["targets"] if item["target_id"] == target), None)
            if definition is None:
                raise ValueError("This target is no longer enabled in the saved scene.")
            selected = self._selected(state, verify=True)
            if not set(definition["dependencies"]) <= set(selected):
                raise ValueError("Select a completed image for each prerequisite target first.")
            selected.pop(target, None)
            with TemporaryDirectory(prefix="zet-scene-prompt-") as temporary:
                snapshot = self._snapshot(spec["story_slug"], spec["scene_slug"], Path(temporary))
                compiled = self.story.story_render_service.compile_batch_target(
                    snapshot["scene"], snapshot["settings"], snapshot["sections"], snapshot["references"],
                    target, selected)
                return compiled["prompt"]

    def _refresh_snapshot_for_render(self, story: str, scene: str, root: Path, spec: dict) -> None:
        """Reconcile active targets with the saved scene before the next render."""
        plan = self.preview(story, scene, {})
        _, state = _read(root / "spec.json"), _read(root / "state.json")
        self._reconcile_targets(spec, state, plan)
        write_json_atomic(root / "spec.json", spec)
        write_json_atomic(root / "state.json", state)

    @staticmethod
    def _empty_group(target: str) -> dict:
        candidates = [{"candidate_id": f"{target}-{ordinal:03d}", "slot": ordinal,
                       "seed": random.SystemRandom().randrange(2**63), "status": "EMPTY",
                       "human_review": {"decision": "undecided"}}
                      for ordinal in range(1, SLOT_COUNT + 1)]
        return {"status": "PENDING", "candidates": candidates, "revision": 0,
                "active_slot_ids": {str(item["slot"]): item["candidate_id"] for item in candidates},
                "attempts": {}, "active": True}

    def _reconcile_targets(self, spec: dict, state: dict, plan: dict) -> None:
        """Apply current target topology and ensure each target has eight slots."""
        active = {item["target_id"] for item in plan["targets"]}
        for target, group in state.setdefault("groups", {}).items():
            group["active"] = target in active
            group.setdefault("attempts", {})
            candidates = group.setdefault("candidates", [])
            slots = group.setdefault("active_slot_ids", {})
            for item in candidates:
                slot = str(item.get("slot") or "")
                if slot and slot not in slots:
                    slots[slot] = item["candidate_id"]
            for ordinal in range(1, SLOT_COUNT + 1):
                key = str(ordinal)
                if key not in slots:
                    candidate_id = f"{target}-{ordinal:03d}"
                    if any(item["candidate_id"] == candidate_id for item in candidates):
                        candidate_id = f"{target}-{ordinal:03d}-{uuid4().hex[:8]}"
                    candidate = {"candidate_id": candidate_id, "slot": ordinal,
                                 "seed": random.SystemRandom().randrange(2**63), "status": "EMPTY",
                                 "human_review": {"decision": "undecided"}}
                    candidates.append(candidate)
                    slots[key] = candidate_id
        for definition in plan["targets"]:
            target = definition["target_id"]
            if target not in state["groups"]:
                state["groups"][target] = self._empty_group(target)
            group = state["groups"][target]
            group["active"] = True
            group["label"] = definition.get("label") or target
            group["kind"] = definition.get("kind") or ""
            group["dependencies"] = list(definition.get("dependencies") or [])
            group.setdefault("attempts", {})
        spec.update(targets=plan["targets"], views=[item["target_id"] for item in plan["targets"]],
                    slot_count=SLOT_COUNT, initial_render_count=INITIAL_SLOT_COUNT)

    def _invalidate_dependents(self, spec: dict, state: dict, target: str) -> None:
        """Selections never erase candidates; dependent renders use selections at submission time."""
        return None

    def _withdraw(self, group: dict) -> None:
        for item in group["candidates"]:
            if item.get("ask_id"):
                for task in self.proxy.task_paths("ask", "running", "answer"):
                    if task.name == item["ask_id"]:
                        supersede_task(Path(self.app.config.base_ai_queue_path), task, "Scene batch attempt superseded or stopped")

    def _withdraw_pending_for_new_render(self, state: dict) -> None:
        queued = {task.name: task for task in self.proxy.task_paths("ask")}
        for group in state["groups"].values():
            for item in group["candidates"]:
                if item["status"] not in {"SUBMITTING", "QUEUED"}:
                    continue
                task = queued.get(item.get("ask_id"))
                if task is None:
                    continue
                supersede_task(Path(self.app.config.base_ai_queue_path), task, "Scene batch render replaced by a new render request")
                item["status"] = "STOPPED"
                if item.get("work_path"):
                    Path(item.pop("work_path")).unlink(missing_ok=True)

    def _discard_replaced_candidates(self, root: Path, state: dict) -> None:
        """Keep only the eight current slot records and remove replaced slot images."""
        for target, group in state["groups"].items():
            active_ids = set(group.get("active_slot_ids", {}).values())
            replaced = [item for item in group["candidates"] if item["candidate_id"] not in active_ids]
            for item in replaced:
                self._withdraw({"candidates": [item]})
                for key in ("image_path", "work_path"):
                    path = Path(item.get(key) or "")
                    if path.is_file() and path.resolve().is_relative_to(root.resolve()):
                        path.unlink()
                if state["selected_views"].get(target) == item["candidate_id"]:
                    state["selected_views"].pop(target, None)
                    state.pop("publication", None)
            group["candidates"] = sorted(
                (item for item in group["candidates"] if item["candidate_id"] in active_ids),
                key=lambda item: item["slot"])
            ranking = state["rankings"].get(target)
            if replaced and ranking and any(candidate_id not in active_ids
                                            for candidate_id in ranking.get("ordered_candidate_ids", [])):
                state["rankings"].pop(target, None)

    def _harvest(self, group: dict) -> None:
        for candidate in group["candidates"]:
            if candidate["status"] == "SUBMITTING":
                # Recover the queue publication/state-write boundary after a restart.
                match = next((path for path in self.proxy.task_paths("ask", "running", "answer")
                              if (path / "ask_manifest.json").is_file() and _read(path / "ask_manifest.json").get("source_ask_id") == candidate["source_ask_id"]), None)
                if match:
                    candidate.update(status="QUEUED", ask_id=match.name)
                else:
                    candidate.update(status="FAILED", error="Submission was interrupted before queue publication. Retry this candidate.")
            if candidate["status"] not in {"QUEUED", "RUNNING"}:
                continue
            ask_id = candidate["ask_id"]
            folder = self.proxy.answer_root() / ask_id
            if not (folder / "answer_manifest.json").is_file():
                if (self.proxy.running_root() / ask_id).is_dir():
                    candidate["status"] = "RUNNING"
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
                output = Path(candidate["work_path"])
                atomic_copy(source, output)
                atomic_copy(output, Path(candidate["image_path"]))
                output.unlink(missing_ok=True)
                candidate.update(status="COMPLETE", sha256=_hash(Path(candidate["image_path"])))
                write_json_atomic(folder / "harvest_manifest.json", {"consumer": "zet-scene-batches", "harvested_at": _now()})
            except Exception as exc:
                candidate.update(status="FAILED", error=str(exc))
            if candidate.get("work_path"):
                work_file = Path(candidate["work_path"])
                work_file.unlink(missing_ok=True)
                shutil.rmtree(work_file.parent.parent, ignore_errors=True)
            candidate.pop("work_path", None)

    def detail(self, story: str, scene: str, run_id: str, *, refresh_previews: bool = False) -> dict:
        root = self.root(story, scene, run_id)
        with file_lock(root / "state.lock"):
            spec, state = _read(root / "spec.json"), _read(root / "state.json")
            original_spec, original_state = copy.deepcopy(spec), copy.deepcopy(state)
            self._reconcile_targets(spec, state, self.preview(story, scene, {}))
            self._discard_replaced_candidates(root, state)
            state.pop("view_reviews", None)
            state.pop("prompt_improvement_migrated", None)
            selected = self._selected(state)
            preview_key = self._reference_preview_key(story, scene, state)
            if refresh_previews or state.get("reference_preview_key") != preview_key:
                if self._refresh_reference_previews(root, spec, state, selected):
                    state["reference_preview_key"] = preview_key
                else:
                    state.pop("reference_preview_key", None)
            for target, candidate_id in list(state["selected_views"].items()):
                if target not in selected:
                    state["selected_views"].pop(target, None)
            for target, group in state["groups"].items():
                self._harvest(group)
                self._harvest_analysis(group)
                active_ids = set(group.get("active_slot_ids", {}).values())
                candidates = [item for item in group["candidates"] if item["candidate_id"] in active_ids]
                active = any(item["status"] in {"SUBMITTING", "QUEUED", "RUNNING"} for item in candidates)
                if candidates and not active and any(item["status"] == "COMPLETE" for item in candidates):
                    if any(item["status"] == "COMPLETE" for item in candidates):
                        ranking = state["rankings"].get(target) or {}
                        if ranking.get("status") == "RUNNING" and ranking.get("job_id") not in _ACTIVE_REVIEWS:
                            ranking.update(status="FAILED", error="Rating was interrupted; re-evaluate this group.")
                        if not ranking:
                            job_id = uuid4().hex
                            state["rankings"][target] = {"status": "RUNNING", "job_id": job_id}
                            _ACTIVE_REVIEWS.add(job_id)
                            _REVIEWS.submit(self._rate, story, scene, run_id, target, group.get("revision", 0), job_id)
                        group["status"] = ("SELECTED" if target in selected else "AWAITING_HUMAN_SELECTION")
                        if state.get("publication", {}).get("status") == "COMPLETE" and target in selected:
                            decision = state["publication"].get("reviews", {}).get(target, {}).get("decision")
                            group["status"] = "CURRENT_LOCK_KEPT" if decision == "keep-current" else "PUBLISHED"
                elif not active and any(item["status"] == "FAILED" for item in candidates):
                    group["status"] = "FAILED"
                elif not active and not any(item["status"] == "COMPLETE" for item in candidates):
                    group["status"] = "COMPILED" if group.get("prompt_path") else "PENDING"
            if state["stop_requested"]:
                state["status"] = "STOPPED"
            elif all(target in selected for target in spec["views"]):
                state["status"] = "COMPLETE" if state.get("publication", {}).get("status") == "COMPLETE" else "READY_TO_PUBLISH"
            elif any(item["status"] in {"QUEUED", "RUNNING"} for group in state["groups"].values() for item in group["candidates"]):
                state["status"] = "RUNNING"
            elif any(group["status"] == "FAILED" for group in state["groups"].values()):
                state["status"] = "FAILED"
            else:
                state["status"] = "AWAITING_HUMAN_SELECTION" if any(
                    candidate["status"] == "COMPLETE" for group in state["groups"].values()
                    for candidate in group["candidates"]) else "QUEUED"
            if state != original_state or spec != original_spec:
                state["updated_at"] = _now()
            if state != original_state:
                write_json_atomic(root / "state.json", state)
            if spec != original_spec:
                write_json_atomic(root / "spec.json", spec)
            result = {**spec, **state, "root": str(root)}
            for group in result["groups"].values():
                active_ids = set(group.get("active_slot_ids", {}).values())
                group["active_candidates"] = [item for item in group["candidates"] if item["candidate_id"] in active_ids]
            result["candidates"] = [{**item, "view": target,
                                     "reference_images": group.get("attempts", {}).get(item.get("attempt_id"), group).get("reference_images", []),
                                     "prompt_path": group.get("attempts", {}).get(item.get("attempt_id"), group).get("prompt_path", "")}
                                    for target, group in state["groups"].items() for item in group["candidates"]]
            result["ready_targets"] = [item["target_id"] for item in spec["targets"]
                                       if set(item["dependencies"]) <= set(selected)
                                       and item["target_id"] not in state["selected_views"]]
            return result

    def _reference_preview_key(self, story: str, scene: str, state: dict) -> str:
        builder_path = self.story.scene_builder_json_path(story, scene)
        try:
            builder_stat = builder_path.stat()
            builder_signature = (builder_stat.st_size, builder_stat.st_mtime_ns)
        except OSError:
            builder_signature = None
        selected_signatures = []
        for target, candidate_id in sorted(state.get("selected_views", {}).items()):
            group = state.get("groups", {}).get(target, {})
            candidate = next((item for item in group.get("candidates", [])
                              if item.get("candidate_id") == candidate_id), {})
            path = Path(candidate.get("image_path") or "")
            try:
                image_stat = path.stat()
                image_signature = (image_stat.st_size, image_stat.st_mtime_ns)
            except OSError:
                image_signature = None
            selected_signatures.append((target, candidate_id, image_signature))
        return json.dumps((builder_signature, selected_signatures), separators=(",", ":"))

    def _refresh_reference_previews(self, root: Path, spec: dict, state: dict, selected: dict) -> bool:
        """Expose the saved references that would feed each target's next render."""
        complete = True
        document = self.story.load_scene_builder_data(spec["story_slug"], spec["scene_slug"])
        scene = copy.deepcopy(document.data)
        scene.setdefault("scene", {})["_story_slug"] = spec["story_slug"]
        statuses = {target: {"locked_exists": True, "locked_current": True, "locked_image_path": value["path"]}
                    for target, value in selected.items()}
        for definition in spec["targets"]:
            target = definition["target_id"]
            try:
                projected = (self.targets.project_main(scene, statuses) if target == "main"
                             else self.targets.project_subscene(scene, target))
                preview_source = re.sub(r"\{\{SCENE_RENDER:[^}]+\}\}", "", json.dumps(projected))
                references = self.story.story_reference_service.resolve_scene_references("\n" + preview_source)
                bindings = {item.get("tag"): item for item in references if item.get("tag")}
                for dependency in definition.get("dependencies", []):
                    source = selected.get(dependency)
                    if source:
                        tag = self.targets.image_tag(spec["story_slug"], spec["scene_slug"], dependency)
                        bindings[tag] = {**source, "tag": tag, "label": self.targets.target_label(scene, dependency),
                                         "kind": "scene-render"}
                preview_dir = root / "reference-previews" / target
                preview_dir.mkdir(parents=True, exist_ok=True)
                previews = []
                previous_by_source = {
                    str(item.get("source_path") or ""): item
                    for item in state["groups"].get(target, {}).get("next_reference_images", [])
                }
                for index, reference in enumerate(bindings.values(), 1):
                    source = Path(str(reference.get("path") or ""))
                    if not source.is_file():
                        continue
                    source_stat = source.stat()
                    source_key = str(source.resolve())
                    previous_preview = previous_by_source.get(source_key)
                    source_signature = (source_stat.st_size, source_stat.st_mtime_ns)
                    if previous_preview and (
                        previous_preview.get("source_size"), previous_preview.get("source_mtime_ns")
                    ) == source_signature:
                        digest = str(previous_preview.get("sha256") or "")
                    else:
                        digest = _hash(source)
                    destination = preview_dir / f"{index:03d}_{digest[:16]}{source.suffix or '.png'}"
                    destination_stat = destination.stat() if destination.is_file() else None
                    previous_destination_matches = bool(
                        previous_preview
                        and previous_preview.get("path") == str(destination)
                        and destination_stat
                        and (previous_preview.get("preview_size"), previous_preview.get("preview_mtime_ns"))
                        == (destination_stat.st_size, destination_stat.st_mtime_ns)
                    )
                    if not previous_destination_matches and (
                        not destination_stat or _hash(destination) != digest
                    ):
                        atomic_copy(source, destination)
                        destination_stat = destination.stat()
                    previews.append({
                        **reference,
                        "path": str(destination),
                        "source_path": source_key,
                        "sha256": digest,
                        "source_size": source_stat.st_size,
                        "source_mtime_ns": source_stat.st_mtime_ns,
                        "preview_size": destination_stat.st_size if destination_stat else 0,
                        "preview_mtime_ns": destination_stat.st_mtime_ns if destination_stat else 0,
                        "image_index": index,
                    })
                keep = {Path(item["path"]).resolve() for item in previews}
                for previous in preview_dir.iterdir():
                    if previous.is_file() and previous.resolve() not in keep:
                        previous.unlink(missing_ok=True)
                state["groups"][target]["next_reference_images"] = previews
            except Exception:
                complete = False
                # Keep page loading available when a saved source is temporarily unavailable;
                # submission validates and reports actual missing/unsupported inputs.
                state["groups"][target]["next_reference_images"] = []
        return complete

    def _rate(self, story, scene, run_id, target, revision, job_id):
        root = self.root(story, scene, run_id)
        try:
            with file_lock(root / "state.lock"):
                state = _read(root / "state.json")
                group = state["groups"][target]
                if group.get("revision", 0) != revision:
                    raise ValueError("This rating attempt was superseded.")
                attempt_id = group.get("attempt_id")
                candidates = [item for item in group["candidates"]
                              if item["status"] == "COMPLETE" and item.get("attempt_id") == attempt_id]
            hashes = {item["candidate_id"]: _hash(Path(item["image_path"])) for item in candidates}
            if len(candidates) == 1:
                entries, model = [{"candidate_id": candidates[0]["candidate_id"], "reason": "Only completed image."}], "single-survivor"
            else:
                attempt = group.get("attempts", {}).get(attempt_id, group)
                prompt = ("Rank every supplied scene candidate for prompt adherence, composition, visual continuity, "
                          "reference preservation and image quality. Explicitly check the exact required character count and identity of each character; "
                          "penalize duplicated or missing characters and unrequested background structures. Check each character's gaze direction and verify "
                          "that every dialogue line appears exactly as written, with a visible panel and pointer aimed at its speaker. State these checks in each reason. "
                          "References precede candidates. Human decisions are independent advice. "
                          f"Candidate IDs: {list(hashes)}\nExact submitted prompt:\n" + Path(attempt["prompt_path"]).read_text(encoding="utf-8"))
                entries, model = rank_images_with_luna(
                    project_root=self.project_root, model=self.app.config.codex_default_model, prompt=prompt,
                    candidate_ids=list(hashes), image_paths=[item["image_path"] for item in candidates],
                    reference_image_paths=[item["path"] for item in attempt.get("reference_images", [])],
                    executable=shutil.which("codex") or "codex")
            ranking = {"status": "COMPLETE", "entries": entries, "ordered_candidate_ids": [item["candidate_id"] for item in entries],
                       "luna_ordered_candidate_ids": [item["candidate_id"] for item in entries], "input_hashes": hashes, "model": model}
        except Exception as exc:
            ranking = {"status": "FAILED", "error": str(exc)}
        with file_lock(root / "state.lock"):
            state = _read(root / "state.json")
            if state["groups"][target].get("revision", 0) == revision and state["rankings"].get(target, {}).get("job_id") == job_id:
                state["rankings"][target] = ranking
                write_json_atomic(root / "state.json", state)
        _ACTIVE_REVIEWS.discard(job_id)

    def action(self, story: str, scene: str, run_id: str, name: str, payload: dict) -> dict:
        root = self.root(story, scene, run_id)
        self.detail(story, scene, run_id)
        with file_lock(root / "state.lock"):
            spec, state = _read(root / "spec.json"), _read(root / "state.json")
            self._reconcile_targets(spec, state, self.preview(story, scene, {}))
            target = str(payload.get("target_id") or "main")
            if target not in state["groups"]:
                raise ValueError("Unknown scene target.")
            group = state["groups"][target]
            if name == "stop":
                state["stop_requested"] = True
                for value in state["groups"].values():
                    self._withdraw(value)
                    for item in value["candidates"]:
                        if item["status"] in {"SUBMITTING", "QUEUED", "RUNNING"}:
                            item["status"] = "STOPPED"
                            Path(item.get("work_path") or "").unlink(missing_ok=True) if item.get("work_path") else None
                            item.pop("work_path", None)
            elif name in {"start", "resume", "render", "fill", "retry", "rerender", "compile", "recompile"}:
                state["stop_requested"] = False
                if name in {"start", "resume"}:
                    ready = [item["target_id"] for item in spec["targets"]
                             if set(item["dependencies"]) <= set(self._selected(state))
                             and item["target_id"] not in state["selected_views"]]
                    if not ready:
                        if all(item["target_id"] in self._selected(state) for item in spec["targets"]):
                            write_json_atomic(root / "spec.json", spec)
                            write_json_atomic(root / "state.json", state)
                            return self.detail(story, scene, run_id)
                        raise ValueError("Select a completed image for each prerequisite target first.")
                    target, group = ready[0], state["groups"][ready[0]]
                definition = next((item for item in spec["targets"] if item["target_id"] == target), None)
                if definition is None:
                    raise ValueError("This target is no longer enabled in the saved scene.")
                if not set(definition["dependencies"]) <= set(self._selected(state)):
                    raise ValueError("Select a completed image for each prerequisite target first.")
                if name in {"compile", "recompile"}:
                    group["revision"] = int(group.get("revision", 0)) + 1
                    self._compile(root, state, target)
                else:
                    requested_slot = None
                    if name == "retry":
                        candidate_id = str(payload.get("candidate_id") or "")
                        candidate = next((item for item in group["candidates"]
                                          if item["candidate_id"] == candidate_id), None)
                        if candidate is None:
                            raise ValueError("Choose a candidate to retry.")
                        if candidate["status"] in {"SUBMITTING", "QUEUED", "RUNNING"}:
                            raise ValueError("This candidate is already rendering.")
                        requested_slot = int(candidate.get("slot") or 1)
                        slot_numbers = [requested_slot]
                    elif name == "rerender":
                        slot_numbers = list(range(1, SLOT_COUNT + 1))
                    elif name == "fill":
                        slot_numbers = [int(slot) for slot, candidate_id in group["active_slot_ids"].items()
                                        if next((item for item in group["candidates"]
                                                 if item["candidate_id"] == candidate_id), {}).get("status") == "EMPTY"]
                    elif name == "resume":
                        slot_numbers = [int(slot) for slot, candidate_id in group["active_slot_ids"].items()
                                        if next((item for item in group["candidates"]
                                                 if item["candidate_id"] == candidate_id), {}).get("status")
                                        in {"EMPTY", "STOPPED", "FAILED"}]
                    else:
                        slot_numbers = list(range(1, INITIAL_SLOT_COUNT + 1))
                    if not slot_numbers:
                        raise ValueError("There are no empty render slots to fill." if name == "fill"
                                         else "There are no unfinished render slots to resume.")
                    had_attempt = bool(group.get("attempt_id"))
                    group["revision"] = int(group.get("revision", 0)) + 1
                    self._compile(root, state, target)
                    if name in {"render", "rerender"}:
                        self._withdraw_pending_for_new_render(state)
                    attempt_id = group["attempt_id"]
                    candidate_ids = self._activate_attempt_slots(
                        group, target, slot_numbers, attempt_id, force_new=had_attempt or name in {"retry", "rerender"})
                    self._discard_replaced_candidates(root, state)
                    state["rankings"].pop(target, None)
                    self._queue(root, spec, state, target, candidate_ids=candidate_ids)
            elif name in {"select", "review", "move-rank"}:
                candidate_id = str(payload.get("candidate_id") or "")
                candidate = next((item for item in group["candidates"] if item["candidate_id"] == candidate_id), None)
                if name == "select" and not candidate_id:
                    state["selected_views"].pop(target, None)
                    state.pop("publication", None)
                elif not candidate:
                    raise ValueError("Choose a candidate from this target.")
                elif name == "review":
                    decision = normalize_human_decision(payload.get("decision"))
                    candidate["human_review"] = {"decision": decision}
                elif name == "move-rank":
                    state["rankings"][target] = adjust_candidate_ranking(state["rankings"].get(target, {}), candidate_id,
                                                                        payload.get("direction"), timestamp=_now())
                else:
                    image_path = Path(candidate.get("image_path") or "")
                    if candidate["status"] != "COMPLETE" or not image_path.is_file():
                        raise ValueError("Choose a completed image that is still available.")
                    expected_hash = str(candidate.get("sha256") or "")
                    if expected_hash and _hash(image_path) != expected_hash:
                        raise ValueError("The completed image was changed after rendering.")
                    if state["selected_views"].get(target) != candidate_id:
                        state.pop("publication", None)
                    state["selected_views"][target] = candidate_id
            elif name == "clear":
                candidate_id = str(payload.get("candidate_id") or "")
                slot = next((item for item in group["candidates"] if item["candidate_id"] == candidate_id), None)
                if slot is None:
                    raise ValueError("Choose a slot to clear.")
                self._withdraw({"candidates": [slot]})
                old_path = Path(slot.get("image_path") or "")
                if old_path.is_file():
                    old_path.unlink()
                work_path = Path(slot.get("work_path") or "")
                if work_path.is_file():
                    work_path.unlink()
                if slot.get("work_path"):
                    shutil.rmtree(work_path.parent.parent, ignore_errors=True)
                slot.update(status="CLEARED", human_review={"decision": "undecided"})
                for key in ("image_path", "sha256", "work_path", "ask_id", "source_ask_id", "error"):
                    slot.pop(key, None)
                if group["active_slot_ids"].get(str(slot.get("slot"))) == candidate_id:
                    replacement_id = f"{target}-{int(slot.get('slot') or 1):03d}-{uuid4().hex[:8]}"
                    replacement = {"candidate_id": replacement_id, "slot": int(slot.get("slot") or 1),
                                   "seed": random.SystemRandom().randrange(2**63), "status": "EMPTY",
                                   "human_review": {"decision": "undecided"}}
                    group["candidates"].append(replacement)
                    group["active_slot_ids"][str(replacement["slot"])] = replacement_id
                self._discard_replaced_candidates(root, state)
                group["revision"] = int(group.get("revision", 0)) + 1
                state["rankings"].pop(target, None)
                if state["selected_views"].get(target) == candidate_id:
                    state["selected_views"].pop(target, None)
                    state.pop("publication", None)
            elif name == "reevaluate":
                state["rankings"].pop(target, None)
            elif name == "publish":
                self._publish(root, spec, state, payload.get("reviews"))
            else:
                raise ValueError("Unknown scene batch action.")
            write_json_atomic(root / "spec.json", spec)
            write_json_atomic(root / "state.json", state)
        return self.detail(story, scene, run_id, refresh_previews=name in {
            "start", "resume", "render", "fill", "retry", "rerender", "compile", "recompile",
        })

    @staticmethod
    def _activate_attempt_slots(group: dict, target: str, slot_numbers: list[int], attempt_id: str,
                                *, force_new: bool) -> list[str]:
        candidates = group["candidates"]
        ids = []
        for ordinal in slot_numbers:
            key = str(ordinal)
            current_id = group["active_slot_ids"].get(key)
            current = next((item for item in candidates if item["candidate_id"] == current_id), None)
            if force_new or current is None or current.get("status") != "EMPTY" or current.get("attempt_id"):
                candidate_id = f"{target}-{ordinal:03d}-{attempt_id[:8]}"
                suffix = 2
                while any(item["candidate_id"] == candidate_id for item in candidates):
                    candidate_id = f"{target}-{ordinal:03d}-{attempt_id[:8]}-{suffix}"
                    suffix += 1
                current = {"candidate_id": candidate_id, "slot": ordinal,
                           "seed": random.SystemRandom().randrange(2**63), "status": "EMPTY",
                           "human_review": {"decision": "undecided"}}
                candidates.append(current)
                group["active_slot_ids"][key] = candidate_id
            current.update(attempt_id=attempt_id, status="EMPTY")
            ids.append(current["candidate_id"])
        return ids

    def _queue(self, root, spec, state, target, *, candidate_ids, allow_retry=False):
        group = state["groups"][target]
        profile = require_qwen_profile(self.project_root, SCENE_PROFILE)
        attempt = group.get("attempts", {}).get(group.get("attempt_id"), group)
        self._validate_attempt_inputs(attempt)
        state["rankings"].pop(target, None)
        selected_ids = set(candidate_ids)
        if not selected_ids:
            raise ValueError("No render slots were selected.")
        for item in group["candidates"]:
            if item["candidate_id"] not in selected_ids:
                continue
            if item["status"] == "COMPLETE" and not allow_retry:
                continue
            if item["status"] in {"QUEUED", "RUNNING", "SUBMITTING"}:
                continue
            item["seed"] = random.SystemRandom().randrange(2**63)
            render_attempt_id = uuid4().hex
            source_id = f"SceneSlot_{spec['run_id']}_{target}_{item['candidate_id']}_{render_attempt_id}"
            slot_path = root / "slots" / target / f"{item['candidate_id']}.png"
            output = root / "rendering" / target / item["candidate_id"] / render_attempt_id
            output.mkdir(parents=True, exist_ok=True)
            item.update(status="SUBMITTING", source_ask_id=source_id, ask_id="", image_path=str(slot_path),
                        work_path=str(output / "candidate.png"), error="")
            item["human_review"] = {"decision": "undecided"}
            write_json_atomic(root / "state.json", state)
            try:
                ask_path = self.app.ai_proxy_service.stage_render_task_local_render_ask(
                    {"ask_id": source_id, "pipeline": "Local-Scene", "pipeline_stage": "SCENE_BATCH_RENDER"},
                    Path(attempt["prompt_path"]), output, scene_render_ir_path=Path(attempt["ir_path"]),
                    allow_parallel=True, seed=item["seed"], checkpoint=profile["diffusion_model"],
                    render_preset=SCENE_PROFILE, image_generation="comfyui", reference_files=attempt["reference_images"],
                    consumer="zet-scene-batches")
                item.update(status="QUEUED", ask_id=ask_path.name, source_ask_id=source_id,
                            image_path=str(slot_path), error="")
            except Exception as exc:
                item.update(status="FAILED", error=str(exc))
            write_json_atomic(root / "state.json", state)
        group["status"] = "RUNNING"

    def publication_review(self, story: str, scene: str, run_id: str) -> dict:
        """Capture the selected candidates and current locks for a human comparison."""
        self.detail(story, scene, run_id)
        root = self.root(story, scene, run_id)
        with file_lock(root / "state.lock"):
            spec, state = _read(root / "spec.json"), _read(root / "state.json")
            selected = self._selected(state, verify=True)
            if not all(target in selected for target in spec["views"]):
                raise ValueError("Select an available image for every active target before publishing.")
            targets = []
            with file_lock(self.targets.pipeline_path(story, scene, "main") / "Scene_Review.lock"):
                for definition in spec["targets"]:
                    target = definition["target_id"]
                    locked = self.targets.review_paths(story, scene, target)["locked"]
                    targets.append({"target_id": target, "label": definition["label"],
                                    "candidate_id": selected[target]["candidate_id"],
                                    "candidate_sha256": selected[target]["sha256"],
                                    "locked_sha256": _hash(locked) if locked.is_file() else "",
                                    "locked_exists": locked.is_file()})
            return {"run_id": run_id, "targets": targets}

    def _publish(self, root, spec, state, reviews=None):
        all_selected = self._selected(state, verify=True)
        selected = {target: all_selected[target] for target in spec["views"] if target in all_selected}
        if set(selected) != set(spec["views"]):
            raise ValueError("Select an available image for every active target before publishing.")
        publication = state.setdefault("publication", {"status": "PUBLISHING", "targets": {}})
        with file_lock(self.targets.pipeline_path(spec["story_slug"], spec["scene_slug"], "main") / "Scene_Review.lock"):
            # Validate every comparison before replacing any image. Retrying a committed
            # target uses its recorded outcome so an interrupted publication is recoverable.
            decisions = {}
            if reviews is not None:
                if not isinstance(reviews, dict) or set(reviews) != set(spec["views"]):
                    raise ValueError("Review every active target before publishing.")
            for target in spec["views"]:
                selection = selected[target]
                locked = self.targets.review_paths(spec["story_slug"], spec["scene_slug"], target)["locked"]
                digest = _hash(locked) if locked.is_file() else ""
                outcome = publication.get("reviews", {}).get(target, {})
                committed = (publication["targets"].get(target) == selection["sha256"]
                             and digest == outcome.get("result_sha256", selection["sha256"]))
                if committed:
                    continue
                review = reviews.get(target, {}) if reviews is not None else {}
                decision = review.get("decision", "promote")
                if decision not in {"promote", "keep-current"}:
                    raise ValueError("Choose whether to promote the candidate or keep the current locked image.")
                if reviews is not None:
                    if (review.get("candidate_id") != selection["candidate_id"]
                            or review.get("candidate_sha256") != selection["sha256"]
                            or review.get("locked_sha256") != digest):
                        raise ValueError("Scene images changed after comparison. Reopen the publication review.")
                elif digest:
                    raise ValueError("Compare the candidate with the current locked image before publishing.")
                if decision == "keep-current" and not digest:
                    raise ValueError("There is no current locked image to keep.")
                decisions[target] = (decision, digest)
            for target in spec["views"]:
                paths = self.targets.review_paths(spec["story_slug"], spec["scene_slug"], target)
                selection = selected[target]
                if target not in decisions:
                    continue
                decision, digest = decisions[target]
                candidate = next(item for item in state["groups"][target]["candidates"]
                                 if item["candidate_id"] == selection["candidate_id"])
                if decision == "keep-current":
                    candidate["human_review"] = {"decision": "reject"}
                    publication.setdefault("reviews", {})[target] = {
                        "decision": decision, "candidate_id": selection["candidate_id"], "result_sha256": digest}
                    publication["targets"][target] = selection["sha256"]
                    write_json_atomic(root / "state.json", state)
                    continue
                attempt = state["groups"][target].get("attempts", {}).get(candidate.get("attempt_id"),
                                                                              state["groups"][target])
                atomic_copy(Path(selection["path"]), paths["candidate"])
                write_json_atomic(paths["candidate"].with_suffix(".render.json"), {
                    "image_sha256": selection["sha256"], "batch_id": spec["run_id"], "candidate_id": selection["candidate_id"],
                    "story_slug": spec["story_slug"], "scene_slug": spec["scene_slug"], "render_target_id": target,
                    "attempt_id": candidate.get("attempt_id") or attempt.get("attempt_id", ""),
                    "batch_render_input_hash": attempt.get("render_input_hash", ""),
                    "prompt_sha256": attempt.get("prompt_sha256", ""),
                    "render_input_hash": attempt.get("render_input_hash", "")})
                self.app.scene_image_review_service.promote(spec["story_slug"], spec["scene_slug"], target,
                                                            preserve_previous=True)
                candidate["human_review"] = {"decision": "keep"}
                publication.setdefault("reviews", {})[target] = {
                    "decision": decision, "candidate_id": selection["candidate_id"],
                    "result_sha256": selection["sha256"]}
                publication["targets"][target] = selection["sha256"]
                write_json_atomic(root / "state.json", state)
        publication.update(status="COMPLETE", published_at=_now())
        invalidate_summary_cache()

    @staticmethod
    def _validate_attempt_inputs(attempt):
        artifacts = [(attempt["prompt_path"], attempt["prompt_sha256"]), (attempt["ir_path"], attempt["ir_sha256"])]
        artifacts.extend((reference["path"], reference["sha256"]) for reference in attempt["reference_images"])
        if any(not Path(path).is_file() or _hash(Path(path)) != digest for path, digest in artifacts):
            raise ValueError("The saved render-attempt inputs are missing or altered.")

    def artifact(self, story, scene, run_id, target, kind, index="", attempt_id="") -> Path:
        root = self.root(story, scene, run_id)
        state = _read(root / "state.json")
        group = state["groups"].get(target)
        if group is None:
            raise ValueError("Unknown scene target.")
        attempts = group.get("attempts", {})
        if attempt_id and attempt_id not in attempts and attempt_id != group.get("attempt_id"):
            raise ValueError("Unknown scene render prompt.")
        attempt = attempts.get(attempt_id, group) if attempt_id else group
        if kind == "prompt":
            path = Path(attempt.get("prompt_path") or "")
        elif kind == "reference":
            references = attempt.get("reference_images", [])
            if not 0 <= int(index) < len(references):
                raise ValueError("Unknown reference image.")
            path = Path(references[int(index)]["path"])
        elif kind == "next-reference":
            references = group.get("next_reference_images", [])
            if not 0 <= int(index) < len(references):
                raise ValueError("Unknown current reference image.")
            path = Path(references[int(index)]["path"])
        elif kind == "locked":
            path = self.targets.review_paths(story, scene, target)["locked"]
            # This canonical path is computed by the target service, rather than
            # read from batch state, and intentionally lives outside the batch root.
            if not path.is_file():
                raise ValueError("The current locked image is unavailable.")
            return path
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
            self._reconcile_targets(_read(root / "spec.json"), state, self.preview(story, scene, {}))
            self._compile(root, state, target)
            attempt = group.get("attempts", {}).get(group.get("attempt_id"), group)
            self._validate_attempt_inputs(attempt)
            previous = group.get("analysis") or {}
            if previous.get("status") in {"QUEUED", "RUNNING"}:
                raise ValueError("Prompt analysis is already running.")
            if second_opinion and previous.get("status") != "COMPLETE":
                raise ValueError("Complete the primary analysis before requesting a second opinion.")
            ask_id = f"SceneBatchAnalysis_{run_id}_{target}_{uuid4().hex}"
            folder = self.proxy.file_proxy_client.create_staging(ask_id)
            result = Path(attempt["prompt_path"]).parent / f"{ask_id}.md"
            manifest = {"version": AI_PROXY_PROTOCOL_VERSION, "ask_id": ask_id, "worker_type": "ollama_generate",
                        "ollama_model": ScenePromptAnalysisService._alternate_model(self.app.config.ai_prompt_analysis_model)
                        if second_opinion else self.app.config.ai_prompt_analysis_model,
                        "prompt_file": "OLLAMA_PROMPT.md", "expected_output": "Analysis.md", "task_type": "scene_batch_prompt_analysis",
                        "consumer": "zet-scene-batches", "source_prompt_sha256": attempt["prompt_sha256"],
                        "batch_id": run_id, "render_target_id": target, "attempt_id": group["attempt_id"], "auxiliary": True}
            instructions = (self.project_root / self.app.config.ai_prompt_analysis_instructions_file).read_text(encoding="utf-8")
            prompt = Path(attempt["prompt_path"]).read_text(encoding="utf-8")
            request = (instructions.replace("{{FINAL_IMAGE_PROMPT}}", prompt) if "{{FINAL_IMAGE_PROMPT}}" in instructions
                       else instructions + "\n\nExact submitted Qwen image prompt:\n" + prompt)
            if second_opinion:
                request += "\n\nProvide an independent second opinion on this prior analysis:\n" + Path(previous["result_path"]).read_text(encoding="utf-8")
            (folder / "OLLAMA_PROMPT.md").write_text(request, encoding="utf-8")
            write_json_atomic(folder / "ask_manifest.json", manifest)
            if previous.get("result_path"):
                Path(previous["result_path"]).unlink(missing_ok=True)
            group["analysis"] = {"ask_id": ask_id, "prompt_sha256": attempt["prompt_sha256"], "attempt_id": group["attempt_id"],
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
