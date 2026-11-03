"""Mode-scoped character batch reads without the full detail presentation pass."""
from __future__ import annotations

from pathlib import Path
import hashlib
from typing import Any

from zet.services.library_reference_service import read_library_json, write_library_json
from zet.services.local_pipeline_operation_context import (
    candidate_retry_context, evaluation_context, operation_context,
)
from zet.services.local_view_reference_service import reference_recipes
from zet.services.render_slot_service import merge_candidates, slot_maps
from zet.services.workflow_storage import file_lock


class LocalPipelineProjectionService:
    """Read one spec/state pair and expose only the requested page's records."""

    def __init__(self, workflow: Any):
        self.workflow = workflow
        self.adapter = workflow.adapter

    def _load(self, run_id: str, costume: str) -> tuple[dict, dict]:
        pipeline = self.workflow.pipeline
        if pipeline == "body-reference":
            root = self.adapter._root(run_id)
        elif pipeline == "costume-dressing":
            root = self.adapter._run_root(run_id, costume)
        else:
            root = self.adapter._run_root(run_id)
        root = Path(root).resolve()
        owner = Path(self.adapter.library_root).resolve()
        if not root.is_relative_to(owner):
            raise ValueError("Batch is outside the selected universe.")
        spec = read_library_json(root / "spec.json", owner)
        with file_lock(root / "state.lock"):
            state = read_library_json(root / "state.json", owner)
        if not isinstance(spec, dict) or not isinstance(state, dict):
            raise ValueError("Batch records are invalid.")
        if pipeline == "costume-dressing" and not costume:
            raise ValueError("Choose the costume for this batch.")
        run = {**spec, **state, "root": str(root), "candidates": list(merge_candidates(spec, state).values())}
        run["selected_views"] = state.get("selected_views") or {}
        run["final_selected_views"] = state.get("final_selected_views") or {}
        run["slots_by_view"] = state.get("slots_by_view") or spec.get("slots_by_view") or {}
        run["final_slots_by_view"] = state.get("final_slots_by_view") or spec.get("final_slots_by_view") or {}
        run["slots_by_mode"] = {mode: slot_maps(run, mode) for mode in ("draft", "final")}
        run["selected_views_by_mode"] = {"draft": run["selected_views"], "final": run["final_selected_views"]}
        run["view_reference_recipes"] = reference_recipes(root, pipeline, state=run)
        run["active_template_revision_id"] = (state.get("character_progression") or {}).get("accepted_revision_id", "")
        if pipeline == "costume-dressing":
            from zet.services.costume_render_mode_service import render_settings
            run["render_settings"] = {view: render_settings(run, view) for view in run.get("views") or []}
        run["stop_requested"] = bool(state.get("stop_requested"))
        run["slot_paused"] = bool(state.get("slot_paused"))
        assets = self.adapter.asset_store.detail(run["character"], run["phase"]).get("assets") or {}
        run["_assets"] = assets
        source_pipeline = ("Body-Reference" if pipeline == "body-reference" else
                           self.adapter.asset_pipeline if pipeline in {"head-image", "head-image-edit"} else
                           self.adapter.definition["asset_pipeline"])
        qualifier = self.adapter._qualifier(str(run.get("costume") or "")) if pipeline == "costume-dressing" else ""
        run["locked_draft_comparisons"] = {
            item["view"]: {"key": item["key"], "image_sha256": item.get("image_sha256", "")}
            for item in self.adapter.asset_store.locked_assets(run["character"], run["phase"], source_pipeline,
                                                                qualifier, render_mode="draft")
            if str(item.get("qualifier") or "").casefold() == qualifier.casefold()
        }
        return run, state

    def _mode(self, mode: str) -> str:
        if mode not in {"draft", "final"}:
            raise ValueError("Render mode must be draft or final.")
        return mode

    def _asset_key(self, run: dict, view: str, mode: str) -> str:
        pipeline = ("Body-Reference" if self.workflow.pipeline == "body-reference" else
                    self.adapter.asset_pipeline if self.workflow.pipeline in {"head-image", "head-image-edit"} else
                    self.adapter.definition["asset_pipeline"])
        qualifier = self.adapter._qualifier(str(run.get("costume") or "")) if self.workflow.pipeline == "costume-dressing" else ""
        return self.adapter.asset_store.mode_key(pipeline, view, qualifier, render_mode=mode)

    @staticmethod
    def _candidate_available(run: dict, candidate: dict) -> bool:
        path = Path(str(candidate.get("image_path") or "")).resolve()
        return path.is_file() and path.is_relative_to(Path(run["root"])) and path.stat().st_size > 0

    @staticmethod
    def _saved_source_changed(candidate: dict, current_refs: dict) -> bool:
        frozen = candidate.get("render_input") or {}
        sources = frozen.get("template_sources") or []
        for source in sources:
            path = Path(str(source.get("path") or ""))
            if not path.is_file():
                return True
            if hashlib.sha256(path.read_bytes()).hexdigest() != source.get("sha256"):
                return True
        if not current_refs or not frozen.get("references"):
            return False
        if current_refs.get("error"):
            return True
        for ref in frozen["references"]:
            current = current_refs.get(ref.get("role"))
            if not current:
                continue
            if ref.get("candidate_id") and current.get("candidate_id"):
                if ref["candidate_id"] != current["candidate_id"]:
                    return True
            if ref.get("sha256") and current.get("sha256") and ref["sha256"] != current["sha256"]:
                return True
        return False

    def summary(self, run_id: str, mode: str = "draft", costume: str = "") -> dict:
        mode = self._mode(mode)
        run, state = self._load(run_id, costume)
        views = (run.get("character_progression") or {}).get("requested_views") or run.get("views") or []
        selected = run["selected_views_by_mode"][mode]
        by_id = {item.get("candidate_id"): item for item in run["candidates"]}
        pending = set(run.get("slot_render_ids") or [])
        cards = []
        for view in views:
            candidate_id = selected.get(view) or ""
            candidate = by_id.get(candidate_id) or {}
            slots = run["slots_by_mode"][mode].get(view, [])
            slot_candidates = [by_id.get(cid) for cid in slots if cid]
            slot_candidates = [item for item in slot_candidates if item
                               and item.get("render_mode", "draft") == mode
                               and item.get("view") == view]
            queued = any(item.get("candidate_id") in pending
                         or item.get("render_status", item.get("status")) in {"QUEUED", "RUNNING"}
                         or item.get("status") in {"QUEUED", "RUNNING"}
                         for item in slot_candidates)
            record = run["_assets"].get(self._asset_key(run, view, mode)) or {}
            selected_available = bool(candidate_id and self._candidate_available(run, candidate))
            lock_path = Path(str(record.get("locked_image_path") or "")).resolve()
            locked_available = bool(record.get("locked") and lock_path.is_file()
                                    and lock_path.is_relative_to(Path(self.adapter.library_root).resolve()))
            cards.append({"view": view, "selected_candidate_id": candidate_id,
                          "selected_available": selected_available,
                          "selected_image_sha256": candidate.get("image_sha256", "") if selected_available else "",
                          "locked_key": self._asset_key(run, view, mode) if locked_available else "",
                          "locked_image_sha256": record.get("image_sha256", "") if locked_available else "",
                          "locked_available": locked_available,
                          "display_kind": "selected" if selected_available else "locked" if locked_available else "",
                          "display_candidate_id": candidate_id if selected_available else record.get("candidate_id", "") if locked_available else "",
                          "display_image_sha256": candidate.get("image_sha256", "") if selected_available else record.get("image_sha256", "") if locked_available else "",
                          "locked": bool(record.get("locked") and record.get("batch_id") == run_id
                                         and record.get("candidate_id") == candidate_id),
                          "locked_candidate_id": record.get("candidate_id", "") if record.get("locked") else "",
                          "image_count": sum(bool(item.get("image_path")) for item in slot_candidates),
                          "slot_count": len(slots), "renders_active": queued})
        progress = {}
        for current_mode in ("draft", "final"):
            items = [item for item in run["candidates"] if item.get("render_mode", "draft") == current_mode]
            active = [item for item in items if item.get("candidate_id") in pending or item.get("render_status", item.get("status")) in {"QUEUED", "RUNNING"}]
            progress[current_mode] = {"candidate_count": len(items),
                                      "complete_count": sum(bool(item.get("image_path")) for item in items),
                                      "selected_count": len(run["selected_views_by_mode"][current_mode]),
                                      "current_views": sorted({item.get("view") for item in active if item.get("view")}),
                                      "status": "RUNNING" if active else str(run.get("status") or "NOT_STARTED")}
        flow = run.get("character_progression") or {}
        requested = list(flow.get("requested_views") or views)
        next_views = (["FRONT"] if "FRONT" in requested and not selected.get("FRONT") else
                      [view for view in requested if view != "FRONT" and not selected.get(view)])
        progression = {"stage": flow.get("stage", -1), "next_views": next_views,
                       "current_views": [], "can_continue": bool(next_views),
                       "complete": not bool(next_views), "reason": "",
                       "prompt_review_required": False}
        return {"run_id": run_id, "character": run.get("character", ""), "phase": run.get("phase", ""),
                "costume": run.get("costume", ""), "batch_name": run.get("batch_name", ""),
                "status": run.get("status", ""), "error": run.get("error", ""), "render_mode": mode,
                "views": list(views), "selected_cards": cards, "progress_by_mode": progress,
                "selected_comparison_images": {view: {"candidate_id": candidate_id,
                    "image_sha256": by_id[candidate_id].get("image_sha256", "")}
                    for view, candidate_id in selected.items()
                    if candidate_id in by_id and by_id[candidate_id].get("render_mode", "draft") == mode
                    and self._candidate_available(run, by_id[candidate_id])},
                "locked_draft_comparisons": run["locked_draft_comparisons"],
                "selected_views_by_mode": run["selected_views_by_mode"],
                "character_progression": flow, "progression": progression,
                "front_anchor": run.get("front_anchor"), "final_front_anchor": run.get("final_front_anchor"),
                "front_count": run.get("front_count"), "other_count": run.get("other_count"),
                "slot_render_ids": run.get("slot_render_ids") or [], "slot_paused": run.get("slot_paused"),
                "stop_requested": run.get("stop_requested"), "target_views": run.get("target_views") or [],
                "use_front_anchor": run.get("use_front_anchor"),
                "apply_phase_change": run.get("apply_phase_change"),
                "front_source": run.get("front_source", ""),
                "front_source_sha256": run.get("front_source_sha256", ""),
                "front_sources_by_mode": run.get("front_sources_by_mode") or {},
                "created_by_autogenerate": run.get("created_by_autogenerate"),
                "universe_style_variant": run.get("universe_style_variant", "canonical"),
                "active_template_revision_id": run["active_template_revision_id"],
                "prompt_review": state.get("template_revision_review") or {},
                "operation_context": operation_context(run, mode),
                "evaluation_context": evaluation_context(run, mode)}

    def view(self, run_id: str, view: str, mode: str = "draft", costume: str = "") -> dict:
        mode = self._mode(mode)
        run, state = self._load(run_id, costume)
        view = str(view or "").upper()
        if view not in run.get("views", []):
            raise ValueError(f"Unknown character view: {view}")
        candidates = []
        slots = run["slots_by_mode"][mode].get(view, [])
        for source in run["candidates"]:
            if source.get("view") != view or source.get("render_mode", "draft") != mode:
                continue
            candidate = dict(source)
            available = self._candidate_available(run, candidate)
            candidate["image_available"] = available
            candidate["render_status"] = ("COMPLETE" if available else "FAILED" if candidate.get("render_error") else
                                          "RUNNING" if candidate.get("status") == "RUNNING" else
                                          "QUEUED" if candidate.get("ask_id") and candidate.get("status") == "QUEUED" else "PENDING")
            if not available:
                candidate["image_path"] = ""
            candidate["slot"] = slots.index(candidate["candidate_id"]) + 1 if candidate["candidate_id"] in slots else None
            candidate["slot_reason"] = self.workflow.slots._protected(run, candidate)
            candidates.append(candidate)
        rankings = state.get("rankings" if mode == "draft" else "final_rankings") or {}
        evaluations = state.get("evaluations" if mode == "draft" else "final_evaluations") or {}
        selected_id = run["selected_views_by_mode"][mode].get(view) or ""
        record = run["_assets"].get(self._asset_key(run, view, mode)) or {}
        sources = (run.get("sources") or {}).get(view) or {}
        preview = {}
        if self.workflow.pipeline in {"character-assembly", "costume-dressing"}:
            try:
                resolved = self.workflow.slots._mode_sources(run, view, mode)
                preview = {role: {"render_mode": item.get("render_mode", mode),
                                  "candidate_id": item.get("candidate_id", ""),
                                  "sha256": item.get("image_sha256") or item.get("sha256", ""),
                                  "label": item.get("label", "")}
                           for role, item in resolved.items()}
            except (ValueError, OSError) as exc:
                preview = {"error": str(exc)}
        pipeline_key = self._asset_key(run, view, mode)
        locked_id = str(record.get("candidate_id") or "") if record.get("locked") else ""
        eligible = [item for item in candidates if item["candidate_id"] == locked_id] if locked_id else candidates
        if locked_id and record.get("source_change_fyi"):
            for item in eligible:
                item["source_change_fyi"] = True
        newly_marked = [item for item in eligible if (item["image_available"] or item["candidate_id"] == locked_id)
                        and not item.get("source_change_fyi")
                        and self._saved_source_changed(item, preview)]
        if newly_marked:
            with file_lock(Path(run["root"]) / "state.lock"):
                fresh = read_library_json(Path(run["root"]) / "state.json", self.adapter.library_root)
                for item in newly_marked:
                    saved = (fresh.get("candidates") or {}).get(item["candidate_id"])
                    if saved is not None:
                        saved["source_change_fyi"] = True
                        item["source_change_fyi"] = True
                write_library_json(Path(run["root"]) / "state.json", fresh, self.adapter.library_root)
        if locked_id and any(item["candidate_id"] == locked_id and item.get("source_change_fyi") for item in eligible):
            self.adapter.asset_store.mark_source_change_fyi(run["character"], run["phase"], pipeline_key,
                                                            run_id, locked_id)
            record["source_change_fyi"] = True
        return {"run_id": run_id, "view": view, "render_mode": mode, "status": run.get("status", ""),
                "character": run.get("character", ""), "phase": run.get("phase", ""),
                "costume": run.get("costume", ""), "batch_name": run.get("batch_name", ""),
                "views": list(run.get("views") or []), "candidates": candidates, "slots": slots,
                "slots_by_mode": {mode: {view: slots}},
                "slot_controls_by_mode": {mode: {view: {"stage_reason": "",
                    "reason": "", "empty_count": slots.count(None),
                    "legacy": len(slots) > 8, "can_generate": None in slots}}},
                "ranking": rankings.get(view) or {}, "evaluation": evaluations.get(view) or {},
                "view_review": (state.get("view_reviews") or {}).get(view) or {},
                "reference_recipe": run["view_reference_recipes"].get(view) or {},
                "render_settings": (run.get("render_settings") or {}).get(view) or {},
                "selected_views_by_mode": {key: {view: values[view]} if view in values else {}
                                           for key, values in run["selected_views_by_mode"].items()},
                "front_anchor": run.get("front_anchor"), "final_front_anchor": run.get("final_front_anchor"),
                "character_progression": run.get("character_progression") or {},
                "sources": {view: sources}, "source_previews_by_mode": {mode: {view: preview}},
                "front_source": run.get("front_source", ""),
                "front_source_sha256": run.get("front_source_sha256", ""),
                "front_sources_by_mode": run.get("front_sources_by_mode") or {},
                "local_assets": {pipeline_key: record} if record else {},
                "selected_candidate_id": selected_id,
                "locked": bool(record.get("locked") and record.get("batch_id") == run_id
                               and record.get("candidate_id") == selected_id),
                "operation_context": operation_context(run, mode, view),
                "evaluation_context": evaluation_context(run, mode, view),
                "candidate_retry_contexts": {item["candidate_id"]: candidate_retry_context(run, mode, item["candidate_id"])
                                             for item in candidates}}
