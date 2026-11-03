"""Named, ongoing character workspaces over the shared wizard render engine."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import uuid4, uuid5, NAMESPACE_URL

from zet.services.llm_role_service import resolve_role_model
from zet.services.image_reconstruction_contract import fingerprint, text
from zet.services.quick_character_wizard_service import (
    QuickCharacterWizardService, QuickCharacterWizardError, QuickCharacterWizardConflict, _LOCK, _ACTIVE,
)
from zet.services.workflow_storage import file_lock
from zet.services.minor_character_workflow_service import MinorCharacterWorkflow

_REVIEW_ACTIVE = set()


class MinorCharacterNotFound(QuickCharacterWizardError):
    pass


class MinorCharacterService(MinorCharacterWorkflow, QuickCharacterWizardService):
    INPUTS = ("references", "primary_reference_id", "universe_style_variant", "style_mode", "preserve", "changes", "model",
              "notes", "framing", "side", "description", "identity", "proposals", "answers",
              "reconstruction_id", "target_hash")
    ANALYSIS_INPUTS = ("references", "primary_reference_id", "universe_style_variant", "style_mode", "preserve", "changes", "model", "notes")

    @staticmethod
    def name_key(name):
        return str(name).strip().casefold()

    def _read(self, sid):
        with self._lock(sid):
            value = super()._read(sid)
        if value.get("workflow_version") != 1:
            raise QuickCharacterWizardError("This workspace belongs to the retired workflow. Create a new Minor Character.")
        for view in self._views(value):
            value["boards"].setdefault(view, self._empty_board(value, view))
            value.setdefault("final_boards", {}).setdefault(view, self._empty_board(value, view, "final"))
        value.setdefault("final_selected", {})
        value.setdefault("final_locked", {})
        return value

    def _write(self, session):
        with self._lock(session["session_id"]):
            super()._write(session)

    def _records(self):
        records = []
        for path in self.root.glob("*/session.json"):
            try:
                value = self._read(path.parent.name)
                if not value.get("deleted_at") and value["status"] != "ABANDONED":
                    records.append(value)
            except (QuickCharacterWizardError, KeyError, TypeError):
                continue
        return records

    def _canonical(self, sid):
        record = self._read(sid)
        if record.get("deleted_at"):
            raise MinorCharacterNotFound("This Minor Character has been deleted.")
        return record

    def _public(self, session):
        value = super()._public(session)
        value["character_id"] = value["session_id"]
        for ref in value["references"]:
            ref["url"] = f"/api/minor-characters/{value['session_id']}/references/{ref['reference_id']}"
        for key, mode in (("locked", "draft"), ("final_locked", "final")):
            for view, locked in value.get(key, {}).items():
                locked["image_url"] = f"/api/minor-characters/{value['session_id']}/locked/{view}?render_mode={mode}"
        return value

    @staticmethod
    def _delete_character_preview(records):
        effects = []
        for record in records:
            for mode, selected_key, lock_key in (("draft", "selected", "locked"),
                                                  ("final", "final_selected", "final_locked")):
                for view, candidate_id in (record.get(selected_key) or {}).items():
                    effects.append({"id": f"unselect:{record['session_id']}:{mode}:{view}:{candidate_id}",
                                    "label": f"Unselect {mode.title()} {view} ({candidate_id})"})
                for view, locked in (record.get(lock_key) or {}).items():
                    if locked.get("candidate_id"):
                        effects.append({"id": f"unlock:{record['session_id']}:{mode}:{view}:{locked['candidate_id']}",
                                        "label": f"Hide locked {mode.title()} {view} ({locked['candidate_id']})"})
        token = hashlib.sha256(json.dumps(records, sort_keys=True, default=str).encode()).hexdigest()
        return {"protected_effects": effects, "confirmation_token": token}

    def preview_delete_character(self, sid):
        with file_lock(self.root / "names.lock"):
            record = self._canonical(sid)
            ids = sorted(r["session_id"] for r in self._records()
                         if self.name_key(r["name"]) == self.name_key(record["name"]))
            from contextlib import ExitStack
            with ExitStack() as locks:
                for target in ids:
                    locks.enter_context(self._lock(target))
                return self._delete_character_preview([self._read(target) for target in ids])

    def delete_character(self, sid, data=None):
        with file_lock(self.root / "names.lock"):
            record = self._canonical(sid)
            records = self._records()
            ids = sorted(r["session_id"] for r in records if self.name_key(r["name"]) == self.name_key(record["name"]))
            from contextlib import ExitStack
            with ExitStack() as locks:
                for target in ids:
                    locks.enter_context(self._lock(target))
                current_records = [self._read(target) for target in ids]
                preview = self._delete_character_preview(current_records)
                data = data or {}
                if data.get("confirmation_token") != preview["confirmation_token"]:
                    from zet.services.protected_effect_preview import ProtectedEffectsChanged
                    raise ProtectedEffectsChanged(preview)
                approved = data.get("approved_effects")
                if not isinstance(approved, list) or set(approved) != {effect["id"] for effect in preview["protected_effects"]}:
                    raise QuickCharacterWizardError("Approve each selected or locked image affected by deletion.")
                for target in ids:
                    current = self._read(target)
                    current.update(deleted_at=self._now(), status="ABANDONED",
                        job={"kind": "delete", "status": "COMPLETE", "error": ""})
                    self._write(current)
        return {"deleted": True, "character_id": record["session_id"]}

    @staticmethod
    def _deleted_candidate(session, candidate_id):
        return bool(candidate_id) and candidate_id not in MinorCharacterWorkflow._working_ids(session)

    def list_characters(self):
        records = self._records()
        grouped = {}
        for record in sorted(records, key=lambda s: (s.get("updated_at", ""), s["session_id"])):
            grouped[self.name_key(record["name"])] = record
        result = []
        for record in grouped.values():
            locked = {view: {**item, "image_url": f"/api/minor-characters/{record['session_id']}/locked/{view}?render_mode={mode}"}
                      for key, mode in (("locked", "draft"), ("final_locked", "final"))
                      for view, item in (record.get(key) or {}).items()}
            result.append({"character_id": record["session_id"], "name": record["name"], "locked": locked})
        return sorted(result, key=lambda s: self.name_key(s["name"]))

    def list_sessions(self):
        return [self.get_character(c["character_id"]) for c in self.list_characters()]

    def get_character(self, sid):
        canonical = self._canonical(sid)
        value = super().get_session(canonical["session_id"])
        with self._lock(canonical["session_id"]):
            record = self._read(canonical["session_id"])
            interrupted = False
            reviewing_ids = [candidate["candidate_id"] for candidate in record["candidates"]
                             if candidate["status"] == "REVIEWING"]
            with _LOCK:
                active_ids = {candidate_id for candidate_id in reviewing_ids
                              if (self._key(canonical["session_id"]), candidate_id) in _REVIEW_ACTIVE}
                pending = bool(reviewing_ids) and self._pending_workflow(canonical["session_id"])
            for candidate in record["candidates"]:
                reviewing = candidate["candidate_id"] in active_ids or pending
                if candidate["status"] == "REVIEWING" and not reviewing:
                    candidate.update(status="REVIEW_FAILED", error="Suggestions were interrupted. You can continue with this image.")
                    interrupted = True
            if interrupted:
                self._write(record)
                value = self._public(record)
        return value

    def get_session(self, sid):
        return self.get_character(sid)

    def _busy(self, session):
        with _LOCK:
            active = self._key(session["session_id"]) in _ACTIVE
        working = self._working_ids(session)
        return active or (session["job"]["kind"] == "draft" and session["job"]["status"] == "RUNNING") or any(
            c["status"] in {"QUEUING", "QUEUED", "RUNNING"} and c["candidate_id"] in working
            for c in session["candidates"])

    def _start_review(self, sid, candidate_id):
        session = self._read(sid)
        if session.get("deleted_at") or self._deleted_candidate(session, candidate_id):
            candidate = next(c for c in session["candidates"] if c["candidate_id"] == candidate_id)
            candidate["status"] = "READY"
            if session["job"]["kind"] == "review":
                session["job"]["status"] = "COMPLETE"
            self._write(session)
            return
        candidate = next(c for c in session["candidates"] if c["candidate_id"] == candidate_id)
        self._review_harvest(sid, candidate)
        session["job"] = {"kind": "review", "status": "COMPLETE", "error": ""}
        session["status"] = "REVIEW_READY"
        key = (self._key(sid), candidate_id)
        self._write(session)
        with _LOCK:
            _REVIEW_ACTIVE.add(key)

        def review():
            try:
                self._review_job(sid, candidate_id)
            except Exception as exc:
                from zet.services.storage_health_service import pause_on_storage_error
                pause_on_storage_error(self.app.config, exc)
                with self._lock(sid):
                    current = self._read(sid)
                    candidate = next(c for c in current["candidates"] if c["candidate_id"] == candidate_id)
                    candidate.update(status="REVIEW_FAILED", error="Suggestions unavailable: " + str(exc))
                    self._write(current)
            finally:
                with _LOCK:
                    _REVIEW_ACTIVE.discard(key)
        from zet.services.ai_workflow_service import AIWorkflowService
        workflow_key = uuid5(NAMESPACE_URL, f"minor-review:{self.app.universe_id}:{sid}:{candidate_id}:{candidate['sha256']}").hex
        try:
            AIWorkflowService(self.app).submit(self._review_job, [sid, candidate_id], service="minor", key=workflow_key, initial=review)
        finally:
            with _LOCK:
                _REVIEW_ACTIVE.discard(key)

    def create_character(self, payload):
        name = text(payload.get("name", ""), "Character name").strip()
        if not name:
            raise QuickCharacterWizardError("Enter a Minor Character name.")
        self.root.mkdir(parents=True, exist_ok=True)
        with file_lock(self.root / "names.lock"):
            match = next((c for c in self.list_characters() if self.name_key(c["name"]) == self.name_key(name)), None)
            if match:
                return {**self.get_character(match["character_id"]), "existing": True}
            sid = uuid4().hex
            record = {"session_id": sid, "name": name, "version": 2, "minor_character": True,
                "notes": "", "style_mode": "universe", "preserve": "Preserve original identity, hair silhouette and length, body build and visible costume except requested changes.",
                "changes": "", "model": resolve_role_model(self.app.config, "character_description"), "model_explicit": False,
                "framing": "full_body", "side": "left", "references": [], "description": "", "identity": "",
                "observations": [], "proposals": [], "proposals_approved": True, "questions": [], "answers": [],
                "revision_id": uuid4().hex, "candidates": [], "selected": {}, "locked": {}, "status": "DRAFT_READY",
                "needs_analysis": True, "primary_reference_id": "", "comparison_reference_id": "",
                "job": {"kind": "draft", "status": "COMPLETE", "error": ""}, "created_at": self._now(), "publication": None}
            self._initialize_workflow(record)
            self._write(record)
            return self._public(record)

    def create_session(self, payload):
        value = self.create_character(payload)
        if value.get("existing"):
            return value
        value = self.update_character(value["session_id"], {"style_mode": "preserve_source", **payload})
        primary = payload.get("primary_index", 0)
        if type(primary) is int and 0 <= primary < len(value["references"]):
            value = self.update_character(value["session_id"], {"primary_reference_id": value["references"][primary]["reference_id"]})
        return self.analyze(value["session_id"])

    def _signature(self, session):
        return fingerprint({key: session.get(key) for key in self.ANALYSIS_INPUTS})

    def _snapshot(self, session):
        return json.loads(json.dumps({key: session[key] for key in self.INPUTS if key in session}))

    def update_character(self, sid, payload):
        current = self._canonical(sid)
        sid = current["session_id"]
        rename_requested = "name" in payload and self.name_key(payload["name"]) != self.name_key(current["name"])
        with file_lock(self.root / "names.lock"):
            records = self._records()
            if rename_requested:
                return self._update_character(sid, payload, records)
        return self._update_character(sid, payload, [])

    def _update_character(self, sid, payload, workspace_records):
        with self._lock(sid):
            session = self._read(sid)
            previous_name = session["name"]
            before = self._signature(session)
            name = text(payload.get("name", session["name"]), "Character name").strip()
            if not name:
                raise QuickCharacterWizardError("Enter a Minor Character name.")
            duplicate = next((c for c in workspace_records if c["session_id"] != sid and self.name_key(c["name"]) == self.name_key(name)
                              and self.name_key(c["name"]) != self.name_key(previous_name)), None)
            if duplicate:
                raise QuickCharacterWizardConflict("A Minor Character named " + duplicate["name"] + " already exists. Open it or choose another name.")
            session["name"] = name
            for key in ("notes", "preserve", "changes", "description", "identity"):
                if key in payload:
                    session[key] = text(payload[key], key)
            for key, allowed in (("framing", {"full_body", "portrait"}), ("side", {"left", "right"}),
                                 ("style_mode", {"universe", "preserve_source"}),
                                 ("universe_style_variant", {"canonical", "environmental"})):
                if key in payload:
                    if payload[key] not in allowed:
                        raise QuickCharacterWizardError("Choose a valid " + key + ".")
                    session[key] = payload[key]
            if session["style_mode"] == "preserve_source":
                session.pop("reconstruction_id", None)
                session.pop("target_hash", None)
            if "model" in payload:
                model = text(payload["model"], "Model")
                if model not in self.reconstruction_options()["models"]:
                    raise QuickCharacterWizardError("Choose an available analysis model.")
                session["model"] = model
                session["model_explicit"] = True
            if "proposals" in payload:
                if not isinstance(payload["proposals"], list) or any(not isinstance(p, str) for p in payload["proposals"]):
                    raise QuickCharacterWizardError("Proposed details must be text.")
                session["proposals"] = payload["proposals"]
            if "references" in payload:
                refs = payload["references"]
                if not isinstance(refs, list) or len(refs) > 3 or any(not isinstance(r, dict) for r in refs):
                    raise QuickCharacterWizardError("Use up to three reference images.")
                old = {r["reference_id"]: r for r in session["references"]}
                next_index = max((r["index"] for r in session["references"]), default=-1) + 1
                records = []
                for ref in refs:
                    if ref.get("reference_id") in old and not ref.get("image"):
                        record = dict(old[ref["reference_id"]])
                    else:
                        data, extension = self._image_bytes(ref)
                        rid = uuid4().hex
                        filename = f"references/{rid}.{extension}"
                        path = self._directory(sid) / filename
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(data)
                        record = {"reference_id": rid, "index": next_index, "filename": filename,
                                  "asset_id": str(ref.get("asset_id") or ""), "checksum": hashlib.sha256(data).hexdigest(),
                                  "managed_checksum": ref.get("managed_checksum", "")}
                        next_index += 1
                    record["caption"] = text(ref.get("caption", record.get("caption", "Identity and appearance reference")), "Caption") or "Identity and appearance reference"
                    records.append(record)
                if len({r["reference_id"] for r in records}) != len(records):
                    raise QuickCharacterWizardError("Each reference must be distinct.")
                session["references"] = records
            ids = [r["reference_id"] for r in session["references"]]
            for key in ("primary_reference_id", "comparison_reference_id"):
                requested = payload.get(key, session.get(key))
                session[key] = requested if requested in ids else (ids[0] if ids else "")
            for key in ("active_view", "preview_candidate_id"):
                if key in payload:
                    session[key] = text(payload[key], key)
            if "board_edit" in payload:
                edit = payload["board_edit"]
                board = self._board(session, edit["view"], edit["revision"], edit.get("render_mode", "draft"))
                self._edit_board(board, edit)
                board["revision"] += 1
            if before != self._signature(session):
                session["needs_analysis"] = True
                for candidate in session.get("candidates") or []:
                    locks = session.get("final_locked" if candidate.get("render_mode") == "final" else "locked") or {}
                    locked_id = (locks.get(candidate.get("view")) or {}).get("candidate_id")
                    inputs = candidate.get("inputs") or {}
                    if ((not locked_id or locked_id == candidate.get("candidate_id"))
                            and candidate.get("filename") and not candidate.get("source_change_fyi")
                            and any(key in inputs and inputs[key] != session.get(key)
                                    for key in self.ANALYSIS_INPUTS)):
                        candidate["source_change_fyi"] = True
            if self._busy(session) and session["job"]["kind"] == "draft" and any(k in payload for k in ("description", "identity", "proposals")):
                session["description_override"] = {k: session[k] for k in ("description", "identity", "proposals")}
            elif session.get("reconstruction_id") and not session["needs_analysis"] and any(k in payload for k in ("description", "identity", "proposals")):
                job = self._reconstruction().revise(session["reconstruction_id"], session["description"], session["identity"], session["proposals"])
                session.update(reconstruction_id=job["id"], target_hash=job["target_hash"])
            session["proposals_approved"] = True
            self._write(session)
            return self._public(session)

    def update_draft(self, sid, revision_id, payload):
        return self.update_character(sid, payload)

    def _draft_session(self, sid):
        session = self._read(sid)
        return {**session, **session.get("analysis_inputs", {})}

    def analyze(self, sid, pending=None, answers=None):
        sid = self._canonical(sid)["session_id"]
        return self._analyze(sid, pending, answers)

    def _analyze(self, sid, pending=None, answers=None):
        with self._lock(sid):
            session = self._read(sid)
            if self._busy(session):
                raise QuickCharacterWizardConflict("An image task is already running.")
            if not session["references"]:
                raise QuickCharacterWizardError("Add at least one reference image.")
            if answers is not None:
                session["answers"] = answers
            if pending and pending.get("render_mode", "draft") == "draft":
                pending = {**pending, "_cleanup_epoch": (session.get("draft_cleanup_epochs") or {}).get(pending["view"], 0)}
            session.update(analysis_inputs=self._snapshot(session), status="DRAFTING",
                           job={"kind": "draft", "status": "RUNNING", "error": ""})
            self._write(session)
            self._submit(sid, self._analyze_then_render, session["revision_id"], self._signature(session), pending)
            return self._public(session)

    def generate_draft(self, sid, revision_id, answers=None):
        return self.analyze(sid, answers=answers)

    def _analyze_then_render(self, sid, revision_id, signature, pending):
        from zet.services.ai_workflow_service import current_workflow
        context = current_workflow.get()
        continuation_id = context["id"] if context else ""
        previous = self._read(sid).get("analysis_continuation") or {}
        if continuation_id and previous.get("id") == continuation_id:
            if previous.get("candidate_id"):
                self._render_job(sid, previous["candidate_id"], (pending or {}).get("item_ids"))
            return
        super()._draft_job(sid, revision_id)
        with self._lock(sid):
            session = self._read(sid)
            if session.get("deleted_at"):
                return
            session["needs_analysis"] = signature != self._signature(session)
            overrides = session.pop("description_override", None)
            if overrides:
                session.update(overrides)
                if session.get("reconstruction_id"):
                    job = self._reconstruction().revise(session["reconstruction_id"], session["description"], session["identity"], session["proposals"])
                    session.update(reconstruction_id=job["id"], target_hash=job["target_hash"])
            session.pop("analysis_inputs", None)
            session["proposals_approved"] = True
            if pending and "_cleanup_epoch" in pending:
                pending = dict(pending)
                epoch = pending.pop("_cleanup_epoch")
                if epoch != (session.get("draft_cleanup_epochs") or {}).get(pending["view"], 0):
                    pending = None
            if pending and not session["needs_analysis"] and not self._deleted_candidate(session, pending.get("candidate_id")):
                candidate = self._new_candidate(session, **pending)
            else:
                candidate = None
            if continuation_id:
                session["analysis_continuation"] = {"id": continuation_id, "candidate_id": candidate["candidate_id"] if candidate else ""}
            self._write(session)
        if candidate:
            self._render_job(sid, candidate["candidate_id"], pending["item_ids"])

    def _draft_delete_preview(self, session, views):
        effects = []
        for item in views:
            selected = (session.get("selected") or {}).get(item)
            if selected:
                effects.append({"id": f"unselect:draft:{item}:{selected}",
                                "label": f"Unselect Draft {item} ({selected})"})
            locked = (session.get("locked") or {}).get(item) or {}
            if locked.get("candidate_id"):
                effects.append({"id": f"unlock:draft:{item}:{locked['candidate_id']}",
                                "label": f"Unlock Draft {item} ({locked['candidate_id']})"})
        token = hashlib.sha256(json.dumps(session, sort_keys=True, default=str).encode()).hexdigest()
        return {"protected_effects": effects, "confirmation_token": token}

    def preview_draft_delete(self, sid, view=""):
        sid = self._canonical(sid)["session_id"]
        with self._lock(sid):
            session = self._read(sid)
            views = [view] if view else self._views(session)
            if any(item not in self._views(session) for item in views):
                raise QuickCharacterWizardError("Choose a character stage or view.")
            return self._draft_delete_preview(session, views)

    def _restart_preview(self, session, view, render_mode):
        if render_mode not in {"draft", "final"} or view not in self._views(session):
            raise QuickCharacterWizardError("Choose a character stage, view, and render mode.")
        selections = session.get("final_selected" if render_mode == "final" else "selected") or {}
        locks = session.get("final_locked" if render_mode == "final" else "locked") or {}
        views = self._views(session) if view == "STYLE" else [view]
        effects = [{"id": f"unselect:{render_mode}:{item}:{selections[item]}",
                    "label": f"Unselect {render_mode.title()} {item} ({selections[item]})"}
                   for item in views if selections.get(item)]
        effects.extend({"id": f"unlock:{render_mode}:{item}:{locks[item]['candidate_id']}",
                        "label": f"Unlock {render_mode.title()} {item} ({locks[item]['candidate_id']})"}
                       for item in views if (locks.get(item) or {}).get("candidate_id"))
        token = hashlib.sha256(json.dumps(session, sort_keys=True, default=str).encode()).hexdigest()
        return {"protected_effects": effects, "confirmation_token": token}

    def preview_restart(self, sid, view, render_mode="draft"):
        sid = self._canonical(sid)["session_id"]
        with self._lock(sid):
            return self._restart_preview(self._read(sid), view, render_mode)

    def delete_draft_images(self, sid, view="", *, confirmation_token="", approved_effects=None):
        """Remove Draft outputs and cancel their work for one view or the workspace."""
        from datetime import datetime, timezone
        from zet.services.ai_workflow_service import AIWorkflowService
        sid = self._canonical(sid)["session_id"]
        with self._lock(sid):
            session = self._read(sid)
            views = [view] if view else self._views(session)
            if any(item not in self._views(session) for item in views):
                raise QuickCharacterWizardError("Choose a character stage or view.")
            preview = self._draft_delete_preview(session, views)
            if confirmation_token != preview["confirmation_token"]:
                from zet.services.protected_effect_preview import ProtectedEffectsChanged
                raise ProtectedEffectsChanged(preview)
            if not isinstance(approved_effects, list) or set(approved_effects) != {effect["id"] for effect in preview["protected_effects"]}:
                raise QuickCharacterWizardError("Approve each selected or locked Draft image affected by deletion.")
            root = self._directory(sid).resolve()
            candidates = [c for c in session["candidates"] if c.get("view") in views
                          and c.get("render_mode", "draft") == "draft"]
            candidate_ids = {c["candidate_id"] for c in candidates}
            cutoff = datetime.now(timezone.utc).isoformat()
            outputs = []
            for candidate in candidates:
                request_id = candidate.get("render_request_id") or candidate.get("request_id")
                if request_id:
                    self._generation().cancel_owned_request(request_id, {"session_id": sid, "candidate_id": candidate["candidate_id"]})
                if candidate.get("filename"):
                    outputs.append(candidate["filename"])
                candidate.update(status="CANCELLED", filename="", error="Deleted with Draft images.")
            epochs = session.setdefault("draft_cleanup_epochs", {})
            for item in views:
                epochs[item] = epochs.get(item, 0) + 1
                board = self._board(session, item)
                revision = board["revision"] + 1
                board.clear()
                board.update(self._empty_board(session, item))
                board["revision"] = revision
                session["selected"].pop(item, None)
                lock = session["locked"].pop(item, None) or {}
                if lock.get("snapshot"):
                    outputs.append(lock["snapshot"])
            if session.get("preview_candidate_id") in candidate_ids:
                session["preview_candidate_id"] = ""
            for relative in outputs:
                path = (root / relative).resolve()
                if not path.is_relative_to(root) or path == root:
                    raise QuickCharacterWizardError("Draft output is outside this workspace.")
                path.unlink(missing_ok=True)
            self._write(session)
            result = self._public(session)
        def matches(record):
            if (record.get("service") != "minor" or record.get("owner", {}).get("session_id") != sid
                    or record.get("created_at", "") > cutoff):
                return False
            args = record.get("args") or []
            if record.get("method") == "_analyze_then_render" and len(args) > 3:
                pending = args[3] or {}
                return pending.get("render_mode", "draft") == "draft" and pending.get("view") in views
            if len(args) > 1:
                candidate = args[1]
                identity = candidate.get("candidate_id") if isinstance(candidate, dict) else candidate
                return identity in candidate_ids
            return False
        AIWorkflowService(self.app).cancel_matching(matches)
        return result

    def lock_view(self, sid, view, candidate_id="", expected=None, render_mode="draft"):
        from zet.services.quick_character_publication_service import publish_quick_character
        sid = self._canonical(sid)["session_id"]
        with self._lock(sid):
            session = self._read(sid)
            board = self._board(session, view, expected, render_mode)
            selected_key = "final_selected" if render_mode == "final" else "selected"
            locked_key = "final_locked" if render_mode == "final" else "locked"
            if self._deleted_candidate(session, candidate_id or session[selected_key].get(view)):
                raise MinorCharacterNotFound("This candidate's iteration has been deleted.")
            candidate = next((c for c in session["candidates"] if c["candidate_id"] == (candidate_id or session[selected_key].get(view))
                and c["view"] == view and c.get("render_mode", "draft") == render_mode and c.get("filename")
                and c["candidate_id"] in board["slots"]), None)
            if not candidate:
                raise QuickCharacterWizardError("Select an image for this view first.")
            existing = session[locked_key].get(view) or {}
            if existing and existing.get("candidate_id") != candidate["candidate_id"]:
                raise QuickCharacterWizardConflict("Unlock this mode's existing image before locking another.")
            if not (self._directory(sid) / candidate["filename"]).is_file():
                raise QuickCharacterWizardError("This candidate image is unavailable.")
            board["selected_id"] = candidate["candidate_id"]
            board["revision"] += 1
            session[selected_key][view] = candidate["candidate_id"]
            locked = {"candidate_id": candidate["candidate_id"], "source_session_id": sid, "locked_at": self._now(), "render_mode": render_mode}
            if render_mode == "final" and view != "STYLE":
                frozen = {**session, **candidate.get("inputs", {}), "selected": {**session["selected"], view: candidate["candidate_id"]}}
                published = publish_quick_character(self.app, frozen, self._directory(sid), views=[view])
                session["minor_set_id"] = published["set_id"]
                locked.update(asset_id=published["asset_ids"][view], set_id=published["set_id"])
            else:
                from zet.services.atomic_file_service import write_bytes_atomic
                source = self._directory(sid) / candidate["filename"]
                relative = f"locks/{render_mode}_{view}_{candidate['candidate_id']}{source.suffix}"
                destination = self._directory(sid) / relative
                contents = source.read_bytes()
                if destination.exists() and destination.read_bytes() != contents:
                    raise QuickCharacterWizardConflict("The locked image snapshot has changed.")
                if not destination.exists():
                    write_bytes_atomic(destination, contents)
                locked["snapshot"] = relative
            session[locked_key][view] = locked
            self._write(session)
            return self._public(session)

    def unlock_view(self, sid, view, candidate_id, expected=None, render_mode="draft"):
        sid = self._canonical(sid)["session_id"]
        with self._lock(sid):
            session = self._read(sid)
            board = self._board(session, view, expected, render_mode)
            locked_key = "final_locked" if render_mode == "final" else "locked"
            if session[locked_key].get(view, {}).get("candidate_id") != candidate_id:
                raise QuickCharacterWizardConflict("This view's locked image changed. Reload it before trying again.")
            session[locked_key].pop(view)
            board["revision"] += 1
            self._write(session)
            return self._public(session)

    def accept(self, sid, revision_id):
        session = self._read(sid)
        views = [view for view in session["final_selected"] if view != "STYLE"]
        if not views:
            raise QuickCharacterWizardError("Select a Final view before publishing.")
        for view in views:
            self.lock_view(sid, view, render_mode="final")
        return self.get_character(sid)

    def owner(self, asset_id):
        for record in self._records():
            if any(v.get("asset_id") == asset_id for key in ("locked", "final_locked") for v in record[key].values()):
                return self._canonical(record["session_id"])["session_id"]
            for candidate in record["candidates"]:
                if uuid5(NAMESPACE_URL, f"zet:minor-character:{record['session_id']}:{candidate['candidate_id']}:{candidate['view']}").hex == asset_id.replace("-", ""):
                    return self._canonical(record["session_id"])["session_id"]
        return None

    def locked_image_path(self, sid, view, render_mode="draft"):
        session = self._canonical(sid)
        if render_mode not in ("draft", "final"):
            raise QuickCharacterWizardError("Render mode must be draft or final.")
        locks = session["final_locked" if render_mode == "final" else "locked"]
        record = locks.get(view) or {}
        if record.get("snapshot"):
            path = (self._directory(sid) / record["snapshot"]).resolve()
            if not path.is_relative_to(self._directory(sid).resolve()) or not path.is_file():
                raise QuickCharacterWizardError("The locked image snapshot is unavailable.")
            return path
        if view == "STYLE" and record:
            candidate = next(c for c in session["candidates"]
                             if c["candidate_id"] == record["candidate_id"])
            return self._directory(sid) / candidate["filename"]
        asset_id = record.get("asset_id")
        if not asset_id:
            raise QuickCharacterWizardError("This view has no locked image.")
        return Path(self.app.entity_library_service.get_asset(asset_id)["image_path"])

    def reference_image_path(self, sid, reference_id):
        reference = next((r for r in self._read(sid)["references"] if r["reference_id"] == reference_id), None)
        if not reference:
            raise QuickCharacterWizardError("Reference image is unavailable.")
        return self.image_path(sid, reference_index=reference["index"])
