"""Minor Character collections and their shared image boards."""
from copy import deepcopy
from pathlib import Path
import random
from uuid import uuid4

from zet.services import image_candidate_board_service as board_policy
from zet.services import workflow_lock_journal
from zet.services.atomic_file_service import write_bytes_atomic
from zet.services.image_production_service import ImageProductionService
from zet.services.image_render_request import ImageRenderRequest, draft_upscale_request, verify_upscale_output
from zet.services.image_sizing_service import resolve_image_sizing
from zet.services.local_render_backend_service import LocalRenderBackendService
from zet.services.protected_effect_preview import ProtectedEffectsChanged
from zet.services.quick_character_wizard_service import (
    QuickCharacterWizardConflict, QuickCharacterWizardService,
)
from zet.services.render_slot_service import frozen_input, verify_input
from zet.services.workflow_storage import file_lock

VIEWS = {
    "STYLE": "Style Alignment", "FRONT": "Front",
    "FRONT_LEFT_3_4": "Front Left 3/4", "FRONT_RIGHT_3_4": "Front Right 3/4",
    "LEFT_PROFILE": "Left Profile", "RIGHT_PROFILE": "Right Profile",
}
FIELDS = ("appearance", "framing", "directions")
ACTIVE = {"SUBMITTING", "QUEUED", "RUNNING"}
CONSUMER = "zet-minor-collections"


class MinorCharacterNotFound(ValueError):
    pass


def empty_collection(sid, name):
    return {
        "session_id": sid, "character_id": sid, "name": name, "version": 2,
        "workflow_version": 2, "revision": 0, "source": None,
        "boards": {
            view: {
                "id": f"{sid}:{view}", "label": label, "fields": dict.fromkeys(FIELDS, ""),
                "prompt": "", "aspect_ratio": "2:3", "slots": [None] * board_policy.SLOT_COUNT,
                "candidates": {}, "selected_id": None,
            } for view, label in VIEWS.items()
        },
    }


