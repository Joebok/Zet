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

    def _load(self):
        if not self.path.exists():
            return {"version": 1, "slots": [None] * 8, "selected_slot": None, "imported_browser_state": False}
        board = json.loads(self.path.read_text(encoding="utf-8"))
        if board.get("version") != 1 or len(board.get("slots", [])) != 8:
            raise ValueError("Unsupported Image Generation workspace.")
        return board

    def detail(self):
        with file_lock(self.lock), self.generator._lock:
            return self._detail(self._load())

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
        return {**board, "jobs": list(jobs.values()), "busy": busy, "empty_count": board["slots"].count(None)}

    def reserve_reconstruction(self, request_id, count):
        with file_lock(self.lock), self.generator._lock:
            board = self._load()
            indices = [i for i, value in enumerate(board["slots"]) if value is None][:count]
            if len(indices) != count:
                raise RenderSlotConflict("Not enough empty slots. Clear slots before reconstructing.")
            for child, position in enumerate(indices):
                board["slots"][position] = {"requestId": request_id, "index": child}
            board["imported_browser_state"] = True
            write_json_atomic(self.path, board)

    def selected_result(self, expected):
        """Resolve an exact completed selection in this universe, never a client path."""
        with file_lock(self.lock), self.generator._lock:
            board = self._load()
            position = board["selected_slot"]
            assignment = board["slots"][position] if position is not None else None
            if (not isinstance(expected, dict) or not assignment or assignment != expected
                    or type(expected.get("index")) is not int):
                raise RenderSlotConflict("The selected image changed. Select the current image and try again.")
            self.generator.status(assignment["requestId"])
            contents, _, provenance = self.generator.library_result(assignment["requestId"], assignment["index"])
            return contents, {"request_id": assignment["requestId"], "image_index": assignment["index"],
                              "asset_id": "", "label": "Selected Image Generation result",
                              "reconstruction": provenance.get("reconstruction", {})}

    def submit_reconstruction(self, request_id, inputs, expected_source=None):
        with file_lock(self.lock), self.generator._lock:
            if request_id in self.generator._jobs:
                return
            board = self._load()
            if expected_source is not None:
                selected = board["selected_slot"]
                if selected is None or board["slots"][selected] != expected_source:
                    raise RenderSlotConflict("The selected source changed during analysis. Start again.")
            children = {item["index"] for item in board["slots"] if item and item["requestId"] == request_id}
            if children != set(range(inputs["count"])):
                raise RenderSlotConflict("Reconstruction slots changed during analysis. Start a new reconstruction.")
            self.generator.submit(inputs, request_id=request_id)

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
            board = self._load()
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
                    inputs["count"] = len(indices)
                    request_id = uuid4().hex
                    # Save inputs and reservation before publishing asks. Crash recovery can
                    # display a failed reservation without assigning another job's output.
                    previous = deepcopy(board["slots"])
                    for child_index, position in enumerate(indices):
                        board["slots"][position] = {"requestId": request_id, "index": child_index}
                    board["imported_browser_state"] = True
                    write_json_atomic(self.path, board)
                    try:
                        self.generator.submit(inputs, request_id=request_id, seeds=seeds)
                    except Exception:
                        if request_id not in self.generator._jobs:
                            board["slots"] = previous
                            write_json_atomic(self.path, board)
                        raise
                else:
                    raise ValueError("Unknown Image Generation slot action.")
            board["imported_browser_state"] = True
            write_json_atomic(self.path, board)
            return self._detail(board)
