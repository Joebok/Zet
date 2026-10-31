"""Mode-scoped character selections and explicit image locks."""
from pathlib import Path

from zet.services.library_reference_service import pipeline_library_root_for_path, read_library_json, write_library_json
from zet.services.render_slot_service import slot_maps
from zet.services.workflow_storage import file_lock


class LocalModeSelectionService:
    def __init__(self, workflow):
        self.workflow = workflow
        self.store = workflow.adapter.asset_store

    def _pipeline(self):
        if self.workflow.pipeline == "body-reference":
            return "Body-Reference"
        if self.workflow.pipeline in {"head-image", "head-image-edit"}:
            return self.workflow.adapter.asset_pipeline
        return self.workflow.adapter.definition["asset_pipeline"]

    def _context(self, run_id, view, mode, costume):
        if mode not in ("draft", "final"):
            raise ValueError("Render mode must be draft or final.")
        run = self.workflow.prompt_improvement.detail(run_id, costume)
        view = str(view).upper()
        if view not in run.get("views", []):
            raise ValueError("Unknown character view.")
        qualifier = self.workflow.adapter._qualifier(costume) if self.workflow.pipeline == "costume-dressing" else ""
        return run, view, qualifier

    @staticmethod
    def _available_candidate(run, view, candidate_id, mode):
        candidate = next((c for c in run.get("candidates", []) if c.get("candidate_id") == candidate_id), None)
        image = Path(str((candidate or {}).get("image_path") or ""))
        return bool(candidate and candidate.get("view") == view
                    and candidate.get("render_mode", "draft") == mode
                    and candidate_id in slot_maps(run, mode).get(view, [])
                    and image.is_file() and image.resolve().is_relative_to(Path(run["root"]).resolve())
                    and (candidate.get("human_review") or {}).get("decision") != "reject")

    def select(self, run_id, view, candidate_id, mode, costume=""):
        run, view, qualifier = self._context(run_id, view, mode, costume)
        root = Path(run["root"])
        with file_lock(root / "state.lock"):
            run, view, qualifier = self._context(run_id, view, mode, costume)
            state_path = root / "state.json"
            state = read_library_json(state_path, pipeline_library_root_for_path(root))
            field = "selected_views" if mode == "draft" else "final_selected_views"
            selected = state.setdefault(field, {})
            record = self.store.mode_record(run["character"], run["phase"], self._pipeline(), view, qualifier, render_mode=mode)
            if record and record.get("locked") and record.get("batch_id") == run_id and record.get("candidate_id") != candidate_id:
                raise ValueError("Unlock this mode's image before changing its selection.")
            if candidate_id:
                if not self._available_candidate(run, view, candidate_id, mode):
                    raise ValueError("Select an available, non-rejected image in this view and mode.")
                selected[view] = candidate_id
            else:
                selected.pop(view, None)
            if view == "FRONT":
                previous = state.get("front_anchor" if mode == "draft" else "final_front_anchor")
                state["front_anchor" if mode == "draft" else "final_front_anchor"] = candidate_id or None
                if mode == "draft" and self.workflow.pipeline == "character-assembly" and previous != (candidate_id or None):
                    from zet.services.local_character_progression_service import invalidate_assembly_rankings
                    invalidate_assembly_rankings(state)
            write_library_json(state_path, state, pipeline_library_root_for_path(root))
        return self.workflow._present_run(self.workflow.prompt_improvement.detail(run_id, costume))

    def lock(self, run_id, view, mode, costume=""):
        run, view, qualifier = self._context(run_id, view, mode, costume)
        root = Path(run["root"])
        with file_lock(root / "state.lock"):
            run, view, qualifier = self._context(run_id, view, mode, costume)
            field = "selected_views" if mode == "draft" else "final_selected_views"
            candidate_id = (run.get(field) or {}).get(view)
            candidate = next((c for c in run.get("candidates", []) if c.get("candidate_id") == candidate_id), None)
            if not self._available_candidate(run, view, candidate_id, mode):
                raise ValueError("Select an available image in this view and mode before locking.")
            record = self.store.mode_record(run["character"], run["phase"], self._pipeline(), view, qualifier, render_mode=mode)
            if not (record and record.get("locked") and record.get("batch_id") == run_id and record.get("candidate_id") == candidate_id):
                self.store.record_mode_selection(run["character"], run["phase"], self._pipeline(), view,
                    qualifier=qualifier, render_mode=mode, candidate_id=candidate_id,
                    image_path=candidate["image_path"], batch_id=run_id)
            if mode == "draft":
                return self.store.lock_private_draft(run["character"], run["phase"], self._pipeline(), view, qualifier)
            return self.store.lock_final(run["character"], run["phase"], self._pipeline(), view, qualifier)

    def unlock(self, run_id, view, mode, costume=""):
        run, view, qualifier = self._context(run_id, view, mode, costume)
        root = Path(run["root"])
        with file_lock(root / "state.lock"):
            run, view, qualifier = self._context(run_id, view, mode, costume)
            record = self.store.mode_record(run["character"], run["phase"], self._pipeline(), view, qualifier, render_mode=mode)
            if not record or not record.get("locked") or record.get("batch_id") != run_id:
                raise ValueError("This batch has no locked image in the requested mode.")
            return self.store.unlock(run["character"], run["phase"], self._pipeline(), view, qualifier, render_mode=mode)
