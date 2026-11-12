"""Universe-owned eight-slot board over persisted ad hoc render jobs."""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import json
from uuid import uuid4

from zet.services.atomic_file_service import write_json_atomic
from zet.services.render_slot_service import RenderSlotConflict, render_count
from zet.services.workflow_storage import file_lock, validate_image


class ImageGenerationWorkspace:
    def __init__(self, generator, asset_id=None):
        self.generator = generator
        self.asset_id = asset_id
        self.assets = generator.results_root / "assets"
        self.path = self.assets / f"{asset_id}.json" if asset_id else generator.results_root / "workspace.json"
        self.lock = generator.results_root / "workspace.lock"

    @contextmanager
    def locked(self):
        with file_lock(self.lock, shared=True), self.generator._lock:
            yield

    def _load(self, render_mode="draft"):
        if render_mode not in ("draft", "final"):
            raise ValueError("Render mode must be draft or final.")
        if self.asset_id:
            if not self.path.is_file():
                raise KeyError("Image Generation asset not found.")
            board = json.loads(self.path.read_text(encoding="utf-8"))
            if board.get("version") != 2 or board.get("asset_id") != self.asset_id or len(board.get("slots", [])) != 8:
                raise ValueError("Unsupported Image Generation asset.")
            return board
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
        if self.asset_id:
            board["revision"] += 1
        elif render_mode == "final":
            draft = self._load()
            draft["final_board"] = board
            board = draft
        write_json_atomic(self.path, board)

    def detail(self, render_mode="draft"):
        with self.locked():
            board = self._load(render_mode)
            return self._detail(board) if self.asset_id else {**self._detail(board), "render_mode": render_mode}

    def _detail(self, board):
        jobs = {}
        busy = False
        for assignment in board["slots"]:
            if not assignment:
                continue
            request_id = assignment["requestId"]
            if request_id not in jobs:
                try:
                    jobs[request_id] = (self.generator.workspace_status(request_id) if self.asset_id
                                        else self.generator.status(request_id))
                except KeyError:
                    pending = self.generator.reconstruction.pending(request_id)
                    jobs[request_id] = {"request_id": request_id, "status": pending.get("status", "FAILED"), "images": [],
                        "error": pending.get("error", "Render submission was interrupted. Clear this slot and generate again."),
                        "results": [], "prompt": pending.get("prompt", "")}
            busy |= self._active(assignment, {"jobs": [jobs[request_id]]})
        return {**{key: value for key, value in board.items() if key != "final_board"}, "jobs": list(jobs.values()), "busy": busy, "empty_count": board["slots"].count(None)}

    def reserve_reconstruction(self, request_id, count, render_mode="draft"):
        with self.locked():
            board = self._load(render_mode)
            indices = [i for i, value in enumerate(board["slots"]) if value is None][:count]
            if len(indices) != count:
                raise RenderSlotConflict("Not enough empty slots. Clear slots before reconstructing.")
            for child, position in enumerate(indices):
                board["slots"][position] = {"requestId": request_id, "index": child,
                    **({"quality": render_mode} if self.asset_id else {})}
            board["imported_browser_state"] = True
            self._save(board, render_mode)

    def selected_result(self, expected, render_mode=None):
        """Resolve an exact completed selection in this universe, never a client path."""
        with self.locked():
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
                    selected_mode = current.get("quality", mode)
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
        with self.locked():
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
            if not frozen_sizing and "render_mode" not in inputs and "width" in inputs and "height" in inputs:
                options["legacy_dimensions"] = True
            if self.asset_id:
                inputs = {**inputs, "ai_owner": {"image_generation_asset_id": self.asset_id}}
                options["candidate_board"] = {"asset_id": self.asset_id, "label": board["name"]}
            self.generator.submit(inputs, **options)

    def action(self, operation, payload):
        with self.locked():
            render_mode = payload.get("render_mode", "draft")
            board = self._load(render_mode)
            if self.asset_id:
                self._check_revision(board, payload)
            detail = self._detail(board)
            slot = payload.get("slot")
            index = render_count(slot) - 1 if slot is not None else None
            assignment = board["slots"][index] if index is not None else None
            if "expected_assignment" in payload and payload["expected_assignment"] != assignment:
                raise RenderSlotConflict("This slot changed. Review its current image before acting.")
            if operation == "unselect":
                if self.asset_id and (index is None or index != board["selected_slot"]):
                    raise RenderSlotConflict("The selection changed.")
                board["selected_slot"] = None
            elif operation == "select":
                if not assignment or not any(image["index"] == assignment["index"] for job in detail["jobs"] if job["request_id"] == assignment["requestId"] for image in job["images"]):
                    raise RenderSlotConflict("Select a completed image.")
                if self.asset_id:
                    self.generator.image(assignment["requestId"], assignment["index"])
                board["selected_slot"] = index
            else:
                if self.asset_id and index is not None and self._active(assignment, detail):
                    raise RenderSlotConflict("Wait for this render to settle.")
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
                        inputs = deepcopy(board["inputs"] if self.asset_id else payload.get("inputs") or {})
                        seeds = None
                    else:
                        job = (self.generator._read_saved_job(assignment["requestId"]) if self.asset_id
                               else self.generator._jobs.get(assignment["requestId"]))
                        if not job or not job.get("render_payload"):
                            raise RenderSlotConflict("Saved render inputs are unavailable. Clear this slot and generate again.")
                        child = next((child for child in job["children"] if child["index"] == assignment["index"]), None)
                        if operation == "retry" and (any(image["index"] == assignment["index"] for image in self.generator.status(job["request_id"])["images"]) or (child and not child.get("error"))):
                            raise RenderSlotConflict("Retry requires a failed render.")
                        indices = [index]
                        inputs = deepcopy(board["inputs"] if self.asset_id else payload.get("inputs") or job["render_payload"]) if operation == "regenerate" else deepcopy(job["render_payload"])
                        if operation == "regenerate" and not job.get("render_sizing") and "width" in inputs and "height" in inputs:
                            inputs.setdefault("aspect_ratio", f"{inputs.pop('width')}:{inputs.pop('height')}")
                            inputs.setdefault("render_mode", render_mode)
                        if job.get("reconstruction") and "reconstruction" not in inputs and (not self.asset_id or operation == "retry"):
                            inputs["reconstruction"] = deepcopy(job["reconstruction"])
                        seeds = [child["seed"]] if operation == "retry" and child and "seed" in child else None
                    if operation != "retry" and "render_mode" in payload:
                        inputs["render_mode"] = render_mode
                    if self.asset_id and operation != "retry":
                        inputs.setdefault("aspect_ratio", "1:1")
                        inputs["reference_images"] = [ref for ref in inputs.get("reference_images", []) if ref.get("image")]
                    inputs["count"] = len(indices)
                    request_id = uuid4().hex
                    # Save inputs and reservation before publishing asks. Crash recovery can
                    # display a failed reservation without assigning another job's output.
                    previous = deepcopy(board["slots"])
                    for child_index, position in enumerate(indices):
                        board["slots"][position] = {"requestId": request_id, "index": child_index,
                            **({"quality": assignment["quality"] if operation == "retry" else render_mode} if self.asset_id else {})}
                    board["imported_browser_state"] = True
                    self._save(board, render_mode)
                    try:
                        submit_options = {"request_id": request_id, "seeds": seeds}
                        if self.asset_id:
                            inputs["ai_owner"] = {"image_generation_asset_id": self.asset_id}
                            submit_options["candidate_board"] = {"asset_id": self.asset_id, "label": board["name"]}
                        if operation == "retry" and job.get("render_sizing"):
                            submit_options["frozen_sizing"] = job["render_sizing"]
                        if operation == "retry" and not job.get("render_sizing"):
                            submit_options["legacy_dimensions"] = True
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
            return self._detail(board) if self.asset_id else {**self._detail(board), "render_mode": render_mode}

    def asset(self, asset_id):
        if not isinstance(asset_id, str) or len(asset_id) != 32 or any(c not in "0123456789abcdef" for c in asset_id):
            raise KeyError("Image Generation asset not found.")
        return ImageGenerationWorkspace(self.generator, asset_id)

    @contextmanager
    def standalone_request(self, request_id):
        with self.locked():
            if any(item and item["requestId"] == request_id
                   for path in self.assets.glob("*.json") if len(path.stem) == 32
                   for item in self.asset(path.stem)._load()["slots"]):
                raise RenderSlotConflict("Manage this image through its Image Generation asset.")
            yield

    @staticmethod
    def _check_revision(board, payload):
        if type(payload.get("expected_revision")) is not int or payload["expected_revision"] != board["revision"]:
            raise RenderSlotConflict("This asset changed. Refresh before applying changes.")

    @staticmethod
    def _active(assignment, detail):
        if assignment is None:
            return False
        job = next(job for job in detail["jobs"] if job["request_id"] == assignment["requestId"])
        child = next((child for child in job["results"] if child["index"] == assignment["index"]), None)
        return (child or job)["status"] in {"QUEUED", "RUNNING", "DISPATCHING"}

    @staticmethod
    def _name(value):
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > 160:
            raise ValueError("Enter an asset name of 1 to 160 characters.")
        return value.strip()

    @staticmethod
    def _inputs(value):
        from base64 import b64decode

        if not isinstance(value, dict):
            raise ValueError("Invalid generation inputs.")
        keys = {"mode", "prompt", "negative_prompt", "aspect_ratio", "reference_images",
                "render_config", "source_asset_id", "source_checksum", "universe_style_variant",
                "universe_style", "managed_style", "reconstruction"}
        inputs = {key: item for key, item in value.items() if key in keys}
        refs = inputs.get("reference_images", [])
        if not isinstance(refs, list) or len(refs) > 10:
            raise ValueError("Choose no more than 10 reference images.")
        for ref in refs:
            if not isinstance(ref, dict):
                raise ValueError("Invalid reference image.")
            encoded = ref.get("image") or ""
            if not isinstance(encoded, str) or len(encoded) > 28 * 1024 * 1024:
                raise ValueError("Reference images must be 20 MiB or smaller.")
            if encoded:
                image = b64decode(encoded.split(",", 1)[-1], validate=True)
                if len(image) > 20 * 1024 * 1024:
                    raise ValueError("Reference images must be 20 MiB or smaller.")
                validate_image(image)
        return inputs

    def _create(self, asset_id, name, inputs=None, slots=None, selected=None):
        self.assets.mkdir(parents=True, exist_ok=True)
        target = self.asset(asset_id)
        board = {"version": 2, "asset_id": asset_id, "revision": 0, "name": name,
                 "inputs": inputs or {}, "slots": slots or [None] * 8, "selected_slot": selected,
                 "authoring": {}, "refinement": {}}
        write_json_atomic(target.path, board)
        return board

    def _migrate(self):
        from uuid import NAMESPACE_URL, uuid5

        marker = self.assets / "legacy-migrated.json"
        if marker.exists() or not self.path.exists():
            return
        boards = [self._load(mode) for mode in ("draft", "final")]
        slots = [[{**item, "quality": mode} if item else None for item in board["slots"]]
                 for mode, board in zip(("draft", "final"), boards)]
        selections = [board["selected_slot"] for board in boards]
        count = sum(item is not None for group in slots for item in group)
        def recover(key, name, items, selected):
            asset_id = uuid5(NAMESPACE_URL, f"zet/image-generation/legacy/{key}").hex
            if not self.asset(asset_id).path.exists():
                self._create(asset_id, name, slots=items, selected=selected)
        if count and count <= 8 and selections.count(None) >= 1:
            occupied = [(quality, i, item) for quality, group in enumerate(slots)
                        for i, item in enumerate(group) if item]
            selected = next((i for i, (q, index, _) in enumerate(occupied) if selections[q] == index), None)
            recover("mixed", "Recovered Image Generation", [item for _, _, item in occupied] + [None] * (8-count), selected)
        elif count:
            for i, mode in enumerate(("Draft", "Final")):
                if any(slots[i]):
                    recover(mode, f"Recovered {mode}", slots[i], selections[i])
        self.assets.mkdir(parents=True, exist_ok=True)
        write_json_atomic(marker, {"version": 1})

    def list_assets(self):
        with self.locked():
            self._migrate()
            records = []
            for path in self.assets.glob("*.json"):
                if len(path.stem) != 32:
                    continue
                board = self.asset(path.stem)._load()
                index = board["selected_slot"]
                selected = board["slots"][index] if index is not None else None
                records.append({"asset_id": board["asset_id"], "name": board["name"],
                                "revision": board["revision"], "selected": selected})
            return sorted(records, key=lambda record: (record["name"].casefold(), record["asset_id"]))

    def create_asset(self, name, inputs=None, recovery_id=None):
        from uuid import NAMESPACE_URL, uuid5

        with self.locked():
            self._migrate()
            asset_id = uuid5(NAMESPACE_URL, f"zet/image-generation/browser/{recovery_id}").hex if recovery_id else uuid4().hex
            target = self.asset(asset_id)
            if target.path.exists():
                return target._load()
            return self._create(asset_id, self._name(name), self._inputs(inputs or {}))

    def update_asset(self, payload):
        with self.locked():
            board = self._load()
            self._check_revision(board, payload)
            if "name" in payload:
                board["name"] = self._name(payload["name"])
            if "inputs" in payload:
                board["inputs"] = self._inputs(payload["inputs"])
            for key in ("authoring", "refinement"):
                if key in payload:
                    if not isinstance(payload[key], dict):
                        raise ValueError("Invalid saved prompt state.")
                    board[key] = {**board[key], **payload[key]}
            self._save(board)
            return self._detail(board)

    def progress(self):
        with self.locked():
            detail = self._detail(self._load())
            return {"revision": detail["revision"], "busy": detail["busy"], "jobs": [
                {key: job[key] for key in ("request_id", "status", "results", "error")} for job in detail["jobs"]]}

    def publish(self, operation, payload):
        with self.locked():
            board = self._load()
            index = render_count(payload["slot"]) - 1
            assignment = board["slots"][index]
            if not assignment or assignment != payload.get("expected_assignment"):
                raise RenderSlotConflict("The candidate changed. Review the current image.")
            request_id, child = assignment["requestId"], assignment["index"]
            self.generator.status(request_id)
            if operation == "inventory-update":
                return {"asset": self.generator.apply_to_source(request_id, child)}
            return self.generator.import_into_library(request_id, child, payload)

    def bulk(self, operation, payload, *, preview=False):
        with self.locked():
            board = self._load()
            detail = self._detail(board)
            selected = board["selected_slot"]
            slots = [i for i, item in enumerate(board["slots"]) if item and (
                operation == "delete-asset" or
                operation == "delete-drafts" and item["quality"] == "draft" or
                operation == "delete-non-selected" and i != selected)]
            active = [i for i in slots if self._active(board["slots"][i], detail)]
            if operation != "delete-drafts" and (active or operation == "delete-asset" and
                    self._analysis_active(board)):
                raise RenderSlotConflict("Wait for active work to settle.")
            effects = [{"id": str(i + 1), "label": f"Selected image in slot {i + 1}",
                        "image_url": f"/api/image-generation/jobs/{board['slots'][i]['requestId']}/images/{board['slots'][i]['index']}"}
                       for i in slots if i == selected]
            result = {"revision": board["revision"], "slots": [i + 1 for i in slots],
                      "active_slots": [i + 1 for i in active], "effects": effects}
            if preview:
                return result
            self._check_revision(board, payload)
            if payload.get("preview") != result or payload.get("approved") != [effect["id"] for effect in effects]:
                raise RenderSlotConflict("Deletion effects changed. Review them again.")
            if operation == "delete-asset":
                self.path.unlink()
                return {"deleted": True}
            retained = {item["requestId"] for i, item in enumerate(board["slots"]) if item and i not in slots}
            for path in self.assets.glob("*.json"):
                if path == self.path or len(path.stem) != 32:
                    continue
                other = self.asset(path.stem)._load()
                retained.update(item["requestId"] for item in other["slots"] if item)
            for request_id in {board["slots"][i]["requestId"] for i in active} - retained:
                job = self.generator._read_saved_job(request_id)
                if job is not None:
                    self.generator.cancel_owned_request(request_id, {"image_generation_asset_id": self.asset_id})
            for i in slots:
                board["slots"][i] = None
            if selected in slots:
                board["selected_slot"] = None
            self._save(board)
            return self._detail(board)

    def _analysis_active(self, board):
        job_id = board["authoring"].get("job_id")
        return job_id and self.generator.reconstruction.pending(job_id).get("status") == "RUNNING"
