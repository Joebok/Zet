"""Explicit, candidate-backed Character.md proposals for Asset Containers."""
from __future__ import annotations

import difflib
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
from uuid import uuid4

from zet.services.atomic_file_service import write_json_atomic
from zet.services.character_asset_container_service import CharacterAssetContainerService
from zet.services.local_template_revision_service import LocalTemplateRevisionService, template_diff_rows
from zet.services.template_source_service import template_sources


class CharacterContainerTemplateError(ValueError):
    pass


class CharacterContainerTemplateService:
    PIPELINES = {"body-reference", "head-image", "head-image-edit", "character-assembly", "costume-dressing"}

    def __init__(self, app, project_root: str | Path):
        self.app = app
        self.project_root = Path(project_root).resolve()
        self.containers = CharacterAssetContainerService(app)

    @staticmethod
    def _hash(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def _proposal_path(self, scope: dict, proposal_id: str) -> Path:
        if len(proposal_id) != 32 or any(char not in "0123456789abcdef" for char in proposal_id):
            raise CharacterContainerTemplateError("Invalid template proposal identity.")
        root = self.containers._path(scope).parent / "template-proposals"
        return root / f"{proposal_id}.json"

    def _read(self, scope: dict, proposal_id: str) -> dict:
        path = self._proposal_path(scope, proposal_id)
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise CharacterContainerTemplateError("Template proposal is unavailable.") from exc
        if value.get("scope") != scope or value.get("proposal_id") != proposal_id:
            raise CharacterContainerTemplateError("Template proposal belongs to another Asset Container.")
        return value

    @staticmethod
    def _public(record: dict) -> dict:
        public = {key: value for key, value in record.items()
                  if key not in {"master_text", "proposed_text"}}
        public["diff_rows"] = template_diff_rows(record["master_text"], record["proposed_text"])
        public["diff"] = "".join(difflib.unified_diff(
            record["master_text"].splitlines(True), record["proposed_text"].splitlines(True),
            fromfile="Character.md (current master)", tofile="Character.md (proposal)"))
        return public

    def propose(self, character: str, phase: str, pipeline: str, costume: str,
                view: str, candidate_id: str, *, direction: str = "", model: str = "",
                expected_revision: int) -> dict:
        if pipeline not in self.PIPELINES:
            raise CharacterContainerTemplateError("Choose a character Asset Container.")
        if not isinstance(direction, str) or len(direction) > 20000:
            raise CharacterContainerTemplateError("Improvement direction must be text of at most 20,000 characters.")
        container = self.containers.detail(character, phase, pipeline, costume)
        if container["revision"] != expected_revision:
            raise CharacterContainerTemplateError("The container changed. Refresh before proposing a template edit.")
        board = container["boards"].get(view)
        candidate = (board or {}).get("candidates", {}).get(candidate_id)
        if not candidate or candidate_id not in board["slots"] or candidate.get("status") != "COMPLETE":
            raise CharacterContainerTemplateError("Choose a finished candidate from this view as evidence.")
        evidence = Path(str(candidate.get("image_path") or "")).resolve()
        if not evidence.is_relative_to(self.containers._path(container["scope"]).parent) or not evidence.is_file():
            raise CharacterContainerTemplateError("The candidate image is unavailable in this Asset Container.")
        request = candidate.get("render_request") or {}
        if (request.get("universe_id") != container["scope"]["universe_id"]
                or request.get("target_id") != f"{container['container_id']}:{view}"
                or request.get("candidate_id") != candidate_id):
            raise CharacterContainerTemplateError("Candidate production evidence does not match this view.")
        from zet.services.render_slot_service import verify_input
        try:
            verify_input({"references": request.get("inputs", [])})
        except (OSError, ValueError, KeyError) as exc:
            raise CharacterContainerTemplateError(f"Candidate input snapshots are unavailable: {exc}") from exc

        source = self.containers.governing_template(character, phase, pipeline, costume)
        raw = source.read_bytes()
        before = raw.decode("utf-8")
        source_hash = self._hash(raw)
        proposal_id = uuid4().hex
        directory = self._proposal_path(container["scope"], proposal_id).parent / proposal_id
        directory.mkdir(parents=True, exist_ok=False)
        evidence_copy = directory / f"evidence{evidence.suffix.lower()}"
        shutil.copy2(evidence, evidence_copy)
        evidence_hash = self._hash(evidence_copy.read_bytes())
        prompt = ("Review this finished character candidate and its exact submitted prompt. Suggest a focused revision to "
            "the editable Character.md source that could improve future renders. The image is evidence, not a target to "
            "recreate. Preserve intentional design, markers, placeholders, reference order, and all unrelated source text. "
            "Do not change character identity or add unsupported design facts. Return the complete replacement Character.md "
            "text only in the replacement field. If no justified edit exists, return the original text unchanged and explain.\n\n"
            f"Pipeline: {pipeline}; view: {view}; candidate: {candidate_id}; quality: {candidate.get('render_mode', 'draft')}\n"
            f"Operator direction: {direction}\nSubmitted prompt:\n{request.get('prompt') or candidate.get('prompt') or ''}\n\n"
            f"Current complete Character.md:\n{before}")
        schema = {"type": "object", "properties": {"summary": {"type": "string"},
            "rationale": {"type": "string"}, "replacement": {"type": "string"}},
            "required": ["summary", "rationale", "replacement"], "additionalProperties": False}
        from zet.services.llm_role_service import resolve_role_model
        selected_model = str(resolve_role_model(self.app.config, "character_prompt_review", model))
        try:
            answer, runtime = self.app.ai_proxy_service.ai_proxy_path_service.jobs.generate_json(
                selected_model, "", prompt, schema, [evidence_copy],
                task_type="character_template_revision", role="template_revision",
                render_context={"operation": "mixed", "bindings_owned_by_zet": True},
                workflow=pipeline, owner={"container_id": container["container_id"],
                    "candidate_id": candidate_id, "view": view, "proposal_id": proposal_id})
        except Exception:
            shutil.rmtree(directory, ignore_errors=True)
            raise
        try:
            if not isinstance(answer, dict) or any(not isinstance(answer.get(key), str)
                    for key in ("summary", "rationale", "replacement")):
                raise ValueError("Template review returned an invalid proposal.")
            replacement = answer["replacement"]
            LocalTemplateRevisionService._validate_text(before, replacement)
            LocalTemplateRevisionService._validate_owned(pipeline,
                {"source_path": str(source)}, before, replacement)
            from zet.services.template_validation_service import TemplateValidationService
            analysis = TemplateValidationService(self.app).analyze(source, replacement, "character")
            if analysis["diagnostics"]:
                errors = "; ".join(item["message"] for item in analysis["diagnostics"][:5])
                raise ValueError(f"Proposed template does not validate: {errors}")
            from zet.services.character_container_prompt_service import CharacterContainerPromptService
            provenance = request.get("provenance") or {}
            preview_dir = directory / "compiled" / view
            with template_sources([{"source_path": str(source), "text": replacement}]):
                preview = CharacterContainerPromptService(self.app, self.project_root).compile(
                    container["scope"], view, preview_dir, request.get("inputs", []),
                    apply_phase_change=provenance.get("apply_phase_change") is True,
                    assembly_style_mode=str(provenance.get("assembly_style_mode") or ""),
                    render_mode=str(candidate.get("render_mode") or "draft"))
        except Exception as exc:
            shutil.rmtree(directory, ignore_errors=True)
            raise CharacterContainerTemplateError(str(exc)) from exc
        record = {"schema_version": 1, "proposal_id": proposal_id,
            "container_id": container["container_id"], "scope": container["scope"],
            "pipeline": pipeline, "view": view, "candidate_id": candidate_id,
            "render_mode": candidate.get("render_mode", "draft"),
            "created_at": datetime.now().astimezone().isoformat(timespec="microseconds"),
            "status": "PROPOSED", "model": selected_model,
            "summary": answer["summary"], "rationale": answer["rationale"],
            "direction": direction, "evidence_path": str(evidence_copy),
            "evidence_sha256": evidence_hash, "submitted_prompt": str(request.get("prompt") or candidate.get("prompt") or ""),
            "master_path": str(source), "master_sha256": source_hash, "master_text": before,
            "proposed_text": replacement, "compiled_prompt": preview["prompt"],
            "compiled_references": preview["reference_inputs"], "template_revision_id": preview.get("template_revision_id", ""),
            "runtime": runtime}
        write_json_atomic(self._proposal_path(container["scope"], proposal_id), record)
        return self._public(record)

    def detail(self, character: str, phase: str, pipeline: str, costume: str,
               proposal_id: str) -> dict:
        scope = self.containers._scope(character, phase, pipeline, costume)
        return self._public(self._read(scope, proposal_id))

    def latest(self, character: str, phase: str, pipeline: str, costume: str) -> dict:
        scope = self.containers._scope(character, phase, pipeline, costume)
        root = self.containers._path(scope).parent / "template-proposals"
        records = []
        for path in root.glob("*.json") if root.is_dir() else ():
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if value.get("scope") == scope and value.get("proposal_id") == path.stem:
                records.append(value)
        records.sort(key=lambda value: value.get("created_at") or "", reverse=True)
        return {"proposal": self._public(records[0]) if records else None}

    def accept(self, character: str, phase: str, pipeline: str, costume: str,
               proposal_id: str, *, confirm: bool) -> dict:
        if confirm is not True:
            raise CharacterContainerTemplateError("Confirm the reviewed Character.md proposal before saving it.")
        scope = self.containers._scope(character, phase, pipeline, costume)
        path = self._proposal_path(scope, proposal_id)
        record = self._read(scope, proposal_id)
        if record.get("status") == "ACCEPTED":
            return self._public(record)
        if record.get("status") != "PROPOSED":
            raise CharacterContainerTemplateError("This template proposal is no longer available for acceptance.")
        evidence = Path(record["evidence_path"]).resolve()
        if (not evidence.is_relative_to(path.parent / proposal_id)
                or not evidence.is_file()
                or self._hash(evidence.read_bytes()) != record.get("evidence_sha256")):
            raise CharacterContainerTemplateError("The saved candidate evidence changed; create a new proposal.")
        current = Path(record["master_path"]).resolve()
        if not current.is_file():
            raise CharacterContainerTemplateError("The governing Character.md is unavailable.")
        current_hash = self._hash(current.read_bytes())
        if current_hash == self._hash(record["proposed_text"].encode("utf-8")):
            record.update(status="ACCEPTED", accepted_at=datetime.now().astimezone().isoformat(timespec="microseconds"))
            write_json_atomic(path, record)
            return self._public(record)
        if current_hash != record.get("master_sha256"):
            raise CharacterContainerTemplateError("Character.md changed since this proposal. Review the current master and create a new proposal.")
        from zet.services.source_editor_service import SourceEditorService
        result = SourceEditorService(self.app, self.project_root).save({
            "path": str(current), "editor_type": "markdown_file", "text": record["proposed_text"],
            "master_revision": current_hash})
        if result.get("status") != "SAVED":
            raise CharacterContainerTemplateError(result.get("message") or "The proposed Character.md could not be saved.")
        record.update(status="ACCEPTED", accepted_at=datetime.now().astimezone().isoformat(timespec="microseconds"),
                      accepted_master_sha256=result.get("master_revision", ""))
        write_json_atomic(path, record)
        return self._public(record)