class MinorCharacterService(QuickCharacterWizardService):
    """Use the existing session file location and file primitives."""

    def __init__(self, app, project_root):
        super().__init__(app, project_root)
        self.production = ImageProductionService(app)

    def _path(self, sid):
        return self._directory(sid) / "session.json"

    def _read(self, sid):
        if (self.root.parent / "minor-collection-migration.json").exists():
            raise QuickCharacterWizardConflict("Finish the offline Minor Character migration before opening collections.")
        if not self._path(sid).is_file():
            raise MinorCharacterNotFound("Minor Character was not found.")
        workflow_lock_journal.recover(self._path(sid), self.app.entity_library_service, self._write)
        value = super()._read(sid)
        if value.get("workflow_version") != 2:
            raise QuickCharacterWizardConflict("This Minor Character needs the offline collection migration.")
        return value

    def list_characters(self):
        rows = []
        for path in self.root.glob("*/session.json"):
            if len(path.parent.name) != 32 or any(c not in "0123456789abcdef" for c in path.parent.name):
                continue
            with self._lock(path.parent.name):
                try:
                    saved = super()._read(path.parent.name)
                except ValueError:
                    continue
                if saved.get("deleted_at") or saved.get("status") == "ABANDONED":
                    continue
                if saved.get("workflow_version") in (1, 2):
                    rows.append({"character_id": path.parent.name, "name": saved["name"],
                                 "needs_migration": saved["workflow_version"] == 1})
        return sorted(rows, key=lambda row: row["name"].casefold())

    def create_character(self, data):
        name = self._name(data.get("name"))
        with file_lock(self.root / "names.lock"):
            if any(row["name"].casefold() == name.casefold() for row in self.list_characters()):
                raise QuickCharacterWizardConflict("A Minor Character with that name already exists.")
            value = empty_collection(uuid4().hex, name)
            self._write(value)
            return self._public(value)

    @staticmethod
    def _name(name):
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Enter a Minor Character name.")
        return name.strip()

    def _public(self, value):
        public = deepcopy(value)
        public.pop("cleanup_pending", None)
        sid = value["session_id"]
        if public["source"]:
            public["source"]["url"] = f"/api/minor-characters/{sid}/source"
            public["source"].pop("file", None)
        for view, board in public["boards"].items():
            for item in board["candidates"].values():
                item.pop("image_path", None)
                item.pop("upscale_request", None)
                for index, entry in enumerate(item.get("render_request", {}).get("inputs", []), 1):
                    item["render_request"]["inputs"][index - 1] = {"role": entry.get("role", "Reference")}
            if board.get("text_job"):
                for key in ("baseline", "evidence", "feedback"):
                    board["text_job"].pop(key, None)
            if board.get("luna_review"):
                board["luna_review"].pop("images", None)
        return public

    def get_character(self, sid):
        with self._lock(sid):
            return self._public(self._read(sid))

    def _save(self, value):
        value["revision"] += 1
        self._write(value)

    def _check(self, value, data):
        if type(data.get("revision")) is not int or value["revision"] != data["revision"]:
            raise QuickCharacterWizardConflict("This collection changed. Refresh and try again.")

    def update_character(self, sid, data):
        with file_lock(self.root / "names.lock"), self._lock(sid):
            value = self._read(sid)
            self._check(value, data)
            if "name" in data:
                name = self._name(data["name"])
                if any(row["character_id"] != sid and row["name"].casefold() == name.casefold()
                       for row in self.list_characters()):
                    raise QuickCharacterWizardConflict("A Minor Character with that name already exists.")
                value["name"] = name
            if "source" in data:
                item = data["source"]
                contents, extension = self._image_bytes(item)
                relative = f"references/{uuid4().hex}.{extension}"
                write_bytes_atomic(self._directory(sid) / relative, contents)
                value["source"] = {"file": relative, "label": str(item.get("label") or "Source image")}
                self._mark_changed(value["boards"]["STYLE"])
            if "view" in data:
                board = self._board(value, data["view"])
                for key in FIELDS:
                    if key in data:
                        if not isinstance(data[key], str):
                            raise ValueError("Authoring fields must be text.")
                        board["fields"][key] = data[key]
                if "prompt" in data:
                    if not isinstance(data["prompt"], str):
                        raise ValueError("Prompt must be text.")
                    if board["prompt"] != data["prompt"]:
                        self._mark_changed(board)
                    board["prompt"] = data["prompt"]
                if "aspect_ratio" in data:
                    resolve_image_sizing(self.app.config, "draft", data["aspect_ratio"])
                    board["aspect_ratio"] = data["aspect_ratio"]
            self._save(value)
            return self._public(value)

    @staticmethod
    def _mark_changed(board):
        for item in board["candidates"].values():
            if item["status"] == "COMPLETE":
                item["source_change_fyi"] = True

    @staticmethod
    def _board(value, view):
        if view not in VIEWS:
            raise ValueError("Choose a Minor Character asset.")
        return value["boards"][view]

    def _owned_file(self, sid, relative):
        root = self._directory(sid).resolve()
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise MinorCharacterNotFound("This image is unavailable.")
        return path

    def _reference(self, value, view):
        sid = value["session_id"]
        if view == "STYLE":
            if not value["source"]:
                raise ValueError("Choose a source image for Style Alignment.")
            return self._owned_file(sid, value["source"]["file"]), "Original character reference"
        style = value["boards"]["STYLE"]
        item = style["candidates"].get(style["selected_id"], {})
        if not item.get("locked"):
            raise ValueError("Lock a Style Alignment image before preparing this view.")
        return self._owned_file(sid, item["image_path"]), "Locked Style Alignment"

    def source_image(self, sid):
        with self._lock(sid):
            return self._reference(self._read(sid), "STYLE")[0]

    def candidate_file(self, sid, view, cid, index=None):
        with self._lock(sid):
            board = self._board(self._read(sid), view)
            item = board_policy.validate_membership(board["slots"], board["candidates"], cid)
            if index is None:
                return self._owned_file(sid, item["image_path"])
            inputs = item.get("render_request", {}).get("inputs", [])
            if not 1 <= index <= len(inputs):
                raise MinorCharacterNotFound("Captured input was not found.")
            return self._owned_file(sid, inputs[index - 1]["path"])

    def owner(self, asset_id):
        row = self.app.entity_library_service.repository.fetchone("SELECT lock_owner FROM assets WHERE asset_id=?", (asset_id,))
        if row and row.get("lock_owner"):
            import json
            owner = json.loads(row["lock_owner"])
            if len(owner) == 3 and owner[0] == "minor":
                return owner[1]
        return None

    def _request(self, value, view, cid, mode, board, reference):
        preset = "comfyui-qwen-local-character-edit"
        preset_path = self.app.config.state_file(self.project_root, "Local_Render_Presets.json")
        profile = LocalRenderBackendService(preset_path, config=self.app.config).preset(preset)
        if not profile:
            raise ValueError("The reference image render profile is unavailable.")
        sizing = resolve_image_sizing(self.app.config, mode, board["aspect_ratio"])
        directory = self._directory(value["session_id"]) / "renders" / cid / "inputs"
        path, role = reference
        frozen = frozen_input(directory, board["prompt"], [{"path": str(path), "role": role}],
                              preset, render_sizing=sizing)
        settings = {**sizing, "profile": preset, "profile_snapshot": profile,
                    "checkpoint": profile["diffusion_model"], "disable_prompt_globals": True}
        return ImageRenderRequest(self.app.universe_id, board["id"], cid, frozen["prompt"],
                                  tuple(frozen["references"]), settings,
                                  random.SystemRandom().randrange(2**63 - 1),
                                  {"view": view, "source": str(path)}).to_dict()

    def generate(self, sid, view, data):
        with self._lock(sid):
            value = self._read(sid)
            self._check(value, data)
            board = self._board(value, view)
            reference = self._reference(value, view)
            mode = data.get("render_mode")
            if mode not in ("draft", "final") or not board["prompt"].strip():
                raise ValueError("Save a render prompt and choose Draft or Final.")
            slot = data.get("slot")
            positions = board_policy.allocate(board["slots"], board["candidates"], board["selected_id"],
                                              data.get("count", 1), slot, active=ACTIVE)
            if slot and board["slots"][slot - 1] != data.get("expected_candidate_id"):
                raise QuickCharacterWizardConflict("This slot changed.")
            prepared = []
            for pos in positions:
                cid = uuid4().hex
                request = self._request(value, view, cid, mode, board, reference)
                prepared.append({"id": cid, "candidate_id": cid, "slot": pos + 1, "locked": False,
                                 "render_mode": mode, "prompt": request["prompt"], "render_request": request,
                                 "image_path": "", "image": False})
            self._obsolete_review(board)
            for item in prepared:
                pos = item["slot"] - 1
                previous = board["slots"][pos]
                if previous:
                    self._remove(value, board, previous)
                board["slots"][pos] = item["id"]
                board["candidates"][item["id"]] = item
                self._reserve(item)
            self._save(value)
            for item in prepared:
                self._submit(value, view, item)
            self._cleanup(value)
            return self._public(value)

    @staticmethod
    def _reserve(item):
        item.update(status="SUBMITTING", attempt_id=uuid4().hex, ask_id="", output_path="", error="")
        item["reserved_ask_id"] = item["attempt_id"]
        board_policy.record_render_start(item)

    def _transport_owner(self, value, view, item):
        return {"universe_id": self.app.universe_id, "target_id": value["boards"][view]["id"],
                "candidate_id": item["id"], "attempt_id": item["attempt_id"],
                "consumer": CONSUMER, "slot": item["slot"], "session_id": value["session_id"], "view": view}

    def _submit(self, value, view, item):
        request = item.get("upscale_request") or item["render_request"]
        sid, attempt = value["session_id"], item["attempt_id"]
        root = self._directory(sid) / "renders" / item["id"] / "attempts" / attempt
        owner = self._transport_owner(value, view, item)
        try:
            verify_input({"references": request["inputs"]})
            staged = self.production.submit(request, manifest={
                "ask_id": attempt, "transport_job_id": attempt, "pipeline": "minor-character",
                "pipeline_stage": "ASSET_COLLECTION_RENDER", "image_production": owner,
                "render_sizing": {key: request["settings"][key] for key in
                                  ("render_mode", "aspect_ratio", "target_pixels", "width", "height")},
            }, prompt_path=root / "prompt.md", output_directory=root, consumer=CONSUMER)
            item.update(status="QUEUED", **{key: staged[key] for key in ("ask_id", "output_path")})
        except Exception as exc:
            if self.production.find_attempt(attempt, owner, attempt) is None:
                self._failed(item, str(exc))
        self._save(value)

    @staticmethod
    def _failed(item, error):
        item.update(status="COMPLETE" if item.pop("upscale_request", None) else "FAILED", error=error)

    def _remove(self, value, board, cid):
        removed = board_policy.remove(board, cid)
        pending = value.setdefault("cleanup_pending", [])
        pending.append(f"renders/{cid}")
        path = removed.get("image_path", "")
        if path.startswith("collection-import/"):
            pending.append(path)

    def _cleanup(self, value):
        pending = value.get("cleanup_pending", [])
        if pending:
            board_policy.cleanup(self._directory(value["session_id"]), pending)
            value.pop("cleanup_pending")
            self._write(value)

    def _refresh(self, value, view):
        board = self._board(value, view)
        sid = value["session_id"]
        changed = False
        for item in board["candidates"].values():
            if item["status"] not in ACTIVE:
                continue
            attempt = item["attempt_id"]
            root = self._directory(sid) / "renders" / item["id"] / "attempts" / attempt
            updates = self.production.reconcile(item, self._transport_owner(value, view, item), root, attempt)
            if updates["status"] == "COMPLETE":
                if item.get("upscale_request"):
                    from PIL import Image
                    try:
                        with Image.open(updates["image_path"]) as image:
                            verify_upscale_output(image, item["upscale_request"])
                    except (OSError, ValueError) as exc:
                        self._failed(item, str(exc))
                        changed = True
                        continue
                    item.pop("upscale_request")
                    item["render_mode"] = "final"
                updates["image"] = True
                board_policy.record_render_completion(item)
                self._obsolete_review(board)
            elif updates["status"] == "FAILED":
                self._failed(item, updates["error"])
                changed = True
                continue
            changed |= any(item.get(key) != val for key, val in updates.items())
            item.update(updates)
        if changed:
            self._save(value)
        self._cleanup(value)

    @staticmethod
    def _obsolete_review(board):
        review = board.get("luna_review")
        if review and review["status"] in {"RUNNING", "COMPLETE"}:
            review["status"] = "OBSOLETE"

    def progress(self, sid, view):
        with self._lock(sid):
            value = self._read(sid)
            self._refresh(value, view)
            board = self._board(value, view)
            return {"revision": value["revision"],
                    "candidates": {cid: row["status"] for cid, row in board["candidates"].items()},
                    "text": board.get("text_job", {}).get("status"),
                    "review": board.get("luna_review", {}).get("status")}

    def collect_background(self, ask_id, ask):
        owner = ask["image_production"]
        sid, view, cid = (owner[key] for key in ("session_id", "view", "candidate_id"))
        with self._lock(sid):
            value = self._read(sid)
            board = self._board(value, view)
            item = board["candidates"].get(cid)
            if (item and cid in board["slots"] and item.get("attempt_id") == ask_id
                    and owner == self._transport_owner(value, view, item)):
                self._refresh(value, view)
                return item["status"] not in ACTIVE
            return True

    def action(self, sid, view, cid, action, data):
        with self._lock(sid):
            value = self._read(sid)
            self._check(value, data)
            board = self._board(value, view)
            item = board_policy.validate_membership(board["slots"], board["candidates"], cid)
            if item["status"] in ACTIVE:
                raise QuickCharacterWizardConflict("Wait for the render to finish.")
            if action in {"select", "lock", "upscale"}:
                image = self._owned_file(sid, item["image_path"])
                if item["status"] != "COMPLETE":
                    raise ValueError("Choose a completed candidate.")
            if action == "select":
                board_policy.select(board, cid)
            elif action in {"lock", "unlock"}:
                if action == "lock":
                    board_policy.lock(board, cid)
                else:
                    if not item["locked"]:
                        raise ValueError("Choose the locked candidate.")
                    board_policy.unlock(board, cid)
                if view == "STYLE":
                    for key in VIEWS.keys() - {"STYLE"}:
                        self._mark_changed(value["boards"][key])
                self._publish(value, view, item, image if action == "lock" else None)
                return self._public(value)
            elif action == "clear":
                if item["locked"] or (board["selected_id"] == cid and data.get("confirm_selected") is not True):
                    raise ValueError("Unlock the candidate or confirm clearing its selection.")
                self._remove(value, board, cid)
                self._obsolete_review(board)
            elif action == "retry":
                board_policy.retry_request(board, cid)
                self._reserve(item)
            elif action == "upscale":
                root = self._directory(sid) / "renders" / cid / f"upscale-{uuid4().hex}"
                item["upscale_request"] = draft_upscale_request(self.app.config, board["id"], cid, item, image, root)
                self._reserve(item)
            else:
                raise ValueError("Choose a candidate action.")
            self._save(value)
            if item["status"] == "SUBMITTING":
                self._submit(value, view, item)
            self._cleanup(value)
            return self._public(value)

    def _publish(self, value, view, item, source):
        library = self.app.entity_library_service
        sid = value["session_id"]
        owner = library.lock_owner("minor", sid, view)
        value["revision"] += 1

        def change(operation_id, stage):
            if source is None:
                library.unbind_workflow_locks([owner], operation_id=operation_id, before_commit=stage)
                return

            def bind(asset):
                item["inventory_asset_id"] = asset["asset_id"]
                stage()

            library.bind_workflow_lock(owner, item["id"], source, origin="imagegen",
                label=f"{value['name']} · {VIEWS[view]}", prompt=item["prompt"],
                operation_id=operation_id, before_commit=bind)

        workflow_lock_journal.commit(self._path(sid), library, value, self._write, change)

    def bulk(self, sid, view, kind, data=None):
        with self._lock(sid):
            value = self._read(sid)
            board = self._board(value, view)
            if kind not in {"drafts", "non-selected"}:
                raise ValueError("Choose a bulk board action.")
            targets = [board["candidates"][cid] for cid in board["slots"] if cid and (
                board["candidates"][cid]["render_mode"] == "draft" if kind == "drafts"
                else cid != board["selected_id"] and not board["candidates"][cid]["locked"])]
            effects = [{"id": f"{item['id']}:{effect}", "label": f"Slot {item['slot']} {effect}",
                        "candidate_id": item["id"], "effect": effect}
                       for item in targets for effect, affected in (
                           ("selection", board["selected_id"] == item["id"]), ("lock", item["locked"]))
                       if affected]
            preview = {"revision": value["revision"], "slots": [item["slot"] for item in targets],
                       "protected_effects": effects}
            if data is None:
                return preview
            if data.get("revision") != preview["revision"] or set(data.get("approved_effects", [])) != {
                    effect["id"] for effect in effects}:
                raise ProtectedEffectsChanged(preview)
            if any(item["status"] in ACTIVE for item in targets):
                raise ValueError("Wait for the affected renders to settle.")
            for item in targets:
                self._remove(value, board, item["id"])
            self._obsolete_review(board)
            if any(item["locked"] for item in targets):
                self._publish(value, view, None, None)
            else:
                self._save(value)
            self._cleanup(value)
            return self._public(value)


    def _baseline(self, value, view):
        board = self._board(value, view)
        ref, _ = self._reference(value, view)
        from zet.services.universe_style_service import universe_style
        return {"fields": dict(board["fields"]), "prompt": board["prompt"], "reference": str(ref),
                "style": universe_style(self.app.config.base_library_path)["text"] if view == "STYLE" else ""}

    def text_action(self, sid, view, action, data):
        from zet.services.ai_workflow_service import AIWorkflowService
        with self._lock(sid):
            value = self._read(sid)
            self._check(value, data)
            board = self._board(value, view)
            if action == "apply":
                job = board.get("text_job", {})
                if job.get("id") != data.get("job_id") or job.get("status") != "COMPLETE" or not job.get("review"):
                    raise ValueError("Choose the current interview review.")
                if job["baseline"] != self._baseline(value, view):
                    raise QuickCharacterWizardConflict("Authoring inputs changed. Run a new interview.")
                from zet.services.narrative_interview_service import proposal_choices
                for row, choice in proposal_choices(job["review"]["proposals"], data.get("choices")):
                    if choice == "accept":
                        board["fields"][row["field"]] = row["text"]
                job.pop("review")
            elif action in {"interview", "write-prompt", "luna-review"}:
                field = "luna_review" if action == "luna-review" else "text_job"
                if board.get(field, {}).get("status") == "RUNNING":
                    raise QuickCharacterWizardConflict("This action is already running.")
                job = {"id": uuid4().hex, "status": "RUNNING", "action": action}
                if action == "luna-review":
                    job["images"] = {cid: row["image_path"] for cid, row in board["candidates"].items()
                                     if row["status"] == "COMPLETE" and row["image"]}
                    if not job["images"]:
                        raise ValueError("Generate at least one candidate before reviewing.")
                else:
                    job["baseline"] = self._baseline(value, view)
                    job["feedback"] = str(data.get("feedback") or "") if action == "interview" else ""
                    job["model"] = str(data.get("model") or "")
                    cid = data.get("candidate_id")
                    if cid and action == "interview":
                        item = board_policy.validate_membership(board["slots"], board["candidates"], cid)
                        if item["status"] != "COMPLETE":
                            raise ValueError("Choose a completed interview candidate.")
                        path = self._owned_file(sid, item["image_path"])
                        relative = f"interviews/{job['id']}{path.suffix}"
                        write_bytes_atomic(self._directory(sid) / relative, path.read_bytes())
                        job["evidence"] = relative
                board[field] = job
                self._save(value)
                try:
                    AIWorkflowService(self.app).submit(self.run_authoring_job, [sid, view, field, job["id"]],
                        service="minor_collection", key=job["id"], owner={"session_id": sid, "view": view})
                except Exception as exc:
                    job.update(status="FAILED", error=str(exc))
                    self._save(value)
                return self._public(value)
            else:
                raise ValueError("Choose an authoring action.")
            self._save(value)
            return self._public(value)

    def run_authoring_job(self, sid, view, field, job_id):
        from zet.services.ai_workflow_service import AIPending
        with self._lock(sid):
            value = self._read(sid)
            board = self._board(value, view)
            job = deepcopy(board.get(field, {}))
            if job.get("id") != job_id or job.get("status") != "RUNNING":
                return
            candidates = [deepcopy(board["candidates"][cid]) for cid in job.get("images", {})]
            for item in candidates:
                item["image_path"] = str(self._owned_file(sid, item["image_path"]))
        try:
            if field == "luna_review":
                from zet.services.local_image_ranking_service import review_images_with_luna
                entries, model, prompt = review_images_with_luna(
                    criteria=f"Rank these Minor Character {VIEWS[view]} candidates for identity, style and view accuracy.",
                    candidates=candidates, paths=self.app.ai_proxy_service.ai_proxy_path_service,
                    owner={"session_id": sid, "view": view, "luna_review_id": job_id})
                result = {"entries": entries, "model": model, "prompt": prompt}
            else:
                result = self._authoring_result(sid, view, job)
            status = "COMPLETE"
        except AIPending:
            raise
        except Exception as exc:
            status, result = "FAILED", {"error": str(exc)}
        with self._lock(sid):
            value = self._read(sid)
            board = self._board(value, view)
            current = board.get(field, {})
            if current.get("id") != job_id or current["status"] != "RUNNING":
                return
            if field == "text_job" and status == "COMPLETE":
                try:
                    unchanged = job["baseline"] == self._baseline(value, view)
                except ValueError:
                    unchanged = False
                if not unchanged:
                    status, result = "OBSOLETE", {"error": "Authoring inputs changed during this request."}
                elif "written_prompt" in result:
                    self._mark_changed(board)
                    board["prompt"] = result.pop("written_prompt")
            current.update(status=status, **result)
            self._save(value)

    def _authoring_result(self, sid, view, job):
        import json
        from zet.services.llm_role_service import resolve_role_model
        from zet.services.narrative_interview_service import field_replacement
        interview = job["action"] == "interview"
        role = "minor_interview" if interview else "minor_prompt"
        model = resolve_role_model(self.app.config, role, job["model"])
        baseline = job["baseline"]
        images = [baseline["reference"]]
        if job.get("evidence"):
            images.append(str(self._owned_file(sid, job["evidence"])))
        properties = {"prompt": {"type": "string"}}
        if interview:
            properties = {"proposals": {"type": "array", "items": {"type": "object",
                "properties": {"field": {"type": "string", "enum": list(FIELDS)},
                               "text": {"type": "string"}, "reason": {"type": "string"}},
                "required": ["field", "text", "reason"], "additionalProperties": False}}}
        schema = {"type": "object", "properties": properties, "required": list(properties),
                  "additionalProperties": False}
        context = {key: baseline[key] for key in ("fields", "prompt", "style")}
        context.update(asset=VIEWS[view], feedback=job["feedback"])
        system = ("Produce optional whole-field replacements, each with a reason." if interview else
                  "Write one complete image-editing prompt using the first image as the reference.")
        system += (" Preserve character identity, clothing and anatomical asymmetry except for requested changes."
                   " Follow the named view, using anatomical left/right. Style Alignment establishes the art style"
                   " without requiring a specific angle. Any second image is interview evidence only.")
        result, _ = self.app.ai_proxy_service.ai_proxy_path_service.jobs.generate_json(
            model, system, json.dumps(context), schema, images, role=role,
            owner={"session_id": sid, "view": view}, render_context={"operation": "edit"})
        if not interview:
            if not isinstance(result.get("prompt"), str) or not result["prompt"].strip():
                raise ValueError("The model returned an empty prompt.")
            return {"written_prompt": result["prompt"]}
        rows, seen = [], set()
        for proposal in result["proposals"]:
            field = proposal["field"]
            if field not in FIELDS or field in seen:
                raise ValueError("The interview proposed an invalid or duplicate field.")
            seen.add(field)
            row = field_replacement(proposal, baseline["fields"][field], job["id"], len(rows))
            if row:
                rows.append(row)
        return {"review": {"proposals": rows}}
