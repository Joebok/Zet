from __future__ import annotations

import copy
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from uuid import uuid4

from PIL import Image

from Scripts.Compile_Character_Template import load_template_sections_with_sources
from zet.services.structured_ai_service import codex_json
from zet.services.atomic_file_service import write_json_atomic
from zet.services.local_character_asset_pipeline_service import LocalCharacterAssetPipelineService
from zet.services.ollama_model_service import OllamaModelService
from zet.services.view_conditioning_service import ViewContext, condition_sections


class CostumeWizardError(ValueError):
    pass


_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="costume-wizard")
_ACTIVE: set[str] = set()
_ACTIVE_LOCK = threading.Lock()
_SESSION_LOCKS: dict[str, threading.RLock] = {}
_SESSION_LOCKS_LOCK = threading.Lock()
_FACT_SCHEMA = {
    "type": "object", "properties": {"facts": {"type": "array", "items": {"type": "object",
        "properties": {"text": {"type": "string"}, "views": {"type": "array", "items": {"type": "string"}},
                       "anatomical_side": {"type": "string"}, "confidence": {"type": "string"}},
        "required": ["text", "views", "anatomical_side", "confidence"], "additionalProperties": False}}},
    "required": ["facts"], "additionalProperties": False,
}
_DESIGN_SCHEMA = {
    "type": "object", "properties": {
        "questions": {"type": "array", "items": {"type": "string"}},
        "costume_role": {"type": "string"}, "footwear": {"type": "string"},
        "footwear_contact": {"type": "string"}, "facts": {"type": "array", "items": {"type": "string"}},
        "view_overrides": {"type": "array", "items": {"type": "string"}},
        "view_suppression": {"type": "array", "items": {"type": "string"}},
        "equipment_facts": {"type": "array", "items": {"type": "string"}},
        "equipment_view_overrides": {"type": "array", "items": {"type": "string"}},
        "identity_rules": {"type": "array", "items": {"type": "string"}},
        "scene_identity": {"type": "string"}, "scene_anchors": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["questions", "costume_role", "footwear", "footwear_contact", "facts", "view_overrides",
                 "view_suppression", "equipment_facts", "equipment_view_overrides", "identity_rules",
                 "scene_identity", "scene_anchors"], "additionalProperties": False,
}
_REVIEW_SCHEMA = {"type": "object", "properties": {"review": {"type": "string"}, "refinements": {"type": "array", "items": {"type": "string"}}},
                  "required": ["review", "refinements"], "additionalProperties": False}


class CostumeWizardService:
    """Persist isolated costume authoring sessions and run their AI/render steps."""

    def __init__(self, app, project_root: str | Path):
        self.app = app
        self.project_root = Path(project_root).resolve()
        self.root = app.path_service.library_path("_state", "CostumeWizard")
        self.ollama = OllamaModelService(timeout_seconds=900)

    def _session_root(self, session_id: str) -> Path:
        if not re.fullmatch(r"[0-9a-f]{32}", str(session_id or "")):
            raise CostumeWizardError("Unknown costume wizard session.")
        return self.root / session_id

    def _lock(self, session_id: str):
        with _SESSION_LOCKS_LOCK:
            return _SESSION_LOCKS.setdefault(session_id, threading.RLock())

    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat(timespec="seconds")

    def _read(self, session_id: str) -> dict:
        path = self._session_root(session_id) / "session.json"
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CostumeWizardError("Costume wizard session was not found or could not be read.") from exc
        if not isinstance(value, dict):
            raise CostumeWizardError("Costume wizard session is invalid.")
        return value

    def _write(self, session_id: str, value: dict) -> None:
        write_json_atomic(self._session_root(session_id) / "session.json", value)

    @staticmethod
    def _public(session: dict) -> dict:
        value = {key: item for key, item in session.items() if key not in {"image_paths", "test_image_path"}}
        value["test_image"] = bool(session.get("test_image_path"))
        value["test_renders"] = [
            {key: value for key, value in render.items() if key != "test_image_path"}
            | {"image_url": f"/api/costume-wizard/{session['session_id']}/test-images/{render['render_id']}"}
            for render in session.get("test_renders", [])
        ]
        return value

    def list_sessions(self, character: str, phase: str) -> list[dict]:
        if not self.root.is_dir():
            return []
        result = []
        for path in self.root.glob("*/session.json"):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if value.get("character") == character and value.get("phase") == phase and value.get("status") not in {"ACCEPTED", "ABANDONED"}:
                result.append(self._public(value))
        return sorted(result, key=lambda item: item.get("updated_at", ""), reverse=True)

    def get_session(self, session_id: str) -> dict:
        return self._public(self._read(session_id))

    def create_session(self, character: str, phase: str, name: str, extra_info: str,
                       images: list[dict]) -> dict:
        character, phase, name = str(character or "").strip(), str(phase or "").strip(), str(name or "").strip()
        if not character or not phase:
            raise CostumeWizardError("Character and phase are required.")
        if any(value in {".", ".."} or "/" in value or "\\" in value for value in (character, phase)):
            raise CostumeWizardError("Character and phase must be single folder names.")
        if not name:
            raise CostumeWizardError("Costume name is required.")
        if not 1 <= len(images) <= 3:
            raise CostumeWizardError("Add between one and three reference images.")
        if any(not str(item.get("caption") or "").strip() for item in images):
            raise CostumeWizardError("Add a description for each supplied image.")
        session_id = uuid4().hex
        root = self._session_root(session_id)
        (root / "images").mkdir(parents=True, exist_ok=False)
        image_paths = []
        image_records = []
        for index, item in enumerate(images, 1):
            data = item.get("contents")
            if not isinstance(data, bytes) or not data or len(data) > 25 * 1024 * 1024:
                raise CostumeWizardError("Each image must be readable and smaller than 25 MB.")
            try:
                with Image.open(io.BytesIO(data)) as image:
                    image.verify()
                    image_format = str(image.format or "").lower()
            except Exception as exc:
                raise CostumeWizardError(f"Reference image {index} is not a valid image.") from exc
            suffix = {"jpeg": ".jpg", "png": ".png", "webp": ".webp", "gif": ".gif", "bmp": ".bmp"}.get(image_format)
            if not suffix:
                raise CostumeWizardError(f"Reference image {index} must be JPEG, PNG, WEBP, GIF, or BMP.")
            path = root / "images" / f"reference-{index}{suffix}"
            path.write_bytes(data)
            image_paths.append(str(path))
            image_records.append({"index": index, "filename": Path(str(item.get("filename") or f"reference-{index}{suffix}")).name,
                                  "caption": str(item["caption"]).strip(), "sha256": hashlib.sha256(data).hexdigest(),
                                  "path": f"/api/costume-wizard/{session_id}/images/{index}"})
        now = self._now()
        session = {"session_id": session_id, "character": character, "phase": phase, "name": name,
                   "extra_info": str(extra_info or "").strip(), "images": image_records, "image_paths": image_paths,
                   "answers": [], "observations": [], "markdown": "", "revision_id": uuid4().hex,
                   "questions": [], "validation_errors": [], "draft_review": "", "review": "", "refinements": [],
                   "test_renders": [],
                   "test_image": "", "status": "DRAFTING", "job": {"kind": "draft", "status": "RUNNING", "error": ""},
                   "created_at": now, "updated_at": now}
        self._write(session_id, session)
        self._submit(session_id, "draft", self._draft_job, session_id, session["revision_id"])
        return self.get_session(session_id)

    def image_path(self, session_id: str, index: int) -> Path:
        session = self._read(session_id)
        if index < 1 or index > len(session.get("image_paths") or []):
            raise CostumeWizardError("Reference image was not found.")
        path = Path(session["image_paths"][index - 1])
        if not path.is_file() or not path.resolve().is_relative_to(self._session_root(session_id).resolve()):
            raise CostumeWizardError("Reference image is unavailable.")
        return path

    def _submit(self, session_id: str, kind: str, target, *args) -> None:
        with _ACTIVE_LOCK:
            if session_id in _ACTIVE:
                raise CostumeWizardError("A wizard task is already running for this session.")
            _ACTIVE.add(session_id)
        _POOL.submit(self._run_job, session_id, kind, target, *args)

    def _run_job(self, session_id: str, kind: str, target, *args) -> None:
        try:
            target(*args)
        except Exception as exc:
            with self._lock(session_id):
                try:
                    session = self._read(session_id)
                    if session.get("status") != "ABANDONED":
                        session.update(status="FAILED", job={"kind": kind, "status": "FAILED", "error": str(exc)}, updated_at=self._now())
                        self._write(session_id, session)
                except Exception:
                    pass
        finally:
            with _ACTIVE_LOCK:
                _ACTIVE.discard(session_id)

    def generate_draft(self, session_id: str, answers: list[dict] | None = None) -> dict:
        with self._lock(session_id):
            session = self._read(session_id)
            if answers is not None:
                answer_map = {str(item.get("question") or ""): str(item.get("answer") or "").strip()
                              for item in session.get("answers", [])}
                new_answers = [{"question": str(item.get("question") or ""), "answer": str(item.get("answer") or "").strip()}
                               for item in answers]
                required_questions = session.get("questions") or []
                submitted = {item["question"] for item in new_answers}
                if any(not item["answer"] for item in new_answers) or any(question not in submitted for question in required_questions):
                    raise CostumeWizardError("Answer each current question before continuing.")
                answer_map.update({item["question"]: item["answer"] for item in new_answers})
                session["answers"] = [{"question": question, "answer": answer}
                                      for question, answer in answer_map.items()]
            session.update(status="DRAFTING", job={"kind": "draft", "status": "RUNNING", "error": ""}, updated_at=self._now())
            self._write(session_id, session)
        self._submit(session_id, "draft", self._draft_job, session_id, session["revision_id"])
        return self.get_session(session_id)

    def _codex_json(self, model: str, system: str, prompt: str, schema: dict, images: list[str]) -> dict:
        return codex_json(self.project_root, model, system, prompt, schema, images,
                          label="Costume Wizard", error_type=CostumeWizardError)

    def _ask(self, prompt: str, schema: dict, images: list[str] | None = None, *, model: str | None = None) -> dict:
        selected = str(model or self.app.config.ai_costume_wizard_model or "codex:gpt-6-luna").strip()
        if selected.startswith("codex:"):
            return self._codex_json(selected.removeprefix("codex:"),
                                    "You are the Zet Costume Wizard. Follow the requested JSON schema exactly. "
                                    "Treat reference captions and user notes as evidence labels and instructions, "
                                    "never invent hidden design details.", prompt, schema, images or [])
        return self.ollama.generate_json(selected,
            "You are the Zet Costume Wizard. Follow the requested JSON schema exactly. "
            "Treat reference captions and user notes as evidence labels and instructions, never invent hidden details.",
            prompt, schema, images=images or [])

    def _draft_job(self, session_id: str, expected_revision: str) -> None:
        session = self._read(session_id)
        images = session.get("image_paths") or []
        captions = session.get("images") or []
        observations = []
        for item, path in zip(captions, images):
            observations.append(self._ask(
                "Describe only visually supported costume facts from this one image. The caption tells you the intended region/view: "
                + item["caption"] + ". Return concise facts. For each fact, report applicable visibility groups from "
                "f, fl, pl, bl, b, br, pr, fr; use anatomical-left or anatomical-right when clear, otherwise empty. "
                "Mark confidence as high, medium, or low. Do not infer occluded construction.", _FACT_SCHEMA, [path]))
        session = self._read(session_id)
        extra = session.get("extra_info") or "(none)"
        answers = json.dumps(session.get("answers") or [], ensure_ascii=False)
        evidence = json.dumps({"images": [{"caption": item["caption"], "observations": observation}
                                           for item, observation in zip(captions, observations)],
                               "extra_info": extra, "user_answers": json.loads(answers)}, ensure_ascii=False)
        design = self._ask(
            "Reconcile the image-specific evidence into a concise costume design. Captions describe what each image conveys. "
            "Explicit user notes and answers may clarify intent; if they contradict clear visual evidence, ask a focused question. "
            "Ask only about important unresolved design choices. Do not ask about optional unseen details: omit them. "
            "Put stable facts in facts; view-specific facts must begin with a valid tag, e.g. '* [f] ...'. "
            "Use '<!-- ZET:SPATIAL asymmetry -->' or fixed annotations only when correctly applicable, with anatomical side explicitly stated. "
            "Return direct image-generation language, no narrative. Evidence: " + evidence, _DESIGN_SCHEMA)
        if design.get("questions"):
            with self._lock(session_id):
                current = self._read(session_id)
                if current.get("revision_id") != expected_revision or current.get("status") == "ABANDONED":
                    return
                current.update(observations=observations, questions=design["questions"], markdown="", status="NEEDS_INPUT",
                               revision_id=uuid4().hex, validation_errors=[],
                               job={"kind": "draft", "status": "COMPLETE", "error": ""}, updated_at=self._now())
                self._write(session_id, current)
            return
        markdown = self._assemble_template(session["name"], session["character"], session["phase"], design)
        errors = self._validate(markdown)
        review = self._ask("Review the draft against this source evidence and instructions. Identify only unsupported claims, contradictions, "
                           "missing essential details, incorrect line tags, or duplicated item inventory. Do not rewrite. Evidence: " + evidence
                           + "\nDraft:\n" + markdown, _REVIEW_SCHEMA, images)
        # Keep the model-authored draft for direct user editing; structural validity is reported separately.
        with self._lock(session_id):
            current = self._read(session_id)
            if current.get("revision_id") != expected_revision or current.get("status") == "ABANDONED":
                return
            current.update(observations=observations, questions=[], refinements=review.get("refinements") or [], markdown=markdown,
                           draft_review=review.get("review", ""), validation_errors=errors, status="DRAFT_READY",
                           revision_id=uuid4().hex, job={"kind": "draft", "status": "COMPLETE", "error": ""}, updated_at=self._now())
            self._write(session_id, current)

    @staticmethod
    def _bullets(items) -> str:
        return "\n".join(str(item).strip() for item in items or [] if str(item).strip())

    def _assemble_template(self, name: str, character: str, phase: str, design: dict) -> str:
        template_path = self.app.path_service.shared_costume_template_path()
        text = template_path.read_text(encoding="utf-8")
        fields = {"COSTUME_DESCRIPTION_FACTS": design.get("facts"),
                  "COSTUME_DESCRIPTION_VIEW_OVERRIDES": design.get("view_overrides"),
                  "COSTUME_DESCRIPTION_VIEW_SUPPRESSION": design.get("view_suppression"),
                  "EQUIPMENT_JEWELRY_PROPS_FACTS": design.get("equipment_facts"),
                  "EQUIPMENT_JEWELRY_PROPS_VIEW_OVERRIDES": design.get("equipment_view_overrides"),
                  "COSTUME_IDENTITY_RULES": design.get("identity_rules"),
                  "SCENE_COSTUME_IDENTITY": [design.get("scene_identity", "")],
                  "SCENE_COSTUME_ANCHORS": design.get("scene_anchors")}
        for section, values in fields.items():
            pattern = re.compile(rf"(<!-- ZET:BEGIN {section} -->)(.*?)(<!-- ZET:END {section} -->)", re.DOTALL)
            match = pattern.search(text)
            if not match:
                raise CostumeWizardError(f"Shared costume template is missing {section} markers.")
            content = "\n\n" + self._bullets(values) + "\n\n"
            text = text[:match.start()] + match.group(1) + content + match.group(3) + text[match.end():]
        for label, value in {"Costume Name": name, "Character Name": character, "Character Phase": phase,
                             "Costume Role": design.get("costume_role", ""), "Footwear": design.get("footwear", ""),
                             "Footwear Contact": design.get("footwear_contact", "")}.items():
            clean_value = " ".join(str(value or "").splitlines()).strip()
            text = re.sub(rf"(?im)^{re.escape(label)}\s*:\s*.*$",
                          lambda _: f"{label}: `[{clean_value}]`", text, count=1)
        return text.rstrip() + "\n"

    def _validate(self, markdown: str) -> list[str]:
        try:
            self.app.costume_service._validate_costume_markdown(markdown)
            with tempfile.TemporaryDirectory(prefix="zet_costume_wizard_validate_") as temp:
                template_path = Path(temp) / "Costume.md"
                template_path.write_text(markdown, encoding="utf-8")
                sections, sources = load_template_sections_with_sources(template_path)
            for view in ("FRONT", "BACK"):
                condition_sections(sections, sources, ViewContext(body_view=view, head_view=view))
        except Exception as exc:
            return [str(exc)]
        return []

    def update_draft(self, session_id: str, expected_revision: str, markdown: str) -> dict:
        with self._lock(session_id):
            session = self._read(session_id)
            if session.get("revision_id") != expected_revision:
                raise CostumeWizardError("This draft changed. Reload it before saving your edits.")
            errors = self._validate(markdown)
            session.update(markdown=markdown, revision_id=uuid4().hex, validation_errors=errors,
                           status="DRAFT_READY", draft_review="", refinements=[], updated_at=self._now())
            self._write(session_id, session)
        return self.get_session(session_id)

    def render_test(self, session_id: str, expected_revision: str) -> dict:
        with self._lock(session_id):
            session = self._read(session_id)
            if session.get("revision_id") != expected_revision:
                raise CostumeWizardError("This draft changed. Save or reload the current revision before testing it.")
            errors = self._validate(session.get("markdown", ""))
            if errors:
                raise CostumeWizardError("Fix template validation errors before testing: " + "; ".join(errors))
            session.update(status="RENDERING", test_image_path="", review="",
                           job={"kind": "render", "status": "RUNNING", "error": ""}, updated_at=self._now())
            self._write(session_id, session)
        self._submit(session_id, "render", self._render_job, session_id, expected_revision)
        return self.get_session(session_id)

    def _render_job(self, session_id: str, expected_revision: str) -> None:
        session = self._read(session_id)
        sid_root = self._session_root(session_id)
        render_id = uuid4().hex
        work_root = sid_root / "renders" / render_id
        character_root = work_root / "Characters"
        phase_root = character_root / session["character"] / session["phase"]
        phase_root.mkdir(parents=True, exist_ok=True)
        source_template = self.app.path_service.character_template_path(session["character"], session["phase"])
        if not source_template.is_file():
            raise CostumeWizardError("A valid Character.md is required for a test render.")
        shutil.copy2(source_template, phase_root / "Character.md")
        name = f"Wizard_{session_id[:12]}"
        filename = "Costume_" + re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_") + ".md"
        (phase_root / filename).write_text(session["markdown"], encoding="utf-8")
        from dataclasses import replace
        runtime_app = copy.copy(self.app)
        runtime_app.config = replace(self.app.config, base_library_path=str(work_root),
                                     base_character_path=str(character_root))
        runtime_app.costume_template_status = lambda character, phase, costume: {"template_ready": True, "validation_errors": []}
        pipeline = LocalCharacterAssetPipelineService(runtime_app, self.project_root, "costume-dressing",
                                                      runs_root=work_root / "runs")
        pipeline.asset_store = self.app.local_asset_source_service.store
        run = pipeline.create_run({"character": session["character"], "phase": session["phase"], "costume": name,
                                   "front_count": 1, "other_count": 1, "front_only": True,
                                   "use_front_anchor": False})
        run_id = run["run_id"]
        pipeline.execute_run(run_id, views={"FRONT"}, candidate_ids={"F-001"}, costume=name, render_only=True)
        latest = pipeline.detail(run_id, name)
        candidate = next((item for item in latest.get("candidates", []) if item.get("candidate_id") == "F-001"), None)
        image_path = Path(str((candidate or {}).get("image_path") or ""))
        if not candidate or not image_path.is_file():
            raise CostumeWizardError(str(candidate.get("render_error") if candidate else "Front render did not produce an image."))
        source_images = session.get("image_paths", [])
        review = self._ask("Review this single FRONT Costume Dressing test. Compare it with the costume template and supplied costume references. "
                           "Report visible mismatches and preserve character identity. Do not invent details hidden by the FRONT view. "
                           "Return a concise review and actionable refinement suggestions.\nTemplate:\n" + session["markdown"],
                           _REVIEW_SCHEMA, [str(image_path), *source_images])
        with self._lock(session_id):
            current = self._read(session_id)
            if current.get("revision_id") != expected_revision or current.get("status") == "ABANDONED":
                return
            render_record = {"render_id": render_id, "revision_id": expected_revision, "test_image_path": str(image_path),
                             "review": review.get("review", ""), "refinements": review.get("refinements") or [],
                             "created_at": self._now()}
            renders = list(current.get("test_renders") or [])
            renders.append(render_record)
            current.update(status="TEST_READY", test_image_path=str(image_path), review=review.get("review", ""),
                           refinements=review.get("refinements") or [], test_renders=renders,
                           job={"kind": "render", "status": "COMPLETE", "error": ""},
                           updated_at=self._now())
            self._write(session_id, current)

    def test_image_path(self, session_id: str, render_id: str = "") -> Path:
        session = self._read(session_id)
        if render_id:
            render = next((item for item in session.get("test_renders", []) if item.get("render_id") == render_id), None)
            path = Path(str((render or {}).get("test_image_path") or ""))
        else:
            path = Path(str(session.get("test_image_path") or ""))
        if not path.is_file():
            raise CostumeWizardError("No test render is available yet.")
        return path

    def refine(self, session_id: str, expected_revision: str, instructions: str) -> dict:
        instructions = str(instructions or "").strip()
        if not instructions:
            raise CostumeWizardError("Enter refinement instructions.")
        with self._lock(session_id):
            session = self._read(session_id)
            if session.get("status") == "ABANDONED":
                raise CostumeWizardError("An abandoned costume wizard draft cannot be refined.")
            if session.get("revision_id") != expected_revision:
                raise CostumeWizardError("This draft changed. Reload it before refining.")
            session.update(status="REFINING", job={"kind": "refine", "status": "RUNNING", "error": ""}, updated_at=self._now())
            self._write(session_id, session)
        self._submit(session_id, "refine", self._refine_job, session_id, expected_revision, instructions)
        return self.get_session(session_id)

    def _refine_job(self, session_id: str, expected_revision: str, instructions: str) -> None:
        session = self._read(session_id)
        current_markdown = session.get("markdown") or ""
        review_images = list(session.get("image_paths") or [])
        latest_test = str(session.get("test_image_path") or "")
        if latest_test and Path(latest_test).is_file():
            review_images.append(latest_test)
        result = self._ask("Apply only these user-requested costume refinements to the current markdown. Preserve all metadata, "
                           "section markers, and unrelated text. Return the complete revised Markdown as JSON in a field named markdown.\n"
                           "User refinement: " + instructions + "\nCurrent markdown:\n" + current_markdown,
                           {"type": "object", "properties": {"markdown": {"type": "string"}},
                            "required": ["markdown"], "additionalProperties": False}, review_images)
        markdown = str(result.get("markdown") or "")
        errors = self._validate(markdown)
        with self._lock(session_id):
            current = self._read(session_id)
            if current.get("revision_id") != expected_revision:
                return
            current.update(markdown=markdown, revision_id=uuid4().hex, validation_errors=errors,
                           status="DRAFT_READY", refinements=[],
                           job={"kind": "refine", "status": "COMPLETE", "error": ""}, updated_at=self._now())
            self._write(session_id, current)

    def accept(self, session_id: str, expected_revision: str):
        with self._lock(session_id):
            session = self._read(session_id)
            if session.get("status") == "ABANDONED":
                raise CostumeWizardError("An abandoned costume wizard draft cannot be accepted.")
            if session.get("revision_id") != expected_revision:
                raise CostumeWizardError("This draft changed. Reload it before accepting.")
            errors = self._validate(session.get("markdown", ""))
            if errors:
                raise CostumeWizardError("Fix template validation errors before accepting: " + "; ".join(errors))
            result = self.app.create_costume(session["character"], session["phase"], session["name"], session["markdown"])
            session.update(status="ACCEPTED", accepted_path=result.costume.path, updated_at=self._now())
            self._write(session_id, session)
        return result

    def abandon(self, session_id: str) -> dict:
        with self._lock(session_id):
            session = self._read(session_id)
            if session.get("status") == "ACCEPTED":
                raise CostumeWizardError("An accepted costume cannot be abandoned.")
            session.update(status="ABANDONED", revision_id=uuid4().hex,
                           job={"kind": "", "status": "CANCELLED", "error": ""}, updated_at=self._now())
            self._write(session_id, session)
        return self.get_session(session_id)
