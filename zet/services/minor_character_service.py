"""Named, ongoing character workspaces over the shared wizard render engine."""
from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4, uuid5, NAMESPACE_URL

from zet.services.image_reconstruction_contract import fingerprint, text
from zet.services.quick_character_wizard_service import (
    QuickCharacterWizardService, QuickCharacterWizardError, QuickCharacterWizardConflict, _LOCK, _ACTIVE,
)
from zet.services.workflow_storage import file_lock
from zet.services.minor_character_workflow_service import MinorCharacterWorkflow

_REVIEWS = ThreadPoolExecutor(max_workers=1, thread_name_prefix="minor-character-review")
_REVIEW_ACTIVE = set()


class MinorCharacterNotFound(QuickCharacterWizardError):
    pass


class MinorCharacterService(MinorCharacterWorkflow, QuickCharacterWizardService):
    INPUTS = ("references", "primary_reference_id", "style_mode", "preserve", "changes", "model",
              "notes", "framing", "side", "description", "identity", "proposals", "answers",
              "reconstruction_id", "target_hash")
    ANALYSIS_INPUTS = ("references", "primary_reference_id", "style_mode", "preserve", "changes", "model", "notes")

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
        for view, locked in value.get("locked", {}).items():
            locked["image_url"] = f"/api/minor-characters/{value['session_id']}/locked/{view}"
        return value

    def delete_character(self, sid):
        with file_lock(self.root / "names.lock"):
            record = self._canonical(sid)
            records = self._records()
            ids = {r["session_id"] for r in records if self.name_key(r["name"]) == self.name_key(record["name"])}
            for target in sorted(ids):
                with self._lock(target):
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
            result.append({"character_id": record["session_id"], "name": record["name"],
                           "locked": self._public(record)["locked"]})
        return sorted(result, key=lambda s: self.name_key(s["name"]))

    def list_sessions(self):
        return [self.get_character(c["character_id"]) for c in self.list_characters()]

    def get_character(self, sid):
        canonical = self._canonical(sid)
        value = super().get_session(canonical["session_id"])
        with self._lock(canonical["session_id"]):
            record = self._read(canonical["session_id"])
            interrupted = False
            for candidate in record["candidates"]:
                key = (self._key(canonical["session_id"]), candidate["candidate_id"])
                with _LOCK:
                    reviewing = key in _REVIEW_ACTIVE
                if candidate["status"] == "REVIEWING" and not reviewing:
                    candidate.update(status="REVIEW_FAILED", error="Suggestions were interrupted. You can continue with this image.")
                    interrupted = True
            if interrupted:
                self._write(record)
                value = self._public(record)
        for view, locked in value["locked"].items():
            locked["image_url"] = f"/api/minor-characters/{canonical['session_id']}/locked/{view}"
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
        session["job"] = {"kind": "review", "status": "COMPLETE", "error": ""}
        session["status"] = "REVIEW_READY"
        key = (self._key(sid), candidate_id)
        with _LOCK:
            _REVIEW_ACTIVE.add(key)
        self._write(session)

        def review():
            try:
                self._review_job(sid, candidate_id)
            except Exception as exc:
                with self._lock(sid):
                    current = self._read(sid)
                    candidate = next(c for c in current["candidates"] if c["candidate_id"] == candidate_id)
                    candidate.update(status="REVIEW_FAILED", error="Suggestions unavailable: " + str(exc))
                    self._write(current)
            finally:
                with _LOCK:
                    _REVIEW_ACTIVE.discard(key)
        _REVIEWS.submit(review)

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
                "changes": "", "model": self.app.config.ai_quick_character_wizard_model,
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
        sid = self._canonical(sid)["session_id"]
        with file_lock(self.root / "names.lock"):
            records = self._records()
            return self._update_character(sid, payload, records)

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
                                 ("style_mode", {"universe", "preserve_source"})):
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
                                  "asset_id": str(ref.get("asset_id") or ""), "checksum": hashlib.sha256(data).hexdigest()}
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
                board = self._board(session, edit["view"], edit["revision"])
                self._edit_board(board, edit)
                board["revision"] += 1
            if before != self._signature(session):
                session["needs_analysis"] = True
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
            session.update(analysis_inputs=self._snapshot(session), status="DRAFTING",
                           job={"kind": "draft", "status": "RUNNING", "error": ""})
            self._write(session)
            self._submit(sid, self._analyze_then_render, session["revision_id"], self._signature(session), pending)
            return self._public(session)

    def generate_draft(self, sid, revision_id, answers=None):
        return self.analyze(sid, answers=answers)

    def _analyze_then_render(self, sid, revision_id, signature, pending):
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
            self._write(session)
            if pending and not session["needs_analysis"] and not self._deleted_candidate(session, pending.get("candidate_id")):
                candidate = self._new_candidate(session, **pending)
                self._write(session)
            else:
                candidate = None
        if candidate:
            self._render_job(sid, candidate["candidate_id"], pending["item_ids"])

    def lock_view(self, sid, view, candidate_id="", expected=None):
        from zet.services.quick_character_publication_service import publish_quick_character
        sid = self._canonical(sid)["session_id"]
        with self._lock(sid):
            session = self._read(sid)
            if self._deleted_candidate(session, candidate_id or session["selected"].get(view)):
                raise MinorCharacterNotFound("This candidate's iteration has been deleted.")
            candidate = next((c for c in session["candidates"] if c["candidate_id"] == (candidate_id or session["selected"].get(view))
                and c["view"] == view and c.get("filename")), None)
            if not candidate:
                raise QuickCharacterWizardError("Select an image for this view first.")
            board = self._board(session, view, expected)
            if view == "STYLE" or candidate.get("kind") != "true_up":
                raise QuickCharacterWizardError("Only generated view true-up images can be locked.")
            board["selected_id"] = candidate["candidate_id"]
            board["revision"] += 1
            session["selected"][view] = candidate["candidate_id"]
            frozen = {**session, **candidate.get("inputs", {})}
            published = publish_quick_character(self.app, frozen, self._directory(sid), views=[view])
            session["minor_set_id"] = published["set_id"]
            session["locked"][view] = {"asset_id": published["asset_ids"][view], "candidate_id": candidate["candidate_id"],
                "set_id": published["set_id"], "source_session_id": sid, "locked_at": self._now()}
            self._write(session)
            return self._public(session)

    def accept(self, sid, revision_id):
        session = self._read(sid)
        for view in session["selected"]:
            if view != "STYLE":
                self.lock_view(sid, view)
        return self.get_character(sid)

    def owner(self, asset_id):
        for record in self._records():
            if any(v["asset_id"] == asset_id for v in record["locked"].values()):
                return self._canonical(record["session_id"])["session_id"]
            for candidate in record["candidates"]:
                if uuid5(NAMESPACE_URL, f"zet:minor-character:{record['session_id']}:{candidate['candidate_id']}:{candidate['view']}").hex == asset_id.replace("-", ""):
                    return self._canonical(record["session_id"])["session_id"]
        return None

    def locked_image_path(self, sid, view):
        session = self.get_character(sid)
        asset_id = session["locked"].get(view, {}).get("asset_id")
        if not asset_id:
            raise QuickCharacterWizardError("This view has no locked image.")
        return Path(self.app.entity_library_service.get_asset(asset_id)["image_path"])

    def reference_image_path(self, sid, reference_id):
        reference = next((r for r in self._read(sid)["references"] if r["reference_id"] == reference_id), None)
        if not reference:
            raise QuickCharacterWizardError("Reference image is unavailable.")
        return self.image_path(sid, reference_index=reference["index"])
