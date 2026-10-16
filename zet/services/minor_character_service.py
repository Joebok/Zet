"""Named, ongoing character workspaces over the shared wizard render engine."""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4, uuid5, NAMESPACE_URL

from zet.services.atomic_file_service import write_json_atomic
from zet.services.image_reconstruction_contract import correction_items, fingerprint, text
from zet.services.quick_character_wizard_service import (
    QuickCharacterWizardService, QuickCharacterWizardError, QuickCharacterWizardConflict, _LOCK, _ACTIVE,
)
from zet.services.workflow_storage import file_lock

_REVIEWS = ThreadPoolExecutor(max_workers=1, thread_name_prefix="minor-character-review")
_REVIEW_ACTIVE = set()


class MinorCharacterNotFound(QuickCharacterWizardError):
    pass


class MinorCharacterService(QuickCharacterWizardService):
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
        value.update(version=2, minor_character=True)
        value.setdefault("style_mode", "preserve_source")
        value.setdefault("model", self.app.config.ai_quick_character_wizard_model)
        value.setdefault("preserve", "Preserve original identity and visible design except requested changes.")
        value.setdefault("changes", "")
        value.setdefault("locked", {})
        for ref in value["references"]:
            ref.setdefault("reference_id", uuid5(NAMESPACE_URL, f"minor:{sid}:reference:{ref['index']}").hex)
        first = value["references"][0]["reference_id"] if value["references"] else ""
        value.setdefault("primary_reference_id", first)
        value.setdefault("comparison_reference_id", first)
        value.setdefault("needs_analysis", not bool(value["description"]))
        publication = value.get("publication") or {}
        value.setdefault("minor_set_id", publication.get("set_id", ""))
        for view, aid in publication.get("asset_ids", {}).items():
            value["locked"].setdefault(view, {"asset_id": aid, "candidate_id": value["selected"].get(view),
                "set_id": publication.get("set_id"), "locked_at": value.get("updated_at", ""), "source_session_id": sid})
        if value["status"] == "ACCEPTED":
            value["status"] = "REVIEW_READY"
        iterations = value.setdefault("iterations", [])
        for candidate in value["candidates"]:
            if not candidate.get("iteration_id"):
                candidate["iteration_id"] = candidate["candidate_id"]
                iterations.append({"iteration_id": candidate["candidate_id"], "view": candidate["view"],
                    "template_candidate_id": candidate["candidate_id"], "slots": [candidate["candidate_id"], None, None, None]})
        return value

    def _write(self, session):
        with self._lock(session["session_id"]):
            super()._write(session)

    def _records(self, include_aliases=False):
        records = []
        for path in self.root.glob("*/session.json"):
            try:
                value = self._read(path.parent.name)
                if not value.get("deleted_at") and value["status"] != "ABANDONED" and (include_aliases or not value.get("minor_character_alias")):
                    records.append(value)
            except (QuickCharacterWizardError, KeyError, TypeError):
                continue
        return records

    def _canonical(self, sid):
        record = self._read(sid)
        if record.get("deleted_at"):
            raise MinorCharacterNotFound("This Minor Character has been deleted.")
        if record.get("minor_character_alias"):
            return self._canonical(record["minor_character_alias"])
        siblings = [s for s in self._records() if self.name_key(s["name"]) == self.name_key(record["name"])]
        return max(siblings, key=lambda s: (s.get("updated_at", ""), s["session_id"])) if siblings else record

    def _with_legacy_locks(self, record, records):
        for old in sorted(records, key=lambda s: s.get("updated_at", "")):
            if self.name_key(old["name"]) == self.name_key(record["name"]):
                for view, locked in old["locked"].items():
                    existing = record["locked"].get(view)
                    if not existing or locked.get("locked_at", "") > existing.get("locked_at", ""):
                        record["locked"][view] = locked
        return record

    def _public(self, session):
        value = super()._public(session)
        deleted = {i["iteration_id"] for i in value.get("iterations", []) if i.get("deleted_at")}
        value["iterations"] = [i for i in value.get("iterations", []) if i["iteration_id"] not in deleted]
        value["candidates"] = [c for c in value["candidates"] if c.get("iteration_id") not in deleted]
        value["character_id"] = value["session_id"]
        for ref in value["references"]:
            ref["url"] = f"/api/minor-characters/{value['session_id']}/references/{ref['reference_id']}"
        for view, locked in value.get("locked", {}).items():
            locked["image_url"] = f"/api/minor-characters/{value['session_id']}/locked/{view}"
        return value

    def delete_character(self, sid):
        with file_lock(self.root / "names.lock"):
            record = self._canonical(sid)
            records = self._records(include_aliases=True)
            ids = {r["session_id"] for r in records if self.name_key(r["name"]) == self.name_key(record["name"])}
            # Include aliases from earlier renames so old inventory handoffs cannot reopen them.
            while True:
                aliases = {r["session_id"] for r in records if r.get("minor_character_alias") in ids}
                if aliases <= ids:
                    break
                ids.update(aliases)
            for target in sorted(ids):
                with self._lock(target):
                    current = self._read(target)
                    current.update(deleted_at=self._now(), status="ABANDONED",
                        job={"kind": "delete", "status": "COMPLETE", "error": ""})
                    self._write(current)
        return {"deleted": True, "character_id": record["session_id"]}

    def delete_iteration(self, sid, iteration_id):
        sid = self._canonical(sid)["session_id"]
        with self._lock(sid):
            session = self._read(sid)
            iteration = next((i for i in session["iterations"] if i["iteration_id"] == iteration_id and not i.get("deleted_at")), None)
            if not iteration:
                raise MinorCharacterNotFound("This iteration is no longer available.")
            iteration["deleted_at"] = self._now()
            ids = {c["candidate_id"] for c in session["candidates"] if c.get("iteration_id") == iteration_id}
            session["selected"] = {view: cid for view, cid in session["selected"].items() if cid not in ids}
            remaining = [i for i in session["iterations"] if i["view"] == iteration["view"] and not i.get("deleted_at")]
            if session.get("active_iteration_id") == iteration_id or session.get("preview_candidate_id") in ids:
                session["active_iteration_id"] = remaining[-1]["iteration_id"] if remaining else ""
                session["preview_candidate_id"] = next((cid for cid in remaining[-1]["slots"] if cid), "") if remaining else ""
            self._write(session)
            return self._public(session)

    @staticmethod
    def _deleted_candidate(session, candidate_id):
        deleted = {i["iteration_id"] for i in session.get("iterations", []) if i.get("deleted_at")}
        return any(c["candidate_id"] == candidate_id and c.get("iteration_id") in deleted for c in session["candidates"])

    def list_characters(self):
        records = self._records()
        grouped = {}
        for record in sorted(records, key=lambda s: (s.get("updated_at", ""), s["session_id"])):
            grouped[self.name_key(record["name"])] = record
        result = []
        for record in grouped.values():
            record = self._with_legacy_locks(record, records)
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
        value = self._with_legacy_locks(value, self._records())
        for view, locked in value["locked"].items():
            locked["image_url"] = f"/api/minor-characters/{canonical['session_id']}/locked/{view}"
        return value

    def get_session(self, sid):
        return self.get_character(sid)

    def _busy(self, session):
        with _LOCK:
            active = self._key(session["session_id"]) in _ACTIVE
        deleted = {i["iteration_id"] for i in session.get("iterations", []) if i.get("deleted_at")}
        return active or (session["job"]["kind"] == "draft" and session["job"]["status"] == "RUNNING") or any(
            c["status"] in {"QUEUING", "QUEUED", "RUNNING"} and c.get("iteration_id") not in deleted
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
                "revision_id": uuid4().hex, "candidates": [], "iterations": [], "selected": {}, "locked": {}, "status": "DRAFT_READY",
                "needs_analysis": True, "primary_reference_id": "", "comparison_reference_id": "",
                "job": {"kind": "draft", "status": "COMPLETE", "error": ""}, "created_at": self._now(), "publication": None}
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
            session = self._with_legacy_locks(self._read(sid), workspace_records)
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
            for key in ("active_view", "preview_candidate_id", "active_iteration_id"):
                if key in payload:
                    session[key] = text(payload[key], key)
            if before != self._signature(session):
                session["needs_analysis"] = True
            if self._busy(session) and session["job"]["kind"] == "draft" and any(k in payload for k in ("description", "identity", "proposals")):
                session["description_override"] = {k: session[k] for k in ("description", "identity", "proposals")}
            elif session.get("reconstruction_id") and not session["needs_analysis"] and any(k in payload for k in ("description", "identity", "proposals")):
                job = self._reconstruction().revise(session["reconstruction_id"], session["description"], session["identity"], session["proposals"])
                session.update(reconstruction_id=job["id"], target_hash=job["target_hash"])
            session["proposals_approved"] = True
            for old in workspace_records:
                if old["session_id"] != sid and self.name_key(old["name"]) == self.name_key(previous_name):
                    old["minor_character_alias"] = sid
                    with self._lock(old["session_id"]):
                        write_json_atomic(self._directory(old["session_id"]) / "session.json", old)
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

    def _new_candidate(self, session, view, instructions="", candidate_id="", item_ids=None):
        if session.get("deleted_at") or self._deleted_candidate(session, candidate_id):
            raise MinorCharacterNotFound("This character or refinement iteration has been deleted.")
        if view not in self._views(session):
            raise QuickCharacterWizardError("Choose a character view.")
        anchor = session["selected"].get("FRONT")
        if view != "FRONT" and not anchor:
            raise QuickCharacterWizardError("Select a front image to use for the other views.")
        base = next((c for c in session["candidates"] if c["candidate_id"] == candidate_id and c["view"] == view and c.get("filename")), None)
        if (instructions or item_ids) and not base:
            raise QuickCharacterWizardError("Choose a rendered candidate to refine.")
        if base:
            correction_items(base.get("comparison") or {"items": []}, item_ids or [], instructions)
        candidate = {"candidate_id": uuid4().hex, "view": view, "revision_id": session["revision_id"],
            "anchor_id": anchor if view != "FRONT" else None, "refinement_base_id": base["candidate_id"] if base else None,
            "request_id": "", "status": "QUEUING", "error": "", "review": "", "refinements": [],
            "stale": False, "instructions": instructions, "created_at": self._now(), "inputs": self._snapshot(session)}
        if session.get("reconstruction_id"):
            candidate.update(reconstruction_id=session["reconstruction_id"], target_hash=session["target_hash"])
            # A previous target's findings are advice, not a reason to block an edit.
            if base and base.get("target_hash") != session["target_hash"]:
                instructions = "\n".join([instructions, *[i["correction"] for i in base.get("comparison", {}).get("items", []) if i["id"] in (item_ids or [])]])
                candidate["instructions"] = instructions
                candidate["correction_report_id"] = ""
        session["candidates"].append(candidate)
        candidate["iteration_id"] = candidate["candidate_id"]
        session["iterations"].append({"iteration_id": candidate["iteration_id"], "view": view,
            "template_candidate_id": candidate["candidate_id"], "slots": [candidate["candidate_id"], None, None, None]})
        session.update(status="RENDERING", job={"kind": "render", "status": "COMPLETE", "error": ""})
        return candidate

    def iteration_slots(self, sid, iteration_id, action, slot=None, count=1):
        """Manage a four-slot board; rerenders replay submitted inputs, never current form inputs."""
        sid = self._canonical(sid)["session_id"]
        with self._lock(sid):
            session = self._read(sid)
            iteration = next((i for i in session["iterations"] if i["iteration_id"] == iteration_id and not i.get("deleted_at")), None)
            if not iteration or action not in {"add", "regenerate", "clear"}:
                raise QuickCharacterWizardError("Choose an iteration and slot action.")
            if action != "add" and (type(slot) is not int or not 0 <= slot < 4):
                raise QuickCharacterWizardError("Choose a slot from 1 to 4.")
            by_id = {c["candidate_id"]: c for c in session["candidates"]}
            if action == "clear":
                iteration["slots"][slot] = None
                self._write(session)
                return self._public(session)
            template = by_id[iteration["template_candidate_id"]]
            if not template.get("render_payload"):
                raise QuickCharacterWizardError("This iteration has no submitted prompt. Generate a new iteration.")
            empty = [n for n, cid in enumerate(iteration["slots"]) if not cid]
            if action == "add" and (type(count) is not int or not 1 <= count <= len(empty)):
                raise QuickCharacterWizardError("Choose a render count within the empty slots.")
            targets = empty[:count] if action == "add" else [slot]
            candidates = []
            for target in targets:
                candidate = {key: deepcopy(template[key]) for key in (
                    "view", "revision_id", "anchor_id", "refinement_base_id", "instructions", "inputs",
                    "reconstruction_id", "target_hash", "view_context", "correction_report_id") if key in template}
                candidate.update(candidate_id=uuid4().hex, iteration_id=iteration_id, request_id="",
                    status="QUEUING", error="", review="", refinements=[], stale=False, created_at=self._now())
                session["candidates"].append(candidate)
                iteration["slots"][target] = candidate["candidate_id"]
                candidates.append(candidate)
            session["status"] = "RENDERING"
            self._write(session)
            # Submission only packages work into the queue; it does not wait for rendering.
            # Keep allocation/submission atomic to readers without a workspace-wide task fence.
            self._render_slots(sid, candidates, deepcopy(template["render_payload"]))
            return self._public(self._read(sid))

    def _render_slots(self, sid, candidates, payload):
        for candidate in candidates:
            try:
                self._dispatch_candidate(sid, candidate, payload)
            except Exception as exc:
                with self._lock(sid):
                    session = self._read(sid)
                    target = next(c for c in session["candidates"] if c["candidate_id"] == candidate["candidate_id"])
                    target.update(status="FAILED", error=str(exc))
                    self._write(session)

    def render(self, sid, revision_id, view, instructions="", candidate_id="", item_ids=None):
        sid = self._canonical(sid)["session_id"]
        with self._lock(sid):
            session = self._read(sid)
            if self._deleted_candidate(session, candidate_id):
                raise MinorCharacterNotFound("This candidate's iteration has been deleted.")
            if self._busy(session):
                raise QuickCharacterWizardConflict("An image task is already running.")
            if view != "FRONT" and not session["selected"].get("FRONT"):
                raise QuickCharacterWizardError("Select a front image to use for the other views.")
            pending = dict(view=view, instructions=text(instructions, "Changes"), candidate_id=candidate_id, item_ids=item_ids or [])
            if session["needs_analysis"] or not session["description"]:
                return self._analyze(sid, pending=pending)
            candidate = self._new_candidate(session, **pending)
            self._write(session)
            self._submit(sid, self._render_job, candidate["candidate_id"], item_ids)
            return self._public(session)

    def select(self, sid, revision_id, candidate_id):
        sid = self._canonical(sid)["session_id"]
        with self._lock(sid):
            session = self._read(sid)
            if self._deleted_candidate(session, candidate_id):
                raise MinorCharacterNotFound("This candidate's iteration has been deleted.")
            candidate = next((c for c in session["candidates"] if c["candidate_id"] == candidate_id and c.get("filename")), None)
            if not candidate:
                raise QuickCharacterWizardError("Choose a rendered image.")
            session["selected"][candidate["view"]] = candidate_id
            self._write(session)
            return self._public(session)

    def retry_render(self, sid, revision_id, candidate_id):
        sid = self._canonical(sid)["session_id"]
        with self._lock(sid):
            if self._deleted_candidate(self._read(sid), candidate_id):
                raise MinorCharacterNotFound("This candidate's iteration has been deleted.")
            return super().retry_render(sid, revision_id, candidate_id)

    def lock_view(self, sid, view, candidate_id=""):
        from zet.services.quick_character_publication_service import publish_quick_character
        sid = self._canonical(sid)["session_id"]
        records = self._records()
        with self._lock(sid):
            session = self._with_legacy_locks(self._read(sid), records)
            if self._deleted_candidate(session, candidate_id or session["selected"].get(view)):
                raise MinorCharacterNotFound("This candidate's iteration has been deleted.")
            candidate = next((c for c in session["candidates"] if c["candidate_id"] == (candidate_id or session["selected"].get(view))
                and c["view"] == view and c.get("filename")), None)
            if not candidate:
                raise QuickCharacterWizardError("Select an image for this view first.")
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
            self.lock_view(sid, view)
        return self.get_character(sid)

    def owner(self, asset_id):
        for record in self._records(include_aliases=True):
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
