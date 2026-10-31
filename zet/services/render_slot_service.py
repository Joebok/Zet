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
ASSEMBLY_INPUT_VERSION = 2
_SLOT_WORKERS: set[str] = set()
_SLOT_WORKERS_LOCK = threading.Lock()
_SLOT_WAKEUPS: dict[str, threading.Event] = {}


class RenderSlotConflict(ValueError):
    pass


class RenderExecutionFailure(ValueError):
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


def slot_maps(run: dict, render_mode: str = "draft") -> dict[str, list[str | None]]:
    if render_mode not in ("draft", "final"):
        raise ValueError("Render mode must be draft or final.")
    saved = run.get("slots_by_view" if render_mode == "draft" else "final_slots_by_view") or {}
    result = {}
    for view in run.get("views") or []:
        if view in saved:
            result[view] = list(saved[view])
        else:
            ids = [c["candidate_id"] for c in run.get("candidates") or []
                   if c["view"] == view and c.get("render_mode", "draft") == render_mode]
            result[view] = ids + [None] * max(0, SLOT_COUNT - len(ids))
    return result


def frozen_input(directory: Path, prompt: str, references: list[dict], preset: str, *, render_sizing: dict | None = None) -> dict:
    """Copy ordered reference bytes once, then verify them before each submission."""
    if render_sizing is not None:
        from zet.services.image_sizing_service import validate_frozen_image_sizing
        render_sizing = validate_frozen_image_sizing(render_sizing)
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
    result = {"prompt": prompt, "references": frozen, "preset": preset}
    if render_sizing is not None:
        result["render_sizing"] = render_sizing
    return result


def verify_input(record: dict) -> None:
    for ref in record.get("references") or []:
        path = Path(ref["path"])
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != ref.get("sha256"):
            raise ValueError("Saved render reference is missing or changed. Refresh sources explicitly.")


def _rebind_mode_references(resources: list, current: list[dict], roles: set[str]) -> list[dict]:
    """Replace mode-dependent bindings without changing saved prompt or reference order."""
    if any(not isinstance(item, dict) for item in resources):
        raise ValueError("Saved prompt has invalid reference bindings. Recompile the prompt.")
    replacements = {item["role"]: item for item in current if item.get("role") in roles}
    for role in roles:
        count = sum(item.get("role") == role for item in resources)
        if count != (1 if role in replacements else 0):
            raise ValueError(f"Saved prompt has an invalid {role} reference binding. Recompile the prompt.")
    return [{**item, **replacements[item["role"]]} if item.get("role") in replacements else item
            for item in resources]


