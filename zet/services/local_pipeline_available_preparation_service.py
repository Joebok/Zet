"""Prepare reserved Run available candidates without holding the batch lock."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import hashlib
import re
from uuid import uuid4

from zet.services.library_reference_service import pipeline_library_root_for_path, read_library_json
from zet.services.local_image_evaluation_service import mode_field, supersede_evaluations
from zet.services.local_pipeline_operation_context import check_reserved_operation_context
from zet.services.local_pipeline_operation_reservation import LocalPipelineOperationReservation, ReservationConflict
from zet.services.render_slot_service import frozen_input, merge_candidates, slot_maps, verify_input
from zet.services.workflow_storage import file_lock


class LocalPipelineAvailablePreparationService:
    def __init__(self, workflow):
        self.workflow = workflow

    def _run(self, request):
        return self.workflow.action("detail", run_id=request["run_id"], costume=request.get("costume") or "")

    def prepare(self, request: dict, operation_id: str, candidate_id: str) -> dict | None:
        """Compile and freeze one reserved target outside the state lock."""
        if not re.fullmatch(r"(?:F|FL|FR|PL|PR|B|BR|BL)-\d{3,}", str(candidate_id)):
            raise ValueError("Invalid local image candidate ID.")
        run = self._run(request)
        root = Path(run["root"])
        reservation = LocalPipelineOperationReservation(root)
        record = reservation.snapshot(operation_id)
        if record.get("status") != "PREPARING":
            raise ReservationConflict("This operation no longer owns preparation.")
        if candidate_id in record.get("committed_candidate_ids", []):
            return None
        target = next((item for item in record["targets"] if item["candidate_id"] == candidate_id), None)
        if not target:
            raise ReservationConflict("This candidate is not reserved by the operation.")
        check_reserved_operation_context(run, request, record)
        template = None
        if not target.get("existing"):
            with file_lock(root / "state.lock"):
                library = pipeline_library_root_for_path(root)
                spec = read_library_json(root / "spec.json", library)
                state = read_library_json(root / "state.json", library)
                template = merge_candidates(spec, state, include_detached=True).get(target["template_candidate_id"])
                if not template or template.get("view") != target["view"]:
                    raise ReservationConflict("The source candidate for this view is unavailable.")
                template = deepcopy(template)
        if target.get("retry") and template.get("render_input"):
            frozen = deepcopy(template["render_input"])
        elif target.get("retry"):
            prompt_path = Path(str(template.get("prompt_path") or ""))
            prompt = template.get("prompt")
            if prompt is None:
                if not prompt_path.is_file() or hashlib.sha256(prompt_path.read_bytes()).hexdigest() != template.get("prompt_sha256"):
                    raise ReservationConflict("Saved prompt changed or is unavailable. Refresh the view before retrying.")
                prompt = prompt_path.read_text(encoding="utf-8")
            preset = template.get("render_preset") or ("comfyui-qwen-body-reference-text" if target["view"] == "FRONT" else "comfyui-qwen-body-reference-edit")
            frozen = frozen_input(root / "renders" / candidate_id / "inputs", prompt, template.get("reference_images") or [], preset)
        else:
            frozen = self.workflow.slots.prepare_input(run, target["view"], root / "renders" / candidate_id / "inputs",
                recompile=bool(target.get("recompile", target.get("existing"))), render_mode=target["mode"], aspect_ratio=request.get("aspect_ratio"))
        verify_input(frozen)
        return {"target": target, "render_input": frozen, "template": template}

    def commit(self, request: dict, operation_id: str, prepared: dict) -> bool:
        """Recheck current inputs and commit one prepared target atomically."""
        target = prepared["target"]
        frozen = prepared["render_input"]
        verify_input(frozen)
        root = Path(self._run(request)["root"])
        reservation = LocalPipelineOperationReservation(root)
        current = {}

        def validate(state, record):
            run = self._run(request)
            check_reserved_operation_context(run, request, record)
            reason = "" if target.get("retry_input_frozen") else self.workflow.slots._prerequisite(run, target["view"], target["mode"])
            if reason:
                raise ReservationConflict(reason)
            current["run"] = run

        def apply(state, reserved):
            if reserved != target:
                raise ReservationConflict("The reserved candidate changed.")
            run = current["run"]
            view, mode, cid = target["view"], target["mode"], target["candidate_id"]
            maps = slot_maps(run, mode)
            slots = maps[view]
            position = target["slot"] - 1
            candidates = {item["candidate_id"]: item for item in run.get("candidates") or []}
            if target.get("existing"):
                candidate = candidates.get(cid) or {}
                if (slots[position] != cid or candidate.get("render_status") != "PENDING" or candidate.get("ask_id")
                        or (candidate.get("image_path") and Path(candidate["image_path"]).is_file())
                        or cid in (state.get("slot_render_ids") or [])):
                    raise ReservationConflict("The reserved candidate is no longer available.")
                state.setdefault("candidates", {}).setdefault(cid, {}).update(
                    render_input=deepcopy(frozen), slot_managed=True, render_mode=mode, status="PENDING")
            else:
                previous_id = target.get("previous_candidate_id")
                if slots[position] != previous_id or cid in candidates:
                    raise ReservationConflict("The reserved slot or candidate changed.")
                previous = candidates.get(previous_id) if previous_id else None
                if previous_id and (not previous or self.workflow.slots._protected(run, previous)):
                    raise ReservationConflict("The previous candidate is no longer available for replacement.")
                if target.get("retry") and (not previous or previous.get("render_status") != "FAILED"
                        or Path(str(previous.get("image_path") or "")).is_file()):
                    raise ReservationConflict("The previous render is no longer eligible for retry.")
                template = prepared.get("template") or {}
                if template.get("candidate_id") != target.get("template_candidate_id"):
                    raise ReservationConflict("The saved view template changed.")
                fields = ("method", "prompt", "prompt_sha256", "view_index")
                library = pipeline_library_root_for_path(root)
                spec = read_library_json(root / "spec.json", library)
                current_template = merge_candidates(spec, state, include_detached=True).get(template["candidate_id"]) or {}
                checked_fields = fields + (("seed", "render_input", "reference_images", "prompt_path", "render_preset", "ask_id") if target.get("retry") else ())
                if any(current_template.get(key) != template.get(key) for key in checked_fields):
                    raise ReservationConflict("The saved view template changed.")
                keep = {key: deepcopy(template[key]) for key in fields if key in template}
                candidate = {**keep, "candidate_id": cid, "view": view, "ordinal": target["ordinal"],
                    "render_mode": mode, "seed": target["seed"], "status": "PENDING", "image_path": "", "ask_id": "",
                    "retry_count": 0, "human_review": {"decision": "undecided"}, "render_error": "",
                    "slot_managed": True, "render_input": deepcopy(frozen)}
                if self.workflow.pipeline == "body-reference":
                    candidate["prompt"] = frozen["prompt"]
                    candidate["prompt_sha256"] = hashlib.sha256(candidate["prompt"].encode()).hexdigest()
                sizing = frozen.get("render_sizing")
                if sizing:
                    candidate.update({key: sizing[key] for key in ("aspect_ratio", "target_pixels", "width", "height")})
                state.setdefault("candidates", {})[cid] = candidate
                state.setdefault("added_candidates", {})[cid] = {key: deepcopy(value) for key, value in candidate.items() if key != "render_input"}
                if previous_id:
                    state.setdefault("detached_candidates", []).append(previous_id)
                    state["slot_render_ids"] = [item for item in state.get("slot_render_ids", []) if item != previous_id]
                slots[position] = cid
                state["slots_by_view" if mode == "draft" else "final_slots_by_view"] = maps
                state["slot_version"] = 1
                supersede_evaluations(state, {view}, "Render slots changed.", render_mode=mode)
                evaluation = (state.get(mode_field("evaluations", mode)) or {}).get(view)
                if evaluation:
                    evaluation.update(evaluation_id=uuid4().hex, status="SUPERSEDED")
                ranking = (state.get(mode_field("rankings", mode)) or {}).get(view)
                if ranking:
                    ranking.update(status="STALE", stale_reason="Render slots changed.")
                if mode == "draft":
                    review = state.setdefault("view_reviews", {}).setdefault(view, {})
                    review["ai_observations"] = {"status": "PENDING", "text": "", "auto_started": False}
            state.pop("slot_collection_error", None)
            pending = state.setdefault("slot_render_ids", [])
            if cid not in pending:
                pending.append(cid)
            reviews = state.setdefault(mode_field("slot_review_views", mode), [])
            if view not in reviews:
                reviews.append(view)

        return reservation.commit(operation_id, target["candidate_id"], apply, validate=validate)
