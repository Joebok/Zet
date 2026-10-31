"""Universe-owned eight-slot board over persisted ad hoc render jobs."""
from __future__ import annotations

from copy import deepcopy
import json
from uuid import uuid4

from zet.services.atomic_file_service import write_json_atomic
from zet.services.render_slot_service import RenderSlotConflict, render_count
from zet.services.workflow_storage import file_lock


class ImageGenerationWorkspace:
    def __init__(self, generator):
        self.generator = generator
        self.path = generator.results_root / "workspace.json"
        self.lock = generator.results_root / "workspace.lock"

    def _load(self, render_mode="draft"):
        if render_mode not in ("draft", "final"):
            raise ValueError("Render mode must be draft or final.")
        if not self.path.exists():
            board = {"version": 1, "slots": [None] * 8, "selected_slot": None, "imported_browser_state": False}
        else:
            board = json.loads(self.path.read_text(encoding="utf-8"))
        if board.get("version") != 1 or len(board.get("slots", [])) != 8:
            raise ValueError("Unsupported Image Generation workspace.")
        if render_mode == "final":
            board = board.get("final_board") or {"version": 1, "slots": [None] * 8,
                                                  "selected_slot": None, "imported_browser_state": True}
            if board.get("version") != 1 or len(board.get("slots", [])) != 8:
                raise ValueError("Unsupported Final Image Generation workspace.")
        return board

    def _save(self, board, render_mode="draft"):
        if render_mode == "final":
            draft = self._load()
            draft["final_board"] = board
            board = draft
        write_json_atomic(self.path, board)

    def detail(self, render_mode="draft"):
        with file_lock(self.lock), self.generator._lock:
            return {**self._detail(self._load(render_mode)), "render_mode": render_mode}

    def reset_for_staging(self, render_mode="draft"):
        """Detach all results and selection without deleting jobs or image bytes."""
        with file_lock(self.lock), self.generator._lock:
            board = self._load(render_mode)
            board.update(slots=[None] * 8, selected_slot=None, imported_browser_state=True)
            self._save(board, render_mode)
            return {**self._detail(board), "render_mode": render_mode}

    def delete_draft_images(self):
        """Cancel and clear this workspace's Draft results, retaining Final work."""
        with file_lock(self.lock), self.generator._lock:
            board = self._load("draft")
            final_ids = {item["requestId"] for item in self._load("final")["slots"] if item}
            request_ids = {item["requestId"] for item in board["slots"] if item} - final_ids
            for request_id in request_ids:
                job = self.generator._read_saved_job(request_id)
                if job is None:
                    # An analysis can reserve slots before its render job exists;
                    # removing the reservation fences its eventual submission.
                    continue
                owner = (job.get("submission") or {}).get("owner") or {}
                if owner:
                    raise RenderSlotConflict("A Draft result is owned by another workflow.")
                self.generator.cancel_owned_request(request_id, {})
            board.update(slots=[None] * 8, selected_slot=None, imported_browser_state=True)
            self._save(board, "draft")
            result = {**self._detail(board), "render_mode": "draft"}
        if request_ids:
            from zet.services.ai_workflow_service import AIWorkflowService
            AIWorkflowService(self.generator.zet_app).cancel_matching(
                lambda record: record.get("service") == "reconstruction"
                and record.get("owner", {}).get("reconstruction_id") in request_ids)
        return result

    def _detail(self, board):
        jobs = {}
        busy = False
        for assignment in board["slots"]:
            if not assignment:
                continue
            request_id = assignment["requestId"]
            if request_id not in jobs:
                try:
                    jobs[request_id] = self.generator.status(request_id)
                except KeyError:
                    pending = self.generator.reconstruction.pending(request_id)
                    jobs[request_id] = {"request_id": request_id, "status": pending.get("status", "FAILED"), "images": [],
                        "error": pending.get("error", "Render submission was interrupted. Clear this slot and generate again."),
                        "results": [], "prompt": pending.get("prompt", "")}
            busy |= jobs[request_id]["status"] in {"QUEUED", "RUNNING"}
        return {**{key: value for key, value in board.items() if key != "final_board"}, "jobs": list(jobs.values()), "busy": busy, "empty_count": board["slots"].count(None)}

    def reserve_reconstruction(self, request_id, count, render_mode="draft"):
        with file_lock(self.lock), self.generator._lock:
            board = self._load(render_mode)
            indices = [i for i, value in enumerate(board["slots"]) if value is None][:count]
            if len(indices) != count:
                raise RenderSlotConflict("Not enough empty slots. Clear slots before reconstructing.")
            for child, position in enumerate(indices):
                board["slots"][position] = {"requestId": request_id, "index": child}
            board["imported_browser_state"] = True
            self._save(board, render_mode)

    def selected_result(self, expected, render_mode=None):
        """Resolve an exact completed selection in this universe, never a client path."""
        with file_lock(self.lock), self.generator._lock:
            assignment = None
            if render_mode not in (None, "draft", "final"):
                raise ValueError("Render mode must be draft or final.")
            selected_mode = None
            for mode in ((render_mode,) if render_mode else ("draft", "final")):
                board = self._load(mode)
                position = board["selected_slot"]
                current = board["slots"][position] if position is not None else None
                if current and current == expected:
                    assignment = current
                    selected_mode = mode
                    break
            if (not isinstance(expected, dict) or not assignment or type(expected.get("index")) is not int):
                raise RenderSlotConflict("The selected image changed. Select the current image and try again.")
            self.generator.status(assignment["requestId"])
            contents, _, provenance = self.generator.library_result(assignment["requestId"], assignment["index"])
            return contents, {"request_id": assignment["requestId"], "image_index": assignment["index"],
                              "asset_id": "", "label": "Selected Image Generation result",
                              "render_mode": selected_mode,
                              "reconstruction": provenance.get("reconstruction", {})}

    def submit_reconstruction(self, request_id, inputs, expected_source=None, *, render_mode="draft", frozen_sizing=None,
                              source_render_mode=None):
        with file_lock(self.lock), self.generator._lock:
            if request_id in self.generator._jobs:
                return
            board = self._load(render_mode)
            if expected_source is not None:
                source_board = self._load(source_render_mode or render_mode)
                selected = source_board["selected_slot"]
                if selected is None or source_board["slots"][selected] != expected_source:
                    raise RenderSlotConflict("The selected source changed during analysis. Start again.")
            children = {item["index"] for item in board["slots"] if item and item["requestId"] == request_id}
            if children != set(range(inputs["count"])):
                raise RenderSlotConflict("Reconstruction slots changed during analysis. Start a new reconstruction.")
            options = {"request_id": request_id}
            if frozen_sizing:
                options["frozen_sizing"] = frozen_sizing
            self.generator.submit(inputs, **options)

    def import_browser(self, payload):
        with file_lock(self.lock), self.generator._lock:
            board = self._load()
            if board["imported_browser_state"] or any(board["slots"]):
                return self._detail(board)
            slots = payload.get("slots")
            if isinstance(slots, list) and len(slots) == 8:
                for index, assignment in enumerate(slots):
                    if not isinstance(assignment, dict):
                        continue
                    job = self.generator._jobs.get(str(assignment.get("requestId") or ""))
                    result_index = assignment.get("index")
                    if job and isinstance(result_index, int) and not isinstance(result_index, bool) and 0 <= result_index < job["count"]:
                        board["slots"][index] = {"requestId": job["request_id"], "index": result_index}
                selected = payload.get("selected_slot")
                if isinstance(selected, int) and not isinstance(selected, bool) and 0 <= selected < 8 and board["slots"][selected]:
                    board["selected_slot"] = selected
            board["imported_browser_state"] = True
            write_json_atomic(self.path, board)
            return self._detail(board)

    def action(self, operation, payload):
        with file_lock(self.lock), self.generator._lock:
            render_mode = payload.get("render_mode", "draft")
            board = self._load(render_mode)
            detail = self._detail(board)
            slot = payload.get("slot")
            index = render_count(slot) - 1 if slot is not None else None
            assignment = board["slots"][index] if index is not None else None
            if "expected_assignment" in payload and payload["expected_assignment"] != assignment:
                raise RenderSlotConflict("This slot changed. Review its current image before acting.")
            if operation == "unselect":
                board["selected_slot"] = None
            elif operation == "select":
                if not assignment or not any(image["index"] == assignment["index"] for job in detail["jobs"] if job["request_id"] == assignment["requestId"] for image in job["images"]):
                    raise RenderSlotConflict("Select a completed image.")
                board["selected_slot"] = index
            else:
                if operation != "generate" and operation != "clear_all" and not assignment:
                    raise RenderSlotConflict("This slot is empty.")
                if operation != "generate" and board["selected_slot"] is not None and (operation == "clear_all" or index == board["selected_slot"]):
                    raise RenderSlotConflict("Unselect this image before clearing or regenerating it.")
                if operation == "clear_all":
                    board["slots"] = [None] * 8
                elif operation == "clear":
                    board["slots"][index] = None
                elif operation in {"generate", "regenerate", "retry"}:
                    if operation == "generate":
                        if assignment:
                            raise RenderSlotConflict("This slot is occupied. Clear it explicitly first.")
                        count = 1 if index is not None else render_count(payload.get("count"), 4)
                        indices = [index] if index is not None else [i for i, value in enumerate(board["slots"]) if value is None][:count]
                        if len(indices) != count:
                            raise RenderSlotConflict("Not enough empty slots.")
                        inputs = deepcopy(payload.get("inputs") or {})
                        seeds = None
                    else:
                        job = self.generator._jobs.get(assignment["requestId"])
                        if not job or not job.get("render_payload"):
                            raise RenderSlotConflict("Saved render inputs are unavailable. Clear this slot and generate again.")
                        child = next((child for child in job["children"] if child["index"] == assignment["index"]), None)
                        if operation == "retry" and (any(image["index"] == assignment["index"] for image in self.generator.status(job["request_id"])["images"]) or (child and not child.get("error"))):
                            raise RenderSlotConflict("Retry requires a failed render.")
                        indices = [index]
                        inputs = deepcopy(payload.get("inputs") or job["render_payload"]) if operation == "regenerate" else deepcopy(job["render_payload"])
                        if job.get("reconstruction") and "reconstruction" not in inputs:
                            inputs["reconstruction"] = deepcopy(job["reconstruction"])
                        seeds = [child["seed"]] if operation == "retry" and child and "seed" in child else None
                    if operation != "retry" and "render_mode" in payload:
                        inputs["render_mode"] = render_mode
                    inputs["count"] = len(indices)
                    request_id = uuid4().hex
                    # Save inputs and reservation before publishing asks. Crash recovery can
                    # display a failed reservation without assigning another job's output.
                    previous = deepcopy(board["slots"])
                    for child_index, position in enumerate(indices):
                        board["slots"][position] = {"requestId": request_id, "index": child_index}
                    board["imported_browser_state"] = True
                    self._save(board, render_mode)
                    try:
                        submit_options = {"request_id": request_id, "seeds": seeds}
                        if operation == "retry" and job.get("render_sizing"):
                            submit_options["frozen_sizing"] = job["render_sizing"]
                        self.generator.submit(inputs, **submit_options)
                    except Exception:
                        if request_id not in self.generator._jobs:
                            board["slots"] = previous
                            self._save(board, render_mode)
                        raise
                else:
                    raise ValueError("Unknown Image Generation slot action.")
            board["imported_browser_state"] = True
            self._save(board, render_mode)
            return {**self._detail(board), "render_mode": render_mode}
