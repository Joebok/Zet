"""Stable render positions; candidate identities and frozen inputs outlive slots."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import random
import shutil
import time
import threading
from typing import Any
from uuid import uuid4
from zet.services.library_reference_service import pipeline_library_root_for_path, write_library_json

SLOT_COUNT = 8
ASSEMBLY_INPUT_VERSION = 1
_SLOT_WORKERS: set[str] = set()
_SLOT_WORKERS_LOCK = threading.Lock()


class RenderSlotConflict(ValueError):
    pass


def render_count(value: Any, default: int = 1) -> int:
    value = default if value is None else value
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError("Render count must be an integer from 1 to 8.")
    try:
        count = int(value)
    except (ValueError, TypeError) as exc:
        raise ValueError("Render count must be an integer from 1 to 8.") from exc
    if not 1 <= count <= SLOT_COUNT:
        raise ValueError("Render count must be an integer from 1 to 8.")
    return count


def merge_candidates(spec: dict, state: dict, *, include_detached: bool = False) -> dict[str, dict]:
    candidates = {item["candidate_id"]: dict(item) for item in spec.get("candidates", [])}
    candidates.update({cid: dict(item) for cid, item in (state.get("added_candidates") or {}).items()})
    for cid, update in (state.get("candidates") or {}).items():
        if cid in candidates or update.get("view"):
            candidates.setdefault(cid, {}).update(update)
    detached = set(state.get("detached_candidates") or [])
    return {cid: item for cid, item in candidates.items() if include_detached or cid not in detached}


def slot_maps(run: dict) -> dict[str, list[str | None]]:
    saved = run.get("slots_by_view") or {}
    result = {}
    for view in run.get("views") or []:
        if view in saved:
            result[view] = list(saved[view])
        else:
            ids = [c["candidate_id"] for c in run.get("candidates") or [] if c["view"] == view]
            result[view] = ids + [None] * max(0, SLOT_COUNT - len(ids))
    return result


def frozen_input(directory: Path, prompt: str, references: list[dict], preset: str) -> dict:
    """Copy ordered reference bytes once, then verify them before each submission."""
    directory.mkdir(parents=True, exist_ok=True)
    frozen = []
    for index, ref in enumerate(references):
        if str(ref.get("path", "")).startswith("declared:"):
            raise ValueError("Text-only preview references cannot be rendered.")
        source = Path(ref["path"])
        target = directory / f"reference-{index + 1}{source.suffix}"
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
        frozen.append({**ref, "path": str(target), "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
    return {"prompt": prompt, "references": frozen, "preset": preset}


def verify_input(record: dict) -> None:
    for ref in record.get("references") or []:
        path = Path(ref["path"])
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != ref.get("sha256"):
            raise ValueError("Saved render reference is missing or changed. Refresh sources explicitly.")


class CharacterRenderSlots:
    """Short state transactions shared by all four character generation adapters."""

    def __init__(self, workflow):
        self.workflow = workflow
        self.adapter = workflow.adapter

    def detail(self, run: dict) -> dict:
        run = dict(run)
        run["slots_by_view"] = maps = slot_maps(run)
        run["candidate_count"] = len(run.get("candidates") or [])
        busy = self._busy_reason(run)
        run["slot_controls"] = {}
        for view, slots in maps.items():
            stage_reason = self._prerequisite(run, view)
            reason = busy or stage_reason
            run["slot_controls"][view] = {"empty_count": slots.count(None), "reason": reason,
                "legacy": len(slots) > SLOT_COUNT, "can_generate": not reason and len(slots) <= SLOT_COUNT and None in slots,
                "stage_reason": stage_reason}
            if self.workflow.pipeline == "costume-dressing":
                from zet.services.costume_rotation_service import rotation_source
                try:
                    source = rotation_source(run, view)
                    run["slot_controls"][view].update(rotation_reason="", rotation_source_view=source["view"])
                except ValueError as exc:
                    run["slot_controls"][view]["rotation_reason"] = str(exc)
        for candidate in run.get("candidates") or []:
            slots = maps.get(candidate["view"], [])
            candidate["slot"] = slots.index(candidate["candidate_id"]) + 1 if candidate["candidate_id"] in slots else None
            candidate["slot_reason"] = busy or self._protected(run, candidate)
            candidate["slot_waiting"] = run["slot_controls"][candidate["view"]]["stage_reason"] if candidate.get("render_status") == "PENDING" else ""
        return run

    @staticmethod
    def _busy_reason(run: dict) -> str:
        if run.get("stop_requested") or run.get("status") == "STOPPING":
            return "Resume the stopped batch before submitting more renders."
        return ""

    def prepare_input(self, run: dict, view: str, directory: Path, *, recompile: bool = False, output_dir: Path | None = None) -> dict:
        """Read the current view prompt, optionally compile it, then freeze this ask."""
        packet_facts = {}
        packet_declarations = []
        from zet.services.template_source_service import active_revision
        from zet.services.local_view_reference_service import custom_references, reference_recipes
        root = Path(run["root"])
        pipeline = self.workflow.pipeline
        revision = active_revision(root)
        output = output_dir or root / "prompts" / view
        stamp = output / "Template_Revision.json"
        compiled_revision = json.loads(stamp.read_text(encoding="utf-8")).get("revision_id", "") if stamp.is_file() else ""
        recipe = reference_recipes(root, pipeline).get(view) or {"mode": "default"}
        recipe_stamp = output / "Reference_Recipe.json"
        prior_recipe = json.loads(recipe_stamp.read_text(encoding="utf-8")) if recipe_stamp.is_file() else {"mode": "default"}
        assembly_stamp = output / "Assembly_Input_Version.json"
        if pipeline == "character-assembly":
            version = json.loads(assembly_stamp.read_text(encoding="utf-8")).get("version") if assembly_stamp.is_file() else None
            recompile = recompile or version != ASSEMBLY_INPUT_VERSION
        recompile = recompile or output_dir is not None or compiled_revision != revision.get("revision_id", "") or recipe != prior_recipe or recipe["mode"] != "default"
        if pipeline == "body-reference":
            snapshot = next(item for item in run["prompt_snapshots"] if item["view"] == view)
            anchor = next((c for c in run["candidates"] if c["candidate_id"] == run.get("front_anchor")), {})
            refs = [{"role": "body_reference_front_anchor", "path": anchor["image_path"]}] if view != "FRONT" and anchor.get("image_path") else []
            refs = custom_references(run, view, pipeline, refs)
            if recompile or refs:
                snapshot = self.adapter._compile_view(root, run["character"], run["phase"], view, run["views"].index(view) + 1, output_dir=output, references=refs)
            path = Path(snapshot["prompt_path"])
            prompt = self.adapter._qwen_prompt(path.read_text(encoding="utf-8"), view, anchor=bool(refs), anchor_view=refs[0].get("view", "FRONT") if refs else "FRONT")
            manifest = path.parent / "dependency_manifest.json"
            if manifest.is_file():
                resources = json.loads(manifest.read_text(encoding="utf-8")).get("resources")
                if isinstance(resources, list):
                    refs = resources
            preset = "comfyui-qwen-body-reference-edit" if refs else "comfyui-qwen-body-reference-text"
        elif pipeline in {"head-image", "head-image-edit"}:
            anchor = next((c for c in run["candidates"] if c["candidate_id"] == run.get("front_anchor")), {})
            source = run.get("front_source") if view == "FRONT" else anchor.get("image_path")
            refs = [{"role": "head_image_source", "path": source}] if source else []
            refs = custom_references(run, view, pipeline, refs)
            path = output / "Final_Image_Prompt.md"
            if recompile or not path.is_file():
                compiled = self.adapter._compile(root, run["character"], run["phase"], view, refs,
                    apply_phase_change=bool(run.get("apply_phase_change")), output_dir=output)
                path = Path(compiled["final_prompt"])
                packet_facts = compiled.get("packet_facts", {})
                source_map_path = Path(str(compiled.get("source_map") or ""))
                if source_map_path.is_file():
                    packet_declarations = json.loads(source_map_path.read_text(encoding="utf-8")).get("prompt_packet_declarations", [])
            # Keep compiler-added images in the same order as the prompt citations,
            # including when reusing a saved prompt without recompilation.
            manifest = path.parent / "dependency_manifest.json"
            if manifest.is_file():
                resources = json.loads(manifest.read_text(encoding="utf-8")).get("resources")
                if isinstance(resources, list):
                    refs = resources
            prompt = path.read_text(encoding="utf-8")
            preset = self.adapter.edit_preset if refs else self.adapter.text_preset
        else:
            if recompile and pipeline == "costume-dressing" and output_dir is None:
                self.adapter._refresh_costume_snapshot(run)
                run = self.adapter.detail(run["run_id"], run.get("costume", ""))
            refs = self.adapter._references(run, view, use_recipe=True)
            path = output / "Final_Image_Prompt.md"
            if recompile or not path.is_file():
                compiled = self.adapter._compile(run, view, refs, output_dir=output, use_reference_recipe=True)
                path = Path(compiled["final_prompt"])
                packet_facts = compiled.get("packet_facts", {})
                source_map_path = Path(str(compiled.get("source_map") or ""))
                if source_map_path.is_file():
                    packet_declarations = json.loads(source_map_path.read_text(encoding="utf-8")).get("prompt_packet_declarations", [])
            # Compilation may package additional ordered costume references.
            manifest = output / "dependency_manifest.json"
            if manifest.is_file():
                resources = json.loads(manifest.read_text(encoding="utf-8")).get("resources")
                if isinstance(resources, list) and resources:
                    refs = resources
            prompt = path.read_text(encoding="utf-8")
            preset = self.adapter.definition["preset"]
        from zet.services.atomic_file_service import write_json_atomic
        if output_dir is None:
            write_json_atomic(recipe_stamp, recipe)
        if pipeline == "character-assembly":
            write_json_atomic(assembly_stamp, {"version": ASSEMBLY_INPUT_VERSION})
            write_json_atomic(stamp, {"revision_id": revision.get("revision_id", "")})
        saved = frozen_input(directory, prompt, refs, preset)
        if packet_facts:
            saved["compiler_facts"] = packet_facts
        if packet_declarations:
            saved["prompt_packet_declarations"] = packet_declarations
        saved["template_revision_id"] = revision.get("revision_id", "")
        saved["reference_recipe"] = recipe
        if pipeline == "head-image-edit":
            from zet.services.local_render_backend_service import LocalRenderBackendService
            saved["recipe_version"] = 1
            saved["render_settings"] = LocalRenderBackendService(self.workflow.app.config.state_file(self.workflow.project_root, "Local_Render_Presets.json"), config=self.workflow.app.config).preset(preset)
        if pipeline == "character-assembly":
            saved["assembly_input_version"] = ASSEMBLY_INPUT_VERSION
        return saved

    def _prerequisite(self, run: dict, view: str) -> str:
        from zet.services.local_character_progression_service import guard_view
        try:
            guard_view(run, view)
        except ValueError as exc:
            return str(exc)
        from zet.services.local_view_reference_service import recipe_requirement
        custom = recipe_requirement(run, view)
        if custom is not None:
            return custom
        requires = self.workflow.pipeline in {"body-reference", "head-image", "head-image-edit"} or run.get("use_front_anchor", False)
        if view != "FRONT" and requires and not run.get("front_anchor"):
            return "Select a FRONT anchor before rendering this view."
        return ""

    @staticmethod
    def _protected(run: dict, candidate: dict) -> str:
        cid = candidate["candidate_id"]
        if cid in (run.get("selected_views") or {}).values() or cid == run.get("front_anchor"):
            return "Unselect this image before clearing or regenerating it."
        for asset in (run.get("local_assets") or {}).values():
            if asset.get("locked") and asset.get("batch_id") == run["run_id"] and asset.get("candidate_id") == cid:
                return "Unlock this image before clearing or regenerating it."
        return ""

    def change(self, run_id: str, view: str, action: str, payload: dict, costume: str = "") -> dict:
        from zet.services.local_image_pipeline_policy import view_candidate_id
        from zet.services.local_image_evaluation_service import supersede_evaluations
        from zet.services.workflow_storage import file_lock

        load = lambda: self.workflow.prompt_improvement.detail(run_id, costume)
        run = load()
        root = Path(run["root"])
        try:
            with file_lock(root / "state.lock"):
                run = load()
                view = view.upper()
                if view not in run["views"]:
                    raise ValueError("Unknown character view.")
                reason = self._busy_reason(run) if action != "clear" else ""
                if reason:
                    raise RenderSlotConflict(reason)
                state = json.loads((root / "state.json").read_text(encoding="utf-8"))
                spec = json.loads((root / "spec.json").read_text(encoding="utf-8"))
                maps = slot_maps(run)
                slots = maps[view]
                index = payload.get("slot")
                if index is not None:
                    if isinstance(index, bool) or not isinstance(index, int) or not 1 <= index <= len(slots):
                        raise ValueError(f"Choose a slot from 1 to {len(slots)}.")
                    index -= 1
                candidates = {c["candidate_id"]: c for c in run["candidates"]}
                old = candidates.get(slots[index]) if index is not None else None
                if "expected_candidate_id" in payload and payload["expected_candidate_id"] != (old or {}).get("candidate_id"):
                    raise RenderSlotConflict("This slot changed. Review its current image before acting.")
                if action != "generate" and not old:
                    raise RenderSlotConflict("This slot is empty.")
                if old and action == "generate":
                    raise RenderSlotConflict("This slot is occupied. Clear it explicitly first.")
                if old and self._protected(run, old):
                    raise RenderSlotConflict(self._protected(run, old))
                if action != "clear" and self._prerequisite(run, view):
                    raise RenderSlotConflict(self._prerequisite(run, view))
                if action == "retry" and (old.get("render_status") != "FAILED" or Path(str(old.get("image_path") or "")).is_file()):
                    raise RenderSlotConflict("Render Retry requires a failed image render. Use review retry for failed advice.")
                if len(slots) > SLOT_COUNT and action != "clear":
                    raise RenderSlotConflict("Clear surplus legacy candidates before adding renders.")
                if action != "generate" and index is None:
                    raise ValueError("Choose a slot.")
                indices = [index] if index is not None else [i for i, cid in enumerate(slots) if cid is None][:render_count(payload.get("count"))]
                if index is None and len(indices) != render_count(payload.get("count")):
                    raise RenderSlotConflict("Not enough empty slots.")
                all_candidates = merge_candidates(spec, state, include_detached=True)
                template = old or next((c for c in reversed(list(all_candidates.values())) if c.get("view") == view), None)
                if action != "clear" and template is None:
                    raise ValueError("This view has no saved render inputs.")
                if template and action == "retry" and not template.get("render_input") and template.get("ask_id"):
                    # Pre-slot batches may only have a compiled path. Do not silently
                    # use a later compilation if the original prompt has changed.
                    prompt_path = Path(str(template.get("prompt_path") or ""))
                    prompt = template.get("prompt")
                    if prompt is None:
                        if not prompt_path.is_file() or hashlib.sha256(prompt_path.read_bytes()).hexdigest() != template.get("prompt_sha256"):
                            raise RenderSlotConflict("Saved prompt changed or is unavailable. Refresh/recompile this view explicitly.")
                        prompt = prompt_path.read_text(encoding="utf-8")
                    preset = template.get("render_preset") or ("comfyui-qwen-body-reference-text" if view == "FRONT" else "comfyui-qwen-body-reference-edit")
                    template = dict(template)
                    template["render_input"] = frozen_input(root / "renders" / template["candidate_id"] / "inputs", prompt, template.get("reference_images") or [], preset)
                created = []
                if old:
                    state.setdefault("detached_candidates", []).append(old["candidate_id"])
                for position in indices:
                    if action == "clear":
                        slots[position] = None
                        continue
                    ordinal = max((int(c.get("ordinal") or c["candidate_id"].rsplit("-", 1)[1]) for c in all_candidates.values() if c.get("view") == view), default=0) + 1
                    cid = view_candidate_id(view, ordinal)
                    keep = {key: deepcopy(template[key]) for key in ("method", "prompt", "prompt_sha256", "view_index", "render_input") if key in template}
                    candidate = {**keep, "candidate_id": cid, "view": view, "ordinal": ordinal,
                        "seed": template["seed"] if action == "retry" else str(random.SystemRandom().randrange(0, 2**63 - 1)),
                        "status": "PENDING", "image_path": "", "ask_id": "", "retry_count": 0,
                        "human_review": {"decision": "undecided"}, "render_error": ""}
                    if action != "retry":
                        candidate["render_input"] = self.prepare_input(run, view, root / "renders" / cid / "inputs",
                            recompile=bool(payload.get("recompile")))
                        if self.workflow.pipeline == "body-reference":
                            candidate["prompt"] = candidate["render_input"]["prompt"]
                            candidate["prompt_sha256"] = hashlib.sha256(candidate["prompt"].encode()).hexdigest()
                    candidate["slot_managed"] = True
                    state.setdefault("candidates", {})[cid] = candidate
                    state.setdefault("added_candidates", {})[cid] = {key: deepcopy(value) for key, value in candidate.items() if key != "render_input"}
                    all_candidates[cid] = candidate
                    slots[position] = cid
                    created.append(cid)
                if len(slots) > SLOT_COUNT:
                    slots[:] = [cid for cid in slots if cid]  # Only legacy galleries compact.
                    slots.extend([None] * max(0, SLOT_COUNT - len(slots)))
                supersede_evaluations(state, {view}, "Render slots changed.")
                if view in (state.get("evaluations") or {}):
                    state["evaluations"][view].update(evaluation_id=uuid4().hex, status="SUPERSEDED")
                ranking = state.setdefault("rankings", {}).get(view)
                if ranking:
                    ranking.update(status="STALE", stale_reason="Render slots changed.")
                review = state.setdefault("view_reviews", {}).setdefault(view, {})
                review["ai_observations"] = {"status": "PENDING", "text": "", "auto_started": False}
                state.pop("slot_collection_error", None)
                state.update(slots_by_view=maps, slot_version=1, updated_at=datetime.now().astimezone().isoformat(timespec="seconds"))
                if created:
                    pending = state.setdefault("slot_render_ids", [])
                    pending.extend(created)
                if old:
                    state["slot_render_ids"] = [cid for cid in state.get("slot_render_ids", []) if cid != old["candidate_id"]]
                review_views = state.setdefault("slot_review_views", [])
                if view not in review_views:
                    review_views.append(view)
                write_library_json(root / "state.json", state, pipeline_library_root_for_path(root))
        except TimeoutError as exc:
            raise RenderSlotConflict("Wait for this batch to finish rendering.") from exc
        result = self.detail(load())
        result["submitted_candidate_ids"] = created
        return result

    def collect(self, run_id: str, costume: str = "") -> None:
        """Reconcile independent slot asks without owning the batch runner lock."""
        from zet.services.local_image_pipeline_policy import mutate_local_run_state
        from zet.services.workflow_storage import file_lock

        load = lambda: self.workflow.prompt_improvement.detail(run_id, costume)
        root = Path(load()["root"])
        try:
            with file_lock(root / "slot_runner.lock", timeout=0):
                while root.is_dir():
                    with file_lock(root / "state.lock"):
                        run = load()
                        if run.get("stop_requested"):
                            return
                        state = json.loads((root / "state.json").read_text(encoding="utf-8"))
                        pending = list(state.get("slot_render_ids") or [])
                        review_views = list(state.get("slot_review_views") or [])
                        if not pending and not review_views:
                            return
                        changed = set()
                        done = set()
                        for cid in pending:
                            candidate = next((c for c in run["candidates"] if c["candidate_id"] == cid), None)
                            if candidate is None:
                                done.add(cid)
                                continue
                            try:
                                kwargs = {"costume": costume} if self.workflow.pipeline in {"character-assembly", "costume-dressing"} else {}
                                if not candidate.get("ask_id"):
                                    self.adapter.queue_render_candidate(run_id, cid, **kwargs)
                                    candidate = next(c for c in load()["candidates"] if c["candidate_id"] == cid)
                                if self.workflow.pipeline == "body-reference":
                                    target = Path(candidate["image_path"])
                                    self.adapter._harvest_local_body_reference_answer(run_id, cid, candidate["ask_id"], target)
                                elif self.workflow.pipeline in {"head-image", "head-image-edit"}:
                                    self.adapter._harvest(run_id, candidate)
                                else:
                                    self.adapter._harvest_render(run, candidate)
                                target = Path(candidate["image_path"])
                                status, answer = self.adapter._proxy_answer(candidate["ask_id"])
                                if target.is_file():
                                    updates = {"status": "WAITING_FOR_HUMAN_REVIEW", "image_sha256": self.adapter._hash(target), "render_error": ""}
                                    changed.add(candidate["view"])
                                    done.add(cid)
                                elif answer.get("status") in {"ERROR", "RETRY_LATER"} or status == "UNKNOWN":
                                    raise ValueError(answer.get("error_message") or "Render ask is missing. Use Retry to resubmit it.")
                                else:
                                    queued_at = datetime.fromisoformat(candidate["queued_at"])
                                    if (datetime.now(queued_at.tzinfo) - queued_at).total_seconds() > 1860:
                                        raise ValueError("Timed out waiting for the render. Use Retry after checking AI_Proxy.")
                                    updates = {"status": "RUNNING" if status == "RUNNING" else "QUEUED"}
                                self._update(run_id, cid, costume, updates)
                            except Exception as exc:
                                self._update(run_id, cid, costume, {"status": "FAILED", "render_error": str(exc)})
                                done.add(cid)
                                changed.add(candidate["view"])
                        def finish(state):
                            state["slot_render_ids"] = [cid for cid in state.get("slot_render_ids", []) if cid not in done]
                            views = state.setdefault("slot_review_views", [])
                            for view in changed:
                                if view not in views:
                                    views.append(view)
                        mutate_local_run_state(root, finish)
                        run = load()
                        for view in set(review_views) | changed:
                            if any(c["view"] == view and c.get("render_status") in {"QUEUED", "RUNNING"} for c in run["candidates"]):
                                continue
                            if any(c["view"] == view and Path(str(c.get("image_path") or "")).is_file() for c in run["candidates"]):
                                self.workflow.stage_view_evaluation(run_id, view, costume=costume)
                            mutate_local_run_state(root, lambda state, view=view: state.update(slot_review_views=[v for v in state.get("slot_review_views", []) if v != view]))
                    time.sleep(max(.5, float(self.adapter.app.config.comfyui_poll_seconds)))
        except TimeoutError:
            return

    def start(self, run_id: str, costume: str = "") -> None:
        """Deduplicate collectors and close the last-action/worker-exit race."""
        from zet.services.local_character_overview_service import submit_local_pipeline_task
        run = self.workflow.prompt_improvement.detail(run_id, costume)
        root = Path(run["root"])
        key = str(root.resolve())
        with _SLOT_WORKERS_LOCK:
            if key in _SLOT_WORKERS:
                return
            _SLOT_WORKERS.add(key)

        def work():
            finished = False
            try:
                self.collect(run_id, costume)
                finished = True
            except Exception as exc:
                if (root / "state.json").is_file():
                    from zet.services.local_image_pipeline_policy import mutate_local_run_state
                    mutate_local_run_state(root, lambda state: state.update(slot_collection_error=str(exc)))
            finally:
                with _SLOT_WORKERS_LOCK:
                    _SLOT_WORKERS.discard(key)
                if finished and (root / "state.json").is_file():
                    state = json.loads((root / "state.json").read_text(encoding="utf-8"))
                    if not state.get("stop_requested") and (state.get("slot_render_ids") or state.get("slot_review_views")):
                        self.start(run_id, costume)
        submit_local_pipeline_task(work)

    def _update(self, run_id: str, cid: str, costume: str, updates: dict) -> None:
        if self.workflow.pipeline == "body-reference":
            self.adapter._candidate_update(run_id, cid, updates)
        elif self.workflow.pipeline in {"head-image", "head-image-edit"}:
            self.adapter._update(run_id, cid, **updates)
        else:
            self.adapter._update(run_id, cid, costume, **updates)