class CharacterRenderSlots:
    """Short state transactions shared by all four character generation adapters."""

    def __init__(self, workflow):
        self.workflow = workflow
        self.adapter = workflow.adapter

    def _mode_sources(self, run, view, render_mode):
        sources = self.adapter._locked_view_inputs(run, view, render_mode=render_mode)
        if render_mode == "final":
            for role, source in sources.items():
                if source.get("render_mode", "draft") != "final":
                    raise ValueError(f"A locked Final {role.replace('_', ' ')} image is required for {view}.")
                if source.get("source_mode") == "batch":
                    record = self.adapter.asset_store.mode_record(run["character"], run["phase"],
                        source["pipeline"], view, source.get("qualifier", ""), render_mode="final") or {}
                    if not record.get("locked") or record.get("batch_id") != source.get("batch_id") or record.get("candidate_id") != source.get("candidate_id"):
                        raise ValueError(f"Lock the selected Final {role.replace('_', ' ')} image for {view}.")
        return sources

    def detail(self, run: dict) -> dict:
        run = dict(run)
        state_path = Path(run["root"]) / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {}
        run["slot_paused"] = bool(state.get("slot_paused"))
        run["slots_by_view"] = maps = slot_maps(run)
        run["slots_by_mode"] = {"draft": maps, "final": slot_maps(run, "final")}
        run["selected_views_by_mode"] = {"draft": dict(run.get("selected_views") or {}),
                                         "final": dict(run.get("final_selected_views") or {})}
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
                from zet.services.costume_render_mode_service import CostumeRenderModeService, render_settings, MODES
                service = CostumeRenderModeService(self.workflow)
                settings = render_settings(run, view)
                reasons = {mode: service.reason(run, view, {**settings, "mode": mode}) for mode in MODES}
                run.setdefault("render_settings", {})[view] = settings
                run["slot_controls"][view].update(mode_reasons=reasons,
                    no_costume_ref_reason=reasons["doll-dressing-no-ref"], rotation_reason=reasons["rotate"],
                    rotation_source_view=settings["costume_reference_view"])
        run["slot_controls_by_mode"] = {"draft": {}, "final": {}}
        for mode, mode_slots in run["slots_by_mode"].items():
            for view, slots in mode_slots.items():
                stage_reason = self._prerequisite(run, view, mode)
                reason = busy or stage_reason
                run["slot_controls_by_mode"][mode][view] = {
                    "empty_count": slots.count(None), "reason": reason,
                    "legacy": len(slots) > SLOT_COUNT,
                    "can_generate": not reason and len(slots) <= SLOT_COUNT and None in slots,
                    "stage_reason": stage_reason,
                }
        for candidate in run.get("candidates") or []:
            candidate.setdefault("render_mode", "draft")
            slots = run["slots_by_mode"].get(candidate["render_mode"], {}).get(candidate["view"], [])
            candidate["slot"] = slots.index(candidate["candidate_id"]) + 1 if candidate["candidate_id"] in slots else None
            candidate["slot_reason"] = busy or self._protected(run, candidate)
            controls = run["slot_controls_by_mode"].get(candidate["render_mode"], {})
            candidate["slot_waiting"] = controls.get(candidate["view"], {}).get("stage_reason", "") if candidate.get("render_status") == "PENDING" else ""
        return run

    @staticmethod
    def _busy_reason(run: dict) -> str:
        if run.get("slot_paused") or run.get("stop_requested") or run.get("status") == "STOPPING":
            return "Resume the stopped batch before submitting more renders."
        return ""

    def pause(self, run_id: str, costume: str = "", *, paused: bool = True) -> dict:
        from zet.services.local_image_pipeline_policy import mutate_local_run_state
        run = self.workflow.prompt_improvement.detail(run_id, costume)
        root = Path(run["root"])
        def update(state):
            if paused and not (state.get("slot_render_ids") or state.get("slot_review_views") or state.get("final_slot_review_views")):
                raise RenderSlotConflict("There is no slot work to pause.")
            if not paused and not state.get("slot_paused"):
                raise RenderSlotConflict("Slot work is not paused.")
            state["slot_paused"] = paused
        mutate_local_run_state(root, update)
        return self.workflow.action("detail", run_id=run_id, costume=costume)

    def run_available(self, run_id: str, payload: dict, costume: str = "") -> dict:
        """Queue the configured number of candidates for each ready view."""
        from zet.services.workflow_storage import file_lock, runner_lock_active
        from zet.services.local_image_evaluation_service import mode_field
        mode = payload.get("render_mode", "draft")
        scope = payload.get("scope", "available")
        if mode not in {"draft", "final"} or scope not in {"front", "available"}:
            raise ValueError("Choose a valid render mode and scope.")
        load = lambda: self.workflow.prompt_improvement.detail(run_id, costume)
        run = load()
        root = Path(run["root"])
        submitted, blocked, errors = [], {}, {}
        with file_lock(root / "state.lock"):
            run = load()
            state = json.loads((root / "state.json").read_text(encoding="utf-8"))
            if state.get("slot_paused"):
                raise RenderSlotConflict("Resume the paused batch before submitting more renders.")
            if self._busy_reason(run):
                raise RenderSlotConflict(self._busy_reason(run))
            if runner_lock_active(root):
                raise RenderSlotConflict("Wait for the batch runner to finish.")
            views = (run.get("character_progression") or {}).get("requested_views") or run.get("views") or []
            views = [v for v in views if scope != "front" or v == "FRONT"]
            for view in views:
                run = load()
                reason = self._prerequisite(run, view, mode)
                if reason:
                    blocked[view] = reason
                    continue
                try:
                    slots = slot_maps(run, mode)[view]
                    target = render_count(run.get("front_count" if view == "FRONT" else "other_count"), 8 if view == "FRONT" else 4)
                    candidates = {c["candidate_id"]: c for c in run.get("candidates") or []}
                    state_path = root / "state.json"
                    state = json.loads(state_path.read_text(encoding="utf-8"))
                    pending = state.setdefault("slot_render_ids", [])
                    prepared = []
                    for cid in [cid for cid in slots if cid][:target]:
                        candidate = candidates.get(cid) or {}
                        if (candidate.get("render_status") != "PENDING" or candidate.get("ask_id")
                                or (candidate.get("image_path") and Path(candidate["image_path"]).is_file()) or cid in pending):
                            continue
                        frozen = self.prepare_input(run, view, root / "renders" / cid / "inputs",
                            recompile=True, render_mode=mode, aspect_ratio=payload.get("aspect_ratio"))
                        state.setdefault("candidates", {}).setdefault(cid, {}).update(render_input=frozen, slot_managed=True, render_mode=mode, status="PENDING")
                        pending.append(cid)
                        prepared.append(cid)
                    if prepared:
                        review = state.setdefault(mode_field("slot_review_views", mode), [])
                        if view not in review:
                            review.append(view)
                        write_library_json(state_path, state, pipeline_library_root_for_path(root))
                        submitted.extend(prepared)
                    deficit = max(0, target - sum(bool(cid) for cid in slots))
                    if deficit:
                        result = self.change(run_id, view, "generate", {"count": deficit, "render_mode": mode,
                            "aspect_ratio": payload.get("aspect_ratio")}, costume)
                        submitted.extend(result.get("submitted_candidate_ids") or [])
                except (ValueError, OSError, KeyError) as exc:
                    errors[view] = str(exc)
        return {"render_mode": mode, "submitted_candidate_ids": submitted, "blocked_views": blocked, "errors": errors}

    def prepare_input(self, run: dict, view: str, directory: Path, *, recompile: bool = False, output_dir: Path | None = None,
                      render_mode: str | None = None, aspect_ratio: str | None = None) -> dict:
        """Read the current view prompt, optionally compile it, then freeze this ask."""
        sizing = None
        if render_mode is not None:
            from zet.services.image_sizing_service import resolve_image_sizing
            from zet.services.local_view_reference_service import selected_run_for_mode
            default_ratio = "1:1" if self.workflow.pipeline in {"head-image", "head-image-edit"} else "2:3"
            sizing = resolve_image_sizing(self.workflow.app.config, render_mode, aspect_ratio or default_ratio)
            run = selected_run_for_mode(run, render_mode, allow_fallback=render_mode != "final")
        if self.workflow.pipeline == "costume-dressing":
            from zet.services.costume_render_mode_service import CostumeRenderModeService
            if render_mode is not None:
                resolved = self._mode_sources(run, view, render_mode)
                run = {**run, "sources": {**(run.get("sources") or {}), view: resolved}}
            saved = CostumeRenderModeService(self.workflow).prepare(run, view, directory,
                output_dir=output_dir or Path(run["root"]) / "prompts" / view,
                reuse_saved_prompt=render_mode is not None and not recompile)
            if sizing is not None:
                saved["render_sizing"] = sizing
            return saved
        packet_facts = {}
        packet_declarations = []
        from zet.services.template_source_service import active_revision
        from zet.services.local_view_reference_service import custom_references, reference_recipes
        root = Path(run["root"])
        pipeline = self.workflow.pipeline
        request_run = run
        if pipeline == "character-assembly" and render_mode is not None:
            # Resolve into this request only; saved run-level sources are shared by
            # both modes and must not be replaced when another render is prepared.
            resolved = self._mode_sources(run, view, render_mode)
            request_run = {**run, "sources": {**(run.get("sources") or {}), view: resolved}}
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
            refs = [{"role": "body_reference_front_anchor", "path": anchor["image_path"],
                     "render_mode": anchor.get("render_mode", "draft")}] if view != "FRONT" and anchor.get("image_path") else []
            refs = custom_references(run, view, pipeline, refs)
            if recompile or (refs and render_mode is None):
                snapshot = self.adapter._compile_view(root, run["character"], run["phase"], view, run["views"].index(view) + 1, output_dir=output, references=refs)
            path = Path(snapshot["prompt_path"])
            prompt = self.adapter._qwen_prompt(path.read_text(encoding="utf-8"), view, anchor=bool(refs), anchor_view=refs[0].get("view", "FRONT") if refs else "FRONT")
            manifest = path.parent / "dependency_manifest.json"
            if manifest.is_file():
                resources = json.loads(manifest.read_text(encoding="utf-8")).get("resources")
                if isinstance(resources, list):
                    refs = (_rebind_mode_references(resources, refs, {"body_reference_front_anchor", "batch_view_reference"})
                            if render_mode is not None else resources)
            preset = "comfyui-qwen-body-reference-edit" if refs else "comfyui-qwen-body-reference-text"
        elif pipeline in {"head-image", "head-image-edit"}:
            anchor = next((c for c in run["candidates"] if c["candidate_id"] == run.get("front_anchor")), {})
            source = run.get("front_source") if view == "FRONT" else anchor.get("image_path")
            refs = [{"role": "head_image_source", "path": source,
                     **({"render_mode": anchor.get("render_mode", "draft")} if view != "FRONT" else {})}] if source else []
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
                    refs = (_rebind_mode_references(resources, refs, {"head_image_source"})
                            if render_mode is not None else resources)
            prompt = path.read_text(encoding="utf-8")
            preset = self.adapter.edit_preset if refs else self.adapter.text_preset
        else:
            if recompile and pipeline == "costume-dressing" and output_dir is None:
                self.adapter._refresh_costume_snapshot(run)
                run = self.adapter.detail(run["run_id"], run.get("costume", ""))
            refs = self.adapter._references(request_run, view, use_recipe=True)
            path = output / "Final_Image_Prompt.md"
            if recompile or not path.is_file():
                compiled = self.adapter._compile(request_run, view, refs, output_dir=output, use_reference_recipe=True)
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
                    if request_run is not run and pipeline == "character-assembly":
                        refs = _rebind_mode_references(resources, refs, {"body_reference", "head_image"})
                    else:
                        refs = resources
            prompt = path.read_text(encoding="utf-8")
            preset = self.adapter.definition["preset"]
        from zet.services.atomic_file_service import write_json_atomic
        if output_dir is None:
            write_json_atomic(recipe_stamp, recipe)
        if pipeline == "character-assembly":
            write_json_atomic(assembly_stamp, {"version": ASSEMBLY_INPUT_VERSION})
            write_json_atomic(stamp, {"revision_id": revision.get("revision_id", "")})
        saved = frozen_input(directory, prompt, refs, preset, render_sizing=sizing)
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

    def _prerequisite(self, run: dict, view: str, render_mode: str | None = None) -> str:
        if render_mode is not None:
            from zet.services.local_view_reference_service import selected_run_for_mode
            run = selected_run_for_mode(run, render_mode, allow_fallback=render_mode != "final")
        if self.workflow.pipeline == "costume-dressing":
            from zet.services.costume_render_mode_service import CostumeRenderModeService
            if render_mode is not None:
                try:
                    sources = self._mode_sources(run, view, render_mode)
                except (ValueError, OSError) as exc:
                    return str(exc)
                run = {**run, "sources": {**(run.get("sources") or {}), view: sources}}
            return CostumeRenderModeService(self.workflow).reason(run, view)
        from zet.services.local_character_progression_service import guard_view
        try:
            guard_view(run, view, mode_aware=render_mode is not None)
        except ValueError as exc:
            return str(exc)
        if self.workflow.pipeline == "character-assembly" and render_mode is not None:
            try:
                self._mode_sources(run, view, render_mode)
            except (ValueError, OSError) as exc:
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
        if (cid in (run.get("selected_views") or {}).values()
                or cid in (run.get("final_selected_views") or {}).values() or cid == run.get("front_anchor")):
            return "Unselect this image before clearing or regenerating it."
        for asset in (run.get("local_assets") or {}).values():
            if asset.get("locked") and asset.get("batch_id") == run["run_id"] and asset.get("candidate_id") == cid:
                return "Unlock this image before clearing or regenerating it."
        if (cid in (run.get("slot_render_ids") or [])
                or candidate.get("render_status") in {"QUEUED", "RUNNING"}):
            return "Wait for this render to finish before clearing or regenerating it."
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
                if state.get("slot_paused") and action != "clear":
                    raise RenderSlotConflict("Resume the paused batch before submitting more renders.")
                spec = json.loads((root / "spec.json").read_text(encoding="utf-8"))
                render_mode = payload.get("render_mode", "draft")
                maps = slot_maps(run, render_mode)
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
                # A retry owns its previously captured prompt and references; current
                # selections are relevant only to newly prepared renders.
                frozen_retry = action == "retry" and bool(old.get("render_input"))
                if action != "clear" and not frozen_retry:
                    prerequisite = self._prerequisite(run, view, render_mode if "render_mode" in payload else None)
                    if prerequisite:
                        raise RenderSlotConflict(prerequisite)
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
                seed_source_id = payload.get("seed_candidate_id")
                if seed_source_id and not isinstance(seed_source_id, str):
                    raise ValueError("Seed source candidate ID must be text.")
                seed_source = candidates.get(seed_source_id) if seed_source_id else None
                if seed_source_id and (action not in {"generate", "regenerate"} or not seed_source
                        or seed_source.get("view") != view or seed_source.get("render_mode", "draft") == render_mode
                        or seed_source.get("seed") is None):
                    raise ValueError("Choose a candidate from the other mode in this view to reuse its seed.")
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
                        "render_mode": render_mode,
                        "seed": (template["seed"] if action == "retry" else seed_source["seed"] if seed_source
                                 else str(random.SystemRandom().randrange(0, 2**63 - 1))),
                        "status": "PENDING", "image_path": "", "ask_id": "", "retry_count": 0,
                        "human_review": {"decision": "undecided"}, "render_error": ""}
                    if action != "retry":
                        candidate["render_input"] = self.prepare_input(run, view, root / "renders" / cid / "inputs",
                            recompile=bool(payload.get("recompile")),
                            render_mode=render_mode if "render_mode" in payload else None,
                            aspect_ratio=payload.get("aspect_ratio"))
                        if self.workflow.pipeline == "body-reference":
                            candidate["prompt"] = candidate["render_input"]["prompt"]
                            candidate["prompt_sha256"] = hashlib.sha256(candidate["prompt"].encode()).hexdigest()
                    sizing = (candidate.get("render_input") or {}).get("render_sizing")
                    if sizing:
                        candidate.update({key: sizing[key] for key in ("aspect_ratio", "target_pixels", "width", "height")})
                    candidate["slot_managed"] = True
                    state.setdefault("candidates", {})[cid] = candidate
                    state.setdefault("added_candidates", {})[cid] = {key: deepcopy(value) for key, value in candidate.items() if key != "render_input"}
                    all_candidates[cid] = candidate
                    slots[position] = cid
                    created.append(cid)
                if len(slots) > SLOT_COUNT:
                    slots[:] = [cid for cid in slots if cid]  # Only legacy galleries compact.
                    slots.extend([None] * max(0, SLOT_COUNT - len(slots)))
                from zet.services.local_image_evaluation_service import mode_field
                supersede_evaluations(state, {view}, "Render slots changed.", render_mode=render_mode)
                evaluation_field = mode_field("evaluations", render_mode)
                if view in (state.get(evaluation_field) or {}):
                    state[evaluation_field][view].update(evaluation_id=uuid4().hex, status="SUPERSEDED")
                ranking = state.setdefault(mode_field("rankings", render_mode), {}).get(view)
                if ranking:
                    ranking.update(status="STALE", stale_reason="Render slots changed.")
                if render_mode == "draft":
                    review = state.setdefault("view_reviews", {}).setdefault(view, {})
                    review["ai_observations"] = {"status": "PENDING", "text": "", "auto_started": False}
                state.pop("slot_collection_error", None)
                state["slots_by_view" if render_mode == "draft" else "final_slots_by_view"] = maps
                state.update(slot_version=1, updated_at=datetime.now().astimezone().isoformat(timespec="seconds"))
                if created:
                    pending = state.setdefault("slot_render_ids", [])
                    pending.extend(created)
                if old:
                    state["slot_render_ids"] = [cid for cid in state.get("slot_render_ids", []) if cid != old["candidate_id"]]
                review_views = state.setdefault(mode_field("slot_review_views", render_mode), [])
                if view not in review_views:
                    review_views.append(view)
                write_library_json(root / "state.json", state, pipeline_library_root_for_path(root))
        except TimeoutError as exc:
            raise RenderSlotConflict("Wait for this batch to finish rendering.") from exc
        result = self.detail(load())
        result["submitted_candidate_ids"] = created
        return result

    def recover_timeouts(self, run_id: str, costume: str = "") -> None:
        """Reattach current slots to their original requests after a historical wait timeout."""
        from zet.services.workflow_storage import file_lock, validate_image
        from zet.services.local_image_pipeline_policy import mutate_local_run_state

        root = Path(self.workflow.prompt_improvement.detail(run_id, costume)["root"])
        jobs = self.adapter.app.ai_proxy_service.ai_proxy_path_service.jobs
        with file_lock(root / "state.lock"):
            run = self.workflow.prompt_improvement.detail(run_id, costume)
            state = json.loads((root / "state.json").read_text(encoding="utf-8"))
            if state.get("stop_requested") or state.get("slot_paused"):
                return
            slots = {cid for field in ("slots_by_view", "final_slots_by_view")
                     for values in (state.get(field) or {}).values() for cid in values if cid}
            changes = {}
            pending = []
            for candidate in run.get("candidates", []):
                cid = candidate.get("candidate_id")
                ask = str(candidate.get("ask_id") or "")
                saved_error = (state.get("candidates") or {}).get(cid, {}).get("render_error", "")
                if cid not in slots or not ask or "Timed out waiting for the render" not in str(saved_error):
                    continue
                info = jobs.inspect(ask)
                record = jobs.repository.get(ask)
                manifest = record.get("manifest") or {}
                source = str(manifest.get("source_ask_id") or "")
                if (manifest.get("ask_id") != ask or manifest.get("universe_id") != self.adapter.app.universe_id
                        or run_id not in source or f"_{cid}_" not in source or info.get("status") in {"DELETED", "SUPERSEDED"}
                        or info.get("current_attempt_id", ask) != ask):
                    continue
                target = Path(str(candidate.get("image_path") or ""))
                if info.get("location") == "receipt" and info.get("execution_status") == "SUCCEEDED" and info.get("answer_status") == "SUCCESS" and target.is_file() and target.resolve().is_relative_to(root.resolve()):
                    validate_image(target.read_bytes())
                    changes[cid] = {"status": "WAITING_FOR_HUMAN_REVIEW", "render_error": "", "image_sha256": self.adapter._hash(target)}
                elif info.get("location") == "receipt" and info.get("execution_status") == "SUCCEEDED" and info.get("answer_status") == "SUCCESS":
                    changes[cid] = {"status": "QUEUED", "render_error": ""}
                    pending.append(cid)
                elif info.get("location") in {"ask", "running", "answer", "inbox"} or info.get("status") in {"RECOVERY_REQUIRED", "RECONCILING", "PAUSED_STORAGE", "HELD", "RECOVERING", "HARVEST_FAILED"}:
                    changes[cid] = {"status": "RUNNING" if info.get("location") == "running" else "QUEUED", "render_error": ""}
                    pending.append(cid)
            if changes:
                def apply(state):
                    for cid, update in changes.items():
                        state.setdefault("candidates", {}).setdefault(cid, {}).update(update)
                    ids = state.setdefault("slot_render_ids", [])
                    ids.extend(cid for cid in pending if cid not in ids)
                mutate_local_run_state(root, apply)

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
                        if state.get("slot_paused"):
                            return
                        pending = list(state.get("slot_render_ids") or [])
                        review_views = {(mode, view) for mode, field in (("draft", "slot_review_views"), ("final", "final_slot_review_views"))
                                        for view in state.get(field) or []}
                        if not pending and not review_views:
                            return
                    changed = set()
                    done = set()
                    for cid in pending:
                        # Keep membership checks and result commits fenced, but let
                        # dashboard reads and pause/slot actions in between asks.
                        with file_lock(root / "state.lock"):
                            run = load()
                            state = json.loads((root / "state.json").read_text(encoding="utf-8"))
                            if run.get("stop_requested") or state.get("slot_paused"):
                                return
                            if cid not in (state.get("slot_render_ids") or []):
                                continue
                            candidate = next((c for c in run["candidates"] if c["candidate_id"] == cid), None)
                            if candidate is None:
                                done.add(cid)
                                continue
                            try:
                                kwargs = {"costume": costume} if self.workflow.pipeline in {"character-assembly", "costume-dressing"} else {}
                                if not candidate.get("ask_id"):
                                    self.adapter.queue_render_candidate(run_id, cid, **kwargs)
                                    candidate = next(c for c in load()["candidates"] if c["candidate_id"] == cid)
                                target = Path(candidate["image_path"])
                                status, answer = ("HARVESTED", {}) if target.is_file() else self.adapter._proxy_answer(candidate["ask_id"])
                                if answer.get("status") in {"ERROR", "RETRY_LATER", "FAILED"}:
                                    raise RenderExecutionFailure(answer.get("error_message") or "AI Proxy render failed.")
                                if not target.is_file():
                                    if self.workflow.pipeline == "body-reference":
                                        self.adapter._harvest_local_body_reference_answer(run_id, cid, candidate["ask_id"], target)
                                    elif self.workflow.pipeline in {"head-image", "head-image-edit"}:
                                        self.adapter._harvest(run_id, candidate)
                                    else:
                                        self.adapter._harvest_render(run, candidate)
                                target = Path(candidate["image_path"])
                                if target.is_file():
                                    updates = {"status": "WAITING_FOR_HUMAN_REVIEW", "image_sha256": self.adapter._hash(target), "render_error": ""}
                                    changed.add((candidate.get("render_mode", "draft"), candidate["view"]))
                                    done.add(cid)
                                else:
                                    updates = {"status": "RUNNING" if status == "RUNNING" else "QUEUED"}
                                if any(candidate.get(key) != value for key, value in updates.items()):
                                    self._update(run_id, cid, costume, updates)
                            except RenderExecutionFailure as exc:
                                self._update(run_id, cid, costume, {"status": "FAILED", "render_error": str(exc)})
                                done.add(cid)
                                changed.add((candidate.get("render_mode", "draft"), candidate["view"]))
                            except Exception as exc:
                                if not candidate.get("ask_id") and isinstance(exc, ValueError):
                                    self._update(run_id, cid, costume, {"status": "FAILED", "render_error": str(exc)})
                                    done.add(cid)
                                    changed.add((candidate.get("render_mode", "draft"), candidate["view"]))
                                else:
                                    mutate_local_run_state(root, lambda state: state.update(slot_collection_error=str(exc)))
                    def finish(state):
                        state["slot_render_ids"] = [cid for cid in state.get("slot_render_ids", []) if cid not in done]
                        for mode, view in changed:
                            views = state.setdefault("slot_review_views" if mode == "draft" else "final_slot_review_views", [])
                            if view not in views:
                                views.append(view)
                    if done or changed:
                        mutate_local_run_state(root, finish)
                    for mode, view in review_views | changed:
                        with file_lock(root / "state.lock"):
                            run = load()
                            state = json.loads((root / "state.json").read_text(encoding="utf-8"))
                            if run.get("stop_requested") or state.get("slot_paused"):
                                return
                            field = "slot_review_views" if mode == "draft" else "final_slot_review_views"
                            if view not in (state.get(field) or []):
                                continue
                            mode_candidates = [c for c in run["candidates"] if c["view"] == view
                                               and c.get("render_mode", "draft") == mode]
                            if any(c["candidate_id"] in (state.get("slot_render_ids") or [])
                                   or c.get("render_status") in {"QUEUED", "RUNNING"} for c in mode_candidates):
                                continue
                            if any(Path(str(c.get("image_path") or "")).is_file() for c in mode_candidates):
                                self.workflow.stage_view_evaluation(run_id, view, costume=costume, render_mode=mode)
                            mutate_local_run_state(root, lambda state, view=view, field=field: state.update({field: [v for v in state.get(field, []) if v != view]}))
                    with _SLOT_WORKERS_LOCK:
                        wakeup = _SLOT_WAKEUPS.get(str(root.resolve()))
                    if wakeup is None:
                        time.sleep(30)
                    else:
                        wakeup.wait(30)
                        wakeup.clear()
        except TimeoutError:
            return

    def rerun_mode_view(self, run_id: str, view: str, payload: dict, costume: str = "", *, failed_only: bool = False) -> dict:
        """Regenerate or retry occupied slots in one view and render mode."""
        from zet.services.workflow_storage import file_lock

        mode = payload.get("render_mode")
        run = self.workflow.prompt_improvement.detail(run_id, costume)
        root = Path(run["root"])
        completed, errors = [], {}
        with file_lock(root / "state.lock"):
            run = self.workflow.prompt_improvement.detail(run_id, costume)
            view = str(view).upper()
            maps = slot_maps(run, mode)
            if view not in maps:
                raise ValueError("Unknown character view.")
            candidates = {item["candidate_id"]: item for item in run.get("candidates") or []}
            targets = [(index + 1, candidates[cid]) for index, cid in enumerate(maps[view]) if cid in candidates
                       and (not failed_only or candidates[cid].get("render_status") == "FAILED")]
            if not targets:
                raise RenderSlotConflict("No failed renders in this view and mode." if failed_only else "No occupied slots in this view and mode.")
            for index, candidate in targets:
                try:
                    result = self.change(run_id, view, "retry" if failed_only else "regenerate", {
                        "render_mode": mode, "slot": index, "expected_candidate_id": candidate["candidate_id"],
                        "aspect_ratio": payload.get("aspect_ratio"), "recompile": bool(payload.get("recompile")),
                    }, costume)
                    completed.extend(result.get("submitted_candidate_ids") or [])
                except (ValueError, OSError) as exc:
                    errors[candidate["candidate_id"]] = str(exc)
        return {"render_mode": mode, "submitted_candidate_ids": completed, "errors": errors}

    def delete_draft_images(self, run_id: str, view: str = "", costume: str = "") -> dict:
        """Cancel and remove Draft outputs within one batch or view."""
        from zet.services.local_image_evaluation_service import supersede_evaluations
        from zet.services.local_mode_selection_service import LocalModeSelectionService
        from zet.services.library_reference_service import read_library_json
        from zet.services.workflow_storage import file_lock, supersede_task

        load = lambda: self.workflow.prompt_improvement.detail(run_id, costume)
        root = Path(load()["root"]).resolve()
        library = pipeline_library_root_for_path(root)
        with file_lock(root / "state.lock"):
            run = load()
            views = [view.upper()] if view else list(run["views"])
            if any(item not in run["views"] for item in views):
                raise ValueError("Unknown character view.")
            state = read_library_json(root / "state.json", library)
            spec = read_library_json(root / "spec.json", library)
            candidates = [c for c in merge_candidates(spec, state, include_detached=True).values()
                          if c.get("view") in views and c.get("render_mode", "draft") == "draft"]
            ids = {c["candidate_id"] for c in candidates}
            paths = self.adapter.app.ai_proxy_service.ai_proxy_path_service
            evaluation_ids = {str((state.get("evaluations") or {}).get(item, {}).get("evaluation_id") or "")
                              for item in views} - {""}
            ask_ids = set()
            for candidate in candidates:
                ask_id = candidate.get("ask_id")
                if ask_id and candidate.get("status") in {"PENDING", "SUBMITTING", "QUEUED", "RUNNING", "PAUSED_STORAGE", "RECOVERING"}:
                    ask_ids.add(str(ask_id))
                local_job = candidate.get("local_job") or {}
                if local_job.get("ask_id") and local_job.get("status") in {"PENDING", "SUBMITTING", "QUEUED", "RUNNING", "PAUSED_STORAGE", "RECOVERING"}:
                    ask_ids.add(str(local_job["ask_id"]))
            selection = LocalModeSelectionService(self.workflow)
            qualifier = self.adapter._qualifier(costume) if self.workflow.pipeline == "costume-dressing" else ""
            store = selection.store
            snapshots = []
            for item in views:
                record = store.mode_record(run["character"], run["phase"], selection._pipeline(), item, qualifier)
                if not record or record.get("batch_id") != run_id:
                    continue
                if record.get("locked"):
                    snapshot = Path(str(record.get("locked_image_path") or ""))
                    snapshot = (snapshot if snapshot.is_absolute() else Path(library) / snapshot).resolve()
                    snapshot_root = (store.workspace_path(run["character"], run["phase"]).parent / "draft-locks").resolve()
                    if snapshot.is_relative_to(snapshot_root) and snapshot != snapshot_root:
                        snapshots.append(snapshot)
                    store.unlock(run["character"], run["phase"], selection._pipeline(), item, qualifier)
                store.clear_mode_selection(run["character"], run["phase"], selection._pipeline(), item,
                                           qualifier, batch_id=run_id)
            slots = slot_maps(run, "draft")
            selected = dict(run.get("selected_views") or {})
            for item in views:
                slots[item] = [None] * len(slots[item])
                selected.pop(item, None)
                state.setdefault("rankings", {}).pop(item, None)
                state.setdefault("view_reviews", {}).pop(item, None)
            if "FRONT" in views:
                state["front_anchor"] = None
            supersede_evaluations(state, set(views), "Draft images were deleted.")
            state.update(slots_by_view=slots, selected_views=selected,
                         detached_candidates=list(dict.fromkeys([*(state.get("detached_candidates") or []), *sorted(ids)])),
                         slot_render_ids=[cid for cid in state.get("slot_render_ids", []) if cid not in ids],
                         target_candidate_ids=[cid for cid in state.get("target_candidate_ids", []) if cid not in ids],
                         slot_review_views=[item for item in state.get("slot_review_views", []) if item not in views],
                         updated_at=datetime.now().astimezone().isoformat(timespec="seconds"))
            write_library_json(root / "state.json", state, library)
            if evaluation_ids:
                for job in paths.jobs.repository.all():
                    manifest = job.get("manifest") or {}
                    if (manifest.get("run_id") == run_id and manifest.get("evaluation_id") in evaluation_ids
                            and job.get("harvest_state") not in {"APPLIED", "FAILED", "SUPERSEDED"}):
                        ask_ids.add(str(job["ask_id"]))
            for ask_id in ask_ids:
                paths.jobs.validate_id(ask_id)
                task = paths.file_proxy_client.ask_root / ask_id
                if not task.exists():
                    task = paths.file_proxy_client.running_root / ask_id
                supersede_task(Path(paths.config.base_ai_queue_path), task,
                               "Character Draft images were deleted.", state_root=paths.lifecycle.storage_root)
            for candidate in candidates:
                cid = candidate["candidate_id"]
                output_dir = (root / "renders" / cid / "Local_Test_Renders").resolve()
                if not output_dir.is_relative_to(root / "renders"):
                    raise ValueError("Invalid candidate output directory.")
                if output_dir.is_dir():
                    for image in output_dir.iterdir():
                        if image.is_file() and image.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
                            image.unlink()
                raw = candidate.get("image_path")
                if raw:
                    image = Path(raw)
                    image = (image if image.is_absolute() else Path(library) / image).resolve()
                    if not image.is_relative_to(root):
                        raise ValueError("Candidate output is outside this batch.")
                    image.unlink(missing_ok=True)
            for snapshot in snapshots:
                snapshot.unlink(missing_ok=True)
            return self.workflow._present_run(load())

    def rerun_mode_batch(self, run_id: str, payload: dict, costume: str = "") -> dict:
        """Regenerate the occupied slots of one mode across the batch's views."""
        run = self.workflow.prompt_improvement.detail(run_id, costume)
        maps = slot_maps(run, payload.get("render_mode"))
        submitted, errors = [], {}
        for view, slots in maps.items():
            if not any(slots):
                continue
            try:
                result = self.rerun_mode_view(run_id, view, payload, costume)
                submitted.extend(result["submitted_candidate_ids"])
                errors.update({f"{view} / {key}": value for key, value in result["errors"].items()})
            except (ValueError, OSError) as exc:
                errors[view] = str(exc)
        if not submitted and not errors:
            raise RenderSlotConflict("No occupied slots in this mode.")
        return {"render_mode": payload["render_mode"], "submitted_candidate_ids": submitted, "errors": errors}

    def start(self, run_id: str, costume: str = "", *, wake: bool = True) -> None:
        """Deduplicate collectors and close the last-action/worker-exit race."""
        from zet.services.local_character_overview_service import submit_local_pipeline_task
        run = self.workflow.prompt_improvement.detail(run_id, costume)
        root = Path(run["root"])
        key = str(root.resolve())
        with _SLOT_WORKERS_LOCK:
            if key in _SLOT_WORKERS:
                if wake:
                    _SLOT_WAKEUPS[key].set()
                return
            _SLOT_WORKERS.add(key)
            _SLOT_WAKEUPS[key] = threading.Event()

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
                    _SLOT_WAKEUPS.pop(key, None)
                if finished and (root / "state.json").is_file():
                    state = json.loads((root / "state.json").read_text(encoding="utf-8"))
                    if not state.get("stop_requested") and not state.get("slot_paused") and (state.get("slot_render_ids") or state.get("slot_review_views") or state.get("final_slot_review_views")):
                        self.start(run_id, costume)
        submit_local_pipeline_task(work)

    def _update(self, run_id: str, cid: str, costume: str, updates: dict) -> None:
        if self.workflow.pipeline == "body-reference":
            self.adapter._candidate_update(run_id, cid, updates)
        elif self.workflow.pipeline in {"head-image", "head-image-edit"}:
            self.adapter._update(run_id, cid, **updates)
        else:
            self.adapter._update(run_id, cid, costume, **updates)
