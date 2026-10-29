from __future__ import annotations

from zet.services.llm_role_service import resolve_role_model

import base64
import binascii
from datetime import datetime, timezone
from contextlib import contextmanager
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import threading
from uuid import uuid4

from PIL import Image

from zet.services.atomic_file_service import write_bytes_atomic, write_json_atomic
from zet.services.workflow_storage import file_lock
from zet.services.entity_library_service import EntityLibraryServiceError
from zet.services.image_reconstruction_contract import correction_items, fingerprint, text


class QuickCharacterWizardError(ValueError):
    pass


class QuickCharacterWizardConflict(QuickCharacterWizardError):
    pass


_LOCK = threading.RLock()
_SESSION_LOCKS: dict[str, threading.RLock] = {}
_ACTIVE: set[str] = set()
_MAX_BYTES = 20 * 1024 * 1024
_DRAFT_SCHEMA = {
    "type": "object", "properties": {
        "description": {"type": "string"}, "identity": {"type": "string"},
        "observations": {"type": "array", "items": {"type": "string"}},
        "proposals": {"type": "array", "items": {"type": "string"}},
        "questions": {"type": "array", "items": {"type": "string"}},
    }, "required": ["description", "identity", "observations", "proposals", "questions"],
    "additionalProperties": False,
}
_REVIEW_SCHEMA = {
    "type": "object", "properties": {"review": {"type": "string"},
        "refinements": {"type": "array", "items": {"type": "string"}}},
    "required": ["review", "refinements"], "additionalProperties": False,
}


