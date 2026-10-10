from __future__ import annotations

import base64
import binascii
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import threading
from uuid import uuid4

from PIL import Image

from zet.services.atomic_file_service import write_json_atomic
from zet.services.entity_library_service import EntityLibraryServiceError
from zet.services.ollama_model_service import OllamaModelService
from zet.services.structured_ai_service import codex_json


class QuickCharacterWizardError(ValueError):
    pass


class QuickCharacterWizardConflict(QuickCharacterWizardError):
    pass


_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="quick-character")
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
        self.ollama = OllamaModelService(timeout_seconds=900)

    def _directory(self, session_id: str) -> Path:
        if not re.fullmatch(r"[0-9a-f]{32}", str(session_id)):
            raise QuickCharacterWizardError("Unknown quick character session.")
        return self.root / session_id

    def _key(self, session_id: str) -> str:
        return str(self._directory(session_id).resolve())

    def _lock(self, session_id: str):
        with _LOCK:
            return _SESSION_LOCKS.setdefault(self._key(session_id), threading.RLock())

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _read(self, session_id: str) -> dict:
        try:
            return json.loads((self._directory(session_id) / "session.json").read_text(encoding="utf-8"))
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
        value = json.loads(json.dumps(session))
        for item in value["references"]:
            item.pop("filename", None)
            item["url"] = f"/api/quick-character-wizard/{session['session_id']}/references/{item['index']}"
        for candidate in value["candidates"]:
            candidate["image_url"] = (f"/api/quick-character-wizard/{session['session_id']}/images/{candidate['candidate_id']}"
                                      if candidate.get("filename") else "")
            candidate.pop("filename", None)
        value["views"] = self._views(session)
        value["busy"] = self._busy(session)
        return value

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
            if hashlib.sha256(data).hexdigest() != asset["checksum"]:
                raise QuickCharacterWizardConflict("A library reference changed outside the library. Refresh it first.")
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
            raise QuickCharacterWizardError("Choose a readable PNG, JPEG, or WEBP reference.") from exc
        return data, extension

    def create_session(self, payload: dict) -> dict:
        name = str(payload.get("name") or "").strip()
        refs = payload.get("references")
        framing, side = payload.get("framing", "full_body"), payload.get("side", "left")
        if not name:
            raise QuickCharacterWizardError("Character name is required.")
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
                            "checksum": hashlib.sha256(data).hexdigest()})
        session = {"session_id": sid, "name": name, "notes": str(payload.get("notes") or "").strip(),
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
            if key in _ACTIVE:
                raise QuickCharacterWizardConflict("A wizard task is already running.")
            _ACTIVE.add(key)

        def run():
            try:
                target(sid, *args)
            except Exception as exc:
                with self._lock(sid):
                    session = self._read(sid)
                    if session["status"] not in {"ABANDONED", "ACCEPTED"}:
                        session["status"] = "FAILED"
                        session["job"].update(status="FAILED", error=str(exc))
                        for candidate in session["candidates"]:
                            if candidate["status"] == "REVIEWING":
                                candidate.update(status="REVIEW_FAILED", error=str(exc))
                        self._write(session)
            finally:
                with _LOCK:
                    _ACTIVE.discard(key)
        _POOL.submit(run)

    def _ask(self, prompt: str, schema: dict, images: list[str]) -> dict:
        model = self.app.config.ai_quick_character_wizard_model
        system = ("You are the Zet Quick Character Wizard. Follow the JSON schema. Treat captions as reference roles. "
                  "Preserve stable identity, clothing, equipment, style and anatomical asymmetry. "
                  "Clearly identify proposed unseen details, never present them as observed facts.")
        if model.startswith("codex:"):
            return codex_json(self.project_root, model.removeprefix("codex:"), system, prompt, schema, images,
                              label="Quick Character Wizard", error_type=QuickCharacterWizardError)
        return self.ollama.generate_json(model, system, prompt, schema, images=images)

    def _reference_paths(self, session: dict) -> list[str]:
        return [str(self._directory(session["session_id"]) / ref["filename"]) for ref in session["references"]]

    def _draft_job(self, sid: str, revision_id: str) -> None:
        session = self._read(sid)
        draft = self._ask(
            "Analyze these ordered references (first is primary identity). Return a compact, editable image-generation "
            "description including identity, outfit, equipment, style and view-specific asymmetry with explicit anatomical sides when supported. Separate observations "
            "from minimal consistent proposals needed for unseen regions. Ask only important unresolved conflicts. "
            "Keep source camera angle, gaze direction, pose, crop and background out of the reusable description and "
            "observations; include only stable appearance and design facts. "
            "No character biography or full template. Honor user notes and answers.\n" + json.dumps({
                "captions": [r["caption"] for r in session["references"]], "notes": session["notes"],
                "answers": session["answers"], "framing": session["framing"], "side": session["side"],
                "current_description": session["description"]}), _DRAFT_SCHEMA, self._reference_paths(session))
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
            changed = description != session["description"] or identity != session["identity"] or proposals != session["proposals"]
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
            from zet.services.ad_hoc_image_generation_service import AdHocImageGenerationService
            self.generation_service = AdHocImageGenerationService(self.app, self.project_root)
        return self.generation_service

    def render(self, sid: str, revision_id: str, view: str, instructions: str = "", candidate_id: str = "") -> dict:
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
            if instructions:
                eligible = [c for c in session["candidates"] if c["view"] == view and not c["stale"]
                            and c["revision_id"] == revision_id and c["status"] in {"READY", "REVIEW_FAILED"}]
                refinement_base = next((c for c in eligible if c["candidate_id"] == candidate_id), None) if candidate_id else (eligible[-1] if eligible else None)
                if not refinement_base:
                    raise QuickCharacterWizardConflict("Choose a current image to refine.")
            candidate = {"candidate_id": uuid4().hex, "view": view, "revision_id": revision_id,
                         "anchor_id": anchor if view != "FRONT" else None, "request_id": "",
                         "status": "QUEUING", "error": "", "review": "", "refinements": [],
                         "stale": False, "instructions": str(instructions or "").strip(), "created_at": self._now()}
            candidate["refinement_base_id"] = refinement_base["candidate_id"] if refinement_base else None
            session["candidates"].append(candidate)
            session["status"] = "RENDERING"
            self._write(session)
            try:
                paths = self._reference_paths(session)
                labels = [r["caption"] for r in session["references"]]
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
                          + "\nRefinement: " + candidate["instructions"])
                candidate["prompt"] = prompt
                width, height = (832, 1216) if session["framing"] == "full_body" else (1024, 1024)
                result = self._generation().submit({"mode": "img2img", "count": 1, "prompt": prompt,
                    "negative_prompt": "multiple characters, extra limbs, mirrored asymmetry, text, labels, collage",
                    "width": width, "height": height, "reference_images": [
                        {"label": label, "image": base64.b64encode(Path(path).read_bytes()).decode("ascii")}
                        for path, label in zip(paths, labels)]})
                candidate.update(request_id=result["request_id"], status="QUEUED")
            except Exception as exc:
                candidate.update(status="FAILED", error=str(exc))
                session["status"] = "FAILED"
            self._write(session)
            return self._public(session)

    def _review_job(self, sid: str, candidate_id: str) -> None:
        session = self._read(sid)
        candidate = next(c for c in session["candidates"] if c["candidate_id"] == candidate_id)
        paths = [str(self._directory(sid) / candidate["filename"]), *self._reference_paths(session)]
        if candidate["anchor_id"]:
            front = next(c for c in session["candidates"] if c["candidate_id"] == candidate["anchor_id"])
            paths.append(str(self._directory(sid) / front["filename"]))
        review = self._ask("Review the first image against the other reference images and this approved description. "
                           "Check identity, requested viewing angle, framing, clothing, equipment, anatomical asymmetry "
                           "and consistency with the approved front when supplied. Only report visible mismatches; "
                           "give concise actionable refinements.\nRequested prompt: " + candidate["prompt"], _REVIEW_SCHEMA, paths)
        with self._lock(sid):
            current = self._read(sid)
            if current["status"] == "ABANDONED" or current["revision_id"] != candidate["revision_id"]:
                return
            target = next(c for c in current["candidates"] if c["candidate_id"] == candidate_id)
            target.update(status="READY", review=review["review"], refinements=review["refinements"], error="")
            current.update(status="REVIEW_READY", job={"kind": "review", "status": "COMPLETE", "error": ""})
            self._write(current)

    def get_session(self, sid: str) -> dict:
        with self._lock(sid):
            session = self._read(sid)
            if session["status"] in {"ACCEPTED", "ABANDONED"}:
                return self._public(session)
            with _LOCK:
                active = self._key(sid) in _ACTIVE
            if session["job"]["status"] == "RUNNING" and not active:
                session["job"].update(status="FAILED", error="Analysis was interrupted. Retry analysis or image review.")
                session["status"] = "FAILED"
                for c in session["candidates"]:
                    if c["status"] == "REVIEWING":
                        c["status"] = "REVIEW_FAILED"
                self._write(session)
            for c in session["candidates"]:
                if c["status"] == "QUEUING":
                    c.update(status="FAILED", error="Submission was interrupted. Check Image Generation before retrying.")
                    session["status"] = "FAILED"
                    self._write(session)
                if c["status"] not in {"QUEUED", "RUNNING"}:
                    continue
                try:
                    result = self._generation().status(c["request_id"])
                    if result["status"] in {"QUEUED", "RUNNING"}:
                        c["status"] = result["status"]
                    elif result["status"] == "COMPLETE" and result["images"]:
                        contents, mime = self._generation().image(c["request_id"], result["images"][0]["index"])
                        suffix = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}[mime]
                        c["filename"] = f"renders/{c['candidate_id']}.{suffix}"
                        path = self._directory(sid) / c["filename"]
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(contents)
                        c.update(status="REVIEWING", mime_type=mime)
                        session["job"] = {"kind": "review", "status": "RUNNING", "error": ""}
                        self._write(session)
                        self._submit(sid, self._review_job, c["candidate_id"])
                        return self._public(self._read(sid))
                    else:
                        c.update(status="FAILED", error=result.get("error") or "The render did not produce an image.")
                        session["status"] = "FAILED"
                except Exception as exc:
                    c.update(status="FAILED", error=str(exc))
                    session["status"] = "FAILED"
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
            if not candidate or candidate["status"] != "READY" or candidate["stale"] or candidate["revision_id"] != revision_id:
                raise QuickCharacterWizardConflict("Choose a reviewed image from the current revision.")
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
