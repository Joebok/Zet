"""Preflight for a mode-scoped character batch restart."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from zet.services.library_reference_service import pipeline_library_root_for_path, read_library_json, write_library_json
from zet.services.local_image_evaluation_service import mode_field
from zet.services.local_mode_selection_service import LocalModeSelectionService
from zet.services.render_slot_service import merge_candidates, slot_maps
from zet.services.workflow_storage import atomic_copy, file_lock, runner_lock_active


class LocalCharacterBatchRestartService:
    """Inspect the exact batch state and source locks before a restart."""

    def __init__(self, workflow):
        self.workflow = workflow
        self.adapter = workflow.adapter

    @staticmethod
    def _digest(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    def preview(self, run_id: str, payload: dict, costume: str = "") -> dict:
        mode = payload.get("render_mode")
        recompile = payload.get("recompile", False)
        if mode not in {"draft", "final"} or not isinstance(recompile, bool):
            raise ValueError("Choose Draft or Final and a valid Recompile option.")
        initial = self.workflow.prompt_improvement.detail(run_id, costume)
        root = Path(initial["root"]).resolve()
        with file_lock(root / "state.lock"):
            run = self.workflow.prompt_improvement.detail(run_id, costume)
            return self._preview_locked(run, mode, recompile, costume)

    def clear_mode(self, run_id: str, payload: dict, costume: str = "") -> dict:
        """Prepare and clear one idle mode after a fenced preview."""
        mode = payload.get("render_mode")
        recompile = payload.get("recompile", False)
        if mode not in {"draft", "final"} or not isinstance(recompile, bool):
            raise ValueError("Choose Draft or Final and a valid Recompile option.")
        initial = self.workflow.prompt_improvement.detail(run_id, costume)
        root = Path(initial["root"]).resolve()
        library = pipeline_library_root_for_path(root)
        selection = LocalModeSelectionService(self.workflow)
        qualifier = self.adapter._qualifier(costume) if self.workflow.pipeline == "costume-dressing" else ""
        store = selection.store
        with file_lock(root / "template_improvement" / "revisions.lock"), file_lock(root / "state.lock"), file_lock(store.workspace_path(initial["character"], initial["phase"]).with_suffix(".lock")):
            run = self.workflow.prompt_improvement.detail(run_id, costume)
            from zet.services.local_pipeline_operation_reservation import active_preparation
            state = read_library_json(root / "state.json", library)
            if active_preparation(state):
                from zet.services.render_slot_service import RenderSlotConflict
                raise RenderSlotConflict("Another operation is preparing this batch. Wait before restarting it.")
            preview = self._preview_locked(run, mode, recompile, costume)
            if preview["issues"]:
                raise ValueError(" ".join(preview["issues"]))
            if payload.get("confirmation_token") != preview["confirmation_token"]:
                from zet.services.protected_effect_preview import ProtectedEffectsChanged
                raise ProtectedEffectsChanged(preview)
            approved = payload.get("approved_effects")
            if not isinstance(approved, list) or set(approved) != {effect["id"] for effect in preview["protected_effects"]}:
                raise ValueError("Approve each selected or locked image affected by restart.")
            spec = read_library_json(root / "spec.json", library)
            # Head phase-change sources are mode-specific snapshots. Prepare a
            # new immutable copy before touching any selections or candidates.
            if self.workflow.pipeline in {"head-image", "head-image-edit"}:
                previous = self.adapter.mode_front_source(run, mode)
                origin = previous.get("origin") or {}
                if origin.get("kind") == "locked_phase":
                    source_path, source_origin = self.adapter._locked_phase_source_for_mode({
                        "character": run["character"], "phase": run["phase"],
                        "front_source_phase": origin.get("phase"),
                        "front_source_pipeline": origin.get("pipeline"),
                    }, mode)
                    source = Path(source_path)
                    digest = self._digest(source)
                    destination = root / "inputs" / f"{mode}_front_source_{digest}{source.suffix.lower()}"
                    if not destination.is_file():
                        atomic_copy(source, destination)
                    if self._digest(destination) != digest or self._digest(source) != digest:
                        raise ValueError("The locked phase source changed while preparing restart.")
                    record = {"path": str(destination), "sha256": digest,
                              "origin": {**source_origin, "snapshot_sha256": digest}}
                    spec.setdefault("front_sources_by_mode", {})[mode] = record
                    if mode == "draft":
                        spec.update(front_source=str(destination), front_source_sha256=digest,
                                    front_source_origin=record["origin"])
            candidates = [item for item in merge_candidates(spec, state, include_detached=True).values()
                          if item.get("render_mode", "draft") == mode]
            ids = {item["candidate_id"] for item in candidates}
            paths = []
            for candidate in candidates:
                raw = str(candidate.get("image_path") or "")
                if raw:
                    path = Path(raw)
                    path = (path if path.is_absolute() else Path(library) / path).resolve()
                    if not path.is_relative_to(root):
                        raise ValueError("Candidate output is outside this batch.")
                    paths.append(path)
                output = (root / "renders" / candidate["candidate_id"] / "Local_Test_Renders").resolve()
                if not output.is_relative_to(root / "renders"):
                    raise ValueError("Candidate output is outside this batch.")
                if output.is_dir():
                    paths.extend(path for path in output.iterdir()
                                 if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"})
            confirmed = self._preview_locked(run, mode, recompile, costume)
            if confirmed["issues"] or confirmed["confirmation_token"] != payload.get("confirmation_token"):
                raise ValueError("Batch state or inputs changed while preparing restart; review it again.")
            if recompile:
                if self.workflow.pipeline == "character-assembly":
                    # Assembly has no governing revision workflow. Compile into
                    # an isolated directory; generation remains an explicit action.
                    with TemporaryDirectory(prefix=".restart_compile_", dir=root) as stage_path:
                        stage = Path(stage_path)
                        self.workflow.slots.prepare_input(run, "FRONT", stage / "inputs",
                                                          recompile=True, output_dir=stage / "prompt",
                                                          render_mode=mode)
                else:
                    from zet.services.local_template_revision_service import LocalTemplateRevisionService
                    revisions = LocalTemplateRevisionService(self.workflow.app, self.workflow.project_root)
                    revisions.start(self.workflow.pipeline, run_id, {
                        "from_master": True, "skip_analysis": True,
                        "expected_active": run.get("active_template_revision_id", ""),
                    }, costume)
                    # Revision acceptance updates the same state file.
                    state = read_library_json(root / "state.json", library)
            if self.workflow.pipeline in {"head-image", "head-image-edit"} and spec.get("front_sources_by_mode") != run.get("front_sources_by_mode"):
                write_library_json(root / "spec.json", spec, library)
            for view in run.get("views") or []:
                record = store.mode_record(run["character"], run["phase"], selection._pipeline(),
                                           view, qualifier, render_mode=mode) or {}
                if record.get("batch_id") != run_id:
                    continue
                if record.get("locked"):
                    if mode == "draft" and record.get("locked_image_path"):
                        snapshot = Path(record["locked_image_path"])
                        snapshot = (snapshot if snapshot.is_absolute() else Path(library) / snapshot).resolve()
                        snapshot_root = (store.workspace_path(run["character"], run["phase"]).parent / "draft-locks").resolve()
                        if snapshot.is_relative_to(snapshot_root) and snapshot != snapshot_root:
                            paths.append(snapshot)
                    store.unlock(run["character"], run["phase"], selection._pipeline(), view,
                                 qualifier, render_mode=mode)
                store.clear_mode_selection(run["character"], run["phase"], selection._pipeline(),
                                           view, qualifier, render_mode=mode, batch_id=run_id)
            slots = slot_maps(run, mode)
            for view in slots:
                slots[view] = [None] * len(slots[view])
                state.setdefault(mode_field("rankings", mode), {}).pop(view, None)
                # A new identity prevents late evaluation updates from matching.
                state.setdefault(mode_field("evaluations", mode), {})[view] = {
                    "evaluation_id": uuid4().hex, "status": "SUPERSEDED",
                    "superseded_reason": "Batch mode was restarted.",
                }
                ai = (state.get("view_reviews", {}).get(view) or {}).get("ai_observations")
                if ai:
                    ai.update(status="STALE", stale_reason="Batch images were cleared.", job_id=uuid4().hex)
            state[mode_field("slots_by_view", mode)] = slots
            state[mode_field("selected_views", mode)] = {}
            state[mode_field("front_anchor", mode)] = None
            state[mode_field("slot_review_views", mode)] = []
            state["slot_version"] = int(state.get("slot_version") or 0) + 1
            state["detached_candidates"] = list(dict.fromkeys([*(state.get("detached_candidates") or []), *sorted(ids)]))
            for field in ("slot_render_ids", "target_candidate_ids"):
                state[field] = [cid for cid in state.get(field, []) if cid not in ids]
            if not state["target_candidate_ids"]:
                state["target_views"] = []
            state["slot_paused"] = False
            state["stop_requested"] = False
            if state.get("status") in {"STOPPED", "CANCELLED", "INTERRUPTED", "ERROR"}:
                state["status"] = "QUEUED"
                state["error"] = ""
            write_library_json(root / "state.json", state, library)
            for path in paths:
                path.unlink(missing_ok=True)
        return self.workflow._present_run(self.workflow.prompt_improvement.detail(run_id, costume))

    def _preview_locked(self, run: dict, mode: str, recompile: bool, costume: str) -> dict:
        root = Path(run["root"]).resolve()
        selection = LocalModeSelectionService(self.workflow)
        qualifier = self.adapter._qualifier(costume) if self.workflow.pipeline == "costume-dressing" else ""
        views = list(run.get("views") or [])
        issues = []
        active = {"STAGING", "QUEUED", "RUNNING"}
        if (runner_lock_active(root) or run.get("slot_work_pending") or run.get("slot_render_ids")
                or run.get("slot_review_views") or run.get("final_slot_review_views")
                or run.get("status") in {"PREFLIGHT", "RUNNING", "STOPPING", "REEVALUATING"}
                or any(record.get("status") in active for field in ("evaluations", "final_evaluations")
                       for record in (run.get(field) or {}).values() if isinstance(record, dict))):
            issues.append("Wait for all rendering and ranking work to finish before restarting.")
        records = {}
        locked = []
        for view in views:
            record = selection.store.mode_record(run["character"], run["phase"], selection._pipeline(),
                                                 view, qualifier, render_mode=mode) or {}
            if record.get("batch_id") == run["run_id"]:
                records[view] = record
                if record.get("locked"):
                    locked.append(view)
        sources = {}
        try:
            if self.workflow.pipeline in {"character-assembly", "costume-dressing"}:
                for view in views:
                    resolved = self.workflow.slots._mode_sources(run, view, mode)
                    sources[view] = {role: {**item, "current_sha256": self._digest(Path(item["image_path"]))}
                                     for role, item in resolved.items()}
            elif self.workflow.pipeline in {"head-image", "head-image-edit"}:
                current = self.adapter.mode_front_source(run, mode)
                origin = current.get("origin") or {}
                if origin.get("kind") == "locked_phase":
                    path, source_origin = self.adapter._locked_phase_source_for_mode({
                        "character": run["character"], "phase": run["phase"],
                        "front_source_phase": origin.get("phase"),
                        "front_source_pipeline": origin.get("pipeline"),
                    }, mode)
                    sources["FRONT"] = {"path": path, "origin": source_origin,
                                        "current_sha256": self._digest(Path(path))}
        except (ValueError, OSError, KeyError) as exc:
            issues.append(str(exc))
        masters = []
        if recompile:
            from zet.services.local_template_revision_service import LocalTemplateRevisionService
            revisions = LocalTemplateRevisionService(self.workflow.app, self.workflow.project_root)
            masters = [{"source_id": source["source_id"], "sha256": source["master_sha256"]}
                       for source in revisions._sources(self.workflow, run)]
        candidates = [candidate for candidate in run.get("candidates") or []
                      if candidate.get("render_mode", "draft") == mode]
        selected = run.get("selected_views" if mode == "draft" else "final_selected_views") or {}
        protected_effects = []
        for view in views:
            candidate_id = selected.get(view)
            if candidate_id:
                protected_effects.append({"id": f"unselect:{mode}:{view}:{candidate_id}",
                                          "label": f"Unselect {mode.title()} {view} ({candidate_id})"})
            record = records.get(view) or {}
            if record.get("locked"):
                protected_effects.append({"id": f"unlock:{mode}:{view}:{record.get('candidate_id')}",
                                          "label": f"Unlock {mode.title()} {view} ({record.get('candidate_id')})"})
        evidence = {"mode": mode, "recompile": recompile, "run_id": run["run_id"],
                    "state": self._digest(root / "state.json"), "spec": self._digest(root / "spec.json"),
                    "records": records, "sources": sources, "masters": masters, "issues": issues}
        token = hashlib.sha256(json.dumps(evidence, sort_keys=True, default=str).encode()).hexdigest()
        return {"render_mode": mode, "recompile": recompile, "candidate_count": len(candidates),
                "image_count": sum(bool(item.get("image_path")) for item in candidates),
                "locked_views": locked, "protected_effects": protected_effects,
                "issues": issues, "confirmation_token": token}