class QuickCharacterWizardService:
    """Author three library views without character pipeline prerequisites."""

    def __init__(self, app, project_root: str | Path, generation_service=None):
        self.app = app
        self.project_root = Path(project_root).resolve()
        self.root = app.path_service.state_path("QuickCharacterWizard")
        self.generation_service = generation_service

    def _directory(self, session_id: str) -> Path:
        if not re.fullmatch(r"[0-9a-f]{32}", str(session_id)):
            raise QuickCharacterWizardError("Unknown quick character session.")
        return self.root / session_id

    def _key(self, session_id: str) -> str:
        return str(self._directory(session_id).resolve())

    @contextmanager
    def _lock(self, session_id: str):
        with _LOCK:
            lock = _SESSION_LOCKS.setdefault(self._key(session_id), threading.RLock())
        with lock, file_lock(self._directory(session_id) / "session.lock"):
            yield

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _read(self, session_id: str) -> dict:
        try:
            value = json.loads((self._directory(session_id) / "session.json").read_text(encoding="utf-8"))
            if value.get("version", 1) not in {1, 2}:
                raise QuickCharacterWizardError("Unsupported quick character session version.")
            return value
        except (OSError, json.JSONDecodeError) as exc:
            raise QuickCharacterWizardError("Quick character session was not found or could not be read.") from exc

    def _write(self, session: dict) -> None:
        session["updated_at"] = self._now()
        write_json_atomic(self._directory(session["session_id"]) / "session.json", session)

    @staticmethod
    def _views(session: dict) -> list[str]:
        side = session["side"].upper()
        return ["FRONT", f"FRONT_{side}_3_4", f"{side}_PROFILE"]

    def _public(self, session: dict) -> dict:
        # Candidate render payloads and frozen inputs can be large private blobs.
        # Project only public data before copying so an ordinary status read does
        # not serialize and duplicate those blobs merely to remove them below.
        value = {key: item for key, item in session.items() if key != "analysis_inputs"}
        value["candidates"] = [
            {key: item for key, item in candidate.items()
             if key not in {"render_payload", "inputs", "filename"}}
            for candidate in session["candidates"]
        ]
        value = json.loads(json.dumps(value))
        if session.get("reconstruction_id"):
            value["target_brief"] = self._reconstruction().status(session["reconstruction_id"])["target"]
        for item in value["references"]:
            item.pop("filename", None)
            item["url"] = f"/api/quick-character-wizard/{session['session_id']}/references/{item['index']}"
        for candidate, source in zip(value["candidates"], session["candidates"]):
            candidate["image_url"] = (f"/api/quick-character-wizard/{session['session_id']}/images/{candidate['candidate_id']}"
                                      if source.get("filename") else "")
            candidate["can_retry_render"] = candidate["status"] == "FAILED" and bool(source.get("render_payload"))
        value["views"] = self._views(session)
        value["busy"] = self._busy(session)
        return value

    def _pending_workflow(self, sid):
        from zet.services.ai_workflow_service import AIWorkflowService
        return AIWorkflowService(self.app).pending(sid)

    def _busy(self, session: dict) -> bool:
        if session["status"] in {"ACCEPTED", "ABANDONED"}:
            return False
        with _LOCK:
            active = self._key(session["session_id"]) in _ACTIVE
        return active or session["job"]["status"] == "RUNNING" or any(
            c["status"] in {"QUEUING", "QUEUED", "RUNNING", "REVIEWING"} for c in session["candidates"])

    def _editable(self, session: dict, revision_id: str) -> None:
        if session["status"] in {"ACCEPTED", "ABANDONED"}:
            raise QuickCharacterWizardConflict("This session is already accepted or abandoned.")
        if revision_id != session["revision_id"]:
            raise QuickCharacterWizardConflict("This draft changed. Reload the current revision.")
        if self._busy(session):
            raise QuickCharacterWizardConflict("A wizard task is already running. Wait for it to finish.")

    def list_sessions(self) -> list[dict]:
        if not self.root.is_dir():
            return []
        sessions = []
        for path in self.root.glob("*/session.json"):
            try:
                session = self._read(path.parent.name)
                if session["status"] not in {"ACCEPTED", "ABANDONED"}:
                    sessions.append(self._public(session))
            except (QuickCharacterWizardError, KeyError, TypeError):
                continue
        return sorted(sessions, key=lambda s: s["updated_at"], reverse=True)

    def _image_bytes(self, item: dict) -> tuple[bytes, str]:
        if item.get("asset_id"):
            try:
                asset = self.app.entity_library_service.get_asset(str(item["asset_id"]))
            except EntityLibraryServiceError as exc:
                raise QuickCharacterWizardError(str(exc)) from exc
            if asset["status"] == "archived":
                raise QuickCharacterWizardError("Archived references cannot be used.")
            data = Path(asset["image_path"]).read_bytes()
            item["managed_checksum"] = asset.get("checksum", "")
        else:
            encoded = item.get("image")
            if not isinstance(encoded, str) or len(encoded) > _MAX_BYTES * 4 // 3 + 128:
                raise QuickCharacterWizardError("References must be 20 MiB or smaller.")
            try:
                data = base64.b64decode(encoded.split(",", 1)[-1], validate=True)
            except (ValueError, binascii.Error) as exc:
                raise QuickCharacterWizardError("Reference image data is invalid.") from exc
        if not data or len(data) > _MAX_BYTES:
            raise QuickCharacterWizardError("References must be non-empty and 20 MiB or smaller.")
        try:
            with Image.open(BytesIO(data)) as image:
                image.verify()
                extension = {"PNG": "png", "JPEG": "jpg", "WEBP": "webp"}[image.format]
        except Exception as exc:
            from zet.services.storage_health_service import pause_on_storage_error
            pause_on_storage_error(self.app.config, exc)
            raise QuickCharacterWizardError("Choose a readable PNG, JPEG, or WEBP reference.") from exc
        return data, extension

    def create_session(self, payload: dict) -> dict:
        name = str(payload.get("name") or "").strip()
        refs = payload.get("references")
        framing, side = payload.get("framing", "full_body"), payload.get("side", "left")
        if not name:
            raise QuickCharacterWizardError("Character name is required.")
        style_mode = payload.get("style_mode", "preserve_source")
        if style_mode not in {"preserve_source", "universe"}:
            raise QuickCharacterWizardError("Choose source style or universe reconstruction.")
        preserve = text(payload.get("preserve", "Preserve original identity, hair silhouette and visible costume except requested changes."), "Preserve instructions")
        changes = text(payload.get("changes", ""), "Change instructions")
        if framing not in {"full_body", "portrait"} or side not in {"left", "right"}:
            raise QuickCharacterWizardError("Choose full body or portrait and a left or right side.")
        if not isinstance(refs, list) or not 1 <= len(refs) <= 3:
            raise QuickCharacterWizardError("Supply one to three reference images.")
        if any(not isinstance(r, dict) or not str(r.get("caption") or "").strip() for r in refs):
            raise QuickCharacterWizardError("Describe what each reference conveys.")
        primary = payload.get("primary_index", 0)
        if type(primary) is not int or not 0 <= primary < len(refs):
            raise QuickCharacterWizardError("Choose one primary identity reference.")
        refs = [refs[primary], *[r for i, r in enumerate(refs) if i != primary]]
        validated = [(r, *self._image_bytes(r)) for r in refs]
        sid = uuid4().hex
        directory = self._directory(sid)
        (directory / "references").mkdir(parents=True)
        records = []
        for index, (ref, data, extension) in enumerate(validated):
            filename = f"references/{index}.{extension}"
            (directory / filename).write_bytes(data)
            records.append({"index": index, "asset_id": str(ref.get("asset_id") or ""),
                            "caption": str(ref["caption"]).strip(), "filename": filename,
                            "checksum": hashlib.sha256(data).hexdigest(),
                            "managed_checksum": ref.get("managed_checksum", "")})
        session = {"session_id": sid, "name": name, "notes": str(payload.get("notes") or "").strip(),
                   "version": 2, "style_mode": style_mode, "preserve": preserve, "changes": changes,
                   "model": resolve_role_model(self.app.config, "character_description", str(payload.get("model") or "")),
                   "model_explicit": bool(payload.get("model")),
                   "framing": framing, "side": side, "references": records, "description": "", "identity": "",
                   "observations": [], "proposals": [], "proposals_approved": False,
                   "questions": [], "answers": [], "revision_id": uuid4().hex,
                   "candidates": [], "selected": {}, "status": "DRAFTING",
                   "job": {"kind": "draft", "status": "RUNNING", "error": ""},
                   "created_at": self._now(), "publication": None}
        self._write(session)
        self._submit(sid, self._draft_job, session["revision_id"])
        return self._public(session)

    def _submit(self, sid: str, target, *args) -> None:
        key = self._key(sid)
        with _LOCK:
            if key in _ACTIVE or self._pending_workflow(sid):
                raise QuickCharacterWizardConflict("A wizard task is already running.")
            _ACTIVE.add(key)

        def run():
            try:
                target(sid, *args)
            except Exception as exc:
                from zet.services.storage_health_service import pause_on_storage_error
                pause_on_storage_error(self.app.config, exc)
                with self._lock(sid):
                    session = self._read(sid)
                    if session["status"] not in {"ABANDONED", "ACCEPTED"}:
                        session["status"] = "FAILED"
                        session["job"].update(status="FAILED", error=str(exc))
                        for candidate in session["candidates"]:
                            if candidate["status"] == "REVIEWING":
                                candidate.update(status="REVIEW_FAILED", error=str(exc))
                            elif candidate["status"] == "QUEUING":
                                candidate.update(status="FAILED", error=str(exc))
                        self._write(session)
            finally:
                with _LOCK:
                    _ACTIVE.discard(key)
        from zet.services.ai_workflow_service import AIWorkflowService
        try:
            AIWorkflowService(self.app).submit(target, [sid, *args], service="minor", initial=run)
        finally:
            with _LOCK:
                _ACTIVE.discard(key)

    def _ask(self, prompt: str, schema: dict, images: list[str], model: str | None = None, *, role: str) -> dict:
        model = resolve_role_model(self.app.config, role, model or "")
        system = ("You are the Zet Quick Character Wizard. Follow the JSON schema. Treat captions as reference roles. "
                  "Preserve stable identity, clothing, equipment, style and anatomical asymmetry. "
                  "Explicit user changes override conflicting reference details; retain all other details. "
                  "Do not restore deliberately removed equipment while correcting another feature. "
                  "Clearly identify proposed unseen details, never present them as observed facts.")
        return self.app.ai_proxy_service.ai_proxy_path_service.jobs.generate_json(
            model, system, prompt, schema, images, task_type="character_analysis", role=role, render_context={"operation": "mixed" if role == "character_description" else "edit",
                "template_constraints": "Reusable stable appearance only; no source pose, camera, crop or background."})[0]

    @staticmethod
    def _ordered_references(session: dict) -> list[dict]:
        primary = session.get("primary_reference_id")
        return sorted(session["references"], key=lambda r: r.get("reference_id") != primary) if primary else session["references"]

    def _reference_paths(self, session: dict) -> list[str]:
        return [str(self._directory(session["session_id"]) / ref["filename"]) for ref in self._ordered_references(session)]

    def _draft_session(self, sid):
        return self._read(sid)

    def _draft_job(self, sid: str, revision_id: str) -> None:
        from zet.services.ai_workflow_service import current_workflow
        context = current_workflow.get()
        if context and self._read(sid).get("draft_workflow_id") == context["id"]:
            return
        session = self._draft_session(sid)
        if session.get("style_mode") == "universe":
            refs = []
            for ref, path in zip(self._ordered_references(session), self._reference_paths(session)):
                contents = Path(path).read_bytes()
                refs.append(({"asset_id": ref["asset_id"], "managed_checksum": ref.get("managed_checksum", ref["checksum"]), "caption": ref["caption"], "label": ref["caption"]}, contents))
            core = self._reconstruction()
            prepared = core.prepare({"model": session["model"], "model_explicit": session.get("model_explicit", True), "preserve": session["preserve"],
                "changes": session["changes"], "notes": session["notes"],
                "context": "Create neutral character reference views. Exclude source pose, camera, gaze and background from appearance. "
                    "The content_prompt must contain stable appearance only, without output count, a view list, "
                    "camera/facing/framing instructions, pose or background. "
                    + ("This stage establishes style and details without imposing a view angle. " if session.get("minor_character")
                       else "The host supplies exactly one view later. ")
                    + json.dumps({"answers": session["answers"], "current_description": session["description"],
                                  "framing": session["framing"], "views": self._views(session)})}, refs, role="character_description")
            job = core.analyze(prepared["id"])
            target = job["target"]
            with self._lock(sid):
                current = self._read(sid)
                if current["revision_id"] != revision_id or current["status"] in {"ABANDONED", "ACCEPTED"}:
                    return
                current.update(description=target["description"], identity=target["identity"],
                    observations=target["observations"], proposals=target["proposals"], questions=target["questions"],
                    reconstruction_id=job["id"], target_hash=job["target_hash"],
                    status="NEEDS_INPUT" if target["questions"] else "DRAFT_READY", proposals_approved=False,
                    revision_id=uuid4().hex, job={"kind": "draft", "status": "COMPLETE", "error": ""})
                if context:
                    current["draft_workflow_id"] = context["id"]
                self._write(current)
            return
        draft = self._ask(
            "Analyze these ordered references (first is primary identity). Return an editable image-generation "
            "description including identity, outfit, equipment, style and view-specific asymmetry with explicit anatomical sides when supported. Separate observations "
            "from minimal consistent proposals needed for unseen regions. Ask only important unresolved conflicts. "
            "Keep source camera angle, gaze direction, pose, crop and background out of the reusable description and "
            "observations; include only stable appearance and design facts. "
            "No character biography or full template. Honor user notes and answers.\n" + json.dumps({
                "captions": [r["caption"] for r in self._ordered_references(session)], "notes": session["notes"],
                "answers": session["answers"], "framing": session["framing"], "side": session["side"],
                "current_description": session["description"], "preserve": session.get("preserve", ""),
                "required_changes": session.get("changes", "")}), _DRAFT_SCHEMA, self._reference_paths(session), session.get("model") if session.get("model_explicit", True) else None, role="character_description")
        if any(not isinstance(draft.get(key), str) or not draft[key].strip() for key in ("description", "identity")):
            raise QuickCharacterWizardError("The model returned an empty description or identity. Retry analysis.")
        if any(not isinstance(draft.get(key), list) or any(not isinstance(value, str) for value in draft[key])
               for key in ("observations", "proposals", "questions")):
            raise QuickCharacterWizardError("The model returned invalid design details. Retry analysis.")
        # Keep the editable brief self-contained even if the model places its
        # detailed design facts only in the observations field.
        draft["description"] = draft["description"].strip() + "\n" + "\n".join(draft["observations"])
        with self._lock(sid):
            current = self._read(sid)
            if current["revision_id"] != revision_id or current["status"] == "ABANDONED":
                return
            current.update({key: draft[key] for key in _DRAFT_SCHEMA["required"]})
            current.update(status="NEEDS_INPUT" if draft["questions"] else "DRAFT_READY",
                           proposals_approved=False, revision_id=uuid4().hex,
                           job={"kind": "draft", "status": "COMPLETE", "error": ""})
            if context:
                current["draft_workflow_id"] = context["id"]
            self._write(current)

    def generate_draft(self, sid: str, revision_id: str, answers: list | None = None) -> dict:
        with self._lock(sid):
            session = self._read(sid)
            self._editable(session, revision_id)
            if answers is not None:
                if not isinstance(answers, list) or any(not isinstance(a, dict) for a in answers):
                    raise QuickCharacterWizardError("Submit an answer for each current question.")
                answer_map = {str(a.get("question")): str(a.get("answer") or "").strip() for a in answers}
                if any(not answer_map.get(q) for q in session["questions"]):
                    raise QuickCharacterWizardError("Answer each current question before continuing.")
                session["answers"].extend({"question": q, "answer": answer_map[q]} for q in session["questions"])
            session.update(status="DRAFTING", proposals_approved=False, selected={},
                           job={"kind": "draft", "status": "RUNNING", "error": ""})
            self._write(session)
            self._submit(sid, self._draft_job, revision_id)
            return self._public(session)

    def update_draft(self, sid: str, revision_id: str, payload: dict) -> dict:
        with self._lock(sid):
            session = self._read(sid)
            self._editable(session, revision_id)
            description, identity = str(payload.get("description") or "").strip(), str(payload.get("identity") or "").strip()
            if not description or not identity:
                raise QuickCharacterWizardError("Description and prompt identity are required.")
            if session["questions"]:
                raise QuickCharacterWizardConflict("Answer the current questions before approving the description.")
            approved = payload.get("proposals_approved") is True
            proposals = payload.get("proposals", session["proposals"])
            if not isinstance(proposals, list) or any(not isinstance(p, str) for p in proposals):
                raise QuickCharacterWizardError("Proposed details must be a list of descriptions.")
            proposals = [p.strip() for p in proposals if p.strip()]
            if session.get("style_mode") == "universe":
                preserve = text(payload.get("preserve", session["preserve"]), "Preserve instructions")
                changes = text(payload.get("changes", session["changes"]), "Change instructions")
                if preserve != session["preserve"] or changes != session["changes"]:
                    session.update(preserve=preserve, changes=changes, description=description, identity=identity,
                                   revision_id=uuid4().hex, selected={}, proposals_approved=False, status="DRAFTING",
                                   job={"kind": "draft", "status": "RUNNING", "error": ""})
                    for candidate in session["candidates"]:
                        candidate["stale"] = True
                    self._write(session)
                    self._submit(sid, self._draft_job, session["revision_id"])
                    return self._public(session)
            changed = description != session["description"] or identity != session["identity"] or proposals != session["proposals"]
            if changed and session.get("reconstruction_id"):
                revised = self._reconstruction().revise(session["reconstruction_id"], description, identity, proposals)
                session.update(reconstruction_id=revised["id"], target_hash=revised["target_hash"])
            session.update(description=description, identity=identity, proposals=proposals, proposals_approved=approved)
            if changed:
                session.update(revision_id=uuid4().hex, selected={})
                for c in session["candidates"]:
                    c["stale"] = True
            session.update(status="DRAFT_READY", job={"kind": "draft", "status": "COMPLETE", "error": ""})
            self._write(session)
            return self._public(session)

    def _generation(self):
        if self.generation_service is None:
            from zet.services.ai_job_coordinator import image_services
            self.generation_service = image_services(self.app)[0]
        return self.generation_service

    def _reconstruction(self):
        return self._generation().reconstruction

    def reconstruction_options(self):
        return {**self._reconstruction().options(), "default_model": resolve_role_model(self.app.config, "character_description")}

    def render(self, sid: str, revision_id: str, view: str, instructions: str = "", candidate_id: str = "",
               item_ids: list | None = None) -> dict:
        with self._lock(sid):
            session = self._read(sid)
            self._editable(session, revision_id)
            if view not in self._views(session):
                raise QuickCharacterWizardError("Unknown character view.")
            if session["questions"] or not session["description"] or not session["proposals_approved"]:
                raise QuickCharacterWizardConflict("Review and approve the description and proposed details first.")
            anchor = session["selected"].get("FRONT")
            if view != "FRONT" and not anchor:
                raise QuickCharacterWizardConflict("Approve a front image before generating other views.")
            refinement_base = None
            if instructions or item_ids:
                eligible = [c for c in session["candidates"] if c["view"] == view and not c["stale"]
                            and c["revision_id"] == revision_id and c["status"] in {"READY", "REVIEW_FAILED"}]
                refinement_base = next((c for c in eligible if c["candidate_id"] == candidate_id), None) if candidate_id else (eligible[-1] if eligible else None)
                if not refinement_base:
                    raise QuickCharacterWizardConflict("Choose a current image to refine.")
                if view != "FRONT" and refinement_base["anchor_id"] != anchor:
                    raise QuickCharacterWizardConflict("This view used a previous front. Generate it again.")
            if session.get("reconstruction_id") and refinement_base:
                if not refinement_base.get("comparison") and not text(instructions, "Refinement"):
                    raise QuickCharacterWizardConflict("Retry image review before applying a correction.")
                comparison = refinement_base.get("comparison") or {"items": []}
                correction_items(comparison, item_ids or [], text(instructions, "Refinement"))
                correction_key = fingerprint([session["revision_id"], refinement_base["candidate_id"],
                    comparison.get("id"), sorted(item_ids or []), instructions, anchor])
                if any(c.get("correction_key") == correction_key and c["status"] != "FAILED" for c in session["candidates"]):
                    return self._public(session)
            candidate = {"candidate_id": uuid4().hex, "view": view, "revision_id": revision_id,
                         "anchor_id": anchor if view != "FRONT" else None, "request_id": "",
                         "status": "QUEUING", "error": "", "review": "", "refinements": [],
                         "stale": False, "instructions": str(instructions or "").strip(), "created_at": self._now()}
            candidate["refinement_base_id"] = refinement_base["candidate_id"] if refinement_base else None
            if session.get("reconstruction_id"):
                candidate.update(reconstruction_id=session["reconstruction_id"], target_hash=session["target_hash"])
                if refinement_base:
                    candidate["correction_key"] = correction_key
            session["candidates"].append(candidate)
            session["status"] = "RENDERING"
            self._write(session)
            self._submit(sid, self._render_job, candidate["candidate_id"], item_ids)
            return self._public(session)

    def _render_job(self, sid: str, candidate_id: str, item_ids: list | None) -> None:
        session = self._read(sid)
        candidate = next(c for c in session["candidates"] if c["candidate_id"] == candidate_id)
        session = {**session, **candidate.get("inputs", {})}
        view = candidate["view"]
        anchor = candidate["anchor_id"]
        instructions = candidate["instructions"]
        refinement_base = next((c for c in session["candidates"] if c["candidate_id"] == candidate["refinement_base_id"]), None)
        try:
            paths = self._reference_paths(session)
            labels = [r["caption"] for r in self._ordered_references(session)]
            if view != "FRONT":
                front = next(c for c in session["candidates"] if c["candidate_id"] == anchor)
                paths.insert(0, str(self._directory(sid) / front["filename"]))
                labels.insert(0, "Approved front: preserve this identity, clothing, equipment and style; change only viewing angle")
            if refinement_base:
                paths.insert(0, str(self._directory(sid) / refinement_base["filename"]))
                labels.insert(0, "Edit this previous candidate for the requested view: apply the correction and preserve other details")
            framing = "head-to-toe full body, feet visible" if session["framing"] == "full_body" else "head-and-shoulders portrait"
            angles = {"FRONT": "straight front, zero-degree rotation, face centered and both shoulders equally visible",
                      "FRONT_LEFT_3_4": "front-left three-quarter, camera on the subject's anatomical left; head and body face screen-left at 45 degrees, near anatomical-left side visible",
                      "FRONT_RIGHT_3_4": "front-right three-quarter, camera on the subject's anatomical right; head and body face screen-right at 45 degrees, near anatomical-right side visible",
                      "LEFT_PROFILE": "strict left profile, camera on the subject's anatomical left; head and body face screen-left at 90 degrees, only anatomical-left eye visible",
                      "RIGHT_PROFILE": "strict right profile, camera on the subject's anatomical right; head and body face screen-right at 90 degrees, only anatomical-right eye visible"}
            prompt = (f"One character, {framing}; {angles[view]}. Neutral pose and plain neutral background. "
                      "Preserve the reference art style, identity, outfit, equipment and anatomical asymmetry. "
                      "Rotate head and body together; gaze follows the facing direction, without turning the face back toward camera. "
                      "The requested view overrides any source pose or angle mentioned below. References provide appearance, "
                      "not a camera angle to copy. Do not mirror the character or make a multi-view sheet.\n"
                      + "Identity: " + session["identity"] + "\nApproved description: " + session["description"]
                      + "\nApproved completion details: " + "\n".join(session["proposals"])
                      + "\nExplicit changes override conflicting source details: " + session.get("changes", "")
                      + "\nRefinement: " + candidate["instructions"])
            width, height = (832, 1216) if session["framing"] == "full_body" else (1024, 1024)
            payload = {"mode": "img2img", "count": 1, "prompt": prompt,
                "negative_prompt": "multiple characters, extra limbs, mirrored asymmetry, text, labels, collage",
                "width": width, "height": height, "reference_images": [
                    {"label": label, "image": base64.b64encode(Path(path).read_bytes()).decode("ascii")}
                    for path, label in zip(paths, labels)]}
            if session.get("reconstruction_id"):
                # Legacy source pixels are analysis-only; use only styled candidate/front renders here.
                refs = []
                if refinement_base:
                    refs.append(("Candidate to correct; retain unaffected target appearance",
                        self.image_path(sid, candidate_id=refinement_base["candidate_id"]).read_bytes()))
                elif view != "FRONT":
                    refs.append(("Approved styled front; change camera angle only",
                        self.image_path(sid, candidate_id=anchor).read_bytes()))
                context = (f"One character, {framing}; {angles[view]}. Neutral pose, plain neutral background. "
                    "Rotate head and body together; gaze follows facing direction. Do not mirror anatomical "
                    "asymmetry or turn toward camera to show hidden features. One view, no sheet.")
                report_id = candidate.get("correction_report_id",
                    refinement_base["comparison"]["id"] if refinement_base and refinement_base.get("comparison") else "")
                payload = {**self._reconstruction().render_spec(session["reconstruction_id"], context, refs,
                    report_id=report_id, item_ids=item_ids if report_id else [], instructions=candidate["instructions"]), "width": width, "height": height,
                    "negative_prompt": "multiple characters, extra limbs, mirrored asymmetry, text, labels, collage"}
                candidate["view_context"] = context
            self._dispatch_candidate(sid, candidate, payload)
        except Exception as exc:
            from zet.services.storage_health_service import pause_on_storage_error
            pause_on_storage_error(self.app.config, exc)
            with self._lock(sid):
                current = self._read(sid)
                if current["status"] not in {"ABANDONED", "ACCEPTED"}:
                    target = next(c for c in current["candidates"] if c["candidate_id"] == candidate_id)
                    target.update(status="FAILED", error=str(exc))
                    current["status"] = "FAILED"
                    self._write(current)

    def _dispatch_candidate(self, sid, candidate, payload, seeds=None):
        with self._lock(sid):
            current = self._read(sid)
            if (current["status"] in {"ABANDONED", "ACCEPTED"} or (not current.get("minor_character") and
                    (current["revision_id"] != candidate["revision_id"] or
                     (candidate["view"] != "FRONT" and current["selected"].get("FRONT") != candidate["anchor_id"])))):
                return
            target = next(c for c in current["candidates"] if c["candidate_id"] == candidate["candidate_id"])
            previous = target.get("render_request_id")
            if previous:
                try:
                    result = self._generation().status(previous)
                    target.update(request_id=previous, status="QUEUED" if result["status"] in {"QUEUED", "RUNNING", "COMPLETE"} else "FAILED")
                    self._write(current)
                    return
                except KeyError:
                    pass
            target.update(prompt=payload["prompt"], render_payload=payload, render_request_id=uuid4().hex)
            if candidate.get("view_context"):
                target["view_context"] = candidate["view_context"]
            self._write(current)
            payload = {**payload, "ai_owner": {"session_id": sid, "candidate_id": candidate["candidate_id"]},
                       "ai_workflow": "Minor Characters"}
            result = self._generation().submit(payload, request_id=target["render_request_id"], seeds=seeds)
            target.update(request_id=result["request_id"], status="QUEUED")
            self._write(current)

    def retry_render(self, sid, revision_id, candidate_id):
        with self._lock(sid):
            session = self._read(sid)
            self._editable(session, revision_id)
            old = next((c for c in session["candidates"] if c["candidate_id"] == candidate_id), None)
            if (not old or old["status"] != "FAILED" or not old.get("render_payload") or old["stale"]
                    or old["revision_id"] != revision_id
                    or (old["view"] != "FRONT" and old["anchor_id"] != session["selected"].get("FRONT"))):
                raise QuickCharacterWizardConflict("Choose a failed current render with saved inputs.")
            previous = self._generation()._jobs.get(old.get("render_request_id"))
            if previous and self._generation().status(previous["request_id"])["status"] in {"QUEUED", "RUNNING", "COMPLETE"}:
                old.update(status="QUEUED", request_id=previous["request_id"], error="")
                self._write(session)
                return self._public(session)
            candidate = {key: old[key] for key in ("view", "revision_id", "anchor_id", "refinement_base_id", "instructions")}
            candidate.update(candidate_id=uuid4().hex, request_id="", status="QUEUING", stale=False,
                             error="", review="", refinements=[], retry_of=candidate_id, created_at=self._now())
            for key in ("reconstruction_id", "target_hash", "view_context"):
                if key in old:
                    candidate[key] = old[key]
            session["candidates"].append(candidate)
            session["status"] = "RENDERING"
            self._write(session)
            seeds = [previous["children"][0]["seed"]] if previous and previous.get("children") else None
            self._submit(sid, self._dispatch_candidate, candidate, old["render_payload"], seeds)
            return self._public(session)

    def _review_job(self, sid: str, candidate_id: str) -> None:
        session = self._read(sid)
        candidate = next(c for c in session["candidates"] if c["candidate_id"] == candidate_id)
        from zet.services.ai_workflow_service import current_workflow
        context = current_workflow.get()
        if context is not None:
            context["admission"] = lambda: self._review_admission(sid, candidate)
        session = {**session, **candidate.get("inputs", {})}
        paths = [str(self._directory(sid) / candidate["filename"]), *self._reference_paths(session)]
        if candidate["anchor_id"]:
            front = next(c for c in session["candidates"] if c["candidate_id"] == candidate["anchor_id"])
            paths.append(str(self._directory(sid) / front["filename"]))
        comparison = None
        if candidate.get("reconstruction_id"):
            feedback = []
            current = candidate
            candidates = {c["candidate_id"]: c for c in session["candidates"]}
            while current:
                if current.get("instructions"):
                    feedback.append(current["instructions"])
                current = candidates.get(current.get("refinement_base_id"))
            context = candidate["view_context"]
            if feedback:
                context += "\nOperator feedback, oldest to newest (latest takes precedence):\n" + "\n".join(reversed(feedback))
            comparison = self._reconstruction().compare(candidate["reconstruction_id"], self.image_path(sid, candidate_id=candidate_id).read_bytes(),
                {"session_id": sid, "candidate_id": candidate_id, "revision_id": candidate["revision_id"],
                 "anchor_id": candidate["anchor_id"]}, context,
                Path(paths[-1]).read_bytes() if candidate["anchor_id"] else None, review_role="character_review",
                review_model=session["model"] if session.get("model_explicit", True) else "")
            review = {"review": comparison["summary"],
                      "refinements": [item["correction"] for item in comparison["items"] if item["correction"]]}
        else:
            review = self._ask("Review the first image against the other reference images and this approved edited description. "
                           "Explicit changes in the requested prompt override source details; do not restore removed equipment. "
                           "Check identity, requested viewing angle, framing, clothing, equipment, anatomical asymmetry "
                           "and consistency with the approved front when supplied. Only report visible mismatches; "
                               "give actionable refinements.\nRequested prompt: " + candidate["prompt"], _REVIEW_SCHEMA, paths, session.get("model") if session.get("model_explicit", True) else None, role="character_review")
        with self._lock(sid):
            current = self._read(sid)
            if current["status"] == "ABANDONED" or (not current.get("minor_character") and current["revision_id"] != candidate["revision_id"]):
                return
            target = next(c for c in current["candidates"] if c["candidate_id"] == candidate_id)
            target.update(status="READY", review=review["review"], refinements=review["refinements"], error="")
            if comparison:
                target["comparison"] = comparison
            if not current.get("minor_character"):
                current.update(status="REVIEW_READY", job={"kind": "review", "status": "COMPLETE", "error": ""})
            self._write(current)

    def _start_review(self, sid, candidate_id):
        self._submit(sid, self._review_job, candidate_id)

    def _review_harvest(self, sid, candidate):
        return self.app.ai_proxy_service.ai_proxy_path_service.jobs.assert_image_harvest(
            candidate.get("render_request_id") or candidate.get("request_id") or "",
            self._directory(sid) / candidate["filename"], candidate.get("sha256", ""))

    @contextmanager
    def _review_admission(self, sid, candidate):
        with self._lock(sid):
            session = self._read(sid)
            current = next((item for item in session["candidates"] if item["candidate_id"] == candidate["candidate_id"]), None)
            if (not current or session.get("deleted_at") or session["status"] in {"ABANDONED", "ACCEPTED"}
                    or current.get("sha256") != candidate.get("sha256") or current.get("stale")
                    or (session.get("minor_character") and candidate["candidate_id"] not in self._working_ids(session))
                    or (not session.get("minor_character") and session["revision_id"] != candidate["revision_id"])):
                raise QuickCharacterWizardConflict("Image review was superseded before publication")
            self._review_harvest(sid, current)
            yield

    def get_session(self, sid: str) -> dict:
        with self._lock(sid):
            session = self._read(sid)
            if session["status"] in {"ACCEPTED", "ABANDONED"}:
                return self._public(session)
            with _LOCK:
                active = self._key(sid) in _ACTIVE
                pending = self._pending_workflow(sid) if not active and session["job"]["status"] == "RUNNING" else False
                active = active or pending
            if session["job"]["status"] == "RUNNING" and not active:
                reviewing = next((c for c in session["candidates"] if c["status"] == "REVIEWING"), None)
                if reviewing is not None:
                    self._start_review(sid, reviewing["candidate_id"])
                    return self._public(self._read(sid))
                session["job"].update(status="FAILED", error="Analysis was interrupted. Retry analysis.")
                session["status"] = "FAILED"
                self._write(session)
            if active:
                return self._public(session)
            for c in session["candidates"]:
                if c["status"] == "QUEUING":
                    request_id = c.get("render_request_id")
                    if request_id and self._generation()._read_saved_job(request_id) is not None:
                        c.update(status="QUEUED", request_id=request_id)
                    else:
                        c.update(status="FAILED", error="Submission was interrupted. Generate another candidate to retry.")
                        session["status"] = "FAILED"
                    self._write(session)
                if c["status"] == "REVIEWING":
                    self._start_review(sid, c["candidate_id"])
                    continue
                if c["status"] not in {"QUEUED", "RUNNING"}:
                    continue
                changed = False
                try:
                    result = self._generation().status(c["request_id"])
                    if result["status"] in {"QUEUED", "RUNNING"}:
                        changed = c["status"] != result["status"]
                        c["status"] = result["status"]
                    elif result["status"] == "COMPLETE" and result["images"]:
                        contents, mime, generation = self._generation().library_result(c["request_id"], result["images"][0]["index"])
                        suffix = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}[mime]
                        c["filename"] = f"renders/{c['candidate_id']}.{suffix}"
                        path = self._directory(sid) / c["filename"]
                        path.parent.mkdir(parents=True, exist_ok=True)
                        write_bytes_atomic(path, contents)
                        c.update(status="REVIEWING", mime_type=mime, sha256=hashlib.sha256(contents).hexdigest(), seed=generation.get("seed"))
                        session["job"] = {"kind": "review", "status": "RUNNING", "error": ""}
                        self._write(session)
                        c["render_harvest"] = self._review_harvest(sid, c)
                        self._write(session)
                        self._start_review(sid, c["candidate_id"])
                        return self._public(self._read(sid))
                    else:
                        c.update(status="FAILED", error=result.get("error") or "The render did not produce an image.")
                        session["status"] = "FAILED"
                        changed = True
                except OSError as exc:
                    error = f"Image collection is temporarily unavailable: {exc}"
                    changed = c.get("error") != error
                    c["error"] = error
                except Exception as exc:
                    from zet.services.storage_health_service import pause_on_storage_error
                    pause_on_storage_error(self.app.config, exc)
                    c.update(status="FAILED", error=str(exc))
                    session["status"] = "FAILED"
                    changed = True
                if changed:
                    self._write(session)
            return self._public(session)

    def retry_review(self, sid: str, revision_id: str, candidate_id: str) -> dict:
        with self._lock(sid):
            session = self._read(sid)
            self._editable(session, revision_id)
            c = next((c for c in session["candidates"] if c["candidate_id"] == candidate_id), None)
            if not c or c["status"] != "REVIEW_FAILED" or c["revision_id"] != revision_id or c["stale"]:
                raise QuickCharacterWizardError("Choose a current image whose review failed.")
            c.update(status="REVIEWING", error="")
            session["job"] = {"kind": "review", "status": "RUNNING", "error": ""}
            self._write(session)
            self._submit(sid, self._review_job, candidate_id)
            return self._public(session)

    def select(self, sid: str, revision_id: str, candidate_id: str) -> dict:
        with self._lock(sid):
            session = self._read(sid)
            self._editable(session, revision_id)
            candidate = next((c for c in session["candidates"] if c["candidate_id"] == candidate_id), None)
            if not candidate or candidate["status"] not in {"READY", "REVIEW_FAILED"} or candidate["stale"] or candidate["revision_id"] != revision_id:
                raise QuickCharacterWizardConflict("Choose a rendered image from the current draft.")
            view = candidate["view"]
            if view == "FRONT" and session["selected"].get(view) != candidate_id:
                session["selected"] = {view: candidate_id}
                for c in session["candidates"]:
                    if c["view"] != "FRONT":
                        c["stale"] = c["anchor_id"] != candidate_id
            elif view != "FRONT" and candidate["anchor_id"] != session["selected"].get("FRONT"):
                raise QuickCharacterWizardConflict("This image used a previous front. Regenerate it.")
            session["selected"][view] = candidate_id
            session["status"] = "READY_TO_SAVE" if all(v in session["selected"] for v in self._views(session)) else "REVIEW_READY"
            self._write(session)
            return self._public(session)

    def accept(self, sid: str, revision_id: str) -> dict:
        with self._lock(sid):
            session = self._read(sid)
            if session["status"] == "ACCEPTED":
                if revision_id != session["revision_id"]:
                    raise QuickCharacterWizardConflict("This draft changed. Reload the current revision.")
                return self._public(session)
            self._editable(session, revision_id)
            if not session["proposals_approved"]:
                raise QuickCharacterWizardConflict("Approve the description and proposed details before saving.")
            if not all(v in session["selected"] for v in self._views(session)):
                raise QuickCharacterWizardConflict("Approve all three current views before saving.")
            from zet.services.quick_character_publication_service import publish_quick_character
            session["publication"] = publish_quick_character(self.app, session, self._directory(sid))
            session["status"] = "ACCEPTED"
            self._write(session)
            return self._public(session)

    def abandon(self, sid: str, revision_id: str) -> dict:
        with self._lock(sid):
            session = self._read(sid)
            if session["status"] == "ACCEPTED":
                raise QuickCharacterWizardConflict("An accepted session cannot be abandoned.")
            if revision_id != session["revision_id"]:
                raise QuickCharacterWizardConflict("This draft changed. Reload the current revision.")
            session.update(status="ABANDONED", job={"kind": "abandon", "status": "COMPLETE", "error": ""})
            for c in session["candidates"]:
                if c["status"] in {"QUEUING", "QUEUED", "RUNNING", "REVIEWING"}:
                    c["status"] = "ABANDONED"
            self._write(session)
            return self._public(session)

    def image_path(self, sid: str, *, reference_index: int | None = None, candidate_id: str = "") -> Path:
        session = self._read(sid)
        if reference_index is not None:
            record = next((r for r in session["references"] if r["index"] == reference_index), None)
        else:
            record = next((c for c in session["candidates"] if c["candidate_id"] == candidate_id), None)
        if not record or not record.get("filename"):
            raise QuickCharacterWizardError("Wizard image was not found.")
        path = self._directory(sid) / record["filename"]
        if not path.resolve().is_relative_to(self._directory(sid).resolve()) or not path.is_file():
            raise QuickCharacterWizardError("Wizard image is unavailable.")
        return path
